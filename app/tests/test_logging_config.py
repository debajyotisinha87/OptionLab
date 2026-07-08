import io
import logging
import logging.handlers
import sys

from app.config.config import LOG_DIR
from app.config.logging_config import TqdmLoggingHandler, get_logger


def test_get_logger_is_idempotent():

    logger = get_logger()
    handler_count = len(logger.handlers)

    logger_again = get_logger()

    assert logger_again is logger
    assert len(logger_again.handlers) == handler_count


def test_get_logger_has_a_console_and_file_handler():

    logger = get_logger()

    handler_types = [type(handler) for handler in logger.handlers]

    assert TqdmLoggingHandler in handler_types
    assert logging.handlers.RotatingFileHandler in handler_types


def test_logger_writes_to_the_log_file():

    logger = get_logger()

    log_file = LOG_DIR / "optionlab.log"

    # The log file persists (append mode, no reset) across every run on
    # this machine, so a plain "marker in contents" check would pass
    # even if this run's logger.info() call were a complete no-op -
    # only bytes appended after this point can prove causation.
    offset_before = log_file.stat().st_size if log_file.exists() else 0

    marker = "TEST_LOGGING_CONFIG_MARKER"
    logger.info(marker)

    for handler in logger.handlers:

        if isinstance(handler, logging.FileHandler):

            handler.flush()

    assert log_file.exists()

    with log_file.open("r", encoding="utf-8") as f:

        f.seek(offset_before)
        new_contents = f.read()

    assert marker in new_contents


def test_tqdm_logging_handler_emit_does_not_raise():

    handler = TqdmLoggingHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="a plain ASCII message",
        args=None,
        exc_info=None,
    )

    # must not raise
    handler.emit(record)


def test_tqdm_logging_handler_emit_replaces_unencodable_characters():

    # Simulates this dev machine's cp1252 console receiving a
    # non-ASCII exception message (e.g. a broker error string) without
    # crashing or falling back to a "--- Logging error ---" dump.
    handler = TqdmLoggingHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="CALL download failed: bad response ₹100",
        args=None,
        exc_info=None,
    )

    original_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        handler.emit(record)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = original_stdout

    assert "Logging error" not in output
    assert "CALL download failed" in output


def test_get_logger_console_handler_writes_through_tqdm():

    # Exercises the real singleton logger end-to-end (get_logger() ->
    # TqdmLoggingHandler -> tqdm.write() -> stdout), not just a
    # hand-built handler instance, so a broken setFormatter()/handler
    # wiring in get_logger() would actually be caught.
    logger = get_logger()

    marker = "CONSOLE_HANDLER_INTEGRATION_MARKER"

    original_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        logger.info(marker)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = original_stdout

    assert marker in output
    assert "[INFO]" in output


if __name__ == "__main__":

    test_get_logger_is_idempotent()
    test_get_logger_has_a_console_and_file_handler()
    test_logger_writes_to_the_log_file()
    test_tqdm_logging_handler_emit_does_not_raise()
    test_tqdm_logging_handler_emit_replaces_unencodable_characters()
    test_get_logger_console_handler_writes_through_tqdm()

    print("Logging config tests passed")
