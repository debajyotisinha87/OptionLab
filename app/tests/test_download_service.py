import logging

import app.services.download_service as download_service_module
from app.config.config import LOG_DIR
from app.services.download_service import DownloadService


class FakeAPI:

    def __init__(self, response):

        self.response = response
        self.fetch_calls = []

    def fetch(self, payload):

        self.fetch_calls.append(payload)

        return self.response


class FakeRepo:

    def __init__(self):

        self.inserted = []

    def insert_option_data(self, df):

        self.inserted.append(df)


class FakeParquetWriter:

    write_calls = []
    raise_error = None

    @staticmethod
    def write(df, output_dir, underlying):

        FakeParquetWriter.write_calls.append((df, output_dir, underlying))

        if FakeParquetWriter.raise_error is not None:

            raise FakeParquetWriter.raise_error


def make_payload(option_type="CALL"):

    return {
        "exchangeSegment": "NSE_FNO",
        "securityId": 13,
        "instrument": "OPTIDX",
        "expiryFlag": "MONTH",
        "expiryCode": 1,
        "fromDate": "2025-01-01",
        "toDate": "2025-01-01",
        "strike": "ATM",
        "drvOptionType": option_type,
        "interval": 1,
        "requiredData": ["open", "high", "low", "close", "volume", "oi", "iv", "spot"],
        "symbol": "NIFTY",
    }


def make_service(api_response, repo=None):

    service = DownloadService.__new__(DownloadService)
    service.api = FakeAPI(api_response)
    service.repo = repo or FakeRepo()

    return service


def with_fake_parquet_writer(fn):

    original = download_service_module.ParquetWriter
    download_service_module.ParquetWriter = FakeParquetWriter
    FakeParquetWriter.write_calls = []
    FakeParquetWriter.raise_error = None

    try:
        return fn()
    finally:
        download_service_module.ParquetWriter = original


def successful_response(option_type="CALL"):

    key = "ce" if option_type == "CALL" else "pe"

    return {
        "data": {
            key: {
                "timestamp": [1735707000],
                "open": [100.0],
                "high": [105.0],
                "low": [95.0],
                "close": [102.5],
                "volume": [1200],
                "oi": [4500],
                "iv": [14.2],
                "spot": [21050.25],
            }
        }
    }


def test_no_data_returned_logs_the_raw_response():

    log_file = LOG_DIR / "optionlab.log"
    offset_before = log_file.stat().st_size if log_file.exists() else 0

    response = {"status": "error", "message": "sandbox unavailable", "_http_status_code": 200}
    service = make_service(response)

    result = service.download(make_payload())

    assert result["success"] is False
    assert result["error"] == "No data returned from API."

    for handler in logging.getLogger("optionlab").handlers:

        if isinstance(handler, logging.FileHandler):

            handler.flush()

    with log_file.open("r", encoding="utf-8") as f:

        f.seek(offset_before)
        new_contents = f.read()

    assert "No data returned from API" in new_contents
    assert "sandbox unavailable" in new_contents


def test_parquet_writer_is_called_when_output_dir_is_set():

    def run():

        service = make_service(successful_response())

        result = service.download(make_payload(), parquet_output_dir="C:/exports")

        assert result["success"] is True
        assert len(FakeParquetWriter.write_calls) == 1

        df, output_dir, underlying = FakeParquetWriter.write_calls[0]
        assert output_dir == "C:/exports"
        assert underlying == "NIFTY"
        assert len(df) == 1

    with_fake_parquet_writer(run)


def test_parquet_writer_is_not_called_when_output_dir_is_none():

    def run():

        service = make_service(successful_response())

        result = service.download(make_payload(), parquet_output_dir=None)

        assert result["success"] is True
        assert FakeParquetWriter.write_calls == []

    with_fake_parquet_writer(run)


def test_parquet_writer_failure_is_logged_but_does_not_fail_the_unit():

    def run():

        FakeParquetWriter.raise_error = RuntimeError("disk full")

        service = make_service(successful_response())

        result = service.download(make_payload(), parquet_output_dir="C:/exports")

        assert result["success"] is True
        assert result["error"] is None
        assert len(FakeParquetWriter.write_calls) == 1

    with_fake_parquet_writer(run)


if __name__ == "__main__":

    test_no_data_returned_logs_the_raw_response()
    test_parquet_writer_is_called_when_output_dir_is_set()
    test_parquet_writer_is_not_called_when_output_dir_is_none()
    test_parquet_writer_failure_is_logged_but_does_not_fail_the_unit()

    print("Download service tests passed")
