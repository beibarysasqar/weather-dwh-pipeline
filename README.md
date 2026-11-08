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

Steps (functions in `src/pipeline.py`, also used as Airflow tasks):
`extract` -> `transform` -> `load_staging` -> `merge_mart` -> `check_counts`.
Steps pass data through CSV files in `data/work/` (`raw_*.csv`, `clean_*.csv`).
Every step logs row counts. The pipeline is idempotent: a second run inserts 0 rows
(existing rows are updated by `MERGE`). Settings (DB path, date range) come from `.env`.

## Run with Docker (Airflow)

One container runs Airflow 3.3.2 in `standalone` mode. The DAG `weather_weekly`
(`dags/weather_dag.py`) runs every week and loads the last 14 days of weather
(the overlap with the previous run is safe: MERGE is idempotent).
The DuckDB file is stored on the host in `./warehouse/warehouse.duckdb`.

```bash
docker compose up -d --build                                   # build image and start Airflow
docker compose exec airflow airflow dags list                  # DAG weather_weekly is visible
docker compose exec airflow airflow dags unpause weather_weekly
docker compose exec airflow airflow dags trigger weather_weekly
docker compose exec airflow airflow dags list-runs weather_weekly
docker compose logs -f airflow                                 # Airflow process logs
docker compose down                                            # stop
```

UI: http://localhost:8080 (no login, local demo only). Task logs are in the UI
(DAG -> run -> task -> Logs) or in the container under `/opt/airflow/logs/`.

Notes:
- Unpausing the DAG immediately creates one scheduled run for the latest week.
- `max_active_runs=1`: DuckDB allows only one writer, so runs never overlap.
- The Airflow metadata DB (SQLite) lives inside the container; `docker compose down` resets
  run history (the DuckDB file in `./warehouse` stays).

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
