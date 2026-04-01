import asyncio
import logging
import os
from typing import Any

import ffmpeg
from faster_whisper import WhisperModel

from subtitle_bot.config import WHISPER_MODEL

logger = logging.getLogger(__name__)

# Model is loaded once and reused for every request
_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        logger.info("Loading faster-whisper model '%s' (int8, CPU)...", WHISPER_MODEL)
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        logger.info("Model loaded.")
    return _model


def _extract_audio(video_path: str, audio_path: str) -> None:
    """Extract mono 16 kHz WAV audio — optimal format for Whisper."""
    (
        ffmpeg
        .input(video_path)
        .output(audio_path, vn=None, ar=16000, ac=1, acodec="pcm_s16le")
        .overwrite_output()
        .run(quiet=True)
    )


def _run_transcribe(audio_path: str) -> tuple[list[dict], str]:
    model = _get_model()
    # vad_filter=True uses Voice Activity Detection — skips silence,
    # eliminates hallucinations without extra parameters
    segments_iter, info = model.transcribe(
        audio_path,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )
    segments = [
        {"start": s.start, "end": s.end, "text": s.text}
        for s in segments_iter
    ]
    return segments, info.language


async def transcribe(video_path: str, job_dir: str) -> tuple[list[dict], str]:
    """
    Extract audio from video and transcribe with faster-whisper.

    Returns:
        segments: list of {"start": float, "end": float, "text": str}
        language: detected language code, e.g. "ru", "en"
    """
    audio_path = os.path.join(job_dir, "audio.wav")

    logger.info("Extracting audio from %s", video_path)
    await asyncio.get_event_loop().run_in_executor(
        None, _extract_audio, video_path, audio_path
    )

    logger.info("Transcribing with faster-whisper '%s'...", WHISPER_MODEL)
    segments, language = await asyncio.get_event_loop().run_in_executor(
        None, _run_transcribe, audio_path
    )

    try:
        os.remove(audio_path)
    except OSError:
        pass

    logger.info("Done. Language: %s, segments: %d", language, len(segments))
    return segments, language


def preload() -> None:
    """Pre-load model at bot startup so the first request isn't slow."""
    _get_model()
