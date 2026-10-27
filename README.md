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

## Phase 4: build curated facts

After building the Phase 3 dimensions, build the four row-level facts:

```powershell
python pipeline\build_facts.py --root "D:\path\to\assignment-pack\data"
```

The default output is `curated\facts\` and is excluded from source control. It contains:

- `fact_pos_transactions.parquet`
- `fact_sales_order_headers.parquet`
- `fact_wms_scan_events.parquet`
- `fact_reefer_telemetry.parquet`
- `build_summary.json`

Every fact includes the raw file path and row number for lineage. Exact duplicate POS and telemetry payloads are collapsed with duplicate counts retained; conflicting rows with the same business identifier remain present and are flagged. The order-header fact is at CDC event-version grain, ordered by source sequence, retaining the current-version flag and delete tombstones. Telemetry readings use normalized Celsius and corrected timestamps for the documented firmware clock offset. The corrupt telemetry file is excluded and listed in the build summary.

## Phase 5: build and compare sales

After building the Phase 3 dimensions and Phase 4 facts:

```powershell
python pipeline\build_sales.py --root "D:\path\to\assignment-pack\data"
```

Outputs are written to the ignored `curated\sales\` directory:

- `fact_reconciled_sales.parquet` — POS line-grain sales, with gross value before discount and tax, net value after discount but before tax, source lineage, and dimension-resolution flags.
- `sales_reconciliation_finance.parquet` — Finance report comparisons by supplied week label and channel. It includes local sale/event-date totals, ingest-date totals, an ingest-date duplicate-inclusive counterfactual, and separate ERP order-header evidence.
- `build_summary.json` — totals and coverage/variance counts.

The reusable SQL is in `sql\05_reconciliation\`. A critical limitation is documented in `docs\sales_reconciliation_findings.md`: although the generator comments describe legacy ingest-date and duplicate-counting defects, its Finance CSV values are generated independently at random rather than aggregated from source feeds. The report can be compared but cannot be numerically reconciled to source rows or used to prove those defects.

## Setup

Use Python 3.10 or later. Install the project dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Current implementation

- `pipeline/profile_raw.py` inventories Parquet feeds, partitions, file counts, row counts, and representative schemas.
- `pipeline/validate_manifest.py` compares manifest counts to the raw POS, telemetry, and WMS partitions, and flags unreadable files.
- `pipeline/build_dimensions.py` builds the Phase 3 Parquet dimensions and reference tables.
- `pipeline/build_facts.py` builds the four Phase 4 facts and records duplicate handling and excluded source files.
- `pipeline/build_sales.py` builds the POS-led reconciled sales fact and Finance comparison.
- `sql/05_reconciliation/` contains the Phase 5 sales and reconciliation SQL.
- `docs/assumptions.md` captures source-contract risks and initial project assumptions.
- `DECISIONS.md` is the project decision ledger.
- `docs/raw_profile.json` is generated profiling metadata; it contains no source records.
- `docs/manifest_validation.json` records the latest manifest validation result.
