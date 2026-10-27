#!/usr/bin/env python3
"""Phase 2: validate the raw manifest against the actual landing zone.

This script checks whether every expected partition exists, whether the row-counts
match the published manifest, and whether any parquet files are unreadable or
truncated. It is intentionally conservative: if a file is unreadable, it is
reported as a data-quality defect rather than silently ignored.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pyarrow.parquet as pq


DEFAULT_CANDIDATE_ROOTS = [
    Path(__file__).resolve().parents[1] / "data",
    Path(__file__).resolve().parents[2] / "AIDE_Assignment_Pack_docs_and_generator_v1" / "data",
]


def find_data_root(explicit_root: str | None) -> Path:
    if explicit_root:
        p = Path(explicit_root).resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"Given data root does not exist: {p}")

    for candidate in DEFAULT_CANDIDATE_ROOTS:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Could not find the assignment data directory. Set --root explicitly to the folder containing raw/ and _manifest/."
    )


def find_manifest_and_raw(raw_root: Path) -> tuple[Path, Path]:
    potential_manifest = raw_root / "_manifest" / "expected_partitions.csv"
    if potential_manifest.exists():
        return potential_manifest, raw_root / "raw"

    if raw_root.name == "raw":
        parent = raw_root.parent
        potential_manifest = parent / "_manifest" / "expected_partitions.csv"
        if potential_manifest.exists():
            return potential_manifest, raw_root

    raise FileNotFoundError(
        f"No expected_partitions.csv found under {raw_root}. Expected a data root containing raw/ and _manifest/."
    )


def iter_partition_dirs(raw_root: Path) -> List[tuple[str, Path]]:
    results: List[tuple[str, Path]] = []
    if not raw_root.exists():
        return results
    for feed_dir in sorted(p for p in raw_root.iterdir() if p.is_dir()):
        for part_dir in sorted(p for p in feed_dir.iterdir() if p.is_dir()):
            results.append((feed_dir.name, part_dir))
    return results


def summarize_partition(feed_name: str, part_dir: Path) -> Dict[str, Any]:
    parquet_files = sorted(part_dir.glob("*.parquet"))
    valid_files: List[str] = []
    invalid_files: List[Dict[str, str]] = []
    row_count = 0

    for file_path in parquet_files:
        try:
            pf = pq.ParquetFile(str(file_path))
            row_count += int(pf.metadata.num_rows)
            valid_files.append(str(file_path.name))
        except Exception as exc:  # pragma: no cover - defensive, norms for a real validation task
            invalid_files.append(
                {
                    "file": str(file_path.relative_to(part_dir.parent.parent)),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    return {
        "feed": feed_name,
        "partition": part_dir.name,
        "file_count": len(valid_files),
        "row_count": row_count,
        "invalid_file_count": len(invalid_files),
        "invalid_files": invalid_files,
    }


def load_manifest(manifest_path: Path) -> List[Dict[str, Any]]:
    manifest = []
    for _, row in pd.read_csv(manifest_path).iterrows():
        manifest.append(
            {
                "feed": row["feed"],
                "partition": row["partition"],
                "file_count": int(row["file_count"]),
                "row_count": int(row["row_count"]),
                "bytes": int(row["bytes"]),
            }
        )
    return manifest


def validate(raw_root: Path, manifest_path: Path) -> Dict[str, Any]:
    actual_partitions: List[Dict[str, Any]] = []
    for feed_name, part_dir in iter_partition_dirs(raw_root):
        actual_partitions.append(summarize_partition(feed_name, part_dir))

    manifest_rows = load_manifest(manifest_path)
    manifest_index = {(r["feed"], r["partition"]): r for r in manifest_rows}
    actual_index = {(r["feed"], r["partition"]): r for r in actual_partitions}

    missing_in_manifest = sorted(set(actual_index) - set(manifest_index))
    missing_in_actual = sorted(set(manifest_index) - set(actual_index))

    mismatches: List[Dict[str, Any]] = []
    for key in sorted(set(manifest_index) & set(actual_index)):
        expected = manifest_index[key]
        actual = actual_index[key]
        if expected["file_count"] != actual["file_count"] or expected["row_count"] != actual["row_count"]:
            mismatches.append(
                {
                    "feed": key[0],
                    "partition": key[1],
                    "expected_file_count": expected["file_count"],
                    "actual_file_count": actual["file_count"],
                    "expected_row_count": expected["row_count"],
                    "actual_row_count": actual["row_count"],
                }
            )

    invalid_files = [
        {
            "feed": part["feed"],
            "partition": part["partition"],
            "file": item["file"],
            "error": item["error"],
        }
        for part in actual_partitions
        for item in part["invalid_files"]
    ]

    by_feed: Dict[str, Dict[str, Any]] = {}
    for feed_name in sorted(set(r["feed"] for r in manifest_rows) | set(r["feed"] for r in actual_partitions)):
        manifest_total_rows = sum(r["row_count"] for r in manifest_rows if r["feed"] == feed_name)
        actual_total_rows = sum(r["row_count"] for r in actual_partitions if r["feed"] == feed_name)
        manifest_total_files = sum(r["file_count"] for r in manifest_rows if r["feed"] == feed_name)
        actual_total_files = sum(r["file_count"] for r in actual_partitions if r["feed"] == feed_name)
        by_feed[feed_name] = {
            "manifest_partition_count": len([r for r in manifest_rows if r["feed"] == feed_name]),
            "actual_partition_count": len([r for r in actual_partitions if r["feed"] == feed_name]),
            "manifest_total_rows": manifest_total_rows,
            "actual_total_rows": actual_total_rows,
            "manifest_total_files": manifest_total_files,
            "actual_total_files": actual_total_files,
            "partition_mismatch_count": len([m for m in mismatches if m["feed"] == feed_name]),
            "invalid_file_count": len([f for f in invalid_files if f["feed"] == feed_name]),
        }

    report = {
        "raw_root": str(raw_root),
        "manifest_path": str(manifest_path),
        "summary": {
            "expected_partitions": len(manifest_rows),
            "actual_partitions": len(actual_partitions),
            "missing_in_manifest": len(missing_in_manifest),
            "missing_in_actual": len(missing_in_actual),
            "partition_mismatches": len(mismatches),
            "invalid_file_count": len(invalid_files),
        },
        "feeds": by_feed,
        "missing_in_manifest": [
            {"feed": key[0], "partition": key[1]} for key in missing_in_manifest
        ],
        "missing_in_actual": [
            {"feed": key[0], "partition": key[1]} for key in missing_in_actual
        ],
        "partition_mismatches": mismatches,
        "invalid_files": invalid_files,
    }

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the manifest against the raw file landing zone.")
    parser.add_argument("--root", default=None, help="Path to the data root (the parent folder of raw/ and _manifest/).")
    parser.add_argument("--manifest", default=None, help="Optional path to expected_partitions.csv.")
    parser.add_argument("--output", default=None, help="Optional path to write the validation JSON report.")
    args = parser.parse_args()

    data_root = find_data_root(args.root)
    manifest_path = Path(args.manifest).resolve() if args.manifest else find_manifest_and_raw(data_root)[0]
    raw_root = find_manifest_and_raw(data_root)[1]
    report = validate(raw_root, manifest_path)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Saved validation report to {out_path}")

    summary = report["summary"]
    print("Manifest validation summary:")
    print(f"- expected partitions: {summary['expected_partitions']}")
    print(f"- actual partitions: {summary['actual_partitions']}")
    print(f"- missing in manifest: {summary['missing_in_manifest']}")
    print(f"- missing in actual: {summary['missing_in_actual']}")
    print(f"- partition mismatches: {summary['partition_mismatches']}")
    print(f"- invalid parquet files: {summary['invalid_file_count']}")

    if report["invalid_files"]:
        first = report["invalid_files"][0]
        print(f"- first invalid file: {first['feed']} / {first['partition']} / {first['file']}")
        print(f"  error: {first['error']}")

    if report["partition_mismatches"]:
        first = report["partition_mismatches"][0]
        print(f"- first mismatch: {first['feed']} / {first['partition']}")
        print(
            f"  expected {first['expected_file_count']} files and {first['expected_row_count']} rows; "
            f"actual {first['actual_file_count']} files and {first['actual_row_count']} rows"
        )


if __name__ == "__main__":
    main()
