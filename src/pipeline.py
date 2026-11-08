"""ETL steps: extract -> transform -> load_staging -> merge_mart -> check_counts.

Each step is a separate function so Airflow can run it as its own task.
Steps pass data to each other through CSV files in the work directory.
"""
import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src import config
from src.load import check_counts, create_mart, get_connection, load_staging, merge_mart
from src.sources.base import BaseSource
from src.sources.cities import CitiesCsvSource
from src.sources.countries import CountriesApiSource
from src.sources.weather import WeatherApiSource

logger = logging.getLogger(__name__)

DATASETS = ["cities", "countries", "weather"]


def read_csv_as_text(path: Path) -> pd.DataFrame:
    """Read a CSV with all columns as text; keep "NA" (Namibia) as a value."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])


def save_csv(df: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to CSV and log the row count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logger.info("saved %d rows to %s", len(df), path.name)


def weather_window(end_date: str, days: int = 14) -> tuple[str, str]:
    """Return (start, end) dates covering the last `days` days up to end_date."""
    end = date.fromisoformat(end_date)
    return (end - timedelta(days=days)).isoformat(), end.isoformat()


def extract(start_date: str, end_date: str, work_dir: Path = config.WORK_DIR) -> None:
    """Step 1: read all sources and save raw CSVs."""
    cities_source = CitiesCsvSource()
    save_csv(cities_source.extract(), work_dir / "raw_cities.csv")
    save_csv(CountriesApiSource().extract(), work_dir / "raw_countries.csv")
    # The weather API needs valid coordinates, so it uses the cleaned city list.
    weather = WeatherApiSource(cities_source.run(), start_date, end_date).extract()
    save_csv(weather, work_dir / "raw_weather.csv")


def extract_recent(end_date: str, days: int = 14, work_dir: Path = config.WORK_DIR) -> None:
    """Step 1 for the weekly DAG: extract the last `days` days up to end_date."""
    start_date, end_date = weather_window(end_date, days)
    logger.info("extracting weather %s .. %s", start_date, end_date)
    extract(start_date, end_date, work_dir)


def transform(work_dir: Path = config.WORK_DIR) -> None:
    """Step 2: clean the raw CSVs and save clean CSVs."""
    sources: dict[str, BaseSource] = {
        "cities": CitiesCsvSource(),
        "countries": CountriesApiSource(),
        "weather": WeatherApiSource(),
    }
    for name, source in sources.items():
        raw = read_csv_as_text(work_dir / f"raw_{name}.csv")
        save_csv(source.clean(raw), work_dir / f"clean_{name}.csv")


def load_staging_step(
    work_dir: Path = config.WORK_DIR, db_path: Path = config.DUCKDB_PATH
) -> None:
    """Step 3: load the clean CSVs into the staging schema."""
    frames = [read_csv_as_text(work_dir / f"clean_{name}.csv") for name in DATASETS]
    with get_connection(db_path) as con:
        load_staging(con, *frames)


def merge_mart_step(db_path: Path = config.DUCKDB_PATH) -> None:
    """Step 4: create the mart tables if needed and MERGE staging into them."""
    with get_connection(db_path) as con:
        create_mart(con)
        merge_mart(con)


def check_counts_step(db_path: Path = config.DUCKDB_PATH) -> dict[str, int]:
    """Step 5: log final mart row counts; fail if a table is empty."""
    with get_connection(db_path) as con:
        return check_counts(con)


def run_pipeline(
    start_date: str = config.WEATHER_START_DATE,
    end_date: str = config.WEATHER_END_DATE,
    db_path: Path = config.DUCKDB_PATH,
    work_dir: Path = config.WORK_DIR,
) -> dict[str, int]:
    """Run all five steps in order and return the final mart row counts."""
    extract(start_date, end_date, work_dir)
    transform(work_dir)
    load_staging_step(work_dir, db_path)
    merge_mart_step(db_path)
    return check_counts_step(db_path)


def main() -> None:
    """Command-line entry point: python -m src.pipeline."""
    logging.basicConfig(
        level=config.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logger.info(
        "Pipeline started (weather %s .. %s)", config.WEATHER_START_DATE, config.WEATHER_END_DATE
    )
    run_pipeline()
    logger.info("Pipeline finished")


if __name__ == "__main__":
    main()
