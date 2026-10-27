WITH feed_duplicates AS (
    SELECT sum(duplicate_rows_removed) AS duplicate_rows_removed
    FROM (
        SELECT duplicate_rows_removed FROM fact_pos_transactions
        WHERE has_exact_duplicates OR duplicate_rows_removed > 0

        UNION ALL

        SELECT duplicate_rows_removed FROM fact_reefer_telemetry
        WHERE has_exact_duplicates OR duplicate_rows_removed > 0

        UNION ALL

        SELECT duplicate_rows_removed FROM fact_wms_scan_events
        WHERE has_exact_duplicates OR duplicate_rows_removed > 0

        UNION ALL

        SELECT duplicate_rows_removed FROM fact_sales_order_headers
        WHERE duplicate_rows_removed > 0
    ) d
),
scan_issues AS (
    SELECT count(*) AS missing_scan_stage_orders
    FROM (
        SELECT order_number, warehouse_code
        FROM fact_wms_scan_events
        WHERE is_timestamp_valid AND NOT is_ambiguous_scan_id
        GROUP BY order_number, warehouse_code
        HAVING count(*) FILTER (WHERE event_type = 'DISPATCH') > 0
           AND (
               count(*) FILTER (WHERE event_type = 'RECEIVE') = 0
               OR count(*) FILTER (WHERE event_type = 'PUTAWAY') = 0
               OR count(*) FILTER (WHERE event_type = 'PICK') = 0
               OR count(*) FILTER (WHERE event_type = 'PACK') = 0
               OR count(*) FILTER (WHERE event_type = 'STAGE') = 0
           )
    ) s
),
telemetry_issues AS (
    SELECT count(*) AS temperature_anomalies
    FROM fact_reefer_telemetry
    WHERE is_temperature_missing
       OR is_temperature_unit_unresolved
       OR (temperature_celsius IS NOT NULL AND (temperature_celsius < 2.0 OR temperature_celsius > 8.0))
),
incomplete_dimensions AS (
    SELECT count(*) AS incomplete_reference_rows
    FROM (
        SELECT warehouse_code FROM dim_warehouse WHERE warehouse_code IS NULL OR warehouse_name IS NULL OR city IS NULL
        UNION ALL
        SELECT outlet_code FROM dim_outlet WHERE outlet_code IS NULL OR outlet_name IS NULL OR city IS NULL
        UNION ALL
        SELECT carrier_id FROM dim_carrier WHERE carrier_id IS NULL OR carrier_name IS NULL OR mode IS NULL
        UNION ALL
        SELECT sku_code FROM dim_product WHERE sku_code IS NULL OR product_name IS NULL OR category IS NULL
    ) d
),
date_range_issues AS (
    WITH expected_bounds AS (
        SELECT min(calendar_date) AS expected_min_date,
               max(calendar_date) AS expected_max_date
        FROM dim_date
    ),
    feed_ranges AS (
        SELECT min(sale_date) AS min_date, max(sale_date) AS max_date
        FROM fact_pos_transactions
        UNION ALL
        SELECT min(reading_date), max(reading_date)
        FROM fact_reefer_telemetry
        UNION ALL
        SELECT min(event_date), max(event_date)
        FROM fact_wms_scan_events
        UNION ALL
        SELECT min(order_date), max(order_date)
        FROM fact_sales_order_headers
    )
    SELECT count(*) AS out_of_range_feed_count
    FROM feed_ranges
    CROSS JOIN expected_bounds
    WHERE min_date < expected_min_date OR max_date > expected_max_date
)
SELECT
    'duplicate_rows_removed' AS metric_name,
    coalesce((SELECT duplicate_rows_removed FROM feed_duplicates), 0) AS metric_value
UNION ALL
SELECT
    'temperature_anomalies' AS metric_name,
    coalesce((SELECT temperature_anomalies FROM telemetry_issues), 0) AS metric_value
UNION ALL
SELECT
    'missing_scan_stage_orders' AS metric_name,
    coalesce((SELECT missing_scan_stage_orders FROM scan_issues), 0) AS metric_value
UNION ALL
SELECT
    'incomplete_reference_rows' AS metric_name,
    coalesce((SELECT incomplete_reference_rows FROM incomplete_dimensions), 0) AS metric_value
UNION ALL
SELECT
    'manifest_partition_issues' AS metric_name,
    count(*) AS metric_value
FROM manifest_partition_issues
UNION ALL
SELECT
    'out_of_range_feeds' AS metric_name,
    coalesce((SELECT out_of_range_feed_count FROM date_range_issues), 0) AS metric_value
ORDER BY metric_name
