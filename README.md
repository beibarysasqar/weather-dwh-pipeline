# Weather Data Warehouse (DuckDB + Airflow)

A small ETL project: daily weather and country data for ~100 world cities,
loaded into a DuckDB star schema.

## Data sources

| Source | What | Class |
|---|---|---|
| `data/cities.csv` | city, country_code (ISO2), lat, lon | `CitiesCsvSource` |
| [Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api) | daily max/min temperature, precipitation | `WeatherApiSource` |
| [World Bank API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392) | country name, region, latest population | `CountriesApiSource` |

No API keys are needed. Each class inherits `BaseSource` and has `extract()` and `clean()`.
`clean()` drops rows with nulls, impossible values and duplicates, and logs how many were removed.

## Project structure

```
src/          Python code (config, sources, pipeline steps)
src/sources/  One class per data source (all inherit BaseSource)
sql/          SQL files (schemas, staging, MERGE into mart)
dags/         Airflow DAG (only calls functions from src/)
tests/        pytest tests
data/         cities.csv seed file
```

## Local setup

Requires Python 3.11 (pandas 2.2 crashes on newer Python versions).

```bash
python3.11 -m venv .venv
# or, without a system Python 3.11:  uv venv --python 3.11 .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run the pipeline

_TODO (next stages)._

## Run with Docker

_TODO (next stages)._

## Run tests

```bash
pytest
```

## Schema

_TODO (next stages)._
