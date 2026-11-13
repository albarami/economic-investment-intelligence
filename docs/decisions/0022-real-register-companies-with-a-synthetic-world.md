# 0022 — Real register companies with a synthetic labour and residence world attached

| | |
|---|---|
| Status | Accepted, 2026-11-13 |
| Date | 2026-11-13 |
| Owner | albarami |
| Decided by | The owner, in his own notes of 2026-11-13 (the public register; the correction and answers that followed) and in his earlier notes of the same day on synthetic companies shaped like the real ones and on the calibration table |
| Amends | AGENTS.md and CLAUDE.md rules 3, 8, 10 and 24; [decision 0001](0001-fully-synthetic-records-real-public-data.md) (consequences); [decision 0016](0016-version-1-covers-the-whole-initiative.md) items 12, 13 and 19 to 21; [decision 0017](0017-public-data-additions-and-public-splits.md) item 9; [decision 0019](0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 1; the passages of the pack listed in "Amended passages" |
| Purpose | Record that the companies of the public business register are real in this project, and that the synthetic labour and residence world is attached to them and treated everywhere as real. |
| Read first | [01_PROJECT_BRIEF.md](../01_PROJECT_BRIEF.md), [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md), [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](../06_PRIVACY_AND_DISCLOSURE_CONTROL.md), [decision 0016](0016-version-1-covers-the-whole-initiative.md) |

## Context

- The project was built on a fully synthetic world of companies and people beside real public data ([decision 0001](0001-fully-synthetic-records-real-public-data.md)). [Decision 0016](0016-version-1-covers-the-whole-initiative.md) item 12 added named synthetic firms as prospects, partners and suppliers.
- On 2026-11-13 the owner decided that what a publisher puts in the open is real in this project, and that the public business register is such a source. The labour and residence side stays synthetic, but it is shaped exactly like the real custodian records and treated everywhere as real, so that whoever he shows the product to sees what the system would do when all the real data is combined. He presents and explains the product himself.

## Decision

1. **The register is a Public source.** The public business register is public data: its establishments are real in this project. The file of its public establishment records (each field the public card shows, person names excluded) is collected by the owner's advisor as a visitor's browser receives it and kept outside the repository. It is read only through the setting `EII_REGISTER_FILE`, by the lead's own shell (the world build run there included), the release build and the running product. It is never committed, never put in a brief or a fixture, and never given to a worker tool or a reviewer. Tests and continuous integration use an invented stand-in of the same shape. No fetcher for the register's site is written into the repository. The financial centre's public register is a second such source under the same rules (the owner's message of 2026-11-13): its companies are register companies in the sense of this decision. Its records come in a file of their own, read through the setting `EII_FC_REGISTER_FILE` by the same readers and under the same rules; they carry a free-text registered address and no position, so placing them on the map is done in the lead's own shell.
2. **The labour and residence world is synthetic and attached to the real companies.** The employment, wage and residence records are generated in the same tables, fields and formats as the real custodian records (the feeds of sections 6.1 to 6.4 of [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md)), the nationality group of each worker included, and attached to the real register companies by their registration number. Their totals by activity, size band, occupation group and salary level follow the calibration table of the owner's note exactly; that table is kept outside the repository and read only by the world build in the lead's own shell. Every person is invented; no real person's record is read.
3. **Treated everywhere as real.** Every analysis, journey, ranking, list and the ministry view (the `oversight` seat) runs on these records. Pay by sector (D5) uses them, with middle ranges. No screen names a data class (the owner's decision on marks of 2026-11-13); the provenance of every number stays behind "More evidence".
4. **What a company's card shows.** Every field the public business register publishes for that company, plus its number of employees from the attached records. Wages and the other labour and residence details stay inside the system: they feed the analyses (released under the disclosure rules of [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](../06_PRIVACY_AND_DISCLOSURE_CONTROL.md)), the ministry view, and a company's own records in its own seat. On any other screen they appear only as released aggregates.
5. **Named synthetic firms are retired.** Lists of prospects, partners and suppliers show real register companies with their card fields and employee counts, ordered by tested code over criteria the user can see and change (rule 25 of AGENTS.md). The two fictional company seats and the four cases stay fictional; their labels pass the name-collision test against the register.
6. **Rules amended.**
   - Rule 3 of AGENTS.md: "Every person is invented; the companies are the real ones of the public register, and their labour and residence records are synthetic; no real custodian record, field, file, count or parameter is ever read, except the calibration table of the owner's note, read only by the world build."
   - Rule 8: a new subject `register_company` accepts Public slots and the attached records' employee count; its other labour and residence facts appear only in analyses under document 06, the ministry view and its own seat. `place_public` and `fdi_project` keep Public slots only.
   - Rule 10: the synthetic worker records carry the nationality group in the format of the real records, and the register's establishment nationality is a company attribute; both may be used as dimensions of released statistics under document 06. No sex or gender attribute or proxy is added. Public splits by sex or nationality stay Public facts on their own geography.
   - Rule 24: showing a company's public card and its employee count is not a lookup; looking up an owner or an individual stays forbidden, and so do the other prohibited claims.
7. **The disclosure rules stand.** [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](../06_PRIVACY_AND_DISCLOSURE_CONTROL.md) governs every released figure: minimum counts, dominance, complements, pooling and the attack suite. A single company's wages and other labour and residence details never leave the system except in its own seat and the ministry view, as their designs provide. The attack suite gains planted cases for the new subject: a company's wage appearing on a card or in a list fails, and a released aggregate that isolates one company fails.
8. **Repository protections stand.** Registration numbers, licence and tax numbers and every register row stay out of the repository, every brief, every fixture, every log and every model request; the identifier and egress scans keep refusing them.

## Evidence

- The owner's notes of 2026-11-13 (project records held by the owner).
- The lead's inventory of the pack passages this decision touches, 2026-11-13 (a project record of the run, not in this repository).

## Consequences

- Slice S4's world build attaches generated employees, wages and residence to register companies; S4-T02 and S4-T03 are re-planned to it; the name generator built ahead and parked is not needed for companies and stays parked.
- Slice S5's release builder releases the new subject's employee count and the area aggregates; the firm-list release of PRV-125 is replaced by the register-company list.
- The tests that guarded named synthetic firms (TST-207, TST-233 and their kin) move to the new subject, each keeping a planted violation; none is deleted.
- The map's establishment points open the company card; firm counts and density come from the register.

## Amended passages

The edit-only sweep amends, to this decision, the passages of AGENTS.md, CLAUDE.md, documents 01 to 17, the glossary and TASKS.md that state the replaced rules, keeping each requirement's identifier and changing only what this decision changes. A requirement the decision withdraws keeps its row, marked "Withdrawn by decision 0022" with its reason. The earlier decision records (0001, 0005, 0013, 0016, 0017 and 0019 among them) are not edited: where they state a rule this record replaces, this record governs.

## What would change this decision

- A further owner decision.
- Terms of the register's publisher that forbid the use made here, found when the file is collected: the source is switched off and the owner is told.

## Open questions and assumptions

- OPEN: the fields of the register file and of its invented stand-in are confirmed when the file is first read, without committing either the file or a field value.

## Sources

- The owner's notes of 2026-11-13 (project records held by the owner).
- Documents 01 to 17 of the pack, as they stand at the base commit of the pull request.
