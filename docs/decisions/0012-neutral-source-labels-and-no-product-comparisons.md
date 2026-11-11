# 0012 — Neutral source labels and no product comparisons

| | |
|---|---|
| Status | Accepted, 2026-11-11 |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Record why record types carry neutral names, why no custodian is named, and why public materials compare the product with no named product. |
| Read first | [01_PROJECT_BRIEF.md](../01_PROJECT_BRIEF.md), [02_ARCHITECTURE.md](../02_ARCHITECTURE.md) |

## Context

- The five record types are held by different custodians. This proof of concept uses none of their data, and none of them supplied, reviewed or endorsed it.
- The repository is public. The audience may own the existing services that a careless sentence would criticise.
- The research compared the idea with existing services, but only from their published descriptions and not from hands-on use.

## Decision

1. Record types have neutral contract names: `business_register.v1`, `employment.v1`, `wages.v1`, `residence.v1`, `mobility.v1`. The pack says "custodian" and never names one.
2. Source labels on screen use the neutral record-type names by default. Naming custodians on screen is an owner choice (open item OI-06), made by one configuration value that the interface reads from the API. Its default is the neutral names.
3. Public materials (the repository, the documents, the screens, the briefing pack) compare the product with no named product. They speak generically: "existing public business maps", "telecom footfall products", "commercial purchasing-power layers", "investment-portal assistants".
4. Public data sources are always named and cited. That is required attribution, not comparison.
5. Software components (databases, libraries, the model) are named in engineering documents, with measured facts and sources. ASSUMPTION: a builder cannot work without their names, and a measured engineering choice is not a market comparison.
6. No material says or implies that an existing public service is wrong or inferior, or that any ministry has endorsed or runs the system.

## Evidence

- The master design's list of prohibited claims (2026-11-11), which this record applies.
- Both final judges (2026-11-11): every finding about what existing services lack rested on reading published descriptions or interface text, not on use. They list a gap claim that the audience knows to be false, and framing that embarrasses the host, among the outcomes most likely to make the audience refuse the product.
- Their conclusion: the claim to be different must rest on the join of record types, the visible privacy controls and real public economics with provenance, and not on features that others could add within a quarter.
- Architecture research (2026-11-11): no source states which database platform the operating bodies run (status: unverified). No fit may therefore be claimed.
- An earlier draft prefixed each contract name with the abbreviation of a custodian. A reader takes such a name to mean "data from that custodian", which is false here.

## Consequences

- Contract names, table names and field names carry no custodian name, so a later owner decision under OI-06 changes labels only.
- The documentation check scans every text file for forbidden patterns from a maintained forbidden-name registry of existing products and of custodian bodies as suppliers or endorsers. The registry is kept outside the repository, so that the public repository never lists those names; `scripts/check_docs.py` reads it from the file named by the environment variable `EII_FORBIDDEN_PATTERNS_FILE` when that is set. The scan covers documents, prepared strings, web assets and exports, and a recorded human review for implied inferiority or endorsement runs before each release.
- The demonstration answers "why not use the existing services?" this way: they do their own jobs well; this adds what only joined records can show.
- The one permitted deployment sentence is the sourced one in [13_DEPLOYMENT_AND_OPERATIONS.md](../13_DEPLOYMENT_AND_OPERATIONS.md).
- Decision records may weigh one software component against another when a measurement supports it. They state the measurement, who made it and when.

## What would change this decision

- The owner's decision under OI-06 to name custodians on screen. Labels change by configuration; no code or contract name changes.
- A formal partnership that makes a named comparison or an endorsement both true and approved. Until then the rule holds even where a comparison would flatter the product.

## Open questions and assumptions

- OI-05: the product name and its Arabic name need the owner's clearance. Working title: "Economic & Investment Intelligence (EII)".
- OI-06: source labels on screen; neutral record-type names by default.
- ASSUMPTION: decision 5 above. No environment variable is pinned for the label choice; the value lives in the product's configuration until the owner decides OI-06.

## Sources

- Master design, prohibited claims and open items (project record held by the owner, 2026-11-11).
- EII feasibility-and-cost judgement, minister-impact judgement and architecture-options research, 2026-11-11 (project records held by the owner).
