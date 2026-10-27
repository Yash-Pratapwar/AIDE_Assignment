WITH valid_readings AS (
    SELECT
        reading_date,
        date_trunc('month', reading_date)::DATE AS reading_month,
        warehouse_code,
        vehicle_registration,
        temperature_celsius
    FROM fact_reefer_telemetry
    WHERE is_timestamp_valid
      AND temperature_celsius IS NOT NULL
      AND NOT is_temperature_unit_unresolved
      AND NOT is_ambiguous_reading_key
),
vehicle_days AS (
    SELECT
        reading_month,
        reading_date,
        warehouse_code,
        vehicle_registration,
        count(*) AS valid_reading_count,
        count(*) FILTER (WHERE temperature_celsius > 8.0)
            AS readings_above_upper_bound,
        count(*) FILTER (WHERE temperature_celsius < 2.0)
            AS readings_below_lower_bound,
        bool_or(temperature_celsius > 8.0) AS has_upper_bound_excursion
    FROM valid_readings
    GROUP BY reading_month, reading_date, warehouse_code, vehicle_registration
)
SELECT
    reading_month,
    warehouse_code,
    count(*) AS observed_vehicle_day_count,
    count(*) FILTER (WHERE has_upper_bound_excursion)
        AS vehicle_days_with_upper_bound_excursion,
    100.0 * count(*) FILTER (WHERE has_upper_bound_excursion)
        / nullif(count(*), 0) AS vehicle_day_upper_excursion_rate_pct,
    sum(valid_reading_count) AS valid_temperature_reading_count,
    sum(readings_above_upper_bound) AS readings_above_8c_count,
    sum(readings_below_lower_bound) AS readings_below_2c_count,
    count(DISTINCT vehicle_registration) AS observed_vehicle_count
FROM vehicle_days
GROUP BY reading_month, warehouse_code
ORDER BY reading_month, warehouse_code
