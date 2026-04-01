import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
TELEGRAM_API_ID: str = os.environ["TELEGRAM_API_ID"]
TELEGRAM_API_HASH: str = os.environ["TELEGRAM_API_HASH"]
LOCAL_API_URL: str = os.getenv("LOCAL_API_URL", "http://telegram-bot-api:8081")

WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "medium")
MAX_VIDEO_DURATION: int = int(os.getenv("MAX_VIDEO_DURATION", "5400"))  # 90 min
TEMP_DIR: str = os.getenv("TEMP_DIR", "/dev/shm/subtitle_bot")
