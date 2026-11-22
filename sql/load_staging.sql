-- Staging is fully reloaded on every run.
-- cities_df, countries_df and weather_df are pandas DataFrames registered from Python.
CREATE SCHEMA IF NOT EXISTS staging;

CREATE OR REPLACE TABLE staging.cities AS
SELECT
    CAST(city AS VARCHAR)         AS city,
    CAST(country_code AS VARCHAR) AS country_code,
    CAST(lat AS DOUBLE)           AS lat,
    CAST(lon AS DOUBLE)           AS lon
FROM cities_df;

CREATE OR REPLACE TABLE staging.countries AS
SELECT
    CAST(country_code AS VARCHAR) AS country_code,
    CAST(country_name AS VARCHAR) AS country_name,
    CAST(region AS VARCHAR)       AS region,
    CAST(population AS BIGINT)    AS population
FROM countries_df;

CREATE OR REPLACE TABLE staging.weather AS
SELECT
    CAST(city AS VARCHAR)         AS city,
    CAST(country_code AS VARCHAR) AS country_code,
    CAST(date AS DATE)            AS date,
    CAST(temp_max AS DOUBLE)      AS temp_max,
    CAST(temp_min AS DOUBLE)      AS temp_min,
    CAST(precipitation AS DOUBLE) AS precipitation
FROM weather_df;
