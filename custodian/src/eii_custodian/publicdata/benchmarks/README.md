# S2-T26 benchmark handoff

All four download mappings remain inactive. S2-P18 records WDI dataset/catalogue
and UNCTAD portal/terms readings, with body hashes and exact words in
`custodian/publicdata/review/trade_publisher_readings.yaml`. Their successfully
read metadata hosts remain outside PUB-03 (L-1270); reading a page never
admits its fetch host. No download URL or redirect is confirmed.
WDI catalogue metadata version is separate from a selected file vintage. Qatar
coverage, indicator/status mappings, native schemas and count/byte bounds remain
unverified. The attempted IMF and ILOSTAT pages returned HTTP 403; neither is
activated and no access challenge is bypassed. No missing source has a substitute.

| Source | Pending source-specific work |
|---|---|
| wb_wdi | Independently read WDI page, terms, version, Qatar key and indicator histories. |
| unctad_fdi | Independently read UNCTADstat page, flow/stock and inward/outward dimensions. Keep announcements separate. |
| imf_weo | Independently read WEO vintage and each indicator's historical/estimate/forecast boundaries. |
| ilostat_qat | Confirm Qatar availability first; otherwise unavailable, with no substitute. |

The offline adapter accepts explicitly mapped JSON, CSV or TSV columns with
source-specific constants, indicator/period status maps and expected last periods.
A bounded ZIP may contain an exact declared member inventory with per-member
byte and row bounds; no member is extracted to a caller-selected path. Tests use
invented layouts, not assertions about the publishers' real formats. Shared
fetch/decimals translates declared missing tokens without inventing zero.
Receipts include raw, selected, excluded and missing counts, last periods,
member hashes and a fingerprint of recorded terms words/date/basis. This is a
recorded-terms fingerprint, not a claim of fetching a separate terms page.

The selected reader hashes raw and output bytes, reparses the raw input, compares
the complete receipt and requires completion. Source flags and decimal text are
preserved. Historical reads use historical_rows after read_selected and exclude
both forecast and unclassified rows. The closed use boundary allows only
context at source geography; it refuses every join, sum, segmentation and
apportionment. Thus UNCTAD cannot combine with fdi_projects; Public sex or
nationality splits cannot join synthetic records, segment worker, residence or
company records, or combine with protected figures.

Lead: transcribe each page's own licence words, attribution, retrieval timestamp,
hash, version, tier and Qatar coverage independently. Review hosts and native
mapping; select OI-n1 indicators/history and OI-n2 trade coverage. Record
registration, sign-in, robot-check and paid-tier obstacles. Do not activate a
mapping merely because fixture tests pass. The live layout verification and terms-page acquisition remain lead work.

Trade reconciliation records the owner-confirmed selection of 2026-11-20 in
publicdata/trade_reconciliation.yaml (PO-S2-80; S2-T26). The owner said
"for number 4i confirm." The two portal content hashes are supplied selection
metadata, not a claim that this task read their bytes. The reporter, mirror and
harmonised inputs remain selected with empty hashes and `pending_fetch: true`.
That boolean is distinct from an evidenced access obstacle: a pending input
cannot carry a hash, a row binding or an obstacle record. It blocks all input
reads, comparisons and comparison reports with `comparison_input_pending_fetch`;
dispatch and assembly retain `NO_DATA` and that reason, without comparison files.

The `pending:all_common_partners_per_year` and `pending:all_present_hs2`
directives retain the selection of every common partner per year, with no size
cut or ranking, and total goods plus every present chapter. They are not native
partner/product cells. After fetch the lead must expand them through the reviewed
closed country-code list and source-present chapters; an unexpanded directive
blocks comparison with `comparison_scope_pending_review` even if inputs have
hashes. The active years are 2019-2024 and the single comparison revision is
HS 2017. For 2022-2024 every chapter changed by HS 2022 needs an evidenced
classification cause. The later portal file is selected for deferred 2025 only
when international coverage exists; partial 2026 is excluded. Native currencies
and valuations stay separate, and every missing cell stays a gap with its reason.

The lead supplies explicit selected hashes, row bindings and their evidence hashes,
country/direction bindings, years, partners and source-native scopes. The builder
reads portal contracts, Comtrade assemble and the BACI typed reader; the selected
reader repeats those reads and recomputes the saved comparison bytes. Every source
role pair gets a row for every requested cell, including two absent sides. Exact
calendar aggregates retain their constituent input IDs; partial calendars stay gaps.
Recorded causes never claim to explain an entire gap. The manifest owner report
retains cause evidence, access/free-plan obstacles and unknown prices as null.
Benchmark access obstacles are written to benchmark_owner_report.json by dispatch.
All these outputs remain cache-only. Different-maker build review is still required.

Refusal plants cover policy, registry binding, acquisition, parsing, selected
readers and trade comparison boundaries in the benchmark and reconciliation
tests. Decoder failures use the selected reader's fixed diagnostic. Reconciliation
dispatch converts native Comtrade, BACI and decimal refusals to comparison_invalid
with NO_DATA and still writes the build log. The ZIP content-length recheck stays:
a corrupt member can have an admitted declared size but shorter readable content.
