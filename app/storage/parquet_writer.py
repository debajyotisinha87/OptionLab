"""
Parquet Writer

Optional export sink alongside the real source of truth (DuckDB's
option_data table) - never the source of truth itself.
"""

from pathlib import Path

import pandas as pd


class ParquetWriter:
    """Writes a normalized option_data-shaped DataFrame into a
    Hive-style year/month-partitioned Parquet layout, so the export is
    directly readable later as a partitioned dataset (e.g.
    duckdb.read_parquet(..., hive_partitioning=True)) with no extra
    glue."""

    FILENAME = "option_data.parquet"

    DEDUP_KEY = [
        "symbol",
        "trade_datetime",
        "option_type",
        "strike_type",
        "expiry_flag",
        "expiry_code",
    ]

    @staticmethod
    def write(df: pd.DataFrame, output_dir: str | Path, underlying: str) -> list[Path]:
        """Splits df by (year, month) of trade_date and merges each
        partition into
            <output_dir>/underlying=<underlying>/year=<YYYY>/month=<MM>/option_data.parquet
        via read-existing + concat + dedupe + rewrite, since Parquet
        has no true streaming append - different units (option types,
        strikes), or even different jobs with overlapping date ranges,
        must accumulate correctly into the same monthly file rather
        than clobber each other. Returns the partition file paths
        touched; a no-op returning [] for an empty df."""

        if df.empty:

            return []

        output_dir = Path(output_dir)

        trade_date = pd.to_datetime(df["trade_date"])

        written_paths = []

        for (year, month), group in df.groupby(
            [trade_date.dt.year, trade_date.dt.month]
        ):

            partition_dir = (
                output_dir
                / f"underlying={underlying}"
                / f"year={year:04d}"
                / f"month={month:02d}"
            )

            partition_dir.mkdir(parents=True, exist_ok=True)

            partition_path = partition_dir / ParquetWriter.FILENAME

            if partition_path.exists():

                existing = pd.read_parquet(partition_path, engine="pyarrow")

                combined = pd.concat([existing, group], ignore_index=True)

            else:

                combined = group.reset_index(drop=True)

            combined = combined.drop_duplicates(
                subset=ParquetWriter.DEDUP_KEY, keep="last"
            )

            combined = combined.sort_values("trade_datetime").reset_index(drop=True)

            combined.to_parquet(partition_path, engine="pyarrow", index=False)

            written_paths.append(partition_path)

        return written_paths
