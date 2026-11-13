# Economic & Investment Intelligence (EII)

| | |
|---|---|
| Status | Slice S0 (foundation) in progress; no feature code yet; scope amended by decisions 0016, 0017 and 0019 on 2026-11-12 |
| Date | 2026-11-12 |
| Owner | albarami |
| Purpose | Introduce a fully synthetic, public proof-of-concept design and its reading path. |
| Read first | This page, then [docs/README.md](docs/README.md) |

## In brief

EII is a design for a company-facing decision-support proof of concept for Qatar, built on one living map. A company draws an area, or sets a radius or a walk or drive time from any point at a chosen hour, and sees who is there through the day, the traffic, the businesses, the pay of the people who work and live there, and the public evidence, with an assistant answering in Arabic and English. Wages are one layer, the distinctive one: privacy-protected, area-level wage statistics for covered earners by where they live and where they work.

On that map, seven company decisions become journeys that each end with their own answer, three services are built from those answers, and four guided cases show them at work ([decision 0016](docs/decisions/0016-version-1-covers-the-whole-initiative.md)). Every answer rests on a governed method for joining business register, employment, wages, residence and mobility record types with cited public data, which [decision 0017](docs/decisions/0017-public-data-additions-and-public-splits.md) extends with 77 portal datasets and two investment sources, and which [decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) extends with forecasts of published series, base rates, a site estimate, scenario tools, people present by pay band, an optional 3D view and six self-serve sources (an optional live traffic provider, the relative busyness of named venues, night-time lights, a further places dataset, population grids by age and sex, and hourly weather history).

Every custodian-type record is fully synthetic and all movement is simulated, as is road traffic unless the optional live traffic provider is switched on, so only figures marked Public describe Qatar. No screen gives a verdict or advice to act. A forecast, an estimate or a base rate appears only as the output of tested code, with its interval, range or counts, its method and its source; a user's scenario is the user's own and is never called a forecast; nothing forecasts the success of a venture and nothing is estimated for a named real business. Each answer shows its evidence, its limits and what remains to test.

## Honesty statement

All custodian-type records will be fully synthetic: every company and person is invented, and no real custodian record is read by repository code. Mobility, footfall and geofencing will be simulated locally, with no telecom operator contacted; a published relative-busyness figure of a named venue is a Public fact, not a mobility feed. Road traffic is simulated locally by default; the optional live traffic provider is off by default and is never needed by a test, a gate, a command or the guided story. Real public data may be shown only with its source, licence and retrieval date.

Only figures marked Public describe Qatar. Synthetic and Simulated figures demonstrate a format and a protection; they are not evidence about a real place, business or person. Suppressed is a separate provenance class, and evidence status is a separate axis from provenance.

## Current status

This repository contains a documentation pack, the [typed-decision qualification set](evals/typed_decisions/README.md) under `evals/`, the scaffolding of the pinned repository layout (slice S0, task S0-T01) and one `uv` workspace with three package skeletons, `eii_core`, `eii_custodian` and `eii_product` (slice S0, task S0-T02). Each skeleton holds a version string and a small test of its own. The tile spike of slice S1 (task S1-T04) serves one synthetic tile artefact with byte ranges from `product/src/eii_product/api/` and tests it over HTTP on the loopback interface. The workspace has a fourth package, `eii_gateway` (slice S1, task S1-T07): the offline typed-decision gateway, used only by tooling under `scripts/` and `evals/`; its default provider `none` opens no connection, and its adapter for the configured provider is written, marked unverified and was never called. There is no feature code yet, and no product, release, privacy engine, assistant or interface is claimed to work.

Twenty-six project commands run from the repository root today: `./eii test`, `./eii preflight`, `./eii up`, the documentation check, the tree check, the lock check, the guard tests on their own, the three Python checks (lint, format and type), the version check, the reference-notes check, the seven sandbox and engine-extension commands (environment, fetch, verify, two launcher checks, the runner facts and the proof of the sandbox tests), the three commit-hook commands (fetch and verify the secret scanner, validate the hook configuration), the two continuous-integration commands (the full-history secret scan and the planted-failure harness), the formatter in write mode and, only after a change to a `pyproject.toml`, the command that rewrites the lock file. Python 3.14 and `uv` are needed for all but the documentation check and the tree check. Two commands change files and are run only to apply the formatter: `uv run --locked ruff format .` here and `npm run format` in `web/`; the lint, format-check and type-check commands only read.

```sh
./eii test
./eii preflight
./eii up
python3 scripts/check_docs.py
python3 scripts/check_tree.py
uv lock --check
uv run --locked python -m unittest discover -s scripts/tests -p 'test_*.py' -v
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked python scripts/check_versions.py
uv run --locked python scripts/check_reference_notes.py
uv sync --managed-python --all-packages --locked --group engine
uv run --locked python scripts/engine_extensions.py fetch
uv run --locked python scripts/engine_extensions.py verify
uv run --locked python scripts/sandbox_check.py check
uv run --locked python scripts/sandbox_check.py check-extensions
uv run --locked python scripts/ci_sandbox.py facts
uv run --locked python scripts/ci_sandbox.py prove
uv run --locked python scripts/hooks_gitleaks.py fetch
uv run --locked python scripts/hooks_gitleaks.py verify
uv run --locked pre-commit validate-config .pre-commit-config.yaml
uv run --locked python scripts/ci_history_scan.py scan
uv run --locked python scripts/ci_plants.py run
uv run --locked ruff format .
uv lock
```

`web/` also holds an application shell built with React, TypeScript and Vite. It has no feature UI, and nothing is claimed to work beyond the checks listed in [web/README.md](web/README.md). In addition to the commands above, ten commands run from `web/` (not from the repository root), and an eleventh, `npm install --package-lock-only`, only after a change to `web/package.json`. `npm ci` and that eleventh command need the network:

```sh
cd web
npm ci
npm run build
npm run check
npm run check:hosts:dist
npm run check:dev
npm run test:checks
npm run lint
npm run format:check
npm run typecheck
npm run format
npm install --package-lock-only
```

`npm run format` changes files and is run only to apply the formatter.

`pins.toml` at the repository root records every pinned version once: the exact version or series, the retreat pin or `none recorded`, a label (a value taken from the documentation pack, to be confirmed at slice S1, or an ASSUMPTION with its source), the pack anchor it answers, and whether it is installed now or only recorded for the slice that first uses it. The manifests, the lock files and the version files must agree with it: `.python-version` and `.nvmrc` hold the Python and Node series, and `required-version` in the root `pyproject.toml` holds the `uv` version. `uv run --locked python scripts/check_versions.py` fails when a dependency named in a judged place of a manifest, a locked version of a recorded component, a version file, a version field, or the Python that runs it, or the `uv`, Node or npm found on the path, differs from that record, and when a manifest, lock or version file outside its closed set is among the files that git tracks or would track (a file that git ignores and does not track is not judged); the places it does not judge are listed in the docstring of `scripts/check_versions.py`. It reads files, asks git for its list of files and runs `--version` on the tools; it changes nothing. The guard tests include a run of this check on the real repository, so `./eii test` and the guard-test command also need `git` on the path, `uv` at the recorded version, and `node` and `npm` on the path within the recorded series, not only for the two web suites. Slice S1 confirms the pins and writes the spike result; until then they are the values of the pack or labelled assumptions.

`web/REFERENCE_NOTES.md` and `docs/REFERENCE_NOTES.md` record, for the libraries that the pack calls newer than most model training data (MapLibre GL JS 6, deck.gl 9.4 with its MapLibre module, DuckDB 2.0, PostgreSQL 18 and the Claude API), the official pages read and the date read, the idioms that changed from earlier versions, the runs made with the packages, and the points that slice S1 still has to confirm. `web/REFERENCE_NOTES.md` also records what was observed in the files of the two IBM Plex font packages (the weights that DES-25 asks for) and in the package that holds the Carbon icons (the licence that DES-45 asks for). Every statement has one kind (READ, OBSERVED or PACK), and a PACK statement is marked as not verified. The notes cite the pack by stable anchors (a requirement identifier with its file, or a section heading with its file), never by line number. `uv run --locked python scripts/check_reference_notes.py` checks the form of the two files: the sections, the kinds, the sources, the allowed addresses, the dates, the confirmation tables, the coverage tables, that nothing but headings, tables and one opening line stands in a library section, the rows of `pins.toml` that they cite, that each anchor they cite exists in the cited file of the pack, and, for the font and icon section, that each font family has an observed row at the weights 400, 500 and 600 and that an observed icon row names a licence identifier. It does not check what the anchored text says, that a quotation is still on its page or says what its row says, and it needs no network. The notes carry no pin; `pins.toml` does.

The generator sandbox is bubblewrap only; there is no fallback. `scripts/sandbox_launch.py` builds the command line of the two profiles, `build-world` and `build-release`, from the closed tables of `scripts/sandbox_profiles.py`: the network is unshared, the checkout is mounted as three read-only code folders only, `data/public_cache/` is read-only, the engine-extension files are checked and bound one by one, read-only, with nothing else of their folder visible, their folder an in-memory mount of its own that is made read-only, and the vault folder (for `build-release` also one staging folder) is the only writable host path. Every mount is made from the descriptor of the object that was checked, so a symbolic link, a rename or a replaced file between the check and the start is never mounted. The launcher does not protect against a process outside the sandbox that has write permission on a mounted object (a process of the same user, or root) and changes that object's content while a build runs, nor against root, the kernel or bubblewrap themselves (OI-61). The environment is made by `uv sync --managed-python --all-packages --locked --group engine`. `scripts/engine_extensions.py fetch` is the one command of this part that needs the network: it installs the DuckDB `spatial` and `h3` extensions into `data/engine_extensions/`, an uncommitted folder under `data/` that the sandbox tests and `scripts/sandbox_check.py` read (a cache path in the sense of rule 13; the path is an assumption that slice S1 confirms or moves). The sandbox tests carry the marker `sandbox`, run in `./eii test` and in the unittest command, and are never skipped: without bubblewrap, without the `engine` group or without the fetched extensions they fail and name the command to run. `.github/workflows/sandbox.yml` runs them on a GitHub-hosted Ubuntu 24.04 runner; where the runner restricts unprivileged user namespaces, the job loads the per-binary AppArmor profile of bubblewrap from the distribution package, and where that does not help the job fails; no system-wide switch is ever written.

`./eii test` runs the six suites that exist, one after the other, and prints the passed, failed and skipped counts of each; the guard-test command above and `npm run test:checks` run the same files as the suites `python-guards` and `web-checks`, without the counts. A Python test that uses subtests counts once, as one test. It exits 0 only if every suite ran at least one test, none failed or errored, every skipped test that the tools report names the standing reason OI-01 or OI-10, and each tool's exit status agrees with its counts. Two Vitest forms are not reported by its JSON reporter and so are not seen: an `it.fails` test whose body fails as expected is written as passed, and a `describe.todo` without a body is omitted; they are left to review and lint (`web/README.md`). The suites are listed in one table at the top of `scripts/run_tests.py`: the guard tests under `scripts/tests`, one suite for each of the three Python packages, the Node checks of `web/` and the Vitest unit tests of `web/`. It needs `uv`, a prior `npm ci` in `web/` for the two web suites, and the pinned secret scanner for the hook tests, fetched once by `uv run --locked python scripts/hooks_gitleaks.py fetch`; once those are installed it needs neither network nor database. It prints `seed=<n>` first, and `./eii test --seed <n>` repeats a run with the same seed. Twelve `./eii` commands are entry points. `./eii test`, `./eii preflight` and `./eii up` run today (`./eii up` refuses with exit 4 when `EII_RELEASE_DIR` is unset). `./eii db-up` and `./eii db-down` start and stop the project's database service and are run only when the task's brief says so. `./eii down`, `./eii build-public`, `./eii build-world`, `./eii build-release`, `./eii load-release` and `./eii freeze` are placeholders that exit 1 and are never claimed to work. The [implementation plan](docs/14_IMPLEMENTATION_PLAN.md) and [task ledger](TASKS.md) are drafts.

## Commit hooks

`.pre-commit-config.yaml` holds eleven hooks of the pre-commit framework (pinned in the root `dev` group). None of them rewrites a file. Five run on every commit: the commit guard, the secret scanner (gitleaks), the documentation check (which also owns the identifier-shaped numbers, absolute paths, address-shaped strings and four secret shapes), the tree check and the version check. Six run only when a staged path matches: the Python lint, format and type checks when a Python file or a `pyproject.toml` is staged, and the web lint, format and type checks when a file under `web/` is staged. The same checks are meant to run again in continuous integration (`TASKS.md`, task S0-T07), with the repository settings of `TASKS.md`, task S0-T14 as a further backstop; the hooks do not judge a commit that skips them.

Install them in your own clone with `uv run --locked python scripts/hooks_gitleaks.py fetch` (network once; the first `uv run --locked` also builds the Python environment) and `uv run --locked python scripts/hooks_install.py`. The installer refuses, and writes nothing, when its folder is not the top of its own checkout, when `core.hooksPath` is set, when it runs in a linked work tree, when a `pre-commit.legacy` file exists (the framework's hook would run it), or when a hook named `pre-commit` already exists that the framework did not write. The framework itself, run by hand over such a hook, moves it to `pre-commit.legacy` and runs it first (a failure of the old hook refuses the commit while the framework hooks still run), replaces an existing `pre-commit.legacy` silently so that its content is lost, and with `-f` deletes the old hook; `pre-commit uninstall` restores a moved hook. Decide what to do with an existing hook before you install (OI-91 in OPEN_ITEMS.md), and copy the hooks folder first. Agents never run `pre-commit install`, `pre-commit uninstall` or the installer in this repository.

The scanner binary is downloaded once from the GitHub release page of gitleaks, checked against a pinned SHA-256 of the archive and kept in `data/tools/gitleaks/<version>/`, an uncommitted folder under `data/` that tests and hooks may read (a cache path in the sense of `AGENTS.md` rule 13). Later runs need no network. The hook tests need that binary even where nobody installs the hooks: `./eii test` and the unittest command of the repository root run them without skipping, and in a fresh clone they fail, naming `uv run --locked python scripts/hooks_gitleaks.py fetch`, until that one-time download has populated `data/tools/gitleaks/8.30.1/gitleaks`; after it, the hook tests run offline. The framework keeps its own small store in the user cache folder (`PRE_COMMIT_HOME` moves it); during a commit with unstaged changes it writes the unstaged diff there as a patch file that it never deletes, so remove old patch files from that store now and then with the framework's own `clean` sub-command (it writes only the store).

The commit guard reads `.env` at the repository root and the process environment for the non-empty values of `ANTHROPIC_API_KEY`, `JEV_PRO_API_KEY`, `TOMTOM_API_KEY`, `EARTHDATA_API_KEY` and the password inside `EII_DATABASE_URL`, and refuses a commit whose staged content or staged path, read from git's index, holds one of them. It prints the variable name, and the path only when the path holds no value, never a value; a path holding eight or more consecutive characters of a value is not printed either. It reads `.env` without a byte order mark, with quotes and with a trailing comment, and refuses a line for a listed name that it cannot read, such as a double-quoted value that holds a backslash. A value shorter than 12 characters (for the database URL, the password as written or percent-decoded), or a database URL that it cannot read as a PostgreSQL URL with a host and, when a port is written, a numeric one, or whose query string names `password` or `passfile`, cannot be checked, so the guard refuses until it is fixed or removed. It does not see a value split over lines, reversed or encoded, the other database role credentials, or a variable outside the closed list.

Gitleaks runs on the staged changes. It does not scan binary files, does not flag a database URL, skips the paths on its own built-in list (images, fonts, documents, lock files, vendored and package folders and others), and a git attribute that marks a path binary hides that path from it. The documentation check reads only text suffixes of a closed list and misses an eight- or eleven-digit run that has a hyphen, colon or slash beside it (OI-93 in OPEN_ITEMS.md).

## Continuous integration

Three workflow files run on every pull request. `docs.yml` provides the required `check-docs` check. `ci.yml` provides `static-checks`, `tests`, `secret-scan` and `planted-failures`. `sandbox.yml` provides the hosted `sandbox proof`. The complete test job prepares the pinned scanner, engine group, engine extensions, web dependencies and hosted-runner namespace profile before `./eii test`; the scanner job checks the full history of the branch; the planted-failure job makes temporary copies and requires one violation per listed guard to be blocked. No workflow skips or retries a failed check. The text of each workflow file is pinned by its SHA-256 in `scripts/tests/ci_workflow_rules.py`, so a change of a workflow file changes its pin in the same commit; the guard tests fail otherwise.

The two CI helper commands are read-only with respect to this checkout. `uv run --locked python scripts/ci_history_scan.py scan` requires the pinned scanner fetched by the commit-hook command and a complete git history; it leaves out findings on ledger lines it knows by exact content (today one line, recorded twice: an earlier recorded command with two dummy values) and fails on every other finding. `uv run --locked python scripts/ci_plants.py run` uses temporary scratch repositories and the already installed package caches; it uses no network.

## Database service and preflight

`infra/compose.yaml` defines this project's PostgreSQL 18 with PostGIS 3.6 service, pinned by image digest, published on the loopback address only on the port of `EII_DATABASE_URL` (documented default `127.0.0.1:55440`), and isolated under Compose project `eii-poc`. Only `./eii db-up` and `./eii db-down` start or stop it. `./eii preflight` only probes, and `./eii up` never starts a database.

The live probe module under `scripts/tests/` fails rather than skips when the service is down. The lead alone arranges the service state for that module; ordinary tests do not start or stop a container.

## How to read the documentation

Start with the [documentation index](docs/README.md). It gives each document's status and reading orders for the owner, builders, reviewers, data custodians and designers. New technical terms are in the [glossary](docs/GLOSSARY.md).

Builders must also read [AGENTS.md](AGENTS.md) (mirrored in [CLAUDE.md](CLAUDE.md)), their task in [TASKS.md](TASKS.md), and the documents for that task before changing anything. Completed evidence belongs in [PROGRESS.md](PROGRESS.md); unresolved decisions and assumptions belong in [OPEN_ITEMS.md](OPEN_ITEMS.md).

## What version 1 will show

The map comes first; the journeys, services and cases are built on it.

- **One living map of Qatar.** Real public geography, roads and business points; synthetic firms and workers as density and statistics at realistic levels; simulated people present and crowd density through the day, and traffic through the day (simulated by default). Public layers of night-time radiance by area and month and of the relative busyness of named venues sit beside them, and an optional 3D view extrudes whole release units. Every Synthetic or Simulated figure carries its mark.
- **Any area.** Draw a shape, set a radius, or pick a walk or drive time from any point at a chosen hour. Public and Simulated layers are computed for that exact shape; figures from the protected record types are read only after the shape snaps to whole release units, with a snap report.
- **Who is there through the day.** Estimated people around this location, hour by hour, as counts with a range, split into workers, residents and visitors, with crowd density, the summer switch and three event days (National Day, a day in Ramadan, a major match). Never the footfall of a named building or business. For a whole release unit, a day type and an hour, the simulated workers and residents present are also shown by pay band, marked Inferred and Simulated and never called spending.
- **Traffic.** Simulated congestion by hour on the real road network, animated through the day, with drive-time areas that change with the hour. With the optional live provider switched on (off by default), live flow tiles and traffic-aware drive-time areas appear with the provider's attribution; nothing of a response is stored.
- **Pay, the distinctive layer.** Separate worker and resident pay cards with coverage and the housing split; six area-level indicators for covered earners, with monthly periods so that "what changed" and wage trends work, and the average never shown alone; a labour-market view whose projections are marked as projections and whose forecasts follow the rules below.
- **The businesses.** Real businesses from public places data and public listings, public tenders where a public source exists, and announced investment projects from the FDI dashboard of the national investment promotion agency, whose capex and jobs keep the source's note that they are estimates. Named synthetic firms appear as prospects, partners and suppliers, always marked Synthetic. Openings and closures are shown over time.
- **Public evidence with source chains.** Licences, zone utilities, transit, property sales with deal counts, building permits, employer scale, industrial capacity, visitor counts of named public places, official splits by sex or nationality as Public facts, population by age and sex from a published grid (whole cells summed over a chosen area), and the agency's sector, opportunity, incentive, set-up and law pages. Every figure shows its source and retrieval date.
- **Forecasts, base rates and estimates.** Forecasts of a closed list of published series (licence issues and cancellations, property prices, hotel demand, prices, imports, announced investment and the construction pipeline), each with an interval built from its own backtest and its measured backtest error; entry and closure base rates from the Public licence tables, with their counts and period, and no survival figure until a Public source links a cancellation to its issue; and a site demand and revenue estimate for a chosen area, as a low, a middle and a high case with its main drivers, labelled "estimate on simulated inputs" while an input is simulated. All of it is computed by tested code; nothing is estimated for a named real building or business.

Seven decision journeys, each ending with its own answer:

| Decision | The answer the journey ends with |
|---|---|
| D1 Whether to enter Qatar | The market entry pack: market profile, customers and competitors, local income context, candidate areas, workforce context and next actions |
| D2 Which location fits (the flagship) | The location choice for a drawn or travel-time area, with the best-location ranking and its reverse |
| D3 Where to find customers | A targeted territory and a prospect list of named synthetic firms by sector and size band |
| D4 Whom to partner with | Named synthetic firms ranked by fit, real businesses from public listings, public tenders where a public source exists, and a structured qualification route |
| D5 How to organise staffing | Pay by occupation with middle ranges and earner counts (Synthetic), where such workers live, trends, national mean pay and wage trends by economic activity (Public) and the labour-market view |
| D6 Where to grow in Qatar | Openings and closures over time, cluster change and a second-site comparison (shared reach and overlap, never lost sales) |
| D7 How to serve the region | Travel times from an area to the ports, the airport, the free zones and the land routes, complementary firms and the import context |

A ranking is the output of tested code over criteria, weights and values the user can see and change, with a rank-stability sentence beside every rank and a public-only mode; it is never a verdict or advice to act. Forecasts, base rates and the site estimate may be among the criteria, each visible with its value and weight and removable by the user; a ranking that uses a forecast is still not a forecast.

- **Three services** as journey outputs: the market entry evidence pack (S1), a comparison of growth and operating options with the barriers to resolve (S2), and local supplier and workforce connections through a structured qualification route (S3).
- **Four guided cases**, each with a one-click start: an industrial services firm (C1), a technology supplier (C2), a distributor weighing a second depot (C3) and a retail chain with a weak branch (C4). The sample files of C3 and C4 are synthetic, marked, and stay inside the session and seat that loaded them.
- **Costs.** Public sector unit economics and a break-even scenario computed deterministically from the user's own inputs, with the agency's incentive packages as optional inputs, never a forecast. Two scenario tools join it: a catchment-share scenario that shows the share of the user's outlet and of the competitors, split by competitor category and by distance band, never per named business, and a revenue range for the user's outlet with low, middle and high cases. Each is the user's own scenario, with every assumption visible and editable, and is never called a forecast.
- **Privacy you can attack.** A privacy receipt on every answer and a "Try to break it" scene, without a certification or formal-privacy claim.
- **A governed bilingual assistant across every module.** It chooses the area and the indicators and calls fixed, tested analyses; application templates render every word and Fact chips render every numeral; a case gallery, a one-page brief export, and a deterministic template writer when no model is available.
- **Proof and oversight.** The activity spine, the supplier lens, the oversight seat and the reviewers' proof views.

The build order is the map and data foundation first, then the location choice in full depth, then the other journeys; each slice ends at a gate with an independent reviewer, and nothing below a slice gate is half-built.

Accuracy is enforced by three code mechanisms: no model calculates, no fact is accepted without its source chain, and the accounting gate checks every answer before display. No model-written prose reaches the screen in version 1.

## Planned repository layout

The architecture pins this layout. `docs/`, `evals/` and `scripts/` hold the documentation pack, the qualification set, the repository checks, the test runner and the sandbox launcher with its proofs and the commit-hook scripts; the file `eii` at the root is the command launcher. `contracts/` and `infra/` exist as scaffolding, each with a short note and no feature code yet. `gateway/` holds the offline typed-decision package `eii_gateway`, which nothing under `core/`, `custodian/` or `product/` imports. `web/` holds the application shell, which has no feature UI yet. `core/`, `custodian/` and `product/` each hold one package skeleton, a version string and a small test of its own. Nothing under `data/` is ever committed (ARC-99), so a fresh clone has no `data/` folder:

```text
contracts/    source and release contracts
core/         shared eii_core library, including deterministic calculation
custodian/    offline synthetic build and privacy plane
product/      read-only serving plane and governed assistant
web/          browser experience plane
evals/        evaluation, attack and typed-decision sets
gateway/      offline typed-decision package, used only by evals and scripts tooling
infra/        database, Compose and stage configuration
scripts/      developer commands
docs/         this documentation pack and decision records
data/         uncommitted public cache, vault, releases, engine extensions and tools
```

The custodian plane is the only place record-level synthetic data may exist. Its vault is deleted after each build. Only an immutable, content-addressed release crosses to the product plane, which never imports custodian code.

## Build and review workflow

Work proceeds in gated slices, one task per branch and pull request. The builder and independent reviewer come from different makers. Tests need real exit codes and recorded evidence; privacy and security checks are never weakened to obtain a pass. The detailed workflow is in [AGENTS.md](AGENTS.md) and the [reviewer checklist](docs/15_REVIEWER_CHECKLIST.md).

## Licence and third-party attribution

Copyright (c) 2026 albarami. All rights reserved. No permission is granted to use, copy, modify or distribute without prior written permission; see [LICENSE](LICENSE).

Third-party data and software named in this pack remain under their own licences. Public-data attribution, licence conditions and retrieval records are specified in [04_PUBLIC_DATA_PACK.md](docs/04_PUBLIC_DATA_PACK.md); map assets are covered in [10_FRONTEND.md](docs/10_FRONTEND.md). Attribution does not imply that a publisher or custodian supplies or endorses EII. No file without a stated licence may be committed.

## Open questions and assumptions

Open owner decisions, technical unknowns and draft assumptions are tracked in [OPEN_ITEMS.md](OPEN_ITEMS.md). The working product name and its Arabic name await clearance. No new assumption is introduced on this page.

## Sources

- [Project brief](docs/01_PROJECT_BRIEF.md) for scope, capabilities and prohibited claims.
- [Architecture](docs/02_ARCHITECTURE.md) and [data contracts](docs/03_DATA_CONTRACTS.md) for the planned planes, release and repository layout.
- [AI assistant](docs/09_AI_ASSISTANT.md) and [decision 0014](docs/decisions/0014-typed-decision-gateway.md) for governed composition and the measured typed-decision evidence.
- [Public data pack](docs/04_PUBLIC_DATA_PACK.md) for third-party sources, licences and retrieval rules.
- [Decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) for forecasts, estimates and base rates by tested code, the scenario tools, the six self-serve sources and the citation of the pack by stable anchor.
