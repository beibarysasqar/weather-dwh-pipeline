# Weather Data Warehouse (DuckDB + Airflow)

A small ETL project: daily weather (Open-Meteo) and country data (REST Countries)
for ~100 world cities, loaded into a DuckDB star schema.

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

Requires Python 3.11.

```bash
python3.11 -m venv .venv
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
