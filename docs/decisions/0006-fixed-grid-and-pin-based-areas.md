# 0006 — Fixed grid and pin-based areas

| | |
|---|---|
| Status | Accepted, 2026-11-11 |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Record why all custodian-type statistics sit on one fixed grid and why an area can come only from a pin. |
| Read first | [02_ARCHITECTURE.md](../02_ARCHITECTURE.md), [0007](0007-disclosure-control-by-pooling-and-stable-treatment.md) |

## Context

- A company asks about what is "within reach of this door". The naive answer is a free-drawn shape over records.
- Two nearly identical shapes can be subtracted to isolate a small group. The stack research and the engineering judge both named free drawing as an attack surface.
- Public statistics already have official geographies: municipality, zone and district.

## Decision

1. One fixed grid carries all custodian-type statistics: H3 resolution 9 in Greater Doha and 8 elsewhere.
2. Public statistics stay on their official geographies and are never blended into a protected figure.
3. Areas come only from a pin: `distance` (250 m, 500 m, 1 km), `walk` (5, 10, 15 minutes), `drive` (5, 10, 15 minutes, plus a drive-only 30-minute cut-off for staffing). Flagship defaults are walk 5 minutes and drive 10 minutes. The cut-offs are defaults to confirm at slice S1. The 30-minute cut-off is required in the privacy, routing and parity tests and is used by the `staffing_and_pay` playbook.
4. Every area is snapped to whole release units before any figure is read, and comes with a snap report. There is no free drawing.
5. H3 arithmetic runs in the build engine and in Python. Cells are stored as 64-bit integers. PostgreSQL carries no H3 extension.

## Evidence

- H3 documentation, resolution table (retrieved by the stack research, 2026-11-11): the average cell area is 0.737 km² at resolution 8 and 0.105 km² at resolution 9. For Qatar's land area of 11,571 km² the stack research computed about 15,700 cells at resolution 8 and about 110,000 at resolution 9.
- deck.gl performance guide (retrieved 2026-11-11): basic layers render fluidly at 60 frames per second up to about one million items. The grid is far inside that; the slice S1 gate tests 110,000 hexagons.
- Engineering judge (2026-11-11): a pin with distance, walking time or driving time "covers every company decision in the brief", while free drawing "adds an attack surface"; a drawing library's behaviour on MapLibre 6 was also unconfirmed.
- Same judge, citing the H3 documentation: hexagons do not subdivide cleanly into seven finer hexagons, so a parent cell is not the exact union of its children. Units are therefore defined by membership (`unit_member`) and drawn as the union of their finest cells.
- Methods research (2026-11-11, pyvalhalla 3.9.1 on the OpenStreetMap Qatar extract): routing graph built in 5 s; a 5, 10 and 15 minute drive-time area in 0.12 s. A departure time alone changed nothing, because the extract carries no traffic speeds.
- Provider pages (checked 2026-11-11): neither in-country managed PostgreSQL service listed an H3 extension.

## Consequences

- Two different shapes that snap to the same units return the identical answer. This is the second act of the "Try to break it" scene.
- Area edges look stepped; the snap report and the snap animation show why. A small ring can snap to a much larger pooled unit, and the report says so.
- Time-of-day differences in `drive` areas come only from explicit speed factors by road class, and every such difference is Simulated.
- The usable resolution is limited by the disclosure rules, not by graphics: finer cells fail minimum sizes more often.

## What would change this decision

- Data owners choosing another base geography or resolution: a new release and a revised record.
- A survival report showing that too little detail survives at these resolutions.
- Free-drawn areas, only with a disclosure design proven safe against subtraction. Not in version 1.
- The spike finding that an isochrone cannot be turned into grid cells reliably: the fallback is then chosen in writing.

## Open questions and assumptions

- The cut-off values are defaults to confirm at slice S1 (master design).
- Resolved by the lead (2026-11-11): capability S2 of the brief is served by the drive-only 30-minute cut-off for staffing (decision 3); the other modes keep 5, 10 and 15 minutes.
- This record makes no ASSUMPTION.

## Sources

- EII technology-stack research, methods research and engineering-and-delivery-risk judgement, 2026-11-11 (project records held by the owner).
- H3, resolution table, https://h3geo.org/docs/core-library/restable/ ; deck.gl performance guide, https://deck.gl/docs/developer-guide/performance ; Valhalla isochrone API, https://valhalla.github.io/valhalla/api/isochrone/ ; retrieved by the research on 2026-11-11.
- OpenStreetMap France, Qatar extract, https://download.openstreetmap.fr/extracts/asia/ (data licence ODbL).
