import io
import sys

import app.downloader.progress_reporter as progress_reporter_module
from app.downloader.progress_reporter import ProgressReporter


class FakeTTYStream(io.StringIO):
    """Makes tqdm's disable=None auto-detection treat this stream as a
    live terminal, so tests can exercise the real (non-disabled) bar
    behavior instead of tqdm's stripped-down disabled-mode no-ops."""

    def isatty(self):

        return True


def with_fake_tty(fn):
    """Runs fn() with sys.stdout replaced by a FakeTTYStream, returning
    (fn's return value, captured output)."""

    original_stdout = sys.stdout
    sys.stdout = FakeTTYStream()

    try:
        result = fn()
        captured = sys.stdout.getvalue()
    finally:
        sys.stdout = original_stdout

    return result, captured


def test_reset_creates_a_bar_with_the_given_total():

    reporter = ProgressReporter()
    reporter.reset(total_units=5, description="Test Job")

    assert reporter.bar is not None
    assert reporter.bar.total == 5
    assert reporter.total_rows == 0

    reporter.close()


def test_reset_seeds_total_rows_from_initial_rows():

    reporter = ProgressReporter()
    reporter.reset(total_units=5, description="Test Job", initial_rows=3000)

    assert reporter.total_rows == 3000
    assert reporter.session_rows == 0

    reporter.close()


def test_record_advances_the_bar_and_accumulates_rows():

    # completed_units/total_rows are tracked independently of tqdm's own
    # internal counter, which tqdm itself doesn't update when the bar is
    # auto-disabled (non-TTY output, e.g. this test running headless).
    reporter = ProgressReporter()
    reporter.reset(total_units=3, description="Test Job")

    reporter.record(inserted_rows=100)
    assert reporter.completed_units == 1
    assert reporter.total_rows == 100

    reporter.record(inserted_rows=50)
    assert reporter.completed_units == 2
    assert reporter.total_rows == 150

    # a skipped/failed unit still advances the bar, just with 0 rows
    reporter.record()
    assert reporter.completed_units == 3
    assert reporter.total_rows == 150

    reporter.close()


def test_record_and_write_actually_drive_the_real_bar_when_enabled():

    def run():

        reporter = ProgressReporter()
        reporter.reset(total_units=2, description="Test Job")

        assert not reporter.bar.disable

        reporter.record(inserted_rows=100)
        reporter.write("status line")

        bar_n = reporter.bar.n
        bar_postfix = reporter.bar.postfix

        reporter.close()

        return bar_n, bar_postfix

    (bar_n, bar_postfix), output = with_fake_tty(run)

    assert bar_n == 1
    assert "rows=100" in bar_postfix
    assert "Test Job" in output
    assert "status line" in output


def test_record_emits_a_plain_text_summary_when_bar_is_disabled():

    # non-TTY stdout (this test's normal execution environment) auto-
    # disables the animated bar, but record() must still surface
    # progress/rows/speed/ETA as plain text so an unattended/logged run
    # isn't left with zero progress information.
    reporter = ProgressReporter()
    reporter.reset(total_units=2, description="Test Job")

    assert reporter.bar.disable

    original_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        reporter.record(inserted_rows=250)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = original_stdout

    reporter.close()

    assert "1/2" in output
    assert "250" in output
    assert "ETA" in output


def test_write_works_with_an_active_bar_and_with_no_bar():

    reporter = ProgressReporter()

    # no bar yet - must not raise
    reporter.write("before any job has started")

    reporter.reset(total_units=1, description="Test Job")
    reporter.write("mid-job status line")
    reporter.close()

    # bar closed - must not raise
    reporter.write("after the job finished")


def test_record_before_reset_does_not_raise():

    reporter = ProgressReporter()

    # no bar yet - must be a no-op, not an AttributeError
    reporter.record(inserted_rows=100)

    assert reporter.total_rows == 0
    assert reporter.completed_units == 0


def test_close_is_idempotent():

    reporter = ProgressReporter()
    reporter.reset(total_units=1, description="Test Job")

    reporter.close()
    assert reporter.bar is None

    reporter.close()
    assert reporter.bar is None


def test_reset_closes_the_previous_bar_before_creating_a_new_one():

    reporter = ProgressReporter()
    reporter.reset(total_units=2, description="First Job")

    first_bar = reporter.bar

    events = []

    original_close = first_bar.close

    def spy_close():
        events.append("closed")
        return original_close()

    first_bar.close = spy_close

    original_tqdm = progress_reporter_module.tqdm

    def spy_tqdm(*args, **kwargs):
        events.append("created")
        return original_tqdm(*args, **kwargs)

    progress_reporter_module.tqdm = spy_tqdm

    try:
        reporter.reset(total_units=4, description="Second Job")
    finally:
        progress_reporter_module.tqdm = original_tqdm

    assert events == ["closed", "created"]
    assert reporter.bar is not first_bar
    assert reporter.bar.total == 4
    assert reporter.total_rows == 0

    reporter.close()


if __name__ == "__main__":

    test_reset_creates_a_bar_with_the_given_total()
    test_reset_seeds_total_rows_from_initial_rows()
    test_record_advances_the_bar_and_accumulates_rows()
    test_record_and_write_actually_drive_the_real_bar_when_enabled()
    test_record_emits_a_plain_text_summary_when_bar_is_disabled()
    test_write_works_with_an_active_bar_and_with_no_bar()
    test_record_before_reset_does_not_raise()
    test_close_is_idempotent()
    test_reset_closes_the_previous_bar_before_creating_a_new_one()

    print("Progress reporter tests passed")
