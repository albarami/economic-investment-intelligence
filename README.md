# Economic & Investment Intelligence (EII)

| | |
|---|---|
| Status | Slice S0 (foundation) in progress; no feature code yet |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Introduce a fully synthetic, public proof-of-concept design and its reading path. |
| Read first | This page, then [docs/README.md](docs/README.md) |

## In brief

EII is a design for a company-facing decision-support proof of concept for Qatar: one business question about one place receives one evidenced answer on a map, in Arabic or English. Its central idea is income geography: privacy-protected, area-level wage statistics for covered earners by where they live and work, beside public sector costs, places and supply evidence. Version 1 is intended to demonstrate a governed method for joining business register, employment, wages, residence and mobility record types, not to provide a market study or investment recommendation.

## Honesty statement

All custodian-type records will be fully synthetic: every company and person is invented, and no real custodian record is read by repository code. Mobility, footfall, traffic and geofencing will be simulated locally, with no telecom operator contacted. Real public data may be shown only with its source, licence and retrieval date.

Only figures marked Public describe Qatar. Synthetic and Simulated figures demonstrate a format and a protection; they are not evidence about a real place, business or person. Suppressed is a separate provenance class, and evidence status is a separate axis from provenance.

## Current status

This repository contains a documentation pack, the [typed-decision qualification set](evals/typed_decisions/README.md) under `evals/`, the scaffolding of the pinned repository layout (slice S0, task S0-T01) and one `uv` workspace with three package skeletons, `eii_core`, `eii_custodian` and `eii_product` (slice S0, task S0-T02). Each skeleton holds a version string and a small test of its own. There is no feature code yet, and no product, release, privacy engine, assistant or interface is claimed to work.

Ten project commands run from the repository root today: the test command `./eii test`, the documentation check, the tree check, the lock check, the guard tests on their own, the three Python checks (lint, format and type), the formatter in write mode and, only after a change to a `pyproject.toml`, the command that rewrites the lock file. Python 3.14 and `uv` are needed for all but the documentation check and the tree check. Two commands change files and are run only to apply the formatter: `uv run --locked ruff format .` here and `npm run format` in `web/`; the lint, format-check and type-check commands only read.

```sh
./eii test
python3 scripts/check_docs.py
python3 scripts/check_tree.py
uv lock --check
uv run --locked python -m unittest discover -s scripts/tests -p 'test_*.py' -v
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
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

`./eii test` runs the six suites that exist, one after the other, and prints the passed, failed and skipped counts of each; the guard-test command above and `npm run test:checks` run the same files as the suites `python-guards` and `web-checks`, without the counts. A Python test that uses subtests counts once, as one test. It exits 0 only if every suite ran at least one test, none failed or errored, every skipped test that the tools report names the standing reason OI-01 or OI-10, and each tool's exit status agrees with its counts. Two Vitest forms are not reported by its JSON reporter and so are not seen: an `it.fails` test whose body fails as expected is written as passed, and a `describe.todo` without a body is omitted; they are left to review and lint (`web/README.md`). The suites are listed in one table at the top of `scripts/run_tests.py`: the guard tests under `scripts/tests`, one suite for each of the three Python packages, the Node checks of `web/` and the Vitest unit tests of `web/`. It needs `uv`, and a prior `npm ci` in `web/` for the two web suites; once those environments are installed it needs neither network nor database. It prints `seed=<n>` first, and `./eii test --seed <n>` repeats a run with the same seed. Only this one `./eii` command exists; the other eleven commands described in the architecture are being built in slice S0 and are not available now. The [implementation plan](docs/14_IMPLEMENTATION_PLAN.md) and [task ledger](TASKS.md) are drafts.

## How to read the documentation

Start with the [documentation index](docs/README.md). It gives each document's status and reading orders for the owner, builders, reviewers, data custodians and designers. New technical terms are in the [glossary](docs/GLOSSARY.md).

Builders must also read [AGENTS.md](AGENTS.md) (mirrored in [CLAUDE.md](CLAUDE.md)), their task in [TASKS.md](TASKS.md), and the documents for that task before changing anything. Completed evidence belongs in [PROGRESS.md](PROGRESS.md); unresolved decisions and assumptions belong in [OPEN_ITEMS.md](OPEN_ITEMS.md).

## What version 1 will show

- A pin-based door with separate worker and resident pay cards, coverage, housing split and privacy-protected release units.
- A Qatari-day dial whose presence index is Simulated, never a count or a named building's footfall.
- Public evidence with source chains: licences, zone utilities, transit, named public places and property sales with deal counts.
- A privacy receipt on every answer and a "Try to break it" scene, without a certification or formal-privacy claim.
- Public sector unit economics and a break-even scenario computed deterministically from the user's own inputs, never a forecast.
- A bilingual governed assistant that selects catalogue claims, components and stage directives; application templates render every word and Fact chips render every numeral.
- A deterministic template writer when no model is available, and exactly three playbooks over nine typed tools.
- An activity spine, supplier lens, comparison, oversight and proof views subject to the documented cut order.

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
