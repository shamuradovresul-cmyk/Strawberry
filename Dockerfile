FROM python:3.11-slim

# Install system dependencies: ffmpeg + fonts for subtitles
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-liberation \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project source
COPY subtitle_bot/ subtitle_bot/

# Temp files live in RAM (/dev/shm), not on disk
ENV TEMP_DIR=/dev/shm/subtitle_bot

CMD ["python", "-m", "subtitle_bot.bot"]
