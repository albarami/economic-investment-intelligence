# Decision 0082: One fixed public entry; promotion switches the served release

| | |
|---|---|
| Status | Accepted, 2026-11-21 |
| Date | 2026-11-21 |
| Owner | The owner |
| Decided by | The owner's approval of 2026-11-21, conditional on no quality effect |
| Amends | [Decision 0071](0071-after-go-live-operations-and-continuous-promotion.md) item 4, interpreting "and port" as the internal backend port behind the fixed entry; [OPEN_ITEMS.md](../../OPEN_ITEMS.md), OI-347; [TASKS.md](../../TASKS.md), S3-T28 box 7; [docs/README.md](../README.md), decision index |
| Purpose | Reconcile the fixed loopback entry with promotion's release and port switch under AGENTS.md rule 46 |
| Read first | Decision 0071 items 1 to 4; decision 0041 item 1; TASKS.md S3-T20 and S3-T28; document 13, S3-T28 isolated Public setup and operator sequence; AGENTS.md rule 46 |

## Context and evidence

OI-347 records the apparent conflict between decision 0071's fixed loopback entry
and item 4's switch of the release "and port". The owner approved the lead's
default on 2026-11-21: one fixed loopback port for the public entry; promotion
switches which release it serves; no second public port. Approval is conditional
on no quality effect. The closure instruction requires a design comparison before
recording the decision, and a new build plan if the built design differs.

The existing S3-T28 implementation matches that default:

- `scripts/operations/config.py`, `DEFAULT_PORTS` and `LIVE_BACKENDS`, separate
  the live entry at 8088 from internal backends 18088 and 18089.
  `read_environment()` refuses a different live entry port or non-loopback host.
- `scripts/operations/activation.py`, `activate()`, requires live entry port
  8088, selects the other permitted backend for promotion, verifies the complete
  evidence and retained installation, and records authorisation before service.
  Readiness and the durable outcome precede atomic replacement of `route.json`.
  Rollback validates the retained predecessor's release, application, backend
  port and code version. `active_route()` and `require_predecessor()` bind the
  route and predecessor to their durable authorisations.
- `scripts/operations/deploy.py`, `up()`, starts a release on its requested
  internal backend port, reuses the owned entry process at 8088 or starts that
  same fixed entry, and retires the previous backend after the switch.
  `require_retained()` verifies the retained installation and archive.
- `scripts/operations/entry.py`, `main()`, binds only `127.0.0.1:8088`;
  `handler()` forwards each request to the authorised route's internal backend.
  `scripts/operations/serve.py`, `main()`, binds backend service to loopback.
  These promotion paths open no second public entry.
- `scripts/operations/runbook.py`, `verify_transcript()`, checks the invented
  promotion and rollback sequence against the two live backend ports.
  `scripts/tests/test_s3_t28_matrix.py`, `Matrix.test_ac7_*`, checks route,
  authorisation, target and rollback refusals. The native archive test in
  `product/tests/test_offline_installation.py` checks identical isolated
  installation; it does not prove a public launch.

This is a records-only reconciliation of the existing design. It changes no
serving behaviour or quality control. Actual reruns and deliberate violations
are recorded in [PROGRESS.md](../../PROGRESS.md), **S3-T28 box 7 — fixed-entry
reconciliation, 2026-11-21**. It does not claim that reconciliation preceded the
existing implementation.

## Decision

1. **Keep one fixed entry.** The public route terminates at the single fixed
   IPv4 loopback entry on port 8088. Promotion and rollback do not change that
   entry port and do not add a second public port.

2. **Switch the release and its internal backend.** In decision 0071 item 4,
   "and port" means the internal backend port behind that fixed entry. A green
   promotion switches the authorised release and internal backend served by
   the entry. It never redirects the public route to staging or development.

3. **Retain rollback and every existing check.** Keep the preceding release,
   application archive and installation for rollback. Restore its authorised
   release and internal backend through the same fixed entry. Decision 0071
   item 3's complete checklist, durable promotion log and every checklist
   result remain required. This decision changes no gate, privacy rule,
   security control, command permission or protected-release obligation.

4. **Close OI-347 on this reading.** The owner's approved default and the built
   promotion design agree. S3-T28 box 7 may be recorded after its deciding tests
   and two separate deliberate violations have been rerun red then restored
   green. S3-T20 still owns the actual public handover after gate approval;
   this decision opens no public route and approves no slice gate.

## Consequences and change triggers

Decision 0071's original wording and OI-347's earlier evidence remain preserved.
This record supplies their explicit reconciliation under rule 46, including the
same wording repeated in S3-T28 and document 14's operations note. No routing
implementation change is needed. A proposal to change the fixed public port,
expose an internal backend, open another public port or weaken rollback or its
checklist requires a new reviewed decision. If a later plan finds a quality
risk in the approved default, stop and return that choice to the owner before
implementation.

## Sources

- The owner's approval of 2026-11-21, item 1, and the supplied closure plan's
  S3-T28 box 7 instruction; cited by date without names or private note paths.
- [Decision 0071](0071-after-go-live-operations-and-continuous-promotion.md),
  items 1 to 4; [decision 0041](0041-remote-mode-through-the-owners-own-host.md),
  item 1; [AGENTS.md](../../AGENTS.md), rule 46; [OPEN_ITEMS.md](../../OPEN_ITEMS.md),
  OI-347; [TASKS.md](../../TASKS.md), S3-T20 and S3-T28.
- [Document 13](../13_DEPLOYMENT_AND_OPERATIONS.md), **S3-T28 isolated Public
  setup and operator sequence**; implementation and test functions identified
  under **Context and evidence**; [PROGRESS.md](../../PROGRESS.md), **S3-T28 box 7
  — fixed-entry reconciliation, 2026-11-21**.
