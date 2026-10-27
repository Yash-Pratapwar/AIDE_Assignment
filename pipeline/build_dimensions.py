#!/usr/bin/env python3
"""Build the canonical dimensions and reference tables for Phase 3."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE_ROOTS = [
    PROJECT_ROOT / "data",
    PROJECT_ROOT.parent / "AIDE_Assignment_Pack_docs_and_generator_v1" / "data",
]
MASTER_COLUMNS = {
    "outlet_master": [
        "outlet_code", "__op", "__op_ts", "__seq", "outlet_name", "channel",
        "outlet_format", "city", "route_code", "warehouse_code", "credit_limit",
        "credit_terms_days", "gst_number", "status",
    ],
    "product_master": [
        "sku_code", "__op", "__op_ts", "__seq", "product_name", "category",
        "brand", "case_pack", "mrp", "list_price", "gst_rate_pct",
        "shelf_life_days", "is_chilled", "status",
    ],
}


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


def read_reference_csv(data_root: Path, name: str) -> pd.DataFrame:
    path = data_root / "reference" / name
    if not path.is_file():
        raise FileNotFoundError(f"Required reference file does not exist: {path}")
    return pd.read_csv(path)


def read_cdc_table(data_root: Path, table_name: str) -> pd.DataFrame:
    table_root = data_root / "raw" / "erp_cdc" / table_name
    if not table_root.is_dir():
        raise FileNotFoundError(f"Required ERP CDC table directory does not exist: {table_root}")

    frames: list[pd.DataFrame] = []
    for file_path in sorted(table_root.rglob("*.parquet")):
        try:
            frame = pq.read_table(file_path, columns=MASTER_COLUMNS[table_name]).to_pandas()
        except Exception as exc:
            raise RuntimeError(f"Could not read ERP CDC file {file_path}: {exc}") from exc
        partition_match = re.search(r"extract_date=(\d{4}-\d{2}-\d{2})", str(file_path.parent))
        frame["source_extract_date"] = partition_match.group(1) if partition_match else None
        frame["source_file"] = str(file_path.relative_to(data_root))
        frames.append(frame)

    if not frames:
        raise ValueError(f"No parquet files found for ERP CDC table {table_name} under {table_root}")
    return pd.concat(frames, ignore_index=True)


def build_scd2(
    changes: pd.DataFrame,
    key_column: str,
    attribute_columns: list[str],
) -> pd.DataFrame:
    required = {key_column, "__op", "__op_ts", "__seq", *attribute_columns}
    missing_columns = required - set(changes.columns)
    if missing_columns:
        raise ValueError(f"CDC input for {key_column} is missing columns: {sorted(missing_columns)}")
    if changes[key_column].isna().any():
        raise ValueError(f"CDC input for {key_column} contains null keys")

    history = changes.copy()
    history["__op_ts"] = pd.to_datetime(history["__op_ts"], utc=True, errors="raise")
    history["__seq"] = pd.to_numeric(history["__seq"], errors="raise").astype("int64")
    history["__op"] = history["__op"].astype(str).str.upper()
    invalid_ops = sorted(set(history["__op"]) - {"I", "U", "D"})
    if invalid_ops:
        raise ValueError(f"CDC input for {key_column} has unsupported operations: {invalid_ops}")

    # Arrival order is not reliable; the source contract's timestamp and sequence define order.
    history = (
        history.sort_values([key_column, "__op_ts", "__seq"], kind="stable")
        .drop_duplicates([key_column, "__op_ts"], keep="last")
        .reset_index(drop=True)
    )
    grouped = history.groupby(key_column, sort=True, dropna=False)
    history["effective_end"] = grouped["__op_ts"].shift(-1)

    active = history.loc[history["__op"].isin(["I", "U"])].copy()
    active = active.rename(columns={"__op_ts": "effective_start", "__seq": "source_seq"})
    active["is_current"] = active["effective_end"].isna()
    active = active.sort_values([key_column, "effective_start"], kind="stable").reset_index(drop=True)
    active.insert(0, "dimension_key", range(1, len(active) + 1))

    output_columns = [
        "dimension_key",
        key_column,
        *attribute_columns,
        "effective_start",
        "effective_end",
        "is_current",
        "source_seq",
        "source_extract_date",
        "source_file",
    ]
    return active[output_columns]


def require_unique_key(frame: pd.DataFrame, column: str, label: str) -> None:
    if frame[column].isna().any():
        raise ValueError(f"{label} contains null values in key column {column}")
    duplicates = frame.loc[frame[column].duplicated(keep=False), column].head(5).tolist()
    if duplicates:
        raise ValueError(f"{label} contains duplicate keys in {column}: {duplicates}")


def build_date_dimension(fiscal_calendar: pd.DataFrame) -> pd.DataFrame:
    dates = fiscal_calendar.copy()
    dates["calendar_date"] = pd.to_datetime(dates["calendar_date"], errors="raise").dt.date
    calendar_ts = pd.to_datetime(dates["calendar_date"])
    dates.insert(0, "date_key", calendar_ts.dt.strftime("%Y%m%d").astype("int32"))
    dates["calendar_year"] = calendar_ts.dt.year.astype("int16")
    dates["calendar_month"] = calendar_ts.dt.month.astype("int8")
    dates["month_name"] = calendar_ts.dt.strftime("%B")
    dates["month_start"] = calendar_ts.dt.to_period("M").dt.start_time.dt.date
    dates["calendar_quarter"] = "Q" + calendar_ts.dt.quarter.astype(str)
    dates["quarter_start"] = calendar_ts.dt.to_period("Q").dt.start_time.dt.date
    dates["fiscal_month_no"] = pd.to_numeric(dates["fiscal_month_no"], errors="raise").astype("int8")
    dates["fiscal_period"] = (
        dates["fiscal_year"].astype(str) + "-P" + dates["fiscal_month_no"].astype(str).str.zfill(2)
    )
    dates["iso_week"] = pd.to_numeric(dates["iso_week"], errors="raise").astype("int8")
    dates["day_of_week_no"] = calendar_ts.dt.day_of_week.add(1).astype("int8")
    dates["is_weekend"] = dates["is_weekend"].astype(bool)
    dates["is_weekday"] = ~dates["is_weekend"]

    columns = [
        "date_key", "calendar_date", "calendar_year", "calendar_month", "month_name",
        "month_start", "calendar_quarter", "quarter_start", "fiscal_year",
        "fiscal_quarter", "fiscal_month_no", "fiscal_period", "iso_week",
        "day_of_week_no", "day_of_week", "is_weekend", "is_weekday",
    ]
    return dates[columns].sort_values("calendar_date").reset_index(drop=True)


def build_channel_history(outlet_dimension: pd.DataFrame) -> pd.DataFrame:
    outlet_dimension = outlet_dimension.sort_values(
        ["outlet_code", "effective_start"], kind="stable"
    )
    channel_changes = outlet_dimension.groupby("outlet_code", sort=False)["channel"].transform(
        lambda values: values.ne(values.shift())
    )
    channel_history = outlet_dimension.loc[channel_changes, [
        "outlet_code", "channel", "effective_start",
        "source_seq", "source_extract_date", "source_file",
    ]].copy()
    channel_history = channel_history.rename(columns={"channel": "new_channel"})
    channel_history["effective_end"] = channel_history.groupby(
        "outlet_code", sort=False
    )["effective_start"].shift(-1)
    final_outlet_versions = outlet_dimension.groupby("outlet_code", sort=False).tail(1)
    final_outlet_end = final_outlet_versions.set_index("outlet_code")["effective_end"]
    channel_history["effective_end"] = channel_history["effective_end"].fillna(
        channel_history["outlet_code"].map(final_outlet_end)
    )
    channel_history["previous_channel"] = outlet_dimension.groupby(
        "outlet_code", sort=False
    )["channel"].shift().loc[channel_changes].to_numpy()
    channel_history["is_current"] = channel_history["effective_end"].isna()
    channel_history.insert(0, "channel_history_key", range(1, len(channel_history) + 1))
    return channel_history.reset_index(drop=True)


def build_dimensions(data_root: Path) -> dict[str, pd.DataFrame]:
    fiscal_calendar = read_reference_csv(data_root, "fiscal_calendar.csv")
    outlet_changes = read_cdc_table(data_root, "outlet_master")
    product_changes = read_cdc_table(data_root, "product_master")

    outlet_attributes = [
        "outlet_name", "channel", "outlet_format", "city", "route_code",
        "warehouse_code", "credit_limit", "credit_terms_days", "gst_number", "status",
    ]
    product_attributes = [
        "product_name", "category", "brand", "case_pack", "mrp", "list_price",
        "gst_rate_pct", "shelf_life_days", "is_chilled", "status",
    ]

    outlet_dimension = build_scd2(outlet_changes, "outlet_code", outlet_attributes)
    product_dimension = build_scd2(product_changes, "sku_code", product_attributes)

    uom = read_reference_csv(data_root, "uom_conversion.csv")
    require_unique_key(uom, "sku_code", "UOM conversion reference")
    product_dimension = product_dimension.merge(
        uom[["sku_code", "eaches_per_case", "base_uom", "case_uom"]],
        on="sku_code",
        how="left",
        validate="many_to_one",
    )
    product_dimension["uom_conversion_available"] = product_dimension["eaches_per_case"].notna()

    warehouse_dimension = read_reference_csv(data_root, "warehouse_master.csv")
    carrier_dimension = read_reference_csv(data_root, "carrier_master.csv")
    require_unique_key(warehouse_dimension, "warehouse_code", "Warehouse reference")
    require_unique_key(carrier_dimension, "carrier_id", "Carrier reference")
    require_unique_key(fiscal_calendar, "calendar_date", "Fiscal calendar")

    return {
        "dim_date": build_date_dimension(fiscal_calendar),
        "dim_outlet": outlet_dimension,
        "dim_product": product_dimension,
        "dim_warehouse": warehouse_dimension,
        "dim_carrier": carrier_dimension,
        "dim_channel_history": build_channel_history(outlet_dimension),
        "ref_uom_conversion": uom,
    }


def write_dimensions(dimensions: dict[str, pd.DataFrame], output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"output_directory": str(output_root), "tables": {}}
    for table_name, frame in dimensions.items():
        output_path = output_root / f"{table_name}.parquet"
        frame.to_parquet(output_path, index=False)
        summary["tables"][table_name] = {
            "rows": len(frame),
            "columns": list(frame.columns),
            "path": str(output_path),
        }

    summary_path = output_root / "build_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase 3 dimensions and reference tables.")
    parser.add_argument("--root", default=None, help="Data root containing raw/ and reference/ (or the raw/ directory).")
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "curated" / "dimensions"),
        help="Output directory for dimension Parquet files.",
    )
    args = parser.parse_args()

    data_root = find_data_root(args.root)
    output_root = Path(args.output).resolve()
    dimensions = build_dimensions(data_root)
    summary = write_dimensions(dimensions, output_root)

    print(f"Built {len(summary['tables'])} dimension tables under {output_root}")
    for table_name, table_summary in summary["tables"].items():
        print(f"- {table_name}: {table_summary['rows']:,} rows")
    print(f"- build summary: {output_root / 'build_summary.json'}")


if __name__ == "__main__":
    main()
