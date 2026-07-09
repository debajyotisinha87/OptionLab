"""
Application Entry Point

Single CLI entry point for OptionLab: verify DhanHQ connectivity, start
a new historical options download job, or resume an existing one.
"""

import argparse
import sys
from datetime import datetime

from app.api.api_client import DhanAPI
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

DATE_FORMAT = "%Y-%m-%d"


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

        datetime.strptime(value, DATE_FORMAT)

    except ValueError:

        raise argparse.ArgumentTypeError(
            f"Invalid date '{_sanitize_for_stderr(value)}': "
            f"expected {DATE_FORMAT}"
        )

    return value


def _parse_non_blank(value: str) -> str:

    stripped = value.strip()

    if not stripped:

        raise argparse.ArgumentTypeError("value must not be blank")

    return stripped


# Per DhanHQ's /v2/charts/rollingoption docs: expiryFlag accepts only
# WEEK/MONTH, drvOptionType accepts only CALL/PUT. Strike-offset bounds
# live on PayloadBuilder, the single source of truth for DhanHQ's
# ATM-10..ATM+10 range for index options.
VALID_EXPIRY_TYPES = ("WEEK", "MONTH")
VALID_OPTION_TYPES = ("CALL", "PUT")


def _make_choice_parser(valid_choices):
    """Builds an argparse type= function that strips/uppercases the
    input and validates it against a fixed set of choices."""

    def _parse(value: str) -> str:

        normalized = value.strip().upper()

        if normalized not in valid_choices:

            raise argparse.ArgumentTypeError(
                f"invalid choice: '{_sanitize_for_stderr(value)}' "
                f"(choose from {', '.join(sorted(valid_choices))})"
            )

        return normalized

    return _parse


_parse_expiry_type = _make_choice_parser(VALID_EXPIRY_TYPES)

_parse_underlying = _make_choice_parser(SUPPORTED_UNDERLYINGS)


def _parse_strike_offset(value: str) -> int:

    try:

        offset = int(value)

    except ValueError:

        raise argparse.ArgumentTypeError(
            f"invalid int value: '{_sanitize_for_stderr(value)}'"
        )

    if (
        offset < PayloadBuilder.MIN_STRIKE_OFFSET
        or offset > PayloadBuilder.MAX_STRIKE_OFFSET
    ):

        raise argparse.ArgumentTypeError(
            f"strike offset must be between "
            f"{PayloadBuilder.MIN_STRIKE_OFFSET} and "
            f"{PayloadBuilder.MAX_STRIKE_OFFSET} "
            "(DhanHQ's supported range for index options)"
        )

    return offset


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

    invalid = [
        option_type
        for option_type in option_types
        if option_type not in VALID_OPTION_TYPES
    ]

    if invalid:

        safe_invalid = [_sanitize_for_stderr(item) for item in invalid]

        raise argparse.ArgumentTypeError(
            f"invalid option type(s): {', '.join(safe_invalid)} "
            f"(choose from {', '.join(VALID_OPTION_TYPES)})"
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
        "--strike-from", required=True, type=_parse_strike_offset
    )
    download_parser.add_argument(
        "--strike-to", required=True, type=_parse_strike_offset
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

    if args.command == "download" and args.strike_from > args.strike_to:

        parser.error(
            f"--strike-from ({args.strike_from}) must be <= "
            f"--strike-to ({args.strike_to})"
        )

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
