#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup.sh — Установка бота на чистый Ubuntu/Debian сервер
# Запускай от рута: bash setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

[[ $EUID -eq 0 ]] || err "Запусти скрипт от рута: sudo bash setup.sh"

# ── 1. Системные пакеты ───────────────────────────────────────────────────────
ok "Обновляю пакеты..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv ffmpeg git screen

ok "Системные пакеты установлены."

# ── 2. Папка проекта ──────────────────────────────────────────────────────────
PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJ_DIR"
ok "Папка проекта: $PROJ_DIR"

# ── 3. Python окружение ───────────────────────────────────────────────────────
if [[ ! -d venv ]]; then
    ok "Создаю виртуальное окружение Python..."
    python3 -m venv venv
fi

ok "Устанавливаю Python зависимости (может занять 2-5 минут)..."
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q
ok "Python зависимости установлены."

# ── 4. .env файл ──────────────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
    cp .env.example .env
    warn ".env создан. Открой его и вставь свой BOT_TOKEN:"
    warn "  nano .env"
    warn "После этого запусти бота: bash start.sh"
    exit 0
fi

ok ".env найден."

# ── 5. Создаём скрипт запуска ─────────────────────────────────────────────────
cat > start.sh << 'STARTSCRIPT'
#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "Запускаю бота в фоне (screen)..."
screen -dmS subtitle_bot venv/bin/python -m subtitle_bot.bot
echo ""
echo "Бот запущен!"
echo "  Логи:       screen -r subtitle_bot"
echo "  Выйти из логов: Ctrl+A затем D"
echo "  Остановить: screen -S subtitle_bot -X quit"
STARTSCRIPT
chmod +x start.sh

# ── 6. Запуск ─────────────────────────────────────────────────────────────────
ok "Запускаю бота..."
bash start.sh

ok ""
ok "Всё готово!"
ok "Проверь логи: screen -r subtitle_bot"
