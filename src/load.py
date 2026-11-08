"""Load cleaned DataFrames into DuckDB: staging tables, then MERGE into the mart."""
import logging
from pathlib import Path

import duckdb
import pandas as pd

from src import config

logger = logging.getLogger(__name__)

SQL_DIR = config.PROJECT_ROOT / "sql"
STAGING_TABLES = ["staging.cities", "staging.countries", "staging.weather"]
# Dimensions first: the fact MERGE looks up city_id in mart.dim_city.
MART_MERGES = [
    ("mart.dim_country", "merge_dim_country.sql"),
    ("mart.dim_city", "merge_dim_city.sql"),
    ("mart.dim_date", "merge_dim_date.sql"),
    ("mart.fact_weather", "merge_fact_weather.sql"),
]


def get_connection(db_path: Path = config.DUCKDB_PATH) -> duckdb.DuckDBPyConnection:
    """Open (or create) the DuckDB database file."""
    return duckdb.connect(str(db_path))


def run_sql_file(con: duckdb.DuckDBPyConnection, file_name: str) -> duckdb.DuckDBPyConnection:
    """Execute all statements from a file in the sql/ folder."""
    return con.execute((SQL_DIR / file_name).read_text())


def count_rows(con: duckdb.DuckDBPyConnection, table: str) -> int:
    """Return the number of rows in a table (DuckDB relational API, no SQL string)."""
    return con.table(table).count("*").fetchone()[0]


def create_mart(con: duckdb.DuckDBPyConnection) -> None:
    """Create the mart schema and tables if they do not exist."""
    run_sql_file(con, "create_mart.sql")


def load_staging(
    con: duckdb.DuckDBPyConnection,
    cities: pd.DataFrame,
    countries: pd.DataFrame,
    weather: pd.DataFrame,
) -> dict[str, int]:
    """Replace the staging tables with the given DataFrames."""
    con.register("cities_df", cities)
    con.register("countries_df", countries)
    con.register("weather_df", weather)
    run_sql_file(con, "load_staging.sql")

    counts = {table: count_rows(con, table) for table in STAGING_TABLES}
    for table, rows in counts.items():
        logger.info("%s: loaded %d rows", table, rows)
    return counts


def merge_mart(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Run the MERGE files and return the number of inserted rows per mart table."""
    inserted = {}
    for table, file_name in MART_MERGES:
        before = count_rows(con, table)
        affected = run_sql_file(con, file_name).fetchone()[0]
        inserted[table] = count_rows(con, table) - before
        logger.info(
            "%s: merged %d rows (inserted %d, updated %d)",
            table, affected, inserted[table], affected - inserted[table],
        )
    return inserted


def check_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Log the final row count of each mart table and fail if one is empty."""
    counts = {table: count_rows(con, table) for table, _ in MART_MERGES}
    for table, rows in counts.items():
        logger.info("%s: %d rows in total", table, rows)
    empty = [table for table, rows in counts.items() if rows == 0]
    if empty:
        raise ValueError(f"Empty mart tables: {empty}")
    return counts
