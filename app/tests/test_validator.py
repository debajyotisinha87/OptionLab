from app.storage.data_normalizer import DataNormalizer
from app.validator.data_validator import DataValidator

sample = {
    "timestamp": [1751341500],
    "open": [420],
    "high": [430],
    "low": [418],
    "close": [425],
    "volume": [100],
    "oi": [500],
    "iv": [10.2],
    "spot": [25500],
}

df = DataNormalizer.normalize(
    option_data=sample,
    symbol="NIFTY",
    option_type="CALL",
    strike_type="ATM",
    expiry_flag="MONTH",
    expiry_code=1,
)

DataValidator.validate(df)

print("Validation Passed")