SELECT 'dim_warehouse' AS dimension_name,
       CAST(warehouse_code AS VARCHAR) AS business_key,
       CAST(warehouse_name AS VARCHAR) AS attribute_1,
       CAST(city AS VARCHAR) AS attribute_2,
       CAST(region_name AS VARCHAR) AS attribute_3,
       'warehouse_reference_missing' AS issue_type
FROM dim_warehouse
WHERE warehouse_code IS NULL OR warehouse_name IS NULL OR city IS NULL

UNION ALL

SELECT 'dim_outlet' AS dimension_name,
       CAST(outlet_code AS VARCHAR) AS business_key,
       CAST(outlet_name AS VARCHAR) AS attribute_1,
       CAST(city AS VARCHAR) AS attribute_2,
       CAST(channel AS VARCHAR) AS attribute_3,
       'outlet_reference_missing' AS issue_type
FROM dim_outlet
WHERE outlet_code IS NULL OR outlet_name IS NULL OR city IS NULL

UNION ALL

SELECT 'dim_carrier' AS dimension_name,
       CAST(carrier_id AS VARCHAR) AS business_key,
       CAST(carrier_name AS VARCHAR) AS attribute_1,
       CAST(mode AS VARCHAR) AS attribute_2,
       CAST(sla_hours AS VARCHAR) AS attribute_3,
       'carrier_reference_missing' AS issue_type
FROM dim_carrier
WHERE carrier_id IS NULL OR carrier_name IS NULL OR mode IS NULL

UNION ALL

SELECT 'dim_product' AS dimension_name,
       CAST(sku_code AS VARCHAR) AS business_key,
       CAST(product_name AS VARCHAR) AS attribute_1,
       CAST(category AS VARCHAR) AS attribute_2,
       CAST(brand AS VARCHAR) AS attribute_3,
       'product_reference_missing' AS issue_type
FROM dim_product
WHERE sku_code IS NULL OR product_name IS NULL OR category IS NULL
ORDER BY dimension_name, business_key
