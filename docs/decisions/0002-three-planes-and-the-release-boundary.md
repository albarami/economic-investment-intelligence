# 0002 — Three planes and the release boundary

| | |
|---|---|
| Status | Accepted, 2026-11-11 |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Record why the system is split into three planes and why a content-addressed release is the only thing that crosses from the build to the product. |
| Read first | [02_ARCHITECTURE.md](../02_ARCHITECTURE.md) |

## Context

- The product must show only protected statistics, to companies and to a model that runs outside the country. Joining five record types is the sensitive step.
- Three competing designs were judged on 2026-11-11. One offered a "lab mode" that switched protections off at run time. One vendor proposal kept synthetic person-level records in a locked schema of the serving database.
- One person builds this with coding agents. A boundary that needs judgement to keep will not be kept; it must be testable by machine.

## Decision

1. Three planes. The custodian plane builds offline (`custodian/`). The product plane serves (`product/`). The experience plane runs in the browser (`web/`).
2. The custodian plane is the only place where record-level (synthetic) data exists. It sits in a vault that is deleted after each build.
3. One thing crosses: the release, a folder of Parquet tables with a manifest, named by a hash of its content. The loader enforces names, paths and schemas; disclosure safety additionally requires every release semantic invariant and a trusted build attestation to verify. An allow-list alone is not evidence that a release is safe.
4. The product plane mounts one release read-only, has no path to the vault, and never imports custodian code.
5. The model sits at the far end and receives tool results only.
6. Privacy decisions are made once, at build time. Nothing is decided from query history at run time. No run-time path holds unprotected data: the attack comparison is a replay of signed build-time results.
7. Offline review assistance may send only cleared Public, Synthetic or project text to the typed-decision gateway. Its output is not a release fact and cannot cross into the product without deterministic rules plus human sign-off.

## Evidence

- Engineering judge (2026-11-11): a build-time vault, an immutable release and a read-only run time are "the right shape". For the design ranked first of three, the judge called the custodian plane that emits one frozen, content-addressed release the cleanest path to real feeds: a real feed is accepted when it passes the same conformance suite, and the screen does not change. The judge added the ephemeral vault to that design because deletion makes "the product cannot open records" literally true on the demonstration machine.
- Same judge: a mode with protections off at run time contradicts a run time that can reach only the release. It needs unprotected records at run time, or it is a canned replay. The replay is kept; the mode is dropped.
- Feasibility judge (2026-11-11), on person-level records in a locked schema of the serving database: they "must never enter the serving store at all, which is a stronger guarantee than a role".
- The ephemeral vault costs almost nothing. The architecture research built a 7.5 million-row synthetic test release in 0.85 s on the build machine (2026-11-11), so regenerating from the seed is cheaper than guarding stored records.
- AI research (2026-11-11): the model provider's data-residency page listed the inference geographies "us" and "global" only. The model must therefore be treated as outside the country, and only material fit to show on screen may be sent.

## Consequences

- Every feature must be answerable from released tables. A feature that needs a record at run time cannot be built in this architecture. That is intended.
- A change of rules, thresholds or geography means a new release, not a setting.
- Free-drawn areas, run-time filters over records and model-written queries are out.
- The boundary is tested by machine: the import-boundary test, the sandbox sentinel test, the loader refusal test and the canary scan (section 3 of the architecture document).
- Deployment maps onto it. The custodian plane runs inside a custodian's environment and exports only a release; tools, assistant and interface do not change.

## What would change this decision

- A requirement that cannot be met from precomputed statistics, such as user-defined areas over records. It would need a governed query service inside the custodian plane, with its own disclosure design and its own decision record. It would not be met by loosening this boundary.
- Evidence that the release format cannot carry what a real custodian must publish.

## Open questions and assumptions

- OI-11: thresholds applied at build time are proposals; data owners set the real ones.
- This record makes no ASSUMPTION. The assumptions about the release folder and the manifest are listed in the architecture document.

## Sources

- EII engineering-and-delivery-risk judgement, feasibility-and-cost judgement, architecture-options research and AI-patterns research, 2026-11-11 (project records held by the owner).
- Anthropic, data-residency page, https://platform.claude.com/docs/en/manage-claude/data-residency , retrieved by the AI-patterns research on 2026-11-11.
