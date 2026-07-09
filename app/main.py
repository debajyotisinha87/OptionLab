"""
Application Entry Point

Single CLI entry point for OptionLab: verify DhanHQ connectivity, start
a new historical options download job, or resume an existing one.
"""

import argparse
import sys
from datetime import datetime

from app import validation
from app.api.api_client import DhanAPI
from app.autosync.sync_planner import SyncPlanner
from app.builders.payload_builder import PayloadBuilder
from app.config.logging_config import get_logger
from app.constants.app_info import (
    APP_NAME,
    APP_VERSION,
)
from app.constants.underlyings import SUPPORTED_UNDERLYINGS
from app.downloader.download_engine import DownloadEngine
from app.models.job import DownloadJob

logger = get_logger()

DATE_FORMAT = validation.DATE_FORMAT


def banner():

    logger.info("=" * 60)
    logger.info(f"{APP_NAME}  v{APP_VERSION}")
    logger.info("=" * 60)


def _sanitize_for_stderr(value: str) -> str:
    """argparse writes ArgumentTypeError messages straight to
    sys.stderr, bypassing the logger's cp1252-safe sanitization, so any
    raw user input embedded in such a message must be sanitized here
    first or it crashes with a raw UnicodeEncodeError instead of a
    clean usage error."""

    encoding = getattr(sys.stderr, "encoding", None) or "ascii"

    return value.encode(encoding, errors="replace").decode(encoding)


def _parse_date(value: str) -> str:

    try:

        return validation.parse_date(value)

    except ValueError as exc:

        raise argparse.ArgumentTypeError(_sanitize_for_stderr(str(exc)))


def _parse_non_blank(value: str) -> str:

    try:

        return validation.non_blank(value)

    except ValueError as exc:

        raise argparse.ArgumentTypeError(str(exc))


# expiryFlag/drvOptionType/strike-offset valid values all live on
# PayloadBuilder, the single source of truth for DhanHQ's payload
# contract, so both the CLI and the web GUI validate against the same
# constants without one importing from the other.
VALID_EXPIRY_TYPES = PayloadBuilder.VALID_EXPIRY_TYPES
VALID_OPTION_TYPES = PayloadBuilder.VALID_OPTION_TYPES


def _make_choice_parser(valid_choices):
    """Builds an argparse type= function that strips/uppercases the
    input and validates it against a fixed set of choices."""

    def _parse(value: str) -> str:

        try:

            return validation.normalize_choice(value, valid_choices)

        except ValueError as exc:

            raise argparse.ArgumentTypeError(_sanitize_for_stderr(str(exc)))

    return _parse


_parse_expiry_type = _make_choice_parser(VALID_EXPIRY_TYPES)

_parse_underlying = _make_choice_parser(SUPPORTED_UNDERLYINGS)


def _parse_option_types(value: str) -> list[str]:

    try:

        return validation.normalize_choices(
            value.split(","), VALID_OPTION_TYPES, label="option type"
        )

    except ValueError as exc:

        raise argparse.ArgumentTypeError(_sanitize_for_stderr(str(exc)))


def build_parser() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(
        prog="python -m app.main",
        description=f"{APP_NAME} - historical options data downloader",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "test-connection",
        help="Verify DhanHQ API credentials and connectivity",
    )

    download_parser = subparsers.add_parser(
        "download",
        help="Start a new historical options download job",
    )
    download_parser.add_argument(
        "--underlying",
        required=True,
        type=_parse_underlying,
        help=f"one of {', '.join(sorted(SUPPORTED_UNDERLYINGS))}",
    )
    download_parser.add_argument(
        "--expiry-type",
        required=True,
        type=_parse_expiry_type,
        help="WEEK or MONTH",
    )
    download_parser.add_argument(
        "--option-types",
        required=True,
        type=_parse_option_types,
        help="Comma-separated option types, e.g. CALL,PUT",
    )
    download_parser.add_argument(
        "--start-date", required=True, type=_parse_date
    )
    download_parser.add_argument(
        "--end-date", required=True, type=_parse_date
    )
    download_parser.add_argument(
        "--job-id",
        type=_parse_non_blank,
        help="Unique job identifier; defaults to "
        "<underlying>-<start_date>-<end_date>",
    )
    download_parser.add_argument(
        "--save-parquet-to",
        type=_parse_non_blank,
        default=None,
        help="Optional folder to auto-save downloaded data as "
        "year/month-partitioned Parquet files, alongside the DuckDB write",
    )

    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume an existing download job by job_id",
    )
    resume_parser.add_argument(
        "--job-id", required=True, type=_parse_non_blank
    )

    subparsers.add_parser(
        "sync",
        help="Catch up NIFTY/SENSEX (WEEK+MONTH, full strike range) to "
        "today, saving Parquet under app/exports/parquet",
    )

    return parser


def run_download(args: argparse.Namespace):

    job_id = (
        args.job_id
        or f"{args.underlying}-{args.start_date}-{args.end_date}"
    )

    job = DownloadJob(
        job_id=job_id,
        underlying=args.underlying,
        expiry_type=args.expiry_type,
        option_types=args.option_types,
        strike_from=PayloadBuilder.MIN_STRIKE_OFFSET,
        strike_to=PayloadBuilder.MAX_STRIKE_OFFSET,
        start_date=args.start_date,
        end_date=args.end_date,
        created_at=datetime.now(),
        parquet_output_dir=args.save_parquet_to,
    )

    DownloadEngine().run(job)


def run_resume(args: argparse.Namespace):

    DownloadEngine().resume(args.job_id)


def run_sync():

    engine = DownloadEngine()

    jobs = SyncPlanner.plan_jobs(engine.repo)

    if not jobs:

        logger.info("NIFTY/SENSEX data is already up to date.")

        return

    for job in jobs:

        engine.run(job)


def main(argv: list[str] | None = None) -> int:

    parser = build_parser()
    args = parser.parse_args(argv)

    banner()

    try:

        if args.command == "test-connection":

            DhanAPI().test_connection()

        elif args.command == "download":

            run_download(args)

        elif args.command == "resume":

            run_resume(args)

        elif args.command == "sync":

            run_sync()

        else:

            raise AssertionError(f"Unhandled command: {args.command!r}")

    except Exception as exc:

        logger.error(str(exc))

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
