"""Weather source: daily weather from the Open-Meteo Archive API."""
import logging
import time

import pandas as pd
import requests

from src import config
from src.sources.base import BaseSource

logger = logging.getLogger(__name__)

DAILY_VARIABLES = "temperature_2m_max,temperature_2m_min,precipitation_sum"


class WeatherApiSource(BaseSource):
    """Daily max/min temperature and precipitation for each city."""

    name = "weather"
    key_columns = ["city", "country_code", "date"]
    required_columns = ["city", "country_code", "date", "temp_max", "temp_min", "precipitation"]

    def __init__(
        self,
        cities: pd.DataFrame | None = None,  # only needed by extract()
        start_date: str = config.WEATHER_START_DATE,
        end_date: str = config.WEATHER_END_DATE,
    ) -> None:
        self.cities = cities if cities is not None else pd.DataFrame()
        self.start_date = start_date
        self.end_date = end_date

    def fetch_city(self, lat: float, lon: float) -> dict:
        """Call the API for one location and return the "daily" block."""
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "daily": DAILY_VARIABLES,
            "timezone": "UTC",
        }
        # First request + up to RATE_LIMIT_MAX_RETRIES retries after a 429 answer.
        for retry in range(config.RATE_LIMIT_MAX_RETRIES + 1):
            response = requests.get(
                config.WEATHER_API_URL, params=params, timeout=config.REQUEST_TIMEOUT_SECONDS
            )
            if response.status_code != 429 or retry == config.RATE_LIMIT_MAX_RETRIES:
                break
            logger.warning(
                "weather: rate limit hit (429), waiting %d s (retry %d of %d)",
                config.RATE_LIMIT_WAIT_SECONDS, retry + 1, config.RATE_LIMIT_MAX_RETRIES,
            )
            time.sleep(config.RATE_LIMIT_WAIT_SECONDS)
        response.raise_for_status()  # still 429 after all retries, or another error
        return response.json()["daily"]

    def extract(self) -> pd.DataFrame:
        """Fetch weather for every city (one request per city)."""
        frames = []
        for city in self.cities.itertuples():
            daily = self.fetch_city(city.lat, city.lon)
            frames.append(
                pd.DataFrame(
                    {
                        "city": city.city,
                        "country_code": city.country_code,
                        "date": daily["time"],
                        "temp_max": daily["temperature_2m_max"],
                        "temp_min": daily["temperature_2m_min"],
                        "precipitation": daily["precipitation_sum"],
                    }
                )
            )
        if not frames:
            return pd.DataFrame(columns=self.required_columns)
        return pd.concat(frames, ignore_index=True)

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fix types, then drop nulls, impossible values and duplicates."""
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        for column in ["temp_max", "temp_min", "precipitation"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        invalid = (
            (df["temp_max"] < df["temp_min"])
            | ~df["temp_max"].between(-90, 60)
            | ~df["temp_min"].between(-90, 60)
            | (df["precipitation"] < 0)
        )
        return self.remove_bad_rows(df, invalid)
