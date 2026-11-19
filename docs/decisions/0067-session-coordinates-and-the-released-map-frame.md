# Decision 0067: Session coordinates and the released map frame

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-19 |
| Owner | The owner |
| Decided by | Not yet decided; this is the requested S7-CONTRACT proposal, not an activation ruling |
| Amends | Once accepted: document 03 sections 9, 9.2 and new 9.3; document 08 sections 8.1 and 8.3; document 10 section 5. The draft rows below carry their own identifiers. No accepted decision text is rewritten. |
| Purpose | Define the coordinate units, session geography, semantic identities, released reference-frame lineage and coverage refusal needed by S7-T29 and S7-T33, without authorising a model or browser calculation |
| Read first | [Document 03](../03_DATA_CONTRACTS.md), DAT-90 to DAT-95, DAT-105 to DAT-107, DAT-120 to DAT-124, DAT-145 to DAT-149; [document 04](../04_PUBLIC_DATA_PACK.md), PUB-19, PUB-24, PUB-29 and PUB-30; [decision 0065](0065-eight-everyday-capabilities-of-the-map-screen.md), items 2, 7 and 9; [AGENTS.md](../../AGENTS.md), rules 6 to 8, 16 to 19, 21 to 25 and 46 |

## Context

The supplied S7-T29 build return, **Lead ledger records and consultation**, stops at:

> Supply the obtained requirement IDs and activation ruling under decision
> 0065 item 9. Default: no invented IDs; routes remain unmounted.

It separately asks to approve the geodesic model, algorithms, units,
precision/rounding and independent fixtures in document 07. Its approved plan,
**Open points → safe defaults**, also leaves trusted seat context and the
outside-polygon orchestration unresolved.

The supplied S7-T33 build return, **Activation condition and disposition**, stops at:

> The approved plan, page 2, “Open → safe default”, explicitly requires reviewed contract/IDs for the new unit, session
> geography and released-reference-frame lineage **before activation**.

That return also requires agreement on mapped-land/extract limits for
`outside_map`. The two returns and their approved plans were supplied under
`.overnight/IN/`; their implementation claims concern their own earlier stack,
not the present base. [TASKS.md](../../TASKS.md), S7-T29 and S7-T33, and decision
0065 items 2 and 7 are the pack authority for the requested capabilities.

Reading establishes the following, rather than their implementation:

- Document 03 section 1.1 defines mapped land as the union of the eight
  municipality polygons. A missing base cell does not make a land point outside.
  Sections 7.2 and 7.3 already name `municipality`, `gazetteer`, `fact_lineage`
  and `source_registry`; no new reference-frame table is needed.
- Document 04 PUB-24 fixes `bnd_hdx` as frame geometry; the 2020 layers are
  build-time checks. Its source registry names **Qatar Subnational Administrative
  Boundaries (COD-AB)**, publisher **HDX, source Planning and Statistics
  Authority**, licence **CC BY-IGO**. The tracked source configuration uses
  `bnd_hdx`, `licence_id: cc-by-igo`. This is attribution, not a comparison.
- `custodian/src/eii_custodian/publicdata/frame/README.md` records `frame.v1`;
  `gazetteer.py::make_row` stores ordinates with six decimal places and
  `ROUND_HALF_EVEN`. `administrative_rows` obtains an interior point from the
  published boundary, whereas `reviewed_points` reads a source-given point.
  A read of the table alone must not call both origins measured coordinates.
- `core/src/eii_core/calc/facts.py::least_real` requires a release input class;
  `user_input` alone is refused. The wire schema in document 03 section 9
  admits neither `decimal_degrees` nor session-point geography.
- The stated base is `b4ca3324b5c089f3ddef36bd0086d7fc465b921d`.
  `core/src/eii_core/facts.py`, cited by the supplied returns, is absent here;
  the present `contracts/` contains its scaffold note. No closed-list admission
  or navigation/measurement implementation on another stack is inferred.

No release, public cache or live source was read for this proposal. Retrieval
dates and file hashes below are bindings to verified release fields, not values
invented by this document. CONSULT entries are in [OPEN_ITEMS.md](../../OPEN_ITEMS.md),
**S7-CONTRACT — decision 0067 consultations**.

## Decision

Every item below is **proposed**. The accompanying requirement rows apply only
following acceptance of decision 0067 and the stated activation prerequisites.

1. **One coordinate unit, two metrics, one calculation owner.** Reserve numeric
   unit `decimal_degrees` and metric keys `longitude` and `latitude`, never a
   combined numeric string or a new date/text unit. Their finite ranges are
   longitude from -180 to 180 and latitude from -90 to 90, inclusive. Named JSON
   fields determine the axis; geometry order is longitude, latitude in
   EPSG:4326, following document 03 section 1.2. Never swap, wrap, clamp or snap.
   The proposed deterministic method is
   `eii_core.calc.coordinates.position@v1`: parse/normalise user decimal input,
   check range and coverage on the unrounded position, then quantise each
   display value to six decimal places using `ROUND_HALF_EVEN`; normalise signed
   zero to zero. Convert a pointer's finite JSON number by its server-side
   decimal representation, never by browser rounding. This precision is a
   display convention, **not positional accuracy**. The browser only captures
   input, draws returned geometry and applies Fact-chip grouping/unit patterns.
   Published `gazetteer.lon` and `.lat` remain the released six-place values;
   no handler creates a new representative point. Source: document 03 section
   7.3 `gazetteer`, DAT-90/DAT-93; document 08 BE-21/BE-23/BE-104; frame
   `gazetteer.py::make_row`; decision 0065 item 7. The method name is a proposed
   registration, not an assertion that the module exists. DAT-172 defines the
   draft obligation.

2. **Session position, never a named-entity observation.** A cursor, touch or
   keyboard inspection and a typed coordinate are user input over the verified
   Public frame. Their facts have `input_classes: [public, user_input]`,
   provenance `public` by DAT-91, evidence status `inferred`, reliability
   `not_applicable` and caveat `your_inputs`. Public describes the released
   frame input; it does not make the selected point a published or observed
   location. No user-input-only fact is reclassified Public. The new closed
   geography is exactly `{kind: session_point, point_id}`; `point_id` is `pt_`
   followed by a lowercase SHA-256, with no area, unit, place or company key.
   Core derives that digest from canonical JSON holding the mounted release,
   an opaque session nonce supplied by trusted application context and the
   normalised **unrounded** longitude and latitude as decimal strings. The
   nonce and digest live only in process/response memory. Normalisation removes
   redundant decimal zeros and signed zero without discarding precision.
   DAT-93 still derives each `f_` identifier from release, metric, geography,
   period and qualifiers. Reserve coordinate-only qualifiers
   `coordinate_method` (literal `coordinates.v1`) and `coordinate_origin`
   (`cursor`, `typed`, `gazetteer_published`, `gazetteer_representative`). Thus
   axes, different input positions even when rounded alike, origins and releases
   do not collide; identical semantic input in one session is repeatable.
   These keys are internal typed identity, never model-selected arguments.
   Session-coordinate metrics cannot fill a named-place claim or any assistant
   claim/question/directive slot. No fake polygon or new catalogue subject is
   made for a point. Source: DAT-92/DAT-93/DAT-145/DAT-149, BE-50/BE-52/BE-54,
   AI-36/AI-42; decision 0065 items 2 and 7. DAT-173 defines this extension.

3. **No persistence or protected-record join.** Raw typed text, positions, their
   digests, coordinate facts and their response registry are transient; none
   enters a release, database, ledger, log, memo, file, bundle, URL, browser
   storage or persistent cache. No server session store retains raw navigation
   text, points or coordinate facts. Only the current candidate identifiers may
   be retained in bounded session memory for explicit name selection. Drop
   current response/panel memory on close, session/seat/release change and
   restart; reject stale responses. Source access uses the complete registry
   carried with that response; it does not require saving the point for a later
   fact-id lookup. Geometry is drawing-only. Neither geometry nor `point_id`
   joins to a worker, residence, company record or protected row; an eventual
   protected area request still goes separately through `make_area` and whole
   release units. These are local UI operations, not assistant tools: typed text
   goes only to the local resolver; no model, gateway, external geocoder, tool
   ledger or egress recorder receives it. The existing provider address-search
   route remains separate and unchanged. Source: DAT-92/DAT-149,
   BE-54/BE-109/BE-136, decision 0065 item 7 and its approved confinement plan.
   BE-143 and FE-156 define the draft lifecycle.

4. **Actual released reference-frame lineage.** User-coordinate and measurement
   methods must consume the verified `municipality.geometry` rows for coverage,
   rather than attach Public lineage to unrelated input. Use existing release
   objects only, through the following chains:

   | Fact family | Release table and deterministic method chain | Source end of the chain |
   |---|---|---|
   | Cursor or typed coordinate | `municipality` coverage geometry → its `fact_lineage` rows for the frame build (`frame.v1`) and the proposed `eii_core.calc.coordinates.position@v1` transform → `source_registry` by `source_id` | `bnd_hdx`, the publisher/title/licence above, and **that release's** `retrieved_on` and `sha256`; keep the source URL and attribution |
   | Named gazetteer coordinate | Fixed packaged read `navigation_place`, keyed by a selected `gazetteer.place_key`, returns `lon`, `lat`, `source_id` and resolved lineage; core emits the coordinate pair → the gazetteer frame transform/version and its actual source rows | The selected row's source, never automatically `bnd_hdx` for a non-administrative point; preserve every contributing source's publisher/title/licence/`retrieved_on`/`sha256` |
   | Own line or polygon measurement | `municipality` coverage geometry and the session's own geometry → the reviewed measurement transform/version still to be pinned in document 07 → the same existing lineage/source objects | The frame source chain, with user geometry explicitly an input, never a Public source row or an outside publisher's measurement |

   All these tables and columns already have contracts in document 03 sections
   7.2, 7.3 and 11. The release builder must register method-specific lineage
   rows in **existing** `fact_lineage` before service; runtime never fabricates
   a `lin_` key, adds a `source_registry` row or edits an immutable release.
   The transform is recorded as `module.function@version`; the full frame and
   calculation composition must resolve, rather than replacing one with the
   other. Manifest table/schema hashes verify geometry and EPSG:4326, and
   `manifest.sources` must agree with registry source hashes. Frame review and
   supporting inputs, including the `bnd_zone_2020` check and reviewed code/name
   mapping, keep their actual lineage under **PUB-67 supporting provenance**;
   the check layer is never substituted for frame geometry. No session value
   is added to those released rows. The response combines the immutable chain
   with the typed method and transient input identity.

   Proposed coordinate `period` means the frame/source reference period, never
   the date a user pointed or the retrieval date. Document 04 section 2.2
   records `bnd_hdx` geometry dated `2015-11-30`; use that date only when the
   mounted release is verified to carry that edition. A source-given gazetteer
   point uses its own recorded source period. If the method/version, source
   period, geometry edition or any required publisher, title, licence,
   retrieval date or hash cannot resolve, emit no coordinate/measurement Fact;
   navigation returns `NO_DATA/lineage_unavailable` with no camera flight.
   Unavailable metadata is a CONSULT, not a licence to use build time as period.
   Neither `municipality`, `gazetteer`, `source_registry` nor `manifest.sources`
   currently declares a source-period/edition column (document 03 sections 7.3
   and 8). SC-C06 therefore specifically requires the release owner to bind
   the selected immutable source hash to its documented reference period in
   the reviewed method registration, or propose the necessary contract
   amendment. No nonexistent metadata field is read by this proposal.
   Administrative interior points remain Public-derived **Inferred** facts with
   `calculated` and no `user_input`; only genuinely source-given points may use
   Public/Observed and `[public]`. Both use public geography
   `{kind: public, public_code: place:<place_key>}`. Never invent an interior
   point, centroid or source at read time. Source: DAT-94/DAT-105/DAT-106,
   PUB-24/PUB-30, frame `administrative_rows`/`reviewed_points`. DAT-174 and
   BE-142 define the release-read requirement. Actual release completeness is
   unverified by this offline documentation task.

5. **One mapped-land coverage rule, distinct refusals.** Propose `outside_map`
   to mean outside the union of the released `municipality.geometry` polygons,
   with `bnd_hdx` attribution and complete lineage from item 4. It is neither an
   extract bounding box nor the union of grid/release-unit shapes, and it makes
   no claim to a current coastline or sovereign boundary. Include polygon
   boundaries, exclude hole interiors, and use no tolerance, clipping, nearest
   point or cell substitution. Apply coverage to the unrounded selected point;
   an accepted camera target is that validated returned geometry, not a new
   point reconstructed from rounded display facts. For a line or polygon,
   require the **whole** geometry covered by mapped land, including segments
   and polygon interiors, not only vertices. Navigation returns
   `OUT_OF_SCOPE/outside_map`, wording key `navigation.reason.outside_map`,
   proposed English sentence **Outside mapped land coverage.** A measure
   returns `NO_DATA/outside_mapped_land`, wording key `measure.outsideLand`,
   proposed English sentence **Outside the mapped land area.** Paired Arabic
   wording and native review remain CONSULT. No refusal contains a numeric
   value, an echoed input or flight geometry. Malformed/out-of-range inputs are
   `INVALID_ARGUMENT`, not outside-map answers. Missing coverage/lineage is
   `NO_DATA/lineage_unavailable`, never evidence that a point is outside. A land
   point without a base cell passes this coverage test. Source: document 03
   section 1.1 and DAT-146, PUB-24/PUB-29, decision 0065 items 2 and 7.
   DAT-175 and FE-155 define the proposed policy. S7-T29's existing polygon
   ingress rejects before an ID is allocated; this record does **not** pretend
   an identifier-only measurement can classify that rejected polygon. SC-C03
   retains the required orchestration ruling.

6. **Measurement shares the frame, not a fabricated place.** Reserve
   `measure_distance` with existing unit `metres` and `measure_area` with new
   numeric unit `square_metre`. Both are own-geometry figures, subject `area`,
   Public plus `user_input`, Inferred, `your_inputs`, reliability
   `not_applicable`, and never a named-entity attribute even with Public inputs.
   A line gets its own session measurement identity; it is never passed as a
   Polygon or a protected-area identifier. Its fact geography is `area_shape`
   with an input-sensitive `area_id` in a measurement-only namespace; this
   namespace does not register an area for protected reads. Polygon identity
   binds the existing session `shape_id` and release. Both identities must
   include the trusted session binding and approved method version, and stay
   in bounded process memory with the existing session-only geometry. DAT-176
   and BE-144 define the draft input/identity boundary before activation.
   Exact geodesic algorithm, precision and independent numerical fixtures are
   absent from the pack: SC-C01 remains CONSULT and no measurement Fact may
   be emitted until its method is pinned. Source: decision 0065 item 2,
   DAT-92/DAT-93/DAT-145 and the supplied S7-T29 approved plan. This record
   settles no ellipsoid, conversion factor, area arithmetic or accuracy claim.

7. **Draft requirement rows and version boundary.** The edits accompany this
   record and are explicitly conditional on acceptance:

   | Document and stable section | Added draft IDs | Covered items |
   |---|---|---|
   | 03, new 9.3 Session coordinate facts | DAT-172 to DAT-175 | Units/metrics, semantic identity, session geography, released lineage, coverage |
   | 03, 9.2 The area record | DAT-176 | Separate measurement inputs and identity; method CONSULT |
   | 08, 8.1 Endpoints | BE-141 to BE-143 | Closed coordinate/go-to requests, responses, fixed gazetteer read and confinement |
   | 08, 8.3 Drawn shapes and case sample files | BE-144 | Separate closed line route and polygon-identifier measurement route |
   | 10, 5 The Fact chip rule | FE-155 to FE-157 | Returned coordinate chips, lifecycle/refusal, measurement chips |

   Existing DAT-90 to DAT-95, DAT-145 to DAT-149, BE-49/BE-54/BE-104,
   BE-117, FE-39/FE-41/FE-45/FE-108 and the polygon ingress remain binding.
   The new rows specify additions, not permissions to widen old requests.
   Adding closed units/geography/qualifiers invokes DAT-121 and DAT-122 after
   a first committed contract: use a new fact major and release major with
   matching producer/consumer conformance suites and DAT-123 refusal. The
   pre-first-contract exception in section 13 applies only if the lead proves
   its condition on the actual integration stack. SC-C05 asks for that evidence
   and version plan; silently extending an installed `.v1` schema is refused.
   No runtime schema, release, catalogue or migration is changed here.

8. **Review and activation stay explicit.** Acceptance of this proposal settles
   the proposed policy, not proof of a working source chain or completed task.
   SC-C01 to SC-C07 list what remains to be obtained. S7-T29 and S7-T33 keep
   their existing implementation, red/green plant, parity, bilingual, frozen
   installation and different-maker review obligations. No gate, privacy
   control, source-field requirement, test tolerance, command or library pin
   changes. No network is needed by the proposed local operations. Source:
   decision 0065 item 9, decision 0042 items 7 and 13, AGENTS.md rules 35 to 39
   and 46. This is a docs-only proposal with a strict self-review; independent
   contract approval has not been supplied.

## Alternatives refused

- **Call user coordinates Public/Observed or add a fifth provenance class.**
  Refused: DAT-91/DAT-92 already separate released Public input, user input and
  Inferred evidence. A fictitious user-input source registry row supplies no
  publisher, licence, retrieval date or hash.
- **Use a constant national geography or identity from rounded display only.**
  Refused: different selections would collide under DAT-93. A session point
  cannot pretend to be a polygon or named place.
- **Use a browser coordinate label, formatter rounding or model-supplied value.**
  Refused by rules 16 to 18 and 23, BE-104 and FE-45; map geometry is transport,
  not a display fact.
- **Use the extract box, tiles or grid-cell footprints as navigation coverage.**
  Refused: the pack already distinguishes mapped land from stored-cell
  ownership; those bounds could accept sea or refuse mapped land (document 03
  section 1.1). A wider navigation policy needs a further explicit decision.
- **Invent release tables, source hashes, retrieval dates or measurement methods.**
  Refused by DAT-94/DAT-106 and rule 46. Actual released rows must resolve;
  otherwise return no figure and keep the CONSULT open.
- **Convert every Polygon 422 into an outside-land measure.** Refused: it would
  misclassify malformed geometry and bypass the approved plan's explicit stop.
- **Treat this record as acceptance or independent approval.** Refused: status
  remains Proposed; no other-maker verdict, implementation or release was tested.

## Consequences and change triggers

The proposal supplies reviewable names and requirement definitions for the
missing contract. Once accepted and implemented against verified release
metadata, user positions can produce chips without impersonating published
locations. Measurements can use the same coverage/source chain while retaining
their separate method and ingress blockers. The new unit and session geography
require explicit version handling; no existing frozen bundle is silently widened.

A different coverage line, precision, input retention, measurement method,
source substitution, catalogue admission or version exception needs a reviewed
amendment under rule 46. Missing runtime evidence leaves a method unavailable;
it does not justify a browser fallback or an incomplete source chain.

## Sources and uncertainty

- Accepted pack authority: [decision 0065](0065-eight-everyday-capabilities-of-the-map-screen.md),
  items 2, 7 and 9; [decision 0035](0035-what-the-audience-sees-names-no-data-origin-and-the-backend-marks-it.md),
  items 1 to 4; [decision 0042](0042-the-front-end-foundation.md), items 7 and 13.
- Contract/source authority: documents 03, 04, 08, 09 and 10 at the stable
  anchors cited in each item. The [source landing page](https://data.humdata.org/dataset/cod-ab-qat)
  is the URL already recorded by document 04; it was not fetched in this task.
- Repository reading: tracked `custodian/publicdata/sources.yaml` entry
  `bnd_hdx`; frame `README.md`, `build.py::read_cached`,
  `live.py::build_live_frame`, `gazetteer.py::make_row`, `administrative_rows`
  and `reviewed_points`; `core/src/eii_core/calc/facts.py::least_real`.
- Supplied evidence: S7-T29 and S7-T33 build returns and approved plans in
  `.overnight/IN/`, quoted above. Their test results are not reproduced here.
- Proposed rather than established: coordinate method and identities, navigation
  boundary/keys, new requirement rows, method-specific release lineage and
  version handling. Unread release dates/hashes, numerical measurement rules,
  trusted seat availability, native wording and independent approval remain
  CONSULT; no implementation, current library capability or runtime pass is claimed.
