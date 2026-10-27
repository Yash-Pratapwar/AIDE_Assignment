WITH valid_scans AS (
    SELECT
        order_number,
        warehouse_code,
        event_type,
        event_timestamp_local
    FROM fact_wms_scan_events
    WHERE is_timestamp_valid
      AND NOT is_ambiguous_scan_id
      AND event_type IN ('RECEIVE', 'DISPATCH')
),
receives AS (
    SELECT
        order_number,
        warehouse_code,
        min(event_timestamp_local) AS receive_timestamp
    FROM valid_scans
    WHERE event_type = 'RECEIVE'
    GROUP BY order_number, warehouse_code
),
paired AS (
    SELECT
        receives.order_number,
        receives.warehouse_code,
        receives.receive_timestamp,
        min(scans.event_timestamp_local) AS dispatch_timestamp
    FROM receives
    LEFT JOIN valid_scans scans
        ON scans.order_number = receives.order_number
       AND scans.warehouse_code = receives.warehouse_code
       AND scans.event_type = 'DISPATCH'
       AND scans.event_timestamp_local > receives.receive_timestamp
    GROUP BY receives.order_number, receives.warehouse_code, receives.receive_timestamp
)
SELECT
    date_trunc('month', paired.receive_timestamp)::DATE AS receive_month,
    paired.warehouse_code,
    count(*) AS orders_with_receive_scan,
    count(*) FILTER (WHERE paired.dispatch_timestamp IS NOT NULL)
        AS orders_with_later_dispatch_scan,
    count(*) FILTER (WHERE paired.dispatch_timestamp IS NULL)
        AS orders_without_later_dispatch_scan,
    median(
        date_diff('second', paired.receive_timestamp, paired.dispatch_timestamp) / 3600.0
    ) FILTER (WHERE paired.dispatch_timestamp IS NOT NULL)
        AS median_receive_to_dispatch_hours,
    quantile_cont(
        date_diff('second', paired.receive_timestamp, paired.dispatch_timestamp) / 3600.0,
        0.9
    ) FILTER (WHERE paired.dispatch_timestamp IS NOT NULL)
        AS p90_receive_to_dispatch_hours
FROM paired
GROUP BY receive_month, paired.warehouse_code
ORDER BY receive_month, paired.warehouse_code
