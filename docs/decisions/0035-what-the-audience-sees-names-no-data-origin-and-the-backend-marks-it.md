# 0035 — What the audience sees names no data origin; the backend marks it

| | |
|---|---|
| Status | Accepted, 2026-11-15 |
| Date | 2026-11-15 |
| Owner | albarami |
| Decided by | The owner, in the task brief of 2026-11-15 |
| Amends | Audience origin-display clauses of the pack, including AGENTS.md and CLAUDE.md rules 24 and 25; backend marker contracts; the removal tasks listed below |
| Purpose | Remove audience data-origin labels while retaining explicit backend origin, complete lineage and method honesty. |
| Read first | [01_PROJECT_BRIEF.md](../01_PROJECT_BRIEF.md) Honesty position and reading guidance; [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md) Explicit backend origin — decision 0035; [AGENTS.md](../../AGENTS.md) rules 6, 23 to 25 and 46 |

## Context

The pack previously required visible provenance words, textures, an origin notice and watermark, and the label “estimate on simulated inputs”. The owner now reserves the explanation of generated data to himself. The change concerns audience presentation; it does not make generated figures Public or change what any subject may carry.

## Decision

1. Nothing the audience sees names data as synthetic, simulated, generated, sample or demo as an origin label. This includes screens, cards, captions, legends, tooltips, accessible names, badges, watermarks, exports and their filenames and column headings, URLs, assistant answers, template-writer text, voice speech, guided stories, the gallery, the case C3 and C4 files and the runbook's visible text. The owner tells the audience himself which data is generated. Provenance-class words are not rendered; the former origin notice, watermark and origin legend are removed.
2. Method honesty stays: the interval and backtest, stated error, rank stability and “how sure”, `NO_DATA`, `CARRIED_FORWARD`, reliability, small-cell suppression, low/middle/high cases and main drivers, base-rate counts and period, and visible editable scenario assumptions. A withheld state and its reason remain visible. This decision does not remove a limitation by calling it an origin mark.
3. Every generated record, table, file and release carries an explicit backend origin field whose value says `synthetic` or `simulated`, with the generator's name and version, in the data contracts, database and ledgers. The provenance classes Public, Synthetic, Simulated and Suppressed remain in contracts and code. Their calculation and the separate evidence-status field remain unchanged. Audience exports omit origin labels; their backend files and ledger metadata still carry the marker.
4. No invented figure is presented as sourced from an outside publisher it does not have. A visible source chain shows the method and producing pipeline's name and version. Public inputs keep their true attribution and lineage. No generated figure is described as official, measured, observed from a real register or coming from a ministry. Rule 24's subject and prohibited-claim restrictions remain; rule 25 loses only the “estimate on simulated inputs” label. No model writes prose or calculates; source-chain and accounting validation stay mandatory.
5. The standing review check in [15_REVIEWER_CHECKLIST.md](../15_REVIEWER_CHECKLIST.md), Standing audience-origin check — decision 0035, requires a script over built screens, templates, catalogue texts and exports to find no visible origin word. The check includes both languages and the audience surfaces of item 1; planted visible labels fail, and missing backend markers fail separately. It is found by script, not by eye. S3-T19 is the later implementation task; no script or test is implemented by this record.
6. This record supersedes earlier pack clauses only insofar as they require audience origin words or origin marks, including the earlier provenance display and estimate-label decisions. It does not rewrite their history. The amended current documents are listed below; all their technical class names still mean backend provenance. No privacy rule, gate, attack size, tolerance or security control changes.
7. Removal starts with the first map in slice S3, then proceeds in slice order: S3-T18, S6-T26, S7-T21, S8-T11, S9-T07, S10-T07 and S11-T08, with script task S3-T19. Each task removes its slice's origin labels and adds absence tests while checking backend markers and preserved method honesty. Slices S4 and S5 build backend data, not audience marks: their existing contract and manifest tasks carry item 3. Task dependencies and exact scopes are in [TASKS.md](../../TASKS.md) and [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md), the corresponding slice sections.

## Evidence

The owner's decision in the full task brief dated 2026-11-15 is the authority for items 1 to 7. Existing pack text supplies the passages being amended, not evidence that the product or the new absence script exists or passes.

## Consequences

Audience labels change; backend origin becomes explicitly inspectable at every generated level. Complete source chains and actual Public attribution remain. The owner supplies the audience's explanation of which data is generated. An origin-free screen is not permission to imply official data or measurement. Future implementation changes require their normal tests and independent review.

## Amended passages

- Document 05, SYN-09 and SYN-81: manifest lineage, case-file source access and backend markers replace audience Synthetic marks (items 1 to 4).
- Document 06, PRV-60 and PRV-126: backend movement and pay-band origin markers replace visible Simulated marks; ranges and stated assumptions remain (items 2 and 3).
- Document 07, In brief, C25 Never say, C32 Provenance and status, MTH-104, MTH-106, and section 6 sales/revenue and differences-between-releases rows: remove origin labels, retain backend markers and honest method limitations (items 1 to 4).
- Document 08, BE-111 and BE-122; GLOSSARY, People present by pay band, Stage and User scenario: backend markers replace visible marks and the Stage watermark is removed (items 1 to 4).
- Document 09, Open points from decision 0022, marks/AI-31 point; document 10, Open questions and assumptions, live-traffic provenance point: close the origin-mark questions while retaining the strength cap and provider attribution (items 1, 3 and 4).
- Document 10, FE-120 and FE-128; document 11, In brief, DES-04, DES-185, DES-195 and DES-208; document 16, Scene 4 Appears: explicitly remove the remaining audience origin words and textures, retaining method and withheld-state information (items 1 to 4).
- Document 14, PLN-19, S3-T09, slice S6 gate, slice S8 Scope, section 20 never-cut list and both OI-07 passages: backend markers replace current visible-origin obligations; retired-firm marks are explicitly historical (items 1 to 4 and 6).
- Decision 0036 item 3: rule 25 display requirements agree with the removal of the estimate origin label and retention of backend metadata (items 3 and 4).
- AGENTS.md and CLAUDE.md: Status; rules 24 and 25 (rule 33 changes under decision 0039).
- Document 01: audience-origin policy, capability and acceptance clauses, Honesty position and reading guidance, prohibited-claim estimate clause and visible mark requirements.
- Document 03: Explicit backend origin — decision 0035.
- Document 09: audience-origin policy, fact rendering, estimate family and template/caveat bindings.
- Document 10: audience-origin policy, shell, chips, layers, exports and automated provenance audit.
- Document 11: audience-origin policy, provenance language, Fact chips, standing marks, fixed sentences, storyboard and design audit.
- Document 12: audience-origin policy and tests that previously required a visible origin mark, preserving all method and privacy assertions.
- Document 15: audience-origin policy, prohibited-claim estimate clause and Standing audience-origin check — decision 0035.
- Document 16: audience-origin policy, scene wording, checklists and prepared answers.
- TASKS.md and document 14: removal tasks, dependencies and backend implementation obligations; docs/README.md: decision index.

- Document 06: PRV-122 (items 1–4 and 6; L-604).
- Document 07: MTH-58; C33 Site demand and revenue estimate; 6. Method eligibility and evidence limits; Open questions and assumptions (items 1–4 and 6; L-604).
- Document 12: 2. Test map by plane; TST-11; TST-14; TST-214; TST-230 (items 1–4 and 6; L-604).
- GLOSSARY: Evidence card; Evidence drawer; Standing strip (items 1–4 and 6; L-604).
- Document 08: BE-123; 6.2 Tool contracts; 7. Playbooks and the template writer; 8.1 Endpoints; BE-85; BE-119; 15. Tests each module ships with (items 1–4 and 6; L-604).
- Document 15: 4. Verdict format (items 1–4 and 6; L-604).
- Document 01: 6. Version 1 capabilities; BRF-19; BRF-92; BRF-93; 6.5 Build order; 7. The flagship journey (narrative by form) (items 1–4 and 6; L-604).
- Document 03: DAT-161; 9. The fact object (items 1–4 and 6; L-604).
- Document 02: ARC-137; ARC-139; 11. Quality attributes and architectural risks (items 1–4 and 6; L-604).
- Document 09: In brief; 5.1 Claim and component families added for version 1; AI-118; AI-124; AI-136; 7. Refusal and caveat templates; AI-88; Open questions and assumptions (items 1–4 and 6; L-604).
- Document 11: DES-165; DES-166; DES-167; DES-46; DES-209; DES-212; DES-66; DES-72; 9.3 Standing marks withdrawn by decision 0035; seat badge retained; DES-93; DES-95; DES-96; DES-97; DES-177; DES-178; 10.13 Fixed sentences of the version 1 families; DES-198; DES-199; DES-201; DES-202; DES-204; DES-115; DES-145; DES-154; 16. Design audit gates; Open questions and assumptions (items 1–4 and 6; L-604).
- Document 10: 3.1 Folders; 4.1 Shell and session; FE-116; FE-117; FE-126; FE-131; FE-132; 6. Map layers; FE-81; 13. Testing (items 1–4 and 6; L-604).
- TASKS.md: S1-T11; S3-T09; S3-T12; S6-T08; S6-T16; S6-T17; S6-T04; slice S6 gate (items 1–4 and 6; L-604).

- Document 10: FE-137; FE-144; 6. Map layers, Requested or drawn area row: solid treatment and traffic dash outline carry no origin-class name (item 1).
- Document 11: DES-200; DES-207; DES-08; DES-50; DES-63: remove class-named styles, define the traffic dash outline and retain traffic motion (items 1 and 2).
- Document 11: In brief, animation bullet; DES-190: reserve dots and dashes for layer textures and the withheld-state hatch without an origin meaning (items 1 and 2).
- Document 11: 16. Design audit gates, Provenance row: absence of audience origin classes, retained suppression and verified backend markers (items 1 to 3).
- GLOSSARY: Estimate on simulated inputs: required backend caveat key, no audience label and no rendering (items 3 and 4; L-604).
- Document 07: C33 Site demand and revenue estimate, Limits and wording, Allowed sentence: withdraw the origin-label prefix, retaining the cases and drivers (items 1 and 4).

- Document 11: DES-06; DES-54; DES-100: opening treatment and point shapes carry no origin meaning; the drive-time outline retains moving dashes and loses its origin-class name and legend sentence (item 1).
- Document 10: FE-103; FE-105; FE-137 fixture: remove origin-class style names and keep fixture provenance in backend metadata (items 1, 3 and 4).
- GLOSSARY: Trap: clarify that the planted pattern's origin is backend-only, not an audience label (items 1 and 3).

- Document 07: C11 and C16, Limits and wording: criterion classes stay in backend metadata; format-not-a-finding limitations remain (item 3).
- Document 10: 6. Map layers, Released units and Ranked or similar areas rows: distinguish magnitude class and replace the origin-class outline with DES-175's data outline (item 1).
- Document 11: DES-172; DES-175; DES-181; DES-211; DES-213: remove visible class lines, retain chips and series lines, and use the data outline of section 9.1 for ranked areas (item 1).
- Document 11: DES-110; DES-172; DES-180: remove Public from chip/count style names; backend provenance remains (items 1 and 3).
- Document 11: DES-91: the solid joining line has no origin meaning; the links' Public class stays in backend metadata (items 1 and 3).
- Document 11: DES-13; DES-51: visual mappings and reduced-motion distinctions use magnitude classes and states, never origin classes (items 1 and 2).

- Document 11: DES-182; 11. The guided story, Scene 1 — The Qatari day, hour by hour, "On screen" row: no origin texture on Synthetic figures or on the crowd-density hero layer (items 1 and 3).
- Document 10: In brief, the bullet on forecasts, base rates, the site estimate and scenarios: an estimate shows its cases and main drivers with no visible origin label (items 1 and 6).
- Document 16: the answer to "Is the pay of the people present what they spend?": the figure's origin mark is backend metadata (item 3).

- Document 07: C10, C12, C15, C19, C20, C21, C25, C26, C27, C30, C32 and C35, Limits and wording, Allowed sentences: remove audience origin words while preserving fact slots and method limitations (item 1).
- Document 06: PRV-82; section 12, privacy receipt `statement`: remove the origin word from fixed audience sentences, retaining their limitations (item 1).
- Document 08: section 6.2 Tool contracts, `what_changed` Outputs; document 09: section 3, `where_to_grow` and `branch_check` limits; document 10: FE-113: point to `synthetic_change` in document 11 section 10.13 instead of repeating stale caveat wording (item 1).
- Document 11: DES-109; DES-175; section 11, Scene 4 Motion; document 16: Scene 4 Tap: remove Public from the context title and criteria-switch label; the switch's filtering rules remain unchanged (item 1).

## What would change this decision

A further owner decision changing audience disclosure, backend markers or the presentation rule, recorded and reviewed as a new amendment under rule 46.

## Open questions and assumptions

No new owner choice is inferred. Exact backend field placement and script implementation belong to the named build tasks, not this documentation change.

## Sources

- The owner's task brief of 2026-11-15, Decision 0035, items 1 to 7 (project record of this assignment).
- AGENTS.md rules 6, 19 to 25 and 46; the pack sections listed under Amended passages.
