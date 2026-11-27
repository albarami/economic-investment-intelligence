# Decision 0134: An empty release table is a closed absence

| | |
|---|---|
| Status | Proposed, 2026-11-27; awaits the owner's acceptance after a different-maker review |
| Date | 2026-11-27 |
| Owner | The owner |
| Amends | Document 04 section 2, **Source registry**, the empty-table credit sentence quoted in item 1 |
| Purpose | Replace bare credits for empty release tables with closed absences, while retaining the held trade rows and their contract question. |
| Read first | Ruling L-2340 item 2 and L-2335 item 1; document 03 section 7.3; document 04 section 2; decision 0040; TASKS.md S7-T12 |

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
2. **Closed absence instead of bare credit.** A selected entry whose declared
   release table has zero rows gives a closed absence with reason
   `additions_table_empty` and state `NO_DATA`, never a bare credit. This applies
   across every parser and phase in plan S2-TRADECREDIT.p1 item 5, not just trade.
   It never drops a row, a check or a source. Receipts, source lineage, contract
   questions, row coverage and existing completeness checks remain required.
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

3. **Proposed document 04 replacement.** Replace only the quoted sentence in
   document 04 section 2 with the following sentence, word for word:

   > A selected entry whose declared release table has zero rows gives a closed absence with reason `additions_table_empty` and state `NO_DATA`, never a bare credit; this rule applies to additions, fsq, busyness, series_stage and frame, across all their parsers, without dropping any row, check or source.

   Document 04 itself stays unchanged until acceptance. The adjacent
   `assembly_lineage_missing` refusal and exact declared/produced table-set
   check are retained; the build must represent the explicit absence through
   those checks rather than bypass or weaken them.
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
5. **S2 audit counts.** Each credited key whose table has zero rows moves from
   "in use" to a closed absence under the proposed rule. The lead measures the
   exact list as "rows per credited key, from the saved release" at the next
   full audit's preflight, using the saved Parquet and manifest, not the plan's
   assembly-JSON probe (L-2340 items 2(e) and 3). No affected count is asserted
   here. A key's mere membership in `table_sources` is not delivered-row
   evidence, including when other sources populate a shared table.
6. **Only after acceptance.** One build task makes the code follow this rule
   across the five phases. Its expected files are
   `custodian/src/eii_custodian/publicdata/assembly_adapters.py` for crediting,
   `custodian/src/eii_custodian/publicdata/assembly_reports.py` (`gather_audit`)
   for closed absences, `custodian/publicdata/sources.yaml` for reviewed caveat
   declarations (including the trade `breakdown_not_in_key` caveat),
   `custodian/tests/test_assembly_producers.py`,
   `custodian/tests/test_assembly_reports.py` and
   `custodian/tests/test_source_completeness.py` for plants and controls, and
   document 04 section 2 for the accepted wording. Keep
   `custodian/src/eii_custodian/publicdata/completeness.py` checks intact.
   Plant an empty declared table presented as "in use": it must be refused
   for the specific empty-table reason `additions_table_empty`; the valid
   closed-absence control must pass as `NO_DATA`, and a populated control must
   pass with real row lineage. Prove the guard red when removed alone and green
   when restored, across the named phases. This proposal builds none of that
   control and changes no code, tests, registry or schema. The lead holds the
   open item until this record is accepted and a producer releases the trade
   rows; another maker's review precedes owner acceptance.
