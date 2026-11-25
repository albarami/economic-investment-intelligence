# 0118 — Food-service classification and verification population

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-25 |
| Scope | S2-T06; PUB-52 and PUB-57 |

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
