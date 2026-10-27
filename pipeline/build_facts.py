#!/usr/bin/env python3
"""Build Phase 4 curated facts with normalized fields and raw-row lineage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE_ROOTS = [
    PROJECT_ROOT / "data",
    PROJECT_ROOT.parent / "AIDE_Assignment_Pack_docs_and_generator_v1" / "data",
]
DIMENSION_NAMES = [
    "dim_date",
    "dim_outlet",
    "dim_product",
    "dim_warehouse",
    "dim_channel_history",
    "ref_uom_conversion",
]


def find_data_root(explicit_root: str | None) -> Path:
    if explicit_root:
        root = Path(explicit_root).resolve()
        if root.name == "raw" and (root.parent / "reference").exists():
            return root.parent
        if root.exists():
            return root
        raise FileNotFoundError(f"Given data root does not exist: {root}")

    for candidate in DEFAULT_CANDIDATE_ROOTS:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Could not find the assignment data directory. Set --root to the folder containing raw/ and reference/."
    )


def require_dimensions(dimensions_root: Path) -> None:
    missing = [
        dimensions_root / f"{name}.parquet"
        for name in DIMENSION_NAMES
        if not (dimensions_root / f"{name}.parquet").is_file()
    ]
    if missing:
        missing_list = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(
            "Phase 3 dimensions are missing. Run pipeline/build_dimensions.py first:\n"
            f"{missing_list}"
        )


def parquet_files(data_root: Path, relative_directory: str) -> list[Path]:
    directory = data_root / "raw" / relative_directory
    if not directory.is_dir():
        raise FileNotFoundError(f"Required raw feed directory does not exist: {directory}")
    files = sorted(directory.rglob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files found under required raw feed directory: {directory}")
    return files


def register_parquet_source(
    connection: duckdb.DuckDBPyConnection,
    view_name: str,
    files: list[Path],
) -> None:
    relation = connection.read_parquet(
        [str(path) for path in files],
        union_by_name=True,
        hive_partitioning=True,
        filename=True,
        file_row_number=True,
    )
    connection.register(view_name, relation)


def readable_telemetry_files(data_root: Path) -> tuple[list[Path], list[dict[str, str]]]:
    files = parquet_files(data_root, "reefer_telemetry")
    readable: list[Path] = []
    excluded: list[dict[str, str]] = []
    for path in files:
        try:
            pq.ParquetFile(path)
        except Exception as exc:
            excluded.append(
                {
                    "file": str(path),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        readable.append(path)
    if not readable:
        raise ValueError("No readable Parquet files remain in the reefer telemetry feed")
    return readable, excluded


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def write_query(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    connection.execute(
        f"COPY ({query}) TO {sql_literal(str(output_path))} "
        "(FORMAT PARQUET, COMPRESSION ZSTD)"
    )


def fact_queries(dimensions_root: Path) -> dict[str, str]:
    dim_date = sql_literal(str(dimensions_root / "dim_date.parquet"))
    dim_outlet = sql_literal(str(dimensions_root / "dim_outlet.parquet"))
    dim_product = sql_literal(str(dimensions_root / "dim_product.parquet"))
    dim_warehouse = sql_literal(str(dimensions_root / "dim_warehouse.parquet"))
    dim_channel = sql_literal(str(dimensions_root / "dim_channel_history.parquet"))
    ref_uom = sql_literal(str(dimensions_root / "ref_uom_conversion.parquet"))

    return {
        "fact_pos_transactions": f"""
            WITH normalized AS (
                SELECT
                    txn_id,
                    txn_line_no,
                    basket_id,
                    outlet_code,
                    channel AS captured_channel,
                    sku_code,
                    try_cast(event_ts AS TIMESTAMPTZ) AS sale_timestamp_utc,
                    coalesce(qty, quantity_units)::BIGINT AS quantity,
                    upper(nullif(trim(uom), '')) AS raw_uom,
                    unit_price,
                    discount_amount,
                    tax_amount,
                    payment_mode,
                    till_id,
                    cashier_id,
                    promo_code,
                    loyalty_id,
                    source_file AS partner_source_file,
                    ingest_date AS source_partition_date,
                    filename AS source_path,
                    file_row_number AS source_row_number
                FROM raw_pos
            ),
            duplicate_stats AS (
                SELECT
                    *,
                    count(*) OVER (
                        PARTITION BY txn_id, txn_line_no, basket_id, outlet_code,
                            captured_channel, sku_code, sale_timestamp_utc, quantity,
                            raw_uom, unit_price, discount_amount, tax_amount,
                            payment_mode, till_id, cashier_id, promo_code, loyalty_id,
                            partner_source_file, source_partition_date
                    ) AS exact_duplicate_count,
                    count(DISTINCT hash(
                        basket_id, outlet_code, captured_channel, sku_code,
                        sale_timestamp_utc, quantity, raw_uom, unit_price,
                        discount_amount, tax_amount, payment_mode, till_id,
                        cashier_id, promo_code, loyalty_id, partner_source_file,
                        source_partition_date
                    )) OVER (PARTITION BY txn_id, txn_line_no) AS key_variant_count,
                    row_number() OVER (
                        PARTITION BY txn_id, txn_line_no, basket_id, outlet_code,
                            captured_channel, sku_code, sale_timestamp_utc, quantity,
                            raw_uom, unit_price, discount_amount, tax_amount,
                            payment_mode, till_id, cashier_id, promo_code, loyalty_id,
                            partner_source_file, source_partition_date
                        ORDER BY source_path, source_row_number
                    ) AS duplicate_rank
                FROM normalized
            ),
            deduplicated AS (
                SELECT *
                FROM duplicate_stats
                WHERE duplicate_rank = 1
            ),
            enriched AS (
                SELECT
                    p.*,
                    timezone('Asia/Kolkata', p.sale_timestamp_utc) AS sale_timestamp_local,
                    timezone('Asia/Kolkata', p.sale_timestamp_utc)::DATE AS sale_date,
                    CASE
                        WHEN p.raw_uom = coalesce(u.base_uom, 'EA') THEN p.quantity
                        WHEN p.raw_uom = coalesce(u.case_uom, 'CS')
                            AND u.eaches_per_case IS NOT NULL
                            THEN p.quantity * u.eaches_per_case
                        ELSE NULL
                    END::BIGINT AS quantity_eaches,
                    u.eaches_per_case,
                    (u.sku_code IS NOT NULL) AS uom_conversion_available,
                    (p.raw_uom IS NULL) AS is_uom_missing,
                    (p.sale_timestamp_utc IS NOT NULL) AS is_timestamp_valid,
                    (p.key_variant_count > 1) AS is_ambiguous_line_key,
                    (p.exact_duplicate_count > 1) AS has_exact_duplicates,
                    p.exact_duplicate_count - 1 AS duplicate_rows_removed
                FROM deduplicated p
                LEFT JOIN {ref_uom} u USING (sku_code)
            )
            SELECT
                e.txn_id,
                e.txn_line_no,
                e.basket_id,
                e.outlet_code,
                o.dimension_key AS outlet_dimension_key,
                e.sku_code,
                product.dimension_key AS product_dimension_key,
                e.captured_channel,
                channel_history.new_channel AS channel_as_of_sale,
                channel_history.channel_history_key,
                (e.captured_channel IS DISTINCT FROM channel_history.new_channel)
                    AS is_captured_channel_mismatch,
                e.sale_timestamp_utc,
                e.sale_timestamp_local,
                e.sale_date,
                date_dim.date_key,
                e.quantity,
                e.raw_uom,
                e.quantity_eaches,
                e.eaches_per_case,
                e.uom_conversion_available,
                e.is_uom_missing,
                e.unit_price,
                e.quantity * e.unit_price AS extended_price_before_discount,
                e.discount_amount,
                e.tax_amount,
                (e.quantity * e.unit_price) - e.discount_amount
                    AS line_amount_after_discount_before_tax,
                e.payment_mode,
                e.till_id,
                e.cashier_id,
                e.promo_code,
                e.loyalty_id,
                e.partner_source_file,
                e.source_partition_date,
                e.source_path,
                e.source_row_number,
                e.is_timestamp_valid,
                e.is_ambiguous_line_key,
                e.has_exact_duplicates,
                e.duplicate_rows_removed
            FROM enriched e
            LEFT JOIN {dim_date} date_dim
                ON date_dim.calendar_date = e.sale_date
            LEFT JOIN {dim_outlet} o
                ON o.outlet_code = e.outlet_code
                AND e.sale_timestamp_utc >= o.effective_start
                AND (e.sale_timestamp_utc < o.effective_end OR o.effective_end IS NULL)
            LEFT JOIN {dim_product} product
                ON product.sku_code = e.sku_code
                AND e.sale_timestamp_utc >= product.effective_start
                AND (e.sale_timestamp_utc < product.effective_end OR product.effective_end IS NULL)
            LEFT JOIN {dim_channel} channel_history
                ON channel_history.outlet_code = e.outlet_code
                AND e.sale_timestamp_utc >= channel_history.effective_start
                AND (
                    e.sale_timestamp_utc < channel_history.effective_end
                    OR channel_history.effective_end IS NULL
                )
        """,
        "fact_sales_order_headers": f"""
            WITH normalized AS (
                SELECT
                    order_number,
                    upper(__op) AS cdc_operation,
                    try_cast(__op_ts AS TIMESTAMPTZ) AS operation_timestamp_utc,
                    __seq::BIGINT AS source_sequence,
                    outlet_code,
                    warehouse_code,
                    route_code,
                    try_cast(order_date AS DATE) AS order_date,
                    try_cast(requested_delivery_date AS DATE) AS requested_delivery_date,
                    order_status,
                    line_count,
                    order_value_gross,
                    discount_amount,
                    tax_amount,
                    source_system,
                    extract_date AS source_partition_date,
                    filename AS source_path,
                    file_row_number AS source_row_number
                FROM raw_orders
            ),
            versioned AS (
                SELECT
                    *,
                    row_number() OVER (
                        PARTITION BY order_number, cdc_operation, operation_timestamp_utc,
                            source_sequence, outlet_code, warehouse_code, route_code,
                            order_date, requested_delivery_date, order_status, line_count,
                            order_value_gross, discount_amount, tax_amount, source_system
                        ORDER BY source_path, source_row_number
                    ) AS exact_version_rank,
                    count(*) OVER (
                        PARTITION BY order_number, cdc_operation, operation_timestamp_utc,
                            source_sequence, outlet_code, warehouse_code, route_code,
                            order_date, requested_delivery_date, order_status, line_count,
                            order_value_gross, discount_amount, tax_amount, source_system
                    ) AS exact_payload_count,
                    count(DISTINCT hash(
                        cdc_operation, outlet_code, warehouse_code, route_code, order_date,
                        requested_delivery_date, order_status, line_count, order_value_gross,
                        discount_amount, tax_amount, source_system
                    )) OVER (
                        PARTITION BY order_number, operation_timestamp_utc, source_sequence
                    ) AS version_variant_count
                FROM normalized
            ),
            deduplicated AS (
                SELECT *
                FROM versioned
                WHERE exact_version_rank = 1
            ),
            ordered AS (
                SELECT
                    *,
                    dense_rank() OVER (
                        PARTITION BY order_number ORDER BY source_sequence
                    ) AS version_number,
                    source_sequence = max(source_sequence) OVER (
                        PARTITION BY order_number
                    ) AS is_latest_version,
                    lag(operation_timestamp_utc) OVER (
                        PARTITION BY order_number
                        ORDER BY source_sequence, source_path, source_row_number
                    ) AS previous_operation_timestamp_utc
                FROM deduplicated
            )
            SELECT
                o.order_number,
                o.version_number,
                o.cdc_operation,
                o.operation_timestamp_utc,
                o.source_sequence,
                o.is_latest_version,
                (o.cdc_operation = 'D') AS is_deleted_event,
                (o.is_latest_version AND o.cdc_operation = 'D') AS is_deleted_current_order,
                (o.version_variant_count > 1) AS is_ambiguous_cdc_version_key,
                (
                    o.previous_operation_timestamp_utc IS NOT NULL
                    AND o.operation_timestamp_utc < o.previous_operation_timestamp_utc
                ) AS is_operation_timestamp_out_of_order,
                o.outlet_code,
                outlet.dimension_key AS outlet_dimension_key,
                o.warehouse_code,
                warehouse.warehouse_code IS NOT NULL AS warehouse_reference_found,
                o.route_code,
                o.order_date,
                order_date_dim.date_key AS order_date_key,
                o.requested_delivery_date,
                delivery_date_dim.date_key AS requested_delivery_date_key,
                o.order_status,
                o.line_count,
                o.order_value_gross,
                o.discount_amount,
                o.tax_amount,
                o.source_system,
                (o.source_system = 'PARTNER_API') AS has_known_partner_freight_adjustment,
                o.source_partition_date,
                o.source_path,
                o.source_row_number,
                o.exact_payload_count - 1 AS duplicate_rows_removed
            FROM ordered o
            LEFT JOIN {dim_outlet} outlet
                ON outlet.outlet_code = o.outlet_code
                AND o.operation_timestamp_utc >= outlet.effective_start
                AND (
                    o.operation_timestamp_utc < outlet.effective_end
                    OR outlet.effective_end IS NULL
                )
            LEFT JOIN {dim_warehouse} warehouse
                ON warehouse.warehouse_code = o.warehouse_code
            LEFT JOIN {dim_date} order_date_dim
                ON order_date_dim.calendar_date = o.order_date
            LEFT JOIN {dim_date} delivery_date_dim
                ON delivery_date_dim.calendar_date = o.requested_delivery_date
        """,
        "fact_wms_scan_events": f"""
            WITH normalized AS (
                SELECT
                    scan_id,
                    upper(event_type) AS event_type,
                    order_number,
                    warehouse_code,
                    sku_code,
                    batch_id,
                    qty_cases::BIGINT AS quantity_cases,
                    pallet_id,
                    dock_door,
                    operator_id,
                    handheld_device,
                    try_cast(event_ts AS TIMESTAMP) AS event_timestamp_local,
                    dt AS source_partition_date,
                    filename AS source_path,
                    file_row_number AS source_row_number
                FROM raw_wms
            ),
            duplicate_stats AS (
                SELECT
                    *,
                    count(*) OVER (
                        PARTITION BY scan_id, event_type, order_number, warehouse_code,
                            sku_code, batch_id, quantity_cases, pallet_id, dock_door,
                            operator_id, handheld_device, event_timestamp_local,
                            source_partition_date
                    ) AS exact_duplicate_count,
                    count(DISTINCT hash(
                        event_type, order_number, warehouse_code, sku_code, batch_id,
                        quantity_cases, pallet_id, dock_door, operator_id,
                        handheld_device, event_timestamp_local, source_partition_date
                    )) OVER (PARTITION BY scan_id) AS key_variant_count,
                    row_number() OVER (
                        PARTITION BY scan_id, event_type, order_number, warehouse_code,
                            sku_code, batch_id, quantity_cases, pallet_id, dock_door,
                            operator_id, handheld_device, event_timestamp_local,
                            source_partition_date
                        ORDER BY source_path, source_row_number
                    ) AS duplicate_rank
                FROM normalized
            ),
            deduplicated AS (
                SELECT *
                FROM duplicate_stats
                WHERE duplicate_rank = 1
            ),
            enriched AS (
                SELECT
                    s.*,
                    timezone(coalesce(w.timezone, 'UTC'), s.event_timestamp_local)
                        AS event_timestamp_utc,
                    s.event_timestamp_local::DATE AS event_date,
                    w.timezone AS warehouse_timezone,
                    (s.event_timestamp_local IS NOT NULL) AS is_timestamp_valid,
                    (s.key_variant_count > 1) AS is_ambiguous_scan_id,
                    (s.exact_duplicate_count > 1) AS has_exact_duplicates,
                    s.exact_duplicate_count - 1 AS duplicate_rows_removed
                FROM deduplicated s
                LEFT JOIN {dim_warehouse} w USING (warehouse_code)
            )
            SELECT
                e.scan_id,
                e.event_type,
                e.order_number,
                e.warehouse_code,
                w.warehouse_name,
                e.sku_code,
                product.dimension_key AS product_dimension_key,
                e.batch_id,
                e.quantity_cases,
                e.pallet_id,
                e.dock_door,
                e.operator_id,
                e.handheld_device,
                e.event_timestamp_local,
                e.event_timestamp_utc,
                e.event_date,
                date_dim.date_key,
                e.warehouse_timezone,
                e.source_partition_date,
                e.source_path,
                e.source_row_number,
                e.is_timestamp_valid,
                e.is_ambiguous_scan_id,
                e.has_exact_duplicates,
                e.duplicate_rows_removed
            FROM enriched e
            LEFT JOIN {dim_warehouse} w USING (warehouse_code)
            LEFT JOIN {dim_date} date_dim
                ON date_dim.calendar_date = e.event_date
            LEFT JOIN {dim_product} product
                ON product.sku_code = e.sku_code
                AND e.event_timestamp_utc >= product.effective_start
                AND (
                    e.event_timestamp_utc < product.effective_end
                    OR product.effective_end IS NULL
                )
        """,
        "fact_reefer_telemetry": f"""
            WITH normalized AS (
                SELECT
                    device_id,
                    telemetry_vendor,
                    firmware_version,
                    vehicle_registration,
                    route_code,
                    warehouse_code,
                    gateway_id,
                    try_cast(reading_ts AS TIMESTAMPTZ) AS reading_timestamp_utc_raw,
                    temp_value,
                    upper(nullif(trim(temp_unit), '')) AS reported_temp_unit,
                    humidity_pct,
                    door_open_flag,
                    gps_lat,
                    gps_lon,
                    battery_pct,
                    dt AS source_partition_date,
                    filename AS source_path,
                    file_row_number AS source_row_number
                FROM raw_telemetry
            ),
            units_and_time AS (
                SELECT
                    *,
                    coalesce(
                        reported_temp_unit,
                        CASE
                            WHEN upper(telemetry_vendor) = 'COLDEYE' THEN 'F'
                            WHEN upper(telemetry_vendor) = 'THERMLOG' THEN 'C'
                            ELSE NULL
                        END
                    ) AS normalized_temp_unit,
                    (reported_temp_unit IS NULL) AS is_temp_unit_inferred,
                    CASE WHEN firmware_version = '2.1.4' THEN 7 ELSE 0 END
                        AS clock_correction_hours,
                    CASE
                        WHEN firmware_version = '2.1.4'
                            THEN reading_timestamp_utc_raw - INTERVAL '7 hours'
                        ELSE reading_timestamp_utc_raw
                    END AS reading_timestamp_utc
                FROM normalized
            ),
            duplicate_stats AS (
                SELECT
                    *,
                    count(*) OVER (
                        PARTITION BY device_id, telemetry_vendor, firmware_version,
                            vehicle_registration, route_code, warehouse_code, gateway_id,
                            reading_timestamp_utc_raw, temp_value, reported_temp_unit,
                            humidity_pct, door_open_flag, gps_lat, gps_lon, battery_pct,
                            source_partition_date
                    ) AS exact_duplicate_count,
                    count(DISTINCT hash(
                        telemetry_vendor, firmware_version, vehicle_registration,
                        route_code, warehouse_code, gateway_id, reading_timestamp_utc_raw,
                        temp_value, reported_temp_unit, humidity_pct, door_open_flag,
                        gps_lat, gps_lon, battery_pct, source_partition_date
                    )) OVER (
                        PARTITION BY device_id, reading_timestamp_utc_raw
                    ) AS key_variant_count,
                    row_number() OVER (
                        PARTITION BY device_id, telemetry_vendor, firmware_version,
                            vehicle_registration, route_code, warehouse_code, gateway_id,
                            reading_timestamp_utc_raw, temp_value, reported_temp_unit,
                            humidity_pct, door_open_flag, gps_lat, gps_lon, battery_pct,
                            source_partition_date
                        ORDER BY source_path, source_row_number
                    ) AS duplicate_rank
                FROM units_and_time
            ),
            deduplicated AS (
                SELECT *
                FROM duplicate_stats
                WHERE duplicate_rank = 1
            ),
            enriched AS (
                SELECT
                    t.*,
                    CASE
                        WHEN normalized_temp_unit = 'C' THEN temp_value
                        WHEN normalized_temp_unit = 'F' THEN (temp_value - 32.0) * 5.0 / 9.0
                        ELSE NULL
                    END AS temperature_celsius,
                    timezone(coalesce(w.timezone, 'UTC'), reading_timestamp_utc)
                        AS reading_timestamp_local,
                    (reading_timestamp_utc IS NOT NULL) AS is_timestamp_valid,
                    (temp_value IS NULL) AS is_temperature_missing,
                    (
                        (
                            normalized_temp_unit IS NULL
                            OR normalized_temp_unit NOT IN ('C', 'F')
                        )
                        AND temp_value IS NOT NULL
                    ) AS is_temperature_unit_unresolved,
                    (key_variant_count > 1) AS is_ambiguous_reading_key,
                    (exact_duplicate_count > 1) AS has_exact_duplicates,
                    exact_duplicate_count - 1 AS duplicate_rows_removed,
                    w.timezone AS warehouse_timezone
                FROM deduplicated t
                LEFT JOIN {dim_warehouse} w USING (warehouse_code)
            )
            SELECT
                e.device_id,
                e.telemetry_vendor,
                e.firmware_version,
                e.vehicle_registration,
                e.route_code,
                e.warehouse_code,
                w.warehouse_name,
                e.gateway_id,
                e.reading_timestamp_utc_raw,
                e.reading_timestamp_utc,
                e.reading_timestamp_local,
                e.reading_timestamp_local::DATE AS reading_date,
                date_dim.date_key,
                e.temp_value AS temperature_raw,
                e.reported_temp_unit,
                e.normalized_temp_unit,
                e.temperature_celsius,
                e.is_temp_unit_inferred,
                e.clock_correction_hours,
                (e.temperature_celsius > 8.0) AS is_above_chilled_upper_bound,
                e.humidity_pct,
                e.door_open_flag,
                e.gps_lat,
                e.gps_lon,
                e.battery_pct,
                e.warehouse_timezone,
                e.source_partition_date,
                e.source_path,
                e.source_row_number,
                e.is_timestamp_valid,
                e.is_temperature_missing,
                e.is_temperature_unit_unresolved,
                e.is_ambiguous_reading_key,
                e.has_exact_duplicates,
                e.duplicate_rows_removed
            FROM enriched e
            LEFT JOIN {dim_warehouse} w USING (warehouse_code)
            LEFT JOIN {dim_date} date_dim
                ON date_dim.calendar_date = e.reading_timestamp_local::DATE
        """,
    }


def summarize_fact(
    connection: duckdb.DuckDBPyConnection,
    fact_path: Path,
    fact_name: str,
) -> dict[str, Any]:
    relation = connection.read_parquet(str(fact_path))
    result: dict[str, Any] = {
        "rows": relation.count("*").fetchall()[0][0],
        "columns": list(relation.columns),
        "path": str(fact_path),
    }
    if "duplicate_rows_removed" in result["columns"]:
        result["duplicate_rows_removed"] = connection.execute(
            f"SELECT coalesce(sum(duplicate_rows_removed), 0) FROM read_parquet({sql_literal(str(fact_path))})"
        ).fetchone()[0]
    if "is_ambiguous_line_key" in result["columns"]:
        result["ambiguous_rows"] = connection.execute(
            f"SELECT count(*) FROM read_parquet({sql_literal(str(fact_path))}) "
            "WHERE is_ambiguous_line_key"
        ).fetchone()[0]
    if "is_ambiguous_scan_id" in result["columns"]:
        result["ambiguous_rows"] = connection.execute(
            f"SELECT count(*) FROM read_parquet({sql_literal(str(fact_path))}) "
            "WHERE is_ambiguous_scan_id"
        ).fetchone()[0]
    if "is_ambiguous_reading_key" in result["columns"]:
        result["ambiguous_rows"] = connection.execute(
            f"SELECT count(*) FROM read_parquet({sql_literal(str(fact_path))}) "
            "WHERE is_ambiguous_reading_key"
        ).fetchone()[0]
        result["corrected_clock_rows"] = connection.execute(
            f"SELECT count(*) FROM read_parquet({sql_literal(str(fact_path))}) "
            "WHERE clock_correction_hours > 0"
        ).fetchone()[0]
        result["missing_temperature_rows"] = connection.execute(
            f"SELECT count(*) FROM read_parquet({sql_literal(str(fact_path))}) "
            "WHERE is_temperature_missing"
        ).fetchone()[0]
        result["inferred_unit_rows"] = connection.execute(
            f"SELECT count(*) FROM read_parquet({sql_literal(str(fact_path))}) "
            "WHERE is_temp_unit_inferred"
        ).fetchone()[0]
    if "date_key" in result["columns"]:
        result["missing_date_key_rows"] = connection.execute(
            f"SELECT count(*) FROM read_parquet({sql_literal(str(fact_path))}) "
            "WHERE date_key IS NULL"
        ).fetchone()[0]
    for column in result["columns"]:
        if column.endswith("_dimension_key") or column.endswith("_history_key"):
            result[f"missing_{column}_rows"] = connection.execute(
                f"SELECT count(*) FROM read_parquet({sql_literal(str(fact_path))}) "
                f"WHERE {column} IS NULL"
            ).fetchone()[0]
    if "is_captured_channel_mismatch" in result["columns"]:
        result["captured_channel_mismatch_rows"] = connection.execute(
            f"SELECT count(*) FROM read_parquet({sql_literal(str(fact_path))}) "
            "WHERE is_captured_channel_mismatch"
        ).fetchone()[0]
    if "is_deleted_current_order" in result["columns"]:
        result["current_deleted_orders"] = connection.execute(
            f"SELECT count(*) FROM read_parquet({sql_literal(str(fact_path))}) "
            "WHERE is_deleted_current_order"
        ).fetchone()[0]
        result["out_of_order_operation_timestamps"] = connection.execute(
            f"SELECT count(*) FROM read_parquet({sql_literal(str(fact_path))}) "
            "WHERE is_operation_timestamp_out_of_order"
        ).fetchone()[0]
        result["ambiguous_cdc_version_rows"] = connection.execute(
            f"SELECT count(*) FROM read_parquet({sql_literal(str(fact_path))}) "
            "WHERE is_ambiguous_cdc_version_key"
        ).fetchone()[0]
    return result


def build_facts(
    data_root: Path,
    dimensions_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    require_dimensions(dimensions_root)
    output_root.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect()
    try:
        source_files = {
            "raw_pos": parquet_files(data_root, "pos_transactions"),
            "raw_orders": parquet_files(data_root, "erp_cdc/sales_order_header"),
            "raw_wms": parquet_files(data_root, "wms_scan_events"),
        }
        telemetry_files, excluded_telemetry_files = readable_telemetry_files(data_root)
        source_files["raw_telemetry"] = telemetry_files
        for view_name, files in source_files.items():
            register_parquet_source(connection, view_name, files)

        query_map = fact_queries(dimensions_root)
        tables: dict[str, Any] = {}
        for table_name, query in query_map.items():
            output_path = output_root / f"{table_name}.parquet"
            write_query(connection, query, output_path)
            tables[table_name] = summarize_fact(connection, output_path, table_name)

        report = {
            "source_data_root": str(data_root),
            "dimensions_root": str(dimensions_root),
            "output_directory": str(output_root),
            "source_files": {name: len(files) for name, files in source_files.items()},
            "tables": tables,
            "excluded_telemetry_files": excluded_telemetry_files,
            "notes": [
                "POS and telemetry facts collapse exact duplicate payloads while retaining duplicate counts and source row lineage.",
                "Conflicting rows that share a business identifier are retained and flagged as ambiguous.",
                "Order-header facts preserve CDC event versions ordered by source sequence, including delete tombstones; consumers should filter is_deleted_current_order for current-order analysis.",
                "Order-header operation timestamps can move backwards relative to source sequence; these records are retained and flagged.",
                "Telemetry temperature is normalized to Celsius; missing units are inferred only from the documented vendor convention.",
                "Telemetry firmware 2.1.4 timestamps are corrected by seven hours based on the supplied generator defect description.",
                "No carrier ID or trip ID is present in telemetry; neither is fabricated in the fact.",
                "Unreadable telemetry files are excluded from the fact and listed explicitly; their manifest shortfall remains a known completeness defect.",
            ],
        }
        summary_path = output_root / "build_summary.json"
        summary_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 4 curated fact tables.")
    parser.add_argument("--root", default=None, help="Data root containing raw/ and reference/ (or raw/).")
    parser.add_argument(
        "--dimensions",
        default=str(PROJECT_ROOT / "curated" / "dimensions"),
        help="Directory containing Phase 3 dimension Parquet files.",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "curated" / "facts"),
        help="Output directory for curated fact Parquet files.",
    )
    args = parser.parse_args()

    report = build_facts(
        find_data_root(args.root),
        Path(args.dimensions).resolve(),
        Path(args.output).resolve(),
    )
    print(f"Built {len(report['tables'])} fact tables under {report['output_directory']}")
    for table_name, summary in report["tables"].items():
        print(f"- {table_name}: {summary['rows']:,} rows")
        if summary.get("duplicate_rows_removed"):
            print(f"  exact duplicate rows removed: {summary['duplicate_rows_removed']:,}")
        if summary.get("ambiguous_rows"):
            print(f"  ambiguous rows retained: {summary['ambiguous_rows']:,}")
    if report["excluded_telemetry_files"]:
        print(f"- unreadable telemetry files explicitly excluded: {len(report['excluded_telemetry_files'])}")
    print(f"- build summary: {Path(report['output_directory']) / 'build_summary.json'}")


if __name__ == "__main__":
    main()
