WITH finance_weeks AS (
    SELECT
        week_ending AS finance_week_label,
        week_ending AS period_start,
        week_ending + INTERVAL '7 days' AS period_end_exclusive,
        channel,
        gross_sales_inr AS finance_gross_sales_inr,
        units_sold AS finance_units_sold,
        basket_count AS finance_basket_count,
        prepared_by,
        note
    FROM legacy_finance
),
period_anchor AS (
    SELECT min(period_start) AS first_period_start
    FROM finance_weeks
),
pos_event_comparison AS (
    SELECT
        (
            a.first_period_start
            + floor(date_diff('day', a.first_period_start, s.sale_date) / 7)::INTEGER * 7
        )::DATE AS period_start,
        s.sales_channel AS channel,
        sum(s.gross_sales_ex_tax_inr) AS event_dedup_gross_sales_inr,
        sum(s.net_sales_ex_tax_inr) AS event_dedup_net_sales_inr,
        sum(s.quantity) AS event_dedup_units_sold,
        count(DISTINCT s.basket_id) AS event_dedup_basket_count
    FROM fact_reconciled_sales s
    CROSS JOIN period_anchor a
    WHERE s.sale_date >= a.first_period_start
      AND s.sale_date < (SELECT max(period_end_exclusive) FROM finance_weeks)
    GROUP BY 1, 2
),
pos_ingest_comparison AS (
    SELECT
        (
            a.first_period_start
            + floor(date_diff('day', a.first_period_start, s.ingest_date) / 7)::INTEGER * 7
        )::DATE AS period_start,
        s.sales_channel AS channel,
        sum(s.gross_sales_ex_tax_inr) AS ingest_gross_sales_inr,
        sum(s.net_sales_ex_tax_inr) AS ingest_net_sales_inr,
        sum(s.quantity) AS ingest_units_sold,
        count(DISTINCT s.basket_id) AS ingest_basket_count,
        sum(s.gross_sales_ex_tax_inr * (s.duplicate_rows_removed + 1))
            AS ingest_duplicate_inclusive_gross_sales_inr,
        sum(s.net_sales_ex_tax_inr * (s.duplicate_rows_removed + 1))
            AS ingest_duplicate_inclusive_net_sales_inr,
        sum(s.quantity * (s.duplicate_rows_removed + 1))
            AS ingest_duplicate_inclusive_units_sold,
        sum(s.duplicate_rows_removed) AS duplicate_rows_removed
    FROM fact_reconciled_sales s
    CROSS JOIN period_anchor a
    WHERE s.ingest_date >= a.first_period_start
      AND s.ingest_date < (SELECT max(period_end_exclusive) FROM finance_weeks)
    GROUP BY 1, 2
),
erp_orders_by_week AS (
    SELECT
        (
            a.first_period_start
            + floor(date_diff('day', a.first_period_start, o.order_date) / 7)::INTEGER * 7
        )::DATE AS period_start,
        coalesce(channel.new_channel, 'UNKNOWN') AS channel,
        sum(o.order_value_gross) AS current_erp_order_gross_value_inr,
        count(*) AS current_erp_order_count,
        sum(o.line_count) AS current_erp_order_line_count,
        count(*) FILTER (WHERE o.has_known_partner_freight_adjustment)
            AS partner_api_order_count
    FROM fact_sales_order_headers o
    CROSS JOIN period_anchor a
    LEFT JOIN dim_channel_history channel
        ON channel.outlet_code = o.outlet_code
       AND timezone('Asia/Kolkata', channel.effective_start) <= o.order_date::TIMESTAMP
       AND (
            timezone('Asia/Kolkata', channel.effective_end) > o.order_date::TIMESTAMP
            OR channel.effective_end IS NULL
       )
    WHERE o.is_latest_version
      AND NOT o.is_deleted_current_order
      AND o.order_date >= a.first_period_start
      AND o.order_date < (SELECT max(period_end_exclusive) FROM finance_weeks)
    GROUP BY 1, 2
),
comparison_keys AS (
    SELECT period_start, channel FROM finance_weeks
    UNION
    SELECT period_start, channel FROM pos_event_comparison
    UNION
    SELECT period_start, channel FROM pos_ingest_comparison
    UNION
    SELECT period_start, channel FROM erp_orders_by_week
)
SELECT
    keys.period_start AS finance_week_label,
    keys.period_start,
    (keys.period_start + INTERVAL '7 days')::DATE AS period_end_exclusive,
    keys.channel,
    finance.finance_gross_sales_inr,
    event_pos.event_dedup_gross_sales_inr,
    event_pos.event_dedup_net_sales_inr,
    ingest_pos.ingest_gross_sales_inr,
    ingest_pos.ingest_net_sales_inr,
    ingest_pos.ingest_duplicate_inclusive_gross_sales_inr,
    ingest_pos.ingest_duplicate_inclusive_net_sales_inr,
    erp.current_erp_order_gross_value_inr,
    (event_pos.event_dedup_gross_sales_inr - finance.finance_gross_sales_inr)
        AS event_basis_gross_variance_inr,
    100.0 * (event_pos.event_dedup_gross_sales_inr - finance.finance_gross_sales_inr)
        / nullif(finance.finance_gross_sales_inr, 0)
        AS event_basis_gross_variance_pct,
    (ingest_pos.ingest_gross_sales_inr - finance.finance_gross_sales_inr)
        AS ingest_basis_gross_variance_inr,
    100.0 * (ingest_pos.ingest_gross_sales_inr - finance.finance_gross_sales_inr)
        / nullif(finance.finance_gross_sales_inr, 0)
        AS ingest_basis_gross_variance_pct,
    (
        ingest_pos.ingest_duplicate_inclusive_gross_sales_inr
        - finance.finance_gross_sales_inr
    ) AS ingest_duplicate_inclusive_gross_variance_inr,
    (
        ingest_pos.ingest_duplicate_inclusive_gross_sales_inr
        - ingest_pos.ingest_gross_sales_inr
    ) AS estimated_duplicate_gross_inflation_inr,
    event_pos.event_dedup_units_sold,
    ingest_pos.ingest_units_sold,
    ingest_pos.ingest_duplicate_inclusive_units_sold,
    finance.finance_units_sold,
    (event_pos.event_dedup_units_sold - finance.finance_units_sold)
        AS event_basis_units_variance,
    (ingest_pos.ingest_units_sold - finance.finance_units_sold)
        AS ingest_basis_units_variance,
    (ingest_pos.ingest_duplicate_inclusive_units_sold - finance.finance_units_sold)
        AS ingest_duplicate_inclusive_units_variance,
    event_pos.event_dedup_basket_count,
    ingest_pos.ingest_basket_count,
    finance.finance_basket_count,
    (event_pos.event_dedup_basket_count - finance.finance_basket_count)
        AS event_basis_basket_variance,
    erp.current_erp_order_count,
    erp.current_erp_order_line_count,
    erp.partner_api_order_count,
    ingest_pos.duplicate_rows_removed,
    finance.prepared_by,
    finance.note,
    (finance.finance_gross_sales_inr IS NULL) AS is_finance_row_missing,
    (
        event_pos.event_dedup_gross_sales_inr IS NULL
        AND ingest_pos.ingest_gross_sales_inr IS NULL
    ) AS is_pos_row_missing,
    (erp.current_erp_order_gross_value_inr IS NULL) AS is_erp_order_evidence_missing
FROM comparison_keys keys
LEFT JOIN finance_weeks finance
    ON finance.period_start = keys.period_start
   AND finance.channel = keys.channel
LEFT JOIN pos_event_comparison event_pos
    ON event_pos.period_start = keys.period_start
   AND event_pos.channel = keys.channel
LEFT JOIN pos_ingest_comparison ingest_pos
    ON ingest_pos.period_start = keys.period_start
   AND ingest_pos.channel = keys.channel
LEFT JOIN erp_orders_by_week erp
    ON erp.period_start = keys.period_start
   AND erp.channel = keys.channel
ORDER BY finance_week_label, channel
