# 15 — Reviewer Checklist

| | |
|---|---|
| Status | Draft v0.2, corrected after independent review on 2026-11-11 (see PROGRESS.md); amended on 2026-11-12 by [decision 0015](decisions/0015-review-rounds-and-the-scope-of-repository-checks.md) |
| Date | 2026-11-12 |
| Owner | albarami |
| Purpose | The checklist and verdict format an independent reviewer applies to one commit before it may merge. |
| Read first | [12_TESTING_AND_QUALITY.md](12_TESTING_AND_QUALITY.md), [14_IMPLEMENTATION_PLAN.md](14_IMPLEMENTATION_PLAN.md), [AGENTS.md](../AGENTS.md) |

## In brief

- Every task ends with an independent review by a reviewer from a different maker than the writer.
- The reviewer reviews exactly one commit, applies every check in sections 2 and 3, and returns APPROVED or REJECTED in the fixed format of section 4.
- The reviewer changes no file. A REJECTED verdict always gives, for each finding, the file, the line, what is wrong and the exact fix.
- APPROVED means no open finding. There is no "approved with comments".
- Round 1 is the full review. A later round still answers every check but may reject only for the four kinds of finding in REV-39; every other valid point is a proposed open item, closed before the slice gate.
- Evidence counts; assurances do not. A check passes only when the reviewer has seen its evidence.

## 1. Rules of the review

| ID | Requirement |
|---|---|
| REV-01 | The reviewer must come from a different maker than the writer of the commit. The verdict names the reviewer by maker and model only, never by a personal name. |
| REV-02 | The review covers exactly one commit, named by its full 40-character hash, and that commit must be the head of the task's pull request. A verdict on any other commit is void. |
| REV-03 | The reviewer changes no file: no edit, no commit, no push, no formatting fix, no baseline update. The reviewer may run commands that leave tracked files unchanged, such as `./eii test` and `python3 scripts/check_docs.py`. |
| REV-04 | The reviewer reads, before judging: the task and its acceptance criteria in [TASKS.md](../TASKS.md), the full diff against the base branch, the evidence entries in [PROGRESS.md](../PROGRESS.md) for this commit, and the documents the task touches. |
| REV-05 | Every check in sections 2 and 3 receives PASS, FAIL or N/A with its evidence. N/A needs one sentence saying why the check does not apply to this commit. |
| REV-06 | One FAIL makes the verdict REJECTED. APPROVED requires every check to be PASS or a justified N/A, and no finding. In a round after the first, a check is FAIL only for a finding of one of the four kinds in REV-39; any other valid point is listed under PROPOSED OPEN ITEMS and does not make a check FAIL. A design-audit Minor, as defined in [11_DESIGN_DIRECTION.md](11_DESIGN_DIRECTION.md) section 16, is recorded in the design audit with an owner and a target slice and is not a verdict finding. A design-audit Blocker or Major is a FAIL of that slice gate and a verdict finding. |
| REV-07 | Each finding must cite the check or the requirement it breaks. A preference is not a finding. A reviewer who thinks a settled decision is wrong raises it with the lead as a proposed open item, not as a finding. |
| REV-08 | After a REJECTED verdict, the writer fixes, the lead re-runs the evidence, and the reviewer reviews the new commit. Round 1 is the full review. In every later round the reviewer still answers every check, within the limit of REV-39. |
| REV-09 | The verdict is posted on the pull request, and the lead copies it unchanged into [PROGRESS.md](../PROGRESS.md). |
| REV-39 | In a round after the first, a verdict finding may only be one of four kinds: an earlier finding that is not fixed; a defect in, or caused by, lines changed since the commit the reviewer last reviewed; a secret, real data or a private path anywhere in the pull request; an acceptance criterion of the task that is not met. Every other valid point goes under PROPOSED OPEN ITEMS, outside the verdict. The brief for round 1 says so, so that everything the reviewer can find is reported in round 1. If a reviewer puts a point outside the four kinds into the verdict, the lead asks an advisor once, and the advisor's ruling on the kind of the point stands. The same limit applies when a plan is reviewed again. |
| REV-40 | Every verdict finding is fixed before the merge. If round 3 is REJECTED and the lead judges its findings valid, the findings are fixed by a stronger builder from a maker other than the reviewer's, and the same reviewer gives up to two confirmation reviews under REV-39. If the second confirmation review is still REJECTED, the task is blocked for the owner and is not merged. |
| REV-41 | Valid proposed open items are entered in [OPEN_ITEMS.md](../OPEN_ITEMS.md) and closed in one follow-up pull request per slice, before that slice's gate review. The slice reviewer checks that none is left open. |
| REV-42 | The repository's own checks (the tree check, the documentation check, the hooks, the commit guard and the CI scripts) are judged against mistakes in three settings: a fresh clone, the CI runner, and a checkout used through the documented commands, including ordinary differences between machines such as personal git configuration, locale or a linked path. Deliberate defeat of a check on one's own checkout (an index flag such as assume-unchanged, a replaced program, a race by a second local process) is outside their scope, and the generator sandbox is judged by what the sandboxed program can do, not by what a second local process could do to the launcher. A point that needs such tampering is a proposed open item, not a verdict finding. |

### 1.1 Order of work

1. Confirm the commit hash is the head of the pull request and that CI on it is green.
2. Read the task, its acceptance criteria and its scope in [TASKS.md](../TASKS.md).
3. Read the full diff. Read the diff of tests, CI configuration, lint configuration and thresholds first and line by line, because that is where checks get weakened.
4. Read the evidence entries for this commit in [PROGRESS.md](../PROGRESS.md) and compare each recorded command, exit code and hash with what CI shows.
5. Re-run `./eii test` and `python3 scripts/check_docs.py` where the machine allows it, and record the exit codes in the verdict.
6. Apply every check in sections 2 and 3, then write the verdict in the format of section 4.

## 2. General checks

| ID | Check | Evidence the reviewer looks for |
|---|---|---|
| REV-10 | Acceptance criteria met, with evidence | Each criterion of the task maps to a test or a recorded check, and that evidence is recorded for this commit as [12_TESTING_AND_QUALITY.md](12_TESTING_AND_QUALITY.md) section 6.3 requires. |
| REV-11 | Tests exist and pass by the lead's own run | A PROGRESS entry by the lead on this exact commit with exit code 0 for `./eii test` and the documentation check; CI green on the same commit; new behaviour has new tests, and each new guard has its planted violation. Skips are only the two standing skips allowed by TST-06. |
| REV-12 | Only in-scope files changed | `git diff --stat` against the base branch lists only files the task names or clearly needs; nothing under `data/`; no unrelated reformatting. |
| REV-13 | No placeholders, stubs or mock data standing in for real work | No `TODO`, `FIXME`, `NotImplementedError`, empty function bodies or fixed return values in delivered code; no hand-written release tables in place of the engine's output; no invented figures. A recorded model provider is allowed only as TST-116 declares it, while OI-01 is open. |
| REV-14 | No secrets or real data | gitleaks clean; no `.env` or key file committed; no real custodian record, field name, file name or count anywhere in the diff. |
| REV-15 | No check weakened | No lowered threshold, widened tolerance, removed or loosened assertion, reduced example count, new skip or expected-failure mark, new lint or type suppression comment, `continue-on-error`, automatic retry, or updated visual baseline or recording without an approved decision record. Review the diff of tests and CI configuration line by line. |
| REV-16 | Follows the approved plan and standards | The work matches the task in [14_IMPLEMENTATION_PLAN.md](14_IMPLEMENTATION_PLAN.md) and the standards in [AGENTS.md](../AGENTS.md); pinned names (tables, tools, commands, seats, slices, classes, configuration keys) are used exactly. Seat selection is the signed session cookie from the seat picker, and presenter routes require the per-session presenter token. Neither is an identity system. `./eii preflight` only probes. `./eii db-up` and `./eii db-down` start and stop the database. `./eii up` does not start a database. The staffing drive cut-off of 30 minutes is rejected on every other playbook. `./eii freeze` takes no new flag and is run twice as OPS-58 and OPS-63 specify. Its first run requires the recorded human review of the release: the reviewer's role, the date, and that the survival report and signed attack report were read. Its second run is from the base-branch commit containing the register line and completes `freeze.json`. |
| REV-17 | Documents updated | Every document the change affects is updated in the same pull request; [PROGRESS.md](../PROGRESS.md) and [OPEN_ITEMS.md](../OPEN_ITEMS.md) are current; a decision record exists for any choice the task made; `python3 scripts/check_docs.py` exits 0. |
| REV-18 | No security or data-handling problem | Secrets read from the environment only; the application role owns no table and has no SELECT on base tables of the `app` schema, reading through fixed functions with separate company and oversight return types; the oversight type carries no organisation identity, no question text and no brief text; no SQL or query text from the model; untrusted free text passed only inside tool results; generators run in the sandbox; logs and egress records carry no record-level data. |
| REV-19 | No settled decision reopened | Nothing on the dropped or later lists in [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md) is built, no component decision in [02_ARCHITECTURE.md](02_ARCHITECTURE.md) or `docs/decisions/` is removed or replaced, and the cut order in [14_IMPLEMENTATION_PLAN.md](14_IMPLEMENTATION_PLAN.md) is respected. A change needs an owner-approved decision record first. |

## 3. Project-specific checks

| ID | Check | Evidence the reviewer looks for |
|---|---|---|
| REV-20 | Every number carries provenance and lineage | Every new figure is a fact object with all pinned fields; its `lineage_ref` resolves to table, method and version, publisher, dataset, licence, retrieval date, file hash and release; the least-real rule is computed in code; provenance and evidence status stay two separate fields and never merge. Evidence status has exactly three values: Observed, Inferred and Still to test; Not measured is a coverage label. Every displayed number, including every comparison, is produced by deterministic tested code in `eii_core.calc`, by the release build, or by a fixed read function of the application schema that the data contracts list and the tests cover; the browser only formats the value it receives and computes no displayed number. A protected figure normally names one home family. The only ratio-statistic exception is the mean wage and the coverage, irregular and deployed-elsewhere shares: numerator and denominator come from columns of the same stored rows, and lineage names both families. A fact without a complete source chain is not rendered, is rejected by the validator and fails the release build; the evidence drawer is labelled "Source chain". |
| REV-21 | No numeral outside the Fact chip | The numeral lint passes with no disable comment for that rule; the provenance audit passes on every new screen and card. Model-written prose is absent from the rendered brief: every Observed and Inferred sentence matches a claim-catalogue template with valid slots, and every component instance is in the closed catalogue or the screen shows the playbook default; a Synthetic or Simulated fact whose subject is a real named place fails the check. The build-time template scan rejects numerals, number words, real place names inside `area` claim templates and go or no-go wording. The answer pipeline has five stages, first reading, watchfulness, striving, accounting and answer; the receipt on every answer shows the result of the five fixed accounting checks (sources, assumptions, nothing invented, scope, limits stated) under the label "Checked before display", and an answer whose gate fails is replaced by the template writer's default answer. |
| REV-22 | Privacy invariants untouched | No change to the partition, the two parameter sets, treatment or the audits unless the task is about them and carries a decision record; the closure, partition, dominance and stable-treatment tests and the attack suite pass at undiminished size. Both sets are evaluated in the custodian plane, but exactly one selected set's protected tables are exported. The Proof room may show survival figures for both sets and tables for the exported set only. Each contributor universe has one parent-linked partition family rooted in resolution-7 parents intersected with municipalities; released primitives are mutually exclusive treated leaf atoms and every within-family total is the exact sum of that family's treated leaves. No equality is required between families. Closure is proved by exhaustive structural checks over units, protected partitions and every area `make_area` can produce; at least 10,000 random pairs per release and parameter set are fuzz testing, not the proof. Version 1 exports one protected window and makes no consecutive-window claim. Cross-period complement fixtures and mover attacks are L4-only. No person-level protection is claimed for movement. A window is never exported under two treatments (PRV-120). `window_key` follows DAT-80 exactly. Continuous integration checks only the register: existing lines unchanged, one `protected_sha256` per `window_key`, and one `window_key` per `world_seed`. `./eii freeze` is run twice with no new flag. A frozen bundle can be installed or started only when the register inside the installed application holds its line and `freeze.json` says complete; otherwise exit 7. A build release without `freeze.json` is not checked. A register conflict needs the new seed and new build required by PRV-120; an incomplete or unlisted frozen bundle is remedied by finishing the two-run freeze, not by changing the seed. No signed receipt file is added. The attacker-view audit is evidence under a stated attacker and is never called a proof. The audit does not model what the layout tells about a population that failed a rule, such as a merged band, a pooled category, merged siblings, a withheld remainder or a reason code. OI-36 records that one typed attack per kind can miss another released instance. The complement step's two prepared requests differ by one published merged unit of at least two base cells. The prepared "Try to break it" regression proves application decline of named-entity pay, identical answers for two shapes snapping to the same units, the complement step through `POST /api/proof/scene` (PRV-119) where one manifest-listed fixture id selects two prepared requests, application decline of the typed phrase "the city minus this cell" separately from that call, and catalogue rejection of one invalid prepared repair with playbook fallback logged from the signed fixture identity; it makes no claim of general injection detection. Canaries are named on rendered proof surfaces only by scenario label. |
| REV-23 | Product never imports custodian | The import-boundary test passes; no import of `eii_custodian` in `product/` or in the product package metadata. |
| REV-24 | Bilingual parity of numbers | The English and Arabic views show the same fact identifiers and the same numerals; digits are Western in both languages; new Arabic strings are marked pending native review. |
| REV-25 | Public-repository safety | None of: an absolute local path, the name of a private individual (the owner handle in a document header is not one), an e-mail address, a real custodian record or field or file name, an internal plan of any ministry, a named existing product in a comparison, a ministry presented as supplier or endorser, a run of exactly eight or eleven digits (TST-142), a secret. Identifiers of the REV-28 forms are allowed. The registry of names that must not appear is a private patterns file outside the repository that `scripts/check_docs.py` loads when present; a recorded human review for implied inferiority or endorsement precedes each release. Every committed public file states its licence; files without a stated licence are fetched at build time, never committed. |
| REV-26 | Prohibited claims absent | No string, template, prompt or document says or implies that the POC uses real custodian data; that a Synthetic or Simulated figure describes a real place; that a simulated index is a named building's footfall; that the privacy engine is certified or formally private; that an existing public service is wrong or inferior; that the ministries endorsed or ran the system; that a revenue, demand or success forecast is given; or that any firm, owner or individual can be looked up. |
| REV-27 | AGENTS.md and CLAUDE.md identical | `cmp AGENTS.md CLAUDE.md` exits 0; the documentation check reports no agent-file failure. |
| REV-28 | Synthetic identifiers never imitate real ones | Every synthetic identifier uses exactly one of the five allowed forms: `SYN-E-` for an establishment, `SYN-L-` for a legal entity, `SYN-G-` for an employer group, `SYN-P-` for a person or `SYN-F-` for a salary file. No run of exactly eight or eleven digits is used as an identifier; the world build's collision check passes. |
| REV-29 | No invented attribute on a real named place | A real named place or business carries Public facts only; no synthetic firm sits in a real named building or is named beside a real one; no simulated figure is presented as a named place's footfall. |
| REV-38 | Typed-decision gateway absent from the serving plane | The typed-decision gateway is absent from the serving plane and from run time. The only allowed screen text is the Proof room lineage line, "N activity codes; review order machine-assisted; every mapping signed by a person." A score, a badge, a panel or a live call fails the check. The import-boundary test shows that `eii_product`, `core`, `custodian` and `web` do not import `eii_gateway`, and no run-time code reads `EII_DECISION_PROVIDER` or `JEV_PRO_API_KEY`. |

## 4. Verdict format

The verdict is plain text in exactly this shape. Every check from REV-10 to REV-29 and REV-38 appears once, in order.

```text
VERDICT: APPROVED | REJECTED
TASK: <task ID from TASKS.md>
COMMIT: <full 40-character hash reviewed>
REVIEWER: <maker and model of the reviewer>
CHECKS:
  REV-10 PASS <evidence>
  REV-11 PASS <evidence: command, exit code, run by>
  ...
  REV-29 N/A <why it does not apply>
  REV-38 PASS <evidence>
FINDINGS:
  F1 (REV-nn)
    File: <repository-relative path>
    Line: <line number or range>
    Wrong: <what is wrong, with the requirement it breaks>
    Fix: <the exact change, and the test or command that will prove it>
PROPOSED OPEN ITEMS:
  <none, or one line per valid point that is outside the verdict (REV-39, REV-42)>
```

In a round after the first, the block `EARLIER FINDINGS:` stands between `REVIEWER:` and `CHECKS:`, with one line per earlier finding: its number, `FIXED` or `NOT FIXED`, and the evidence.

| ID | Requirement |
|---|---|
| REV-30 | A REJECTED verdict must list at least one finding, and every finding must give the file, the line, what is wrong and the exact fix. "Improve", "clean up" or "consider" is not a fix. |
| REV-31 | An APPROVED verdict must read `FINDINGS: none`. |
| REV-32 | The fix must be specific enough that the writer can apply it without asking: name the change, and name the test or command whose result will show it is done. |

An illustrative finding (the path and line are examples, not files of this repository):

```text
  F1 (REV-21)
    File: web/src/cards/ResidentsCard.tsx
    Line: 57
    Wrong: the housing-split share is rendered as a raw string, outside the
           Fact chip, so it has no provenance mark (breaks REV-21).
    Fix: render the share through the Fact chip with its fact identifier,
         remove the raw string, and show the numeral lint and the
         provenance audit passing on this card.
```

## 5. Slice reviews and special cases

| ID | Requirement |
|---|---|
| REV-33 | A slice review covers the slice's final commit and every gate item of that slice in [12_TESTING_AND_QUALITY.md](12_TESTING_AND_QUALITY.md) section 5. Each gate item is listed in CHECKS with PASS or FAIL and its evidence, after REV-10 to REV-29 and REV-38. |
| REV-34 | For the slice S2 gate, the reviewer personally checks 20 randomly chosen stored public figures against their sources and lists each figure, its source link and the result in the verdict. |
| REV-35 | For the slice S5 gate, the reviewer first confirms that OI-37 is closed: a maker other than the one that last edited the privacy document reviewed the lead's last ten corrections to it (made on 2026-11-11 after the second confirmation review) and the review is recorded in PROGRESS.md. The reviewer also confirms the OI-36 layout-signal limit is stated. The reviewer adds attacks of their own to the attack suite through the lead; each new attack becomes a permanent test, and before APPROVED it must recover nothing from the protected release under both parameter sets; an attack that succeeds is a privacy defect that blocks the slice. |
| REV-36 | For a commit that changes only documents, REV-11 is met by `python3 scripts/check_docs.py` exiting 0, and REV-20 to REV-24 may be N/A with a reason; REV-25 to REV-27 always apply. |
| REV-37 | A gate item met by a technical alternative (allowed in slice S1) passes only if the alternative preserves the same user-visible capability, passes the same assertion and has an owner-approved decision record naming the alternative and the reason. No fallback is permitted for sandbox enforcement, store parity or any security check. |

## Open questions and assumptions

- ASSUMPTION: the verdict is posted on the pull request and copied into PROGRESS.md by the lead (REV-09), because the owner's method needs one durable record per task and the pull request is where the commit lives.
- There is no "approved with comments" (REV-06, REV-40): every verdict finding is fixed before the merge. A valid point that a later round may not reject for (REV-39), or that needs deliberate tampering (REV-42), is not a comment on an approval: it is entered as an open item and closed before the slice gate (REV-41). The owner decided this on 2026-11-12 ([decision 0015](decisions/0015-review-rounds-and-the-scope-of-repository-checks.md)); it replaces the earlier assumption that every round is a full review.
- Open items touching this document: OI-01 (recorded provider allowed while the key is absent), OI-09 (native Arabic sign-off is separate from this review), OI-13 (GitHub secret scanning and push protection), OI-14 (no run-time use of the typed-decision gateway before an approved route), OI-35 (which parameter set is exported; default A until the owner or a data owner decides, needed by the slice S1 gate), OI-36 (layout signals outside the acceptance model) and OI-37 (independent review before slice S5).

## Sources

- The binding project rules this checklist applies: [AGENTS.md](../AGENTS.md), [12_TESTING_AND_QUALITY.md](12_TESTING_AND_QUALITY.md) and [14_IMPLEMENTATION_PLAN.md](14_IMPLEMENTATION_PLAN.md). No external source was used.
