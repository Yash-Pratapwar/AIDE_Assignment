#!/usr/bin/env python3
"""Run the Phase 6 SQL KPI library over the curated Phase 3-5 tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOTS = [
    PROJECT_ROOT / "data",
    PROJECT_ROOT.parent / "AIDE_Assignment_Pack_docs_and_generator_v1" / "data",
]
TABLES = {
    "fact_reconciled_sales": ("sales", "fact_reconciled_sales"),
    "fact_sales_order_headers": ("facts", "fact_sales_order_headers"),
    "fact_wms_scan_events": ("facts", "fact_wms_scan_events"),
    "fact_reefer_telemetry": ("facts", "fact_reefer_telemetry"),
    "dim_date": ("dimensions", "dim_date"),
    "dim_channel_history": ("dimensions", "dim_channel_history"),
}
SQL_ROOT = PROJECT_ROOT / "sql" / "06_kpis"


def find_data_root(explicit_root: str | None) -> Path:
    if explicit_root:
        root = Path(explicit_root).resolve()
        if root.name == "raw" and (root.parent / "reference").is_dir():
            return root.parent
        if root.is_dir():
            return root
        raise FileNotFoundError(f"Given data root does not exist: {root}")

    for candidate in DEFAULT_DATA_ROOTS:
        if candidate.is_dir():
            return candidate

    raise FileNotFoundError(
        "Could not find the assignment data directory. Set --root to the folder containing raw/ and _manifest/."
    )


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def require_inputs(
    dimensions_root: Path,
    facts_root: Path,
    sales_root: Path,
    validation_report: Path,
) -> None:
    missing = [
        directory / f"{name}.parquet"
        for directory, names in [
            (sales_root, [name for folder, name in TABLES.values() if folder == "sales"]),
            (facts_root, [name for folder, name in TABLES.values() if folder == "facts"]),
            (
                dimensions_root,
                [name for folder, name in TABLES.values() if folder == "dimensions"],
            ),
        ]
        for name in names
        if not (directory / f"{name}.parquet").is_file()
    ]
    if missing:
        paths = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Required curated Phase 3-5 tables are missing:\n{paths}")
    if not validation_report.is_file():
        raise FileNotFoundError(f"Manifest validation report does not exist: {validation_report}")
    sql_files = sorted(SQL_ROOT.glob("*.sql"))
    if not sql_files:
        raise FileNotFoundError(f"No Phase 6 KPI SQL files found under {SQL_ROOT}")


def load_manifest_issues(report_path: Path) -> list[tuple[Any, ...]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    issues: list[tuple[Any, ...]] = []

    for item in report.get("partition_mismatches", []):
        issues.append(
            (
                item["feed"],
                item["partition"],
                "partition_mismatch",
                item.get("expected_row_count"),
                item.get("actual_row_count"),
                item.get("expected_file_count"),
                item.get("actual_file_count"),
                None,
            )
        )
    for item in report.get("missing_in_actual", []):
        issues.append(
            (
                item["feed"],
                item["partition"],
                "partition_missing",
                None,
                None,
                None,
                None,
                "Expected manifest partition is absent from the raw landing zone.",
            )
        )
    for item in report.get("missing_in_manifest", []):
        issues.append(
            (
                item["feed"],
                item["partition"],
                "partition_not_manifested",
                None,
                None,
                None,
                None,
                "Raw partition is not represented in the expected-partitions manifest.",
            )
        )
    for item in report.get("invalid_files", []):
        issues.append(
            (
                item["feed"],
                item["partition"],
                "unreadable_file",
                None,
                None,
                None,
                None,
                f"{item['file']}: {item['error']}",
            )
        )
    return issues


def build_kpis(
    dimensions_root: Path,
    facts_root: Path,
    sales_root: Path,
    output_root: Path,
    validation_report: Path,
) -> dict[str, Any]:
    require_inputs(dimensions_root, facts_root, sales_root, validation_report)
    output_root.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    try:
        roots = {
            "dimensions": dimensions_root,
            "facts": facts_root,
            "sales": sales_root,
        }
        for view_name, (folder, table_name) in TABLES.items():
            source_path = roots[folder] / f"{table_name}.parquet"
            connection.execute(
                f"CREATE VIEW {view_name} AS "
                f"SELECT * FROM read_parquet({sql_literal(str(source_path))})"
            )

        connection.execute(
            """
            CREATE TABLE manifest_partition_issues (
                feed VARCHAR,
                partition_name VARCHAR,
                issue_type VARCHAR,
                expected_rows BIGINT,
                actual_rows BIGINT,
                expected_files BIGINT,
                actual_files BIGINT,
                detail VARCHAR
            )
            """
        )
        issues = load_manifest_issues(validation_report)
        if issues:
            connection.executemany(
                "INSERT INTO manifest_partition_issues VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                issues,
            )

        results: dict[str, Any] = {}
        for sql_path in sorted(SQL_ROOT.glob("*.sql")):
            query_name = sql_path.stem
            output_path = output_root / f"{query_name}.parquet"
            query = sql_path.read_text(encoding="utf-8")
            connection.execute(
                f"COPY ({query}) TO {sql_literal(str(output_path))} "
                "(FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            rows = connection.execute(
                f"SELECT count(*) FROM read_parquet({sql_literal(str(output_path))})"
            ).fetchone()[0]
            results[query_name] = {
                "rows": rows,
                "sql": str(sql_path.relative_to(PROJECT_ROOT)),
                "path": str(output_path),
            }

        summary = {
            "source_roots": {
                "dimensions": str(dimensions_root),
                "facts": str(facts_root),
                "sales": str(sales_root),
                "manifest_validation_report": str(validation_report),
            },
            "output_directory": str(output_root),
            "manifest_issue_rows": len(issues),
            "queries": results,
        }
        summary_path = output_root / "build_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        return summary
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase 6 SQL KPI library.")
    parser.add_argument("--root", default=None, help="Assignment data root containing raw/ and _manifest/.")
    parser.add_argument(
        "--dimensions",
        default=str(PROJECT_ROOT / "curated" / "dimensions"),
        help="Directory containing Phase 3 dimension Parquet files.",
    )
    parser.add_argument(
        "--facts",
        default=str(PROJECT_ROOT / "curated" / "facts"),
        help="Directory containing Phase 4 fact Parquet files.",
    )
    parser.add_argument(
        "--sales",
        default=str(PROJECT_ROOT / "curated" / "sales"),
        help="Directory containing Phase 5 sales Parquet files.",
    )
    parser.add_argument(
        "--validation-report",
        default=str(PROJECT_ROOT / "docs" / "manifest_validation.json"),
        help="Phase 2 manifest-validation JSON report.",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "curated" / "kpis"),
        help="Output directory for Phase 6 KPI Parquet tables.",
    )
    args = parser.parse_args()
    data_root = find_data_root(args.root)
    summary = build_kpis(
        Path(args.dimensions).resolve(),
        Path(args.facts).resolve(),
        Path(args.sales).resolve(),
        Path(args.output).resolve(),
        Path(args.validation_report).resolve(),
    )
    print("Built Phase 6 KPI outputs:")
    for name, result in summary["queries"].items():
        print(f"- {name}: {result['rows']:,} rows")
    print(f"- summary: {Path(summary['output_directory']) / 'build_summary.json'}")
    print(f"- source data root: {data_root}")


if __name__ == "__main__":
    main()
