-- Add every new date seen in staging.weather. Dates never change, so insert only.
MERGE INTO mart.dim_date AS t
USING (
    SELECT DISTINCT
        CAST(strftime(date, '%Y%m%d') AS INTEGER) AS date_key,
        date                                      AS full_date,
        year(date)                                AS year,
        quarter(date)                             AS quarter,
        month(date)                               AS month,
        monthname(date)                           AS month_name,
        day(date)                                 AS day,
        isodow(date)                              AS day_of_week,
        isodow(date) IN (6, 7)                    AS is_weekend
    FROM staging.weather
) AS s
ON t.date_key = s.date_key
WHEN NOT MATCHED THEN INSERT
    (date_key, full_date, year, quarter, month, month_name, day, day_of_week, is_weekend)
    VALUES (s.date_key, s.full_date, s.year, s.quarter, s.month, s.month_name,
            s.day, s.day_of_week, s.is_weekend);
