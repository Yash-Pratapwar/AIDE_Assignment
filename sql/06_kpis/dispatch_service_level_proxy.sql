WITH current_dispatched_orders AS (
    SELECT
        order_number,
        warehouse_code,
        requested_delivery_date,
        source_system
    FROM fact_sales_order_headers
    WHERE is_latest_version
      AND NOT is_deleted_current_order
      AND order_status = 'DISPATCHED'
      AND requested_delivery_date IS NOT NULL
),
dispatch_scans AS (
    SELECT
        order_number,
        warehouse_code,
        min(event_timestamp_local) AS dispatch_timestamp
    FROM fact_wms_scan_events
    WHERE event_type = 'DISPATCH'
      AND is_timestamp_valid
      AND NOT is_ambiguous_scan_id
    GROUP BY order_number, warehouse_code
)
SELECT
    date_trunc('month', orders.requested_delivery_date)::DATE AS requested_delivery_month,
    orders.warehouse_code,
    count(*) AS current_dispatched_order_count,
    count(*) FILTER (WHERE scans.dispatch_timestamp IS NOT NULL)
        AS orders_with_dispatch_scan,
    100.0 * count(*) FILTER (WHERE scans.dispatch_timestamp IS NOT NULL)
        / nullif(count(*), 0) AS dispatch_scan_coverage_pct,
    count(*) FILTER (
        WHERE scans.dispatch_timestamp::DATE <= orders.requested_delivery_date
    ) AS orders_dispatched_by_requested_date,
    100.0 * count(*) FILTER (
        WHERE scans.dispatch_timestamp::DATE <= orders.requested_delivery_date
    ) / nullif(count(scans.dispatch_timestamp), 0) AS on_time_dispatch_proxy_pct
FROM current_dispatched_orders orders
LEFT JOIN dispatch_scans scans
    ON scans.order_number = orders.order_number
   AND scans.warehouse_code = orders.warehouse_code
GROUP BY requested_delivery_month, orders.warehouse_code
ORDER BY requested_delivery_month, orders.warehouse_code
