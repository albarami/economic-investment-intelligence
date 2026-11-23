# Decision 0103: The model signer may acknowledge the derived acknowledgement rows under the same seeded audit

| | |
|---|---|
| Status | Accepted by the owner, 2026-11-23 ("option b", relayed by the advisor in note owner-relayed-20261123-1434) |
| Date | 2026-11-23 |
| Owner | The owner |
| Decided by | The owner's word "option b", relayed by the advisor in note owner-relayed-20261123-1434 |
| Amends | [Decision 0075](0075-activity-mappings-signed-by-model-review.md) item 3 (its admission of model-signed decisions); the keyed-procedure paragraph of [scripts/spine_triage.md](../../scripts/spine_triage.md) (the acknowledgement sentence) |
| Purpose | Let the model signer acknowledge the derived acknowledgement rows of the activity spine queue under the same seeded audit as its mapped and rejected rows |
| Read first | [Decision 0075](0075-activity-mappings-signed-by-model-review.md); OPEN_ITEMS.md item OI-203; `scripts/spine_review.py` `decision_rows`; [decision 0102](0102-register-projection-run-in-rule-44.md) (the note-citation form) |

## Context

The activity spine queue holds 296 rows: 271 eligible codes the model signer judges, and 25 derived acknowledgement rows (18 `not_mappable_legacy` / `legacy_code_length` and 7 `not_mappable_invalid_prefix` / `invalid_isic_prefix`). Before this record, an acknowledgement row admitted only a person's role; a model-like role refused with `acknowledgement_role_invalid`. The owner was offered the options (a) keep the person-only rule and (b) let the model signer acknowledge those rows under the same seeded audit, and answered with the word "option b".

## Decision

1. **Admission.** In `scripts/spine_review.py` `decision_rows`, an acknowledgement row (a queue code that is not eligible) is admitted in exactly two cases: (a) a person's role, the existing path, unchanged; (b) a role byte-equal to the batch's signer `role`. Every other model-like role refuses with `acknowledgement_role_invalid`. A changed status, reason or non-empty class refuses with `acknowledgement_decision_invalid`, whatever the role.
2. **Audit population.** The model-signed acknowledgement rows join the population the seeded audit draws over: `draw_record`, `audit_record`, assembly and the audit packet. The seed derivation (`derived_audit_seed`) is unchanged; only the population it draws over grows. A drawn acknowledgement code appears in `audit_packet.json` with its code, its name and its derived status, reason and class.
3. **Spine build.** A model-signed acknowledgement row must be a member of exactly one bound, zero-error audited batch, exactly like a model-signed `mapped` or `not_mappable_rejected` row, with the same refusals. A malformed model role on such a row refuses. A person-signed acknowledgement row keeps its existing path. `class_members` and the mapped-row rules are unchanged. A batch record's codes may hold legacy six-digit codes.
4. **Refusal chain.** A historical refused batch holding acknowledgement rows remains verifiable in the committed refusal archive; its rows keep their own code lengths.

## Consequences and limits

The acknowledgement sentence of the keyed-procedure text of `scripts/spine_triage.md` is updated. OI-203 stays open: nothing here signs the real queue, and no box is ticked by this record. The person path and every refusal of decision 0075 are unchanged; no new data source, subject or provenance class is introduced, and no eligible-row rule moves.

## Sources

- The owner's word "option b", relayed by the advisor in note owner-relayed-20261123-1434.
- [Decision 0075](0075-activity-mappings-signed-by-model-review.md) items 3 and 4.
- OPEN_ITEMS.md item OI-203 and its rounds S2-P60 to S2-P63.
- `scripts/spine_review.py` (`decision_rows`, `draw_audit`), `scripts/spine_refusals.py` (`refusal_rows`) and `custodian/src/eii_custodian/publicdata/review/activity.py` (`_require_model_audits`, `_audit_codes`).
