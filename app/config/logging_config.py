"""
Logging Configuration

Shared application logger: a tqdm-safe console handler (routes
through tqdm.write() so it can't corrupt a live progress bar) plus a
rotating file handler under LOG_DIR for a persistent record of each run.
"""

import logging
import logging.handlers
import sys

from tqdm import tqdm

from app.config.config import LOG_DIR

LOGGER_NAME = "optionlab"

LOG_FILE_MAX_BYTES = 5_000_000
LOG_FILE_BACKUP_COUNT = 5


class TqdmLoggingHandler(logging.Handler):
    """Routes log records through tqdm.write() so console output can't
    corrupt a live progress bar.

    Downloaded/API error text can contain arbitrary, non-ASCII
    characters (e.g. a broker error message). This dev machine's
    console is cp1252, so messages are re-encoded for whatever stream
    tqdm.write() resolves to at call time before it reaches sys.stdout,
    or a single bad character replaces a clean log line with a
    "--- Logging error ---" traceback dump.
    """

    def emit(self, record):

        try:

            message = self.format(record)
            encoding = getattr(sys.stdout, "encoding", None) or "ascii"
            safe_message = message.encode(
                encoding, errors="replace"
            ).decode(encoding)

            tqdm.write(safe_message)

        except Exception:

            self.handleError(record)


def get_logger() -> logging.Logger:

    logger = logging.getLogger(LOGGER_NAME)

    if logger.handlers:

        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(module)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = TqdmLoggingHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "optionlab.log",
        maxBytes=LOG_FILE_MAX_BYTES,
        backupCount=LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
