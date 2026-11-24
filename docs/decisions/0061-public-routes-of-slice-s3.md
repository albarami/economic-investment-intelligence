# Decision 0061 — Public routes of slice S3

| | |
|---|---|
| Status | Proposed; task-owned draft, no gate approval |
| Date | 2026-11-19 |
| Owner | Project owner |
| Authority | L-1012 Q1, L-1018, L-1022, L-1030, L-1033 and binding L-1036 items 1–4 and L-1060 item 2; independent design review r5 with L-1036 applied |

## Context

The S3-T10 plan found no browser-to-release path. Document 08 section 8.1 already fixes the four paths; classed layers lacked a shared class method. This record amends TASKS.md and document 14 slice S3, document 03 fixed reads and named queries, document 07 section 1 (MTH-126), document 08 BE-117, BE-109, section 12 RATE_LIMITED, its section 8.1 layer contract and routing section. It closes the shape-limit choice without changing any privacy rule.

## Decision

1. S3-T22 mounts the four routes of the Goal.
2. No five widenings: S3-T12, S3-T14, S3-T13, S3-T04 and S3-T08 are built and several approved; S3-T22 makes the named forced differences F1–F14 and F15–F16, each confirmed by its reviewer.
3. Every path, schema, status and code comes from document 08 §§6.1, 6.2, 8.1, 12; only the four §6.1 statuses become envelopes, every other outcome a §12 error.
4. Class method MTH-126; a zone the calculator does not rank is shown not ranked, never classed, and a selected one shows its own reason.
5. BE-117 gains "500 vertices, a request body of at most 64 KiB, and at most 50 shapes held per session"; its OPEN line closes.
6. Until S9-T02, `eii_session` (HttpOnly, SameSite=Strict, Path=/; no Secure on loopback HTTP until S3-T20), memory only, cleared on restart, never shared. BE-109 gains "at most `SESSION_CAP` live sessions (default 1,000); a new session beyond it is refused with `RATE_LIMITED`; no live session is evicted"; the §12 `RATE_LIMITED` meaning gains "or the process holds its live-session cap (BE-109)".
7. `fc_firms_per_tower` and its bodies unchanged; S3-T20's loopback entry stays; no development proxy.
8. Field gaps named, not filled: G1, no ledger field marks a direct call (`kind` admits none) and `tool_entry` labels every direct call `playbook="site_check"`; G2, the public-only partition key is `cells` (L-1022 item 2). The owner rules on both.
9. S3-T10 depends on S3-T22.
10. No gate, privacy rule, tolerance or check is weakened.
11. The §8.1 layer row gains: "A classed layer (`night_lights`, `land_prices`, `zone_electricity_growth`) carries `class_breaks`: for each class present, its class key and the fact ID of its boundary feature, in one group, or for `land_prices` one group per use category; no low or high value is sent; the browser checks the keys and binds each fact, refuses a missing, unbound, wrong-class or empty band, and draws the present bands with `compact` Fact chips. The hero carries `not_ranked` zones, each with its closed reason, drawn as outlines and selectable." It continues: "The layer sends the classes present from the lowest upward; the browser accepts any present classes in ramp order without a repeat, one bound break for each, and never adds an empty class. `land_prices` groups come in the code-point order of their use category; the browser draws, lists and legends one use at a time, starting with the first group, and switches only by the category control; every group stays in the payload. After an area is submitted, only Public point and listing features are kept by their position inside the outline; classed and unclassed source-geography layers, including zoning, parcels, rail lines/protection zones, health-centre catchments and property-price fills, stay whole as the same objects on their published geography with all geometry and metadata, including class breaks and not-ranked zones where present; non-Public layers remain untouched, and the area cards still use the exact outline."
12. The routing section gains: "The API process takes its routing only from a source given at start: the `artefacts/routing/` entry of the checked release (ARC-119), or an in-process routing callable in tests; never from a request, never over a network. Every area context the API builds, for `make_area`, for the area cards' decoding and for a playbook, receives it."


## Evidence and consequences

The three passes implement Part M, the invented cards fixture, R1–R4, F1–F16, the routing-context seam, the shared selected-use store, source-geography preservation and scoped parity cases. Ruling L-1060 item 2 adds the closed source-geometry extension of document 03, including holes and MultiPolygon, with exact preservation and bounded transport. PROGRESS.md records actual commands and plants. No implementation review, campaign completion, live parity, Arabic wording approval, merge approval or slice gate is asserted.

L-1036 item 1 settles 429 RATE_LIMITED for session capacity; item 2 authorizes no new live parity runner. Item 3 preserves classed and unclassed source-geography layers whole after an area submission. Item 4 requires S3-T22's full area-filter campaign on its own approved head or merged commit, regardless of an earlier or queued S3-T13 campaign. Its command is `uv run --locked python scripts/mutation_web.py web/src/stage/layers/area-filter.ts`; module, full commit, file hash, counts and decision-0052 lane status must be recorded. An unfinished campaign remains open and blocks the slice gate. These are settled matters, not unresolved policy choices.

## Open matters and change control

The existing layers.py refusal bodies await S3-T11. Playbook shape-id support awaits S3-T10's scene choice. S3-T20 owns Secure cookies. G1's fixed site_check label and missing direct-call field await the owner. Real-store statement-timeout classification remains absent; injected TimeoutError is no proof of it. No authorized live runner reaches the new parity cases; an in-process second-engine stand-in is never live PostgreSQL evidence. No content-digest rule exists for a routing folder; routing_from_release checks listing, ARC-119 and config.json only. The serving entry that passes the checked release's routing into create_app remains unbuilt. None of these limitations is silently closed here.

Every forced difference needs another maker's file-by-file confirmation. state/area-actions.ts has only the F6 changes, listed and confirmed hunk by hunk; it is excluded from the later blanket empty-diff proof. The financial-centre files, route branch and tests and unrelated Stage/map/selection/shell files keep that proof. Further material amendments need a new decision record under AGENTS.md rule 46.

## Sources

TASKS.md S3-T22; document 14 slice S3; document 03 Fixed Public context reads (S3-T14); document 07 Classes of a classed map layer; document 08 sections 6.1, 6.2, 8.1, 8.3, 10 and 12; document 02 ARC-119; decision 0052; the authority rulings recorded above. This draft describes intended final behavior; PROGRESS.md distinguishes implementation evidence from pending work (rule 47).
