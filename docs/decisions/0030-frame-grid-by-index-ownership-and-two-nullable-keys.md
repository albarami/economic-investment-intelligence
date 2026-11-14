# 0030 — The frame's grid by index ownership, the district-free zone and two nullable keys

| | |
|---|---|
| Status | Proposed, 2026-11-14: the lead's decision under the owner's delegation, for the owner's confirmation |
| Date | 2026-11-14 |
| Owner | Project owner |
| Decided by | The lead, in ruling L-255 of 2026-11-14, on the one design review of the frame's sixth pass (another maker, REJECTED with four findings, all adopted) and on the lead's own measurements on the real public boundaries |
| Supersedes | Once confirmed, the clause "H3 resolution 9 in Greater Doha and 8 elsewhere" of [decision 0006](0006-fixed-grid-and-pin-based-areas.md) item 1. Its clause "One fixed grid carries all custodian-type statistics" stands. Items 2 to 5 of decision 0006 are unchanged by this record; items 3 and 4 stand as [decision 0016](0016-version-1-covers-the-whole-initiative.md) item 17 amended them. |
| Amends | Once confirmed, [decision 0016](0016-version-1-covers-the-whole-initiative.md) item 6 in part: a point without a base cell gets no Simulated figure (item 10). Documents 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12 and 15, the glossary, TASKS.md (task S2-T02) and docs/README.md, in the passages listed under "Amended passages". |
| Purpose | Record which H3 cells form the fixed grid, which cell owns a point, how a cell is drawn, what happens where a zone has no district or an administrative point has no cell, and what a pin without a cell gets. The first run on the real boundaries forced each of these corrections. |
| Read first | [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md) section 1.1, section 7.3 (`grid_cell`, `gazetteer`), section 9.2 and DAT-90; [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md) section 5 and PUB-29; [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](../06_PRIVACY_AND_DISCLOSURE_CONTROL.md) sections 4.1, 4.2 and 4.5 (PRV-10, PRV-11, PRV-17, PRV-18, PRV-20, PRV-22, PRV-122), PRV-111 and PRV-124; [08_BACKEND.md](../08_BACKEND.md) `make_area`, BE-55, BE-84 and BE-130; [decision 0016](0016-version-1-covers-the-whole-initiative.md) item 6; [decision 0026](0026-public-sources-used-in-full-locally.md) item 10 |

## Context

- Decision 0006 item 1 says: "One fixed grid carries all custodian-type statistics: H3 resolution 9 in Greater Doha and 8 elsewhere." The pack repeats this as a rule on a cell's own position. It does not say which cells are stored where the two resolutions meet, which cell owns a point there, or how a resolution-8 cell is drawn.
- Greater Doha is five whole municipalities in version 1. This is the lead's assumption OI-151, kept in the frame's review file ([decision 0026](0026-public-sources-used-in-full-locally.md) item 10). This record does not change it.
- H3 children nest exactly in the index and only roughly on the ground (PRV-10). A resolution-8 hexagon is not the union of its seven resolution-9 children.
- Two words need care. Document 06 section 4.1 says: "The rows of `grid_cell` are the frame." The probe, the ruling and the build use "the frame" for the land of the eight municipalities. In this record, **the frame** is the rows of `grid_cell`, as document 06 defines it, and **the mapped land area** is the union of the eight municipality polygons. Where a measurement or ruling L-255 is quoted, its "in the frame" means "in the mapped land area".
- Task S2-T02 built the frame from the licensed boundary archive. The design review of its sixth pass found four defects:
  - F1: excluding stored ancestors makes the cells disjoint in the index, but not on the ground. A lookup of a point's own cell at both resolutions can disagree with the index.
  - F2: two new nulls had no defined readers.
  - F3: the pack kept contradictory sentences ("8 elsewhere").
  - F4: the Greater Doha set rested on an assumption, and a material change needs a decision record (rule 46).
- The lead's sixth probe, on the real boundaries and under the selection of item 1, measured the following:
  - The grid holds 71,867 cells: 63,163 of resolution 9 (598 of them outside Greater Doha) and 8,704 of resolution 8 (none in Greater Doha).
  - There are 9,229 split parents. For 204 of them, the parent's own centre is outside the mapped land area.
  - Each resolution-9 place has at most one owner: the stored resolution-9 cells and the children of the stored resolution-8 cells are 124,091 places, all distinct.
  - The native hexagons of the stored resolution-8 cells overlap the stored resolution-9 cells of their split neighbours in 442 pairs, about 3.2177 km² in all.
  - The probe drew 318,893 random points in the mapped land area. The two-resolution lookup found two cells for 97 of them and no cell for 194 that the index rule owns. For 10,985 points (3.445%) it named a different cell from the index rule.
  - When a resolution-8 cell is drawn as the union of its seven resolution-9 children, the same pairs overlap by nothing (0 pairs). For one resolution-8 cell the area was about 0.6605 km² either way, the symmetric difference between its native hexagon and the union of its children was about 0.0944 km², and the union's outline has 18 vertices.
- The first run on real boundaries also showed two gaps. One zone of the source (zone 99) has no district in either boundary source. Five district points of the gazetteer have no cell under the ownership rule.
- Scope is frozen since 2026-11-12. This record adds no feature. It records a correction that the first run on real boundaries forced.

## Decision

The lead's decision under the owner's delegation, for the owner's confirmation. The first paragraph of items 1, 2 and 3 quotes ruling L-255 part (2) word for word; in those quotes "the frame" means the mapped land area. Each sentence marked "The lead's reading" is the lead's own and is put to the owner for confirmation.

1. **Selection of stored cells.** Ruling L-255 (2)(a): "for every resolution-8 parent that has its own centre or a resolution-9 child's centre in the frame, the parent is split exactly when at least one child's centre lies in a Greater Doha municipality; a split parent is never stored and its children are stored when their own centre lies in the frame; any other parent is stored exactly when its own centre lies in the frame; split parents are found from their children whether or not their own centre is in the frame. Municipality, zone, district and `in_greater_doha` are those of the stored cell's own centre."

   The lead's reading: a cell's centre is the centre that H3 gives the cell's own index, never a centroid of its stored outline. For a resolution-8 cell, ruling L-255 part (1) calls it "the centre of its centre child"; the probe found the two different only in the fourteenth decimal place, and the build uses the centre of the cell's own index.
2. **Ownership of a point by index.** Ruling L-255 (2)(b): "the base cell of a point is the stored cell that is the point's resolution-9 cell or that cell's resolution-8 parent; by (a) at most one exists; a point with none has NO base cell and none is substituted."

   The lead's reading: "none is substituted" means not a nearest cell, not a neighbour and not a cell found by a second lookup. A point of the mapped land area with no base cell lies in no frame cell. It is not outside the mapped land area, so it is not `OUTSIDE_FRAME` (document 06 section 13); item 10 says what it gets.
3. **Shape of a cell.** Ruling L-255 (2)(c): "the geometry of a resolution-9 base cell is its hexagon; of a resolution-8 base cell, the union of the hexagons of its seven resolution-9 children, traced from the indexes (PRV-10's principle, 'never the outline of a parent hexagon', applied to the base cell). Then ownership and shape agree, no two cells overlap and no gap lies between cells of different resolution."

   The lead's reading: the shape enters three things and no protected value. They are the polygon stored with a unit (PRV-10), the requested and released areas of the snap report and the receipt (PRV-22), and the area weight of card C18 for Simulated counts (PRV-122). Unit membership is by index (PRV-10, `unit_member`), the cells an area selects are found by cell centre (PRV-17), and the half rule counts cells (PRV-18). None of these changes with the shape, and no released count changes.
4. **What the build proves.** Ruling L-255 (2)(c): "The build proves: no stored ancestor; no resolution-9 atom with two owners; on fixtures no positive-area overlap and every sampled point inside a cell's shape is owned by that cell; each with its plant (the native lookup; the native hexagon)." The frame build refuses a grid unless all four hold. The plants are a stored split parent, a duplicate owner, a resolution-8 cell drawn as its native hexagon, and the native lookup of a point's own cell at both resolutions.
5. **A cell's resolution is read from the cell.** Nothing may derive a cell's resolution from `in_greater_doha` or from the cell's municipality (ruling L-255 part (9)). A reader takes `grid_cell.resolution`. A resolution-9 cell outside Greater Doha is normal: the real run stores 598 of them, the children of split parents with their own centre outside Greater Doha.

   What this means for disclosure (the lead's reading): in municipalities outside Greater Doha, the finest unit a partition can publish is resolution 9 for these 598 cells, where decision 0006 item 1 allowed resolution 8. A root there can hold cells of both resolutions. These cells exist because index disjointness needs every stored child of a split parent, not to show finer detail. Each passes the same tests of document 06 or pools with its siblings (section 4.2). No threshold, tier, attack size or tolerance changes, so no privacy rule is tuned to make an area look finer (rule 12 of AGENTS.md). PRV-18's half rule counts cells, whatever their resolution, so in a mixed root a resolution-9 cell weighs as much as a resolution-8 cell.

   A catchment or a drawn polygon selects the base cells whose centres lie inside it, each at its stored resolution (PRV-17's first sentence). BE-84 is brought to those words, and its containment rule is confirmed again on a fixture with both resolutions.
6. **District coverage and the district-free zone.** Municipalities and zones each cover the mapped land area exactly. Districts are valid, do not overlap, and each lies wholly inside one zone with consistent keys. Each zone is either covered exactly by its districts, or has no district and is listed in the reviewed file `zones_without_districts.csv` with its reason. Today the file lists one zone, zone 99, with reason `no_district_in_boundary_source`. The build refuses each of the following:
   - a partly covered zone;
   - a district-free zone that is not listed;
   - a listed zone that has a district;
   - a zone that holds no cell centre.

   A district without a cell centre is kept in `district` and counted in the build report with reason `no_cell_centre`.
7. **`grid_cell.district_key` may be null, in one case only.** It is null only for a cell whose centre lies in a reviewed district-free zone (reason `zone_without_district`). The build report counts these nulls. DAT-07 is met without a new column: its test admits "a null with its reason or in a named count", the build report is that named count, and a row's reason is `zone_without_district` exactly when its `zone_code` is listed in `zones_without_districts.csv`.
8. **`gazetteer.cell` may be null, in one case only.** It is null only for the kinds `municipality`, `zone` and `district`, and only when the unchanged point has no base cell under item 2 (reason `point_without_base_cell`). The build report counts these nulls by kind. A row of any other kind without a base cell refuses the build. The row's point is never moved to find a cell. DAT-07 is met as in item 7: a null `cell` always has the reason `point_without_base_cell`, and the build report counts it.
9. **Readers of the nulls and of a district without a cell.**
   - A reader of `grid_cell.district_key` that finds null gives no district context for that cell.
   - A reader of `gazetteer.cell` that finds null gives no cell anchor for that row. The row still resolves as a name (`resolve`), and its own point still finds its official geographies (PUB-29). A gazetteer row with a null `cell` used as a pin is a pin without a base cell (item 10).
   - Neither reader may substitute a neighbouring cell or district. A pin's own district comes from the pin itself (PUB-29). The district key of the pin's cell describes the cell's centre only.
   - A district without a cell centre selects no frame cell. A protected or Simulated figure asked for it meets the existing rule for an empty selection (PRV-20). No cell whose centre lies in another district stands for it, and nothing is apportioned to it (PRV-122). Its Public figures stay on the district (PUB-29).
   - A figure that needs a district, for a pin in a reviewed district-free zone, returns `NO_DATA` with the reason key `zone_without_district`. The zone and municipality figures stay usable.
10. **A pin without a base cell.** A pin is a point that the user or a place gives. Ruling L-255 part (5): "such a pin gets Public context on the pin itself (PUB-29) and NO protected or simulated figure (`NO_DATA` with the coverage reason)". The pack carries this in a new requirement, PRV-135, directly under PRV-17:
    - **Nothing protected or Simulated.** An area built from such a point selects no frame cell for protected figures. The point is not replaced under PRV-17. No nearest or neighbouring cell stands for it, and the area record has no `protected` entry, so no protected table can be read through it (DAT-146). Every protected and Simulated slot returns `NO_DATA` with the reason key `point_without_base_cell`, never `SUPPRESSED` (PRV-20 amended). This reason key belongs to DAT-90, not to the suppression codes of document 06 section 13. It depends only on the request and the frame, so PRV-84 and PRV-91 hold.
    - **No snap.** PRV-18, PRV-20 and PRV-22 are not reached: no snap is made and no snap report is written. No protected or simulated table is read, so no privacy receipt is written (PRV-87). No municipality unit of PRV-16 is chosen from such a point. A municipality or the national unit opened by its own key is not a figure of the point.
    - **No outline from Simulated speeds.** A `drive` with a `situation`, an `hour_key` or a `day_key` returns `NO_DATA` with that reason, makes no area and reads no `traffic_hourly` row. The traffic provider adapter is never called for such a pin (`make_area` provider mode, BE-130, PRV-124).
    - **Every tool that takes a point.** The rule binds every such tool, not only `make_area`:
      - the catchments of `workers_within_reach` (PRV-127), where both figures and the ratio return `NO_DATA` with that reason;
      - the release unit of a site under PRV-126 and card C33;
      - the candidate depot of card C29;
      - a gazetteer key whose `cell` is null (item 9);
      - the representative point that a tool uses as the origin of a drawn shape's catchment or travel time. The drawn shape itself is not built from a point and snaps as drawn (PRV-17).
    - **Reading.** PRV-135 restricts every statement of the pack that gives an area, a catchment or a point a protected or Simulated figure, a snap, a unit list or an outline by hour of day: a statement that does not repeat it is read with it. The pack names the exception where a requirement states the general area rule in its own words and in the contracts of the tools that the rule names (the amended passages below). A passage that restates the rule for one screen, one card or one test, for example "each catchment snaps like every area", is bound through the requirement it cites and is not amended one by one.
    - **Public context.** Its official geographies are found on the pin itself (PUB-29). The lead's own addition, beyond the ruling's words and for the owner's confirmation: such a pin also gets the Public layers of the exact `distance`, `walk` or free-flow `drive` outline (DAT-153: a free-flow time is Public). This is Public data only. It is the one place where its exact point is the origin of an outline. It is needed because the Public context block is asked through an area (`area_evidence` takes an `area_id`). Ruling L-255 itself says only "Public context on the pin itself (PUB-29)". The question, its default (kept) and its stricter alternative are under "Open questions and assumptions".
    - **The record of such an area.** Its `anchor_cell` is null, its `area_id` carries the literal `none` in place of the pin cell, and it has no `protected` entry and no unit list for any partition. In public-only mode it has no cell set and no snap report either.
    - **Tests.** PRV-111 (g) and TST-21 assert, on a fixture point without a base cell and for every mode and cut-off, that `make_area` returns no `protected` entry and no unit list and that no protected or Simulated row is read through its `area_id`. TST-204 carries the planted violations. Each of these fails: a protected or Simulated figure for such a pin, a substituted cell, an hour-of-day outline built for it, a provider area registered for it, and its exact point used as the origin of a protected or Simulated figure.

    PRV-17's three sentences keep their words. PRV-135 only restricts them, and it keeps the stricter reading of ruling L-255. The lead did not take the design review's proposed sentence that such a point "retains its exact point" as the origin of an area. That sentence would open what PRV-17 closes (rule 12 of AGENTS.md). This item amends decision 0016 item 6 in part: "Simulated layers are computed for that exact shape" no longer holds for an area built from a point without a base cell.
11. **A Public supply point without a base cell.** The lead's default, put to the owner for confirmation. Every supply point of a Simulated access layer resolves to exactly one `px_base` unit through its base cell. A supply point without a base cell contributes nothing to the layer: no cell is substituted for it (item 2). It is never moved to another cell, and it is never left out without a word: it is listed and counted, and the Simulated access layer carries a limitation line with the count of supply points left out for that reason (DAT-151). The stricter alternative, from the design review's F2, makes the whole layer unavailable with the reason key `point_without_base_cell` when any supply point has no base cell; it is named beside the default under "Open questions and assumptions".
12. **The measured limits, stated as limits.** The centre rule is the pack's own (PRV-17) and is unchanged. On the real boundaries it leaves the limits below. The figures of the first two bullets, and the parents of the five district points in the last, come from the lead's sixth probe (project records held by the owner), at commit 9a419f9 before the fix, under the same selection. The null district keys and the gazetteer's null cells are printed by the lead's real run at the committed head 49d131b (project records held by the owner). The count of districts without a cell centre is printed only by the build report of the lead's run of the sixth pass (project records held by the owner; its record names no commit).
    - **Land without a cell.** 460 resolution-9 places have their centre in the mapped land area but lie under a resolution-8 parent whose own centre is outside it, so they have no owner. That is about 48.45 km². They are in three municipalities outside Greater Doha that reach the coast or the border: 185, 147 and 128 places. Edge pieces of places whose centre lies outside the mapped land area also have no cell, in Greater Doha too: one of the five district points without a cell lies in a Greater Doha municipality. Of the probe's 318,893 random points in the mapped land area, two groups had no base cell: 1,640 (0.514%) and 112 (0.035%). The probe does not label the groups.
    - **Owned places centred outside the mapped land area.** 473 owned resolution-9 places have their centre outside the mapped land area, at sea or beyond the border. As whole places that is about 49.82 km². A stored cell's shape can reach outside the mapped land area.
    - **The district-free zone.** Zone 99 of the source has no district in either boundary source (ruling L-255 part (3)). The real run prints five `grid_cell` rows with a null `district_key`, all of zone 99: five cells have their centre there.
    - **Districts without a cell centre.** 2 of the 781 districts hold no cell centre (the build report of the run of the sixth pass prints `district: 2 no_cell_centre`; the file of the run at the committed head prints no build-report line). They stay in `district` and are reported (`no_cell_centre`).
    - **Administrative points without a cell.** 5 of the 781 district points of the gazetteer have no base cell. Every municipality point and every zone point has one. Each of the five lies under an unsplit resolution-8 parent whose own centre is outside the mapped land area. None is an artefact of the edge between the two resolutions.

    The areas are the probe's estimates: the number of places times the average resolution-9 area of 0.10533 km². They are not exact intersections of land and sea. The frame is not an exact cover of the land. No contributor is placed on land without a cell (PRV-11), and a blank for a point there says only that the frame has no cell at that point (document 06 section 17, amended).
13. **The acceptance criterion of task S2-T02.** "District keys are present" becomes, in these words: "district rows and their keys are kept, and the grid's district keys meet document 03 section 7.3, including its one reviewed null exception: a cell whose centre lies in a zone listed in `zones_without_districts.csv` has a null `district_key`, counted with reason `zone_without_district`."
14. **Unchanged.** Decision 0006 items 2 to 5 stay as decision 0016 item 17 left them. The words of PRV-10, PRV-17 and PRV-18 are unchanged. PRV-17 gains a restricting row, PRV-135, and PRV-20 gains a closing sentence; both are stricter. Every privacy threshold, tier, attack size and tolerance stays as it is. No Public figure is apportioned to a cell. Greater Doha's five municipalities stay the assumption OI-151 of decision 0026 item 10.

## Evidence

- **The lead's sixth probe** (project records held by the owner), 2026-11-14, on the real public cache, at commit 9a419f9 of the frame's fifth pass. It was read-only and used h3 4.5.0 and shapely 2.2.0. It reports:
  - the counts of the Context and of the first two bullets of item 12;
  - 460 places without an owner, all for the reason "parent unsplit, parent centre outside frame";
  - 473 owned places with their centre outside the mapped land area;
  - 442 overlapping pairs with native resolution-8 hexagons, and 0 pairs with the union of children.
- **The lead's real run at the committed head** 49d131b2e6c48d96f6eb3e2f1572fd3a8ae98d73 of task S2-T02 (worktree clean), on the real public cache, 2026-11-14 17:46:47, with the lead's own checks (project records held by the owner; build 92 seconds, run exit 0). Its 300,000 ownership sample points are drawn by the run's script from Python's `random.Random(2026111460)`, each longitude and latitude uniform over the bounding box of the union of all stored cell shapes. Its check lines, as printed:
  - `TABLE district 781`; `TABLE gazetteer 880`; `TABLE grid_cell 71867`; `TABLE municipality 8`; `TABLE pub_census_district 778`; `TABLE pub_census_national 2`; `TABLE pub_census_zone 175`; `TABLE pub_population_municipality 48`; `TABLE zone 91`
  - `CHECK resolutions {8: 8704, 9: 63163}`; `CHECK res9 outside Greater Doha 598`; `CHECK res8 inside Greater Doha 0`
  - `CHECK null district_key 5 by zone {'99': 5}`
  - `CHECK geometry types {'Polygon': 71867} invalid 0`; `CHECK vertices of res8 shapes {18: 8704}`
  - `CHECK overlapping pairs with positive area 0 worst_area_deg2 0.000e+00 candidate_pairs 213657 seconds 2`
  - `CHECK sum_area 1.043316697252 union_area 1.043316697252 relative_difference 1.064e-15 seconds 2`
  - `CHECK ownership sample n 300000 agree 162613 none_both 137387 geometry_only 0 index_only 0 differ 0 points_in_two_shapes 0`
  - `CHECK centres not owned by their own cell 0`
  - `CHECK gazetteer kinds {'municipality': 8, 'zone': 91, 'district': 781} null cell by kind {'district': 5}`
  - `CHECK gazetteer rows whose cell is not the owner of the stored point 0`; `CHECK gazetteer coordinates with more than six decimals 0`
  - `CHECK7 gazetteer max decimals lon 6 lat 6 rows 880`; `CHECK7 gazetteer rows whose stored point is not owned by their stored cell 0`
  - `CHECK7 PUB-73: the 2020 national establishment total of the build ['71203'] against the published 71203 of PUB-73: EQUAL`
  - The gazetteer's coordinates: the frame's seventh pass stores them at six decimals, rounded half to even, and a point's cell is found from the stored point (ruling L-265 part (1)). The lines above show at most six decimals on all 880 rows and every stored point owned by its stored cell.
- **The lead's run of the sixth pass** (project records held by the owner; its record names no commit): the source of the one count of item 12 that the run at the committed head does not print, its build-report line `district: 2 no_cell_centre`. Its report also marked the frame as partial: place points remain for S2-T06.
- **The design review of the sixth pass**: findings F1 to F4 and the pack sentences it proposed. They are the starting text of the amendments, except the sentence on an exact pin.
- **Two adversarial readings of the first draft of this record**, 2026-11-14: one for privacy and disclosure, against PRV-17, PRV-18, PRV-20, PRV-111, PRV-122 and PRV-124, and one for figures, anchors and pack coverage. Their findings are taken into this text (project records held by the owner).

## Consequences

- Every sentence of the pack is amended that states the old rule, a native hexagon for a resolution-8 cell, a district key on every cell, a cell on every gazetteer row, or a base cell for every pin (Amended passages).
- In municipalities outside Greater Doha, 598 resolution-9 cells can now be published as `cell` units when they pass, and roots there can mix resolutions (item 5). No disclosure rule changes.
- This record and its amendments merge before or with the pull request of task S2-T02 (ruling L-255 part (8)).
- Task S2-T02 builds the rule of items 1 to 4, the coverage rule of item 6 and the nulls of items 7 and 8, each with its plant. The limits of item 12 go into the task's open items.
- Other tasks:
  - The point-to-cell rule of the backend's `grid` and `shapes` modules is item 2.
  - S4-T04's simulator is checked at its verification for any resolution derived from `in_greater_doha` or a municipality (item 5).
  - S4-T01's registry rows of `grid_cell` and `gazetteer` follow this record.
  - The slice S3 tasks that show areas carry item 10's `NO_DATA` reason key and its template.
- Every map layer keyed by cell draws a resolution-8 cell as its seven resolution-9 children, never as its own hexagon (document 10).
- A change to the Greater Doha set (OI-151) changes which parents are split. That needs a new build of the frame, and after a freeze a new world seed (rule 12 of AGENTS.md).

## Amended passages

Listed below by document and stable anchor: the whole change of this record's pull request against its parent, outside this record's own file, PROGRESS.md and OPEN_ITEMS.md. Decisions 0006 and 0016 are not edited. The decision index in docs/README.md records that decision 0006 item 1 is superseded in part and decision 0016 item 6 amended in part.

### docs/README.md

- Decision records table, row 0006
- Decision records table, row 0016, end of its status cell
- Decision records table: new row after the last row (0027)
- In brief, the bullet beginning "Decision records 0001"
- header table, row "Status": end of its cell
- Documents table, the status cell of each amended document's row

### docs/01_PROJECT_BRIEF.md

- BRF-58, second sentence
- BRF-04, the sentence that cites BRF-58
- section "The five record types and income geography", the bullet **Area**, at its end
- BRF-73, after its first sentence
- header table, row "Status"

### docs/02_ARCHITECTURE.md

- 1.1 What the system is, row "Grid and release unit", first sentence
- 4.1 Folder structure, the paragraph that begins "`grid_cell` carries the zone"
- header table, row "Status"
- ARC-90, after its second sentence
- ARC-89, after the sentence on a drive area for an hour of day
- ARC-89, the sentence on the provider switch
- ARC-135, after the sentence on the ledger record of a traffic-aware area

### docs/03_DATA_CONTRACTS.md

- 1.1 Terms, **Base cell**
- DAT-51, requirement column
- 7.3 Columns, row `grid_cell`, field `resolution`
- 7.3 Columns, row `grid_cell`, field `in_greater_doha`
- 7.3 Columns, row `grid_cell`, field `geometry`
- 7.3 Columns, row `grid_cell`, field `district_key`
- 7.3 Columns, row `gazetteer`, field `cell`
- 9.2 The area record, field `anchor_cell`
- DAT-151 (`access_score`), the clause on supply points
- 9.2 The area record, field `protected`
- DAT-146, requirement column
- DAT-146, test column: at its end
- DAT-90, requirement column, the list of reason keys
- DAT-146, requirement column (validity of a drawn polygon)
- DAT-146, test column
- 9.2 The area record, opening paragraph, the last sentence but one
- 7.3 Columns, row `pub_census_zone`
- header table, row "Status"

### docs/04_PUBLIC_DATA_PACK.md

- 5. The frame: geographies, gazetteer and crosswalks, level table, row "Grid cell", column "Count (research, 2026-11-11)"
- 5., new paragraph directly after the paragraph that begins "Greater Doha means" (after the level table), before the requirement table
- PUB-29, first sentence
- PUB-30
- PUB-100, first sentence
- PUB-81: at its end
- header table, row "Status"

### docs/05_SYNTHETIC_WORLD_AND_SIMULATION.md

- 4. The frame, SYN-10, first sentence
- header table, row "Status"

### docs/06_PRIVACY_AND_DISCLOSURE_CONTROL.md

- 4.1 Frame, units and partitions, **Base cell**, first two sentences
- 4.2 The algorithm, paragraph after the code block, last two sentences
- 4.3 Worked examples (all counts invented), Root R2, child H
- 4.3, Root R2, child K
- 4.5 The snap rule, introductory paragraph, last sentence
- 4.5 The snap rule, requirement table: new row PRV-135 directly under PRV-17
- PRV-20, last sentence
- PRV-122, first sentence
- PRV-124, after the sentence on the traffic-aware drive-time area
- PRV-111, item (g): after its last clause
- 17. Limits and non-claims, new bullet after the bullet "**Drawn shapes.**"
- header table, row "Status"

### docs/07_ECONOMIC_METHODS.md

- C29 Sums over a case sample file, case C3 access, depots
- 7. Where the units are too few, row "Grid cell", column "Units"
- C40, the uncertain inputs, the sentence on rent
- C12 Reachable-access score, Inputs, travel times, the containing-unit sentence
- C12, new paragraph directly before "**Formula.**"
- C12, Limits and wording, second sentence
- C12, MTH-66, opening clause
- header table, row "Status"
- MTH-56, after its second sentence

### docs/08_BACKEND.md

- 2.1 `eii_core` (shared library), module `grid`
- 6.2 Tool contracts, `resolve`, Outputs: after its last sentence
- 6.2, `make_area`, Statuses, first clause
- 6.2, `make_area`, row "Public-only mode"
- BE-105, the same clause
- 6.2, `make_area`, row "Provider mode": before its last sentence
- BE-130: after its first sentence
- BE-55, first sentence
- 6.2, `area_evidence`, Outputs, the clause of decision 0017
- 6.2, `price_measures`, Inputs
- 10. Routing, BE-82, second sentence
- 10. Routing, BE-84, first sentence
- 10. Routing, BE-84, its closing sentence on the H3 containment rule
- 11.1 Area ids, first sentence
- 6.2, `workers_within_reach`, Statuses
- 15. Tests each module ships with, row `eii_core.shapes`, the point-in-shape clause
- 2.1, module `shapes`, its validity checks
- 6.1 Common contract, the sentence before the envelope
- 6.2, `resolve`, Statuses
- 6.2, `make_area`, Outputs, the snap report clause
- 6.2, `area_evidence`, Outputs, the receipt sentence
- 6.2, `present_by_pay_band`, Outputs
- 6.2, `present_by_pay_band`, Statuses
- 6.2, `workers_within_reach`, Outputs, the snap report sentence
- 8.3 Drawn shapes and case sample files, BE-117
- 8.1 Endpoints, row `POST /api/areas/shapes`, response column
- 15., row `eii_core.shapes`, the refusal clause
- header table, row "Status"
- 6.2 Tool contracts, `travel_times`, row Statuses
- 6.2 Tool contracts, `compare_areas`, row Statuses
- 6.2 Tool contracts, `own_records`, row Outputs

### docs/09_AI_ASSISTANT.md

- 3. Playbooks, bundle table, rows `site_check` and `staffing_and_pay`
- 7. Refusal and caveat templates, row `NO_DATA`, display cell
- 7., AI-52
- header table, row "Status"
- AI-103, the clause on the exact shape

### docs/10_FRONTEND.md

- 6. Map layers, row "Released units", drawing column
- 6. Map layers, row "Night-time lights", drawing column
- Open questions and assumptions, item 14
- 6. Map layers, one sentence directly after the layer table, before "**Provenance textures.**"
- 6. Map layers, FE-55
- 6. Map layers, paragraph "**Camera.**", last sentence
- header table, row "Status"

### docs/11_DESIGN_DIRECTION.md

- 8. The map, DES-60
- header table, row "Status"
- DES-99, after its first sentence

### docs/12_TESTING_AND_QUALITY.md

- 3.2 Property tests for the privacy invariants, TST-204, after its last sentence
- 3.2, TST-21, at the end of its requirement column
- header table, row "Status"

### docs/15_REVIEWER_CHECKLIST.md

- REV-22, after the sentence on what snaps
- header table, row "Status"

### docs/GLOSSARY.md

- B, **Base cell**
- D, **Door**, second sentence
- header table, row "Status"
- A, **Area**, at its end
- D, **Drawn area (geofence)**, after its second sentence

### TASKS.md

- S2-T02 Frame and gazetteer, Acceptance criteria, second criterion

## What would change this decision

- The owner's answer to OI-151: a different Greater Doha set changes the selection, but not the rule.
- An approved rule that covers the land exactly, for example a coastal cut of cell shapes. That would need its own record and its own privacy reading, because PRV-17 and PRV-10 select and draw by whole cells.
- A boundary source that gives zone 99 districts. The reviewed file then loses its row, and the build refuses until it does.
- A version of H3 whose indexes or centres differ. The proofs of item 4 are then run again.

## What is not decided

- The Greater Doha set itself (OI-151, decision 0026 item 10).
- The wording that a screen shows for `point_without_base_cell` and `zone_without_district`. Those templates belong to the slice S3 tasks that show them.
- How a register company's registered location, a case sample file's depot or a synthetic record is placed when its point has no base cell. PRV-11 is unchanged: a contributor whose cell is not a row of `grid_cell` fails the build. Until a record decides this, no generator moves a contributor into a neighbouring cell (item 2). It is an open item, entered by the lead at the frame's ledger ("Open questions and assumptions").
- The names file keyed by the frame's own codes, with its new check of bilingual agreement, and the proposed review files written only to the output folder (ruling L-255 parts (6) and (7)). They change no sentence of the pack.

## Open questions and assumptions

- OI-151 (Greater Doha's five municipalities) stays the lead's assumption.
- ASSUMPTION: the areas of item 12 are estimates from the average cell area, not measured intersections.
- OPEN (an open item, entered by the lead at the frame's ledger): how a register company's registered location, a case depot or a synthetic record whose point has no base cell is placed. Until the first task that places such a location decides it in its own record, three things hold. PRV-11 fails the build for a contributor. DAT-164's null `registered_cell` puts a register company in no area. The build report counts such locations first, so the size of the case is known before a rule is chosen. The lead's default owner for the register companies' locations is task S4-T02.
- PROPOSED OPEN ITEM (the advice of this record's design review): when the generator of SYN-32 and its fidelity check F15 is built, its fixtures include a cell with a null `district_key` (a reviewed district-free zone); a missing district price is never substituted, and no fidelity tolerance is relaxed for it.
- FOR THE OWNER (default: kept): the Public layers of the exact `distance`, `walk` or free-flow `drive` outline for a pin without a base cell (item 10; PUB-29 in document 04 and the statuses of `make_area` in document 08). This is the lead's own addition: ruling L-255 itself says only "Public context on the pin itself (PUB-29)". It is kept because Public layers are Public facts and carry no protected figure, while the stricter alternative would leave such a pin with no Public context of its surroundings. The stricter alternative: `make_area` returns `NO_DATA` with reason `point_without_base_cell` and makes no area record, so the pin keeps only the official geographies found on the pin itself; the pack has no other carrier for its Public context today (`area_evidence` takes an `area_id`).
- FOR THE OWNER (default: left out, listed and counted): a Public supply point of a Simulated access layer that has no base cell (item 11; DAT-151 in document 03). By default it contributes nothing (no cell is substituted for it, item 2), it is listed and counted, and the layer carries a limitation line with the count of supply points left out for that reason. The stricter alternative, the design review's proposal under F2 and an earlier draft's default, makes the whole layer unavailable with reason `point_without_base_cell` when any supply point has no base cell; its cost is that one supply point on land without a cell removes the access layer for every area.

## Sources

- Ruling L-255 of the lead, 2026-11-14 (project records held by the owner).
- The design review of the frame's sixth pass, 2026-11-14 (project records held by the owner).
- The lead's sixth probe, the lead's run of the sixth pass and the lead's real run at the committed head 49d131b, 2026-11-14 (project records held by the owner).
- H3 documentation, as decision 0006 cites it; the h3-py API reference and the Shapely 2.2.0 manual, read by the build on 2026-11-14.
