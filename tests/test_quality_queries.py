import unittest
from pathlib import Path

import duckdb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_ROOT = PROJECT_ROOT / "sql" / "07_quality"


class QualityQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = duckdb.connect()

    def tearDown(self) -> None:
        self.connection.close()

    def execute_query(self, query_name: str) -> list[tuple]:
        query = (SQL_ROOT / f"{query_name}.sql").read_text(encoding="utf-8")
        return self.connection.execute(query).fetchall()

    def test_duplicate_record_counts_aggregates_feed_level_duplicates(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE fact_pos_transactions (
                has_exact_duplicates BOOLEAN,
                duplicate_rows_removed BIGINT
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE fact_reefer_telemetry (
                has_exact_duplicates BOOLEAN,
                duplicate_rows_removed BIGINT
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE fact_wms_scan_events (
                has_exact_duplicates BOOLEAN,
                duplicate_rows_removed BIGINT
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE fact_sales_order_headers (
                has_exact_duplicates BOOLEAN,
                duplicate_rows_removed BIGINT
            )
            """
        )
        self.connection.execute(
            "INSERT INTO fact_pos_transactions VALUES (true, 3), (false, 0)"
        )
        self.connection.execute(
            "INSERT INTO fact_reefer_telemetry VALUES (true, 2), (false, 0)"
        )
        self.connection.execute(
            "INSERT INTO fact_wms_scan_events VALUES (false, 0), (false, 0)"
        )
        self.connection.execute(
            "INSERT INTO fact_sales_order_headers VALUES (true, 1), (false, 0)"
        )

        rows = self.execute_query("duplicate_record_counts")
        self.assertEqual(rows[0][0], "fact_pos_transactions")
        self.assertEqual(rows[0][2], 3)
        self.assertEqual(rows[1][0], "fact_reefer_telemetry")
        self.assertEqual(rows[1][2], 2)
        self.assertEqual(rows[2][0], "fact_sales_order_headers")
        self.assertEqual(rows[2][2], 1)

    def test_temperature_anomaly_flags_captures_out_of_band_and_missing_values(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE fact_reefer_telemetry (
                reading_date DATE,
                warehouse_code VARCHAR,
                vehicle_registration VARCHAR,
                device_id VARCHAR,
                temperature_celsius DOUBLE,
                normalized_temp_unit VARCHAR,
                is_temperature_missing BOOLEAN,
                is_temperature_unit_unresolved BOOLEAN,
                is_timestamp_valid BOOLEAN
            )
            """
        )
        self.connection.execute(
            """
            INSERT INTO fact_reefer_telemetry VALUES
                ('2025-01-01', 'WH1', 'MH12AB0001', 'DEV-00001', 9.0, 'C', false, false, true),
                ('2025-01-01', 'WH1', 'MH12AB0002', 'DEV-00002', NULL, 'C', true, false, true),
                ('2025-01-01', 'WH1', 'MH12AB0003', 'DEV-00003', 3.0, NULL, false, true, true),
                ('2025-01-01', 'WH1', 'MH12AB0004', 'DEV-00004', 5.0, 'C', false, false, true)
            """
        )

        rows = self.execute_query("temperature_anomaly_flags")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][6], "temperature_out_of_band")
        self.assertEqual(rows[1][6], "missing_temperature")
        self.assertEqual(rows[2][6], "unit_unresolved")

    def test_missing_scan_stage_transitions_flags_holes_in_order_lifecycle(self) -> None:
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
                ('SO-1', 'WH1', 'RECEIVE', '2025-01-01 08:00:00', true, false),
                ('SO-1', 'WH1', 'DISPATCH', '2025-01-01 11:00:00', true, false),
                ('SO-2', 'WH1', 'RECEIVE', '2025-01-02 08:00:00', true, false),
                ('SO-2', 'WH1', 'PUTAWAY', '2025-01-02 09:00:00', true, false),
                ('SO-2', 'WH1', 'PICK', '2025-01-02 10:00:00', true, false),
                ('SO-2', 'WH1', 'PACK', '2025-01-02 11:00:00', true, false),
                ('SO-2', 'WH1', 'STAGE', '2025-01-02 12:00:00', true, false),
                ('SO-2', 'WH1', 'DISPATCH', '2025-01-02 13:00:00', true, false)
            """
        )

        rows = self.execute_query("missing_scan_stage_transitions")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "SO-1")
        self.assertEqual(rows[0][10], "missing_intermediate_stage")

    def test_incomplete_reference_dimensions_flags_missing_keys(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE dim_warehouse (
                warehouse_code VARCHAR,
                warehouse_name VARCHAR,
                city VARCHAR,
                region_name VARCHAR
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE dim_outlet (
                outlet_code VARCHAR,
                outlet_name VARCHAR,
                city VARCHAR,
                channel VARCHAR
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE dim_carrier (
                carrier_id VARCHAR,
                carrier_name VARCHAR,
                mode VARCHAR,
                sla_hours BIGINT
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE dim_product (
                sku_code VARCHAR,
                product_name VARCHAR,
                category VARCHAR,
                brand VARCHAR
            )
            """
        )
        self.connection.execute(
            """
            INSERT INTO dim_warehouse VALUES
                (NULL, 'WH1', 'Mumbai', 'West'),
                ('WH2', 'WH2', 'Pune', 'West')
            """
        )
        self.connection.execute(
            """
            INSERT INTO dim_outlet VALUES
                ('OUT1', 'Outlet 1', NULL, 'GT'),
                ('OUT2', 'Outlet 2', 'Pune', 'ECOM')
            """
        )
        self.connection.execute(
            "INSERT INTO dim_carrier VALUES (NULL, 'Carrier A', 'SURFACE', 24)"
        )
        self.connection.execute(
            "INSERT INTO dim_product VALUES ('SKU1', NULL, 'Dairy', 'BrandA')"
        )

        rows = self.execute_query("incomplete_reference_dimensions")
        self.assertEqual(len(rows), 4)
        self.assertEqual(
            {row[0] for row in rows},
            {"dim_warehouse", "dim_outlet", "dim_carrier", "dim_product"},
        )


if __name__ == "__main__":
    unittest.main()
