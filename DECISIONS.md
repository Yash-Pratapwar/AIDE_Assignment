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

## Phase 4 decisions

### 20) Build order headers at CDC event-version grain
- Date: 2026-10-27
- Decision: Preserve every distinct order-header CDC version in `fact_sales_order_headers`, order versions by source sequence, mark the latest version per order, and retain delete tombstones with explicit flags.
- Context: The ERP feed contains order lifecycle updates and later hard deletes. Inspection showed delete rows reuse the insert's operation timestamp while carrying a later sequence and extract date; timestamp-only ordering misclassified all 2,880 delete rows as non-current.
- Alternatives considered:
  - Keep only current order headers
  - Drop delete events and their tombstone evidence
- Impact: Current-order analyses must filter on `is_latest_version` and exclude `is_deleted_current_order` where appropriate. Backwards operation timestamps are flagged for review.

### 21) Collapse only exact POS and telemetry duplicates
- Date: 2026-10-27
- Decision: Remove exact duplicate payloads from POS and telemetry facts, retain the number removed on each surviving row, and preserve/flag conflicting rows that share a business identifier.
- Context: At-least-once delivery is documented for POS and telemetry; data inspection found 84,000 duplicated POS key occurrences and exact payloads are the safe deduplication target.
- Alternatives considered:
  - Keep all duplicate deliveries in the analytical facts
  - Drop every repeated identifier, even when payload values conflict
- Impact: Fact row counts exclude exact retransmissions while traceability and ambiguity remain visible.

### 22) Normalize POS quantities and dates without inferring missing UOM
- Date: 2026-10-27
- Decision: Map both `qty` and the schema-drift field `quantity_units` to canonical quantity; convert event timestamps from UTC to `Asia/Kolkata`; calculate eaches only for recognized base units or supplied case conversions.
- Context: The POS schema changes across the feed and the pre-drift schema omits UOM. Inventing an unknown unit would make physical quantity totals unreliable.
- Alternatives considered:
  - Use ingest date as sale date
  - Assume missing UOM means eaches
  - Drop pre-drift records
- Impact: Pre-drift rows remain available with raw quantity but no derived eaches when the unit is unknown.

### 23) Normalize known telemetry conventions and expose incomplete source coverage
- Date: 2026-10-27
- Decision: Convert Fahrenheit to Celsius, infer null units only from the documented vendor convention, and correct the documented firmware `2.1.4` clock offset by seven hours. Exclude unreadable Parquet files from the fact only when explicitly listed in the build summary.
- Context: The generator explicitly describes these source defects; one telemetry file is unreadable and the prior manifest check measured a 945-row deficit for its partition.
- Alternatives considered:
  - Leave mixed units and known offset unnormalized
  - Silently ignore the corrupt file
  - Stop the entire fact build because of one corrupt partition
- Impact: Readable telemetry is queryable in normalized form, and the known incompleteness remains explicit for downstream metrics.

### 24) Treat WMS event timestamps as warehouse-local time
- Date: 2026-10-27
- Decision: Preserve the original WMS local timestamp and derive UTC using the warehouse timezone reference.
- Context: The feed contract says WMS `event_ts` is site local and the supplied warehouse reference provides timezone.
- Alternatives considered:
  - Interpret all WMS timestamps as UTC
  - Keep only the raw timestamp string
- Impact: Downstream cycle-time work can use consistent instants while retaining the source-local representation.

### 25) Do not invent telemetry trip or carrier keys
- Date: 2026-10-27
- Decision: Keep telemetry at timestamp-reading grain and do not infer a trip boundary or assign a carrier where the source provides no trip or carrier identifier.
- Context: Telemetry supplies device, vehicle, route, warehouse, and timestamp, but no authoritative trip ID or carrier ID.
- Alternatives considered:
  - Create trip groups from an arbitrary time gap or route/date combination
  - Guess carrier from route or vehicle
- Impact: Trip-level and carrier-level metrics require a separately agreed derivation or new source mapping.

### 26) Preserve both POS and ERP outlet-channel evidence
- Date: 2026-10-27
- Decision: Retain the POS captured channel and the channel-history value effective at sale time as separate fields, and flag mismatches rather than selecting one silently.
- Context: The built fact identifies 1,923,702 POS rows where the captured channel differs from the effective-dated ERP channel or the channel history is unavailable. The assignment describes channel changes and possible cross-system comparability issues.
- Alternatives considered:
  - Overwrite the POS value with ERP history
  - Treat the POS value as canonical and discard ERP history
- Impact: Phase 5 reconciliation must choose/document which channel definition supports each business question.

## Phase 5 decisions

### 27) Use POS transaction lines as the canonical sales grain and keep ERP orders non-additive
- Date: 2026-10-27
- Decision: Define the reconciled sales fact at deduplicated POS line grain; retain current ERP order-header values only as separate comparison evidence and never add them to POS sales.
- Context: POS and ERP order headers have no shared transaction/order key in the provided data. ERP records are order lifecycle snapshots, have delete tombstones, and one source system has a documented freight valuation issue; they do not represent a directly joinable invoice fact.
- Alternatives considered:
  - Add POS and ERP values together
  - Treat ERP order-header gross as an invoice/posted-sales fact
- Impact: Sales totals remain attributable to POS rows; ERP values can be compared without double counting or implying unsupported equivalence.

### 28) Define POS gross and net sales exclusive of tax
- Date: 2026-10-27
- Decision: Define gross sales as quantity times the tax-exclusive POS unit price before discounts; define net sales as gross less line discount, still before tax; retain tax as a separate amount.
- Context: The POS contract explicitly says unit price is exclusive of tax and discounts/tax are supplied as line-level fields.
- Alternatives considered:
  - Include tax in sales totals
  - Call gross-after-discount the gross measure
- Impact: Finance comparison must be labelled as a like-for-like check only if Finance confirms the same tax/discount convention.

### 29) Use POS-captured channel for sales attribution and retain ERP channel as a diagnostic
- Date: 2026-10-27
- Decision: Attribute POS revenue to the channel captured at the POS line; preserve ERP channel history separately and flag discrepancies.
- Context: POS carries a transaction-time captured channel, while ERP channel updates have major mismatches and no independently confirmed business rule for which system owns historical classification.
- Alternatives considered:
  - Replace POS channel with ERP effective-dated channel
  - Discard ERP channel evidence
- Impact: The fact remains traceable to the transactional source; channel-mismatch counts are exposed for business review.

### 30) Preserve sales rows with unresolved dimensions
- Date: 2026-10-27
- Decision: Keep valid, timestamped POS lines in the sales total even if an outlet/product/channel dimension lookup is unresolved; retain null dimension keys and quality flags.
- Context: Dimension history has key gaps. Excluding these rows without a business-approved policy would silently understate sales.
- Alternatives considered:
  - Filter unresolved rows out of sales totals
  - Assign a fabricated “unknown” master record
- Impact: Downstream reports should disclose unresolved-dimension counts and may show an explicit unknown member.

### 31) Interpret supplied Finance week labels as period starts and treat the report as a non-authoritative benchmark
- Date: 2026-10-27
- Decision: Treat each supplied `week_ending` value as the start of a seven-day half-open bucket for the comparison, and label all results with the original Finance week date.
- Context: The CSV dates are Wednesdays exactly seven days apart and the generator creates them from `DAYSTR[::7]`, so the column label “week_ending” does not describe the observed boundary.
- Alternatives considered:
  - Assume a conventional Sunday week end
  - Shift labels to a different weekday without source evidence
- Impact: Comparison windows are reproducible and the source label is retained; the interpretation is documented as a data-layout assumption.

### 32) Do not claim exact Finance reconciliation from independently generated report values
- Date: 2026-10-27
- Decision: Report event-date, ingest-date, and duplicate-inclusive POS counterfactuals, but do not claim they explain or reproduce the Finance numbers.
- Context: The generator comments assert ingest-date grouping and missing deduplication, but its actual Finance CSV writer populates gross sales, units, and baskets using independent random draws rather than source aggregates. The report also lacks a gross-sales definition for tax/discount treatment.
- Alternatives considered:
  - Treat the comment as proof that the emitted Finance values were calculated from POS
  - Tune an undocumented reconciliation until random values appear closer
- Impact: The published report remains a comparison benchmark; a true variance explanation requires the original Finance aggregation logic or a corrected report.

---

## Phase 6 decisions

### 33) Keep KPI logic in versioned SQL and materialize reusable result tables
- Date: 2026-10-27
- Decision: Store each Phase 6 metric query in `sql/06_kpis/` and use a small Python runner only to register curated inputs, execute SQL, and write Parquet outputs.
- Context: The project plan prioritizes SQL as the metric layer and requires queries to be reusable, testable, and runnable without interactive notebooks.
- Alternatives considered:
  - Embed metric logic in the runner
  - Provide isolated SQL that users must wire up manually
- Impact: Query definitions remain directly inspectable, while the runner gives users one command to produce a consistent KPI output set.

### 34) Keep unresolved sales dimensions visible rather than excluding valid POS lines
- Date: 2026-10-27
- Decision: Sales KPI queries exclude invalid timestamp and ambiguous line-key records, but keep valid POS lines with unresolved outlet/product dimensions and report those counts.
- Context: Dropping unresolved records would silently understate sales; the sales fact already preserves these rows and flags the lookup gaps.
- Alternatives considered:
  - Filter to fully resolved outlet and product records
  - Add synthetic unknown dimension members
- Impact: KPI totals remain traceable to valid POS evidence, with dimension coverage visible alongside them.

### 35) Define chilled excursion output as a vehicle-day proxy, not a trip or carrier rate
- Date: 2026-10-27
- Decision: Report the share of observed vehicle-days with at least one valid temperature reading above 8°C, grouped by month and warehouse; do not call it a trip or carrier rate.
- Context: Telemetry has no trip or carrier key. An observed vehicle-day is the narrowest reproducible grouping that does not invent trip boundaries. The feed contract specifically describes an excursion as a reading above the chilled upper bound.
- Alternatives considered:
  - Infer trips from arbitrary time gaps
  - Attribute telemetry to carriers using route or vehicle guesses
  - Report a reading-level rate as if it were a trip rate
- Impact: The output is useful for diagnostic trend analysis but is not interchangeable with excursion rate per actual trip. Readings below 2°C are separately visible but do not enter the upper-bound numerator.

### 36) Treat receive-to-dispatch and on-time dispatch as operational proxies
- Date: 2026-10-27
- Decision: Provide an exploratory receive-to-later-dispatch scan interval and a dispatched-order on-time-dispatch proxy, explicitly separate from validated warehouse cycle time and delivery service level.
- Context: The generator assigns WMS scan stage, order, and day independently, omits approximately 6.5% of events, and the feeds contain no delivery scan or confirmed service target.
- Alternatives considered:
  - Present scan-based intervals and dispatch timing as definitive KPIs
  - Omit all operational queries despite the assignment's core questions
- Impact: Queries and coverage measures are available for review, but proxy results must not be reported as true lifecycle performance until the source data semantics are corrected.

### 37) Use manifest validation findings as the missing-day KPI input
- Date: 2026-10-27
- Decision: The missing-data query reads partition issues from the Phase 2 validation report instead of comparing curated fact row counts with raw manifest row counts.
- Context: Exact duplicates are removed from curated POS/telemetry facts and one unreadable telemetry file is explicitly excluded, so curated row counts are not directly comparable to raw manifest expectations.
- Alternatives considered:
  - Compare deduplicated fact counts with raw manifest counts
  - Re-read every raw partition inside the KPI query
- Impact: The KPI reports known raw partition/file defects without conflating them with downstream deduplication.

### 38) Keep source-system order values unadjusted and non-comparable
- Date: 2026-10-27
- Decision: Report current ERP order values by source system with the known Partner API caveat, but do not adjust or rank systems as comparable accounting values.
- Context: Finance documented an unresolved valuation difference for one source system and supplied no validated correction.
- Alternatives considered:
  - Apply an estimated adjustment
  - Treat all source-system values as directly comparable
- Impact: The query is descriptive diagnostic evidence; a reconciliation requires an approved valuation rule.

## Phase 7 decisions

### 39) Treat operational quality checks as a required guardrail for any KPI interpretation
- Date: 2026-10-28
- Decision: Phase 7 is not optional reporting hygiene. The project must surface duplicate counts, telemetry anomalies, missing WMS stage transitions, date-range drift, and incomplete reference rows before a KPI can be treated as dependable.
- Context: The assignment explicitly states that the ask-anything capability requires knowing whether the feed is trustworthy and what is missing. A KPI without a quality story is not ready for decision-making.
- Alternatives considered:
  - Skip explicit quality checks and rely on aggregate KPI outputs alone
  - Add quality checks only after all metrics are complete
- Impact: Business users can distinguish a number from a trusted number, and suspected data issues are preserved in the analytical layer.

### 40) Keep duplicate and anomaly logic tied to the raw fact semantics, not to a generic “bad row” bucket
- Date: 2026-10-28
- Decision: Duplicate rows are captured per feed and anomaly conditions are reported with their specific type (`temperature_out_of_band`, `missing_temperature`, `unit_unresolved`, `missing_intermediate_stage`, etc.), rather than collapsing them into one catch-all flag.
- Context: Different feeds have different failure modes. A single generic quality flag would hide the diagnostic value of the check and make a user unable to know what needs attention.
- Alternatives considered:
  - One count-only quality score per feed
  - Silent filtering of anomalous rows without preserving the evidence
- Impact: Quality outputs remain actionable, auditable, and traceable to underlying rows and source defects.

### 41) Use incomplete reference dimensions as an explicit quality issue, not a hidden fallback
- Date: 2026-10-28
- Decision: Missing warehouse, outlet, carrier, and product master rows are surfaced in the quality layer and counted as reference incompleteness rather than being filled with synthetic labels or silently ignored.
- Context: The data generator confirms that some reference rows can be missing or incomplete, and downstream analytics should never claim a full dimension coverage if the source is incomplete.
- Alternatives considered:
  - Auto-fill unknown dimensions
  - Drop records with missing master references
- Impact: Data health output tells business users whether metric output is limited by incomplete reference coverage.

### 42) Keep the Phase 7 output distinct from Phase 6 metric outputs
- Date: 2026-10-28
- Decision: Quality checks are executed separately in `sql/07_quality/` and written to `curated/quality/`, with dedicated summary metadata. They are not folded into the KPI result tables.
- Context: The quality layer is meant to answer a different business question: “is this signal trustworthy?” rather than “what is the metric value?”
- Alternatives considered:
  - Merge quality and KPI outputs into one table
  - Store quality data only as ad hoc Python logs
- Impact: The repository preserves a clean separation between metric logic and operational controls.

## Phase 8 decisions

### 43) Make the final business-definition layer a first-class deliverable
- Date: 2026-10-28
- Decision: Implement a single KPI catalogue document that records each metric's definition, grain, filters, source feeds, calculation logic, owner, limitations, and assumptions.
- Context: The project plan requires a single stakeholder-facing registry and the repository already contains the underlying SQL. The metric layer without a business-definition layer is not fully reviewable.
- Alternatives considered:
  - Treat the SQL file names as the catalogue
  - Keep the README and decisions as the only documentation layer
- Impact: Business users have a single source of truth for the definition and caveats behind each metric.

### 44) Separate KPI definitions from operational quality alerts
- Date: 2026-10-28
- Decision: The catalogue includes both business KPI definitions and the Phase 7 operational quality summary, but keeps them explicitly separated in the documentation and execution structure.
- Context: KPI values answer “what is the number?”, while quality checks answer “is the number trustworthy?”. Both are important, but they must not be conflated.
- Alternatives considered:
  - Fold every quality metric into the KPI catalogue without distinction
  - Omit quality checks from the final business-definition layer
- Impact: The repository preserves the distinction between metric output and confidence checks.

### 45) Use business ownership in the catalogue instead of technical ownership only
- Date: 2026-10-28
- Decision: Each metric is assigned a business owner or operational owner, such as Finance, Logistics, or Data Quality, instead of only a technical file owner.
- Context: The assignment specifically asks for ownership metadata and business-context understanding, not just technical documentation.
- Alternatives considered:
  - List only data-engineering owners
  - Omit owner metadata altogether
- Impact: The catalogue supports stakeholder conversations and review of metric trustworthiness.

### 46) Treat known limitations as part of the metric surface, not as hidden footnotes
- Date: 2026-10-28
- Decision: Every metric entry documents its known limitations and assumptions, including source defects, missing data, and proxy logic where a true business KPI is unavailable.
- Context: Several metrics are explicitly proxy or partial measures, and the project plan requires those caveats to be written down clearly.
- Alternatives considered:
  - Only document the happy-path metric logic
  - Keep limitations in code comments instead of the catalogue
- Impact: Users can interpret the outputs responsibly and avoid overstating the quality of proxy KPIs.

### 47) Complete the final documentation layer and mark Phase 8 as done
- Date: 2026-10-28
- Decision: The repository now includes the final `KPI_CATALOGUE.md` and the infrastructure documentation directly references it; this closes the Phase 8 documentation requirement.
- Context: The assignment required a complete repo-level analytical foundation with query library, metrics, quality checks, and documentation. The catalogue is now present and the decision log reflects the final state.
- Alternatives considered:
  - Declare documentation complete without a business registry
  - Leave a partial catalogue and continue claiming the project is final
- Impact: The repository meets the stated Phase 8 exit criteria: stakeholders can read one place to understand what was built, what it means, and where the logic remains limited.

### 48) Treat catalogue owners as proposed functions until stakeholders confirm accountability
- Date: 2026-10-28
- Decision: Assign business functions as provisional owners in the KPI catalogue; do not present them as approved or named Kestrel owners.
- Context: The assignment data and repository do not identify accountable people or provide governance sign-off evidence.
- Alternatives considered:
  - Invent named owners
  - Omit owner metadata despite the Phase 8 requirement
- Impact: The catalogue has usable role-level ownership proposals while clearly identifying stakeholder confirmation as a remaining governance action.

### 49) Validate the complete pipeline in dependency order and preserve known defects as findings
- Date: 2026-10-28
- Decision: Run manifest validation, dimensions, facts, sales, KPI queries, and quality checks sequentially against the supplied data; record actual outcomes and do not treat known manifest defects as a clean pass.
- Context: Unit tests validate query logic on fixtures but do not prove the end-to-end pipeline operates against the supplied multi-feed data.
- Alternatives considered:
  - Rely only on unit tests
  - Skip known-bad source files without carrying the quality finding forward
- Impact: Final readiness claims are based on generated outputs and observed counts, with source incompleteness retained as an explicit limitation.

## Current status

The project has implemented Phases 1-8. The end-to-end run completed on 2026-10-28; the pipeline ran successfully with the expected known source-quality findings listed below.

### End-to-end validation evidence (2026-10-28)

- Manifest validation found 1,638 expected and 1,638 actual manifest-scoped partitions, with no missing partitions. It reported one telemetry partition mismatch and one unreadable telemetry Parquet file: `reefer_telemetry/dt=2025-07-14`, 5,779 readable rows versus 6,724 expected (945 rows short). The manifest summary counts the mismatch and unreadable file as two issue records for the same partition.
- Phase 3 built 546 date rows, 8,640 outlet versions, 3,520 product versions, 8 warehouses, 5 carriers, 7,095 channel-history rows, and 1,054 UOM conversions.
- Phase 4 built 4,000,000 POS rows, 3,598,770 telemetry rows, 1,496,000 WMS scan rows, and 963,307 order-header versions. It removed 84,000 exact POS duplicates and 115,156 exact telemetry duplicates; one unreadable telemetry file was explicitly excluded.
- Phase 5 built 4,000,000 reconciled sales rows and 378 Finance week/channel comparisons. Event-date POS gross sales were INR 5,508,198,259.46. The Finance figures remain an independent synthetic benchmark and are not claimed as reconciled.
- Phase 6 produced all eight KPI outputs: 72 gross-sales rows, 72 units rows, 152 chilled vehicle-day rows, 144 warehouse cycle-time rows, 144 service-proxy rows, 4,695 channel-change rows, one missing-data partition row, and three source-system order-value rows.
- Phase 7 produced all six quality outputs. The summary flagged 199,156 removed duplicates, 988,211 telemetry anomaly rows, 237,870 order/warehouse groups with missing WMS stages, two manifest issue records, one feed outside the date-dimension range, and zero incomplete reference rows. The out-of-range feed is telemetry, whose corrected reading date reaches 2026-07-01 while `dim_date` ends 2026-06-30.
- `python -m unittest discover -s tests -q` passed all 12 tests after the pipeline and quality-runner corrections.
- All build summaries and the manifest report were regenerated under `curated/` and `docs/manifest_validation.json`. The raw assignment data was read-only.

The pipeline completed successfully, but the data is not clean: those quality findings and the explicitly documented KPI proxy limitations remain material. The business-function owners in the catalogue are proposals pending stakeholder confirmation, not approved accountable owners.

The following artifacts are now in place:
- [README.md](./README.md)
- [DECISIONS.md](./DECISIONS.md)
- [KPI_CATALOGUE.md](./KPI_CATALOGUE.md)
- [docs/assumptions.md](./docs/assumptions.md)
- [docs/sales_reconciliation_findings.md](./docs/sales_reconciliation_findings.md)
- [pipeline/profile_raw.py](./pipeline/profile_raw.py)
- [pipeline/validate_manifest.py](./pipeline/validate_manifest.py)
- [pipeline/build_dimensions.py](./pipeline/build_dimensions.py)
- [pipeline/build_facts.py](./pipeline/build_facts.py)
- [pipeline/build_sales.py](./pipeline/build_sales.py)
- [pipeline/run_kpis.py](./pipeline/run_kpis.py)
- [pipeline/run_quality.py](./pipeline/run_quality.py)
- [sql/05_reconciliation/fact_reconciled_sales.sql](./sql/05_reconciliation/fact_reconciled_sales.sql)
- [sql/05_reconciliation/sales_reconciliation_finance.sql](./sql/05_reconciliation/sales_reconciliation_finance.sql)
- [sql/06_kpis/](./sql/06_kpis/)
- [sql/07_quality/](./sql/07_quality/)
- [tests/test_build_dimensions.py](./tests/test_build_dimensions.py)
- [tests/test_sales_reconciliation.py](./tests/test_sales_reconciliation.py)
- [tests/test_kpi_queries.py](./tests/test_kpi_queries.py)
- [tests/test_quality_queries.py](./tests/test_quality_queries.py)
- [docs/raw_profile.json](./docs/raw_profile.json)
- [docs/manifest_validation.json](./docs/manifest_validation.json)
- [curated/facts/build_summary.json](./curated/facts/build_summary.json) (generated locally; not tracked)
- [curated/sales/build_summary.json](./curated/sales/build_summary.json) (generated locally; not tracked)
- [curated/kpis/build_summary.json](./curated/kpis/build_summary.json) (generated locally; not tracked)
- [curated/quality/build_summary.json](./curated/quality/build_summary.json) (generated locally; not tracked)

This decisions log is now being used as the formal place to record project decisions going forward.

---

## Forward decisions to log

From this point forward, new decisions should be added here in the same pattern, with a date and explicit rationale. Major design choices, metric definition choices, source-of-truth decisions, and quality-policy decisions should all be logged here.
