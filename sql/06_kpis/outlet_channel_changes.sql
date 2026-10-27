SELECT
    outlet_code,
    previous_channel,
    new_channel,
    effective_start AS effective_start_utc,
    timezone('Asia/Kolkata', effective_start)::DATE AS effective_date_local,
    effective_end,
    source_seq,
    source_extract_date,
    source_file
FROM dim_channel_history
WHERE previous_channel IS NOT NULL
  AND previous_channel IS DISTINCT FROM new_channel
ORDER BY outlet_code, effective_start
