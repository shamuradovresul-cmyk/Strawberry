#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup.sh — Установка бота на чистый Ubuntu/Debian сервер
# Запускай от рута: sudo bash setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
info() { echo -e "${CYAN}[..]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

[[ $EUID -eq 0 ]] || err "Запусти скрипт от рута: sudo bash setup.sh"

PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJ_DIR"

echo ""
echo "=========================================="
echo "  Установка Telegram Subtitle Bot"
echo "=========================================="
echo ""

# ── 1. Системные пакеты ───────────────────────────────────────────────────────
info "Устанавливаю системные пакеты..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv ffmpeg git screen curl ca-certificates
ok "Системные пакеты готовы."

# ── 2. Docker ─────────────────────────────────────────────────────────────────
if command -v docker &>/dev/null; then
    ok "Docker уже установлен: $(docker --version | head -1)"
else
    info "Устанавливаю Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    ok "Docker установлен."
fi

# ── 3. .env файл ──────────────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
    cp .env.example .env
    echo ""
    warn "══════════════════════════════════════════════════"
    warn " Нужно заполнить .env перед запуском!"
    warn "══════════════════════════════════════════════════"
    echo ""
    echo " Открой файл командой:"
    echo "   nano $PROJ_DIR/.env"
    echo ""
    echo " Вставь три значения:"
    echo "   BOT_TOKEN      — токен от @BotFather"
    echo "   TELEGRAM_API_ID   — с сайта my.telegram.org"
    echo "   TELEGRAM_API_HASH — с сайта my.telegram.org"
    echo ""
    echo " После заполнения запусти снова:"
    echo "   sudo bash $PROJ_DIR/setup.sh"
    echo ""
    exit 0
fi

# ── 4. Проверка заполненности .env ────────────────────────────────────────────
source .env 2>/dev/null || true

missing=()
[[ -z "${BOT_TOKEN:-}"        ]] && missing+=("BOT_TOKEN")
[[ -z "${TELEGRAM_API_ID:-}"  ]] && missing+=("TELEGRAM_API_ID")
[[ -z "${TELEGRAM_API_HASH:-}" ]] && missing+=("TELEGRAM_API_HASH")

if [[ ${#missing[@]} -gt 0 ]]; then
    echo ""
    warn "В .env не заполнены обязательные поля:"
    for v in "${missing[@]}"; do
        warn "  ✗ $v"
    done
    echo ""
    echo " Открой файл: nano $PROJ_DIR/.env"
    echo " Затем запусти снова: sudo bash $PROJ_DIR/setup.sh"
    echo ""
    exit 1
fi
ok ".env заполнен."

# ── 5. Запуск Local Telegram Bot API Server ───────────────────────────────────
info "Запускаю Local Telegram Bot API Server (Docker)..."
docker compose up -d

# Ждём пока сервер поднимется
info "Жду запуска API сервера (10 сек)..."
sleep 10

if docker compose ps | grep -q "running\|Up"; then
    ok "Telegram Bot API Server запущен на порту 8081."
else
    warn "Контейнер мог не стартовать. Проверь: docker compose logs telegram-bot-api"
fi

# ── 6. Python окружение ───────────────────────────────────────────────────────
if [[ ! -d venv ]]; then
    info "Создаю виртуальное окружение Python..."
    python3 -m venv venv
fi

info "Устанавливаю Python зависимости (может занять 3-5 минут, скачивается Whisper)..."
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q
ok "Python зависимости установлены."

# ── 7. Скрипт запуска/остановки ───────────────────────────────────────────────
cat > start.sh << STARTSCRIPT
#!/usr/bin/env bash
cd "\$(dirname "\$0")"
if screen -list | grep -q "subtitle_bot"; then
    echo "Бот уже запущен. Логи: screen -r subtitle_bot"
    exit 0
fi
venv/bin/python -m subtitle_bot.bot &> /tmp/subtitle_bot.log &
echo "Бот запущен. Логи: tail -f /tmp/subtitle_bot.log"
STARTSCRIPT

cat > stop.sh << STOPSCRIPT
#!/usr/bin/env bash
pkill -f "subtitle_bot.bot" && echo "Бот остановлен." || echo "Бот не запущен."
STOPSCRIPT

chmod +x start.sh stop.sh

# ── 8. Запуск бота ────────────────────────────────────────────────────────────
info "Запускаю бота..."

# Останавливаем старый процесс если есть
pkill -f "subtitle_bot.bot" 2>/dev/null || true
sleep 1

# Запускаем в фоне через screen
screen -dmS subtitle_bot bash -c "cd $PROJ_DIR && venv/bin/python -m subtitle_bot.bot 2>&1 | tee /tmp/subtitle_bot.log"

sleep 3

if screen -list | grep -q "subtitle_bot"; then
    ok "Бот запущен в фоне!"
else
    warn "Проверь логи: tail -f /tmp/subtitle_bot.log"
fi

# ── 9. Итог ───────────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
ok " Установка завершена!"
echo "=========================================="
echo ""
echo " Полезные команды:"
echo "   Логи бота:          screen -r subtitle_bot"
echo "   Выйти из логов:     Ctrl+A затем D"
echo "   Остановить бота:    bash $PROJ_DIR/stop.sh"
echo "   Перезапустить бота: bash $PROJ_DIR/stop.sh && bash $PROJ_DIR/start.sh"
echo "   Логи API сервера:   docker compose logs -f telegram-bot-api"
echo ""
