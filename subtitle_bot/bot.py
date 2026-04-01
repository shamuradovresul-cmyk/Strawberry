import logging

from telegram.ext import Application, MessageHandler, filters

from subtitle_bot.config import BOT_TOKEN, LOCAL_API_URL
from subtitle_bot.handlers.video import handle_video

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting subtitle bot (local API: %s)", LOCAL_API_URL)

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .base_url(f"{LOCAL_API_URL}/bot")
        .base_file_url(f"{LOCAL_API_URL}/file/bot")
        .local_mode(True)
        .build()
    )

    # Accept both native video and video sent as document (file)
    app.add_handler(
        MessageHandler(
            filters.VIDEO | filters.Document.VIDEO,
            handle_video,
        )
    )

    logger.info("Bot is running. Waiting for videos...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
