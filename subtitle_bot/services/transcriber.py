import os
import logging
import asyncio
from functools import partial
from typing import Any

import ffmpeg
import whisper

from subtitle_bot.config import WHISPER_MODEL

logger = logging.getLogger(__name__)

# Load model once at module import time — stays in RAM
_model: whisper.Whisper | None = None


def _get_model() -> whisper.Whisper:
    global _model
    if _model is None:
        logger.info("Loading Whisper model '%s'...", WHISPER_MODEL)
        _model = whisper.load_model(WHISPER_MODEL)
        logger.info("Whisper model loaded.")
    return _model


def _extract_audio(video_path: str, audio_path: str) -> None:
    """Extract mono 16kHz WAV audio from video — required by Whisper."""
    (
        ffmpeg
        .input(video_path)
        .output(audio_path, vn=None, ar=16000, ac=1, acodec="pcm_s16le")
        .overwrite_output()
        .run(quiet=True)
    )


def _run_transcribe(audio_path: str) -> dict[str, Any]:
    model = _get_model()
    return model.transcribe(
        audio_path,
        task="transcribe",
        verbose=False,
        # Suppress hallucinations during silence/music
        no_speech_threshold=0.6,
        logprob_threshold=-1.0,
    )


def preload() -> None:
    """Pre-load the Whisper model at bot startup so the first request isn't slow."""
    _get_model()


async def transcribe(video_path: str, job_dir: str) -> tuple[list[dict], str]:
    """
    Extract audio from video and transcribe with Whisper.

    Returns:
        segments: list of {"start": float, "end": float, "text": str}
        language: detected language code, e.g. "ru", "en"
    """
    audio_path = os.path.join(job_dir, "audio.wav")

    logger.info("Extracting audio from %s", video_path)
    await asyncio.get_event_loop().run_in_executor(
        None, _extract_audio, video_path, audio_path
    )

    logger.info("Transcribing audio with Whisper model '%s'...", WHISPER_MODEL)
    result = await asyncio.get_event_loop().run_in_executor(
        None, _run_transcribe, audio_path
    )

    os.remove(audio_path)

    segments: list[dict] = [
        {"start": seg["start"], "end": seg["end"], "text": seg["text"]}
        for seg in result["segments"]
    ]
    language: str = result.get("language", "unknown")
    logger.info("Transcription done. Language: %s, segments: %d", language, len(segments))
    return segments, language
