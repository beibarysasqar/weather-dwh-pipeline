from pathlib import Path

import pandas as pd

from src import config
from src.sources.base import BaseSource


class CitiesCsvSource(BaseSource):
    name = "cities"
    key_columns = ["city", "country_code"]
    required_columns = ["city", "country_code", "lat", "lon"]

    def __init__(self, path: Path = config.CITIES_CSV_PATH) -> None:
        self.path = path

    def extract(self) -> pd.DataFrame:
        # by default pandas reads "NA" (Namibia) as NaN, so only empty cells are nulls
        return pd.read_csv(self.path, dtype=str, keep_default_na=False, na_values=[""])

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["city"] = df["city"].str.strip()
        df["country_code"] = df["country_code"].str.strip().str.upper()
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

        invalid = (
            ~df["lat"].between(-90, 90)
            | ~df["lon"].between(-180, 180)
            | ~df["country_code"].str.fullmatch(r"[A-Z]{2}", na=False)
        )
        return self.remove_bad_rows(df, invalid)
