import logging

import pandas as pd

logger = logging.getLogger(__name__)


class BaseSource:
    name = "base"
    key_columns: list[str] = []
    required_columns: list[str] = []

    def extract(self) -> pd.DataFrame:
        raise NotImplementedError

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError

    def remove_bad_rows(self, df: pd.DataFrame, invalid: pd.Series) -> pd.DataFrame:
        before = len(df)
        df = df.dropna(subset=self.required_columns)
        logger.info("%s: removed %d rows with nulls", self.name, before - len(df))

        # invalid was built on the full df, dropna removed some of its index labels
        before = len(df)
        df = df[~invalid.reindex(df.index, fill_value=False)]
        logger.info("%s: removed %d rows with invalid values", self.name, before - len(df))

        before = len(df)
        df = df.drop_duplicates(subset=self.key_columns)
        logger.info("%s: removed %d duplicate rows", self.name, before - len(df))
        return df.reset_index(drop=True)
