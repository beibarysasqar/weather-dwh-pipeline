"""Countries source: country name, region and population from the World Bank API."""
import logging

import pandas as pd
import requests

from src import config
from src.sources.base import BaseSource

logger = logging.getLogger(__name__)

AGGREGATES_REGION = "Aggregates"  # World Bank groups like "Arab World", not countries


def get_world_bank_rows(url: str, params: dict) -> list[dict]:
    """Call a World Bank endpoint and return the list of records."""
    params = {"format": "json", "per_page": 1000, **params}
    response = requests.get(url, params=params, timeout=config.REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    body = response.json()
    # Success: [metadata, records]. Error: [{"message": [...]}]
    if len(body) < 2 or body[1] is None:
        raise ValueError(f"Unexpected World Bank response: {body}")
    return body[1]


class CountriesApiSource(BaseSource):
    """One row per country: code, name, region, latest population."""

    name = "countries"
    key_columns = ["country_code"]
    required_columns = ["country_code", "country_name", "region"]

    def extract(self) -> pd.DataFrame:
        """Fetch the country list and latest population, joined by ISO2 code."""
        countries = pd.DataFrame(
            {
                "country_code": row["iso2Code"],
                "country_name": row["name"],
                "region": row["region"]["value"],
            }
            for row in get_world_bank_rows(config.COUNTRIES_API_URL, {})
        )
        population = pd.DataFrame(
            {"country_code": row["country"]["id"], "population": row["value"]}
            for row in get_world_bank_rows(config.POPULATION_API_URL, {"mrnev": 1})
        )
        return countries.merge(population, on="country_code", how="left")

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Drop aggregate regions, then nulls, bad values and duplicates."""
        df = df.copy()
        for column in ["country_code", "country_name", "region"]:
            df[column] = df[column].str.strip().replace("", None)
        df["population"] = pd.to_numeric(df["population"], errors="coerce").astype("Int64")

        before = len(df)
        df = df[df["region"] != AGGREGATES_REGION]
        logger.info("%s: removed %d aggregate rows (not countries)", self.name, before - len(df))

        invalid = (
            ~df["country_code"].str.fullmatch(r"[A-Z]{2}", na=False)
            | (df["population"] < 0).fillna(False)
        )
        return self.remove_bad_rows(df, invalid)
