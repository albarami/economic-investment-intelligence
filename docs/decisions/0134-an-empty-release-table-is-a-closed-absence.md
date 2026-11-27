# Decision 0134: An empty release table is a closed absence

| | |
|---|---|
| Status | Accepted by the owner on 2026-11-27, at commit `b417470c`, with conditions ("Owner decision, 2026-11-27: I accept decision 0134 ("An empty release table is a closed absence") at commit b417470c, with these conditions kept on the acceptance record:"; "1. The follow-up build adds the plant the record lacks. An absence claimed with no attached rule 53 and 57 searches, or with searches that omit a place rule 53 lists, must refuse with its own specific reason. A valid absence with its searches passes."; "2. The follow-up build keeps the completeness checks and the exact declared/produced table-set check unchanged. Each guard must be shown to fail when removed alone and pass when restored."; "3. The acceptance goes by a documents-only pull request with another maker approving. Reconfirm the review on the head that merges (the approval on b417470c is S2-TRADECREDIT.rv2)."; owner’s signed answer under OWNER_RULES 60, recorded by L-2357); approving review: S2-TRADECREDIT.rv2, Droid kimi-k3, APPROVED `b417470c`. The acceptance holds while any condition is unmet. |
| Date | 2026-11-27 |
| Owner | The owner |
| Amends | Document 04 section 2, **Source registry**, the empty-table credit sentence quoted in item 1 |
| Purpose | Distinguish held-blocked open obligations, substantiated closed absences and populated credits. |
| Read first | Ruling L-2345 item 1; OWNER_RULES 53 and 57; ruling L-2340 item 2 and L-2335 item 1; document 03 section 7.3; document 04 section 2; decision 0040; TASKS.md S7-T12 |

## Proposed rule and follow-up

1. **Problem and present contract.** Document 04 section 2, **Source registry**,
   says: "An empty table credits only selected entries that declare that table in
   `release_tables`." Under that accepted rule, a credited key can show "in use"
   with zero delivered rows. Ruling L-2340 item 2(a) confirms that this complies
   with the current contract and falsifies no S2 gate row. The found case is
   `trade_wr`: `additions/industry.py` functions `parse_trade` and `_trade` return
   zero `pub_trade_wr` rows because the six measure and breakdown pairs do not
   fit the document 03 section 7.3 key (`trade_type`, `period`, `indicator`).
   `_TRADE_QUESTION` records the missing breakdown dimension; `_trade` ends in
   `_finish` with an empty row list and coverage reason `breakdown_not_in_key`.
   The source rows are held (L-2340 item 2(d)); this is a contract gap, not a data
   gap. No saved release was read for this proposal.
2. **Three evidence-based cases, never a bare empty-table credit.** Each
   selected entry and its declared release table is classified into exactly one
   of the following cases by recorded evidence, never by row count alone
   (L-2345 item 1; OWNER_RULES 53 and 57):

   - **Held but blocked — open.** Observations are held, but a schema, key or
     contract obligation prevents their release into the table. The obligation
     stays open, is never credited and is never a closed absence. Record the
     obligation and its consumer. Worked example: `trade_wr` observations are
     held, as recorded in the supplied `holdings-trade.txt` lookup; `_trade`
     yields no rows with reason `breakdown_not_in_key`. The document 03 key
     question in item 4 stays open for consumer S7-T12 under decision 0040.
   - **Substantiated permitted absence — closed.** Attached searches under
     OWNER_RULES 53 and 57 establish that there is nothing to release for the
     period and geography: search the holdings lookup, original extracts,
     archives, relevant public caches, snapshots, authorised intakes and
     receipts, recording the places searched and the remaining gap. An
     unfinished acquisition, schema, access approval, evidence or implementation
     stays open instead. Only this substantiated permitted absence gives reason
     `additions_table_empty` and state `NO_DATA`. Worked illustrative example
     (invented, not a source finding): entry `illustrative_absent` declares
     `illustrative_table`; attached searches establish no releasable observations
     for its declared period and geography and no unfinished obligation. Its
     empty table is a closed `additions_table_empty` / `NO_DATA` absence.
   - **Populated control — credited.** The table has rows and the existing
     row-source lineage and completeness checks hold; it is credited as today.
     Worked illustrative example (invented, not a source finding): entry
     `illustrative_populated` supplies rows to its declared `illustrative_table`
     with valid row-source lineage. Those rows credit that entry.

   The rule applies across every parser and phase in plan S2-TRADECREDIT.p1
   item 5, not just trade. It never drops a row, a check or a source. Receipts,
   source lineage, contract questions, row coverage and existing completeness
   checks remain required.
   The implementation evidence is in
   `custodian/src/eii_custodian/publicdata/assembly_adapters.py`:

   - `Production.table` stores `sources` in `table_sources` and appends the table
     to `source_tables` for each key, without a row-count condition.
   - Phase `additions`, function `Production.additions`: when `sources` is empty,
     the `if not sources` branch selects declaring entries from `release_tables`,
     then calls `self.table(name, rows, sources)` regardless of row count.
     The parsers named in the plan are `parse_trade`, `parse_logistics` and
     `parse_manufacturing` in `additions/industry.py`, `parse_property`,
     `parse_museum` and `parse_health_centres` in `additions/property_venues.py`,
     `parse_permits` in `additions/municipal.py`, and `parse_splits` in
     `additions/splits.py` for workforce splits. The plan's `parse_workforce`,
     `parse_museums` and `parse_phcc` are descriptive names, not current function
     names. All additions parsers registered by `additions/build.py` function
     `parsers` are covered, including the other municipal and split families.
   - Phase `fsq`, function `Production.fsq`: the call
     `self.table("pub_place_fsq", [asdict(r) for r in result.rows], (row.key,))`
     credits `row.key` even if `result.rows` is empty.
   - Phase `busyness`, function `Production.busyness`: the call
     `self.table("pub_venue_busyness", rows, (entry.key,))` credits `entry.key`
     even if `rows` is empty.
   - Phase `series_stage`, function `Production.series_stage`: keys come from
     `envelope["source_chain"]`; `self.table(name, envelope["rows"], tuple(keys))`
     credits them even if `envelope["rows"]` is empty.
   - Phase `frame`, function `Production.frame`: when `gazetteer` exists, the
     `for key in building_keys` block adds each key to
     `self.table_sources["gazetteer"]` and appends `gazetteer` to
     `self.source_tables`, without checking for yielded building rows.

3. **Proposed document 04 replacement.** Replace the empty-table credit
   sentence in document 04 section 2 with the following text, word for word;
   keep its lineage refusal as a separate sentence:

   > For each selected entry and its declared release table, recorded evidence, never row count alone, distinguishes three cases: held observations blocked by a schema, key or contract obligation stay open with the obligation and consumer named, never credited and never a closed absence; an empty table with attached OWNER_RULES 53 and 57 searches substantiating a permitted absence for the period and geography gives the closed absence `additions_table_empty` in state `NO_DATA`; a populated table credits its rows' `source_key` values under the existing lineage and completeness checks. With no selected entry declaring the table in `release_tables`, assembly refuses `assembly_lineage_missing`.

   This applies to additions, fsq, busyness, series_stage and frame, across all
   their parsers, without dropping any row, check or source. Document 04 itself
   stays unchanged until acceptance. The exact declared/produced table-set
   check remains; the build must represent open obligations and permitted
   absences through those checks rather than bypass or weaken them.
4. **Open trade-key choice, ordered by S7.** Document 03 section 7.3 declares
   `pub_trade_wr` at trade type × year × indicator, keyed by `trade_type`,
   `period`, `indicator`. Its key-field row permits purchases, sales or stocks
   as `indicator`, with `value` decimal(18,2) and `unit`; it has no breakdown
   field. A document 03 change is needed to release the held pairs faithfully.
   Options for owner review are to add a reviewed breakdown field to the key
   while retaining indicator as the measure, or to specify a separate
   breakdown-bearing table and its key, with an explicit consumer mapping.
   Neither option is selected here; no collapsed breakdown, fabricated total
   or indicator overloading is authorised. The consumer is S7-T12's national
   benchmark context under decision 0040, which also retains wholesale and
   retail trade as present-size context. Under L-2340 item 2(d) and OWNER_RULES
   34, this work runs in the background lane ordered by S7, outside the S2 path.
5. **S2 audit counts.** Each credited key whose table has zero rows moves
   from "in use" either to the held-blocked open case, counted apart, or to a
   substantiated permitted closed absence, according to the recorded evidence
   of item 2. The lead measures the exact list as "rows per credited key, from
   the saved release" at the next full audit's preflight, using the saved
   Parquet and manifest, not the plan's assembly-JSON probe (L-2340 items 2(e)
   and 3; L-2345 item 1). No affected count is asserted here. A key's mere
   membership in `table_sources` is not delivered-row evidence, including when
   other sources populate a shared table.
6. **Only after acceptance.** One build task makes the code follow the three
   cases across the five phases. Its expected files are
   `custodian/src/eii_custodian/publicdata/assembly_adapters.py` for crediting,
   `custodian/src/eii_custodian/publicdata/assembly_reports.py` (`gather_audit`)
   for open obligations and substantiated closed absences,
   `custodian/publicdata/sources.yaml` for reviewed declarations that preserve
   the trade `breakdown_not_in_key` obligation as open,
   `custodian/tests/test_assembly_producers.py`,
   `custodian/tests/test_assembly_reports.py` and
   `custodian/tests/test_source_completeness.py` for plants and controls, and
   document 04 section 2 for the accepted wording. Keep
   `custodian/src/eii_custodian/publicdata/completeness.py` checks intact.
   Plant a held-blocked case presented as a closed absence: it must refuse
   specifically because the recorded blocking obligation remains open. Plant
   a populated table presented as an absence: it must refuse specifically
   because populated rows contradict the absence. A valid substantiated
   permitted absence with its attached searches must pass as
   `additions_table_empty` / `NO_DATA`; a held-blocked control stays open and
   uncredited, and a populated control passes with real row lineage. Each
   negative case changes only its disposition while other inputs remain valid;
   assert the specific refusal reason, then prove each guard red when removed
   alone and green when restored across the named phases.

   Named acceptance evidence for condition 1: take one otherwise-valid
   substantiated-absence case and keep every other input identical. Removing
   its attached rule 53 and 57 search evidence must refuse with its own specific
   reason, provisionally `absence_searches_missing`. Restoring the evidence but
   omitting one place listed by rule 53 must refuse with a different specific
   reason, provisionally `absence_search_place_missing`. Restoring the complete
   searches must pass as `additions_table_empty` / `NO_DATA`. These reason names
   are placeholders; the follow-up build chooses the final codes and asserts
   each specific reason.

   Named acceptance evidence for condition 2: the checks of
   `custodian/src/eii_custodian/publicdata/completeness.py` and the exact
   declared/produced table-set check stay unchanged. Show each guard red when
   removed alone and green when restored. This documents-only acceptance record
   builds none of those controls and changes no code, tests, registry or schema.
   The lead holds the trade-key open item until a producer releases the trade
   rows; the conditions below remain separately required.
7. **Acceptance conditions.** The owner's signed answer of 2026-11-27,
   recorded by L-2357 under OWNER_RULES 60, keeps these conditions on acceptance:

   > 1. The follow-up build adds the plant the record lacks. An absence claimed with no attached rule 53 and 57 searches, or with searches that omit a place rule 53 lists, must refuse with its own specific reason. A valid absence with its searches passes.

   Satisfied by the follow-up build’s condition 1 evidence in item 6: the
   two distinct specific refusals and the restored complete-search control.

   > 2. The follow-up build keeps the completeness checks and the exact declared/produced table-set check unchanged. Each guard must be shown to fail when removed alone and pass when restored.

   Satisfied by the follow-up build’s condition 2 evidence in item 6: the
   unchanged completeness and exact table-set checks, each guard independently
   shown red when removed and green when restored.

   > 3. The acceptance goes by a documents-only pull request with another maker approving. Reconfirm the review on the head that merges (the approval on b417470c is S2-TRADECREDIT.rv2).

   Satisfied by this documents-only pull request, PR 175, approved by
   another maker, with that review reconfirmed on the head that merges.
   S2-TRADECREDIT.rv2 approved `b417470c`; that approval does not substitute
   for review of this acceptance-record delta.

   The acceptance holds while any condition is unmet. If a condition cannot
   be met, hold the acceptance and tell the owner why in one line.
