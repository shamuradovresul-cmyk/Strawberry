import asyncio
import logging

from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

# Languages that Whisper may detect — mapped to deep-translator codes
# GoogleTranslator uses ISO 639-1 codes, same as Whisper
_RUSSIAN = "ru"


def _translate_batch(texts: list[str], src_lang: str) -> list[str]:
    """Translate a list of texts from src_lang to Russian in one batch call."""
    translator = GoogleTranslator(source=src_lang, target=_RUSSIAN)
    translated = []
    for text in texts:
        t = text.strip()
        if not t:
            translated.append(t)
            continue
        try:
            translated.append(translator.translate(t) or t)
        except Exception as e:
            logger.warning("Translation failed for segment '%s': %s", t[:40], e)
            translated.append(t)
    return translated


async def translate_segments(
    segments: list[dict], src_lang: str
) -> list[dict]:
    """
    Translate subtitle segments to Russian if source language is not Russian.

    Args:
        segments: list of {"start", "end", "text"}
        src_lang: Whisper-detected language code

    Returns:
        Same list with "text" replaced by Russian translation (if needed).
    """
    if src_lang == _RUSSIAN:
        logger.info("Source is already Russian — skipping translation.")
        return segments

    logger.info("Translating %d segments from '%s' to Russian...", len(segments), src_lang)
    texts = [seg["text"] for seg in segments]

    translated_texts = await asyncio.get_event_loop().run_in_executor(
        None, _translate_batch, texts, src_lang
    )

    return [
        {**seg, "text": tr_text}
        for seg, tr_text in zip(segments, translated_texts)
    ]
