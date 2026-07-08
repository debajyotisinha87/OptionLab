"""
Application Entry Point

Single CLI entry point for OptionLab: verify DhanHQ connectivity, start
a new historical options download job, or resume an existing one.
"""

import argparse
import sys
from datetime import datetime

from app.api.api_client import DhanAPI
from app.config.logging_config import get_logger
from app.constants.app_info import (
    APP_NAME,
    APP_VERSION,
)
from app.downloader.download_engine import DownloadEngine
from app.models.job import DownloadJob

logger = get_logger()

DATE_FORMAT = "%Y-%m-%d"


def banner():

    logger.info("=" * 60)
    logger.info(f"{APP_NAME}  v{APP_VERSION}")
    logger.info("=" * 60)


def _parse_date(value: str) -> str:

    try:

        datetime.strptime(value, DATE_FORMAT)

    except ValueError:

        # argparse writes this message straight to sys.stderr, bypassing
        # the logger's cp1252-safe sanitization, so a non-ASCII value
        # must be sanitized here or it crashes with a raw
        # UnicodeEncodeError instead of a clean usage error.
        encoding = getattr(sys.stderr, "encoding", None) or "ascii"
        safe_value = value.encode(encoding, errors="replace").decode(encoding)

        raise argparse.ArgumentTypeError(
            f"Invalid date '{safe_value}': expected {DATE_FORMAT}"
        )

    return value


def _parse_non_blank(value: str) -> str:

    stripped = value.strip()

    if not stripped:

        raise argparse.ArgumentTypeError("value must not be blank")

    return stripped


def _parse_option_types(value: str) -> list[str]:

    option_types = [
        option_type.strip().upper()
        for option_type in value.split(",")
        if option_type.strip()
    ]

    if not option_types:

        raise argparse.ArgumentTypeError(
            "--option-types must contain at least one value, e.g. CALL,PUT"
        )

    return option_types


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
        "--underlying", required=True, type=_parse_non_blank
    )
    download_parser.add_argument(
        "--expiry-type", required=True, type=_parse_non_blank
    )
    download_parser.add_argument(
        "--option-types",
        required=True,
        type=_parse_option_types,
        help="Comma-separated option types, e.g. CALL,PUT",
    )
    download_parser.add_argument("--strike-from", required=True, type=int)
    download_parser.add_argument("--strike-to", required=True, type=int)
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

    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume an existing download job by job_id",
    )
    resume_parser.add_argument(
        "--job-id", required=True, type=_parse_non_blank
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
        strike_from=args.strike_from,
        strike_to=args.strike_to,
        start_date=args.start_date,
        end_date=args.end_date,
        created_at=datetime.now(),
    )

    DownloadEngine().run(job)


def run_resume(args: argparse.Namespace):

    DownloadEngine().resume(args.job_id)


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

        else:

            raise AssertionError(f"Unhandled command: {args.command!r}")

    except Exception as exc:

        logger.error(str(exc))

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
