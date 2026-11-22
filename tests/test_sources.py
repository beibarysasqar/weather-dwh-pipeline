from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.sources.cities import CitiesCsvSource
from src.sources.countries import CountriesApiSource
from src.sources.weather import WeatherApiSource


def fake_response(body) -> MagicMock:
    response = MagicMock()
    response.json.return_value = body
    return response


def test_cities_removes_duplicates_and_malformed_rows(tmp_path):
    path = tmp_path / "cities.csv"
    path.write_text(
        "city,country_code,lat,lon\n"
        "London,GB,51.5,-0.12\n"
        "London,GB,51.5,-0.12\n"  # duplicate
        ",FR,48.8,2.35\n"  # null city
        "Atlantis,XX,200,10\n"  # impossible latitude
        "Nowhere,G1,10,10\n"  # bad country code
        "Windhoek,NA,-22.56,17.08\n"  # "NA" is Namibia, not a missing value
    )
    source = CitiesCsvSource(path)

    result = source.clean(source.extract())

    assert list(result["city"]) == ["London", "Windhoek"]
    assert list(result["country_code"]) == ["GB", "NA"]
    assert list(result.columns) == ["city", "country_code", "lat", "lon"]
    assert result["lat"].dtype == "float64"


WEATHER_BODY = {
    "latitude": 51.49,
    "longitude": -0.16,
    "daily": {
        "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "temperature_2m_max": [12.2, 12.9, 5.0],
        "temperature_2m_min": [5.8, 8.3, 9.0],  # 3rd day: min > max
        "precipitation_sum": [10.5, None, 2.3],  # 2nd day: null
    },
}


def london_weather_source() -> WeatherApiSource:
    cities = pd.DataFrame([{"city": "London", "country_code": "GB", "lat": 51.5, "lon": -0.12}])
    return WeatherApiSource(cities, "2024-01-01", "2024-01-03")


@patch("src.sources.weather.requests.get")
def test_weather_extract_builds_one_row_per_day(mock_get):
    mock_get.return_value = fake_response(WEATHER_BODY)

    raw = london_weather_source().extract()

    assert len(raw) == 3
    assert list(raw.columns) == [
        "city", "country_code", "date", "temp_max", "temp_min", "precipitation"
    ]
    assert mock_get.call_args.kwargs["params"]["latitude"] == 51.5


@patch("src.sources.weather.requests.get")
def test_weather_clean_removes_malformed_and_duplicate_rows(mock_get):
    mock_get.return_value = fake_response(WEATHER_BODY)
    source = london_weather_source()
    raw = source.extract()
    raw = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)

    result = source.clean(raw)

    assert len(result) == 1
    assert result.loc[0, "date"] == date(2024, 1, 1)


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
def test_countries_clean_drops_aggregates_and_strips_text(mock_get):
    mock_get.side_effect = [fake_response(COUNTRIES_BODY), fake_response(POPULATION_BODY)]
    source = CountriesApiSource()

    result = source.clean(source.extract())

    assert list(result["country_code"]) == ["GB", "JP"]
    assert result.loc[0, "region"] == "Europe & Central Asia"
    assert result.loc[1, "population"] == 124000000


@patch("src.sources.countries.requests.get")
def test_countries_error_response_raises(mock_get):
    # World Bank answers 200 even for a bad request, the error is in the body
    mock_get.return_value = fake_response(
        [{"message": [{"id": "120", "key": "Invalid value",
                       "value": "The provided parameter value is not valid"}]}]
    )

    with pytest.raises(ValueError):
        CountriesApiSource().extract()
