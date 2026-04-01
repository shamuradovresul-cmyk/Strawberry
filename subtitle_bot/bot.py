import asyncio
import logging

from telegram.ext import Application, MessageHandler, filters

from subtitle_bot.config import BOT_TOKEN, LOCAL_API_URL
from subtitle_bot.handlers.video import handle_video
from subtitle_bot.services.transcriber import preload as preload_whisper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _on_startup(app: Application) -> None:
    logger.info("Pre-loading Whisper model...")
    await asyncio.get_event_loop().run_in_executor(None, preload_whisper)
    logger.info("Whisper model ready.")
    app.bot_data["semaphore"] = asyncio.Semaphore(1)


def main() -> None:
    builder = Application.builder().token(BOT_TOKEN)

    if LOCAL_API_URL:
        # Local Bot API Server — no file size limits
        logger.info("Using Local Bot API Server: %s", LOCAL_API_URL)
        builder = (
            builder
            .base_url(f"{LOCAL_API_URL}/bot")
            .base_file_url(f"{LOCAL_API_URL}/file/bot")
            .local_mode(True)
        )
    else:
        # Standard Telegram API — files limited to 50 MB
        logger.info("Using standard Telegram API (50 MB file limit)")

    app = builder.post_init(_on_startup).build()

    app.add_handler(
        MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video)
    )

    logger.info("Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
