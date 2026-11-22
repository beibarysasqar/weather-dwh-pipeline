import pandas as pd
import requests

from src import config
from src.sources.base import BaseSource

DAILY_VARIABLES = "temperature_2m_max,temperature_2m_min,precipitation_sum"


class WeatherApiSource(BaseSource):
    name = "weather"
    key_columns = ["city", "country_code", "date"]
    required_columns = ["city", "country_code", "date", "temp_max", "temp_min", "precipitation"]

    # cities are only needed for extract(); transform() calls clean() without them
    def __init__(
        self,
        cities: pd.DataFrame | None = None,
        start_date: str = config.WEATHER_START_DATE,
        end_date: str = config.WEATHER_END_DATE,
    ) -> None:
        self.cities = cities if cities is not None else pd.DataFrame()
        self.start_date = start_date
        self.end_date = end_date

    def fetch_city(self, lat: float, lon: float) -> dict:
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "daily": DAILY_VARIABLES,
            "timezone": "UTC",
        }
        response = requests.get(
            config.WEATHER_API_URL, params=params, timeout=config.REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return response.json()["daily"]

    def extract(self) -> pd.DataFrame:
        frames = []
        for city in self.cities.itertuples():
            daily = self.fetch_city(city.lat, city.lon)
            frames.append(pd.DataFrame({
                "city": city.city,
                "country_code": city.country_code,
                "date": daily["time"],
                "temp_max": daily["temperature_2m_max"],
                "temp_min": daily["temperature_2m_min"],
                "precipitation": daily["precipitation_sum"],
            }))
        if not frames:
            return pd.DataFrame(columns=self.required_columns)
        return pd.concat(frames, ignore_index=True)

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        for column in ["temp_max", "temp_min", "precipitation"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        invalid = (
            (df["temp_min"] > df["temp_max"])
            | ~df["temp_max"].between(-90, 60)
            | ~df["temp_min"].between(-90, 60)
            | (df["precipitation"] < 0)
        )
        return self.remove_bad_rows(df, invalid)
