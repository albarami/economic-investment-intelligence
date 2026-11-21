# Decision 0076: Company web pages: search, fetch, review and storage

| | |
|---|---|
| Status | Accepted, 2026-11-20 |
| Date | 2026-11-20 |
| Owner | The owner |
| Decided by | The owner's decision of 2026-11-20, recorded in decision 0074 item 8, and the lead's S2-T48 design-review rulings of 2026-11-20 |
| Amends | Decision 0022 item 1 and document 04 PUB-03 only, on the narrow terms below; command documentation in PUB-01 and AGENTS.md and CLAUDE.md rule 44 |
| Purpose | Implement the approved company-web task without disclosing register files or widening other sources' host policy |
| Read first | Decision 0074 item 8; decision 0022 item 1; document 04 PUB-01, PUB-03, PUB-04, PUB-12 and PUB-86; TASKS.md S2-T48 |

## Context

Decision 0074 item 8 approves command-line web searches for financial-centre and register companies, followed by deterministic fetch and extraction and another-maker review. The lead's rulings on the design review settle the register-name disclosure, host scope and full-page storage. This record states those decisions; it claims no live capture or accepted field.

## Decision

1. **Register-name exception.** Decision 0022 item 1 is amended only to permit the company name, a public register value, plus the word "Qatar" as the query of a command-line web search run from the lead's shell. No other register field leaves that shell. The reviewer receives the matched company name, archived declared-block fragment, its source address and hash, and candidate fields, never a register row or file. Search returns result addresses only, never snippets. No model fetches, extracts fields or normalises addresses; deterministic code uses the shared transport under rules 16 and 18.
2. **Command.** Only the lead-shell form `./eii build-public --company-web` selects this source. Ordinary build-public never selects it. Search is keyless and visitor-readable; a single provider's host, terms and closed request contract must be reviewed and pinned before live use. This record admits no registration, paid access, access-control bypass or unverified provider.
3. **Scoped hosts.** PUB-03 is amended for `company_web` only: a run-scoped, uncommitted, hash-pinned host manifest reviewed in the lead's shell admits the run's hosts. Each company's exact reviewed URLs narrow that manifest further. A scoped transport context checks requests and redirects against that company's exact URLs. The static allow-list and all other sources' checks remain unchanged. A changed manifest invalidates its review; scope ends even after failure.
4. **Parser.** Extraction reads only a declared schema.org Organization or LocalBusiness JSON-LD or microdata block: name, PostalAddress address, url, and activity from isicV4, naics or a declared description in the source's words. An optional per-host selector must be lead-reviewed, hash-bound and uncommitted. Missing blocks are counted as `no_declared_block`; personal contexts and ambiguous blocks are refused. Matching uses the existing award-name normaliser; legal-suffix variants remain ambiguous. No activity-spine mapping is performed here.
5. **Storage.** Each fetched page is stored in the public cache with source address, retrieval date and SHA-256 and a provenance receipt. Store the complete upstream body in the uncommitted PUB-04 archive, including mixed-content pages and pages without a declared block; do not substitute a projection. Extraction reads only the declared block and reviewers receive only that fragment. Bind full-page and fragment hashes, original and final addresses, retrieval UTC, publisher, licence/basis and parser version. Readers select explicit reviewed hashes, never latest. Nothing of a fetched page is committed.
6. **Access and output.** Record per-host dated terms in the publisher's words and robots files, or "none found"; terms are a record, never a reuse gate. Robot checks, sign-in and paywalls stop a host without bypass. Keep a minimum two-second request interval, slower where required, and at most ten companies and three result pages per company. Company-level fields only: refuse personal fields, job titles, salaries, telephone/fax labels, e-mail addresses, person titles and runs of exactly eight or eleven digits before publication. Bind another-maker acceptance to the exact field/value, company, page, fragment and parser version and the reviewer tool, model and session run. Pending or rejected fields are not retained. The keyless provider, the two-second interval and the batch bounds are plan revision 2's F2 and F10 choices, adopted under the lead's ruling.
7. **Inputs and evidence.** Use both public-register inputs in the lead's shell, never the owner's workbook. Preserve registration and visibly prefixed licence namespaces and absent financial-centre numbers. Web fields never replace register-published fields; retain separate lineage and mark conflicts. Contribute retained names to the collision inventory. The lead owns live search, manifest review, fetch and independent field review, with reconciled counts and evidence E1–E5. Invented offline fixtures prove guards, not live acceptance criteria 1, 2, 4 or 7 of S2-T48.

## Consequences and change triggers

No other part of decision 0022 or PUB-03 is amended. No product or release schema is widened. Live runs wait for this build and S2-T36's live capture. Provider verification and refresh cadence remain lead-owned open work. Wider disclosure, model extraction, another source's dynamic hosts or different storage requires a new decision.

## Sources

- [Decision 0074](0074-company-level-fields-of-the-owners-company-workbook.md), item 8, recording the owner's decision of 2026-11-20.
- The lead's S2-T48 design-review rulings of 2026-11-20: F1–F4 and F6–F14 adopted; F5 requires full-page storage.
- S2-T48 implementation plan revision 2, F2 and F10: keyless provider, two-second minimum interval and batch bounds, adopted under those rulings.
- [Decision 0022](0022-real-register-companies-with-a-synthetic-world.md), item 1; [document 04](../04_PUBLIC_DATA_PACK.md), PUB-01, PUB-03, PUB-04, PUB-12 and PUB-86; [TASKS.md](../../TASKS.md), S2-T48.
