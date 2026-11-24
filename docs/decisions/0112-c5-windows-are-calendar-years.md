# 0112 — C5's two windows are calendar years

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-24 |
| Owner | The owner |
| Amends | Document 07 section "C5 Customs supplier lens", its **Formula** window sentence and its trend sentence |
| Purpose | Give the C5 window one reading that the allowed card sentence, the worked example and the two customs tables all support, so the S2-T09 generation configuration can bind its window before the live build |
| Read first | Document 07 sections "C5 Customs supplier lens" and MTH-03, MTH-04 and MTH-30; [CLAUDE.md](../../CLAUDE.md) rules 16, 25 and 46; open item OI-283 |

## Context

The C5 **Formula** says "window of the latest 12 complete months in the
release" and compares the latest twelve months with the twelve before them.
The C5 **Inputs** give the customs imports in two tables of different
widths: 2025–2026 at twelve digits and 2019–2024 at eight digits. The C5
allowed sentence and its worked example name a calendar year ("In 2025, …",
"imports 2025"). The configuration validator of S2-T09 fixes the earlier
window to the calendar year 2024 and accepts any twelve consecutive months of
2025–2026 as the later window, and the pin producer reads the earlier window
only from the eight-digit table and the later one only from the
twelve-digit table.

The selected twelve-digit snapshot of the release now holds months of 2026.
Read literally, "the latest 12 complete months" then ends in 2026, the
earlier twelve months straddle both tables at two digit widths, and the
allowed sentence's "In 2025" no longer names the window. Document 07 does
not say which reading holds.

## Decision

1. **Both windows are calendar years.** The later window is the latest
   complete calendar year in the release; the earlier window is the calendar
   year before it. In version 1 they are 2025 (twelve-digit table) and 2024
   (eight-digit table).
2. **Formula wording.** In document 07 "C5 Customs supplier lens", the
   window sentence reads "window of the latest complete calendar year in the
   release", and the trend compares that year with the calendar year before
   it; the trend's `NO_DATA` rule is unchanged.
3. **What stays.** The validator's fixed 2024 earlier window, the producer's
   two-table reading, MTH-30's per-line treatment, the allowed and forbidden
   sentences, and every check stay unchanged. No guard is relaxed.
4. **Months after the latest complete year.** Months of a later, incomplete
   year in the release are not part of either window. They are not dropped
   from the release; they stay in the customs table and its other uses.
5. **Binding.** The S2-T09 generation configuration records `latest_months`
   as 2025-01 to 2025-12 under this record, before the live build, because
   that file enters the live build's fetch fingerprint.

## Consequences

- The C5 card's numbers and its allowed sentence name the same year.
- The card does not show the two months of 2026 in its window; a rolling
  window that included them would need an earlier window built across the
  eight- and twelve-digit tables, which the producer cannot build today and
  which would change a gate guard. That alternative is recorded, not built.

## Sources

Document 07 sections "C5 Customs supplier lens" and MTH-03; the S2-T09
configuration validator and pin producer named in OI-283; the month count of
the selected twelve-digit customs snapshot, read in the lead's shell.
