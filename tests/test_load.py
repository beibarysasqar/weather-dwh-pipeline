"""Tests for loading into DuckDB: star schema, MERGE idempotency, date dimension."""
from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from src.load import check_counts, create_mart, get_connection, load_staging, merge_mart
from src.pipeline import run_pipeline

CITIES = pd.DataFrame(
    [
        {"city": "London", "country_code": "GB", "lat": 51.5, "lon": -0.12},
        {"city": "Windhoek", "country_code": "NA", "lat": -22.56, "lon": 17.08},
    ]
)
COUNTRIES = pd.DataFrame(
    [
        {"country_code": "GB", "country_name": "United Kingdom", "region": "Europe", "population": 69_000_000},
        {"country_code": "NA", "country_name": "Namibia", "region": "Africa", "population": 3_000_000},
    ]
)
WEATHER = pd.DataFrame(
    [
        {"city": c, "country_code": cc, "date": d, "temp_max": 10.0, "temp_min": 2.0, "precipitation": 1.0}
        for c, cc in [("London", "GB"), ("Windhoek", "NA")]
        for d in [date(2024, 1, 5), date(2024, 1, 6)]
    ]
)


@pytest.fixture
def con(tmp_path):
    """A fresh DuckDB file with the mart tables created."""
    connection = get_connection(tmp_path / "test.duckdb")
    create_mart(connection)
    yield connection
    connection.close()


def load_and_merge(con, weather=WEATHER) -> dict[str, int]:
    """Load staging and merge into the mart, return inserted rows per table."""
    load_staging(con, CITIES, COUNTRIES, weather)
    return merge_mart(con)


def test_merge_twice_inserts_no_duplicates(con):
    first = load_and_merge(con)
    counts_after_first = check_counts(con)
    second = load_and_merge(con)

    assert first == {
        "mart.dim_country": 2, "mart.dim_city": 2, "mart.dim_date": 2, "mart.fact_weather": 4
    }
    assert all(rows == 0 for rows in second.values())
    assert check_counts(con) == counts_after_first


def test_merge_updates_changed_values(con):
    load_and_merge(con)
    changed = WEATHER.copy()
    changed["temp_max"] = 15.0

    inserted = load_and_merge(con, changed)

    assert inserted["mart.fact_weather"] == 0
    temps = con.execute("SELECT DISTINCT temp_max FROM mart.fact_weather").fetchall()
    assert temps == [(15.0,)]


def test_date_dimension_is_built_correctly(con):
    load_and_merge(con)

    row = con.execute(
        "SELECT full_date, year, quarter, month, month_name, day, day_of_week, is_weekend "
        "FROM mart.dim_date WHERE date_key = 20240106"
    ).fetchone()

    assert row == (date(2024, 1, 6), 2024, 1, 1, "January", 6, 6, True)  # a Saturday


def test_fact_table_has_star_schema_columns(con):
    load_and_merge(con)

    columns = [c[0] for c in con.execute("DESCRIBE mart.fact_weather").fetchall()]

    assert columns == [
        "city_id", "country_code", "date_key", "temp_max", "temp_min", "precipitation"
    ]


@patch("src.pipeline.extract_and_clean", return_value=(CITIES, COUNTRIES, WEATHER))
def test_pipeline_twice_gives_same_counts(mock_extract, tmp_path):
    db_path = tmp_path / "warehouse.duckdb"

    first = run_pipeline(db_path)
    second = run_pipeline(db_path)

    assert first == second
    assert second["mart.fact_weather"] == 4
