-- Match cities by natural key (city, country_code). city_id comes from the sequence.
MERGE INTO mart.dim_city AS t
USING staging.cities AS s
ON t.city = s.city AND t.country_code = s.country_code
WHEN MATCHED THEN UPDATE SET
    lat = s.lat,
    lon = s.lon
WHEN NOT MATCHED THEN INSERT (city, country_code, lat, lon)
    VALUES (s.city, s.country_code, s.lat, s.lon);
