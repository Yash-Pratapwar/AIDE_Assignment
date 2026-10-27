#!/usr/bin/env python3
"""Phase 1: profile the raw Parquet feeds and capture schema inventories.

This script is intentionally simple and operationally focused. It answers:
- what feeds exist
- how many partitions/files exist
- what the schema looks like per file
- how many rows exist per partition
- whether there are obvious schema drift patterns

Usage examples:
    python pipeline/profile_raw.py
    python pipeline/profile_raw.py --root ../AIDE_Assignment_Pack_docs_and_generator_v1/data/raw
    python pipeline/profile_raw.py --output /tmp/raw_profile.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import pyarrow.parquet as pq


DEFAULT_CANDIDATE_ROOTS = [
    Path(__file__).resolve().parents[1] / "data" / "raw",
    Path(__file__).resolve().parents[2] / "AIDE_Assignment_Pack_docs_and_generator_v1" / "data" / "raw",
]


def find_raw_root(explicit_root: str | None) -> Path:
    if explicit_root:
        p = Path(explicit_root).resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"Given raw data root does not exist: {p}")

    for candidate in DEFAULT_CANDIDATE_ROOTS:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Could not find a raw data directory under the project or sibling assignment bundle. "
        "Set --root explicitly."
    )


def iter_parquet_files(root: Path) -> List[Path]:
    return sorted(p for p in root.rglob("*.parquet") if p.is_file())


def summarize_file(file_path: Path) -> Dict[str, Any]:
    pf = pq.ParquetFile(str(file_path))
    schema = pf.schema_arrow
    fields = [str(field.name) for field in schema]
    row_count = int(pf.metadata.num_rows)
    file_size = int(file_path.stat().st_size)
    return {
        "rows": row_count,
        "file_size_bytes": file_size,
        "fields": fields,
    }


def summarize_feed(root: Path) -> Dict[str, Any]:
    by_feed: Dict[str, Any] = {}
    for feed_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        feed_name = feed_dir.name
        files = iter_parquet_files(feed_dir)
        partitions = sorted({p.parent.name for p in files})

        feed_summary = {
            "feed": feed_name,
            "partition_count": len(partitions),
            "file_count": len(files),
            "partitions": partitions[:20],
            "files": [],
        }

        for file_path in files[:20]:
            feed_summary["files"].append({
                "path": str(file_path.relative_to(root)),
                **summarize_file(file_path),
            })

        # Avoid reading all files for the summary if there are many; keep the main schema inventory
        # but still show a compact file count and a representative schema sample.
        by_feed[feed_name] = feed_summary

    return by_feed


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile the raw dataset for phase 1 analysis.")
    parser.add_argument("--root", default=None, help="Path to raw feed root, for example data/raw")
    parser.add_argument("--output", default=None, help="Optional path for JSON output")
    args = parser.parse_args()

    raw_root = find_raw_root(args.root)
    profile = {
        "root_directory_name": raw_root.name,
        "feeds": summarize_feed(raw_root),
    }

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        print(f"Saved raw data profile to {out_path}")

    print(f"Raw data root: {raw_root}")
    print("\nFeed Summary:")
    for feed_name, summary in profile["feeds"].items():
        print(f"- {feed_name}: {summary['file_count']} parquet files across {summary['partition_count']} partitions")
        if summary["files"]:
            first = summary["files"][0]
            print(f"  sample file: {first['path']}")
            print(f"  row count: {first['rows']}")
            print(f"  fields: {first['fields'][:10]}" + (" ..." if len(first['fields']) > 10 else ""))

    print("\nNext phase: inspect the schema drift and actual raw values before writing the curated layer.")


if __name__ == "__main__":
    main()
