import os
import shutil
import tempfile
import logging

from subtitle_bot.config import TEMP_DIR

logger = logging.getLogger(__name__)


def make_job_dir() -> str:
    """Create a temporary directory for one processing job."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    job_dir = tempfile.mkdtemp(dir=TEMP_DIR)
    logger.debug("Created job dir: %s", job_dir)
    return job_dir


def cleanup(job_dir: str) -> None:
    """Remove the temporary job directory and all its contents."""
    try:
        shutil.rmtree(job_dir, ignore_errors=True)
        logger.debug("Cleaned up job dir: %s", job_dir)
    except Exception as e:
        logger.warning("Failed to clean up %s: %s", job_dir, e)
