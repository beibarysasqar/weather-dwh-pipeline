-- Insert new countries, update name/region/population of existing ones.
MERGE INTO mart.dim_country AS t
USING staging.countries AS s
ON t.country_code = s.country_code
WHEN MATCHED THEN UPDATE SET
    country_name = s.country_name,
    region       = s.region,
    population   = s.population
WHEN NOT MATCHED THEN INSERT (country_code, country_name, region, population)
    VALUES (s.country_code, s.country_name, s.region, s.population);
