# Phase 5 sales reconciliation findings

## Canonical sales basis

The canonical sales fact uses deduplicated POS transaction lines, with channel
from the POS transaction as captured. `gross_sales_ex_tax_inr` is quantity times
unit price before discounts; `net_sales_ex_tax_inr` subtracts line discounts.
Tax is stored separately. This follows the POS contract, which says unit price
is exclusive of tax. Rows with unresolved master/channel lookups remain in the
fact and are flagged rather than silently removed.

The ERP order-header feed is kept as independent comparison evidence. It is not
added to POS sales because it has order-header rather than transaction-line
grain, has no join key to the POS rows, includes lifecycle versions/tombstones,
and the assignment documents a source-system valuation issue. Its value is
reported separately and is explicitly non-additive.

## Finance comparison

The supplied Finance report contains 312
week/channel rows. The comparison output contains
378 rows in total: the Finance report
rows have POS counterparts, and 66
additional rows contain ERP evidence only, with neither Finance nor POS sales.
Across its covered windows, published gross sales total
INR 4,589,317,346.95. The corresponding
deduplicated POS gross amount is INR
5,508,198,259.46
when bucketed by local sale/event date, and INR
5,508,198,259.46
when bucketed by ingest date. Event-date POS minus Finance is INR
918,880,912.51; ingest-date POS minus Finance is INR 918,880,912.51.

Reconstructing duplicate delivery without deduplication would add an estimated
INR 115,724,876.64 to the ingest-date POS gross amount, based on the
exact-duplicate counts retained by the Phase 4 fact.

## Important limitation: supplied report does not encode the stated legacy logic

The assignment generator labels the Finance report as having ingest-date and
duplicate-counting defects. However, the generator code creates
`legacy_finance_weekly_report.csv` from independent random values
(`rng.uniform` for gross sales and `rng.integers` for units/baskets), rather
than aggregating either POS or ERP source rows. Therefore the numerical
variances cannot validate those defects or be fully reconciled to source rows.
The comparison table shows event-date, ingest-date, and duplicate-inclusive
counterfactuals so a real report with the described legacy logic can be
reconciled when supplied. Until then, published report values are a benchmark,
not a validated target.

The report's `week_ending` values are Wednesdays spaced seven days apart, and
the generator derives them from `DAYSTR[::7]`. The reconciliation therefore
uses each supplied label as the start of a seven-day, half-open bucket
`[week_ending, week_ending + 7 days)`. This is an observed data-layout
interpretation; the column name itself suggests the opposite boundary.
