# Glossary

| | |
|---|---|
| Status | Draft v0.3, amended by decisions 0016 and 0017 on 2026-11-12 |
| Date | 2026-11-12 |
| Owner | albarami |
| Purpose | Define the shared vocabulary of the EII proof of concept without changing its binding decisions. |
| Read first | [README.md](../README.md), [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md) |

## In brief

- Provenance and evidence status are different axes; tool status is a third concept.
- “Observed” never means “real” when a fact is Synthetic or Simulated.
- “Not measured” is a coverage label, never zero and not an evidence status.
- A release contains statistics and Public records, plus the restricted named synthetic firm list ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 12; ARC-131); every other record-level synthetic input stays in the build vault.
- The application calculates and renders. Models select catalogue entries; they do not write prose, queries or numbers.
- Only figures from the four protected record types snap to release units; the Public and Simulated layers of a drawn area are computed for its exact shape ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)).
- Synthetic and protected records carry no sex, gender or nationality; an official split by sex or nationality is a Public fact only ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)).
- Terms are requirements for the planned product, not claims that it exists.

## A

- **Accounting gate**: The deterministic audit before display, labelled on the receipt as "Checked before display". It runs five checks—Sources, Assumptions, Nothing invented, Scope, Limits stated—on the complete structured brief; failure selects the template writer and is logged.
- **Activity spine**: The reviewed mapping among commerce activity code, ISIC Rev.4 class and public place category, with unmapped and not-mappable cases visible.
- **Additive family**: One release table, one partition, one measure where the table has measures, and one breakdown. Inside it the leaves are mutually exclusive and treated once, and every stored total is the exact sum of that family's own leaves. Equality is not required between families (PRV-29, PRV-71).
- **Apportioning**: Post-processing in the product plane that spreads a released value over a drawn shape by a fixed weight: a released Simulated presence count at release-unit grain, or a Public statistic published on an official geography. A Public statistic apportioned to a shape is labelled Inferred and names its method and its geography. Figures from the protected record types are never apportioned (they snap), and no Public split by sex or nationality is apportioned to a drawn area. The weight is fixed in document 07 (decision 0016).
- **Area**: The geography of an answer, built from a pin, a drawn shape, a radius or a walk or drive time. Figures from the four protected record types (business register, employment, residence, wages) are read only after the area is snapped to whole release units; Public and Simulated layers are computed for the exact shape (decision 0016).
- **Artefact**: A non-table file listed and hashed in a release manifest, such as a routing graph or signed build report.
- **ASSUMPTION**: A labelled default chosen where no binding decision exists. It is not evidence and needs the named decision or test stated with it.
- **Atom**: A leaf atom or one of its derived totals inside one additive family. An `other` row is a treated leaf where pooling occurred, not a derived total. The atom's population is the set of contributors it counts.
- **Attack suite**: Typed recovery predicates (PRV-116) that must succeed with controls off and fail with controls on. Both parameter sets are evaluated inside the custodian plane; exactly one protected table set is exported.
- **Attacker-view audit**: The one release-gating acceptance model (PRV-112 to PRV-116, PRV-121). Every published leaf is fixed to its untreated aggregate. Signed knowledge fixtures are checked against sealed truth before use, and a published leaf is constrained as having passed its rules. Targets the model cannot tell apart form one target class and are audited once. A time budget is set from a measured run at the start of slice S5. What the layout tells about a population that failed a rule is not in the model. The audit is evidence under a stated attacker, never a proof. Its configuration is `artefacts/attacker_view_audit.json`; public totals are `artefacts/attacker_view_public_totals.json`.

## B

- **Base cell**: A cell of the fixed H3 frame at resolution 9 in Greater Doha and resolution 8 elsewhere.
- **Best-location ranking**: Candidate areas for an activity ranked by tested code in `eii_core.calc`, with every criterion, its weight and its value visible, weights the user can change, a rank-stability sentence beside every rank and a public-only mode (method card C11). It is never a verdict, a probability, a confidence claim, a forecast or advice to act (AGENTS.md rule 25).
- **Brief**: The answer column and its structured selection of claims, caveats, next questions, layout and stage directives.
- **Build machine**: The computer that runs public fetching, synthetic generation, privacy treatment, release building and verification.

## C

- **Calculation layer**: Deterministic tested code in `eii_core.calc`, the release build, or a fixed application-schema read function listed by the data contracts and covered by tests. Every displayed number and comparison comes from one of those three places; nothing else computes, rounds or compares a number, and no model ever does.
- **Calculated import unit value**: The deterministic Public customs ratio of import value to net mass, expressed in QAR per kg. The valuation basis appears as the source states it or as “not stated by the source”; display baskets are defined at eight digits or finer. It is not a landed cost.
- **Calibration manifest**: The generator's complete parameter register. Each parameter is ANCHORED to cited public evidence or ASSUMED with a range and sensitivity sweep.
- **Canary**: A planted synthetic marker or truth used to prove that attacks and leak scans have teeth. It must be recoverable with controls off and unrecoverable with controls on.
- **Case**: One of four illustrative company situations, each a guided story with a one-click start: case C1, an industrial services firm testing local demand; case C2, a technology supplier choosing whom to approach first; case C3, a distributor weighing a second depot; case C4, a retail chain with a weak branch. Cases C3 and C4 load a sample file marked Synthetic that stands for the company's own records and stays inside the session and seat that loaded it. Not to be confused with the method cards C1 to C29 of document 07 (decision 0016).
- **Catalogue version**: The combined hash of the claim, component, fragment and question catalogues, stored in every brief and included in its memo key.
- **Claim catalogue**: The versioned application data that defines permitted Observed and Inferred claims, subjects, fact slots, caveats, strengths and bilingual templates.
- **Component catalogue**: The closed, versioned set of evidence cards and interface components with typed schemas. Components accept fact ids, release unit ids and enumerations, never free numbers, code, HTML, styles or URLs.
- **Conformance suite**: Contract tests that every synthetic or future real adapter must pass unchanged before a feed or release is accepted.
- **Contributor**: The person, job or establishment population behind an atom, defined on a residence, workplace or register basis.
- **Covered earner**: A person in an eligible covered private-sector job. People outside that coverage are not measured, not zero.
- **Coverage**: A declaration of what a feed or figure includes and excludes. Missing coverage is shown explicitly and never converted to zero.
- **Crowd density**: Estimated people present per square kilometre, drawn on the map by hour of day. It is Simulated and computed by tested code from released counts (decision 0016).
- **Custodian**: The body that holds a record type under its own mandate. The pack uses neutral record-type names and does not imply supply or endorsement.
- **Custodian plane**: The offline build environment and the only place record-level synthetic data may exist. Only a release leaves it.

## D

- **Decision class**: One of five closed offline gateway jobs: `spine_match`, `router_miss_finder`, `brief_second_reader`, `question_route` or `string_parity`.
- **Decision journey**: One of the seven company decisions of decision 0016, journey D1 (whether to enter Qatar) to journey D7 (how to serve the region), each ending with its own answer.
- **Decision record**: A numbered amendment record explaining context, decision, evidence and consequences. In the gateway context, it instead means one JSON audit record under `evals/typed_decisions/runs/`; the two are not the same artefact.
- **Dial**: The control that selects a stored situation and summer setting for estimated people present. It is not a clock and has no intermediate positions.
- **Dial situation**: One of `weekday_lunch`, `weekday_evening`, `friday_evening` or `ramadan_iftar`; summer applies only to the first three.
- **District**: An official public geography below municipality. Public district figures are never blended into protected grid statistics.
- **Dominance**: A disclosure risk when one employer group, the largest two groups, or one person accounts for too much of a unit's earners, establishments or wage bill.
- **Door**: A user's pin at a place, from which an area is made by a radius, a walk time or a drive time. For figures from the four protected record types the pin is first replaced by the centre of its base cell and the area snaps to whole release units; Public and Simulated layers use the exact shape (PRV-17, decision 0016).
- **Drawn area (geofence)**: An area the user draws, sets by a radius, or picks as a walk or drive time from any point, by hour of day. Public point layers and Simulated layers are computed for its exact shape; only figures from the four protected record types snap to whole release units, with the snap sentence (DES-101), before they are read (decision 0016; decision 0006 as amended).
- **DuckDB**: The release build engine and the embedded read-only standby. Parquet remains the source of truth and the embedded file is disposable.

## E

- **Egress record**: The append-only record of an attempted outbound model request, including exact payload bytes and hash, written before response content is used.
- **Employer group**: Establishments rolled up through legal entity to a hidden group used for dominance tests. It never leaves the vault.
- **Estimated people present**: Simulated people present inside an area, hour by hour, for each dial situation, the summer switch and the three event days, shown as an estimated count with a range and split into workers, residents and visitors. It is released only at release-unit grain under the panel minimum, complementary suppression and rounding of document 06, and apportioned to a drawn shape in the product plane. The wording is "estimated people around this location", never "footfall of" a named building or business. It replaces the presence index (decision 0016).
- **Event day**: One of three simulated day types, National Day, a day in Ramadan and a major match at a stadium, each with its own hour-by-hour profile of estimated people present; Simulated (decision 0016).
- **Evidence card**: A governed display of one evidence block with Fact chips, class marks, coverage and required caveats.
- **Evidence drawer**: The one-tap view of a fact's provenance, evidence status, inputs, rules, coverage and source chain.
- **Evidence status**: How an answer uses a fact: exactly Observed, Inferred or Still to test. “Not measured” is a separate coverage label, not an evidence status.
- **Experience plane**: The browser application in `web/`. It renders released facts and cannot calculate statistics or reach the vault.
- **Export register**: The committed append-only file `infra/export_register.jsonl`. The first `./eii freeze` run appends one line with these seven fields in order: `window_key`, `protected_sha256`, `world_seed`, `rules_version_id`, `parameter_set`, `release_id`, `code_version`. Continuous integration checks this file alone: existing lines unchanged, one `protected_sha256` per `window_key`, and one `window_key` per `world_seed`. The second no-flag freeze run builds and verifies the application archive from a base-branch commit containing the line and marks `freeze.json` complete. A frozen bundle can be installed or started only when its descriptor is complete and the register inside the installed application holds its line. No signed receipt file is added (PRV-120).

## F

- **Fact**: The governed object that carries a value, unit, period, geography, provenance, input classes, evidence status, reliability, coverage, caveats, labels, lineage and release.
- **Fact chip**: The only interface component family allowed to render a numeral. It shows the fact's value and marks and opens its Evidence drawer.
- **Fact id**: `f_` plus 32 hexadecimal characters derived from the canonical release id, metric key, geography, period and qualifiers.
- **FDI project**: One announced investment project from the national investment promotion agency's FDI projects dashboard (data from fDi Markets), loaded with every field into `fdi_projects` at every build. Its subject, `fdi_project`, accepts Public slots only. Capex and jobs keep the source's note that they are estimates of publicly announced projects and that the dashboard does not capture every project. It is shown as a published announcement, never as a lookup of a firm, and is never joined to synthetic firm data (decision 0017).
- **Feed**: One delivery of one source contract for one reference period, produced by an adapter and checked by its conformance suite.
- **Feed bundle**: A feed manifest, coverage declaration and declared tables with hashes and row counts. Missing headers, scope or internal period fail acceptance.
- **Fixture (scene)**: A manifest-listed fixture identity accepted by the scene-only endpoint for a prepared “Try to break it” request. The complement step returns two pre-validated unit sets; production tools read a protected figure only after snapping an area to whole release units, and no run-time path holds unprotected data.
- **Fragment catalogue**: The versioned application-owned text fragments from which headline and decision templates may be selected. Model output chooses keys; it never edits the fragments.
- **Fidelity report**: The synthetic-world comparison with public margins and predeclared tolerances. It supports “consistent with published anchors within stated tolerances”, never “validated”.
- **Flow scale**: The positive fixed denominator of the first pack's flow index, `flow_score = 100 × sum(expanded_trips over situation hours) / flow_scale` (PRV-59), identical for A and B and never derived from protected-row sums. Version 1 releases flows as rounded estimates of trips, so it uses no flow scale; the rule applies only to an index that a contract keeps (decision 0016).
- **Fuzz pairs**: Seeded random area pairs used as regression evidence after the exhaustive structural checks, not as the proof of closure; at least 10,000 pairs per release and per parameter set (PRV-49, PRV-51).

## G

- **Geofence**: See **Drawn area (geofence)**.
- **Grid cell**: One fixed H3 cell used for custodian-type statistics. Public statistics remain on official geographies.
- **Guided story**: The presenter journey of [16_DEMO_RUNBOOK.md](16_DEMO_RUNBOOK.md) from Public evidence through simulation, synthetic pay, privacy attacks and hand-over. Each of the four cases is also a guided story with a one-click start (decision 0016).

## H

- **Hold-out**: Public evidence excluded from calibration and used later in the validation scorecard. It reduces circular checking but does not prove the simulated world is real.
- **Home family**: The single additive family a displayed figure is normally computed from, named in that fact's lineage (PRV-30). A count and adjacent non-ratio shares use the same home family. The closed ratio-statistic list is the only exception.
- **Housing class**: The housing-split values `family_housing`, `labour_accommodation`, `institution` and `unknown`, plus an explicit `other` row where pooling occurred. `other` is a treated leaf. The count that is not measured is a separate population, not a housing class.

## I

- **Incentive package**: An incentive offer loaded from the national investment promotion agency's incentive pages into a structured record with its parameters and source page. It enters the break-even calculator only as an optional scenario input tagged "your inputs" and never changes a Public figure (decision 0017).
- **Income geography**: Area-level wage statistics for covered earners by home and workplace, released only as privacy-protected statistics. Decision 0016 names six indicators, each with trends: average and median wage by residential area where groups are large enough; wage bands and their spread; the covered wage bill and the earner count; residential income beside presence by time of day; residence and workplace geography; and wage trends by sector and area, separated from changes in worker mix (the trend by sector is a national Public figure from the wage series by economic activity, never a protected split). The average is never shown alone, and the figures describe covered earners and wages paid, not households, wealth or spending power.
- **Inferred**: Evidence status for a reasoned result, including a user scenario. It names its basis and, for catalogue claims, a permitted strength.
- **Input classes**: Every class that fed a composite fact, including Public, Synthetic, Simulated and, where applicable, user input.
- **ISIC Rev.4**: The international activity classification used by the reviewed activity spine. Prefix similarity alone never approves a mapping.

## L

- **Leaf atom**: A mutually exclusive population and primitive inside one additive family: a unit, band, category, joint home-by-work category, side count or register category leaf. Only leaf atoms are perturbed. An `other` row is a treated leaf where pooling occurred. `ALL`, `all`, parent bands and municipality, national and area totals are derived inside their home family.
- **Layout**: The brief's ordered component instances, validated against the component catalogue before rendering. Unknown components, properties or fact kinds reject it.
- **Least-real rule**: Code that marks a composite Public only if all inputs are Public, otherwise Synthetic or Simulated according to the least-real input, with suppression taking precedence.
- **Ledger**: The append-only record of questions, tool calls, saved briefs and store switches, with release and seat context.
- **Licence-activity count**: One activity on one commercial licence. It is not a firm, establishment or job.
- **Lineage**: The references that connect a fact to its release table, methods, sources, rules and release.
- **Load receipt**: `load_receipt.json`, a loader output that is not listed in `manifest.artefacts`, with `state: complete` and the matching manifest `release_id`, written only after both stores are staged and verified. A protected-release receipt also carries the matching protected-window fields. Preflight and the API refuse a release without a complete, matching receipt.
- **Loader**: The only path from a release into either store. It verifies paths, hashes, schemas and allowed tables before atomically loading and writing the receipt.
- **Local ledger**: The SQLite fallback for ledger and egress rows while PostgreSQL is unavailable; oversight shows “paused”.

## M

- **Manifest**: `manifest.json`, the release's declaration of `release_kind`, tables, artefacts, sources, applicable contracts, rules and digests. A `public_only` manifest omits the protected-window fields.
- **Method card**: The definition of one deterministic economic method, including inputs, formula, worked public example, provenance and permitted wording.
- **Mobility**: The record type for aggregate presence and movement. In this project it is simulated and contains no trajectories or device identifiers.
- **Monthly period**: One month of the synthetic reference period, released inside the one protected window, whose protected `period` is the span of its months. Each month passes the same disclosure controls as a single period, one treatment holds for every month, and cross-month differencing attacks must recover nothing (decision 0016).
- **Municipality**: An official public geography used for licences, population and coarse aggregates; it is not interchangeable with a showcase area.

## N

- **Named synthetic firm**: A synthetic firm shown by its fictional name, activity, size band and area only, always marked Synthetic. Its name never resembles a real one, and the build fails on a collision with a real place or business name. It is never placed at a real address or drawn as a named point, its own wages, wage bill and headcount are never shown, and lists of such firms obey the minimum, dominance and complement rules of any protected figure. Its subject, `synthetic_firm`, accepts Synthetic slots only (decision 0016).
- **National unit**: A released sum over published units, labelled “published areas”; it is not an independent hidden total.
- **NO_DATA**: Tool status meaning that the release has no answer for a valid request. It includes a reason and is not zero.
- **Not measured**: A coverage label for a person whose job is outside the wage system's coverage and who therefore has no pay in the wage records. It never means zero and is not an evidence status; an unknown housing class is separately `unknown`.
- **Null area**: A planted area with no intended truth, used to test false discovery.

## O

- **Observed**: Evidence status for a value read or deterministically calculated from its declared sources. It does not upgrade Synthetic or Simulated data to reality.
- **Open item**: A tracked unresolved decision, assumption or pending proof in [OPEN_ITEMS.md](../OPEN_ITEMS.md).
- **OUT_OF_SCOPE**: Tool status for a request the product does not answer, with an application-selected scope template.
- **Oversight seat**: The `oversight` view of anonymised ledger and demand information. It carries no organisation identity, question text or brief text.

## P

- **Parameter set**: Privacy proposal A or stricter B. Both are evaluated inside the custodian plane; exactly one selected set's protected tables are exported in a release. Data owners set real values.
- **Parity suite**: Tests that run the same queries and tools on PostgreSQL and the embedded engine and require identical normalised facts.
- **Partition**: A complete, non-overlapping assignment of frame cells to release units for one population and tier. Protected partitions over one population form a nested laminar hierarchy.
- **Partition family**: The single parent-linked laminar hierarchy for one contributor universe. Every protected partition and breakdown over those people or employers nests within it, so any two units are contained one in the other or disjoint; independent merges never cross.
- **Person concentration**: The disclosure test on the largest single wage's share of a unit's wage bill.
- **Plan rail**: Application-generated steps and statuses for the current answer. It never displays model thinking or prose.
- **Playbook**: One deterministic question journey from the closed, versioned playbook list of document 09. The first pack had three (`site_check`, `staffing_and_pay`, `costs_and_suppliers`); the list grows to cover the seven decision journeys (decision 0016).
- **Presence cube**: The aggregate simulation by cell, segment, day type, time block and season. It contains no individual agents or trails.
- **Presence index**: The unitless Simulated score of workers, residents and visitors of the first pack, on a fixed, pre-committed scale that imposes no sum over protected rows. Decision 0016 replaces it with **Estimated people present**. No presence figure is ever a named building's or business's footfall.
- **Presence scale**: The positive fixed denominator of the first pack's presence index, `presence_score = 100 × arithmetic_mean(expanded_presence over situation hours) / presence_scale` (PRV-59), identical for A and B and never derived from protected-row sums. Version 1 releases presence as rounded estimated counts, so it uses no presence scale; the rule applies only to an index that a contract keeps (decision 0016).
- **Primitive**: An additive released leaf atom from which deterministic code derives other statistics.
- **Privacy receipt**: The per-answer record of release, rules, parameter set, snapped units, treatments, withheld items and accounting-gate result.
- **Product plane**: The read-only serving environment in `product/`, which mounts one release and never imports custodian code.
- **Projection**: A simple projection of a published or released series by tested code, marked as a projection with its method and period. It is never a revenue, demand or success forecast (decision 0016).
- **Proof room**: The view for attack replays, survival, parity, fidelity and sealed evidence, one level below the main journey.
- **Prospect list**: The customer finder's list of named synthetic firms by sector and size band in a targeted territory (journey D3). It is Synthetic, shows no wage, wage bill or headcount, and obeys the list rules of every named synthetic firm.
- **Provenance**: Where data comes from: Public, Synthetic, Simulated or Suppressed.
- **Public**: The provenance class for real cited public data, with publisher, licence, retrieval date and hash.
- **Public cache**: The uncommitted `data/public_cache/` store of fetched public inputs and their sidecar provenance.
- **Public split**: An official figure split by sex or nationality, shown only as a Public fact with its source and year, on the source's own geography and categories (for nationality, the published Qatari and non-Qatari categories). It is never joined to a synthetic record, used to segment synthetic records, apportioned to a drawn area or combined with a protected figure (decision 0017).

## Q

- **Query isolation**: The demonstration that, after seat selection, fixed functions and row-level security restrict each company's reads. It is not identity or tenant authentication.
- **Question catalogue**: The versioned set of permitted follow-up questions and their typed slots. Exactly three valid next questions are selected for each brief.

## R

- **Rank-stability sentence**: The application-template sentence beside every rank that says how stable the rank stays when the weights vary, with its figures from tested code (method card C11, MTH-45). A rank is never shown without it.
- **Reachable access**: A travel-time catchment score from tested code (method card C12), by hour of day where congestion changes travel time; the hourly form is Simulated.
- **Release**: An immutable content-addressed folder of statistics, manifest and listed artefacts. Its kind is `public_only` or `protected`; a `public_only` release contains no Protected or Simulated table and is never frozen or registered. A release is the only artefact that crosses from custodian to product.
- **Release id**: The full SHA-256 of the canonical manifest with `release_id`, `build_id` and `built_at` removed and every table and artefact digest included.
- **Release unit**: A whole-cell unit is one base cell or a union of whole base cells inside one root. Three unions cross roots and stay inside one municipality: a remainder, the union of that municipality's failed roots; the terminal `ha_home` unit, the union of every residence unit and remainder of that municipality; and the municipality unit of each of the four pay partitions `rp_all_money`, `rp_all_quartile`, `wp_all_money` and `wp_all_quartile`, the union of that partition's units and remainders in that municipality. Apart from the two unreleased stayer wage bills behind its stayer index, which are ordinary wage-bill leaves treated once with their own cell key and never released (PRV-55), such a unit holds no leaf of its own: each of its released additive figures is the exact sum of the treated leaves of its published units (PRV-13, PRV-16). A published unit has passed the privacy rules and stores its polygon.
- **Ratio statistic**: One of the mean wage or the coverage, irregular or deployed-elsewhere shares. Its numerator and denominator come from columns of the same stored rows — one table, one partition, one unit set and one measure where the table has measures — even where the columns belong to two additive families. Its fact lineage names both families. It is the only exception to one home family per figure (PRV-30).
- **Reliability**: A code-assessed band that flags small-count evidence without changing the value or its provenance.
- **Remainder**: Failed frame roots pooled by municipality. It is published only if the pooled population passes; otherwise it is withheld without values.
- **Requirement ID**: The stable identifier defined once in the first column of a requirement table and used by tasks, tests and reviews.
- **Reverse fit**: The reverse of the best-location ranking: for a site, which activities fit, for property owners matching tenants to the business mix and the catchment's wage profile. It is the output of tested code over visible criteria, never advice to act.
- **Root**: The intersection of a resolution-7 parent with a municipality from which the privacy partition algorithm starts, so no release unit crosses a municipality boundary.
- **Routing graph**: The manifest-listed road-network artefact used for walk and drive areas from any point, network distances and the traffic assignment; drive times change with the hour where Simulated congestion changes them.

## S

- **Sanad**: See **Source chain (sanad)**.
- **Source chain**: See **Source chain (sanad)**; the evidence drawer label for the complete lineage of a fact.
- **Sealed scenario**: The set of planted truths, traps, null areas and canaries written by an independent reviewer from a different maker and encrypted to the owner's public key. Its plaintext hash is committed before the build; the builder never sees its plaintext.
- **Scene endpoint**: The non-production route `POST /api/proof/scene` (PRV-119). Request body exactly `{"fixture_id": "scene:<lowercase SHA-256>"}`; accepts only manifest-listed fixture ids and returns two pre-validated unit sets and area answers.
- **Sealed world**: W0, with spare seeds W1 and W2, built from a sealed scenario so builders cannot tune to known answers.
- **Seat**: `oversight`, `company_a` or `company_b`, chosen once and bound to a window by the signed `eii_seat` cookie.
- **Service**: One of the three outputs that decision 0016 delivers through the journeys: service S1, the market entry evidence pack; service S2, the comparison of growth and operating options; service S3, local supplier and workforce connections. It is distinct from a slice or a capability with a similar label.
- **Similar areas**: The search for areas like a given one, using three area types (decision 0016; MTH-49).
- **Slice**: One gated implementation step of [14_IMPLEMENTATION_PLAN.md](14_IMPLEMENTATION_PLAN.md), always written with the word slice, such as "slice S0". It is distinct from a SHOULD capability and from a service with a similar label.
- **Snap**: The deterministic conversion of a pin with a distance or travel-time shape, or of a drawn shape, into whole release units before any figure from the four protected record types is read. Public and Simulated layers are not snapped.
- **Snap report**: The requested and released areas, units and cells added or dropped, with the partition and rules that explain the fit.
- **Source chain (sanad)**: The complete chain fact → release table → method and version → source publisher, dataset, licence, retrieval date and hash. A fact without it is rejected.
- **Source registry**: The release table of public and synthetic source metadata, attribution, licences, dates and hashes.
- **Stable treatment**: Treatment applied once at build time and stored, so identical questions and areas that snap to the same units return identical answers.
- **Stage**: The map surface and its governed layers, captions, watermark and stage directives.
- **Stage directive**: A closed `stage` tool instruction such as fly, layer, highlight, rings, dial, split or set scenario inputs. It carries no numeral to render.
- **Standing strip**: The permanent demonstrator notice and provenance legend, present on every screen and export.
- **Still to test**: Evidence status for what the current evidence cannot establish, with a next test rather than a confident conclusion.
- **Store**: PostgreSQL serving or the embedded DuckDB reader of the same release, selected at start-up with no automatic mid-request failover.
- **Suppressed**: The provenance class for a value withheld by privacy rules. It carries no value and must explain the available reason and alternative.
- **Survival report**: The per-partition account of units published, pooled or withheld and the covered-earner share published, measured only on synthetic data.
- **Synthetic**: The provenance class for invented custodian-type records and their protected aggregates. It is not evidence about Qatar.
- **Synthetic identifier**: A visibly invented `SYN-…` identifier that cannot be mistaken for a real registration, establishment or personal identifier.

## T

- **Target class**: People or employer groups the attacker-view model cannot tell apart, because they share the same published-unit memberships, the same contribution class and the same months. The audit solves each class once (PRV-112).
- **Target-surplus scenario**: An optional user scenario with target surplus share `U`, where `0 <= U < m`. Required revenue is `F / (m - U)` and breakpoints use `m - U`; `U = 0` is the default break-even case. A positive target is never called break-even and is not a revenue, demand or capture forecast.
- **Task ID**: The identifier and scope of one unit of work in [TASKS.md](../TASKS.md), used for its branch, review and evidence.
- **Template writer**: Deterministic code that composes the same structured brief from the same facts and catalogues without a model.
- **Tier**: The count, money or quartile level at which a release unit and its primitives pass disclosure tests.
- **Tool status**: `OK`, `SUPPRESSED`, `NO_DATA` or `OUT_OF_SCOPE`; it is separate from provenance and evidence status.
- **Traffic assignment**: Tested code that assigns released hourly origin-destination flows to the road graph with one fixed volume-delay rule, giving Simulated congestion and link speeds by hour; drive-time areas change with the hour. Traffic is never computed from protected rows (decision 0016).
- **Trap**: A planted synthetic pattern that must be flagged or read cautiously, not interpreted naively.
- **Treatment**: Stable perturbation, rounding and band merging applied once at build time and stored, so repeated questions return identical answers.
- **Trust centre**: The view of rules, sources, licences, model boundaries, egress and limitations.
- **Typed-decision gateway**: `eii_gateway` in `gateway/`, an offline provider-neutral interface for bounded judgments over supplied inputs. Its default provider is `none`, and it never determines facts, numbers, privacy, gates or screen content.

## U

- **Unit member**: The mapping from a release unit to every base cell it contains, used to preserve exact partition membership.
- **User scenario**: A deterministic result from the user's own inputs, marked Inferred and “your inputs” and never stored in the release.

## V

- **Validation scorecard**: The predeclared comparison of calibration anchors and separate hold-outs with fixed tolerances and reviewer evidence.
- **Vault**: The ephemeral custodian-plane folder for record-level synthetic data, deleted after every build and unreachable from the product.
- **Venue crosswalk**: The committed, reviewed table that maps each venue name seen in the public visitor-count series to one venue, because names vary between years. The build normalises names only through it and never edits a value by hand (decision 0017).
- **Viewing as badge**: The immutable display of the selected seat, derived from its signed session context rather than editable interface state.

## W

- **Wage band**: One of the fixed B01 to B12 pay ranges; bands may be merged for privacy, and the top band remains open.
- **Wage bill**: An additive treated pay primitive used with earner counts to derive means and other statistics.
- **What changed**: Comparisons between released monthly periods, and of public series over time, computed by tested code: openings and closures, cluster change, and wage trends separated from changes in worker mix. It is Synthetic wherever its inputs are synthetic (decision 0016).
- **Window key**: The SHA-256 of canonical JSON holding the protected `period` and, for the four protected contracts (`business_register.v1`, `employment.v1`, `residence.v1`, `wages.v1`, in that name order), the pair `{name, sha256}` where `sha256` is the `feed_sha256` the manifest already records for that feed. It does not change when a Public or Simulated table, a scene fixture, a report or a treatment rule changes. A change that alters a feed under the same `world_seed` gives that seed a second `window_key`, which the uniqueness rule refuses; no invariance to scenario text is claimed (PRV-120).
- **Within reach**: The area made from a door by an allowed distance, walk or drive cut-off, by hour of day where congestion changes travel time; its protected figures snap to release units.
- **Worked example**: A public or synthetic arithmetic example with a known answer, used as a regression test for a deterministic method.

## Z

- **Zone**: An official public geography used for utilities, census shares and momentum. It is never apportioned into protected grid facts.

## Open questions and assumptions

Vocabulary follows the current master decisions and lead rulings. Any unresolved meaning or cross-document mismatch belongs in [OPEN_ITEMS.md](../OPEN_ITEMS.md), not in an unspoken local redefinition.

- OPEN: the apportioning weight for drawn shapes (area, or a licensed public population grid) is fixed in document 07 and confirmed at slice S2 (decision 0016).

## Sources

- [Project brief](01_PROJECT_BRIEF.md), [architecture](02_ARCHITECTURE.md), [data contracts](03_DATA_CONTRACTS.md) and [privacy rules](06_PRIVACY_AND_DISCLOSURE_CONTROL.md).
- [AI assistant](09_AI_ASSISTANT.md), [front end](10_FRONTEND.md), [design direction](11_DESIGN_DIRECTION.md) and [decision 0014](decisions/0014-typed-decision-gateway.md).
- The accuracy, governed-interface and model-routing decisions reflected in [AGENTS.md](../AGENTS.md).
- [Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) and [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), 2026-11-12, for the terms they add or change.
