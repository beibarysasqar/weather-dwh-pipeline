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

```bash
python -m src.pipeline
```

Steps: extract + clean (3 sources) -> load `staging` -> MERGE into `mart` -> check row counts.
Every step logs row counts. The pipeline is idempotent: a second run inserts 0 rows
(existing rows are updated by `MERGE`). Settings (DB path, date range) come from `.env`.

## Run with Docker

_TODO (next stages)._

## Run tests

```bash
pytest
```

## Schema

DuckDB file `warehouse.duckdb`, two schemas:

- `staging` - `cities`, `countries`, `weather`: cleaned source data, fully replaced on every run.
- `mart` - star schema, updated with `MERGE` (SQL in `sql/merge_*.sql`):

```
                    +-------------------+
                    |   dim_country     |
                    |-------------------|
                    | country_code (PK) |
                    | country_name      |
                    | region            |
                    | population        |
                    +---------+---------+
                              |
+-------------------+  +------+---------------+  +-------------------+
|    dim_city       |  |    fact_weather      |  |    dim_date       |
|-------------------|  |----------------------|  |-------------------|
| city_id (PK)      +--+ city_id    (PK)      +--+ date_key (PK)     |
| city              |  | date_key   (PK)      |  | full_date         |
| country_code      |  | country_code         |  | year, quarter     |
| lat, lon          |  | temp_max, temp_min   |  | month, month_name |
+-------------------+  | precipitation        |  | day, day_of_week  |
                       +----------------------+  | is_weekend        |
                                                 +-------------------+
```

- Grain of `fact_weather`: one row per city per day.
- `city_id` is a surrogate key (sequence); `date_key` is `yyyymmdd` (e.g. `20240106`).
- No FOREIGN KEY constraints (DuckDB restricts updates on referenced rows); keys are matched in MERGE.
