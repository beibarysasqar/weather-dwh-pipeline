"""Cities source: reads the local cities CSV file."""
from pathlib import Path

import pandas as pd

from src import config
from src.sources.base import BaseSource


class CitiesCsvSource(BaseSource):
    """Cities with country code and coordinates from a CSV file."""

    name = "cities"
    key_columns = ["city", "country_code"]
    required_columns = ["city", "country_code", "lat", "lon"]

    def __init__(self, path: Path = config.CITIES_CSV_PATH) -> None:
        self.path = path

    def extract(self) -> pd.DataFrame:
        """Read the CSV as text; keep "NA" (Namibia) as a real country code."""
        return pd.read_csv(self.path, dtype=str, keep_default_na=False, na_values=[""])

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fix types, then drop nulls, impossible coordinates and duplicates."""
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
