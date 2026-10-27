WITH expected_bounds AS (
    SELECT min(calendar_date) AS expected_min_date,
           max(calendar_date) AS expected_max_date
    FROM dim_date
),
feed_ranges AS (
    SELECT 'fact_pos_transactions' AS feed_name,
           count(*) AS row_count,
           min(sale_date) AS min_date,
           max(sale_date) AS max_date
    FROM fact_pos_transactions

    UNION ALL

    SELECT 'fact_reefer_telemetry' AS feed_name,
           count(*) AS row_count,
           min(reading_date) AS min_date,
           max(reading_date) AS max_date
    FROM fact_reefer_telemetry

    UNION ALL

    SELECT 'fact_wms_scan_events' AS feed_name,
           count(*) AS row_count,
           min(event_date) AS min_date,
           max(event_date) AS max_date
    FROM fact_wms_scan_events

    UNION ALL

    SELECT 'fact_sales_order_headers' AS feed_name,
           count(*) AS row_count,
           min(order_date) AS min_date,
           max(order_date) AS max_date
    FROM fact_sales_order_headers
)
SELECT
    feed_ranges.*,
    expected_bounds.expected_min_date,
    expected_bounds.expected_max_date,
    CASE
        WHEN feed_ranges.min_date < expected_bounds.expected_min_date
          OR feed_ranges.max_date > expected_bounds.expected_max_date
            THEN 'outside_expected_range'
        ELSE 'within_expected_range'
    END AS date_range_status
FROM feed_ranges
CROSS JOIN expected_bounds
ORDER BY feed_name
