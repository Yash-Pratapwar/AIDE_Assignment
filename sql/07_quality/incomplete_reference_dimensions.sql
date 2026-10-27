SELECT 'dim_warehouse' AS dimension_name,
       warehouse_code,
       warehouse_name,
       city,
       region_name,
       'warehouse_reference_missing' AS issue_type
FROM dim_warehouse
WHERE warehouse_code IS NULL OR warehouse_name IS NULL OR city IS NULL

UNION ALL

SELECT 'dim_outlet' AS dimension_name,
       outlet_code,
       outlet_name,
       city,
       channel,
       'outlet_reference_missing' AS issue_type
FROM dim_outlet
WHERE outlet_code IS NULL OR outlet_name IS NULL OR city IS NULL

UNION ALL

SELECT 'dim_carrier' AS dimension_name,
       carrier_id,
       carrier_name,
       mode,
       sla_hours,
       'carrier_reference_missing' AS issue_type
FROM dim_carrier
WHERE carrier_id IS NULL OR carrier_name IS NULL OR mode IS NULL

UNION ALL

SELECT 'dim_product' AS dimension_name,
       sku_code,
       product_name,
       category,
       brand,
       'product_reference_missing' AS issue_type
FROM dim_product
WHERE sku_code IS NULL OR product_name IS NULL OR category IS NULL
ORDER BY dimension_name, warehouse_code
