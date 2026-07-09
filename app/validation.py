"""
Shared Input Validation

Framework-agnostic validation helpers (no argparse/Pydantic types) used
by both the CLI (app/main.py) and the web GUI (app/web/server.py) so
the two entry points can't silently drift on what counts as valid
input. Every function raises a plain ValueError on invalid input;
callers translate that into whatever their framework expects
(argparse.ArgumentTypeError, a Pydantic field_validator, etc.).
"""

from datetime import datetime

DATE_FORMAT = "%Y-%m-%d"


def normalize_choice(value: str, valid_choices) -> str:
    """Strips/uppercases value and validates it against valid_choices."""

    normalized = value.strip().upper()

    if normalized not in valid_choices:

        raise ValueError(
            f"invalid choice: '{value}' "
            f"(choose from {', '.join(sorted(valid_choices))})"
        )

    return normalized


def normalize_choices(values: list[str], valid_choices, *, label: str = "value") -> list[str]:
    """List variant of normalize_choice: strips/uppercases every item,
    drops blanks, then validates all of them, reporting every invalid
    item at once (not just the first)."""

    normalized = [value.strip().upper() for value in values if value.strip()]

    if not normalized:

        raise ValueError(f"{label} must contain at least one value")

    invalid = [value for value in normalized if value not in valid_choices]

    if invalid:

        raise ValueError(
            f"invalid {label}(s): {', '.join(invalid)} "
            f"(choose from {', '.join(valid_choices)})"
        )

    return normalized


def parse_date(value: str) -> str:
    """Validates value matches DATE_FORMAT (YYYY-MM-DD)."""

    try:

        datetime.strptime(value, DATE_FORMAT)

    except ValueError:

        raise ValueError(f"invalid date '{value}': expected {DATE_FORMAT}")

    return value


def non_blank(value: str) -> str:
    """Strips value and rejects it if empty."""

    stripped = value.strip()

    if not stripped:

        raise ValueError("value must not be blank")

    return stripped
