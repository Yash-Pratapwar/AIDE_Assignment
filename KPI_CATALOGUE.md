# KPI Catalogue

This catalogue documents the business-definition layer for the Kestrel Provisions analytical foundation. It is intended to answer: what is the metric, how is it defined, what sources produce it, what exclusions apply, and what caveats remain.

The catalogue complements the SQL library in `sql/05_reconciliation/` and `sql/06_kpis/` and the operational guardrails in `sql/07_quality/`.

## Metric registry

### 1) Gross sales by channel
- Metric name: `gross_sales_by_channel`
- Business definition: Total gross sales value by sales channel for a fiscal period, reported in INR exclusive of tax.
- Grain: fiscal period, sales channel
- Filters and exclusions:
  - valid sale timestamps only
  - reject ambiguous transaction-line keys
  - retain unresolved outlet/product dimension rows but flag them
  - exclude rows with invalid timestamps or ambiguous IDs
- Source feeds:
  - `fact_reconciled_sales`
  - `dim_date`
- Calculation logic:
  - sum `gross_sales_ex_tax_inr` for each fiscal period and channel
  - use the POS-captured channel as the transaction attribution basis
- Output query: `sql/06_kpis/gross_sales_by_channel.sql`
- Owner: Commercial Finance / Revenue Analytics
- Known limitations:
  - channel mismatch flags remain visible for downstream review
  - unresolved dimension rows are retained but not silently cleaned
- Assumptions and edge cases:
  - gross sales remain exclusive of tax by contract definition
  - ERP channel history is treated as diagnostic rather than replacement for POS channel

### 2) Units sold (eaches)
- Metric name: `units_sold_eaches`
- Business definition: Total physical items sold, normalized to eaches after UOM conversion when available.
- Grain: fiscal period, sales channel
- Filters and exclusions:
  - valid timestamps and non-ambiguous line keys only
  - do not infer missing UOM conversion from product case-pack
- Source feeds:
  - `fact_reconciled_sales`
  - `dim_date`
- Calculation logic:
  - sum `quantity_eaches` by fiscal period and channel
  - record rows whose UOM conversion is missing as a coverage warning
- Output query: `sql/06_kpis/units_sold_eaches.sql`
- Owner: Commercial Finance / Supply Planning
- Known limitations:
  - some SKUs have no UOM conversion reference
  - physical units remain incomplete where conversion is absent
- Assumptions and edge cases:
  - unit normalization is done only using the supplied conversion table
  - undetermined UOM is not converted by assumption

### 3) Sales reconciliation versus legacy Finance report
- Metric name: `sales_reconciliation_finance`
- Business definition: Compare reconciled POS sales to the board-published Finance week report by week and channel, while keeping event-date, ingest-date, and duplicate-inclusive counterfactuals visible.
- Grain: Finance week label, channel
- Filters and exclusions:
  - compare to the supplied legacy Finance report as benchmark only
  - keep event-date and ingest-date views separate
  - report current ERP order evidence as a separately bounded comparison, not additive sales
- Source feeds:
  - `fact_reconciled_sales`
  - `legacy_finance_weekly_report.csv`
  - ERP order-header fact for non-additive evidence
- Calculation logic:
  - aggregate reconciled POS sales to the Finance week/channel key
  - calculate variance between event-date deduplicated sales and Finance totals
  - add ingest-date and duplicate-inclusive counterfactual metrics
- Output query: `sql/05_reconciliation/sales_reconciliation_finance.sql`
- Owner: Finance / FP&A
- Known limitations:
  - the Finance CSV is generated independently and cannot be numerically reconciled to underlying source rows
  - the report is not the source of truth
- Assumptions and edge cases:
  - the board report is treated as a benchmark, not as the authoritative ledger
  - no exact proof of the Finance logic is available from the generator output alone

### 4) Chilled excursion rate (vehicle-day proxy)
- Metric name: `chilled_excursion_vehicle_day`
- Business definition: Share of observed vehicle-days with at least one valid temperature reading above the chilled upper bound (8°C), by month and warehouse.
- Grain: reading month, warehouse, observed vehicle-day
- Filters and exclusions:
  - valid timestamps only
  - exclude ambiguous telemetry keys
  - exclude missing or unresolved unit values from the excursion numerator
- Source feeds:
  - `fact_reefer_telemetry`
  - `dim_date`
- Calculation logic:
  - group by warehouse, vehicle registration, and calendar day
  - count valid readings and identify whether any reading is > 8°C
  - divide by observed vehicle-day count
- Output query: `sql/06_kpis/chilled_excursion_vehicle_day.sql`
- Owner: Logistics / Cold Chain Operations
- Known limitations:
  - not a trip-level rate because trip IDs are absent from source data
  - no carrier or route-level assignment is available for a true carrier SLA rate
- Assumptions and edge cases:
  - the metric is a documented vehicle-day proxy, not a production trip KPI
  - lower-bound excursions (<2°C) are visible but not part of the numerator for this upper-bound rule

### 5) Warehouse receive-to-dispatch cycle time
- Metric name: `warehouse_receive_to_dispatch`
- Business definition: Observe the time from the first valid receive scan to the next valid dispatch scan for each order, aggregated by warehouse and month.
- Grain: warehouse, month
- Filters and exclusions:
  - valid WMS timestamps only
  - exact duplicate scan IDs removed earlier
  - orders without a later dispatch scan remain visible as coverage gaps
- Source feeds:
  - `fact_wms_scan_events`
- Calculation logic:
  - locate each order's earliest receive timestamp
  - find the next dispatch timestamp later than the receive timestamp
  - calculate the interval in hours and aggregate median and p90 by warehouse/month
- Output query: `sql/06_kpis/warehouse_receive_to_dispatch.sql`
- Owner: Warehouse Operations / Fulfilment
- Known limitations:
  - WMS event coverage is partial; approximately 6.5% of events are missing by design
  - the generator does not guarantee a complete lifecycle sequence
- Assumptions and edge cases:
  - this is an exploratory cycle-time proxy rather than a validated end-to-end operation measure

### 6) Dispatch service-level proxy
- Metric name: `dispatch_service_level_proxy`
- Business definition: Share of currently dispatched orders with a dispatch scan and percentage dispatched by the requested delivery date, grouped by warehouse and month.
- Grain: warehouse, month
- Filters and exclusions:
  - current latest-version, non-deleted orders only
  - orders must have a requested_delivery_date and dispatch status
  - dispatch scan presence is evaluated separately from the date target
- Source feeds:
  - `fact_sales_order_headers`
  - `fact_wms_scan_events`
- Calculation logic:
  - identify latest valid order records in DISPATCHED state
  - join the earliest dispatch scan for each order and warehouse
  - calculate scan coverage and a proxy on-time dispatch rate
- Output query: `sql/06_kpis/dispatch_service_level_proxy.sql`
- Owner: Customer Service / Distribution Planning
- Known limitations:
  - this is a proxy only; no definitive delivery scan or service-level SLA table is supplied
  - WMS scan coverage has known gaps
- Assumptions and edge cases:
  - the metric is presented as diagnostic operational insight, not an audited SLA result

### 7) Outlet channel changes
- Metric name: `outlet_channel_changes`
- Business definition: List each outlet's channel history changes with the date the channel changed and the previous/new channel values.
- Grain: outlet, effective date
- Filters and exclusions:
  - use effective-dated `dim_channel_history`
  - show changes only where previous and new channel differ
- Source feeds:
  - `dim_channel_history`
- Calculation logic:
  - read interval boundaries from outlet channel-history records
  - emit only the rows where the active channel changed
- Output query: `sql/06_kpis/outlet_channel_changes.sql`
- Owner: Sales Operations / Master Data
- Known limitations:
  - channel history reflects ERP master evolution; it is not guaranteed to match POS-captured channel values exactly
- Assumptions and edge cases:
  - the channel history is built from effective-dated ERP CDC and is a time-aware classification view, not an immutable POS truth

### 8) Missing data days
- Metric name: `missing_data_days`
- Business definition: Feed partitions with missing or unreadable data, reported by feed and partition, along with issue details and row-count deltas.
- Grain: feed, partition
- Filters and exclusions:
  - reads partition issues from the manifest validation report
  - retains mismatch, missing-partition, unmanifested-partition, and unreadable-file issues
- Source feeds:
  - `manifest_partition_issues` table built from `docs/manifest_validation.json`
- Calculation logic:
  - aggregate all issue rows by feed and partition
  - display expected vs actual row counts and file counts
- Output query: `sql/06_kpis/missing_data_days.sql`
- Owner: Data Quality / Platform Engineering
- Known limitations:
  - it reports raw source-quality issues, not curated fact defects
  - deduplicated curated fact counts are not used as direct validation inputs
- Assumptions and edge cases:
  - it is a raw-data completeness feed, intentionally separate from downstream KPI totals

### 9) Order value by source system
- Metric name: `order_value_by_source_system`
- Business definition: Current order value totals by ERP source system, with a flag for known valuation caveats from the Partner API freight issue.
- Grain: `source_system`
- Filters and exclusions:
  - latest version only
  - exclude deleted current orders
  - show ambiguous current-order counts separately
- Source feeds:
  - `fact_sales_order_headers`
- Calculation logic:
  - sum order value and tax/discount fields by source_system
  - flag rows from `PARTNER_API` where the freight adjustment is known
- Output query: `sql/06_kpis/order_value_by_source_system.sql`
- Owner: ERP Finance / Order Management
- Known limitations:
  - one source system has a documented valuation discrepancy and the issue remains unresolved
- Assumptions and edge cases:
  - source-system totals are descriptive evidence, not a validated accounting ledger

### 10) Operational quality summary
- Metric name: `quality_summary`
- Business definition: Aggregate count of duplicate rows removed, temperature anomalies, missing WMS stage chains, and incomplete reference rows, giving a single health scorecard for the operational layer.
- Grain: metric family-level summary
- Filters and exclusions:
  - uses Phase 7 fact and dimension quality markers only
  - intentionally keeps the quality layer separate from KPI tables
- Source feeds:
  - `fact_pos_transactions`
  - `fact_reefer_telemetry`
  - `fact_wms_scan_events`
  - `fact_sales_order_headers`
  - `dim_warehouse`, `dim_outlet`, `dim_product`, `dim_carrier`
- Calculation logic:
  - sum duplicate rows removed across curated facts
  - count temperature anomalies and missing WMS stage chains
  - count incomplete reference rows, manifest issue records, and feeds outside the date-dimension range
- Output query: `sql/07_quality/quality_summary.sql`
- Owner: Data Quality / Analytics Engineering
- Known limitations:
  - a summary cannot replace row-level diagnosis
  - it is a health dashboard, not a resolved data fix
  - temperature anomaly counts include missing/unresolved readings and values outside the 2–8°C band; a high count is not by itself a count of confirmed cold-chain excursions
- Assumptions and edge cases:
  - the summary is intended to guide prioritization and confidence assessment before actioning KPI outputs

## Definition standards used in this catalogue

Each metric in this catalogue is documented using the same pattern:
- metric name
- business definition in plain English
- grain
- filters and exclusions
- source feeds
- calculation logic
- owner
- output query / output table
- known limitations
- assumptions and edge cases

This follows the project requirement for a single, reviewable business metric registry.

## Ownership conventions

The catalogue deliberately uses business-friendly owners rather than code owners:
- Commercial Finance / Revenue Analytics for POS sales metrics
- Logistics / Cold Chain Operations for telemetry metrics
- Warehouse Operations / Fulfilment for WMS cycle-time metrics
- Data Quality / Analytics Engineering for completeness and health checks
- ERP Finance / Order Management for order-value comparisons

These are proposed accountable business functions based on metric subject
matter, not confirmed assignments. A named owner and sign-off workflow must be
agreed with Kestrel stakeholders before these outputs are used as governed
production KPIs.

## Documentation status

This catalogue is the final Phase 8 documentation layer. It complements the SQL executed in the repository and clarifies the business names and caveats that should be used when reviewing the numbers.
