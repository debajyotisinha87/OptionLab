from app.storage.data_normalizer import DataNormalizer


def make_option_data(timestamps, volumes):

    n = len(timestamps)

    return {
        "timestamp": timestamps,
        "open": [100.0] * n,
        "high": [101.0] * n,
        "low": [99.0] * n,
        "close": [100.0] * n,
        "volume": volumes,
        "oi": [1000] * n,
        "iv": [12.0] * n,
        "spot": [21000.0] * n,
    }


def normalize(timestamps, volumes):

    return DataNormalizer.normalize(
        make_option_data(timestamps, volumes),
        symbol="SENSEX",
        option_type="CALL",
        strike_type="ATM",
        expiry_flag="WEEK",
        expiry_code=1,
    )


def test_no_duplicates_passes_through_unchanged():

    df = normalize([1758268500, 1758268560, 1758268620], [100, 200, 300])

    assert len(df) == 3
    assert df["volume"].tolist() == [100, 200, 300]


def test_duplicate_timestamp_keeps_the_traded_row_over_the_stale_zero_volume_row():

    # Same minute appears twice: a real trade (volume>0) and a stale,
    # carried-forward last-traded-price snapshot (volume=0).
    df = normalize(
        [1758268500, 1758268500, 1758268560],
        [500, 0, 200],
    )

    assert len(df) == 2
    assert df["volume"].tolist() == [500, 200]


def test_duplicate_timestamp_with_both_sides_traded_keeps_the_higher_volume_row():

    df = normalize(
        [1758268500, 1758268500],
        [300, 700],
    )

    assert len(df) == 1
    assert df.iloc[0]["volume"] == 700


def test_result_stays_sorted_by_trade_datetime():

    df = normalize(
        [1758268620, 1758268500, 1758268500, 1758268560],
        [50, 500, 0, 200],
    )

    assert df["trade_datetime"].is_monotonic_increasing
    assert df["volume"].tolist() == [500, 200, 50]


if __name__ == "__main__":

    test_no_duplicates_passes_through_unchanged()
    test_duplicate_timestamp_keeps_the_traded_row_over_the_stale_zero_volume_row()
    test_duplicate_timestamp_with_both_sides_traded_keeps_the_higher_volume_row()
    test_result_stays_sorted_by_trade_datetime()

    print("All test_data_normalizer tests passed.")
