-- Star schema in the "mart" schema. Safe to run many times (IF NOT EXISTS).
-- No FOREIGN KEY constraints: DuckDB restricts updates on referenced rows,
-- so relations are kept by matching keys in the MERGE statements.
CREATE SCHEMA IF NOT EXISTS mart;

CREATE SEQUENCE IF NOT EXISTS mart.seq_city_id START 1;

CREATE TABLE IF NOT EXISTS mart.dim_country (
    country_code VARCHAR PRIMARY KEY,   -- ISO 3166-1 alpha-2
    country_name VARCHAR NOT NULL,
    region       VARCHAR NOT NULL,
    population   BIGINT
);

CREATE TABLE IF NOT EXISTS mart.dim_city (
    city_id      INTEGER PRIMARY KEY DEFAULT nextval('mart.seq_city_id'),  -- surrogate key
    city         VARCHAR NOT NULL,
    country_code VARCHAR NOT NULL,
    lat          DOUBLE NOT NULL,
    lon          DOUBLE NOT NULL,
    UNIQUE (city, country_code)         -- natural key
);

CREATE TABLE IF NOT EXISTS mart.dim_date (
    date_key    INTEGER PRIMARY KEY,    -- yyyymmdd, e.g. 20240106
    full_date   DATE NOT NULL,
    year        INTEGER NOT NULL,
    quarter     INTEGER NOT NULL,
    month       INTEGER NOT NULL,
    month_name  VARCHAR NOT NULL,
    day         INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,       -- ISO: 1 = Monday ... 7 = Sunday
    is_weekend  BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS mart.fact_weather (
    city_id       INTEGER NOT NULL,     -- -> dim_city
    country_code  VARCHAR NOT NULL,     -- -> dim_country
    date_key      INTEGER NOT NULL,     -- -> dim_date
    temp_max      DOUBLE,
    temp_min      DOUBLE,
    precipitation DOUBLE,
    PRIMARY KEY (city_id, date_key)     -- one row per city per day
);
