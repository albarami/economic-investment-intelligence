# Economic & Investment Intelligence (EII)

| | |
|---|---|
| Status | Slice S0 (foundation) in progress; no feature code yet; scope amended by decisions 0016 and 0017 on 2026-11-12 |
| Date | 2026-11-12 |
| Owner | albarami |
| Purpose | Introduce a fully synthetic, public proof-of-concept design and its reading path. |
| Read first | This page, then [docs/README.md](docs/README.md) |

## In brief

EII is a design for a company-facing decision-support proof of concept for Qatar, built on one living map. A company draws an area, or sets a radius or a walk or drive time from any point at a chosen hour, and sees who is there through the day, the traffic, the businesses, the pay of the people who work and live there, and the public evidence, with an assistant answering in Arabic and English. Wages are one layer, the distinctive one: privacy-protected, area-level wage statistics for covered earners by where they live and where they work.

On that map, seven company decisions become journeys that each end with their own answer, three services are built from those answers, and four guided cases show them at work ([decision 0016](docs/decisions/0016-version-1-covers-the-whole-initiative.md)). Every answer rests on a governed method for joining business register, employment, wages, residence and mobility record types with cited public data, which [decision 0017](docs/decisions/0017-public-data-additions-and-public-splits.md) extends with 77 portal datasets and two investment sources.

Every custodian-type record is fully synthetic and all movement and traffic are simulated, so only figures marked Public describe Qatar. No screen gives a forecast, a verdict or advice to act; each answer shows its evidence, its limits and what remains to test.

## Honesty statement

All custodian-type records will be fully synthetic: every company and person is invented, and no real custodian record is read by repository code. Mobility, footfall, traffic and geofencing will be simulated locally, with no telecom operator contacted. Real public data may be shown only with its source, licence and retrieval date.

Only figures marked Public describe Qatar. Synthetic and Simulated figures demonstrate a format and a protection; they are not evidence about a real place, business or person. Suppressed is a separate provenance class, and evidence status is a separate axis from provenance.

## Current status

This repository contains a documentation pack, the [typed-decision qualification set](evals/typed_decisions/README.md) under `evals/`, the scaffolding of the pinned repository layout (slice S0, task S0-T01) and one `uv` workspace with three package skeletons, `eii_core`, `eii_custodian` and `eii_product` (slice S0, task S0-T02). Each skeleton holds a version string and a small test of its own. There is no feature code yet, and no product, release, privacy engine, assistant or interface is claimed to work.

Eleven project commands run from the repository root today: the test command `./eii test`, the documentation check, the tree check, the lock check, the guard tests on their own, the three Python checks (lint, format and type), the version check, the formatter in write mode and, only after a change to a `pyproject.toml`, the command that rewrites the lock file. Python 3.14 and `uv` are needed for all but the documentation check and the tree check. Two commands change files and are run only to apply the formatter: `uv run --locked ruff format .` here and `npm run format` in `web/`; the lint, format-check and type-check commands only read.

```sh
./eii test
python3 scripts/check_docs.py
python3 scripts/check_tree.py
uv lock --check
uv run --locked python -m unittest discover -s scripts/tests -p 'test_*.py' -v
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked python scripts/check_versions.py
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

`pins.toml` at the repository root records every pinned version once: the exact version or series, the retreat pin or `none recorded`, a label (a value taken from the documentation pack, to be confirmed at slice S1, or an ASSUMPTION with its source), the pack line it answers, and whether it is installed now or only recorded for the slice that first uses it. The manifests, the lock files and the version files must agree with it: `.python-version` and `.nvmrc` hold the Python and Node series, and `required-version` in the root `pyproject.toml` holds the `uv` version. `uv run --locked python scripts/check_versions.py` fails when a dependency named in a judged place of a manifest, a locked version of a recorded component, a version file, a version field, or the Python that runs it, or the `uv`, Node or npm found on the path, differs from that record, and when a manifest, lock or version file outside its closed set is among the files that git tracks or would track (a file that git ignores and does not track is not judged); the places it does not judge are listed in the docstring of `scripts/check_versions.py`. It reads files, asks git for its list of files and runs `--version` on the tools; it changes nothing. The guard tests include a run of this check on the real repository, so `./eii test` and the guard-test command also need `git` on the path, `uv` at the recorded version, and `node` and `npm` on the path within the recorded series, not only for the two web suites. Slice S1 confirms the pins and writes the spike result; until then they are the values of the pack or labelled assumptions.

`./eii test` runs the six suites that exist, one after the other, and prints the passed, failed and skipped counts of each; the guard-test command above and `npm run test:checks` run the same files as the suites `python-guards` and `web-checks`, without the counts. A Python test that uses subtests counts once, as one test. It exits 0 only if every suite ran at least one test, none failed or errored, every skipped test that the tools report names the standing reason OI-01 or OI-10, and each tool's exit status agrees with its counts. Two Vitest forms are not reported by its JSON reporter and so are not seen: an `it.fails` test whose body fails as expected is written as passed, and a `describe.todo` without a body is omitted; they are left to review and lint (`web/README.md`). The suites are listed in one table at the top of `scripts/run_tests.py`: the guard tests under `scripts/tests`, one suite for each of the three Python packages, the Node checks of `web/` and the Vitest unit tests of `web/`. It needs `uv`, and a prior `npm ci` in `web/` for the two web suites; once those environments are installed it needs neither network nor database. It prints `seed=<n>` first, and `./eii test --seed <n>` repeats a run with the same seed. Only this one `./eii` command exists; the other eleven commands described in the architecture are being built in slice S0 and are not available now. The [implementation plan](docs/14_IMPLEMENTATION_PLAN.md) and [task ledger](TASKS.md) are drafts.

## How to read the documentation

Start with the [documentation index](docs/README.md). It gives each document's status and reading orders for the owner, builders, reviewers, data custodians and designers. New technical terms are in the [glossary](docs/GLOSSARY.md).

Builders must also read [AGENTS.md](AGENTS.md) (mirrored in [CLAUDE.md](CLAUDE.md)), their task in [TASKS.md](TASKS.md), and the documents for that task before changing anything. Completed evidence belongs in [PROGRESS.md](PROGRESS.md); unresolved decisions and assumptions belong in [OPEN_ITEMS.md](OPEN_ITEMS.md).

## What version 1 will show

The map comes first; the journeys, services and cases are built on it.

- **One living map of Qatar.** Real public geography, roads and business points; synthetic firms and workers as density and statistics at realistic levels; simulated people present, crowd density and traffic through the day. Every Synthetic or Simulated figure carries its mark.
- **Any area.** Draw a shape, set a radius, or pick a walk or drive time from any point at a chosen hour. Public and Simulated layers are computed for that exact shape; figures from the protected record types are read only after the shape snaps to whole release units, with a snap report.
- **Who is there through the day.** Estimated people around this location, hour by hour, as counts with a range, split into workers, residents and visitors, with crowd density, the summer switch and three event days (National Day, a day in Ramadan, a major match). Never the footfall of a named building or business.
- **Traffic.** Simulated congestion by hour on the real road network, animated through the day, with drive-time areas that change with the hour.
- **Pay, the distinctive layer.** Separate worker and resident pay cards with coverage and the housing split; six area-level indicators for covered earners, with monthly periods so that "what changed" and wage trends work, and the average never shown alone; a labour-market view whose projections are marked as projections.
- **The businesses.** Real businesses from public places data and public listings, public tenders where a public source exists, and announced investment projects from the FDI dashboard of the national investment promotion agency, whose capex and jobs keep the source's note that they are estimates. Named synthetic firms appear as prospects, partners and suppliers, always marked Synthetic. Openings and closures are shown over time.
- **Public evidence with source chains.** Licences, zone utilities, transit, property sales with deal counts, building permits, employer scale, industrial capacity, visitor counts of named public places, official splits by sex or nationality as Public facts, and the agency's sector, opportunity, incentive, set-up and law pages. Every figure shows its source and retrieval date.

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

A ranking is the output of tested code over criteria, weights and values the user can see and change, with a rank-stability sentence beside every rank and a public-only mode; it is never a verdict or advice to act.

- **Three services** as journey outputs: the market entry evidence pack (S1), a comparison of growth and operating options with the barriers to resolve (S2), and local supplier and workforce connections through a structured qualification route (S3).
- **Four guided cases**, each with a one-click start: an industrial services firm (C1), a technology supplier (C2), a distributor weighing a second depot (C3) and a retail chain with a weak branch (C4). The sample files of C3 and C4 are synthetic, marked, and stay inside the session and seat that loaded them.
- **Costs.** Public sector unit economics and a break-even scenario computed deterministically from the user's own inputs, with the agency's incentive packages as optional inputs, never a forecast.
- **Privacy you can attack.** A privacy receipt on every answer and a "Try to break it" scene, without a certification or formal-privacy claim.
- **A governed bilingual assistant across every module.** It chooses the area and the indicators and calls fixed, tested analyses; application templates render every word and Fact chips render every numeral; a case gallery, a one-page brief export, and a deterministic template writer when no model is available.
- **Proof and oversight.** The activity spine, the supplier lens, the oversight seat and the reviewers' proof views.

The build order is the map and data foundation first, then the location choice in full depth, then the other journeys; each slice ends at a gate with an independent reviewer, and nothing below a slice gate is half-built.

Accuracy is enforced by three code mechanisms: no model calculates, no fact is accepted without its source chain, and the accounting gate checks every answer before display. No model-written prose reaches the screen in version 1.

## Planned repository layout

The architecture pins this layout. `docs/`, `evals/` and `scripts/` hold the documentation pack, the qualification set, the repository checks and the test runner; the file `eii` at the root is the command launcher. `contracts/`, `gateway/` and `infra/` exist as scaffolding, each with a short note and no feature code yet. `web/` holds the application shell, which has no feature UI yet. `core/`, `custodian/` and `product/` each hold one package skeleton, a version string and a small test of its own. Nothing under `data/` is ever committed (ARC-99), so a fresh clone has no `data/` folder:

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
data/         uncommitted public cache, vault and releases
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
