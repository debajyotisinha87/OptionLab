from datetime import datetime

from app.builders.payload_builder import PayloadBuilder
from app.constants.underlyings import SUPPORTED_UNDERLYINGS
from app.models.download_batch import DownloadBatch
from app.models.job import DownloadJob


def create_test_job(underlying="NIFTY"):

    return DownloadJob(
        job_id="JOB-PAYLOAD-TEST",
        underlying=underlying,
        expiry_type="MONTH",
        option_types=["CALL"],
        strike_from=0,
        strike_to=0,
        start_date="2025-01-01",
        end_date="2025-01-01",
        created_at=datetime.now(),
    )


def create_test_batch():

    return DownloadBatch(
        batch_number=1,
        from_date="2025-01-01",
        to_date="2025-01-01",
    )


def test_build_routes_securityid_and_exchange_segment_per_underlying():

    for underlying, info in SUPPORTED_UNDERLYINGS.items():

        payload = PayloadBuilder.build(
            job=create_test_job(underlying=underlying),
            batch=create_test_batch(),
            option_type="CALL",
        )

        assert payload["securityId"] == info.security_id
        assert payload["exchangeSegment"] == info.exchange_segment
        assert payload["symbol"] == underlying


def test_build_rejects_an_unsupported_underlying():

    try:
        PayloadBuilder.build(
            job=create_test_job(underlying="RELIANCE"),
            batch=create_test_batch(),
            option_type="CALL",
        )
    except ValueError:
        return

    raise AssertionError("Expected ValueError for an unsupported underlying")


def test_build_defaults_to_the_atm_strike():

    payload = PayloadBuilder.build(
        job=create_test_job(),
        batch=create_test_batch(),
        option_type="CALL",
    )

    assert payload["strike"] == "ATM"


def test_build_passes_through_a_non_zero_strike_offset():

    payload = PayloadBuilder.build(
        job=create_test_job(),
        batch=create_test_batch(),
        option_type="CALL",
        strike_offset=3,
    )

    assert payload["strike"] == "ATM+3"

    payload = PayloadBuilder.build(
        job=create_test_job(),
        batch=create_test_batch(),
        option_type="CALL",
        strike_offset=-2,
    )

    assert payload["strike"] == "ATM-2"


def test_strike_label_conversion():

    assert PayloadBuilder.strike_label(0) == "ATM"
    assert PayloadBuilder.strike_label(10) == "ATM+10"
    assert PayloadBuilder.strike_label(-10) == "ATM-10"


def test_strike_label_rejects_offsets_outside_dhanhqs_supported_range():

    try:
        PayloadBuilder.strike_label(11)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for strike_offset=11")

    try:
        PayloadBuilder.strike_label(-11)
    except ValueError:
        return

    raise AssertionError("Expected ValueError for strike_offset=-11")


if __name__ == "__main__":

    test_build_routes_securityid_and_exchange_segment_per_underlying()
    test_build_rejects_an_unsupported_underlying()
    test_build_defaults_to_the_atm_strike()
    test_build_passes_through_a_non_zero_strike_offset()
    test_strike_label_conversion()
    test_strike_label_rejects_offsets_outside_dhanhqs_supported_range()

    print("Payload builder tests passed")
