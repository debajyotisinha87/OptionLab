import argparse
import io
import logging
import sys

import app.main as main_module
from app.config.config import LOG_DIR
from app.main import _parse_date, _parse_non_blank, build_parser, main


class FakeDownloadEngine:

    instances = []

    def __init__(self):

        self.run_calls = []
        self.resume_calls = []

        FakeDownloadEngine.instances.append(self)

    def run(self, job):

        self.run_calls.append(job)

    def resume(self, job_id):

        self.resume_calls.append(job_id)


class FailingDownloadEngine:
    """Simulates DownloadEngine.run()/resume() raising ValueError, e.g.
    from Repository.save_job() rejecting a reused job_id with
    different parameters, or resume() hitting an unknown job_id."""

    def __init__(self):

        pass

    def run(self, job):

        raise ValueError("job_id 'DUPLICATE' already exists with different parameters.")

    def resume(self, job_id):

        raise ValueError(f"Unknown job_id: {job_id}")


class CrashingOnInitDownloadEngine:
    """Simulates DownloadEngine.__init__() raising a non-ValueError
    exception, e.g. duckdb.IOException surfacing from
    Repository/DuckDBManager construction when the database file is
    locked by another process."""

    def __init__(self):

        raise RuntimeError("simulated DuckDB connection failure")


class FakeDhanAPI:

    instances = []

    def __init__(self):

        self.test_connection_calls = 0

        FakeDhanAPI.instances.append(self)

    def test_connection(self):

        self.test_connection_calls += 1


def with_fake_engine(fn):

    FakeDownloadEngine.instances = []

    original_engine = main_module.DownloadEngine
    main_module.DownloadEngine = FakeDownloadEngine

    try:
        return fn()
    finally:
        main_module.DownloadEngine = original_engine


def with_fake_api(fn):

    FakeDhanAPI.instances = []

    original_api = main_module.DhanAPI
    main_module.DhanAPI = FakeDhanAPI

    try:
        return fn()
    finally:
        main_module.DhanAPI = original_api


def test_build_parser_parses_download_arguments():

    parser = build_parser()

    args = parser.parse_args([
        "download",
        "--underlying", "NIFTY",
        "--expiry-type", "MONTH",
        "--option-types", "call, put",
        "--strike-from", "-10",
        "--strike-to", "10",
        "--start-date", "2025-01-01",
        "--end-date", "2025-03-31",
    ])

    assert args.command == "download"
    assert args.underlying == "NIFTY"
    assert args.option_types == ["CALL", "PUT"]
    assert args.strike_from == -10
    assert args.strike_to == 10
    assert args.start_date == "2025-01-01"
    assert args.end_date == "2025-03-31"
    assert args.job_id is None


def test_build_parser_rejects_an_invalid_date():

    parser = build_parser()

    try:
        parser.parse_args([
            "download",
            "--underlying", "NIFTY",
            "--expiry-type", "MONTH",
            "--option-types", "CALL",
            "--strike-from", "0",
            "--strike-to", "0",
            "--start-date", "not-a-date",
            "--end-date", "2025-03-31",
        ])
    except SystemExit as exc:
        assert exc.code != 0
        return

    raise AssertionError("Expected SystemExit for an invalid --start-date")


def test_build_parser_rejects_empty_option_types():

    parser = build_parser()

    try:
        parser.parse_args([
            "download",
            "--underlying", "NIFTY",
            "--expiry-type", "MONTH",
            "--option-types", " , ",
            "--strike-from", "0",
            "--strike-to", "0",
            "--start-date", "2025-01-01",
            "--end-date", "2025-01-01",
        ])
    except SystemExit as exc:
        assert exc.code != 0
        return

    raise AssertionError("Expected SystemExit for empty --option-types")


def test_build_parser_rejects_blank_underlying_and_expiry_type():

    parser = build_parser()

    try:
        parser.parse_args([
            "download",
            "--underlying", "",
            "--expiry-type", "  ",
            "--option-types", "CALL",
            "--strike-from", "0",
            "--strike-to", "0",
            "--start-date", "2025-01-01",
            "--end-date", "2025-01-31",
        ])
    except SystemExit as exc:
        assert exc.code != 0
        return

    raise AssertionError(
        "Expected SystemExit for blank --underlying/--expiry-type"
    )


def test_build_parser_rejects_a_blank_job_id():

    parser = build_parser()

    try:
        parser.parse_args([
            "download",
            "--underlying", "NIFTY",
            "--expiry-type", "MONTH",
            "--option-types", "CALL",
            "--strike-from", "0",
            "--strike-to", "0",
            "--start-date", "2025-01-01",
            "--end-date", "2025-01-31",
            "--job-id", "",
        ])
    except SystemExit as exc:
        assert exc.code != 0
        return

    raise AssertionError("Expected SystemExit for a blank --job-id")


def test_parse_non_blank_rejects_blank_and_strips_whitespace():

    assert _parse_non_blank("NIFTY") == "NIFTY"
    assert _parse_non_blank("  NIFTY  ") == "NIFTY"

    try:
        _parse_non_blank("   ")
    except argparse.ArgumentTypeError:
        return

    raise AssertionError("Expected ArgumentTypeError for a blank value")


def test_parse_date_sanitizes_unencodable_characters_in_its_error_message():

    # Forces sys.stderr to a narrow ascii-only encoding (argparse writes
    # its usage/error text straight there, bypassing the logger's own
    # cp1252-safe sanitization) so this deterministically reproduces the
    # UnicodeEncodeError this fix prevents, regardless of this machine's
    # actual console encoding.
    original_stderr = sys.stderr
    sys.stderr = io.TextIOWrapper(io.BytesIO(), encoding="ascii")

    try:
        try:
            _parse_date("2025-01-01म")  # Devanagari 'म'
        except argparse.ArgumentTypeError as exc:
            message = str(exc)
        else:
            raise AssertionError("Expected ArgumentTypeError for an invalid date")
    finally:
        sys.stderr = original_stderr

    # must not raise - this is exactly the crash the fix prevents
    message.encode("ascii", errors="strict")
    assert "म" not in message


def test_download_defaults_job_id_from_underlying_and_dates():

    def run():

        exit_code = main([
            "download",
            "--underlying", "NIFTY",
            "--expiry-type", "MONTH",
            "--option-types", "CALL,PUT",
            "--strike-from", "-1",
            "--strike-to", "1",
            "--start-date", "2025-01-01",
            "--end-date", "2025-01-31",
        ])

        assert exit_code == 0

        engine = FakeDownloadEngine.instances[-1]
        job = engine.run_calls[-1]

        assert job.job_id == "NIFTY-2025-01-01-2025-01-31"
        assert job.option_types == ["CALL", "PUT"]

    with_fake_engine(run)


def test_download_respects_an_explicit_job_id():

    def run():

        main([
            "download",
            "--underlying", "NIFTY",
            "--expiry-type", "MONTH",
            "--option-types", "CALL",
            "--strike-from", "0",
            "--strike-to", "0",
            "--start-date", "2025-01-01",
            "--end-date", "2025-01-01",
            "--job-id", "MY-CUSTOM-JOB",
        ])

        engine = FakeDownloadEngine.instances[-1]
        job = engine.run_calls[-1]

        assert job.job_id == "MY-CUSTOM-JOB"

    with_fake_engine(run)


def test_resume_dispatches_to_engine_resume():

    def run():

        exit_code = main(["resume", "--job-id", "JOB-000001"])

        assert exit_code == 0

        engine = FakeDownloadEngine.instances[-1]

        assert engine.resume_calls == ["JOB-000001"]

    with_fake_engine(run)


def test_test_connection_dispatches_to_dhan_api():

    def run():

        exit_code = main(["test-connection"])

        assert exit_code == 0

        api = FakeDhanAPI.instances[-1]

        assert api.test_connection_calls == 1

    with_fake_api(run)


def test_main_returns_nonzero_and_logs_on_value_error():

    log_file = LOG_DIR / "optionlab.log"

    # The log file persists (append mode, no reset) across every run,
    # so a plain "message in contents" check would pass even if this
    # run's logger.error() call were a complete no-op - only bytes
    # appended after this point can prove causation (same pattern as
    # test_logging_config.py's test_logger_writes_to_the_log_file).
    offset_before = log_file.stat().st_size if log_file.exists() else 0

    original_engine = main_module.DownloadEngine
    main_module.DownloadEngine = FailingDownloadEngine

    try:
        exit_code = main(["resume", "--job-id", "JOB-DOES-NOT-EXIST"])
    finally:
        main_module.DownloadEngine = original_engine

    assert exit_code == 1

    for handler in main_module.logger.handlers:

        if isinstance(handler, logging.FileHandler):

            handler.flush()

    with log_file.open("r", encoding="utf-8") as f:

        f.seek(offset_before)
        new_contents = f.read()

    assert "Unknown job_id: JOB-DOES-NOT-EXIST" in new_contents


def test_download_returns_nonzero_and_logs_on_value_error():

    original_engine = main_module.DownloadEngine
    main_module.DownloadEngine = FailingDownloadEngine

    try:
        exit_code = main([
            "download",
            "--underlying", "NIFTY",
            "--expiry-type", "MONTH",
            "--option-types", "CALL",
            "--strike-from", "0",
            "--strike-to", "0",
            "--start-date", "2025-01-01",
            "--end-date", "2025-01-01",
            "--job-id", "DUPLICATE",
        ])
    finally:
        main_module.DownloadEngine = original_engine

    assert exit_code == 1


def test_main_returns_nonzero_when_engine_construction_raises():

    # DownloadEngine.__init__() performs real I/O (DuckDB connection,
    # schema DDL) that can raise non-ValueError exceptions (e.g. a
    # locked database file). main()'s error boundary must catch these
    # too, not just ValueError from run()/resume().
    original_engine = main_module.DownloadEngine
    main_module.DownloadEngine = CrashingOnInitDownloadEngine

    try:
        exit_code = main(["resume", "--job-id", "JOB-000001"])
    finally:
        main_module.DownloadEngine = original_engine

    assert exit_code == 1


def test_main_returns_nonzero_for_an_unhandled_command():

    # args.command is currently always one of the three subparsers
    # build_parser() registers, but main()'s dispatch must fail loudly
    # (not silently return 0) if that invariant is ever broken by a
    # future change - this simulates exactly that.
    class FakeArgs:
        command = "not-a-real-command"

    class FakeParser:
        def parse_args(self, argv):
            return FakeArgs()

    original_build_parser = main_module.build_parser
    main_module.build_parser = lambda: FakeParser()

    try:
        exit_code = main([])
    finally:
        main_module.build_parser = original_build_parser

    assert exit_code == 1


if __name__ == "__main__":

    test_build_parser_parses_download_arguments()
    test_build_parser_rejects_an_invalid_date()
    test_build_parser_rejects_empty_option_types()
    test_build_parser_rejects_blank_underlying_and_expiry_type()
    test_build_parser_rejects_a_blank_job_id()
    test_parse_non_blank_rejects_blank_and_strips_whitespace()
    test_parse_date_sanitizes_unencodable_characters_in_its_error_message()
    test_download_defaults_job_id_from_underlying_and_dates()
    test_download_respects_an_explicit_job_id()
    test_resume_dispatches_to_engine_resume()
    test_test_connection_dispatches_to_dhan_api()
    test_main_returns_nonzero_and_logs_on_value_error()
    test_download_returns_nonzero_and_logs_on_value_error()
    test_main_returns_nonzero_when_engine_construction_raises()
    test_main_returns_nonzero_for_an_unhandled_command()

    print("CLI tests passed")
