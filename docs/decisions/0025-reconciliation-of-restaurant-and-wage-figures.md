# Decision 0025 — Reconciliation of restaurant and wage figures

| | |
|---|---|
| Status | Accepted, 2026-11-20; signed off by the owner-delegated advisor under the owner's delegation of 2026-11-20 (OI-03) |
| Date | 2026-11-14 |
| Task | S2-T03 |
| Basis | Document 04, PUB-64 and PUB-74 to PUB-77; document 07, MTH-22; OI-03; ruling L-216 |

## Context

The lead ran the S2-T03 builder on the real public cache on 2026-11-14.
The two reconciliations below record that run, with datasets as published on
2026-11-13. Each source is under CC BY 4.0, with its publisher as recorded in
`custodian/publicdata/sources.yaml`. These are attributed lead results, not a
worker's live-source reading. Selected receipts in the build evidence hold each
source's retrieval date and hash; no receipt or hash is invented here.

## Decisions

1. **R1 — Restaurants: closed as "not published".** For restaurants, activity
   561, year 2022, the five values of PUB-64 are read exactly: establishments
   2,086 and employees 41,458 from `sec_hr_size`; compensation 1,308,140 and
   operating surplus 1,247,422, both in QAR thousand, and published average
   annual wage 31,579 from `sec_hr_ind`. The same indicators table publishes
   the two percentages, 40.6% for intermediate goods and 16.5% for intermediate
   services. The exact fields for these values remain recorded in the registry.

   Production value 6,337,897 (QAR thousand) is not a field of any of the four
   datasets. Three derivations miss it: goods total 2,573,362 from `sec_hr_goods`
   divided by 40.6% gives 6,338,330; services total 1,045,667 from `sec_hr_serv`
   divided by 16.5% gives 6,337,376; output per worker 152,875 multiplied by
   employees gives 6,337,892 in QAR thousand. These are historical reconciliation
   comparisons only: production value is neither derived nor shown. The earlier
   design draft's "restaurant revenue" figure is not found in any published
   field and is not used.

2. **R2 — Wages: reconciled: tables differ, occupation table used.** The
   occupation table (`wage_occ`) and activity table (`wage_act`) have the same
   paid-worker totals in every shared year: 2,120,841 in 2020; 2,013,700 in
   2021; 2,122,250 in 2022; and 2,171,062 in 2023. Their worker-weighted means
   differ (occupation first, QAR): 10,084 against 10,352 in 2020; 10,151 against
   10,404 in 2021; 11,285 against 10,800 in 2022; and 11,714 against 11,025 in
   2023. Neither table is corrected to the other and no figure blends the two.
   Card C3 uses the occupation table and shows the activity table's mean in its
   source chain, as MTH-22 already requires.

3. **Pack text and closure.** The amendments to PUB-64, R1, PUB-75 and method
   card C4 belong to decision record 0026, which arrives with its own pull
   request. This record does not amend document 04. OI-03 closes on the
   advisor's sign-off under the owner's delegation. The lead records that
   sign-off in `OPEN_ITEMS.md` with the task's ledger; the worker does not.
   Internal reconciliation dispositions do not release display facts: the
   decision-bound sign-off and resolved registry entries remain required.

## Consequences

The builder retains both wage-table identities, both means and the totals in
internal evidence, with complete source chains. It reads the published restaurant
wage and percentages directly and supplies no production or revenue fact. A
missing decision or absent sign-off continues to block affected display facts.
The independent reviewer checks this record and the lead's real-cache evidence.

## Sources

- Lead's S2-T03 real-cache builder run, 2026-11-14, reported in ruling L-216
  Q3; restaurant catalogue and cache evidence also recorded in ruling L-203 R6.
- [Source registry](../../custodian/publicdata/sources.yaml): `sec_hr_ind`,
  `sec_hr_goods`, `sec_hr_serv`, `sec_hr_size`, `wage_occ` and `wage_act`;
  publisher National Planning Council, licence CC BY 4.0, with selected cache
  receipts providing retrieval dates and content hashes.
- [Document 04](../04_PUBLIC_DATA_PACK.md), PUB-64 and PUB-74 to PUB-77;
  pack amendments are owned by decision record 0026 in its separate pull request.
- [Document 07](../07_ECONOMIC_METHODS.md), MTH-22 and cards C3 and C4.
- [Open items](../../OPEN_ITEMS.md), OI-03.
