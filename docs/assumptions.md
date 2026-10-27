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

## Phase 4 fact rules

- POS uses the event timestamp as UTC and derives the business timestamp/date in `Asia/Kolkata`. Both `qty` and the post-drift `quantity_units` field map to the canonical quantity.
- POS, WMS, telemetry, and order-header rows retain source file path and source row number. Exact duplicate rows are collapsed only in POS and telemetry, with the removed-duplicate count retained on the surviving fact row. Conflicting records with the same business key are preserved and flagged.
- POS eaches are calculated directly for `EA`, and `CS` quantities use the supplied SKU conversion. Missing UOM is not imputed; a case quantity without a conversion remains unconverted.
- The order-header fact is CDC event-version grain. It retains all insert/update/delete events, orders versions by source sequence, marks the latest event per order, and flags latest delete tombstones. `PARTNER_API` values are flagged but not adjusted.
- Order-header delete rows reuse the insert's `__op_ts` while their extract partition and `__seq` are later. Therefore source sequence, not operation timestamp, determines latest order state; backwards operation timestamps are retained and flagged.
- WMS `event_ts` is interpreted in the static warehouse timezone; both source-local and UTC timestamps are retained.
- Telemetry Fahrenheit is converted to Celsius. A missing unit is inferred from the documented vendor convention only. Firmware `2.1.4` timestamps are shifted back seven hours based on the generator's explicit defect description.
- The unreadable telemetry Parquet file in `dt=2025-07-14` is excluded from the fact build and listed in its build summary. This fact is incomplete by at least the already observed 945-row manifest shortfall; raw data remains unchanged.
- The feed does not provide a carrier identifier or a reliable trip identifier. Neither is manufactured in the timestamp-grain telemetry fact.
- The fiscal date dimension ends at 2026-06-30; telemetry readings whose corrected local date is 2026-07-01 retain a null `date_key` instead of receiving a fabricated fiscal date.
- The POS captured channel is preserved alongside effective-dated ERP channel history. A mismatch is flagged, not overwritten, because the two sources can disagree.

## Phase 5 sales definition and reconciliation

- The POS transaction line is the canonical sales grain. The assignment has no reliable POS-to-ERP order key and no invoice fact; ERP order headers are retained as a separate non-additive comparator, not added to POS sales.
- `gross_sales_ex_tax_inr` is quantity times POS unit price before discount; `net_sales_ex_tax_inr` subtracts line discount. Tax is separate because the POS contract says unit price is tax-exclusive.
- For channel attribution, use the POS channel captured on each line. Keep ERP channel history separately as a diagnostic; do not overwrite either source.
- Retain POS lines with unresolved outlet/product/channel dimensions and flag them, avoiding unreviewed exclusions from sales totals.
- Finance report `week_ending` values are Wednesdays spaced seven days apart, generated from `DAYSTR[::7]`. The supplied label is treated as the start of a seven-day half-open comparison period. The source does not define whether gross sales include tax or discounts.
- The generator comments say Finance groups by ingest date and does not deduplicate, but the code that writes the Finance CSV uses independent random gross/unit/basket values instead of aggregating source records. Event-date, ingest-date, and duplicate-inclusive comparisons are diagnostic counterfactuals, not an exact reproduction of the published report.
