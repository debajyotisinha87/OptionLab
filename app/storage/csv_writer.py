"""
CSV Writer
"""

from pathlib import Path
import pandas as pd

from app.config.logging_config import get_logger

logger = get_logger()


class CSVWriter:

    @staticmethod
    def save(df: pd.DataFrame, filename: str):

        folder = Path("data/csv")

        folder.mkdir(parents=True, exist_ok=True)

        path = folder / filename

        df.to_csv(path, index=False)

        logger.info(f"Saved : {path}")