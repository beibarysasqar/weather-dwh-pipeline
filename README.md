# Weather Data Warehouse (DuckDB + Airflow)

[![CI](https://github.com/beibarysasqar/weather-dwh-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/beibarysasqar/weather-dwh-pipeline/actions/workflows/ci.yml)

A small ETL project: daily weather and country data for ~100 world cities,
cleaned with pandas and loaded into a DuckDB star schema. Runs weekly in Airflow (Docker),
tested with pytest in GitHub Actions.

## Architecture

```
 data/cities.csv ----+
 Open-Meteo API -----+--> extract --> transform --> load_staging --> merge_mart --> check_counts
 World Bank API -----+    (raw CSV)   (clean CSV)   (staging.*)      (mart.* via    (row counts,
                                                                       SQL MERGE)     fail if empty)
```

- Each step is a function in `src/pipeline.py`. The Airflow DAG calls the same functions,
  one task per step. Steps pass data through CSV files in `data/work/`.
- `staging` is fully reloaded every run; `mart` is updated with `MERGE` (insert new, update existing).
- Every step logs row counts (extracted / removed / cleaned / loaded / inserted / updated).

## Data sources

| Source | What | Class |
|---|---|---|
| `data/cities.csv` | city, country_code (ISO2), lat, lon | `CitiesCsvSource` |
| [Open-Meteo Archive API](https://open-meteo.com/en/docs/historical-weather-api) | daily max/min temperature, precipitation | `WeatherApiSource` |
| [World Bank API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392) | country name, region, latest population | `CountriesApiSource` |

No API keys are needed. Each class inherits `BaseSource` (`extract()` -> DataFrame, `clean()` -> DataFrame).
`clean()` drops rows with nulls, impossible values (e.g. `temp_min > temp_max`, latitude > 90)
and duplicates, and logs how many rows were removed at each check.

## Project structure

```
src/
  config.py          settings from .env
  sources/           BaseSource + one class per data source
  load.py            DuckDB helpers: run SQL files, load staging, MERGE, check counts
  pipeline.py        the 5 pipeline steps + CLI entry point
sql/                 all SQL: create_mart, load_staging, merge_* (one file per table)
dags/weather_dag.py  weekly Airflow DAG (only calls src/ functions)
tests/               pytest tests (no network: requests is mocked)
data/cities.csv      seed file with 113 cities
Dockerfile, docker-compose.yml
.github/workflows/ci.yml
```

## Configuration

Copy `.env.example` to `.env`. Relative paths are resolved from the project root.

| Variable | Default | Meaning |
|---|---|---|
| `DUCKDB_PATH` | `warehouse.duckdb` | DuckDB database file |
| `CITIES_CSV_PATH` | `data/cities.csv` | cities seed file |
| `WORK_DIR` | `data/work` | CSV files passed between steps |
| `WEATHER_START_DATE` | `2024-01-01` | first day to load (CLI run) |
| `WEATHER_END_DATE` | `2024-12-31` | last day to load (CLI run) |
| `LOG_LEVEL` | `INFO` | logging level |

## Run locally

Requires Python 3.11 (pandas 2.2 crashes on newer Python versions).

```bash
python3.11 -m venv .venv
# or, without a system Python 3.11:  uv venv --python 3.11 .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

python -m src.pipeline
```

Tip: for a quick run use a short date range (a full year for 113 cities may hit
Open-Meteo's per-minute limit):

```bash
WEATHER_START_DATE=2024-01-01 WEATHER_END_DATE=2024-01-07 python -m src.pipeline
```

Run it twice: the second run logs `inserted 0` for every mart table.

## Run with Docker (Airflow)

One container runs Airflow 3.3.2 in `standalone` mode. The DAG `weather_weekly`
runs every week and loads the last 14 days of weather.
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

- Unpausing the DAG immediately creates one scheduled run for the latest week.
- The Airflow metadata DB (SQLite) lives inside the container; `docker compose down` resets
  run history. The DuckDB file in `./warehouse` stays.

## Tests and CI

```bash
pytest -v
ruff check src tests dags
```

15 fast tests, no real network calls (`requests.get` is mocked). They cover:
duplicate and malformed rows removed, row-count logging, column schema, World Bank error
response, date dimension values, MERGE twice gives the same row counts, changed values are
updated, full pipeline twice is idempotent, "NA" (Namibia) survives CSV round-trips.

GitHub Actions (`.github/workflows/ci.yml`) runs lint + tests on every push and pull request,
every Monday at 06:00 UTC, and manually via "Run workflow". No secrets needed.

## Schema

DuckDB file `warehouse.duckdb`, two schemas:

- `staging` - `cities`, `countries`, `weather`: cleaned source data, replaced on every run.
- `mart` - star schema, updated with `MERGE` (`sql/merge_*.sql`):

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

Example query:

```sql
SELECT co.region, d.month_name, ROUND(AVG(f.temp_max), 1) AS avg_temp_max
FROM mart.fact_weather f
JOIN mart.dim_country co USING (country_code)
JOIN mart.dim_date d USING (date_key)
GROUP BY co.region, d.month, d.month_name
ORDER BY co.region, d.month;
```

## Design decisions

- **Idempotency:** primary keys + `MERGE` (insert new rows, update existing ones), so re-running
  the pipeline never creates duplicates. Requires DuckDB >= 1.4 (pinned to 1.4.0).
- **14-day window in the weekly DAG:** overlaps the previous week on purpose. It is safe because of
  MERGE, and it picks up days that Open-Meteo publishes with a few days delay.
- **World Bank instead of REST Countries:** REST Countries v3.1 was shut down and v5 needs an API key.
  World Bank has no key. Taiwan is not in World Bank data, so the city list does not include Taipei.
- **No FOREIGN KEY constraints:** DuckDB restricts updates on rows referenced by a foreign key;
  keys are matched in the MERGE statements instead.
- **`max_active_runs=1`:** DuckDB allows only one writer, so DAG runs never overlap.
- **SQL in files:** all SQL lives in `sql/`; Python only runs the files and counts rows.
