import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]

# Optional: Local Bot API Server (needed only for files > 50 MB)
# Leave empty to use standard Telegram API
LOCAL_API_URL: str | None = os.getenv("LOCAL_API_URL") or None

WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "tiny")
MAX_VIDEO_DURATION: int = int(os.getenv("MAX_VIDEO_DURATION", "5400"))  # 90 min
TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/subtitle_bot")
