import unittest
from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RECONCILIATION_SQL = (
    PROJECT_ROOT / "sql" / "05_reconciliation" / "sales_reconciliation_finance.sql"
)


class SalesReconciliationTests(unittest.TestCase):
    def test_event_and_ingest_weeks_are_separate_and_duplicates_are_reconstructible(self) -> None:
        connection = duckdb.connect()
        try:
            connection.execute(
                """
                CREATE TABLE legacy_finance (
                    week_ending DATE,
                    channel VARCHAR,
                    gross_sales_inr DOUBLE,
                    units_sold BIGINT,
                    basket_count BIGINT,
                    prepared_by VARCHAR,
                    note VARCHAR
                )
                """
            )
            connection.execute(
                """
                INSERT INTO legacy_finance VALUES
                    ('2025-01-01', 'GT', 100.0, 3, 2, 'Finance MIS', 'benchmark'),
                    ('2025-01-08', 'GT', 100.0, 2, 1, 'Finance MIS', 'benchmark')
                """
            )
            connection.execute(
                """
                CREATE TABLE fact_reconciled_sales (
                    sale_date DATE,
                    ingest_date DATE,
                    sales_channel VARCHAR,
                    gross_sales_ex_tax_inr DOUBLE,
                    net_sales_ex_tax_inr DOUBLE,
                    quantity BIGINT,
                    basket_id VARCHAR,
                    duplicate_rows_removed BIGINT
                )
                """
            )
            connection.execute(
                """
                INSERT INTO fact_reconciled_sales VALUES
                    ('2025-01-02', '2025-01-09', 'GT', 100.0, 90.0, 2, 'B1', 1),
                    ('2025-01-03', '2025-01-03', 'GT', 50.0, 45.0, 1, 'B2', 0)
                """
            )
            connection.execute(
                """
                CREATE TABLE fact_sales_order_headers (
                    order_date DATE,
                    outlet_code VARCHAR,
                    order_value_gross DOUBLE,
                    line_count BIGINT,
                    has_known_partner_freight_adjustment BOOLEAN,
                    is_latest_version BOOLEAN,
                    is_deleted_current_order BOOLEAN
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE dim_channel_history (
                    outlet_code VARCHAR,
                    new_channel VARCHAR,
                    effective_start TIMESTAMPTZ,
                    effective_end TIMESTAMPTZ
                )
                """
            )

            query = RECONCILIATION_SQL.read_text(encoding="utf-8")
            cursor = connection.execute(query)
            columns = [item[0] for item in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

            first_week = next(row for row in rows if row["period_start"].isoformat() == "2025-01-01")
            second_week = next(row for row in rows if row["period_start"].isoformat() == "2025-01-08")

            self.assertEqual(first_week["event_dedup_gross_sales_inr"], 150.0)
            self.assertEqual(first_week["ingest_gross_sales_inr"], 50.0)
            self.assertEqual(first_week["ingest_duplicate_inclusive_gross_sales_inr"], 50.0)
            self.assertEqual(second_week["event_dedup_gross_sales_inr"], None)
            self.assertEqual(second_week["ingest_gross_sales_inr"], 100.0)
            self.assertEqual(second_week["ingest_duplicate_inclusive_gross_sales_inr"], 200.0)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
