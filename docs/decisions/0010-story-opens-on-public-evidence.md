# 0010 — The story opens on public evidence

| | |
|---|---|
| Status | Accepted, 2026-11-11 |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Record why the guided story and the build order both start from real public data, before anything synthetic or simulated is shown. |
| Read first | [16_DEMO_RUNBOOK.md](../16_DEMO_RUNBOOK.md), [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md) |

## Context

- The guided story lasts 8 to 9 minutes in front of a Minister. The first minute decides whether the audience trusts the rest.
- Earlier designs opened on a simulated living map, or on a synthetic wage map drawn over real districts.
- The strongest objection to the whole product is "it is all synthetic".

## Decision

1. Scene 0 (30 seconds) shows real public evidence only: the zone map lit by real electricity growth, licence density and transit ridership. The standing strip and the four provenance marks dock and never leave.
2. The Simulated dial comes second, as an index, with no wages. Synthetic wages appear only in scene 2, together with the housing split, the not-measured share and the "average alone is not enough" pair.
3. The build order follows the story. slice S3 delivers a public-only flagship answer end to end, with no synthetic data and no model, before the synthetic world exists.
4. The public-only answer is on the never-cut list.

## Evidence

- Minister-impact judge (2026-11-11): opening on a simulated crowd invites the question "is this real footfall?" in the first minute, and against telecom footfall products that answer loses. Open on real public momentum, then turn the dial.
- Engineering judge (2026-11-11): drop the synthetic median-wage map as the opening image.
- Feasibility judge (2026-11-11): a public-only flagship answer early means that "a showable product exists from here".
- The public figures exist and were verified on the Qatar Open Data Portal (licence CC BY) on 2026-11-11 by two independent research agents: electricity use in zone 69 (Lusail) in 2025 was 3.34 times its 2021 level, against 1.34 times nationally; Metro riders reached 7.38 million in December 2025, up 33% on December 2024; restaurant licences per 10,000 residents were 32 in Al Daayen against 15 nationally.
- Whether the opening persuades an audience is a judgement. It has not been tested with one.

## Consequences

- The architecture must serve a release whose Protected and Simulated tables are empty (architecture document, section 4).
- Public figures stay on their official geographies and are never blended into a protected figure.
- Electricity use is a proxy for activity, not a count of people. The card must say so.
- The opening depends on the public pack being verified in slice S2: every stored figure has its URL, licence, retrieval date and hash, and a reviewer checks 20 random figures against source.
- Public tables that conflict must be reconciled before either number is displayed (open item OI-03).

## What would change this decision

- A licence or accuracy finding that removes the opening's sources.
- Real feeds: the opening could then show protected statistics from real records, by a new record.
- The owner choosing another opening after rehearsal. The never-cut rule for the public-only answer stays.

## Open questions and assumptions

- OI-03: two restaurant totals and two wage-table means must be reconciled before display.
- OI-04: census map layers state no licence; they are fetched at build time and never committed.
- This record makes no ASSUMPTION.

## Sources

- Master design, guided story and verified public figures (project record held by the owner, 2026-11-11).
- Qatar Open Data Portal, https://www.data.gov.qa/ , licence CC BY, figures checked 2026-11-11. Dataset names and links are in [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md).
- EII minister-impact judgement, engineering-and-delivery-risk judgement and feasibility-and-cost judgement, 2026-11-11 (project records held by the owner).
