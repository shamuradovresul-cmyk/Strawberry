import asyncio
import logging
import os

from telegram import Update, Message
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from subtitle_bot.config import MAX_VIDEO_DURATION
from subtitle_bot.services import transcriber, translator, renderer
from subtitle_bot.utils.temp import make_job_dir, cleanup

logger = logging.getLogger(__name__)


async def _edit(msg: Message, text: str) -> None:
    """Silently edit a status message, ignoring errors if message hasn't changed."""
    try:
        await msg.edit_text(text)
    except TelegramError:
        pass


async def _process_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    status_msg: Message,
    video_file_id: str,
    duration: int,
) -> None:
    job_dir = make_job_dir()
    video_path = os.path.join(job_dir, "input.mp4")

    try:
        # 1. Download
        await _edit(status_msg, "⬇️ Скачиваю видео...")
        tg_file = await context.bot.get_file(video_file_id)
        await tg_file.download_to_drive(video_path)
        logger.info("Video downloaded to %s (%d MB)", video_path,
                    os.path.getsize(video_path) // 1_048_576)

        # 2. Transcribe
        await _edit(status_msg, "🎙 Распознаю речь...\n_(это может занять несколько минут)_")
        segments, language = await transcriber.transcribe(video_path, job_dir)

        if not segments:
            await _edit(status_msg, "❌ В видео не обнаружена речь. Субтитры не созданы.")
            return

        # 3. Translate if needed
        if language != "ru":
            await _edit(
                status_msg,
                f"🌐 Перевожу субтитры с `{language}` на русский..."
            )
        segments = await translator.translate_segments(segments, language)

        # 4. Render
        await _edit(status_msg, "🎬 Рендерю субтитры в видео...")
        output_path = await renderer.render(video_path, segments, job_dir)

        # 5. Send
        await _edit(status_msg, "📤 Отправляю готовое видео...")
        with open(output_path, "rb") as f:
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=f,
                duration=duration,
                caption="✅ Субтитры готовы!",
                supports_streaming=True,
            )

        await status_msg.delete()

    except Exception as e:
        logger.exception("Error processing video")
        await _edit(status_msg, f"❌ Ошибка при обработке видео:\n<code>{e}</code>")

    finally:
        cleanup(job_dir)


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point: handles VIDEO and video Document messages."""
    msg = update.effective_message

    # Extract video object — could be a Video or a Document
    video = msg.video
    doc = msg.document

    if video:
        file_id = video.file_id
        duration = video.duration or 0
    elif doc and doc.mime_type and doc.mime_type.startswith("video/"):
        file_id = doc.file_id
        duration = 0  # documents don't expose duration
    else:
        return

    # Validate duration
    if duration and duration > MAX_VIDEO_DURATION:
        minutes = MAX_VIDEO_DURATION // 60
        await msg.reply_text(
            f"⚠️ Видео слишком длинное. Максимальная длительность — {minutes} минут."
        )
        return

    # Acknowledge and start processing
    status_msg = await msg.reply_text("⏳ Принял видео, начинаю обработку...")

    asyncio.create_task(
        _process_video(update, context, status_msg, file_id, duration)
    )
