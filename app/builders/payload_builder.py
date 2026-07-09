"""
Payload Builder
"""

from app.constants.underlyings import SUPPORTED_UNDERLYINGS
from app.models.job import DownloadJob
from app.models.download_batch import DownloadBatch


class PayloadBuilder:

    INSTRUMENT = "OPTIDX"

    INTERVAL = 1

    # DhanHQ's documented strike range for index options.
    MIN_STRIKE_OFFSET = -10

    MAX_STRIKE_OFFSET = 10

    # Per DhanHQ's /v2/charts/rollingoption docs: expiryFlag accepts
    # only WEEK/MONTH, drvOptionType accepts only CALL/PUT. Defined
    # here (not in app/main.py) so both the CLI and the web GUI can
    # validate against the same source of truth without one importing
    # from the other.
    VALID_EXPIRY_TYPES = ("WEEK", "MONTH")

    VALID_OPTION_TYPES = ("CALL", "PUT")

    @staticmethod
    def build(
        job: DownloadJob,
        batch: DownloadBatch,
        option_type: str,
        strike_offset: int = 0,
    ):

        underlying_info = SUPPORTED_UNDERLYINGS.get(job.underlying)

        if underlying_info is None:

            raise ValueError(f"Unsupported underlying: {job.underlying}")

        return {

            "exchangeSegment": underlying_info.exchange_segment,

            "securityId": underlying_info.security_id,

            "instrument": PayloadBuilder.INSTRUMENT,

            "expiryFlag": job.expiry_type,

            "expiryCode": 1,

            "fromDate": batch.from_date,

            "toDate": batch.to_date,

            "strike": PayloadBuilder.strike_label(strike_offset),

            "drvOptionType": option_type,

            "interval": PayloadBuilder.INTERVAL,

            "requiredData": [

                "open",
                "high",
                "low",
                "close",
                "volume",
                "oi",
                "iv",
                "spot",
            ],

            # Internal metadata (not sent to the API)
            "symbol": job.underlying,
        }

    @staticmethod
    def strike_label(strike_offset: int) -> str:
        """Converts an integer strike offset into DhanHQ's expected
        strike string: 0 -> "ATM", 3 -> "ATM+3", -2 -> "ATM-2"."""

        if (
            strike_offset < PayloadBuilder.MIN_STRIKE_OFFSET
            or strike_offset > PayloadBuilder.MAX_STRIKE_OFFSET
        ):

            raise ValueError(
                f"strike offset {strike_offset} is outside DhanHQ's "
                f"supported range ({PayloadBuilder.MIN_STRIKE_OFFSET} to "
                f"{PayloadBuilder.MAX_STRIKE_OFFSET})"
            )

        if strike_offset == 0:

            return "ATM"

        if strike_offset > 0:

            return f"ATM+{strike_offset}"

        return f"ATM{strike_offset}"