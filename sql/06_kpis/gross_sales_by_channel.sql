SELECT
    date_dim.fiscal_year,
    date_dim.fiscal_quarter,
    date_dim.fiscal_period,
    date_dim.month_start,
    sales.sales_channel,
    count(*) AS transaction_line_count,
    sum(sales.gross_sales_ex_tax_inr) AS gross_sales_ex_tax_inr,
    sum(sales.net_sales_ex_tax_inr) AS net_sales_ex_tax_inr,
    sum(sales.tax_amount) AS tax_amount_inr,
    sum(sales.quantity_eaches) AS units_sold_eaches,
    count(*) FILTER (WHERE sales.is_outlet_dimension_unresolved)
        AS unresolved_outlet_line_count,
    count(*) FILTER (WHERE sales.is_product_dimension_unresolved)
        AS unresolved_product_line_count,
    count(*) FILTER (WHERE sales.is_captured_channel_mismatch)
        AS captured_channel_mismatch_line_count
FROM fact_reconciled_sales sales
JOIN dim_date date_dim
    ON date_dim.calendar_date = sales.sale_date
WHERE sales.is_timestamp_valid
  AND NOT sales.is_ambiguous_line_key
GROUP BY
    date_dim.fiscal_year,
    date_dim.fiscal_quarter,
    date_dim.fiscal_period,
    date_dim.month_start,
    sales.sales_channel
ORDER BY date_dim.month_start, sales.sales_channel
