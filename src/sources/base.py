"""Base class shared by all data sources."""
import logging
from abc import ABC, abstractmethod

import pandas as pd

logger = logging.getLogger(__name__)


class BaseSource(ABC):
    """A data source that can extract raw data and clean it."""

    name: str = "base"
    key_columns: list[str] = []  # must be unique per row
    required_columns: list[str] = []  # must not be null

    @abstractmethod
    def extract(self) -> pd.DataFrame:
        """Read raw data from the source."""

    @abstractmethod
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a cleaned copy of the raw data."""

    def run(self) -> pd.DataFrame:
        """Extract and clean the data, logging row counts."""
        raw = self.extract()
        logger.info("%s: extracted %d rows", self.name, len(raw))
        cleaned = self.clean(raw)
        logger.info("%s: cleaned %d rows", self.name, len(cleaned))
        return cleaned

    def remove_bad_rows(self, df: pd.DataFrame, invalid: pd.Series) -> pd.DataFrame:
        """Drop rows with nulls, invalid values (mask) or duplicate keys, and log counts."""
        before = len(df)
        df = df.dropna(subset=self.required_columns)
        logger.info("%s: removed %d rows with nulls", self.name, before - len(df))

        before = len(df)
        df = df[~invalid.reindex(df.index, fill_value=False)]
        logger.info("%s: removed %d rows with invalid values", self.name, before - len(df))

        before = len(df)
        df = df.drop_duplicates(subset=self.key_columns)
        logger.info("%s: removed %d duplicate rows", self.name, before - len(df))

        return df.reset_index(drop=True)
