# 0001 — Fully synthetic records, real public data

| | |
|---|---|
| Status | Accepted, 2026-11-11 |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Record why every custodian-type record in this proof of concept is invented while public data is shown as real. |
| Read first | [02_ARCHITECTURE.md](../02_ARCHITECTURE.md), [01_PROJECT_BRIEF.md](../01_PROJECT_BRIEF.md) |

## Context

- The initiative joins five record types that different custodians hold: `business_register.v1`, `employment.v1`, `wages.v1`, `residence.v1` and `mobility.v1`.
- This repository is public, and the demonstration audience includes bodies that hold such records. Touching one real record would need a legal basis, a secure environment and thresholds set by data owners. None of these exists yet.
- A proof of concept that is entirely invented meets the objection "none of this is real".
- The owner settled both points on 2026-11-11 (master design, owner decisions 1 to 3).

## Decision

1. Every custodian-type record is synthetic. Every company and person is invented. No real custodian record, field, count or parameter is read, at any stage, by any code in the repository.
2. Any public data, Qatari or international, may be used and shown as real, with its source, licence and retrieval date.
3. Mobility, footfall, traffic and geofencing are simulated locally. No telecom operator is contacted.
4. The rule is enforced, not promised. Generators run in a sandbox whose only data input is the public cache. Every generator parameter is listed as ANCHORED to a cited public figure or ASSUMED with a range. Synthetic identifiers look like `SYN-E-7F3K2Q` and never like a real registration, establishment or personal identifier. The build fails on a name collision with a real place or business. There is no nationality attribute anywhere.
5. Every number on screen carries one of four provenance marks: Public, Synthetic, Simulated, Suppressed ([0009](0009-provenance-classes-and-evidence-status.md)).
6. The claim for the synthetic world is "consistent with published anchors within stated tolerances", never "validated".

## Evidence

- Owner decisions 1, 2 and 3, recorded in the master design on 2026-11-11.
- The sandbox is feasible. The engineering judge checked the build machine on 2026-11-11: bubblewrap 0.11.1 was installed, unprivileged user namespaces worked, and a sandbox saw only the folders mounted into it, also with the network unshared. This is one local check, not yet a proof for CI.
- Public data is rich enough to carry real evidence. Checked on the Qatar Open Data Portal (licence CC BY) on 2026-11-11 by two independent research agents: electricity use in zone 69 (Lusail) rose from 429,964,072 kWh in 2021 to 1,436,402,796 kWh in 2025 (3.34 times, against 1.34 times nationally); the active licence table of May 2025 held 249,622 licence-activity counts across 4,755 activity codes; Metro riders reached 7.38 million in December 2025, 33% above December 2024.
- The final judges (2026-11-11) list, among the outcomes most likely to make the audience refuse the product, a synthetic or simulated number mistaken for a fact about a real place (feasibility judge) and any invented figure attached to a real named business (both judges).

## Consequences

- The proof of concept is a product demonstrator and a proof of method. It is not evidence about Qatar, except for figures marked Public.
- Planted truths, traps and canaries show that the method finds what was planted. They show nothing about real places.
- Real suppression rates stay unknown until the privacy engine runs on real data inside a custodian's environment.
- Synthetic firms are located to a grid cell, never to a real named building. No fictional firm is named beside a real one. No firm, owner or individual can be looked up.
- A real feed later needs no redesign: an adapter, the same conformance suite, linkage and the privacy engine inside the custodian's environment, and a new release ([0002](0002-three-planes-and-the-release-boundary.md)).

## What would change this decision

- A written decision by the owner and a data owner to run a pilot on a real feed, inside that custodian's environment, with thresholds set by the data owner and a stated legal basis. Even then real records are read only there, and only a release leaves.
- A licence finding that a public source may not be shown. That source is removed; the rule stays.

## Open questions and assumptions

- OI-04: the census map layers state no licence; they are fetched at build time and never committed.
- OI-11: privacy thresholds are proposals; data owners set the real ones.
- This record makes no ASSUMPTION.

## Sources

- Master design, owner decisions and verified public figures (project record held by the owner, 2026-11-11).
- Qatar Open Data Portal, https://www.data.gov.qa/ , licence CC BY, figures checked 2026-11-11. Dataset names and links are in [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md).
- EII engineering-and-delivery-risk judgement, sandbox check on the build machine, 2026-11-11 (project record held by the owner).
