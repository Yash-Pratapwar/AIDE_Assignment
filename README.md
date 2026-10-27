# Kestrel Provisions Analytical Foundation

This repository contains the implementation for the AIDE take-home assignment. The initial work profiles the supplied raw feeds and records their schemas and known source-data risks before any business transformations are applied.

## Data policy

The assignment dataset is not stored in this repository. Keep the supplied assignment pack outside this project directory, or regenerate it separately with the provided generator. `.gitignore` excludes the local `data/` directory and common data-file formats.

The profiler defaults to looking for the assignment pack beside this repository. If the raw feeds are elsewhere, pass their location explicitly:

```powershell
python pipeline\profile_raw.py --root "D:\path\to\assignment-pack\data\raw"
```

To save the profiling summary:

```powershell
python pipeline\profile_raw.py `
  --root "D:\path\to\assignment-pack\data\raw" `
  --output docs\raw_profile.json
```

## Setup

Use Python 3.10 or later. Install the project dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Current implementation

- `pipeline/profile_raw.py` inventories Parquet feeds, partitions, file counts, row counts, and representative schemas.
- `docs/assumptions.md` captures source-contract risks and initial project assumptions.
- `docs/raw_profile.json` is generated profiling metadata; it contains no source records.

The profiling script currently summarizes up to 20 representative Parquet files per feed. It is an initial inventory, not yet a full validation of every partition or a complete anomaly report.
