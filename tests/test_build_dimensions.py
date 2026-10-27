import unittest

import pandas as pd

from pipeline.build_dimensions import build_channel_history, build_scd2


class BuildDimensionsTests(unittest.TestCase):
    def test_scd2_orders_events_and_uses_delete_as_interval_end(self) -> None:
        changes = pd.DataFrame(
            [
                {
                    "outlet_code": "OUT1",
                    "__op": "U",
                    "__op_ts": "2025-01-03T00:00:00Z",
                    "__seq": 3,
                    "channel": "MT",
                    "source_extract_date": "2025-01-03",
                    "source_file": "update.parquet",
                },
                {
                    "outlet_code": "OUT1",
                    "__op": "D",
                    "__op_ts": "2025-01-05T00:00:00Z",
                    "__seq": 5,
                    "channel": "MT",
                    "source_extract_date": "2025-01-05",
                    "source_file": "delete.parquet",
                },
                {
                    "outlet_code": "OUT1",
                    "__op": "I",
                    "__op_ts": "2025-01-01T00:00:00Z",
                    "__seq": 1,
                    "channel": "GT",
                    "source_extract_date": "2025-01-01",
                    "source_file": "insert.parquet",
                },
                {
                    "outlet_code": "OUT1",
                    "__op": "U",
                    "__op_ts": "2025-01-03T00:00:00Z",
                    "__seq": 4,
                    "channel": "HORECA",
                    "source_extract_date": "2025-01-03",
                    "source_file": "same_timestamp_later_sequence.parquet",
                },
            ]
        )

        dimension = build_scd2(changes, "outlet_code", ["channel"])

        self.assertEqual(dimension["channel"].tolist(), ["GT", "HORECA"])
        self.assertEqual(dimension["source_seq"].tolist(), [1, 4])
        self.assertEqual(
            dimension["effective_end"].dt.strftime("%Y-%m-%d").tolist(),
            ["2025-01-03", "2025-01-05"],
        )
        self.assertFalse(dimension["is_current"].any())

    def test_channel_history_spans_non_channel_updates_and_closes_on_delete(self) -> None:
        changes = pd.DataFrame(
            [
                {
                    "outlet_code": "OUT1",
                    "__op": "I",
                    "__op_ts": "2025-01-01T00:00:00Z",
                    "__seq": 1,
                    "channel": "GT",
                    "outlet_name": "A",
                    "source_extract_date": "2025-01-01",
                    "source_file": "insert.parquet",
                },
                {
                    "outlet_code": "OUT1",
                    "__op": "U",
                    "__op_ts": "2025-01-02T00:00:00Z",
                    "__seq": 2,
                    "channel": "GT",
                    "outlet_name": "Renamed",
                    "source_extract_date": "2025-01-02",
                    "source_file": "non_channel_update.parquet",
                },
                {
                    "outlet_code": "OUT1",
                    "__op": "U",
                    "__op_ts": "2025-01-03T00:00:00Z",
                    "__seq": 3,
                    "channel": "MT",
                    "outlet_name": "Renamed",
                    "source_extract_date": "2025-01-03",
                    "source_file": "channel_update.parquet",
                },
                {
                    "outlet_code": "OUT1",
                    "__op": "D",
                    "__op_ts": "2025-01-05T00:00:00Z",
                    "__seq": 4,
                    "channel": "MT",
                    "outlet_name": "Renamed",
                    "source_extract_date": "2025-01-05",
                    "source_file": "delete.parquet",
                },
            ]
        )

        outlet_dimension = build_scd2(
            changes,
            "outlet_code",
            ["channel", "outlet_name"],
        )
        channel_history = build_channel_history(outlet_dimension)

        self.assertEqual(channel_history["new_channel"].tolist(), ["GT", "MT"])
        self.assertTrue(pd.isna(channel_history["previous_channel"].iloc[0]))
        self.assertEqual(channel_history["previous_channel"].iloc[1], "GT")
        self.assertEqual(
            channel_history["effective_end"].dt.strftime("%Y-%m-%d").tolist(),
            ["2025-01-03", "2025-01-05"],
        )
        self.assertFalse(channel_history["is_current"].any())


if __name__ == "__main__":
    unittest.main()
