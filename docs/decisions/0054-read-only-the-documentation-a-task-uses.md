# Decision 0054: Read only the documentation a task uses

| | |
|---|---|
| Status | Accepted, 2026-11-18 |
| Date | 2026-11-18 |
| Owner | The owner |
| Decided by | The owner's decision of 2026-11-18, which approved the proposed wording of rule 42, under AGENTS.md rule 46 |
| Amends | Rule 42 of AGENTS.md and CLAUDE.md, and their status lines; the accepted-record sentence and the Decision records table of docs/README.md |
| Purpose | Point the reading that rule 42 requires at the parts of a new library that a task actually uses, and make that reading visible to the reviewer. |
| Read first | AGENTS.md rules 42 and 46; [docs/REFERENCE_NOTES.md](../REFERENCE_NOTES.md); [web/REFERENCE_NOTES.md](../../web/REFERENCE_NOTES.md) |

## Context

Before this decision, rule 42 said: "Read current official documentation before using libraries newer than most training data, especially MapLibre GL JS 6, deck.gl 9.4, DuckDB 2.0, PostgreSQL 18 and the current Claude API." The rule could be read as a reason to read all of a library's documentation, or every listed library's, before a task. The owner was asked whether reading only the relevant documentation would make the work more accurate without losing quality, and approved the proposed wording.

## Decision items

1. **Rule 42 reads:** "Before using a library newer than most training data (for example MapLibre GL JS 6, deck.gl 9.4, DuckDB 2.0, PostgreSQL 18, the current Claude API), read only the current official documentation for the parts the task uses, and confirm exact pins and written retreat pins at slice S1. Each brief names the documentation pages it used (decision 0054)."
2. **Only what the task uses is read.** That means the calls, options, behaviours and pins the task touches. It is taken from the current official documentation, or from a documentation service that names the version it serves. A library the task does not use is not read for it.
3. **The brief names its pages.** Every brief for a task that uses such a library names the pages and sections it used, with the version and the date read, so a reviewer can see a gap. A reviewer who finds a used call, option or behaviour with no named page reports it as a finding.
4. **Nothing else changes.** Current official documentation is still required for everything a task uses. The reference notes keep their form and their READ, OBSERVED and dated rows. Pins and retreat pins are confirmed as before. No check, review or gate is removed.

## Consequences

Briefs carry less unrelated text, and what they carry is the documentation the change depends on. A reviewer can check a brief's named pages against the calls in the diff.
