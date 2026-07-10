from datetime import date, datetime

from app.constants.trading_calendar import (
    expected_latest_trading_date,
    is_trading_day,
    last_trading_day_on_or_before,
)


def test_regular_weekday_is_a_trading_day():

    assert is_trading_day(date(2026, 11, 9))  # Monday, no holiday


def test_saturday_and_sunday_are_not_trading_days():

    assert not is_trading_day(date(2026, 11, 7))  # Saturday
    assert not is_trading_day(date(2026, 1, 25))  # Sunday


def test_known_holiday_is_not_a_trading_day():

    assert not is_trading_day(date(2026, 1, 26))  # Republic Day (Monday)


def test_special_weekend_trading_session_is_a_trading_day():

    assert is_trading_day(date(2026, 11, 8))  # Muhurat trading (Sunday)


def test_unknown_year_falls_back_to_weekday_only():

    assert is_trading_day(date(2030, 3, 5))  # Tuesday, no calendar loaded
    assert not is_trading_day(date(2030, 3, 2))  # Saturday, weekend check still applies


def test_last_trading_day_on_or_before_a_trading_day_returns_itself():

    assert last_trading_day_on_or_before(date(2026, 11, 9)) == date(2026, 11, 9)


def test_last_trading_day_on_or_before_skips_weekend_and_holiday():

    # Jan 26 2026 (Mon, Republic Day) -> Jan 25 (Sun) -> Jan 24 (Sat) -> Jan 23 (Fri, trading day)
    assert last_trading_day_on_or_before(date(2026, 1, 26)) == date(2026, 1, 23)


def test_expected_latest_trading_date_on_a_weekend_is_the_prior_friday():

    # Nov 14 2026 (Sat) -> Nov 13 (Fri, ordinary trading day, no
    # nearby holiday/special session to complicate the expectation).
    saturday_afternoon = datetime(2026, 11, 14, 14, 0)

    assert expected_latest_trading_date(saturday_afternoon) == date(2026, 11, 13)


def test_expected_latest_trading_date_before_cutoff_is_the_prior_trading_day():

    monday_morning = datetime(2026, 11, 16, 10, 0)

    assert expected_latest_trading_date(monday_morning) == date(2026, 11, 13)


def test_expected_latest_trading_date_after_cutoff_is_today():

    monday_evening = datetime(2026, 11, 16, 20, 30)

    assert expected_latest_trading_date(monday_evening) == date(2026, 11, 16)


if __name__ == "__main__":

    test_regular_weekday_is_a_trading_day()
    test_saturday_and_sunday_are_not_trading_days()
    test_known_holiday_is_not_a_trading_day()
    test_special_weekend_trading_session_is_a_trading_day()
    test_unknown_year_falls_back_to_weekday_only()
    test_last_trading_day_on_or_before_a_trading_day_returns_itself()
    test_last_trading_day_on_or_before_skips_weekend_and_holiday()
    test_expected_latest_trading_date_on_a_weekend_is_the_prior_friday()
    test_expected_latest_trading_date_before_cutoff_is_the_prior_trading_day()
    test_expected_latest_trading_date_after_cutoff_is_today()

    print("All test_trading_calendar tests passed.")
