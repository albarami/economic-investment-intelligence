# 0041 — Remote mode through the owner's own host

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-16 |
| Owner | The owner |
| Decided by | The owner, in the relayed note of 2026-11-16; placement and command timing under rulings L-663 and L-667 |
| Amends | Remote access under document 02, ARC-35 and ARC-36; TASKS.md and document 14, slice S3; document 17, Hardening register |
| Purpose | Authorise remote mode and queue its implementation after the slice S3 gate, without claiming that it exists. |
| Read first | Decision 0019, What would change this decision; document 17 sections 5, 6 and 6.1; document 02, ARC-35 and ARC-65; AGENTS.md rules 26 to 29, 44, 46 and 47 |

## Context

The owner's relayed note of 2026-11-16 asks to open the locally running product from another device through the owner's own tunnel. It records the owner's choice of no login gate. Rulings L-663 and L-667 adopt that request and place it after the slice S3 gate as S3-T20, since S3-T18 and S3-T19 already have other work. This is an amendment for a public address, extending decision 0019, “What would change this decision”, and document 17 section 6; it does not grant permission for sources beyond their existing terms.

## Decision

1. **One web entry.** Remote mode serves the web application and API under one origin on the IPv4 loopback at port 8088, with HTTP only on that loopback, compression on and streaming passing through. The owner's own tunnel reaches that entry and provides HTTPS at the owner's own host name, read from `EII_REMOTE_HOST`. The name is never written in a committed file; tests use an invented host (L-663, A-663a; note point 1). This extends document 02, ARC-35 and ARC-36, without widening the API bind or adding a second public port.
2. **Host and origin boundary.** Host and origin rules accept only that one name and localhost. Cookies, if any, are Secure and SameSite. The tunnel connects to the loopback; the API keeps its loopback bind (note point 2; document 02, ARC-35). A host or origin outside those two is refused.
3. **Local presenter and owner-controlled spend.** The presenter console and all its controls stay on the stage machine's localhost only, never reachable through the host, including when `EII_PRESENTER` is enabled (document 02, ARC-65). In remote mode the assistant uses recorded replays and templates only; no provider key is read and no paid assistant call is made unless the owner sets `EII_REMOTE_ALLOW_PAID_ASSISTANT=1`. S3-T20 defines that environment variable, off by default; no test, CI job or lead sets it (note point 3; L-663). This switch does not authorise a run-time typed-decision gateway or override AGENTS.md rules 26 to 29.
4. **Hosting-off sources stay off.** Remote-mode configuration keeps the optional traffic provider, relative-busyness source and weather history off under document 17, DHA-85, DHA-86 and DHA-87, and decision 0019, “What would change this decision” (note point 4). It grants no new source permission under DHA-50 to DHA-54 or DHA-102.
5. **Remote evidence command.** Authorise `./eii remote-check`: from this machine it requests the owner's own host name, read from `EII_REMOTE_HOST`, through the owner's own tunnel, never the loopback. It checks the health page, the start page in both languages, one API call returning a card with its Fact chip, the map style and one tile, and one streamed answer. Each item prints PASS or FAIL with its HTTP status; where no response exists it states that no HTTP status was received. Failure gives a clear message when the tunnel or product is down, without claiming to distinguish causes that the response cannot establish. It is the only command that reaches the network through the tunnel, never run by a test or CI. The lead runs it at every slice gate from S4 on and records the result in that gate record. ASSUMPTION: the slice S3 gate approves before S3-T20 exists; when S3-T20 merges its remote-check result is added to the S3 gate record as an addendum (note point 5; L-663 as amended by L-667 and A-663c). S3-T20 adds this command to rule 44 of AGENTS.md and CLAUDE.md, byte-identically, in the pull request that builds it; this documents-only amendment does not edit rule 44. Tests exercise the check logic against an invented host on the loopback, including the product-down FAIL message; they never invoke the tunnel command against the real host.
6. **Start on boot.** A documented script starts the product inside the Linux side when the owner's computer starts. The remote check detects that the product is not running. At implementation handover the advisor is told when the web entry is ready to take port 8088 so the placeholder can be stopped (note point 6; L-663 item 5). This record claims no boot setup or handover has happened.
7. **Phone evidence.** Include the first map and the story at phone width in both languages, light and dark, in gate evidence, with the owner's phone opening recorded when performed (note point 7). The S3 evidence follows the addendum timing in item 5.
8. **No login gate is the owner's decision.** Anyone who has the address can open it while the owner's computer is on (owner's relayed note, FACTS). Anything a public address needs beyond the note's seven points, including drawn-area audit and rate limits under document 17 section 5, is recorded in that document's Hardening register, with its origin, not added to S3-T20's acceptance criteria. Existing source permissions under section 6.1 remain unresolved where that register says so; this is no blanket clearance for public source use.
9. **Existing controls stand.** Nothing weakens a gate, check, hard limit, privacy rule or sandbox. AGENTS.md rules 26 to 29 and `EII_DECISION_PROVIDER=none` remain; existing offline gates still run without network. Item 5 adds a separately recorded remote observation, not a network dependency of the offline tests (L-663; AGENTS.md rules 12 and 27).
10. **Placement.** S3-T20 runs only after the slice S3 gate approves and is outside that gate. S3-T10 and S3-T11 do not depend on it. Its web and API foundations are S0-T03, S3-T08 and S3-T09 (TASKS.md, those entries; L-667). S3-T11's “every other task” dependency explicitly excludes this post-gate task.

## Evidence and consequences

The owner's relayed note, points 1 to 7 and its no-login decision, and rulings L-663 and L-667 supply the authority. Their tunnel and placeholder facts are advisor-reported, not independently probed here. This record authorises work; it claims no implemented command, successful remote request, gate approval, source clearance or completed phone check (AGENTS.md rule 47). Document 17's existing hosting-off rules and hardening register retain their roles.

## Amended passages

- TASKS.md: S3-T20 directly after the slice S3 gate; S3-T11 Depends excludes S3-T20.
- Document 14: slice S3 task list adds S3-T20 after S3-T19, explicitly following gate approval.
- docs/README.md: accepted-record list and decision index add 0041.
- Document 17, Hardening register: the public-address follow-up beyond the note's seven points, without new S3-T20 criteria.
- Deferred to S3-T20's implementation pull request: rule 44 of AGENTS.md and CLAUDE.md gains the implemented remote-check command under item 5; neither file changes here.

## Open questions and change control

Adopt A-663a (host only in the owner's environment) and A-663b as amended by A-663c (command-list amendment with implementation). The S3-gate addendum timing is the explicit assumption in item 5. To obey the brief's ban on writing an IP address, item 1 specifies the IPv4 loopback in words. The switch name in item 3 is defined by this decision for S3-T20; it is not an existing setting. No live host or tunnel is needed to draft or test the documents. Further public-address hardening and source clearances remain document 17 work, not inferred permission or extra task criteria. Material changes require a new decision record (AGENTS.md rule 46).

## Sources

- Owner's relayed note of 2026-11-16, FACTS and points 1 to 7; lead rulings L-663 and L-667, including A-663a, A-663b and A-663c (masked assignment records).
- [Decision 0019](0019-forecasts-estimates-scenarios-and-self-serve-sources.md), What would change this decision.
- [Document 17](../17_DEPLOYMENT_HARDENING.md), sections 5, 6, 6.1 and 9; DHA-40 to DHA-43, DHA-50 to DHA-54, DHA-85 to DHA-87 and DHA-102.
- [Document 02](../02_ARCHITECTURE.md), ARC-35, ARC-36 and ARC-65; [TASKS.md](../../TASKS.md), S0-T03, S3-T08 to S3-T11 and Difficulty and personas.
- [AGENTS.md](../../AGENTS.md), rules 12 to 15, 26 to 29, 33, 44, 46 and 47.
