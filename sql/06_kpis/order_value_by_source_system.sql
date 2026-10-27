SELECT
    source_system,
    count(*) AS current_order_count,
    sum(order_value_gross) AS current_order_gross_value_inr,
    sum(discount_amount) AS current_order_discount_inr,
    sum(tax_amount) AS current_order_tax_inr,
    count(*) FILTER (WHERE has_known_partner_freight_adjustment)
        AS orders_with_known_valuation_caveat,
    sum(order_value_gross) FILTER (WHERE has_known_partner_freight_adjustment)
        AS gross_value_with_known_valuation_caveat_inr,
    count(*) FILTER (WHERE is_ambiguous_cdc_version_key)
        AS ambiguous_current_order_count
FROM fact_sales_order_headers
WHERE is_latest_version
  AND NOT is_deleted_current_order
GROUP BY source_system
ORDER BY source_system
