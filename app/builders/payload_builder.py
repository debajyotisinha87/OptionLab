"""
Payload Builder
"""

from app.models.job import DownloadJob
from app.models.download_batch import DownloadBatch


class PayloadBuilder:

    @staticmethod
    def build(
        job: DownloadJob,
        batch: DownloadBatch,
        option_type: str,
        strike: str = "ATM",
    ):

        return {

            "exchangeSegment": "NSE_FNO",

            "securityId": 13,

            "instrument": "OPTIDX",

            "expiryFlag": job.expiry_type,

            "expiryCode": 1,

            "fromDate": batch.from_date,

            "toDate": batch.to_date,

            "strike": strike,

            "drvOptionType": option_type,

            "interval": 1,

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