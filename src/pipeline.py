"""Run the whole ETL: extract -> clean -> load staging -> merge mart -> check counts."""
import logging
from pathlib import Path

import pandas as pd

from src import config
from src.load import check_counts, create_mart, get_connection, load_staging, merge_mart
from src.sources.cities import CitiesCsvSource
from src.sources.countries import CountriesApiSource
from src.sources.weather import WeatherApiSource

logger = logging.getLogger(__name__)


def extract_and_clean() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Extract and clean all three sources."""
    cities = CitiesCsvSource().run()
    countries = CountriesApiSource().run()
    weather = WeatherApiSource(cities).run()
    return cities, countries, weather


def run_pipeline(db_path: Path = config.DUCKDB_PATH) -> dict[str, int]:
    """Run all steps and return the final mart row counts."""
    cities, countries, weather = extract_and_clean()
    con = get_connection(db_path)
    try:
        create_mart(con)
        load_staging(con, cities, countries, weather)
        merge_mart(con)
        return check_counts(con)
    finally:
        con.close()


def main() -> None:
    """Command-line entry point: python -m src.pipeline."""
    logging.basicConfig(
        level=config.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logger.info("Pipeline started (weather %s .. %s)", config.WEATHER_START_DATE, config.WEATHER_END_DATE)
    run_pipeline()
    logger.info("Pipeline finished")


if __name__ == "__main__":
    main()
