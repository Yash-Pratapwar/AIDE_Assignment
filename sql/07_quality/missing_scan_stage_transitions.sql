WITH stage_summary AS (
    SELECT
        order_number,
        warehouse_code,
        count(*) FILTER (WHERE event_type = 'RECEIVE') AS receive_count,
        count(*) FILTER (WHERE event_type = 'PUTAWAY') AS putaway_count,
        count(*) FILTER (WHERE event_type = 'PICK') AS pick_count,
        count(*) FILTER (WHERE event_type = 'PACK') AS pack_count,
        count(*) FILTER (WHERE event_type = 'STAGE') AS stage_count,
        count(*) FILTER (WHERE event_type = 'DISPATCH') AS dispatch_count,
        min(CASE WHEN event_type = 'RECEIVE' THEN event_timestamp_local END) AS first_receive_ts,
        min(CASE WHEN event_type = 'DISPATCH' THEN event_timestamp_local END) AS first_dispatch_ts
    FROM fact_wms_scan_events
    WHERE is_timestamp_valid AND NOT is_ambiguous_scan_id
    GROUP BY order_number, warehouse_code
)
SELECT
    order_number,
    warehouse_code,
    receive_count,
    putaway_count,
    pick_count,
    pack_count,
    stage_count,
    dispatch_count,
    first_receive_ts,
    first_dispatch_ts,
    CASE
        WHEN dispatch_count > 0 AND receive_count = 0 THEN 'missing_receive_stage'
        WHEN dispatch_count > 0 AND (putaway_count = 0 OR pick_count = 0 OR pack_count = 0 OR stage_count = 0)
            THEN 'missing_intermediate_stage'
        ELSE 'complete_stage_chain'
    END AS issue_type
FROM stage_summary
WHERE dispatch_count > 0
  AND (
      receive_count = 0
      OR putaway_count = 0
      OR pick_count = 0
      OR pack_count = 0
      OR stage_count = 0
  )
ORDER BY warehouse_code, order_number
