SELECT
    date_dim.fiscal_year,
    date_dim.fiscal_quarter,
    date_dim.fiscal_period,
    date_dim.month_start,
    sales.sales_channel,
    sum(sales.quantity_eaches) AS units_sold_eaches,
    count(*) AS valid_transaction_line_count,
    count(*) FILTER (WHERE sales.quantity_eaches IS NULL)
        AS lines_without_eaches_conversion,
    sum(sales.quantity) FILTER (WHERE sales.quantity_eaches IS NULL)
        AS raw_quantity_without_eaches_conversion,
    count(*) FILTER (WHERE sales.is_product_dimension_unresolved)
        AS unresolved_product_line_count
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
