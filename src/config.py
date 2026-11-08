"""Project configuration loaded from environment variables (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Paths (relative paths are resolved from the project root)
DUCKDB_PATH = PROJECT_ROOT / os.getenv("DUCKDB_PATH", "warehouse.duckdb")
CITIES_CSV_PATH = PROJECT_ROOT / os.getenv("CITIES_CSV_PATH", "data/cities.csv")
WORK_DIR = PROJECT_ROOT / os.getenv("WORK_DIR", "data/work")  # CSV files passed between steps

# Weather date range (YYYY-MM-DD)
WEATHER_START_DATE = os.getenv("WEATHER_START_DATE", "2024-01-01")
WEATHER_END_DATE = os.getenv("WEATHER_END_DATE", "2024-12-31")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Public APIs (no keys needed)
WEATHER_API_URL = "https://archive-api.open-meteo.com/v1/archive"
COUNTRIES_API_URL = "https://api.worldbank.org/v2/country"
POPULATION_API_URL = "https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL"
REQUEST_TIMEOUT_SECONDS = 60
