# Decision 0078: C2 bulk months by the centred median

| | |
|---|---|
| Status | Accepted, 2026-11-20 |
| Date | 2026-11-20 |
| Owner | The owner |
| Decided by | The owner, 2026-11-20, on the advisor's answer to S2 gate item 8 (OI-207) |
| Amends | Document 07 card C2 only, MTH-18 and MTH-20; implemented by TASKS.md S2-T50. |
| Purpose | Replace C2's global bulk-month baseline with a centred local baseline, retaining the superseded result in the method note. |
| Read first | Document 07 card C2; OPEN_ITEMS.md OI-207; AGENTS.md rules 16 to 19, 33, 36, 37 and 46. |

## Context

The lead's comparison of 2026-11-20, using the pinned national dated cancellation counts,
found that the global median of the C2 calendar is 305 and its triple is 915. That rule
flags 42 months holding 89.7 percent of dated cancellations, including every month of
2023 and 2024. It leaves no cancellations in the worked example's excluding figure.
The advisor's answer to S2 gate item 8 recommends the centred median with the same
factor, preserving the older result rather than discarding it. The owner approved the
change on 2026-11-20: "can do the change now".

## Decision

1. **Change C2's window only.** For each calendar month m, take the national dated
   cancellation counts from m-6 through m+6 inclusive, intersected with C2's fixed
   January 2015 through May 2025 calendar. The window therefore contains 7 to 13
   calendar months. A calendar month without dated rows contributes zero. Undated
   rows never enter a window. For an even window, the median is the arithmetic mean
   of its two middle sorted counts. A month is bulk only when its count is strictly
   greater than three times that median; equality is not bulk. Factor 3, the national
   calendar, denominator, geography, undated remainder and all other cards stay as specified.

2. **Version the method and pin the revised examples.** C2's version is `C2-v2`.
   The lead's pinned-file comparison gives these nine bulk months: 2015-12, 2017-06,
   2020-07, 2020-11, 2021-02, 2021-04, 2021-06, 2022-06 and 2024-09. They hold
   54.3 percent of dated cancellations. The three named spikes and their 43.1 percent
   share remain unchanged. Restaurants in 2024: Doha includes 318 of 2,109 (15.1 percent)
   and excludes to 283 of 2,109 (13.4 percent); Al Daayen includes 49 of 361 (13.6 percent)
   and excludes to 48 of 361 (13.3 percent). These are the lead's supplied results,
   pinned by S2-T50 for the lead's real-cache data-test run, not a worker's real-cache validation.

3. **Retain the superseded rule.** Card C2's method note keeps the global-median
   formula, its 42-month list and 89.7 percent share, explicitly marked superseded.
   They are historical method evidence, not the active excluding treatment.

4. **Require discriminating evidence.** S2-T50 uses invented core series for a level
   shift, both cut ends, even medians, a flat series, a single spike, zero months and
   invalid counts. Asymmetric mirrored fixtures pin the median and candidate flag;
   shifting either edge one month in either direction must fail. Equality must remain
   unflagged and raising only its count by one must flag it. Plant the old global
   median and non-strict comparison and record red then green results. The lead alone
   runs the real-cache data tests; another maker independently recomputes the nine
   months from the supplied national extract before approval.

## Consequences and change triggers

OI-207's method choice is CLOSED. Implementation, another-maker review and the lead's
pinned-file check remain task evidence, not consequences implied by accepting this record.
The centred baseline is retrospective: changing the source counts or extending the calendar
can change nearby flags. A different factor, calendar or window needs a new decision record.
No other method card, privacy rule, display policy or slice gate is amended.

## Sources

- The owner's approval of 2026-11-20 and the advisor's answer to S2 gate item 8 (OI-207),
  supplied with the approved S2-T50 plan and its binding design review.
- The lead's comparison of 2026-11-20, computed with `c2_national_totals`, `C2_CALENDAR`
  and `source_period` on pinned `lic_cancelled`, SHA-256
  `572398ca26eb22f750b52133b9d2d4cf11210b1f9dd60ec5dc001fbddaff6970`.
  Its supplied 125-month national aggregate extract is for independent checking and is not committed.
- [07_ECONOMIC_METHODS.md](../07_ECONOMIC_METHODS.md), **C2 Licence churn with bulk months flagged**,
  MTH-18 and MTH-20; [04_PUBLIC_DATA_PACK.md](../04_PUBLIC_DATA_PACK.md), PUB-68;
  [OPEN_ITEMS.md](../../OPEN_ITEMS.md), OI-207; [TASKS.md](../../TASKS.md), S2-T50.
