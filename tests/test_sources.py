"""Tests for the data sources (no real network calls: requests.get is mocked)."""
import logging
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from src.sources.base import BaseSource
from src.sources.cities import CitiesCsvSource
from src.sources.countries import CountriesApiSource
from src.sources.weather import WeatherApiSource


def fake_response(body, status_code: int = 200) -> MagicMock:
    """Build a fake requests.Response that returns the given JSON body."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = body
    return response


# ---------- BaseSource ----------

def test_base_source_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseSource()


# ---------- Cities CSV ----------

def write_csv(tmp_path, text: str):
    path = tmp_path / "cities.csv"
    path.write_text(text)
    return path


def test_cities_removes_duplicates_and_malformed_rows(tmp_path):
    path = write_csv(
        tmp_path,
        "city,country_code,lat,lon\n"
        "London,GB,51.5,-0.12\n"
        "London,GB,51.5,-0.12\n"     # duplicate
        ",FR,48.8,2.35\n"            # null city
        "Atlantis,XX,200,10\n"       # impossible latitude
        "Nowhere,G1,10,10\n"         # bad country code
        "Windhoek,NA,-22.56,17.08\n" # "NA" = Namibia, must be kept
    )
    source = CitiesCsvSource(path)

    result = source.clean(source.extract())

    assert list(result["city"]) == ["London", "Windhoek"]
    assert list(result["country_code"]) == ["GB", "NA"]
    assert list(result.columns) == ["city", "country_code", "lat", "lon"]
    assert result["lat"].dtype == "float64"


def test_cities_logs_removed_row_counts(tmp_path, caplog):
    path = write_csv(
        tmp_path,
        "city,country_code,lat,lon\nParis,FR,48.8,2.35\nParis,FR,48.8,2.35\n",
    )
    caplog.set_level(logging.INFO)

    CitiesCsvSource(path).run()

    assert "cities: extracted 2 rows" in caplog.text
    assert "cities: removed 1 duplicate rows" in caplog.text
    assert "cities: cleaned 1 rows" in caplog.text


# ---------- Weather API ----------

WEATHER_BODY = {
    "latitude": 51.49,
    "longitude": -0.16,
    "daily": {
        "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "temperature_2m_max": [12.2, 12.9, 5.0],
        "temperature_2m_min": [5.8, 8.3, 9.0],  # 3rd day: min > max -> invalid
        "precipitation_sum": [10.5, None, 2.3],  # 2nd day: null -> malformed
    },
}


def make_weather_source() -> WeatherApiSource:
    cities = pd.DataFrame([{"city": "London", "country_code": "GB", "lat": 51.5, "lon": -0.12}])
    return WeatherApiSource(cities, "2024-01-01", "2024-01-03")


@patch("src.sources.weather.requests.get")
def test_weather_extract_builds_one_row_per_day(mock_get):
    mock_get.return_value = fake_response(WEATHER_BODY)

    raw = make_weather_source().extract()

    assert len(raw) == 3
    assert list(raw.columns) == [
        "city", "country_code", "date", "temp_max", "temp_min", "precipitation"
    ]
    assert mock_get.call_args.kwargs["params"]["latitude"] == 51.5


@patch("src.sources.weather.time.sleep")
@patch("src.sources.weather.requests.get")
def test_weather_retries_after_rate_limit(mock_get, mock_sleep, caplog):
    rate_limited = fake_response({"error": True, "reason": "limit exceeded"}, status_code=429)
    mock_get.side_effect = [rate_limited, fake_response(WEATHER_BODY)]
    caplog.set_level(logging.WARNING)

    raw = make_weather_source().extract()

    assert len(raw) == 3
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once()
    assert "rate limit hit (429)" in caplog.text


@patch("src.sources.weather.time.sleep")
@patch("src.sources.weather.requests.get")
def test_weather_gives_up_after_max_retries(mock_get, mock_sleep):
    rate_limited = fake_response({"error": True}, status_code=429)
    rate_limited.raise_for_status.side_effect = requests.HTTPError("429")
    mock_get.return_value = rate_limited

    with pytest.raises(requests.HTTPError):
        make_weather_source().extract()

    assert mock_get.call_count == 4  # first request + 3 retries
    assert mock_sleep.call_count == 3  # no useless wait after the last try


@patch("src.sources.weather.requests.get")
def test_weather_clean_removes_malformed_and_duplicate_rows(mock_get):
    mock_get.return_value = fake_response(WEATHER_BODY)
    source = make_weather_source()
    raw = source.extract()
    raw = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)  # add a duplicate

    result = source.clean(raw)

    assert len(result) == 1
    assert result.loc[0, "date"] == date(2024, 1, 1)


# ---------- Countries API ----------

COUNTRIES_BODY = [
    {"page": 1, "pages": 1, "total": 3},
    [
        {"iso2Code": "GB", "name": "United Kingdom", "region": {"value": "Europe & Central Asia "}},
        {"iso2Code": "1A", "name": "Arab World", "region": {"value": "Aggregates"}},
        {"iso2Code": "JP", "name": "Japan", "region": {"value": "East Asia & Pacific"}},
    ],
]
POPULATION_BODY = [
    {"page": 1, "pages": 1, "total": 2},
    [
        {"country": {"id": "GB", "value": "United Kingdom"}, "value": 69000000},
        {"country": {"id": "JP", "value": "Japan"}, "value": 124000000},
    ],
]


@patch("src.sources.countries.requests.get")
def test_countries_extract_joins_population(mock_get):
    mock_get.side_effect = [fake_response(COUNTRIES_BODY), fake_response(POPULATION_BODY)]

    raw = CountriesApiSource().extract()

    assert list(raw.columns) == ["country_code", "country_name", "region", "population"]
    assert raw.set_index("country_code").loc["JP", "population"] == 124000000


@patch("src.sources.countries.requests.get")
def test_countries_clean_drops_aggregates_and_strips_text(mock_get):
    mock_get.side_effect = [fake_response(COUNTRIES_BODY), fake_response(POPULATION_BODY)]
    source = CountriesApiSource()

    result = source.clean(source.extract())

    assert list(result["country_code"]) == ["GB", "JP"]
    assert result.loc[0, "region"] == "Europe & Central Asia"


@patch("src.sources.countries.requests.get")
def test_countries_error_response_raises(mock_get):
    mock_get.return_value = fake_response([{"message": [{"value": "Invalid value"}]}])

    with pytest.raises(ValueError):
        CountriesApiSource().extract()
