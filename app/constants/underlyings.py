"""
Underlying Index Reference Data

Maps each supported underlying index to the DhanHQ securityId and
exchangeSegment its /v2/charts/rollingoption requests must use.
Values verified against DhanHQ's public instrument master
(https://images.dhan.co/api-data/api-scrip-master.csv, SEM_INSTRUMENT_NAME
= INDEX rows) and cross-checked against the NIFTY example in DhanHQ's own
API docs (securityId 13, exchangeSegment "NSE_FNO").
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UnderlyingInfo:
    """DhanHQ identifiers required to request an underlying's option
    chain: its securityId and the exchangeSegment that owns it."""

    security_id: int

    exchange_segment: str


SUPPORTED_UNDERLYINGS: dict[str, UnderlyingInfo] = {
    "NIFTY": UnderlyingInfo(security_id=13, exchange_segment="NSE_FNO"),
    "BANKNIFTY": UnderlyingInfo(security_id=25, exchange_segment="NSE_FNO"),
    "FINNIFTY": UnderlyingInfo(security_id=27, exchange_segment="NSE_FNO"),
    "MIDCPNIFTY": UnderlyingInfo(security_id=442, exchange_segment="NSE_FNO"),
    "SENSEX": UnderlyingInfo(security_id=51, exchange_segment="BSE_FNO"),
}
