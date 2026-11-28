# Decision 0135: Private personal use, and one scoped marker in eleven source receipts

| | |
|---|---|
| Status | Accepted by the owner, 2026-11-28, under CLAUDE.md rule 46, on the owner's one condition that item 1 states the owner's own words; item 1 quotes them verbatim. Carried by a documents-only pull request with another maker's review. |
| Date | 2026-11-28 |
| Owner | The owner |
| Amends | [Decision 0034](0034-licence-questions-of-public-sources-are-answered-at-a-go-live.md) item 1, including its amendment of 2026-11-18, and the list duty that rulings L-456 and L-997 derived from it |
| Purpose | Record that the system is for the owner's personal use only, end the go-live licence list, and let eleven named source receipts carry one fixed marker without weakening any receipt check. |
| Read first | Decision 0034 item 1; [decision 0059](0059-publisher-terms-are-a-record-not-a-gate.md); OWNER_RULES 13 and 52; rulings L-207, L-456, L-997, L-2579 item 1 and L-2587 |

## Context

1. **The present contract.** On main `66c0ea75`, `sidecar_for` in `custodian/src/eii_custodian/publicdata/fetch/receipts.py` copies the registry entry's `licence_id` into the receipt, and `receipt_disagreement` in `custodian/src/eii_custodian/publicdata/completeness.py` compares that receipt field exactly with the value the writer expects. Ten of the eleven keys below carry `not_stated` in the registry; the producer price index entry carries `CC-BY-4.0` with its recorded source wording.
2. **The replay.** The lead's replay of the receipts on 2026-11-27 refused ten of these keys for `licence_id` (the registry value is set and the receipt value is empty). Writing one marker into all eleven receipts would fail the existing literal comparison, and changing the registry values would discard the distinction between a stated and an unstated identifier.

## Decision

1. **Personal use.** The owner's words, 2026-11-28: “This system is for my personal use only. I will not open it to the public. Licences and go-live are not to be considered, and there is no go-live list.” The project therefore keeps no go-live list, and licences and go-live are not considered for source terms. This subject is not raised as a finding, a gate item, a blocker or a question to the owner. Evidence of how the system was built stays as history, and source provenance is still recorded in full.
2. **The marker.** For the eleven source receipts of item 6, `licence_id` holds the exact value `private_personal_use_not_assessed`. It describes the use of this project, not the source. The publisher's own metadata and each registry entry's identifier, including any stated identifier, are kept with their source and date. Source coverage is unchanged.
3. **The receipt contract.** In the private receipt format, the writer and the validator apply the marker to these eleven keys only. They still bind the registry's original identifier exactly, in a checked `registry_licence_id` beside the marker. Historical receipts keep validating by their original format. The marker alone never authenticates a source. Every other key keeps its existing receipt contract.
4. **The migration.** The eleven receipts are reissued from the verified bytes already held, through the existing immutable publication and selection mechanism. Each original body hash, byte count, source identity, publisher, acquisition time, address, period, table declaration and lineage is kept. The metadata migration is recorded separately. A changed receipt has its own digest. Historical receipts and their pins stay reproducible.
5. **Checks and proofs.** Every other receipt check, access control, privacy rule, tolerance and independent review stays. The implementation proves that the marker is accepted for all eleven keys and refused for any other key. An altered registry identifier, source hash, period and table declaration are each planted alone and each refused for its own reason. The eleven are confirmed through the real selected receipts on a stated main revision, and the time of the first verified 11/11 result is reported. The three existing refusals about a period, a table declaration and an output-table mismatch keep their own work.
6. **The eleven keys.**
   - `gis_address`
   - `gis_context`
   - `gis_land_price`
   - `gis_landmarks`
   - `gis_locator`
   - `gis_parcels`
   - `gis_phcc`
   - `gis_poi_comm`
   - `gis_rail`
   - `gis_zoning`
   - `price_ext/producer-price-index-ppi`

## Acceptance

The owner accepted this record on 2026-11-28, on the condition that it says what the owner said; item 1 carries the owner's three sentences verbatim, and an earlier draft wording of item 1 is never installed. A documents-only pull request with another maker's review carries this record. The owner authorised the scoped implementation and the real replay of the eleven held receipts; the implementation is tested and reviewed by a different maker before the replay, and no check is weakened.

## Sources

- Decision 0034 item 1 and decision 0059, as merged on main.
- The owner's decision of 2026-11-28, relayed to the lead and applied as ruling L-2587.
- The owner's acceptance of 2026-11-28, relayed to the lead and applied as ruling L-2591.
