-- One row per city per day. Re-running updates values instead of adding duplicates.
MERGE INTO mart.fact_weather AS t
USING (
    SELECT
        c.city_id,
        w.country_code,
        CAST(strftime(w.date, '%Y%m%d') AS INTEGER) AS date_key,
        w.temp_max,
        w.temp_min,
        w.precipitation
    FROM staging.weather AS w
    JOIN mart.dim_city AS c
        ON c.city = w.city AND c.country_code = w.country_code
) AS s
ON t.city_id = s.city_id AND t.date_key = s.date_key
WHEN MATCHED THEN UPDATE SET
    temp_max      = s.temp_max,
    temp_min      = s.temp_min,
    precipitation = s.precipitation
WHEN NOT MATCHED THEN INSERT
    (city_id, country_code, date_key, temp_max, temp_min, precipitation)
    VALUES (s.city_id, s.country_code, s.date_key, s.temp_max, s.temp_min, s.precipitation);
