# Phase 1: Initial assumptions and findings

## Source of truth and scope

This phase is focused on understanding the raw source feeds and documenting the assumptions that will drive the rest of the implementation. The purpose is not to pick a final metric definition yet; it is to make the source data, schema drift, and known quality issues explicit before building the curated layer.

## What is already clear

1. The dataset is synthetic and intentionally contains defects and inconsistencies.
2. The raw feeds are partitioned and written by date or extract date.
3. The dataset is large enough that we need to treat it as a warehouse-style analytical workload, not a single-table demo.
4. The legacy Finance weekly report is not a trusted source of truth; it is a comparison benchmark at best.
5. The dataset is designed to expose the exact kinds of problems a real distribution business encounters: duplicate rows, delayed arrivals, schema drift, missing data, and inconsistent vendor conventions.

## Known issue clusters from the shipped documentation

### POS feed
- At-least-once delivery means duplicate rows are expected.
- Event timestamps are recorded in UTC even though business activity is local to Asia/Kolkata.
- A schema drift event appears on a specific date; this means the feed changes shape across partitions.
- There are late-arriving rows (ingest date differs from event date).

### Reefer telemetry
- Two device vendors use different conventions.
- One vendor reports in Fahrenheit while the other reports in Celsius.
- Some rows have missing units.
- Some readings are null.
- One firmware line has a known clock offset.

### WMS scan events
- Handheld devices can buffer scans and sometimes drop the buffer.
- Cycle time calculations are therefore indicative rather than precise.

### ERP CDC
- Files are not sorted within a partition.
- Event semantics are tied to change operations: insert, update, delete.
- Current-state resolution requires taking the last record per key from the most recent file.
- Historical outlet and product attributes matter, but a point-in-time view is required.

## Phase 1 implementation intent

The first technical work is to inventory and profile the raw files so the project can proceed with evidence instead of assumptions.

### We will do the following
- enumerate all raw feed partitions and files
- inspect each parquet schema
- count rows per feed and partition
- capture field names and obvious schema drift
- document missing partitions and anomaly patterns
- record this information in a structured profiling report for later use in the curated layer and metric definitions

## Guardrail for the project

Any metric or dimension that relies on undocumented fields or assumptions must be explicitly recorded in the project decision log. We will not silently normalize or infer business meaning if the upstream contract is unclear.

## Phase 2 validation findings

- The expected-partitions manifest covers `pos_transactions`, `reefer_telemetry`, and `wms_scan_events`; it does not contain ERP CDC rows.
- The manifest contains 1,638 expected partitions, all of which have a matching directory in the three covered feeds.
- One telemetry Parquet file in `dt=2025-07-14` is unreadable. The partition has 7 readable files and 5,779 readable rows versus 8 files and 6,724 rows in the manifest, a 945-row deficit.
- The malformed file is not repaired or silently dropped. Downstream telemetry metrics must retain this known incompleteness as a quality limitation.

## Phase 3 dimension rules

- The fiscal calendar reference is the authority for fiscal labels; Gregorian date attributes are added without replacing its fiscal definitions.
- Outlet and product dimensions preserve effective-dated active versions from ERP CDC, ordered by `__op_ts` and then `__seq`. A delete closes the preceding active interval; the deleted state is not represented as an active dimension row.
- `dim_channel_history` records the initial observed channel and subsequent channel changes. Its intervals span unrelated outlet updates and end on the next channel change or outlet deletion.
- The UOM conversion reference is authoritative. Missing SKU conversions are kept null and explicitly flagged; `case_pack` is not used as a fallback conversion.
- Warehouse, carrier, and UOM references are static snapshots because no effective-dated history was supplied.
