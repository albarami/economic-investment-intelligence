# OI-03 reconciliation evidence status

Status: open. Proposed decision: `0025-reconciliation-of-restaurant-and-wage-figures`.
No selected public cache versions were supplied to this pass. No real-data
reconciliation, actual basket review or sign-off is claimed.

## R1 — Restaurant scope

The proposed default is `sec_hr_ind` production value, never the unmatched
revenue figure (PUB-75). Search `sec_hr_ind`, `sec_hr_goods`, `sec_hr_serv` and
`sec_hr_size`; record dataset, field, activities, measure, year and establishments
covered. Compare all four scope axes. All searched sources are dependencies,
including a match found outside the indicators table. Record the source receipt
and exact field-to-contract mapping for every value of PUB-64. Copy the published
average annual wage; do not replace it by compensation divided by employees.

## R2 — Wage-table identities

The proposed national card uses `wage_occ` (ASSUMPTION from PUB-76). Record both
unrounded means and worker totals for every year shared with `wage_act`.
Discrepancies remain evidence; they are not edits to the data. The parsed rows
carry their registry source as `table_code`. Both means remain separate measures.

## Closure mechanism

`series/reconcile.py` checks that the decision exists and that a separately
recorded JSON sign-off note has `approved: true`, `reviewer_role` equal to
`owner-delegated advisor`, the decision filename in `record`, its exact SHA-256
in `record_sha256`, and the complete affected set in `sources`. These are the
fields of the mechanism, not a sign-off note. The builder creates no such note.
Missing record, missing note, wrong hash or omitted sources leave the item open.
The note records human approval; the code does not authenticate a human identity.

The gate requires complete transitive source dependencies from its caller.
It blocks open or unknown dependencies, including derived facts and newly
affected sources supplied to the gate. It is a reconciliation gate only;
complete fact-schema validation and release integration are still outstanding.

## Handoffs

- S2-T03 still owes the selected-export builder, actual bilingual basket review,
  real R1/R2 evidence, PUB-64 exact mapping, signed decision and OI-03 closure.
- S2-T04 owns PUB-67's ISIC-prefix classification, all four group shares and
  reconciliation, five/eight-digit subcounts, the legacy first-four-digit matches
  that stay unmapped, and the restaurant code's ISIC mapping.
- S2-T02 and S2-T06 own the inputs of PUB-71 to PUB-73; S2-T07 reuses the pure
  calculation functions. No whole-slice regression pass is claimed here.
- `stage.run_stage(required=...)` refuses missing owned figures when requested;
  wiring that requirement and figure generation into `build-public` is unfinished.

## Continuation update — confirmed shapes, no cache values read

The preceding status describes the first pass. The lead subsequently supplied
export field names and JSON types. The registry now records those columns;
`series/parse.py` holds the source-field-to-contract map. Its `UNRESOLVED` targets
are blockers, and `EVIDENCE_ONLY` targets do not enter a contract column.

The selected-hash builder and its one-call fetch integration now exist. It writes
contract-shaped utility, transit, sector and wage rows under `series/internal`,
with method/version, field mappings, per-row source identity and selected receipt
chains. It computes regression evidence separately under `series/regression`.
The final stage validates this evidence, including required owned checks. Missing
checks fail. No source values or real hashes were read in either builder pass.

The confirmed `sec_hr_ind` shape has no production-value field. Production must
not be derived from productivity and employment or copied from the regression
anchor. R1 can search the confirmed numeric fields, but its production comparison
and establishment-coverage comparison remain blocked. The lead must identify
the missing source field and scope evidence before R1 or PUB-64 can pass.

The licence shapes expose `lbldy` as text but do not confirm its mapping to
municipality codes. The customs shapes expose origin text without confirming
ISO3 semantics or a crosswalk, and do not state a quantity-unit field. Those contract tables are withheld pending confirmed mappings/fields;
no country or municipality code is guessed. Registry types currently cannot
express nullability; the series parser records the confirmed nullable fields,
but the upstream fetch schema check may refuse a null in its first row. Changing
that shared fetch check is outside this task's allowed files.

R2 computes all shared years from selected wage tables and retains discrepancies.
PUB-62, PUB-63, PUB-66, PUB-68 and PUB-70 have computed internal checks; this is
not a claim that the real inputs pass. PUB-64, PUB-65, PUB-67 and PUB-69 cannot
pass the current complete owned-check gate. The basket review remains withheld;
the PUB-67 spine handoff above still applies. Transit month conversion currently
accepts numeric text only and refuses another month representation explicitly.

Old owned outputs are removed before selection, provenance or reconciliation
refusals, including missing fetch selections. A blocked or failed build emits
no display table. OI-03 remains open: built; closure awaits the sign-off, real
reconciliation evidence and the identified missing-field work.


## Third-pass correction — ruling L-203

The earlier missing-field requests above are history. The lead confirmed month
forms, integer customs-code padding, source units, Arabic municipality names and
country-name semantics. The builder now writes customs and licence contract rows
as internal evidence. The frame parameter is a sequence of Municipality(code,
name_ar), the latter copied from bnd_hdx adm1_name1 by S2-T02. Exact text only is
matched. No frame implementation or typed input existed in this workspace before
this pass; the narrow typed seam is now explicit. Unknown names keep null codes
and are listed by the municipality_exact_match check. The alias review file is
empty; a reviewed row needs source_name_ar, frame_name_ar, reviewer_role and
review_date. No alias is manufactured here.

Country names use country_iso3.csv: a partial ISO 3166 reference list, not source
data, with human_reviewed false for every row. Unlisted names remain null and
are reported. Quantity unit and valuation basis are not stated by the source;
weight is kg and value QAR. The earlier HS8 length histogram is written before
any length refusal, and one-digit later codes are counted as code_not_stated.

Decision 0025 records the supplied R1 evidence and amends only PUB-64's regression
row: production is absent, not inferred. The builder reads published percentages.
R2 still requires the lead's real-cache run. The bilingual basket review still
needs each included/excluded dotted tariff line, both descriptions, reasons,
supplier ISIC class, reviewer role, date and the hash of the source read by the review.
The build checks every included and excluded code against the twelve-digit source
lines, each included bilingual pair after trimming its ends, all source siblings
under every included eight-digit parent, and no repeated code within an activity.
Closure still needs the delegated note bound to the final decision hash and the
complete source set, then the lead's registry and OI-03 updates.


## PO-S2-R8D-02 — winning dated closure pointer and superseding correction (2026-11-24, records only)

The stored **Handoffs** and earlier "OI-03 remains open" lines above are history.
The OI-03 Closure entry in `OPEN_ITEMS.md` **OI-03 — Conflicting restaurant and wage figures** (CLOSED entry) records the winning dated closure pointer of `2026-11-20, under PUB-77`: [decision 0025](../../../docs/decisions/0025-reconciliation-of-restaurant-and-wage-figures.md) is Accepted and signed off by the owner-delegated advisor under the owner's delegation of `2026-11-20` ("1: you make sign"). The signature binds the record's SHA-256 `9e90ef5499` (the `Status` line set to Accepted; it supersedes the first signature of the same day at `1e71c00107`, whose record differed only in that line) and the six sources `sec_hr_ind`, `sec_hr_goods`, `sec_hr_serv`, `sec_hr_size`, `wage_occ` and `wage_act`. R1 stays "closed: not published" (no production value is derived or shown); R2 stays "reconciled: tables differ, occupation table used", with the activity-table mean in the source chain. The six registry rows read `reconciliation: resolved:0025-reconciliation-of-restaurant-and-wage-figures`; the binding file (`review/oi03_signoff.json`, the advisor's signature record) is written by the lead's shell into the uncommitted public cache before the next live run, never committed; the gate still refuses an absent or unbound sign-off (`series/reconcile.py` `Resolution.approved`, `gate_report.oi03_line`). OI-171 is a separate hotel-basket item and stays open.

Above lines retain their force as written evidence. This pointer does not re-author the earlier missing-field, sign-off, handoff, registry or build-stage text; it is the dated superseding correction that closes the records-only follow-up `PO-S2-R8D-02` of S2-R8D round 3. No earlier row of this file is rewritten; the pointer is appended.
