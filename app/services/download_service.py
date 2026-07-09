"""
Download Service
"""

from app.api.rolling_option import RollingOptionAPI
from app.config.logging_config import get_logger
from app.database.repository import Repository
from app.storage.data_normalizer import DataNormalizer
from app.storage.parquet_writer import ParquetWriter
from app.validator.data_validator import DataValidator

logger = get_logger()


class DownloadService:

    def __init__(self):

        self.api = RollingOptionAPI()
        self.repo = Repository()

    def download(self, payload, parquet_output_dir: str | None = None):

        try:

            response = self.api.fetch(payload)

            data = response.get("data", {})
            option_data_key = self.get_option_data_key(
                payload["drvOptionType"]
            )
            option_data = data.get(option_data_key)

            if option_data is None:

                logger.error(
                    "No data returned from API - underlying=%s option_type=%s "
                    "strike=%s expiry_type=%s range=%s->%s (HTTP %s): "
                    "raw response=%r",
                    payload["symbol"],
                    payload["drvOptionType"],
                    payload["strike"],
                    payload["expiryFlag"],
                    payload["fromDate"],
                    payload["toDate"],
                    response.get("_http_status_code", "unknown"),
                    response,
                )

                return {
                    "success": False,
                    "downloaded_rows": 0,
                    "inserted_rows": 0,
                    "error": "No data returned from API.",
                }

            df = DataNormalizer.normalize(
                option_data=option_data,
                symbol=payload["symbol"],
                option_type=payload["drvOptionType"],
                strike_type=payload["strike"],
                expiry_flag=payload["expiryFlag"],
                expiry_code=payload["expiryCode"],
            )

            report = DataValidator.validate(df)

            if not report.passed:

                return {
                    "success": False,
                    "downloaded_rows": len(df),
                    "inserted_rows": 0,
                    "error": "; ".join(report.errors),
                }

            self.repo.insert_option_data(df)

            if parquet_output_dir:

                try:

                    ParquetWriter.write(
                        df, parquet_output_dir, underlying=payload["symbol"]
                    )

                except Exception as exc:

                    # DuckDB (already written above) remains the source
                    # of truth. A broken export folder (permissions,
                    # deleted drive, full disk) must not turn an
                    # otherwise-successful unit into a FAILED one -
                    # retrying can't fix a bad folder, and would just
                    # burn real DhanHQ API calls on every retry.
                    logger.error(
                        f"Parquet export failed for {payload['symbol']} "
                        f"{payload['drvOptionType']} ({payload['strike']}): {exc}"
                    )

            return {
                "success": True,
                "downloaded_rows": len(df),
                "inserted_rows": len(df),
                "error": None,
            }

        except Exception as ex:

            return {
                "success": False,
                "downloaded_rows": 0,
                "inserted_rows": 0,
                "error": str(ex),
            }

    @staticmethod
    def get_option_data_key(option_type: str):

        if option_type == "CALL":

            return "ce"

        if option_type == "PUT":

            return "pe"

        raise ValueError(f"Unsupported option type: {option_type}")
