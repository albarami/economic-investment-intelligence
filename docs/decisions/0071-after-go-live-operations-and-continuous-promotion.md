# Decision 0071: After-go-live operations and continuous promotion

| | |
|---|---|
| Status | Accepted, 2026-11-20 |
| Date | 2026-11-20 |
| Owner | The owner |
| Decided by | The owner's decision of 2026-11-20 |
| Amends | [TASKS.md](../../TASKS.md), new S3-T28 and its post-gate placement; [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md), slice S3 operations note; [docs/README.md](../README.md), decision index. Assigns the operational freeze/build/load implementation before first live service, with later S11-T01 and S11-T06 hardening and checks retained. |
| Purpose | Start the live site with the approved first map, isolate it from development and staging and promote ready visible work through a recorded green checklist. |
| Read first | Decision 0041 items 1 to 10; TASKS.md S0-T09, S3-T02, S3-T10, S3-T20, S11-T01 and S11-T06; document 13 sections 5, 6 and 7; AGENTS.md rules 12, 24, 33, 36, 44 and 45. |

## Context

The owner's decision of 2026-11-20 starts live service with the first map, when the slice S3 gate is approved,
and promotes subsequent ready user-visible pieces continuously. A live service must remain an identified frozen
release while development continues elsewhere. This is an operations decision, not a claim that the commands or
the first map work today.

S3-T20 already owns the remote entry after the slice S3 gate. S0-T09 owns the command skeleton, and S11-T01 and
S11-T06 specify freeze hardening and the export register. AGENTS.md rule 44 still describes `freeze`,
`build-release` and `load-release` as placeholders that exit 1. S3-T02 currently refuses freeze and an export-register
entry for `public_only`. The first-map frozen service therefore requires explicit task-owned reconciliation of
the release contracts and command implementations; it cannot be claimed from the current Public loader.

## Decision

1. **The live site starts with the first map.** When the slice S3 gate is approved, serve a **FROZEN RELEASE** on
   the owner's public route: a tunnel to a fixed loopback port. The route's domain and provider are not named in
   the pack. Use `EII_TRAFFIC_PROVIDER=simulated` and only the keys the live service needs. This does not enable a
   live model or any optional provider merely because a key exists.

2. **Separate live, staging and development.** Live runs from its own release folder, its own database and its
   own loopback port. Development and staging run on other ports and never touch the live release or database.
   Staging uses a separate copy for its checks. Reuse S3-T20's remote boundary; do not serve a mutable development
   checkout as the live release.

3. **Continuous promotion uses the complete checklist.** From the first map on, promote every ready user-visible
   piece, whether a finished slice, card family or enhancement, only when all of these hold:

   - Its work is merged on `main` with the six required hosted checks green.
   - Another maker has returned **APPROVED** for the work being released.
   - The whole test on the release exits **0**.
   - The staging copy passes both a smoke test and a health check.
   - The previous release folder is kept for instant rollback.
   - Unfinished features are absent from the release.

   The lead promotes on a green checklist. A failed or missing result is not green. A ready piece still satisfies
   its existing task and slice gates; incremental promotion does not waive them.

4. **Switch releases, retain rollback and log every promotion.** Promotion switches which release and port the
   public route serves. Keep the preceding release folder so rollback can switch the route back immediately.
   Every promotion is logged with its release id and every checklist result. Development or staging is never
   promoted implicitly by a restart or a change in its files.

5. **One task owns the operational runbook and its command implementations.** Add S3-T28 for starting live,
   starting staging, promoting and rolling back, using the existing commands. It owns implementing `./eii freeze`,
   `./eii build-release` and `./eii load-release`, today placeholders that exit 1, with their existing contracts.
   It coordinates with S3-T20's entry and documents the exact operator steps and expected results in document 13.
   Later S11-T01 and S11-T06 retain their hardening, register and acceptance checks; no criterion is deleted or
   marked passed by assigning an earlier implementation owner.

   Resolve the Public-only first-map freeze incompatibility explicitly in this task's plan and reviewed contract
   amendments. Never invent a protected window, dummy register entry or synthetic table to make the first map
   freeze. No changed `window_key`, register, two-run freeze or exit-7 rule is authorized. Any material choice not
   settled by this decision goes through AGENTS.md rule 46 before implementation.

6. **Every release stays bound by the existing rules.** Slice gates are unchanged. AGENTS.md rule 12 binds every
   applicable freeze and release: its `window_key` and export-register invariants, both no-flag freeze runs and
   frozen install/start refusal with exit 7 remain. Rule 24's prohibited claims bind every release, including the
   first map and every enhancement. Preflight only probes; only the database commands start or stop the database;
   start never reloads over a mismatched schema (rules 44 and 45). Offline tests and gates need no tunnel, key or
   network. No command permission or working-command claim is added by this documents-only record.

## Consequences and change triggers

S3-T28 belongs to slice S3 because S3-T02 owns the first Public release/load layer and S3-T20 owns its post-gate
remote entry. It follows the approved S3 gate and S3-T20, and is excluded from S3-T11's pre-gate blanket dependency
so it creates no cycle. Preparation follows the existing queue rules; live service waits for the gate and the
verified frozen release. First launch and each promotion require their real evidence, not this record.

The task's implementation updates command documentation and identical AGENTS.md/CLAUDE.md wording when the
placeholders actually work. Until then rule 44 stays true and unchanged. A different promotion checklist, shared
live/development state, unfinished feature in a release, different default traffic mode or weaker freeze rule
requires a new decision. Proposed implementation choices are returned to the lead rather than inserted into
OPEN_ITEMS.md by this documents-only change.

## Sources

- The owner's decision of 2026-11-20, after-go-live operations and continuous promotion, supplied in the task brief.
- [Decision 0041](0041-remote-mode-through-the-owners-own-host.md), items 1 to 10; [TASKS.md](../../TASKS.md),
  S0-T09, S3-T02, S3-T10, S3-T20, S11-T01 and S11-T06.
- [13_DEPLOYMENT_AND_OPERATIONS.md](../13_DEPLOYMENT_AND_OPERATIONS.md), **5. Store selection, the presenter switch and the local ledger**,
  **6. The `./eii` commands** and **7. Building, loading and freezing a release**; [AGENTS.md](../../AGENTS.md), rules 12, 24, 33,
  36, 44 and 45.
