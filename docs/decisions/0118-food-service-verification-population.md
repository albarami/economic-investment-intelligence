# Decision 0118: Food-service classification and verification population

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-25 |
| Scope | S2-T06; PUB-52 and PUB-57; [document 03](../03_DATA_CONTRACTS.md) `pub_place_verification` paragraph |
| Purpose | Make place verification cover every food-service place of a showcase walk polygon, while the PUB-57 restaurant counts stay unchanged |
| Amends | [Document 04](../04_PUBLIC_DATA_PACK.md) PUB-52, the sentence on the verification population; [document 03](../03_DATA_CONTRACTS.md) the `pub_place_verification` paragraph on the required population |
| Read first | AGENTS.md rules 8 and 46; document 04 PUB-52 and PUB-57; document 03 `pub_place_verification` |

## Context and evidence

Lead ruling L-1899 item 2 answered a finding of the U3 rv1 review, which was
rejected with six findings. PUB-52 requires verification of every place in
food-service categories, but the document 03 sentence narrowed the required
population to two classes, `restaurant` and `italian_restaurant`. The lead ruled
one new closed class, `food_service`, that is verified but never counted as a
restaurant, so PUB-57 counts stay unchanged, and ruled eleven named category
labels into it. Under rule 46 the amendment is a decision record in the same
task. This is a lead ruling, not an owner answer; it is Proposed and awaits
acceptance.

## Decision

1. Add the closed category class `food_service`: a food or beverage service place
   that is not a restaurant for the PUB-57 counts. Under task ruling L-1899 item 2,
   assign this class to `bar`, `cafe`, `coffee_shop`, `food_and_drink`, `food_court`,
   `food_service`, `food_truck_stand`, `lounge`, `nightlife_venue`,
   `non_alcoholic_beverage_venue` and `smoothie_juice_bar`.
2. For PUB-52 and document 03's `pub_place_verification` paragraph, the required
   population is the sorted unique kept places in classes `restaurant`,
   `italian_restaurant` and `food_service` inside any showcase walk polygon, plus
   the explicitly supplied prepared-story ids. This leaves PUB-57 restaurant and
   Italian counts, thresholds and every refusal unchanged; unknown category
   classes still refuse with `unknown_category_class`.

## Consequences

The required verification population grows by the places of the eleven labels;
the places `build_report.json` counts, `required_verification.by_area` and
`required_verification.total`, follow that population. Places of the new class
are not restaurants for PUB-57, so restaurant and Italian counts and thresholds
do not move. A category label outside the closed classes still refuses with
`unknown_category_class`. Verification is a reviewer task; the record does not
state any verification result.

## What would change it

Moving a label into or out of `food_service`, adding a food-service class, or
counting `food_service` places toward PUB-57 needs a further decision record and
a lead or owner ruling. Resolving the prepared-story ids (OI-397) changes only the
supplied ids, not this record.

## Sources

- Lead ruling L-1899 item 2 (task ruling of the S2-T06 lane), and the U3 rv1
  review finding it answers.
- [Document 04](../04_PUBLIC_DATA_PACK.md), PUB-52 and PUB-57.
- [Document 03](../03_DATA_CONTRACTS.md), the `pub_place_verification` paragraph.
