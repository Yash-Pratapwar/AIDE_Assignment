WITH feed_ranges AS (
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
SELECT *
FROM feed_ranges
ORDER BY feed_name
