# Rules for coding agents

| | |
|---|---|
| Status | Draft v0.3, amended by decisions 0016 and 0017 on 2026-11-12 |
| Date | 2026-11-12 |
| Owner | albarami |
| Purpose | Give every coding agent the binding safety, accuracy, workflow and evidence rules. |
| Read first | [docs/README.md](docs/README.md) and the documents for the assigned task |

## In brief

1. Read [docs/README.md](docs/README.md), [TASKS.md](TASKS.md), your slice in [docs/14_IMPLEMENTATION_PLAN.md](docs/14_IMPLEMENTATION_PLAN.md), and every document named by the task before changing anything.
2. Keep `AGENTS.md` and `CLAUDE.md` byte-identical. Edit both in the same change and verify their bytes match.

## Data, public-repository and boundary rules

3. Use fully synthetic custodian-type records only. Every company and person is invented; no real custodian record, field, file, count or parameter is ever read.
4. Simulate mobility, footfall, traffic and geofencing locally. Never contact a telecom operator or use a real mobility feed.
5. Cite every Public input with publisher, dataset or page, licence and retrieval date; preserve its hash in the source registry.
6. Keep provenance (Public, Synthetic, Simulated, Suppressed) separate from evidence status (Observed, Inferred, Still to test). "Not measured" is a coverage label, not an evidence status.
7. Give every number provenance and lineage. A fact without a complete source chain is not a fact: fail its build, chip and claim validation.
8. Never invent an attribute for a real named place or business. An `area` subject accepts Public, Synthetic, Simulated and Inferred slots; `place_public` and `fdi_project` accept Public slots only; a named synthetic firm accepts Synthetic slots only and is never placed at a real address. No other subject accepts a Synthetic or Simulated slot.
9. Use visibly synthetic identifiers that never imitate real registrations, establishments or personal identifiers. Fail on real-name collisions and on bare digit runs of exactly eight or eleven digits.
10. Add no nationality, sex or gender attribute, dimension or proxy on the synthetic or protected records or on anything derived from them. Official figures split by sex or nationality appear only as Public facts with source and year, on the source's own geography and categories, and are never joined to a synthetic record, used to segment synthetic records, apportioned to a drawn area or combined with a protected figure.
11. The product must never import custodian code or reach `data/vault/`. Only a verified release crosses from the custodian plane to the product plane.
12. Do not weaken privacy invariants, security controls, their tests, attack sizes or tolerances. No fallback is allowed for sandbox enforcement, store parity or any security check. Evaluate privacy parameter sets A and B only inside the custodian plane and export exactly one selected set's protected tables. Never tune a privacy rule to make an area look finer. A window is never exported under two treatments (PRV-120). `window_key` is the SHA-256 of canonical JSON holding the protected `period` and the four name-ordered `{name, sha256}` pairs for `business_register.v1`, `employment.v1`, `residence.v1` and `wages.v1`, using each feed's manifest `feed_sha256`; nothing else enters it. Continuous integration checks the export register alone: existing lines stay unchanged, with one `protected_sha256` per `window_key` and one `window_key` per `world_seed`. A freeze is refused on either uniqueness conflict; after a freeze, a change of rules version, exported set, treatment code or world generator requires a new `world_seed` and a new build before another freeze. `./eii freeze` is run twice with no new flag: the first run writes the bundle, checksum list and pending `freeze.json` and appends the register line; after normal merge, the second run from the containing base-branch commit builds and verifies the application archive, writes its checksum and marks `freeze.json` complete. For a frozen release only, install and start refuse with exit 7 unless the installed application's register holds the line and `freeze.json` says complete; the remedy is to finish the freeze, not change the seed. No signed receipt file is added.
13. Keep `data/vault/`, every folder that git ignores or does not track, and every path outside the repository off-limits. Tests may use only their documented repository, cache and temporary paths.
14. Put no secret in a file, log, ledger, brief, prompt or error. Read secrets only from the environment; never commit `.env`.
15. Write no private path, personal name, e-mail address, confidential plan, realistic identifier or named existing product comparison. Public data attribution is required and is not a comparison.

## Accuracy, models and screen rules

16. No model ever calculates. Every displayed number comes from deterministic, tested code in `eii_core.calc`, the release build, or a fixed application-schema read function listed by the data contracts and covered by tests. Nothing else computes, rounds or compares a number.
17. Comparisons, rounding, ranking and selection of numbers are calculations too. Models never perform them; code returns comparison facts for catalogue slots.
18. No model writes SQL, Cypher, another query, a tool argument outside its closed schema, or a number. Numeric arguments come only from closed schema values, typed user inputs or returned facts.
19. Apply the sanad rule: every fact resolves through fact → release table → method and version → source, licence, retrieval date and hash.
20. Never weaken the accounting gate. Check sources, assumptions, invention, scope and limits before display; fall back to the template writer and log failure.
21. No model-written prose reaches the screen. Models select and order catalogue claims, components, fragments, questions and stage directives; application-owned templates render every word.
22. Keep claim, component, fragment and question catalogues closed, versioned and typed. Reject unknown keys, properties, wrong fact slots and invalid layouts; one repair, then template fallback.
23. Render every numeral only through the Fact chip family. Build-time scans cover templates; do not substitute a run-time scan of model prose for structural prevention.
24. Never claim real custodian data, a Synthetic or Simulated fact about a real place, a Simulated or Synthetic footfall figure attributed to a named building or business, certified or formal privacy, inferiority of an existing public service, ministry endorsement or operation, a revenue/demand/success forecast, or lookup of a firm, owner or individual.
25. Give no go/no-go verdict, probability or confidence claim. A ranking, fit or suggestion is shown only as the output of tested code over criteria the user can see and change, with its rank-stability sentence, never as advice to act. Show evidence, limitations and the cheapest next test.

## Offline typed-decision gateway

26. Keep `gateway/` (`eii_gateway`) behind the stage only, imported only by tooling under `evals/` and `scripts/`; nothing under `core/`, `custodian/` or `product/` imports it or reads its settings.
27. Default `EII_DECISION_PROVIDER` to `none`. Every gate, the guided story, `./eii up`, preflight and freeze must work with provider `none` and no network.
28. A gateway answer is decision evidence only: never a fact, number, privacy decision, gate, refusal, tool argument, recommendation, Arabic approval or authority.
29. Never send visitor-typed text, real custodian data, real identifiers, credentials, real company questions or text from another project.
30. Use only the five closed classes: `spine_match`, `router_miss_finder`, `brief_second_reader`, `question_route` (shadow, team questions only) and `string_parity` (experiment first).
31. Gateway results may only order human review, flag a report, or become a deterministic rule/test after human confirmation. `brief_second_reader` is advisory and raise-only.
32. Store offline decision records under `evals/typed_decisions/runs/`. There is no `app.decision_record` table and no run-time gateway call in version 1.

## Workflow and evidence

33. Use one task per branch and pull request, with Conventional Commits. Change only the task's scope and update affected documents in the same pull request.
34. Name a senior expert persona and a strict reviewer persona for every task, and log both with the skills used.
35. Builder and reviewer must come from different makers. The reviewer edits nothing and returns APPROVED or REJECTED with file, line, defect and exact fix for every finding.
36. Run tests and record real exit codes. Never hide failure with `|| true`, `continue-on-error`, a missing pipefail setting, retries, skips or refreshed baselines.
37. Give every guard a planted violation. Write a failing test first where practical, then implement and prove the same test passes.
38. Record commands, full commit hash, counts, seeds, environment and evidence in [PROGRESS.md](PROGRESS.md). Append corrections; never rewrite an earlier evidence row.
39. Record unresolved decisions, assumptions and random failures in [OPEN_ITEMS.md](OPEN_ITEMS.md). A green re-run alone does not close a random failure.
40. Push one at a time. Never push to the base branch and never force-push. Follow the task's review gate before merge.
41. Use the top model only for architecture, privacy/security rules, final disagreement rulings, hard debugging and phase reviews; use a strong mid-tier model for most planning, building and review, a fast cheap model for mechanical work, and other makers for independent review. Keep agent counts lean.
42. Read current official documentation before using libraries newer than most training data, especially MapLibre GL JS 6, deck.gl 9.4, DuckDB 2.0, PostgreSQL 18 and the current Claude API. Confirm exact pins and written retreat pins at slice S1.

## Skills and personas

43. Use every installed skill that fits. Where a tool lacks one, the lead must put its rules in the task brief.

| Kind of work | Required skills or equivalent rules |
|---|---|
| Start of any task | `project-orientation`, `task-standards` |
| Hard decision or design | `al-muhasibi`, `superpowers:brainstorming` |
| Planning | `superpowers:writing-plans` |
| Building | `superpowers:test-driven-development`, `superpowers:executing-plans` or `superpowers:subagent-driven-development`, `superpowers:using-git-worktrees` |
| Failure or bug | `superpowers:systematic-debugging` |
| Interface | `frontend-design-pro`; `dataviz` for every chart; `design-audit` as gate |
| Assistant and model | `claude-api`; verify every API statement |
| Facts, data and statistics | `sanad-provenance` |
| Review | `strict-reviewer`, `code-review`; `security-review` for security changes; `superpowers:requesting-code-review`, `superpowers:receiving-code-review` |
| Before claiming completion | `superpowers:verification-before-completion`, `muhasabah-gate` |
| Git and GitHub | `github-flow`, `superpowers:finishing-a-development-branch` |
| Parallel work | `superpowers:dispatching-parallel-agents` |

## Commands and information locations

44. Today run only these commands from the repository root: `./eii test` (`./eii test --seed N` repeats a run with a given seed), `./eii preflight` (it only probes), `./eii up` (with `EII_RELEASE_DIR` unset it refuses and exits 4), `python3 scripts/check_docs.py`, `python3 scripts/check_tree.py`, `uv lock --check`, `uv run --locked python -m unittest discover -s scripts/tests -p 'test_*.py' -v`, `uv run --locked ruff check .`, `uv run --locked ruff format --check .`, `uv run --locked mypy`, `uv run --locked python scripts/check_versions.py`, `uv run --locked ruff format .` (it changes files; run it only to apply the formatter) and, only after a change to a `pyproject.toml`, `uv lock`; and these from `web/`: `npm ci`, `npm run build`, `npm run check`, `npm run check:hosts:dist`, `npm run check:dev`, `npm run test:checks`, `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run format` (it changes files; run it only to apply the formatter) and, only after a change to `web/package.json`, `npm install --package-lock-only`. `./eii db-up` and `./eii db-down` start and stop the project's database service and are run only when the task's brief says so. `./eii down`, `./eii build-public`, `./eii build-world`, `./eii build-release`, `./eii load-release` and `./eii freeze` are placeholders that exit 1 and are never claimed to work.
45. Use pinned command behaviour: preflight only probes; only `db-up`/`db-down` start/stop the database; `up` never starts one or reloads over a mismatched schema.

| Information | Canonical location |
|---|---|
| Scope and prohibited claims | [docs/01_PROJECT_BRIEF.md](docs/01_PROJECT_BRIEF.md) |
| Planes and stack | [docs/02_ARCHITECTURE.md](docs/02_ARCHITECTURE.md) |
| Schemas and application DDL | [docs/03_DATA_CONTRACTS.md](docs/03_DATA_CONTRACTS.md) |
| Public sources and licences | [docs/04_PUBLIC_DATA_PACK.md](docs/04_PUBLIC_DATA_PACK.md) |
| Methods and calculation examples | [docs/07_ECONOMIC_METHODS.md](docs/07_ECONOMIC_METHODS.md) |
| Assistant and catalogues | [docs/09_AI_ASSISTANT.md](docs/09_AI_ASSISTANT.md) |
| Tasks and slices | [TASKS.md](TASKS.md), [docs/14_IMPLEMENTATION_PLAN.md](docs/14_IMPLEMENTATION_PLAN.md) |
| Tests and evidence | [docs/12_TESTING_AND_QUALITY.md](docs/12_TESTING_AND_QUALITY.md), [PROGRESS.md](PROGRESS.md) |
| Vocabulary, open decisions and amendments | [docs/GLOSSARY.md](docs/GLOSSARY.md), [OPEN_ITEMS.md](OPEN_ITEMS.md), `docs/decisions/` |

## Open questions and assumptions

46. Raise unresolved choices instead of guessing. Material amendments need a new decision record, never a silent edit to an approved decision.

## Sources

47. The linked pack and its accepted decision records are the build context. No statement in these rules establishes that the planned product exists or passes a gate.
