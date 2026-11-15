# 0037 — The generated worker records carry gender

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-15 |
| Owner | albarami |
| Decided by | The owner, in the decision of 2026-11-15 supplied in the task brief |
| Amends | AGENTS.md and CLAUDE.md rule 10; decision 0022 item 6 and decision 0023 item 16 only insofar as they exclude employment gender; the passages below |
| Purpose | Permit calibrated employment gender and protected statistics without adding gender to residence or company records. |

## Context

The existing rule permits movement gender aggregates but forbids worker gender. The owner now permits a gender field in the employment records, drawn from his aggregate calibration table. This decision records the exception precisely; it makes no claim that a draw, protected release or attack suite already exists.

## Decision

1. **Employment field and draw.** Generated worker (employment) records carry a gender field in the format of the real records, drawn from the owner's gender mix by occupation group and activity. Until the table is present, leave the field empty (null) and report release coverage as “not drawn”. This is neither zero nor an evidence status. No values or category mapping are inferred from a Public sex split or from the movement gender list.
2. **Protected statistics only.** Gender may be a dimension of released statistics only under document 06, with the same cell rules, differencing and attack tests as nationality group. Its red-team and attack suites cover gender, with unchanged attack sizes, tolerances and controls-off/controls-on requirements. Never show it for a person or use it as a key joining to another record. Never join worker gender to a Public sex split; rule 10's existing movement-generator anchor exception remains separate and unchanged.
3. **No other field or proxy.** Residence and company records carry no gender attribute. No other sex or gender proxy is added. Movement keeps its aggregate-only one-way splits, never person rows or a worker joining key. The three existing nationality forms and Public-split geography rules remain.
4. **Binding amendments.** AGENTS.md and CLAUDE.md remain byte-identical and their status states “amended by decisions 0036 and 0037 on 2026-11-15”. Rule 10 names this exception. Documents 03, 05, 06 and 12 state the field, draw, disclosure dimension and tests, citing this decision. Permission to release a dimension does not bypass the closed release schema: S5-T11 names its columns and governing family before export and proves all existing controls.

## Amended passages

- Document 06, PRV-09: the field, dimension and build-failure rules permit only employment gender and its authorised protected statistics; movement retains its separate exception (items 1 to 3).
- Document 01, In brief and section 14 Pay or workforce split by nationality row; document 02, ARC-132; document 08, BE-110; document 11, DES-193; GLOSSARY, In brief: replace flat gender bans with the same narrow employment/protected-statistics exception (items 1 to 3).
- [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md), section 6.2 `employment.v1`: nullable `employment_spell.gender`; DAT-141: narrow schema exception; DAT-170: draw, permitted release and non-join requirements. Other record schemas remain gender-free.
- [05_SYNTHETIC_WORLD_AND_SIMULATION.md](../05_SYNTHETIC_WORLD_AND_SIMULATION.md), In brief, section 5 People and SYN-13, section 9 F6, section 14.1 SYN-89 and section 18 dropped list: remove the blanket worker-gender ban while preserving Public-anchor and movement boundaries. SYN-92 states the calibrated draw and missing-table behaviour.
- [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](../06_PRIVACY_AND_DISCLOSURE_CONTROL.md), In brief, section 10 PRV-76, section 13 `DIMENSION_NOT_OFFERED`, and PRV-136: gender under nationality-group cell controls, structural checks, differencing and attack coverage; no person display or gender joining key.
- [12_TESTING_AND_QUALITY.md](../12_TESTING_AND_QUALITY.md), TST-208, TST-262, TST-74 and the sex/gender/nationality matrix: lawful employment gender passes; prohibited placements still fail. New TST-264 tests calibration absence, forbidden proxies and joins, and full privacy/red-team coverage. TST-261's movement person/key prohibition remains.
- [01_PROJECT_BRIEF.md](../01_PROJECT_BRIEF.md), section 9.3 gender row and section 10.2 BRF-31: the same narrow employment/released-statistics exception.
- TASKS.md, S4-T02 and S4-T10, and [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md), slice S4 and its Public-split risk row: align the guards. New S4-T13 owns the field and draw, following S4-T11's calibration reader; S5-T11 owns released gender and attacks, following S4-T13, S5-T02 and S5-T03. S5-T04 integrates it before export.
- AGENTS.md and CLAUDE.md status and rule 10; documentation index. Earlier decisions remain unchanged as historical records; this record governs the exception.

## Open implementation dependencies

The real employment format's gender codes and the calibration table's declared shape must be supplied to the owning task without publishing private values. Until the table is present there is no draw. No category or share is guessed here.

## Sources and change control

The owner's decision of 2026-11-15 supplied in the full task brief; decisions 0022 and 0023; decision 0036's aggregate-table access rule; the pack passages above. No calibration values were read or restated. A material change needs a further owner decision; all other privacy and disclosure controls remain unchanged.
