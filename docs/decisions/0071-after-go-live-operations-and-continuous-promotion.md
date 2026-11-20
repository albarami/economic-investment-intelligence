# Decision 0071: After-go-live operations and continuous promotion

| | |
|---|---|
| Status | Accepted, 2026-11-20 |
| Date | 2026-11-20 |
| Owner | The owner |
| Decided by | The owner's decision of 2026-11-20 |
| Amends | [TASKS.md](../../TASKS.md), S3-T28 before the slice S3 gate, S3-T11 Depends and new S11-T09; [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md), task rows and slices S3 and S11 operations notes; [OPEN_ITEMS.md](../../OPEN_ITEMS.md), OI-346 resolution; [docs/README.md](../README.md), decision index. Assigns public_only build/load and live/staging setup to S3-T28 and protected freeze/promotion integration to S11-T09, retaining S11-T01 and S11-T06 and all their checks. |
| Purpose | Start the live site with the approved first map, isolate it from development and staging and promote ready visible work through a recorded green checklist. |
| Read first | Decision 0041 items 1 to 10; TASKS.md S0-T09, S3-T02, S3-T10, S3-T20, S3-T28, S11-T01, S11-T06 and S11-T09; document 03 DAT-133; document 02 ARC-41 and ARC-22; document 13 sections 5, 6 and 7, OPS-63 and OPS-64; AGENTS.md rules 11, 12, 24, 33, 36, 44 and 45. |

## Context

The owner's decision of 2026-11-20 starts live service with the first map, when the slice S3 gate is approved,
and promotes subsequent ready user-visible pieces continuously. The first map uses a fixed content-addressed
`public_only` release while development continues elsewhere. This is an operations decision, not a claim that
the commands or the first map work today.

The owner's placement note, adopted by lead ruling L-1219, puts live and staging setup before the slice S3 gate
so the first map does not wait on its own setup. S3-T20 still owns the remote entry after that gate under
decision 0041. S0-T09 owns the command skeleton, S3-T02 the Public release/load layer, and S11-T01 and S11-T06
the protected freeze and export register. S3-T28 builds and tests the first map's setup on loopback, then uses
S3-T20's entry when it opens after approval. S11-T09 integrates protected-release operations later.
AGENTS.md rule 44 still describes `freeze`, `build-release` and `load-release` as placeholders that exit 1;
this record assigns implementation without claiming it exists.

## Decision

1. **The live site starts with the first map.** When the slice S3 gate is approved, serve a **fixed content-addressed
   `public_only` release** on the owner's public route: a tunnel to a fixed loopback port. The route's domain and
   provider are not named in the pack. Use `EII_TRAFFIC_PROVIDER=simulated` and only the keys the live service needs. This does not enable a
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

5. **Setup precedes the slice S3 gate; protected operations belong to slice S11.** S3-T28 owns starting live,
   starting staging, promoting, rolling back and logging, with the `public_only` `./eii build-release` and
   `./eii load-release` commands the first map needs. It belongs to slice S3, before its gate; S3-T11 depends on
   it. It depends on S3-T02, not on the approved gate, S3-T20 or a later S11 task. Build and test on loopback;
   use S3-T20's entry when it opens after the gate, with decision 0041 unchanged. Public startup refuses without
   recorded S3 gate approval. Local setup completion does not require the later public opening.

   The owner's two sentences, quoted word for word in the placement note adopted by L-1219, are:

   > when the first map is ready push it to the website we create and leave it separate from the development so its stable and keep pushing enhancements in it when its ready

   > i want this map to be in that envitment while we keep deleopbing all the s

   S11-T09, split from S3-T28, owns protected-release operational integration: the two no-flag `./eii freeze`
   runs, the export-register line, frozen install/start refusal with exit 7 and protected-release promotion.
   It depends on S11-T06 and S3-T28. S11-T01 and S11-T06 keep their existing implementation, hardening and
   acceptance criteria; none is deleted or marked passed. Both operational tasks document exact operator steps and
   expected results in document 13 using the existing commands.

6. **Every release stays bound by the existing rules as written.** Rule 12 is unchanged and binds every release.
   Its frozen install/start condition says **"For a frozen release only"**. DAT-133 and OPS-63 define a
   `public_only` release as never frozen or entered in the export register. ARC-41 and the glossary **Release**
   entry define its kind: no Protected or Simulated table; no `window_key`, `protected_sha256`, `parameter_set`,
   `world_seed` or `scenario_sha256` (ARC-41 also omits `contracts`). The first map selects no privacy parameter
   set, because nothing protected is exported. This is the release-kind contract, not an exemption from rule 12;
   no protected window, dummy register line or synthetic table may be invented to satisfy a frozen-only check.

   The `public_only` first map uses the same complete L-1212 promotion checklist in item 3. Both stores load
   with parity and no fallback, with a complete receipt matching the manifest `release_id` (OPS-64, ARC-22).
   Retain its fixed content-addressed `release_id` for rollback. Rule 11 still forbids a product import of
   custodian code or a vault read, and every security check remains unweakened. For a frozen protected release,
   rule 12's canonical `window_key`, immutable unique export register, both no-flag freeze runs and install/start
   exit-7 refusal remain exactly as written, implemented and tested through S11-T01, S11-T06 and S11-T09.
   A missing register line or incomplete freeze is remedied by finishing the freeze, never by changing the seed.

   L-1219 answers OI-346 with these anchors; no first-map freeze reconciliation remains open. Slice gates and
   rule 24's prohibited claims bind the first map and every enhancement. Preflight only probes; only the database
   commands start or stop the database; start never reloads over a mismatched schema (rules 44 and 45).
   Offline tests and gates need no tunnel, key or network. No command permission or working-command claim is
   added by this documents-only record.

## Consequences and change triggers

S3-T28 belongs to slice S3, before its gate, because S3-T02 owns the first Public release/load layer and the
approved first map must not wait for live/staging setup. S3-T11 includes S3-T28 in its pre-gate dependency;
S3-T20 alone keeps its post-gate exception. Setup runs locally before approval; the lead's actual public launch
waits for recorded gate approval and S3-T20's entry. S11-T09 follows S11-T06 and S3-T28 and is included in
S11-T07's every-other-task dependency before the slice S11 gate. First launch and each promotion require real
evidence, not this record. OI-347 still owns reconciliation of the fixed entry with promotion's port switch under
rule 46 before implementation; this placement decision adds no second public port.

Each task's implementation updates command documentation and identical AGENTS.md/CLAUDE.md wording when the
placeholders actually work. Until then rule 44 stays true and unchanged. A different promotion checklist, shared
live/development state, unfinished feature in a release, different default traffic mode or weaker freeze rule
requires a new decision. Other unresolved implementation choices return to the lead under rule 46; this change
records only L-1219's answer to OI-346 and keeps the other open questions.

## Sources

- The owner's decision of 2026-11-20, after-go-live operations and continuous promotion, and the placement note
  with the two verbatim sentences, supplied in the task brief; lead rulings L-1212 (item 3 checklist) and L-1219
  (setup before the slice S3 gate and OI-346 answer, citing rule 12, DAT-133, OPS-63, ARC-41, OPS-64 and ARC-22).
- [Decision 0041](0041-remote-mode-through-the-owners-own-host.md), items 1 to 10; [TASKS.md](../../TASKS.md),
  S0-T09, S3-T02, S3-T10, S3-T11, S3-T20, S3-T28, S11-T01, S11-T06, S11-T07 and S11-T09.
- [13_DEPLOYMENT_AND_OPERATIONS.md](../13_DEPLOYMENT_AND_OPERATIONS.md), **5. Store selection, the presenter switch and the local ledger**,
  **6. The `./eii` commands** and **7. Building, loading and freezing a release**; [AGENTS.md](../../AGENTS.md), rules 12, 24, 33,
  36, 44 and 45; [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md), DAT-133;
  [02_ARCHITECTURE.md](../02_ARCHITECTURE.md), ARC-41 and ARC-22; document 13, OPS-63 and OPS-64;
  [GLOSSARY.md](../GLOSSARY.md), **Release**; [OPEN_ITEMS.md](../../OPEN_ITEMS.md), OI-346 and OI-347.
