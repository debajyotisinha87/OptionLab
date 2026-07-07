"""
CSV Writer
"""

from pathlib import Path
import pandas as pd


class CSVWriter:

    @staticmethod
    def save(df: pd.DataFrame, filename: str):

        folder = Path("data/csv")

        folder.mkdir(parents=True, exist_ok=True)

        path = folder / filename

        df.to_csv(path, index=False)

        print(f"\nSaved : {path}")