# Decision Log

This document records the key product, data, and implementation decisions made during the analytical foundation build. The goal is to keep assumptions explicit and traceable so later metric logic and data-model decisions can be reviewed against the original reasoning.

## Decision logging standard

For each new decision, record:
- Date
- Decision
- Context / why it matters
- Alternatives considered
- Impact on downstream work
- Owner / author (project context)

Whenever a decision is revised, capture the new decision and the reason for the change instead of overwriting the original decision silently.

---

## Phase 1 decisions

### 1) Treat the legacy Finance weekly report as a comparison benchmark, not the source of truth
- Date: 2026-10-27
- Decision: The legacy weekly report is not authoritative for final KPI reconciliation. It is a benchmark for comparison only.
- Context: The assignment brief explicitly says this report is a comparison point and not the truth. The upstream synthetic feeds are the primary evidence base.
- Alternatives considered:
  - Use Finance report as a canonical sales source
  - Blend legacy and raw data without clear weighting
- Impact: The project will prioritize row-level raw feed logic and explicit business assumptions over a single downstream summary file.

### 2) Use raw feed profiling as the initial execution focus before building transformations
- Date: 2026-10-27
- Decision: Phase 1 is a profiling and discovery phase, not a full metric build.
- Context: The project requires understanding feed shape, partitions, schema drift, and data quality risks before making metric assumptions.
- Alternatives considered:
  - Jump directly into building dimension/fact tables
  - Write KPI logic without validating the feed contracts
- Impact: The project begins with a raw inventory and schema-risk assessment to reduce false assumptions in later layers.

### 3) Treat the raw dataset as a warehouse-style analytical workload with expected defects
- Date: 2026-10-27
- Decision: The supplied synthetic data should be handled as a realistic operational dataset with duplicates, missing data, clock offsets, late arrivals, schema drift, and inconsistent vendor conventions.
- Context: Documentation explicitly warns about duplicate rows, missing units, late-arriving POS rows, telemetry calibration issues, and ERP CDC semantics.
- Alternatives considered:
  - Assume the data is clean enough for direct analytics
  - Ignore quality defects until later in the pipeline
- Impact: The project will plan for validation and anomaly handling rather than “happy-path” transformations.

### 4) Build a small working system over a large half-working one
- Date: 2026-10-27
- Decision: Prioritize a minimal but credible implementation that supports core KPI logic and traceability rather than an overbuilt architecture.
- Context: The project plan explicitly prioritizes a small working foundation and a layered architecture.
- Alternatives considered:
  - Broad, ambitious architecture with many speculative features
  - A narrow, non-traceable demo without source-to-metric lineage
- Impact: The implementation will focus on core feed validation, dimension/fact basics, and a small set of credible KPIs.

### 5) Keep source-to-metric lineage explicit
- Date: 2026-10-27
- Decision: Metrics must be traceable back to raw rows and explicit business logic, not inferred from a summary table or a single benchmark.
- Context: The goal is to preserve auditability and explainability in the analytical foundation.
- Alternatives considered:
  - Metric definitions built from aggregated outputs only
  - Assumed business semantics without source evidence
- Impact: Each later metric should be documented with definition, source fields, and reconciliation logic.

### 6) Record uncertainty and assumption gaps in writing
- Date: 2026-10-27
- Decision: Any ambiguous field meaning or contract mismatch must be captured in documentation instead of silently normalized.
- Context: The brief notes that some feed-contract statements are wrong or incomplete, and the project wants to preserve known ambiguities.
- Alternatives considered:
  - Ignore ambiguous contracts and proceed with assumptions
  - Encode undocumented logic without noting the risk
- Impact: The project will maintain an explicit assumption log and update it when evidence changes.

### 7) Use SQL as the main metric logic, and Python for orchestration and validation
- Date: 2026-10-27
- Decision: Business logic should primarily live in SQL queries, while Python handles file discovery, validation, and pipeline orchestration.
- Context: The project plan states SQL is the main metric logic and Python mainly handles orchestration and validation.
- Alternatives considered:
  - Implement metric logic in Python alone
  - Build a complex ETL framework before confirming validation needs
- Impact: The pipeline architecture will stay simple and favor analytical queries over procedural transformation logic.

### 8) Data quality and completeness checks are part of the core scope, not an afterthought
- Date: 2026-10-27
- Decision: The assignment is not only about KPI logic; it requires explicit validation for missing dates, missing partitions, row-count drift, malformed files, and incomplete source histories.
- Context: The project plan stresses that missing data and incomplete days are part of the problem to solve.
- Alternatives considered:
  - Assume feeds are complete after a basic file inventory
  - Ignore missing-data risk until the metric layer is built
- Impact: Validation checks become a prerequisite to downstream metric confidence.

### 9) The raw source feeds are not all equally trustworthy; vendor-specific issues must be called out
- Date: 2026-10-27
- Decision: Feed quality issues are source-specific and should be acknowledged separately per feed rather than treated as one generic data-quality issue.
- Context: POS, reefer telemetry, WMS, and ERP CDC each carry different known problems.
- Alternatives considered:
  - Treat all feeds as uniformly reliable
  - Hide vendor-specific issues behind general “data quality” language
- Impact: Each feed will need tailored validation and transformation rules.

### 10) Phase 1 is intentionally a foundation phase; later phases will refine the final metric definitions
- Date: 2026-10-27
- Decision: The specific final KPI business definitions will be finalized only after raw data and contract inspection are complete.
- Context: The project plan states that metric definitions will be built after understanding source semantics and assumptions.
- Alternatives considered:
  - Lock metric definitions before inspecting raw data
  - Treat the initial assumptions as final definitively
- Impact: The project maintains a disciplined progression from raw evidence to metric definition.

---

## Phase 2 decisions

### 11) Treat manifest validation as a required gate before transformation work
- Date: 2026-10-27
- Decision: The raw landing zone must be validated against the manifest before any curated-layer or KPI work is considered reliable.
- Context: The validation run identified a specific partition-level mismatch and a corrupt parquet file in the reefer telemetry feed.
- Alternatives considered:
  - Ignore manifest drift because the data appears mostly complete
  - Continue building dimensions while unresolved raw defects remain
- Impact: All downstream work must treat raw-quality defects as real project risks rather than abstract future issues.

### 12) A single malformed parquet file is a material data-quality defect, not a harmless edge case
- Date: 2026-10-27
- Decision: The file in the reefer telemetry partition `dt=2025-07-14` is treated as a real data-quality failure and must be documented and investigated before downstream metric logic uses that day.
- Context: The file is unreadable by pyarrow and causes a row-count deficit of 945 rows compared with the manifest expectation.
- Alternatives considered:
  - Skip the bad partition silently
  - Assume the missing rows are negligible and continue
- Impact: Data completeness checks will need to call out missing or failed partitions explicitly and either quarantine or review them.

### 13) Manifest structure for ERP CDC needs a careful interpretation
- Date: 2026-10-27
- Decision: ERP CDC is not covered by the supplied expected-partitions manifest; it is organized into source-table directories (`outlet_master`, `product_master`, `sales_order_header`).
- Context: The manifest feed values contain only POS, telemetry, and WMS. The earlier validator incorrectly compared ERP table directories to manifest partitions.
- Alternatives considered:
  - Report ERP source-table directories as missing manifest partitions
  - Silently claim ERP CDC has been validated by the manifest
- Impact: ERP CDC must be checked for readable Parquet files and valid CDC operations independently of the manifest.

### 14) Correct the Phase 2 validator's manifest scope
- Date: 2026-10-27
- Decision: Compare actual partitions only for feeds represented in the manifest, and report unmanifested raw feed directories separately.
- Context: The first report counted the three ERP CDC table directories as extra partitions, producing a misleading actual-partition count of 1,641. The corrected report compares 1,638 manifest partitions against 1,638 actual manifest-scoped partitions.
- Alternatives considered:
  - Keep the misleading count and describe it as an ERP partition mismatch
  - Remove ERP CDC discovery without disclosing its manifest coverage gap
- Impact: Phase 2 findings now distinguish manifest coverage from the separate ERP CDC source-table layout.

## Phase 3 decisions

### 15) Use the supplied fiscal calendar as the authority for fiscal attributes
- Date: 2026-10-27
- Decision: Enrich the supplied fiscal calendar with Gregorian date fields, but do not recalculate or replace its fiscal year, quarter, fiscal month, or ISO week values.
- Context: Fiscal periods are business-defined and already supplied; rebuilding them would introduce an unnecessary competing definition.
- Alternatives considered:
  - Derive fiscal periods independently from calendar dates
  - Keep only the supplied fields and omit useful date attributes
- Impact: All downstream date joins should use `date_key` or `calendar_date` from `dim_date`.

### 16) Build outlet and product dimensions as effective-dated CDC histories
- Date: 2026-10-27
- Decision: Order CDC history by `__op_ts` and then `__seq`, collapse same-key/same-timestamp ties to the highest sequence, and emit active insert/update states with half-open effective intervals; delete events close the preceding active interval.
- Context: The data generator documents out-of-order extract arrival and same-timestamp CDC ties. Latest file arrival is not a valid state-resolution rule.
- Alternatives considered:
  - Resolve current state by latest extract date
  - Keep only one current row per business key
- Impact: Historical outlet/product attributes remain queryable. Deleted keys have no active row after the deletion timestamp.

### 17) Track channel history only at channel boundaries
- Date: 2026-10-27
- Decision: Include the initial observed channel and create later channel-history rows only when the channel value changes. Intervals span unrelated outlet attribute updates and close at the next channel change or outlet deletion.
- Context: Outlet CDC updates multiple attributes, but users need an accurate answer to the channel-as-of-date question without artificial gaps.
- Alternatives considered:
  - Mirror every outlet dimension version into channel history
  - Keep only each outlet's current channel
- Impact: `dim_channel_history` is a compact, effective-dated lookup for historical classification.

### 18) Do not infer missing UOM conversions from product case pack
- Date: 2026-10-27
- Decision: The supplied UOM conversion reference is authoritative. Missing conversions remain null and are marked with `uom_conversion_available = false`; product `case_pack` is retained as a separate master attribute.
- Context: The conversion reference intentionally omits some SKUs, and treating case pack as an equivalent conversion without validation would conceal the data gap.
- Alternatives considered:
  - Infer eaches-per-case from product case pack
  - Drop products without a conversion
- Impact: Downstream unit metrics must explicitly handle the flagged missing conversions.

### 19) Treat warehouse, carrier, and UOM references as static snapshots
- Date: 2026-10-27
- Decision: Load the supplied warehouse and carrier master files as static dimensions and attach the static UOM mapping to product versions.
- Context: No effective-dated history was provided for these references.
- Alternatives considered:
  - Invent effective dates for reference changes
  - Omit these reference tables
- Impact: Historical changes to these attributes cannot be reconstructed until source history is supplied.

---

## Current status

The project has completed Phase 3: canonical dimensions and reference tables.

The following artifacts are already in place:
- [README.md](./README.md)
- [DECISIONS.md](./DECISIONS.md)
- [docs/assumptions.md](./docs/assumptions.md)
- [pipeline/profile_raw.py](./pipeline/profile_raw.py)
- [pipeline/validate_manifest.py](./pipeline/validate_manifest.py)
- [pipeline/build_dimensions.py](./pipeline/build_dimensions.py)
- [tests/test_build_dimensions.py](./tests/test_build_dimensions.py)
- [docs/raw_profile.json](./docs/raw_profile.json)
- [docs/manifest_validation.json](./docs/manifest_validation.json)

This decisions log is now being used as the formal place to record project decisions going forward.

---

## Forward decisions to log

From this point forward, new decisions should be added here in the same pattern, with a date and explicit rationale. Major design choices, metric definition choices, source-of-truth decisions, and quality-policy decisions should all be logged here.
