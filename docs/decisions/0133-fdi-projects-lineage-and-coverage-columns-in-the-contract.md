# Decision 0133: Declare the existing FDI project lineage and coverage columns

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-27 |
| Scope | Slice S2, task S2-T12; the `fdi_projects` release row only |
| Amends | Document 03 DAT-120 reading for the fifteen existing columns listed below only |
| Read first | Document 03 section 7.3 Columns, DAT-120 and DAT-142; CLAUDE.md rule 19 |

## Reason and bounded ruling

The table has emitted these columns since S2-T08 and S2-T12: `caveat_keys`,
`provenance`, `publisher`, `page_url`, `licence_id`, `licence_basis`,
`decision_record`, `terms_sha256`, `terms_url`, `retrieved_utc`, `page_sha256`,
`method`, `method_version`, `mapping_coverage` and `crosswalk_sha256`.
The supplied S2-FDICONTRACT.p1 inventory found no product, core, web or evals
consumer. The columns carry the sanad chain required by CLAUDE.md rule 19,
the announced-estimate caveat and mapping coverage; cutting them would remove
lineage. DAT-120 permits only a nullable field or a new table that no existing
consumer reads, so documenting these existing non-null fields needs this
bounded amendment rather than an ordinary nullable-field addition.

## Declaration rule

1. Document 03 section 7.3 declares these fifteen existing emitted columns,
   their types, meanings and absence behavior. They are declared, not added.
2. `investment_flight._record` supplies caveat keys and provenance;
   `investment_parse._with_lineage` copies source-envelope lineage;
   `investment_crosswalk.mapped_columns` supplies mapping coverage and the
   crosswalk hash when a reviewed crosswalk exists. Required fields are not
   nullable. Pending terms readings retain empty strings under L-1001;
   the crosswalk hash is absent when no crosswalk is supplied.
3. Classification adds only missing administrative fields to `ADMIN_FIELDS`;
   existing classifications remain, each column in exactly one group.

## Plants and evidence

S2-FDICONTRACT.b1 records the contract-first classification failure, a removed
classification plant, restoration by byte comparison and the required checks
in PROGRESS.md. Tests read the committed contract, without fetching a source.

## Limits and admission

Nothing else changes: no column is removed or renamed, no producer or consumer
changes, and no source, privacy, release or display rule changes. DAT-120 keeps
its existing meaning for every other field and table. This proposed record
requires different-maker review and owner acceptance; it claims neither.

Sources: ruling L-2322 item 4; S2-FDICONTRACT.p1 inventory; the three producer
functions named above; document 03 DAT-120 and DAT-142; CLAUDE.md rule 19.
