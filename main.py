"""
Бот приёма заказов — Клубника в шоколаде 🍓
Запуск: python main.py
"""

import logging
import os
from telegram.ext import Application, MessageHandler, filters
from dotenv import load_dotenv

import db
from handlers.client import get_client_conversation
from handlers.admin import get_admin_handlers, handle_admin_text

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("STRAWBERRY_BOT_TOKEN")
OWNER_ID  = int(os.getenv("OWNER_ID", "0"))


async def text_router(update, context):
    """Роутер текстовых сообщений — сначала проверяем админа, потом клиента."""
    if await handle_admin_text(update, context):
        return
    # Если не админ — ConversationHandler сам разберётся


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан в .env!")

    # Инициализируем БД
    db.init_db()

    # Добавляем владельца если его ещё нет
    if OWNER_ID and not db.is_admin(OWNER_ID):
        db.add_admin(OWNER_ID, "Владелец", role="owner")
        logger.info(f"Владелец добавлен: {OWNER_ID}")

    app = Application.builder().token(BOT_TOKEN).build()

    # Сначала ConversationHandler клиента (он перехватывает /start и кнопки)
    app.add_handler(get_client_conversation())

    # Затем хендлеры админа
    for handler in get_admin_handlers():
        app.add_handler(handler)

    # Текстовый роутер для кнопок админки и пересылки сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    logger.info("🍓 Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()