# Decision 0049: One product for every screen size

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-16 |
| Owner | The owner |
| Decided by | The owner's relayed note of 2026-11-16 16:40 as applied by the lead's ruling L-720 |
| Amends | [TASKS.md](../../TASKS.md) (S3-T16, S3-T20, S3-T21, S6-T37, S8-T15); [docs/10_FRONTEND.md](../10_FRONTEND.md) (Layouts, FE-69, FE-73); [docs/11_DESIGN_DIRECTION.md](../11_DESIGN_DIRECTION.md) (DES-01); [docs/12_TESTING_AND_QUALITY.md](../12_TESTING_AND_QUALITY.md) (TST-90); [docs/16_DEMO_RUNBOOK.md](../16_DEMO_RUNBOOK.md); [docs/README.md](../README.md) |
| Purpose | One product, one codebase, one layout that responds to the screen: phone, tablet, normal laptop or PC, widescreen and ultrawide, and a big presentation screen or TV. |
| Read first | Decisions 0041, 0042, 0044, 0048; documents 10, 11, 12, 16. |

## Context

The owner's relayed note of 2026-11-16 16:40 specifies that the product must be dynamic and adaptable to any screen, not just the phone. It must run on phones, PCs, widescreens, big screens, or normal screens. Rulings L-720 applied this note, stating that EII must use ONE product and one codebase whose layout responds to any screen. There will never be separate phone and desktop versions. Decision 0041's phone wording is widened.

## Decision

1. **One product, one codebase.** One product, one codebase, one layout that responds to the screen: phone, tablet, normal laptop or PC, widescreen and ultrawide, and a big presentation screen or TV. There are never separate phone and desktop versions. Decision 0041 item 7's phone wording is widened, not replaced (its phone evidence stays).
2. **Named sizes.** The eight named sizes to prove are: 360x640 and 390x844 (phones, each in portrait and landscape), 768x1024 (tablet), 1366x768 and 1920x1080 (normal), 2560x1440 and 3440x1440 (wide and ultrawide), 3840x2160 (big screen). No other size and no breakpoint number is added.
3. **Display rules.** Per size: nothing overflows or hides the map's answer card; text and touch targets stay readable (big screen: larger type and controls readable from a distance; phone: one-hand reachable controls, targets of at least 44 px, the answer card as a bottom sheet); mouse and touch both work; Arabic right-to-left and English both hold at every size.
4. **Map first.** The map and the answer pair keep their roles at every size: the map answers first.
5. **Performance adapts.** Performance adapts: the shadow clock's building cap (decision 0048) and the other effects scale to the device's measured frame rate, so a phone is never frozen by a desktop-grade scene. No frame-rate or cap number is set by this record; the measurement method stays the one from decision 0048 and the slice S1 frame-rate configuration fix.
6. **Evidence and notification.** Screenshots of each named size, in both languages, go into each gate pack from the slice S3 gate on, for the owner's visual review. The lead tells the advisor when the first size matrix has run.

## Consequences

- The visual test viewports are expanded to the eight named sizes.
- Phone layout requirements are widened to explicitly include responsive behaviors for all named sizes.
- S3-T21 includes the full size matrix and its screenshots for the test lab.
- S3-T20 remote mode phone evidence is widened to all sizes.
- S3-T16 map modes controls hold at the named sizes, and the building cap scales with the measured frame rate.
- Front-end foundation tasks (decision 0042) incorporate these size rules.
- Existing requirements are updated in place or amended.

## Amended passages

- **10_FRONTEND.md:** Layouts section and FE-69 are amended to replace the breakpoints with the named sizes; FE-73 explicitly maintains 44 px targets on phones.
- **11_DESIGN_DIRECTION.md:** DES-01 is amended to reflect the eight named sizes instead of the original breakpoints.
- **12_TESTING_AND_QUALITY.md:** TST-90 is amended (stricter) to cover the eight named sizes instead of four.
- **TASKS.md:** 
  - S3-T16: Amendment line added that controls hold at the named sizes and the building cap scales with the measured frame rate.
  - S3-T20: Amendment line added that the phone evidence is widened to include the named size matrix.
  - S3-T21: Amendment line added to produce screenshots of each named size in both languages.
  - S6-T37 (Explore screen): Amendment line added to ensure layout responds to the named sizes without overflow.
  - S8-T15 (Map-first answers): Amendment line added that the map answers first at every size.
- **docs/README.md:** 0049 is added to the list of accepted records.

## Sources

- Owner-relayed note of 2026-11-16 16:40.
- Lead's ruling L-720.
