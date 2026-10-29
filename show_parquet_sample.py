#!/usr/bin/env python3
"""Print the schema and a few rows from a Parquet file."""

import argparse
from pathlib import Path

import pyarrow.parquet as pq


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "parquet_file",
        nargs="?",
        type=Path,
        default=project_dir / "curated" / "facts" / "fact_pos_transactions.parquet",
        help="Parquet file to inspect (defaults to the curated POS transactions)",
    )
    parser.add_argument("--rows", type=int, default=10, help="Number of sample rows")
    args = parser.parse_args()

    if args.rows < 1:
        parser.error("--rows must be at least 1")
    if not args.parquet_file.is_file():
        parser.error(f"Parquet file does not exist: {args.parquet_file}")

    parquet = pq.ParquetFile(args.parquet_file)
    print(f"File: {args.parquet_file}")
    print(f"Rows: {parquet.metadata.num_rows:,}")
    print("Schema:")
    print(parquet.schema_arrow)
    print(f"First {args.rows} rows:")
    print(next(parquet.iter_batches(batch_size=args.rows)).to_pandas().to_string(index=False))


if __name__ == "__main__":
    main()
