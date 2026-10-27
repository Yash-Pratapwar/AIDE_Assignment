# Kestrel Provisions Analytical Foundation

This repository contains the implementation for the AIDE take-home assignment. It profiles and validates the supplied raw feeds, builds canonical dimensions from reference data and ERP CDC, and records the decisions and source-data risks that affect downstream metrics.

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

## Phase 2: validate the raw manifest

The manifest validator compares expected feed partitions and row counts with the raw landing zone. The supplied manifest covers POS, telemetry, and WMS; ERP CDC is organized by source table and is not included in that manifest.

```powershell
python pipeline\validate_manifest.py `
  --root "D:\path\to\assignment-pack\data" `
  --output docs\manifest_validation.json
```

Unreadable Parquet files are reported as data-quality failures, not silently skipped.

## Phase 3: build dimensions

Build the fiscal date dimension, effective-dated outlet and product dimensions, channel-change history, and warehouse/carrier reference dimensions:

```powershell
python pipeline\build_dimensions.py --root "D:\path\to\assignment-pack\data"
```

The default output is `curated\dimensions\` and is intentionally excluded from source control. It contains:

- `dim_date.parquet`
- `dim_outlet.parquet`
- `dim_product.parquet`
- `dim_warehouse.parquet`
- `dim_carrier.parquet`
- `dim_channel_history.parquet`
- `ref_uom_conversion.parquet`
- `build_summary.json`

Outlet and product histories are ordered by CDC operation timestamp and sequence, with source-file lineage retained. Delete events close the previous active interval. The channel history only creates a new interval when channel classification changes. Missing UOM conversions remain null and are flagged; they are not inferred from product case-pack values.

## Setup

Use Python 3.10 or later. Install the project dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Current implementation

- `pipeline/profile_raw.py` inventories Parquet feeds, partitions, file counts, row counts, and representative schemas.
- `pipeline/validate_manifest.py` compares manifest counts to the raw POS, telemetry, and WMS partitions, and flags unreadable files.
- `pipeline/build_dimensions.py` builds the Phase 3 Parquet dimensions and reference tables.
- `docs/assumptions.md` captures source-contract risks and initial project assumptions.
- `DECISIONS.md` is the project decision ledger.
- `docs/raw_profile.json` is generated profiling metadata; it contains no source records.
- `docs/manifest_validation.json` records the latest manifest validation result.
