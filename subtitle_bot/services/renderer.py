import os
import asyncio
import logging

import ffmpeg

logger = logging.getLogger(__name__)


def _format_srt_time(seconds: float) -> str:
    """Convert float seconds to SRT timestamp format: HH:MM:SS,mmm"""
    ms = int(round(seconds * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1_000
    ms %= 1_000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _build_srt(segments: list[dict]) -> str:
    """Generate SRT file content from Whisper segments."""
    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        start = _format_srt_time(seg["start"])
        end = _format_srt_time(seg["end"])
        text = seg["text"].strip()
        if not text:
            continue
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def _burn_subtitles(video_path: str, srt_path: str, output_path: str) -> None:
    """Use FFmpeg to hard-burn subtitles into the video."""
    # Escape path for FFmpeg subtitles filter (Windows-safe too)
    escaped_srt = srt_path.replace("\\", "/").replace(":", "\\:")

    subtitle_style = (
        "Fontname=Arial,"
        "Fontsize=22,"
        "PrimaryColour=&H00FFFFFF,"   # white text
        "OutlineColour=&H00000000,"   # black outline
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=0,"
        "Alignment=2"                 # bottom-center
    )

    (
        ffmpeg
        .input(video_path)
        .output(
            output_path,
            vf=f"subtitles='{escaped_srt}':force_style='{subtitle_style}'",
            acodec="copy",
            vcodec="libx264",
            crf=23,
            preset="fast",
        )
        .overwrite_output()
        .run(quiet=True)
    )


async def render(
    video_path: str,
    segments: list[dict],
    job_dir: str,
) -> str:
    """
    Write SRT and burn subtitles into the video with FFmpeg.

    Returns:
        Path to the rendered output video (in job_dir, i.e. in RAM).
    """
    srt_path = os.path.join(job_dir, "subtitles.srt")
    output_path = os.path.join(job_dir, "output.mp4")

    logger.info("Writing SRT file: %s", srt_path)
    srt_content = _build_srt(segments)
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    logger.info("Burning subtitles into video...")
    await asyncio.get_event_loop().run_in_executor(
        None, _burn_subtitles, video_path, srt_path, output_path
    )
    logger.info("Rendering done: %s", output_path)
    return output_path
