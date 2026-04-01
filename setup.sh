#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup.sh — One-shot server setup for the Telegram Subtitle Bot
# Tested on Ubuntu 22.04 / Debian 12
# Run as root: bash setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 0. Root check ─────────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || error "Run this script as root (sudo bash setup.sh)"

# ── 1. System update ──────────────────────────────────────────────────────────
info "Updating system packages..."
apt-get update -qq && apt-get upgrade -y -qq

# ── 2. Install Docker ─────────────────────────────────────────────────────────
if command -v docker &>/dev/null; then
    info "Docker already installed: $(docker --version)"
else
    info "Installing Docker..."
    apt-get install -y -qq ca-certificates curl gnupg lsb-release
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    info "Docker installed: $(docker --version)"
fi

# ── 3. Install docker compose plugin ──────────────────────────────────────────
if docker compose version &>/dev/null 2>&1; then
    info "docker compose already available: $(docker compose version)"
else
    info "Installing docker-compose-plugin..."
    apt-get install -y -qq docker-compose-plugin
fi

# ── 4. Expand /dev/shm for large video processing (default is 50% RAM) ────────
RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
# Use 80% of RAM for /dev/shm
SHM_GB=$(( RAM_KB * 80 / 100 / 1024 / 1024 ))
[[ $SHM_GB -lt 2 ]] && SHM_GB=2   # minimum 2 GB

info "Remounting /dev/shm with size=${SHM_GB}g (80% of RAM)..."
mount -o remount,size=${SHM_GB}g /dev/shm || warn "Could not remount /dev/shm — using default size"

# Make it persistent across reboots
if ! grep -q "tmpfs /dev/shm" /etc/fstab; then
    echo "tmpfs /dev/shm tmpfs defaults,size=${SHM_GB}g 0 0" >> /etc/fstab
    info "Added /dev/shm mount to /etc/fstab"
fi

# ── 5. Create .env if missing ─────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f .env ]]; then
    if [[ -f .env.example ]]; then
        cp .env.example .env
        warn ".env created from .env.example"
        warn "Fill in BOT_TOKEN, TELEGRAM_API_ID, TELEGRAM_API_HASH before starting!"
    else
        error ".env.example not found. Are you running this from the project root?"
    fi
else
    info ".env already exists — skipping copy"
fi

# ── 6. Check that required vars are set ───────────────────────────────────────
source .env 2>/dev/null || true

missing=()
[[ -z "${BOT_TOKEN:-}"        ]] && missing+=("BOT_TOKEN")
[[ -z "${TELEGRAM_API_ID:-}"  ]] && missing+=("TELEGRAM_API_ID")
[[ -z "${TELEGRAM_API_HASH:-}"] && missing+=("TELEGRAM_API_HASH")

if [[ ${#missing[@]} -gt 0 ]]; then
    warn "The following variables are not set in .env:"
    for v in "${missing[@]}"; do warn "  - $v"; done
    warn "Edit .env and then run:  docker compose up -d --build"
    exit 0
fi

# ── 7. Build and start ────────────────────────────────────────────────────────
info "Building and starting containers..."
docker compose up -d --build

info ""
info "✅ Done! Bot is running."
info "   Logs:    docker compose logs -f subtitle-bot"
info "   Stop:    docker compose down"
info "   Restart: docker compose restart subtitle-bot"
