#!/usr/bin/env python3
"""Build the Phase 5 POS-led sales fact and Finance reconciliation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATE_ROOTS = [
    PROJECT_ROOT / "data",
    PROJECT_ROOT.parent / "AIDE_Assignment_Pack_docs_and_generator_v1" / "data",
]
REQUIRED_FACTS = ["fact_pos_transactions", "fact_sales_order_headers"]
REQUIRED_DIMENSIONS = ["dim_channel_history"]
SQL_ROOT = PROJECT_ROOT / "sql" / "05_reconciliation"


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


def require_files(directory: Path, names: list[str], description: str) -> None:
    missing = [directory / f"{name}.parquet" for name in names if not (directory / f"{name}.parquet").is_file()]
    if missing:
        paths = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Missing {description}. Build prior phases first:\n{paths}")


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def create_views(
    connection: duckdb.DuckDBPyConnection,
    data_root: Path,
    dimensions_root: Path,
    facts_root: Path,
) -> None:
    sources = {
        "fact_pos_transactions": facts_root / "fact_pos_transactions.parquet",
        "fact_sales_order_headers": facts_root / "fact_sales_order_headers.parquet",
        "dim_channel_history": dimensions_root / "dim_channel_history.parquet",
    }
    for view_name, path in sources.items():
        connection.execute(
            f"CREATE VIEW {view_name} AS SELECT * FROM read_parquet({sql_literal(str(path))})"
        )

    finance_path = data_root / "reference" / "legacy_finance_weekly_report.csv"
    if not finance_path.is_file():
        raise FileNotFoundError(f"Required Finance report does not exist: {finance_path}")
    connection.execute(
        "CREATE VIEW legacy_finance AS "
        "SELECT "
        "CAST(week_ending AS DATE) AS week_ending, "
        "channel, CAST(gross_sales_inr AS DOUBLE) AS gross_sales_inr, "
        "CAST(units_sold AS BIGINT) AS units_sold, "
        "CAST(basket_count AS BIGINT) AS basket_count, prepared_by, note "
        f"FROM read_csv_auto({sql_literal(str(finance_path))}, header=true)"
    )


def execute_to_parquet(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    connection.execute(
        f"COPY ({query}) TO {sql_literal(str(output_path))} "
        "(FORMAT PARQUET, COMPRESSION ZSTD)"
    )


def fact_summary(connection: duckdb.DuckDBPyConnection, path: Path) -> dict[str, Any]:
    path_sql = sql_literal(str(path))
    rows = connection.execute(
        f"SELECT count(*), count(DISTINCT txn_id || ':' || txn_line_no::VARCHAR), "
        f"sum(gross_sales_ex_tax_inr), sum(net_sales_ex_tax_inr), sum(tax_amount), "
        f"sum(duplicate_rows_removed), "
        f"count(*) FILTER (WHERE is_outlet_dimension_unresolved), "
        f"count(*) FILTER (WHERE is_product_dimension_unresolved), "
        f"count(*) FILTER (WHERE is_erp_channel_unresolved), "
        f"count(*) FILTER (WHERE is_captured_channel_mismatch) "
        f"FROM read_parquet({path_sql})"
    ).fetchone()
    return {
        "rows": rows[0],
        "distinct_transaction_lines": rows[1],
        "gross_sales_ex_tax_inr": rows[2],
        "net_sales_ex_tax_inr": rows[3],
        "tax_amount_inr": rows[4],
        "duplicate_rows_removed": rows[5],
        "rows_without_outlet_dimension": rows[6],
        "rows_without_product_dimension": rows[7],
        "rows_without_erp_channel_history": rows[8],
        "captured_channel_mismatch_rows": rows[9],
        "path": str(path),
    }


def reconciliation_summary(
    connection: duckdb.DuckDBPyConnection,
    path: Path,
) -> dict[str, Any]:
    path_sql = sql_literal(str(path))
    row = connection.execute(
        f"""
        SELECT
            count(*),
            count(*) FILTER (WHERE NOT is_finance_row_missing),
            count(*) FILTER (WHERE is_pos_row_missing),
            sum(finance_gross_sales_inr),
            sum(event_dedup_gross_sales_inr),
            sum(ingest_gross_sales_inr),
            sum(ingest_duplicate_inclusive_gross_sales_inr),
            sum(current_erp_order_gross_value_inr),
            sum(estimated_duplicate_gross_inflation_inr),
            sum(abs(event_basis_gross_variance_inr)),
            sum(abs(ingest_basis_gross_variance_inr)),
            sum(finance_units_sold),
            sum(event_dedup_units_sold),
            sum(ingest_units_sold),
            sum(ingest_duplicate_inclusive_units_sold),
            sum(current_erp_order_count),
            sum(partner_api_order_count)
        FROM read_parquet({path_sql})
        """
    ).fetchone()
    return {
        "weekly_channel_rows": row[0],
        "finance_rows_present": row[1],
        "rows_without_pos_sales": row[2],
        "finance_published_gross_sales_inr": row[3],
        "pos_event_date_deduplicated_gross_sales_ex_tax_inr": row[4],
        "pos_ingest_date_deduplicated_gross_sales_ex_tax_inr": row[5],
        "pos_ingest_date_duplicate_inclusive_gross_sales_ex_tax_inr": row[6],
        "current_erp_order_gross_value_inr_separate_non_additive": row[7],
        "estimated_duplicate_gross_inflation_inr": row[8],
        "sum_absolute_event_basis_variance_inr": row[9],
        "sum_absolute_ingest_basis_variance_inr": row[10],
        "finance_published_units_sold": row[11],
        "pos_event_date_deduplicated_units_sold": row[12],
        "pos_ingest_date_deduplicated_units_sold": row[13],
        "pos_ingest_date_duplicate_inclusive_units_sold": row[14],
        "current_erp_orders": row[15],
        "partner_api_current_orders": row[16],
    }


def write_findings(
    report: dict[str, Any],
    output_path: Path,
) -> None:
    fact = report["fact_reconciled_sales"]
    reconciliation = report["finance_reconciliation"]
    event_delta = (
        reconciliation["pos_event_date_deduplicated_gross_sales_ex_tax_inr"]
        - reconciliation["finance_published_gross_sales_inr"]
    )
    ingest_delta = (
        reconciliation["pos_ingest_date_deduplicated_gross_sales_ex_tax_inr"]
        - reconciliation["finance_published_gross_sales_inr"]
    )
    duplicate_inflation = reconciliation["estimated_duplicate_gross_inflation_inr"]
    content = f"""# Phase 5 sales reconciliation findings

## Canonical sales basis

The canonical sales fact uses deduplicated POS transaction lines, with channel
from the POS transaction as captured. `gross_sales_ex_tax_inr` is quantity times
unit price before discounts; `net_sales_ex_tax_inr` subtracts line discounts.
Tax is stored separately. This follows the POS contract, which says unit price
is exclusive of tax. Rows with unresolved master/channel lookups remain in the
fact and are flagged rather than silently removed.

The ERP order-header feed is kept as independent comparison evidence. It is not
added to POS sales because it has order-header rather than transaction-line
grain, has no join key to the POS rows, includes lifecycle versions/tombstones,
and the assignment documents a source-system valuation issue. Its value is
reported separately and is explicitly non-additive.

## Finance comparison

The supplied Finance report contains {reconciliation['finance_rows_present']:,}
week/channel rows. The comparison output contains
{reconciliation['weekly_channel_rows']:,} rows in total: the Finance report
rows have POS counterparts, and {reconciliation['rows_without_pos_sales']:,}
additional rows contain ERP evidence only, with neither Finance nor POS sales.
Across its covered windows, published gross sales total
INR {reconciliation['finance_published_gross_sales_inr']:,.2f}. The corresponding
deduplicated POS gross amount is INR
{reconciliation['pos_event_date_deduplicated_gross_sales_ex_tax_inr']:,.2f}
when bucketed by local sale/event date, and INR
{reconciliation['pos_ingest_date_deduplicated_gross_sales_ex_tax_inr']:,.2f}
when bucketed by ingest date. Event-date POS minus Finance is INR
{event_delta:,.2f}; ingest-date POS minus Finance is INR {ingest_delta:,.2f}.

Reconstructing duplicate delivery without deduplication would add an estimated
INR {duplicate_inflation:,.2f} to the ingest-date POS gross amount, based on the
exact-duplicate counts retained by the Phase 4 fact.

## Important limitation: supplied report does not encode the stated legacy logic

The assignment generator labels the Finance report as having ingest-date and
duplicate-counting defects. However, the generator code creates
`legacy_finance_weekly_report.csv` from independent random values
(`rng.uniform` for gross sales and `rng.integers` for units/baskets), rather
than aggregating either POS or ERP source rows. Therefore the numerical
variances cannot validate those defects or be fully reconciled to source rows.
The comparison table shows event-date, ingest-date, and duplicate-inclusive
counterfactuals so a real report with the described legacy logic can be
reconciled when supplied. Until then, published report values are a benchmark,
not a validated target.

The report's `week_ending` values are Wednesdays spaced seven days apart, and
the generator derives them from `DAYSTR[::7]`. The reconciliation therefore
uses each supplied label as the start of a seven-day, half-open bucket
`[week_ending, week_ending + 7 days)`. This is an observed data-layout
interpretation; the column name itself suggests the opposite boundary.
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def build_sales(
    data_root: Path,
    dimensions_root: Path,
    facts_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    require_files(facts_root, REQUIRED_FACTS, "Phase 4 facts")
    require_files(dimensions_root, REQUIRED_DIMENSIONS, "Phase 3 dimensions")
    fact_query_path = SQL_ROOT / "fact_reconciled_sales.sql"
    reconciliation_query_path = SQL_ROOT / "sales_reconciliation_finance.sql"
    for path in [fact_query_path, reconciliation_query_path]:
        if not path.is_file():
            raise FileNotFoundError(f"Required Phase 5 SQL file does not exist: {path}")

    connection = duckdb.connect()
    try:
        create_views(connection, data_root, dimensions_root, facts_root)
        fact_query = fact_query_path.read_text(encoding="utf-8")
        reconciliation_query = reconciliation_query_path.read_text(encoding="utf-8")

        fact_path = output_root / "fact_reconciled_sales.parquet"
        execute_to_parquet(connection, fact_query, fact_path)
        connection.execute(
            "CREATE VIEW fact_reconciled_sales AS "
            f"SELECT * FROM read_parquet({sql_literal(str(fact_path))})"
        )

        reconciliation_path = output_root / "sales_reconciliation_finance.parquet"
        execute_to_parquet(connection, reconciliation_query, reconciliation_path)
        report: dict[str, Any] = {
            "source_data_root": str(data_root),
            "output_directory": str(output_root),
            "fact_reconciled_sales": fact_summary(connection, fact_path),
            "finance_reconciliation": reconciliation_summary(connection, reconciliation_path),
            "reconciliation_path": str(reconciliation_path),
            "sql": {
                "fact": str(fact_query_path.relative_to(PROJECT_ROOT)),
                "finance_reconciliation": str(reconciliation_query_path.relative_to(PROJECT_ROOT)),
            },
            "finding": (
                "The supplied Finance report is generated from independent random values in the assignment "
                "generator, so its reported amounts cannot validate the documented ingest-date and "
                "duplicate-counting logic."
            ),
        }
        summary_path = output_root / "build_summary.json"
        findings_path = PROJECT_ROOT / "docs" / "sales_reconciliation_findings.md"
        write_findings(report, findings_path)
        report["findings_document"] = str(findings_path)
        summary_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        return report
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Phase 5 reconciled sales fact and Finance comparison.")
    parser.add_argument("--root", default=None, help="Data root containing raw/ and reference/ (or raw/).")
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
        "--output",
        default=str(PROJECT_ROOT / "curated" / "sales"),
        help="Output directory for Phase 5 sales tables.",
    )
    args = parser.parse_args()

    report = build_sales(
        find_data_root(args.root),
        Path(args.dimensions).resolve(),
        Path(args.facts).resolve(),
        Path(args.output).resolve(),
    )
    fact = report["fact_reconciled_sales"]
    reconciliation = report["finance_reconciliation"]
    print("Built Phase 5 sales outputs:")
    print(f"- fact_reconciled_sales: {fact['rows']:,} rows")
    print(f"- Finance reconciliation: {reconciliation['weekly_channel_rows']:,} week/channel rows")
    print(
        "- POS gross sales (event date, ex tax): "
        f"INR {reconciliation['pos_event_date_deduplicated_gross_sales_ex_tax_inr']:,.2f}"
    )
    print(
        "- Estimated duplicate-inclusive uplift: "
        f"INR {reconciliation['estimated_duplicate_gross_inflation_inr']:,.2f}"
    )
    print("- Finance figures are an independent synthetic benchmark, not source-reconciled output.")
    print(f"- summary: {Path(report['output_directory']) / 'build_summary.json'}")


if __name__ == "__main__":
    main()
