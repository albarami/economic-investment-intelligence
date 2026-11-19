# Financial-centre company register (S2-T36)

The public-page dispatch uses `fc_company_cards`, `fc_company_pane@v1` and
`fc_register_paged_capture@v1`. READ-T36 R2/R3 supplies the card positions and
Company pager controls; L-1045, L-1049 and L-1051 supply the archive and chain
boundaries. Later live pages have not been observed. The committed declaration
stays held for the lead's reviewed pin, bound and activation run. The hidden-state
names in the offline declaration are an ASSUMPTION: the saved reading omitted
hidden state. They must be confirmed before activation. No terms decision is a
hold. The tests use invented cards and an invented issuing intermediate only.

`parse.project` reconstructs only the approved scalar fields and a closed
`{shown_page, continuation}` record. It never serialises a pane or flattens an
undeclared child. Full response bytes and delivered form fields remain in memory.
The archive hashes the fragment separately; `upstream_sha256` hashes the live
response or is explicitly producer-attested for a capture. Neither hash substitutes
for the other. Responses with a changed shape fail with a closed diagnostic.

The initial request is GET. Each subsequent request is the declared Company
next pager POST, with exactly the preceding response's delivered state. Each
identity binds method, exact URL, target, empty argument, ordinal and preceding
full-response hash. Progress must match the ordinal. Repeated response hashes,
repeated/regressing pages and duplicate requests refuse. No company-detail,
other-pane, `/View`, credential or off-frame request is sent. Requests are serial
and paged POSTs are paced; no automatic POST retry is introduced.

The capture producer is `capture.produce(cache, visitor, pin, review, tool=...,
clock=..., sleep=...)`. Only the lead operates its cookie-free visitor session.
It validates the entire chain in memory before writing company-only fragments
and receipts to the documented public-cache intake `intake/fc_register/`:
`fragment-<ordinal>.json` and `capture-<ordinal>.json`. The consumer uses ordinal
filenames only to locate receipts, then verifies the identity inside each receipt,
fragment digest, current projection, progress, visitor access, tool/time, verified
TLS and the configured intermediate. No raw-response capture is accepted.
Producer receipts attest the upstream digest and progress; they are evidence from
the lead's capture procedure, not a signature or an independent remeasurement of
the discarded full response. No signature file is added.

Connection failures, HTTP 403/429/503 and successful refusal bodies attempt the
capture route. Credentials/sign-in, host/path/redirect, TLS/pin, size, schema,
integrity and every unlisted refusal are terminal. Missing/invalid captures and
failed chains record a dated failure without copying refused bytes. A live prefix
may continue with bound captures, but after capture admission only captures are
consumed through terminal; missing state never produces a live POST. Extra
receipts beyond a claimed terminal refuse. No partial table or inventory is
published. The same transition applies to the version-2 schools reader while its
one-request `capture.json` interface remains unchanged.

`names.contribution` reads the explicit `snapshot_pins.json` selection through
`page_records.selected_page`, revalidates input receipts and the complete projected
chain, and returns every company name before display filtering or deduplication.
`name_inventory.check_inventory` composes all contributions using the existing
SYN-20 normaliser. `build.build_inventory` is the refusing build entry point for
S4-T05: a collision raises `name_collision` without a company name in the error.
The task produces no release table. `EII_FC_REGISTER_FILE` remains the separate
geocoded derivative input for `pub_register_company` (document 05 Q19/S4-T02).

Nothing fetched may be committed. Terms are recorded in the registry under
`owner_decision`, decision 0026; a pending reading or basis stays a record under
decision 0059. Live receipts supply retrieval time and hashes, never invented
registry timestamps or hashes. The lead owns live activation and real-cache proof.
