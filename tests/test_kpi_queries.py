import unittest
from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_ROOT = PROJECT_ROOT / "sql" / "06_kpis"


class KpiQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = duckdb.connect()

    def tearDown(self) -> None:
        self.connection.close()

    def execute_query(self, query_name: str) -> list[tuple]:
        query = (SQL_ROOT / f"{query_name}.sql").read_text(encoding="utf-8")
        return self.connection.execute(query).fetchall()

    def test_sales_and_units_include_unresolved_lines_but_exclude_invalid_or_ambiguous(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE dim_date (
                calendar_date DATE,
                fiscal_year VARCHAR,
                fiscal_quarter VARCHAR,
                fiscal_period VARCHAR,
                month_start DATE
            )
            """
        )
        self.connection.execute(
            "INSERT INTO dim_date VALUES ('2025-01-02', 'FY25', 'Q4', 'P10', '2025-01-01')"
        )
        self.connection.execute(
            """
            CREATE TABLE fact_reconciled_sales (
                sale_date DATE,
                sales_channel VARCHAR,
                is_timestamp_valid BOOLEAN,
                is_ambiguous_line_key BOOLEAN,
                gross_sales_ex_tax_inr DOUBLE,
                net_sales_ex_tax_inr DOUBLE,
                tax_amount DOUBLE,
                quantity_eaches DOUBLE,
                quantity BIGINT,
                is_outlet_dimension_unresolved BOOLEAN,
                is_product_dimension_unresolved BOOLEAN,
                is_captured_channel_mismatch BOOLEAN
            )
            """
        )
        self.connection.execute(
            """
            INSERT INTO fact_reconciled_sales VALUES
                ('2025-01-02', 'GT', true, false, 100, 80, 5, 2, 2, false, false, false),
                ('2025-01-02', 'GT', true, false, 50, 40, 2, NULL, 1, true, true, true),
                ('2025-01-02', 'GT', false, false, 900, 800, 10, 9, 9, false, false, false),
                ('2025-01-02', 'GT', true, true, 700, 600, 8, 7, 7, false, false, false)
            """
        )

        sales = self.execute_query("gross_sales_by_channel")[0]
        units = self.execute_query("units_sold_eaches")[0]

        self.assertEqual(sales[5:10], (2, 150.0, 120.0, 7.0, 2.0))
        self.assertEqual(sales[10:13], (1, 1, 1))
        self.assertEqual(units[5:10], (2.0, 2, 1, 1, 1))

    def test_excursion_rate_uses_observed_vehicle_days_and_valid_readings(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE fact_reefer_telemetry (
                reading_date DATE,
                warehouse_code VARCHAR,
                vehicle_registration VARCHAR,
                temperature_celsius DOUBLE,
                is_timestamp_valid BOOLEAN,
                is_temperature_unit_unresolved BOOLEAN,
                is_ambiguous_reading_key BOOLEAN
            )
            """
        )
        self.connection.execute(
            """
            INSERT INTO fact_reefer_telemetry VALUES
                ('2025-01-01', 'W1', 'V1', 9.0, true, false, false),
                ('2025-01-01', 'W1', 'V1', 4.0, true, false, false),
                ('2025-01-02', 'W1', 'V1', 4.0, true, false, false),
                ('2025-01-02', 'W1', 'V1', 12.0, true, false, true),
                ('2025-01-02', 'W1', 'V2', 12.0, true, true, false),
                ('2025-01-02', 'W1', 'V2', 12.0, false, false, false)
            """
        )

        rows = self.execute_query("chilled_excursion_vehicle_day")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], 2)
        self.assertEqual(rows[0][3], 1)
        self.assertEqual(rows[0][4], 50.0)
        self.assertEqual(rows[0][5], 3)

    def test_receive_to_dispatch_pairs_only_later_scans_and_keeps_unpaired_receives(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE fact_wms_scan_events (
                order_number VARCHAR,
                warehouse_code VARCHAR,
                event_type VARCHAR,
                event_timestamp_local TIMESTAMP,
                is_timestamp_valid BOOLEAN,
                is_ambiguous_scan_id BOOLEAN
            )
            """
        )
        self.connection.execute(
            """
            INSERT INTO fact_wms_scan_events VALUES
                ('O1', 'W1', 'DISPATCH', '2025-01-01 08:00:00', true, false),
                ('O1', 'W1', 'RECEIVE',  '2025-01-01 09:00:00', true, false),
                ('O1', 'W1', 'DISPATCH', '2025-01-01 11:00:00', true, false),
                ('O2', 'W1', 'RECEIVE',  '2025-01-02 09:00:00', true, false),
                ('O2', 'W1', 'DISPATCH', '2025-01-02 10:00:00', true, true)
            """
        )

        rows = self.execute_query("warehouse_receive_to_dispatch")

        self.assertEqual(len(rows), 1)
        january = rows[0]
        self.assertEqual(january[0].isoformat(), "2025-01-01")
        self.assertEqual(january[2], 2)
        self.assertEqual(january[3], 1)
        self.assertEqual(january[4], 1)
        self.assertEqual(january[5], 2.0)

    def test_dispatch_service_proxy_reports_scan_coverage_separately(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE fact_sales_order_headers (
                order_number VARCHAR,
                warehouse_code VARCHAR,
                requested_delivery_date DATE,
                source_system VARCHAR,
                order_status VARCHAR,
                is_latest_version BOOLEAN,
                is_deleted_current_order BOOLEAN
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE fact_wms_scan_events (
                order_number VARCHAR,
                warehouse_code VARCHAR,
                event_type VARCHAR,
                event_timestamp_local TIMESTAMP,
                is_timestamp_valid BOOLEAN,
                is_ambiguous_scan_id BOOLEAN
            )
            """
        )
        self.connection.execute(
            """
            INSERT INTO fact_sales_order_headers VALUES
                ('O1', 'W1', '2025-01-02', 'ERP_WEB', 'DISPATCHED', true, false),
                ('O2', 'W1', '2025-01-02', 'SFA_MOBILE', 'DISPATCHED', true, false),
                ('O3', 'W1', '2025-01-02', 'ERP_WEB', 'PICKED', true, false)
            """
        )
        self.connection.execute(
            """
            INSERT INTO fact_wms_scan_events VALUES
                ('O1', 'W1', 'DISPATCH', '2025-01-02 09:00:00', true, false),
                ('O2', 'W1', 'DISPATCH', '2025-01-03 09:00:00', true, false)
            """
        )

        row = self.execute_query("dispatch_service_level_proxy")[0]

        self.assertEqual(row[2], 2)
        self.assertEqual(row[3], 2)
        self.assertEqual(row[4], 100.0)
        self.assertEqual(row[5], 1)
        self.assertEqual(row[6], 50.0)

    def test_missing_data_query_collapses_partition_issues(self) -> None:
        self.connection.execute(
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
        self.connection.execute(
            """
            INSERT INTO manifest_partition_issues VALUES
                ('reefer_telemetry', 'dt=2025-07-14', 'partition_mismatch', 6724, 5779, 8, 7, NULL),
                ('reefer_telemetry', 'dt=2025-07-14', 'unreadable_file', NULL, NULL, NULL, NULL, 'bad parquet')
            """
        )

        rows = self.execute_query("missing_data_days")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "reefer_telemetry")
        self.assertEqual(rows[0][1], "dt=2025-07-14")
        self.assertEqual(rows[0][3:7], (6724, 5779, 8, 7))
        self.assertIn("partition_mismatch", rows[0][2])
        self.assertIn("unreadable_file", rows[0][2])


if __name__ == "__main__":
    unittest.main()
