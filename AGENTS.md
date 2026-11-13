# Rules for coding agents

| | |
|---|---|
| Status | Draft v0.3, amended by decisions 0016, 0017 and 0019 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 |
| Date | 2026-11-13 |
| Owner | albarami |
| Purpose | Give every coding agent the binding safety, accuracy, workflow and evidence rules. |
| Read first | [docs/README.md](docs/README.md) and the documents for the assigned task |

## In brief

1. Read [docs/README.md](docs/README.md), [TASKS.md](TASKS.md), your slice in [docs/14_IMPLEMENTATION_PLAN.md](docs/14_IMPLEMENTATION_PLAN.md), and every document named by the task before changing anything.
2. Keep `AGENTS.md` and `CLAUDE.md` byte-identical. Edit both in the same change and verify their bytes match.

## Data, public-repository and boundary rules

3. Use synthetic custodian-type labour and residence records only. Every person is invented; the companies are the real ones of the public register, and their labour and residence records are synthetic; no real custodian record, field, file, count or parameter is ever read, except the calibration table of the owner's note, read only by the world build (decision 0022). Synthetic records are built only for the confirmed sources of decision 0023 item 12 (the employment records of private-sector individuals with their occupations and nationality group, the wages and the residence addresses, all attached to the register companies, and movement at the grain the pack plans: presence and movement by area and hour, with origin and destination); every other input is public data or a company's own input, and no synthetic data stands in for any other source.
4. Simulate mobility, footfall and geofencing locally. Never contact a telecom operator or use a real mobility feed; a published relative-busyness figure of a named venue is a Public fact, not such a feed. Simulate road traffic locally by default; the optional live traffic provider of decision 0019 is off by default, shows its flow tiles and traffic-aware drive-time areas with the provider's attribution, stores nothing of a response, and is never needed by a test, a gate, a command or the guided story.
5. Cite every Public input with publisher, dataset or page, licence and retrieval date; preserve its hash in the source registry.
6. Keep provenance (Public, Synthetic, Simulated, Suppressed) separate from evidence status (Observed, Inferred, Still to test). "Not measured" is a coverage label, not an evidence status.
7. Give every number provenance and lineage. A fact without a complete source chain is not a fact: fail its build, chip and claim validation.
8. Never invent an attribute for a real named place or business, except the synthetic labour and residence records attached to a register company (decision 0022). An `area` subject accepts Public, Synthetic, Simulated and Inferred slots; `place_public` and `fdi_project` accept Public slots only; a `register_company`, a real company of the public register, accepts Public slots and the employee count of its attached records, and its other labour and residence facts appear only in analyses released under document 06 and in its own seat (decision 0023 item 15). Named synthetic firms are retired. No other subject accepts a Synthetic or Simulated slot.
9. Use visibly synthetic identifiers that never imitate real registrations, establishments or personal identifiers. Fail on real-name collisions and on bare digit runs of exactly eight or eleven digits.
10. Add no sex or gender attribute, dimension or proxy on the synthetic or protected records or on anything derived from them. Nationality enters in two forms only (decision 0022): the synthetic worker records carry the nationality group in the format of the real records, and the register's establishment nationality is a company attribute; both may be used as dimensions of released statistics under document 06, and no other nationality attribute, dimension or proxy is added. Public figures split by sex or nationality appear only as Public facts with source and year, in the source's own categories, on their own geography, and are never joined to a synthetic record, used to segment synthetic records or simulated presence, or combined with a protected figure. A tabulated figure stays on the source's own geography and is never apportioned to a drawn area; whole cells of a published population grid may be summed over an area.
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
24. Never claim real custodian data, a Synthetic or Simulated fact about a real place, a Simulated or Synthetic footfall figure, or an estimate, share or score, attributed to a named building or business, certified or formal privacy, inferiority of an existing public service, ministry endorsement or operation, a forecast of the success of a venture, a forecast, estimate or base rate that tested code did not compute, or lookup of a firm, owner or individual. Showing a register company's public card and its employee count, under rule 8, is not a lookup (decision 0022); looking up an owner or an individual stays forbidden, and so do the other prohibited claims.
25. Give no go/no-go verdict, probability or confidence claim, and no advice to act. A ranking, fit or suggestion is shown only as the output of tested code over criteria the user can see and change, with its rank-stability sentence. A forecast is shown only with its interval from the backtest, its measured backtest error, its method and its source; an estimate with its low, middle and high cases, its main drivers and, while an input is Simulated or Synthetic, the label "estimate on simulated inputs"; a base rate with its counts and period; a user's scenario with every assumption visible and editable, never called a forecast. Show evidence, limitations and the cheapest next test.

## Offline typed-decision gateway

26. Keep `gateway/` (`eii_gateway`) behind the stage only, imported only by tooling under `evals/` and `scripts/`; nothing under `core/`, `custodian/` or `product/` imports it or reads its settings.
27. Default `EII_DECISION_PROVIDER` to `none`. Every gate, the guided story, `./eii up`, preflight and freeze must work with provider `none` and no network.
28. A gateway answer is decision evidence only: never a fact, number, privacy decision, gate, refusal, tool argument, recommendation, Arabic approval or authority.
29. Never send visitor-typed text, real custodian data, real identifiers, credentials, real company questions or text from another project.
30. Use only the five closed classes: `spine_match`, `router_miss_finder`, `brief_second_reader`, `question_route` (shadow, team questions only) and `string_parity` (experiment first).
31. Gateway results may only order human review, flag a report, or become a deterministic rule/test after human confirmation. `brief_second_reader` is advisory and raise-only.
32. Store offline decision records under `evals/typed_decisions/runs/`. There is no `app.decision_record` table and no run-time gateway call in version 1.

## Workflow and evidence

33. Use one task per branch and pull request, with Conventional Commits. Change only the task's scope and update affected documents in the same pull request. Cite a pack document by a stable anchor (a requirement ID, a section heading, a task ID, a rule number or the numbered item of a decision record), never by line number.
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

44. Today run only these commands from the repository root: `./eii test` (`./eii test --seed N` repeats a run with a given seed), `./eii preflight` (it only probes), `./eii up` (with `EII_RELEASE_DIR` unset it refuses and exits 4), `python3 scripts/check_docs.py`, `python3 scripts/check_tree.py`, `uv lock --check`, `uv run --locked python -m unittest discover -s scripts/tests -p 'test_*.py' -v`, `uv run --locked ruff check .`, `uv run --locked ruff format --check .`, `uv run --locked mypy`, `uv run --locked python scripts/check_versions.py`, `uv run --locked python scripts/check_reference_notes.py` (reads the two notes files, `pins.toml` and the pack files that hold the anchors the notes cite, and checks that each anchor exists in its file; writes nothing), `uv sync --managed-python --all-packages --locked --group engine` (makes the environment of the sandbox tests and of the type check, which reads the drivers of the group `engine`; a plain `uv sync --locked` removes it again), `uv run --locked python scripts/engine_extensions.py fetch` (needs the network once; fetches the DuckDB extensions into the uncommitted folder `data/engine_extensions/`), `uv run --locked python scripts/engine_extensions.py verify`, `uv run --locked python scripts/sandbox_check.py check`, `uv run --locked python scripts/sandbox_check.py check-extensions`, `uv run --locked python scripts/sandbox_check.py check-enforcement` (the blocking proof of the generator sandbox on the build machine: it exits non-zero when any part of it fails), `uv run --locked python scripts/ci_sandbox.py facts`, `uv run --locked python scripts/ci_sandbox.py prove` (and `uv run --locked python scripts/ci_sandbox.py install-profile`, which runs only on a GitHub-hosted runner, refuses everywhere else and is never run on the build machine), `uv run --locked python scripts/hooks_gitleaks.py fetch` (needs the network once; installs the pinned secret scanner into the uncommitted folder `data/tools/gitleaks/`), `uv run --locked python scripts/hooks_gitleaks.py verify`, `uv run --locked pre-commit validate-config .pre-commit-config.yaml` (it only reads; `pre-commit install` and `pre-commit uninstall` write into the clone's hooks folder, which can hold a developer's own hooks, and are never run by an agent in this repository: the installer `scripts/hooks_install.py` is for a developer's own clone), `uv run --locked python scripts/ci_history_scan.py scan`, `uv run --locked python scripts/ci_plants.py run`, `uv run --locked python scripts/tests/live_store_spike.py` and its form with `--diverge`, which must exit 3 (the live run of the store spike on both stores; both forms need the project's database service running, never start or stop it, and are run only when the task's brief says so), `uv sync --managed-python --all-packages --locked --group engine --group mutation` (adds the pinned mutation tester mutmut to the environment of the sandbox tests), `uv run --locked python scripts/mutation.py MODULE [MODULE ...]` (mutation testing of the named Python modules that compute or compare numbers, in a disposable copy of the files git lists; it writes nothing in the workspace and exits non-zero on a survivor or a not-covered mutant that `scripts/mutation_explained.toml` does not explain), `uv run --locked python scripts/mutation_web.py MODULE [MODULE ...]` (the same for web modules with StrykerJS and its command runner, browser tests excluded; one mutation run at a time on the machine, the runner bounding Stryker's workers times the test files in flight by the processors; every timeout is replayed alone at normal load and reported apart from killed mutants), `uv run --locked ruff format .` (it changes files; run it only to apply the formatter) and, only after a change to a `pyproject.toml`, `uv lock`; and these from `web/`: `npm ci`, `npm run build`, `npm run check`, `npm run check:hosts:dist`, `npm run check:dev`, `npm run test:checks`, `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run spike:glyphs:install-browser` (needs the network once; fetches the headless shell that the browser tests launch into the uncommitted folder `data/tools/playwright/`; it installs system libraries only in the CI environment), `npm run test:spike:glyphs` (the browser tests of the glyph spike; the pixel comparison runs only in the hosted job's own step and never in `./eii test`), `npm run spike:glyphs:record` (it writes the evidence folder of the spike), `npm run spike:glyphs:verify-evidence`, `npm run test:spike:performance` (the tests of the performance spike with its browser tests; they assert the two layer counts and the trace contract and no frame rate), `npm run spike:performance:serve` (starts a loopback server and prints one address for the owner's native browser; the page writes a trace under `web/spikes/performance/evidence/`; run only when the task's brief says so, never by a test), `npm run spike:performance:verify-evidence` (checks a committed native trace; it fails with `missing-native-trace` until one exists and writes nothing), `npm run format` (it changes files; run it only to apply the formatter) and, only after a change to `web/package.json`, `npm install --package-lock-only`. `./eii db-up` and `./eii db-down` start and stop the project's database service and are run only when the task's brief says so. `./eii down`, `./eii build-public`, `./eii build-world`, `./eii build-release`, `./eii load-release` and `./eii freeze` are placeholders that exit 1 and are never claimed to work.
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
| Reference notes for libraries newer than model training data | [docs/REFERENCE_NOTES.md](docs/REFERENCE_NOTES.md), [web/REFERENCE_NOTES.md](web/REFERENCE_NOTES.md) |
| Vocabulary, open decisions and amendments | [docs/GLOSSARY.md](docs/GLOSSARY.md), [OPEN_ITEMS.md](OPEN_ITEMS.md), `docs/decisions/` |

## Open questions and assumptions

46. Raise unresolved choices instead of guessing. Material amendments need a new decision record, never a silent edit to an approved decision.

## Sources

47. The linked pack and its accepted decision records are the build context. No statement in these rules establishes that the planned product exists or passes a gate.
