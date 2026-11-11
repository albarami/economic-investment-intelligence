# Glossary

| | |
|---|---|
| Status | Draft v0.2, corrected after independent review on 2026-11-11 (see PROGRESS.md) |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Define the shared vocabulary of the EII proof of concept without changing its binding decisions. |
| Read first | [README.md](../README.md), [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md) |

## In brief

- Provenance and evidence status are different axes; tool status is a third concept.
- “Observed” never means “real” when a fact is Synthetic or Simulated.
- “Not measured” is a coverage label, never zero and not an evidence status.
- A release contains statistics only; record-level synthetic inputs stay in the build vault.
- The application calculates and renders. Models select catalogue entries; they do not write prose, queries or numbers.
- Terms are requirements for the planned product, not claims that it exists.

## A

- **Accounting gate**: The deterministic audit before display, labelled on the receipt as "Checked before display". It runs five checks—Sources, Assumptions, Nothing invented, Scope, Limits stated—on the complete structured brief; failure selects the template writer and is logged.
- **Activity spine**: The reviewed mapping among commerce activity code, ISIC Rev.4 class and public place category, with unmapped and not-mappable cases visible.
- **Additive family**: One release table, one partition, one measure where the table has measures, and one breakdown. Inside it the leaves are mutually exclusive and treated once, and every stored total is the exact sum of that family's own leaves. Equality is not required between families (PRV-29, PRV-71).
- **Area**: The released geography used for an answer, built from a pin and snapped to whole release units before any protected figure is read.
- **Artefact**: A non-table file listed and hashed in a release manifest, such as a routing graph or signed build report.
- **ASSUMPTION**: A labelled default chosen where no binding decision exists. It is not evidence and needs the named decision or test stated with it.
- **Atom**: A leaf atom or one of its derived totals inside one additive family. An `other` row is a treated leaf where pooling occurred, not a derived total. The atom's population is the set of contributors it counts.
- **Attack suite**: Typed recovery predicates (PRV-116) that must succeed with controls off and fail with controls on. Both parameter sets are evaluated inside the custodian plane; exactly one protected table set is exported.
- **Attacker-view audit**: The one release-gating acceptance model (PRV-112 to PRV-116, PRV-121). Every published leaf is fixed to its untreated aggregate. Signed knowledge fixtures are checked against sealed truth before use, and a published leaf is constrained as having passed its rules. Targets the model cannot tell apart form one target class and are audited once. A time budget is set from a measured run at the start of slice S5. What the layout tells about a population that failed a rule is not in the model. The audit is evidence under a stated attacker, never a proof. Its configuration is `artefacts/attacker_view_audit.json`; public totals are `artefacts/attacker_view_public_totals.json`.

## B

- **Base cell**: A cell of the fixed H3 frame at resolution 9 in Greater Doha and resolution 8 elsewhere.
- **Brief**: The answer column and its structured selection of claims, caveats, next questions, layout and stage directives.
- **Build machine**: The computer that runs public fetching, synthetic generation, privacy treatment, release building and verification.

## C

- **Calculation layer**: Deterministic tested code in `eii_core.calc`, the release build, or a fixed application-schema read function listed by the data contracts and covered by tests. Every displayed number and comparison comes from one of those three places; nothing else computes, rounds or compares a number, and no model ever does.
- **Calculated import unit value**: The deterministic Public customs ratio of import value to net mass, expressed in QAR per kg. The valuation basis appears as the source states it or as “not stated by the source”; display baskets are defined at eight digits or finer. It is not a landed cost.
- **Calibration manifest**: The generator's complete parameter register. Each parameter is ANCHORED to cited public evidence or ASSUMED with a range and sensitivity sweep.
- **Canary**: A planted synthetic marker or truth used to prove that attacks and leak scans have teeth. It must be recoverable with controls off and unrecoverable with controls on.
- **Catalogue version**: The combined hash of the claim, component, fragment and question catalogues, stored in every brief and included in its memo key.
- **Claim catalogue**: The versioned application data that defines permitted Observed and Inferred claims, subjects, fact slots, caveats, strengths and bilingual templates.
- **Component catalogue**: The closed, versioned set of evidence cards and interface components with typed schemas. Components accept fact ids, release unit ids and enumerations, never free numbers, code, HTML, styles or URLs.
- **Conformance suite**: Contract tests that every synthetic or future real adapter must pass unchanged before a feed or release is accepted.
- **Contributor**: The person, job or establishment population behind an atom, defined on a residence, workplace or register basis.
- **Covered earner**: A person in an eligible covered private-sector job. People outside that coverage are not measured, not zero.
- **Coverage**: A declaration of what a feed or figure includes and excludes. Missing coverage is shown explicitly and never converted to zero.
- **Custodian**: The body that holds a record type under its own mandate. The pack uses neutral record-type names and does not imply supply or endorsement.
- **Custodian plane**: The offline build environment and the only place record-level synthetic data may exist. Only a release leaves it.

## D

- **Decision class**: One of five closed offline gateway jobs: `spine_match`, `router_miss_finder`, `brief_second_reader`, `question_route` or `string_parity`.
- **Decision record**: A numbered amendment record explaining context, decision, evidence and consequences. In the gateway context, it instead means one JSON audit record under `evals/typed_decisions/runs/`; the two are not the same artefact.
- **Dial**: The control that selects a stored situation and summer setting for the presence index. It is not a clock and has no intermediate positions.
- **Dial situation**: One of `weekday_lunch`, `weekday_evening`, `friday_evening` or `ramadan_iftar`; summer applies only to the first three.
- **District**: An official public geography below municipality. Public district figures are never blended into protected grid statistics.
- **Dominance**: A disclosure risk when one employer group, the largest two groups, or one person accounts for too much of a unit's earners, establishments or wage bill.
- **Door**: A user's pin at a place, snapped to the fixed grid before areas and facts are built.
- **DuckDB**: The release build engine and the embedded read-only standby. Parquet remains the source of truth and the embedded file is disposable.

## E

- **Egress record**: The append-only record of an attempted outbound model request, including exact payload bytes and hash, written before response content is used.
- **Employer group**: Establishments rolled up through legal entity to a hidden group used for dominance tests. It never leaves the vault.
- **Evidence card**: A governed display of one evidence block with Fact chips, class marks, coverage and required caveats.
- **Evidence drawer**: The one-tap view of a fact's provenance, evidence status, inputs, rules, coverage and source chain.
- **Evidence status**: How an answer uses a fact: exactly Observed, Inferred or Still to test. “Not measured” is a separate coverage label, not an evidence status.
- **Experience plane**: The browser application in `web/`. It renders released facts and cannot calculate statistics or reach the vault.
- **Export register**: The committed append-only file `infra/export_register.jsonl`. The first `./eii freeze` run appends one line with these seven fields in order: `window_key`, `protected_sha256`, `world_seed`, `rules_version_id`, `parameter_set`, `release_id`, `code_version`. Continuous integration checks this file alone: existing lines unchanged, one `protected_sha256` per `window_key`, and one `window_key` per `world_seed`. The second no-flag freeze run builds and verifies the application archive from a base-branch commit containing the line and marks `freeze.json` complete. A frozen bundle can be installed or started only when its descriptor is complete and the register inside the installed application holds its line. No signed receipt file is added (PRV-120).

## F

- **Fact**: The governed object that carries a value, unit, period, geography, provenance, input classes, evidence status, reliability, coverage, caveats, labels, lineage and release.
- **Fact chip**: The only interface component family allowed to render a numeral. It shows the fact's value and marks and opens its Evidence drawer.
- **Fact id**: `f_` plus 32 hexadecimal characters derived from the canonical release id, metric key, geography, period and qualifiers.
- **Feed**: One delivery of one source contract for one reference period, produced by an adapter and checked by its conformance suite.
- **Feed bundle**: A feed manifest, coverage declaration and declared tables with hashes and row counts. Missing headers, scope or internal period fail acceptance.
- **Fixture (scene)**: A manifest-listed fixture identity accepted by the scene-only endpoint for a prepared “Try to break it” request. The complement step returns two pre-validated unit sets; production tools still accept only pin-based areas, and no run-time path holds unprotected data.
- **Fragment catalogue**: The versioned application-owned text fragments from which headline and decision templates may be selected. Model output chooses keys; it never edits the fragments.
- **Fidelity report**: The synthetic-world comparison with public margins and predeclared tolerances. It supports “consistent with published anchors within stated tolerances”, never “validated”.
- **Flow scale**: The positive fixed denominator in `rules_version` used in `flow_score = 100 × sum(expanded_trips over situation hours) / flow_scale` (PRV-59). Committed with `presence_scale` at slice S1, identical for A and B, never derived from protected-row sums.
- **Fuzz pairs**: Seeded random area pairs used as regression evidence after the exhaustive structural checks, not as the proof of closure; at least 10,000 pairs per release and per parameter set (PRV-49, PRV-51).

## G

- **Grid cell**: One fixed H3 cell used for custodian-type statistics. Public statistics remain on official geographies.
- **Guided story**: The eight-scene presenter journey from Public evidence through simulation, synthetic pay, privacy attacks and hand-over.

## H

- **Hold-out**: Public evidence excluded from calibration and used later in the validation scorecard. It reduces circular checking but does not prove the simulated world is real.
- **Home family**: The single additive family a displayed figure is normally computed from, named in that fact's lineage (PRV-30). A count and adjacent non-ratio shares use the same home family. The closed ratio-statistic list is the only exception.
- **Housing class**: The housing-split values `family_housing`, `labour_accommodation`, `institution` and `unknown`, plus an explicit `other` row where pooling occurred. `other` is a treated leaf. The count that is not measured is a separate population, not a housing class.

## I

- **Income geography**: Area-level wage statistics for covered earners by home and workplace, released only as privacy-protected statistics.
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
- **Municipality**: An official public geography used for licences, population and coarse aggregates; it is not interchangeable with a showcase area.

## N

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
- **Playbook**: One deterministic question journey: `site_check`, `staffing_and_pay` or `costs_and_suppliers`.
- **Presence cube**: The aggregate simulation by cell, segment, day type, time block and season. It contains no individual agents or trails.
- **Presence index**: A unitless Simulated index of workers, residents and visitors around an area on a fixed, pre-committed scale that imposes no sum over protected rows. It is never a person count or named-building footfall.
- **Presence scale**: The positive fixed denominator in `rules_version` used in `presence_score = 100 × arithmetic_mean(expanded_presence over situation hours) / presence_scale` (PRV-59). Committed with `flow_scale` at slice S1, identical for A and B, never derived from protected-row sums.
- **Primitive**: An additive released leaf atom from which deterministic code derives other statistics.
- **Privacy receipt**: The per-answer record of release, rules, parameter set, snapped units, treatments, withheld items and accounting-gate result.
- **Product plane**: The read-only serving environment in `product/`, which mounts one release and never imports custodian code.
- **Proof room**: The view for attack replays, survival, parity, fidelity and sealed evidence, one level below the main journey.
- **Provenance**: Where data comes from: Public, Synthetic, Simulated or Suppressed.
- **Public**: The provenance class for real cited public data, with publisher, licence, retrieval date and hash.
- **Public cache**: The uncommitted `data/public_cache/` store of fetched public inputs and their sidecar provenance.

## Q

- **Query isolation**: The demonstration that, after seat selection, fixed functions and row-level security restrict each company's reads. It is not identity or tenant authentication.
- **Question catalogue**: The versioned set of permitted follow-up questions and their typed slots. Exactly three valid next questions are selected for each brief.

## R

- **Release**: An immutable content-addressed folder of statistics, manifest and listed artefacts. Its kind is `public_only` or `protected`; a `public_only` release contains no Protected or Simulated table and is never frozen or registered. A release is the only artefact that crosses from custodian to product.
- **Release id**: The full SHA-256 of the canonical manifest with `release_id`, `build_id` and `built_at` removed and every table and artefact digest included.
- **Release unit**: A whole-cell unit is one base cell or a union of whole base cells inside one root. Two unions cross roots and stay inside one municipality: a remainder, the union of that municipality's failed roots, and the terminal `ha_home` unit, the union of every residence unit and remainder of that municipality. A published unit has passed the privacy rules and stores its polygon.
- **Ratio statistic**: One of the mean wage or the coverage, irregular or deployed-elsewhere shares. Its numerator and denominator come from columns of the same stored rows — one table, one partition, one unit set and one measure where the table has measures — even where the columns belong to two additive families. Its fact lineage names both families. It is the only exception to one home family per figure (PRV-30).
- **Reliability**: A code-assessed band that flags small-count evidence without changing the value or its provenance.
- **Remainder**: Failed frame roots pooled by municipality. It is published only if the pooled population passes; otherwise it is withheld without values.
- **Requirement ID**: The stable identifier defined once in the first column of a requirement table and used by tasks, tests and reviews.
- **Root**: The intersection of a resolution-7 parent with a municipality from which the privacy partition algorithm starts, so no release unit crosses a municipality boundary.
- **Routing graph**: The manifest-listed road-network artefact used for pin-based walk and drive areas and network distances.

## S

- **Sanad**: See **Source chain (sanad)**.
- **Source chain**: See **Source chain (sanad)**; the evidence drawer label for the complete lineage of a fact.
- **Sealed scenario**: The set of planted truths, traps, null areas and canaries written by an independent reviewer from a different maker and encrypted to the owner's public key. Its plaintext hash is committed before the build; the builder never sees its plaintext.
- **Scene endpoint**: The non-production route `POST /api/proof/scene` (PRV-119). Request body exactly `{"fixture_id": "scene:<lowercase SHA-256>"}`; accepts only manifest-listed fixture ids and returns two pre-validated unit sets and area answers.
- **Sealed world**: W0, with spare seeds W1 and W2, built from a sealed scenario so builders cannot tune to known answers.
- **Seat**: `oversight`, `company_a` or `company_b`, chosen once and bound to a window by the signed `eii_seat` cookie.
- **Slice**: One gated implementation step, slice S0 to slice S11. It is distinct from a SHOULD capability with a similar label.
- **Snap**: The deterministic conversion of a pin and requested distance or travel-time shape into whole release units before reading figures.
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
- **Viewing as badge**: The immutable display of the selected seat, derived from its signed session context rather than editable interface state.

## W

- **Wage band**: One of the fixed B01 to B12 pay ranges; bands may be merged for privacy, and the top band remains open.
- **Wage bill**: An additive treated pay primitive used with earner counts to derive means and other statistics.
- **Window key**: The SHA-256 of canonical JSON holding the protected `period` and, for the four protected contracts (`business_register.v1`, `employment.v1`, `residence.v1`, `wages.v1`, in that name order), the pair `{name, sha256}` where `sha256` is the `feed_sha256` the manifest already records for that feed. It does not change when a Public or Simulated table, a scene fixture, a report or a treatment rule changes. A change that alters a feed under the same `world_seed` gives that seed a second `window_key`, which the uniqueness rule refuses; no invariance to scenario text is claimed (PRV-120).
- **Within reach**: The area made from a door by an allowed distance, walk or drive cut-off and snapped to release units.
- **Worked example**: A public or synthetic arithmetic example with a known answer, used as a regression test for a deterministic method.

## Z

- **Zone**: An official public geography used for utilities, census shares and momentum. It is never apportioned into protected grid facts.

## Open questions and assumptions

Vocabulary follows the current master decisions and lead rulings. Any unresolved meaning or cross-document mismatch belongs in [OPEN_ITEMS.md](../OPEN_ITEMS.md), not in an unspoken local redefinition.

## Sources

- [Project brief](01_PROJECT_BRIEF.md), [architecture](02_ARCHITECTURE.md), [data contracts](03_DATA_CONTRACTS.md) and [privacy rules](06_PRIVACY_AND_DISCLOSURE_CONTROL.md).
- [AI assistant](09_AI_ASSISTANT.md), [front end](10_FRONTEND.md), [design direction](11_DESIGN_DIRECTION.md) and [decision 0014](decisions/0014-typed-decision-gateway.md).
- The accuracy, governed-interface and model-routing decisions reflected in [AGENTS.md](../AGENTS.md).
