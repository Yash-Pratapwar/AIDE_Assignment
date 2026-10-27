SELECT
    reading_date,
    warehouse_code,
    vehicle_registration,
    device_id,
    temperature_celsius,
    normalized_temp_unit,
    CASE
        WHEN is_temperature_missing THEN 'missing_temperature'
        WHEN is_temperature_unit_unresolved THEN 'unit_unresolved'
        WHEN temperature_celsius IS NOT NULL AND (temperature_celsius < 2.0 OR temperature_celsius > 8.0)
            THEN 'temperature_out_of_band'
        ELSE 'valid_temperature'
    END AS anomaly_type,
    is_timestamp_valid
FROM fact_reefer_telemetry
WHERE is_temperature_missing
   OR is_temperature_unit_unresolved
   OR (temperature_celsius IS NOT NULL AND (temperature_celsius < 2.0 OR temperature_celsius > 8.0))
ORDER BY reading_date, warehouse_code, vehicle_registration
