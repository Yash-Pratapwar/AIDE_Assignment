#!/usr/bin/env python3
"""Run a SQL query against the curated Parquet data and print a sample."""

import argparse
import json
from pathlib import Path

import duckdb


PROJECT_DIR = Path(__file__).resolve().parent
CURATED_DIR = PROJECT_DIR / "curated"
MANIFEST_REPORT = PROJECT_DIR / "docs" / "manifest_validation.json"
DATA_ROOTS = [
    PROJECT_DIR / "data",
    PROJECT_DIR.parent / "AIDE_Assignment_Pack_docs_and_generator_v1" / "data",
]


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def load_manifest_issues() -> list[tuple[object, ...]]:
    if not MANIFEST_REPORT.is_file():
        return []

    report = json.loads(MANIFEST_REPORT.read_text(encoding="utf-8"))
    issues: list[tuple[object, ...]] = []
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


def register_data_views(connection: duckdb.DuckDBPyConnection) -> None:
    if not CURATED_DIR.is_dir():
        raise FileNotFoundError(f"Curated data directory does not exist: {CURATED_DIR}")

    for parquet_file in sorted(CURATED_DIR.rglob("*.parquet")):
        view_name = '"' + parquet_file.stem.replace('"', '""') + '"'
        connection.execute(
            f"CREATE VIEW {view_name} AS "
            f"SELECT * FROM read_parquet({sql_literal(str(parquet_file))})"
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
    issues = load_manifest_issues()
    if issues:
        connection.executemany(
            "INSERT INTO manifest_partition_issues VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            issues,
        )

    finance_file = next(
        (
            root / "reference" / "legacy_finance_weekly_report.csv"
            for root in DATA_ROOTS
            if (root / "reference" / "legacy_finance_weekly_report.csv").is_file()
        ),
        None,
    )
    if finance_file:
        connection.execute(
            "CREATE VIEW legacy_finance AS "
            "SELECT CAST(week_ending AS DATE) AS week_ending, channel, "
            "CAST(gross_sales_inr AS DOUBLE) AS gross_sales_inr, "
            "CAST(units_sold AS BIGINT) AS units_sold, "
            "CAST(basket_count AS BIGINT) AS basket_count, prepared_by, note "
            f"FROM read_csv_auto({sql_literal(str(finance_file))}, header=true)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sql_file", type=Path, help="Path to the SQL query file")
    parser.add_argument("--rows", type=int, default=5, help="Number of result rows to display")
    args = parser.parse_args()
    if args.rows < 1:
        parser.error("--rows must be at least 1")
    sql_file = args.sql_file.resolve()
    if not sql_file.is_file():
        parser.error(f"SQL file does not exist: {sql_file}")

    connection = duckdb.connect()
    try:
        register_data_views(connection)
        query = sql_file.read_text(encoding="utf-8").strip().rstrip(";")
        if not query:
            parser.error(f"SQL file is empty: {sql_file}")

        row_count = connection.execute(
            f"SELECT count(*) FROM ({query}) AS query_results"
        ).fetchone()[0]
        columns = [
            column[0]
            for column in connection.execute(
                f"SELECT * FROM ({query}) AS query_results LIMIT 0"
            ).description
        ]
        shown_columns = columns[:12]
        quoted_columns = ['"' + column.replace('"', '""') + '"' for column in shown_columns]
        projection = ", ".join(f"{column}::VARCHAR" for column in quoted_columns)
        result = connection.execute(
            f"SELECT {projection} FROM ({query}) AS query_results LIMIT {args.rows}"
        )
        print(f"SQL: {sql_file}")
        print(f"Rows returned: {row_count:,}")
        print(f"First {args.rows} rows:")
        print(" | ".join(shown_columns))
        for row in result.fetchall():
            print(" | ".join(str(value) for value in row))
        if len(columns) > len(shown_columns):
            print(f"(Showing {len(shown_columns)} of {len(columns)} columns)")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
