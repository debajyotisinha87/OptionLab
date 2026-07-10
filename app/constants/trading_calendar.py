"""
Trading Calendar

NSE/BSE trading-day awareness: which calendar dates are real trading
sessions, and what "today's data should be ready by now" means.
DhanHQ's API exposes no holiday-calendar endpoint, so - same as
brokers and data vendors do in practice - this is a maintained static
list, sourced from NSE's published holiday circular each year and
cross-checked against secondary sources (Zerodha/Groww/ClearTax, all
of which agreed on the 2026 list below). Needs a manual refresh once
a year when NSE publishes the next year's calendar; a year missing
from HOLIDAYS_BY_YEAR degrades to "every weekday is a trading day"
rather than raising, since that's still closer to correct than
refusing to run.
"""

from datetime import date, datetime, time, timedelta

HOLIDAYS_BY_YEAR: dict[int, set[date]] = {
    2026: {
        date(2026, 1, 15),   # Maharashtra Municipal Corporation Elections
        date(2026, 1, 26),   # Republic Day
        date(2026, 3, 3),    # Holi
        date(2026, 3, 26),   # Shri Ram Navami
        date(2026, 3, 31),   # Shri Mahavir Jayanti
        date(2026, 4, 3),    # Good Friday
        date(2026, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
        date(2026, 5, 1),    # Maharashtra Day
        date(2026, 5, 28),   # Bakri Id
        date(2026, 6, 26),   # Muharram
        date(2026, 9, 14),   # Ganesh Chaturthi
        date(2026, 10, 2),   # Mahatma Gandhi Jayanti
        date(2026, 10, 20),  # Dussehra
        date(2026, 11, 10),  # Diwali - Balipratipada
        date(2026, 11, 24),  # Guru Nanak Jayanti
        date(2026, 12, 25),  # Christmas
    },
}

# Falls on a weekend but is a real (limited) trading session -
# Muhurat trading for Diwali Laxmi Pujan.
SPECIAL_TRADING_DAYS_BY_YEAR: dict[int, set[date]] = {
    2026: {date(2026, 11, 8)},
}

# Regular market hours. DhanHQ documents no official end-of-day
# publish time, so this is a conservative estimate of when a trading
# session's data should realistically be downloadable - also the time
# the web GUI's daily auto-sync is scheduled to run (app/web/server.py).
MARKET_CLOSE_TIME = time(15, 30)

DATA_AVAILABLE_BY = time(20, 0)


def is_trading_day(day: date) -> bool:
    """Whether NSE/BSE's equity & derivatives segment is open on this
    calendar date."""

    if day in SPECIAL_TRADING_DAYS_BY_YEAR.get(day.year, set()):

        return True

    if day.weekday() >= 5:  # Saturday=5, Sunday=6

        return False

    return day not in HOLIDAYS_BY_YEAR.get(day.year, set())


def last_trading_day_on_or_before(day: date) -> date:
    """Walks backward from `day` (inclusive) to the most recent actual
    trading day."""

    cursor = day

    while not is_trading_day(cursor):

        cursor -= timedelta(days=1)

    return cursor


def expected_latest_trading_date(now: datetime) -> date:
    """The most recent trading session whose data should realistically
    already be available, given the current date/time - the correct
    "as of" reference for data-freshness checks. Comparing against
    raw calendar `today` is wrong on weekends/holidays (nothing can
    ever catch up to a day that will never have data) and wrong on a
    trading day before DATA_AVAILABLE_BY (today's session hasn't
    finished publishing yet)."""

    today = now.date()

    if is_trading_day(today) and now.time() >= DATA_AVAILABLE_BY:

        return today

    return last_trading_day_on_or_before(today - timedelta(days=1))
