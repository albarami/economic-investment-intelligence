# Decision 0072: Loopback activation and ready return

| | |
|---|---|
| Status | Implementation of lead ruling L-1238; OI-347 and OI-353 remain owner-open |
| Date | 2026-11-20 |
| Authority | Supplied S3-T28 plan revision 2; L-1219; L-1238 A-S3-28a/b/c and F6 |
| Amends | Document 02 ARC-05 and document 13 section 6, narrowly for S3-T28 live/staging |
| Purpose | Record the fixed-entry/port-switch and detached-readiness reconciliation explicitly |

## Decision

1. Live has one IPv4 loopback entry at port 8088. Its authorised route alternates
   private IPv4 loopback upstreams at ports 18088 and 18089. A candidate starts
   only after its checklist authorisation is durable; readiness precedes the
   atomic route switch; the retiring owned upstream stops afterwards. Rollback
   restores both identity and upstream port. This is L-1238 A-S3-28a's candidate
   answer, not closure of the owner's OI-347 or permission for another public port.
2. ARC-05's single-process assumption has this narrow exception: the fixed
   loopback entry, one active API, and brief overlap with one candidate/retiring
   API. Staging has its own API and port. It is not another product data plane,
   tile server, database controller, watchdog or automatic failover service.
3. For live/staging only, `./eii up` detaches its owned processes and returns zero
   only after matching healthy identity. This applies the L-1238 F6 ready-return
   ruling to document 13's foreground command row; it does not silently replace
   the foreground contract in other environments. The readiness and shutdown
   bounds remain fixed. Down verifies ownership and preserves all data.
4. Only pristine empty history permits `initial_live_activation` with a null
   predecessor; retain the initial installation itself and require all other
   checklist evidence. A later initial request refuses. An initial rollback
   refuses with its own reason. Missing history is never pristine bootstrap.
5. Staging/live operations support `public_only` only. Protected kind refuses
   `protected_release_requires_s11_t09`, under A-S3-28b; OI-353 stays owner-open.
   World build, protected build and the protected two-run freeze/register/start
   integration remain with their existing owners. No privacy or slice gate changes.
6. Loopback setup precedes the S3 gate under L-1219. Public exposure requires
   candidate-bound recorded gate approval and a lead handover through S3-T20's
   future callback. This decision implements no tunnel, boot setup or public opening.

## Evidence and limits

`scripts/tests/test_s3_t28_promotion.py` covers the local transaction with invented
interfaces; the task's return records distinguish contract tests from executed
engine and service evidence. No hosted check, owner answer, independent approval
or public route observation follows merely from this record. Authoritative task
and decision 0071 wording is supplied by the separate documents branch.

## Sources

- Supplied lead rulings L-1219 and L-1238 A-S3-28a/b/c, F6; supplied S3-T28 plan
  revision 2, P4 to P6, and verification specification AC1, AC5 and AC7.
- [Architecture](../02_ARCHITECTURE.md), ARC-05, ARC-22 and ARC-41.
- [Operations](../13_DEPLOYMENT_AND_OPERATIONS.md), sections 5, 6 and 7; OPS-27
  to OPS-31 and OPS-63 to OPS-64.
- [Decision 0041](0041-remote-mode-through-the-owners-own-host.md), items 1 to 10.
