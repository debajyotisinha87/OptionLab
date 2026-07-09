import shutil
import tempfile
from pathlib import Path

import pandas as pd

from app.storage.parquet_writer import ParquetWriter

COLUMNS = [
    "symbol", "trade_datetime", "trade_date", "trade_time",
    "option_type", "strike_type", "expiry_flag", "expiry_code",
    "open", "high", "low", "close", "volume", "oi", "iv", "spot",
]


def make_row(trade_date, close=100.0, option_type="CALL", strike_type="ATM"):

    trade_datetime = pd.Timestamp(f"{trade_date} 09:15:00")

    return {
        "symbol": "NIFTY",
        "trade_datetime": trade_datetime,
        "trade_date": trade_datetime.date(),
        "trade_time": trade_datetime.time(),
        "option_type": option_type,
        "strike_type": strike_type,
        "expiry_flag": "MONTH",
        "expiry_code": 1,
        "open": close - 1,
        "high": close + 1,
        "low": close - 2,
        "close": close,
        "volume": 100,
        "oi": 200,
        "iv": 15.0,
        "spot": 21000.0,
    }


def make_df(rows):

    return pd.DataFrame(rows, columns=COLUMNS)


def with_temp_dir(fn):

    temp_dir = tempfile.mkdtemp()

    try:
        return fn(Path(temp_dir))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_write_creates_the_hive_style_partition_path():

    def run(temp_dir):

        df = make_df([make_row("2025-01-15")])

        written = ParquetWriter.write(df, temp_dir, underlying="NIFTY")

        expected = temp_dir / "underlying=NIFTY" / "year=2025" / "month=01" / "option_data.parquet"

        assert written == [expected]
        assert expected.exists()

        result = pd.read_parquet(expected, engine="pyarrow")
        assert len(result) == 1
        assert result.iloc[0]["close"] == 100.0

    with_temp_dir(run)


def test_write_splits_rows_spanning_a_month_boundary_into_two_partitions():

    def run(temp_dir):

        df = make_df([make_row("2025-01-31"), make_row("2025-02-01")])

        written = ParquetWriter.write(df, temp_dir, underlying="NIFTY")

        assert len(written) == 2

        jan_path = temp_dir / "underlying=NIFTY" / "year=2025" / "month=01" / "option_data.parquet"
        feb_path = temp_dir / "underlying=NIFTY" / "year=2025" / "month=02" / "option_data.parquet"

        assert jan_path.exists()
        assert feb_path.exists()
        assert len(pd.read_parquet(jan_path, engine="pyarrow")) == 1
        assert len(pd.read_parquet(feb_path, engine="pyarrow")) == 1

    with_temp_dir(run)


def test_write_splits_rows_spanning_a_year_boundary_into_two_partitions():

    def run(temp_dir):

        df = make_df([make_row("2025-12-31"), make_row("2026-01-01")])

        written = ParquetWriter.write(df, temp_dir, underlying="NIFTY")

        assert len(written) == 2

        y2025_path = temp_dir / "underlying=NIFTY" / "year=2025" / "month=12" / "option_data.parquet"
        y2026_path = temp_dir / "underlying=NIFTY" / "year=2026" / "month=01" / "option_data.parquet"

        assert y2025_path.exists()
        assert y2026_path.exists()

    with_temp_dir(run)


def test_a_second_write_merges_into_the_same_partition_instead_of_clobbering():

    def run(temp_dir):

        ParquetWriter.write(
            make_df([make_row("2025-01-01", option_type="CALL")]),
            temp_dir,
            underlying="NIFTY",
        )
        ParquetWriter.write(
            make_df([make_row("2025-01-02", option_type="PUT")]),
            temp_dir,
            underlying="NIFTY",
        )

        path = temp_dir / "underlying=NIFTY" / "year=2025" / "month=01" / "option_data.parquet"

        result = pd.read_parquet(path, engine="pyarrow")

        assert len(result) == 2
        assert set(result["option_type"]) == {"CALL", "PUT"}

    with_temp_dir(run)


def test_overlapping_rows_across_writes_are_deduped():

    def run(temp_dir):

        row = make_row("2025-01-01", close=100.0)

        ParquetWriter.write(make_df([row]), temp_dir, underlying="NIFTY")

        updated_row = dict(row)
        updated_row["close"] = 999.0

        ParquetWriter.write(make_df([updated_row]), temp_dir, underlying="NIFTY")

        path = temp_dir / "underlying=NIFTY" / "year=2025" / "month=01" / "option_data.parquet"

        result = pd.read_parquet(path, engine="pyarrow")

        assert len(result) == 1
        assert result.iloc[0]["close"] == 999.0

    with_temp_dir(run)


def test_empty_dataframe_is_a_no_op():

    def run(temp_dir):

        written = ParquetWriter.write(make_df([]), temp_dir, underlying="NIFTY")

        assert written == []
        assert not (temp_dir / "underlying=NIFTY").exists()

    with_temp_dir(run)


if __name__ == "__main__":

    test_write_creates_the_hive_style_partition_path()
    test_write_splits_rows_spanning_a_month_boundary_into_two_partitions()
    test_write_splits_rows_spanning_a_year_boundary_into_two_partitions()
    test_a_second_write_merges_into_the_same_partition_instead_of_clobbering()
    test_overlapping_rows_across_writes_are_deduped()
    test_empty_dataframe_is_a_no_op()

    print("Parquet writer tests passed")
