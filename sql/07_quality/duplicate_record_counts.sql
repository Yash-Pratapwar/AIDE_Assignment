WITH feed_duplicate_totals AS (
    SELECT 'fact_pos_transactions' AS feed_name,
           count(*) AS rows_flagged,
           coalesce(sum(duplicate_rows_removed), 0) AS duplicate_rows_removed
    FROM fact_pos_transactions
    WHERE has_exact_duplicates OR duplicate_rows_removed > 0

    UNION ALL

    SELECT 'fact_reefer_telemetry' AS feed_name,
           count(*) AS rows_flagged,
           coalesce(sum(duplicate_rows_removed), 0) AS duplicate_rows_removed
    FROM fact_reefer_telemetry
    WHERE has_exact_duplicates OR duplicate_rows_removed > 0

    UNION ALL

    SELECT 'fact_wms_scan_events' AS feed_name,
           count(*) AS rows_flagged,
           coalesce(sum(duplicate_rows_removed), 0) AS duplicate_rows_removed
    FROM fact_wms_scan_events
    WHERE has_exact_duplicates OR duplicate_rows_removed > 0

    UNION ALL

    SELECT 'fact_sales_order_headers' AS feed_name,
           count(*) AS rows_flagged,
           coalesce(sum(duplicate_rows_removed), 0) AS duplicate_rows_removed
    FROM fact_sales_order_headers
    WHERE duplicate_rows_removed > 0
)
SELECT
    feed_name,
    rows_flagged,
    duplicate_rows_removed
FROM feed_duplicate_totals
ORDER BY feed_name
