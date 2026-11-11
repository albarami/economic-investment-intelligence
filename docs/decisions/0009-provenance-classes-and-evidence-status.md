# 0009 — Provenance classes and evidence status

| | |
|---|---|
| Status | Accepted, 2026-11-11 |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Record why every fact carries two separate labels, where its data comes from and how the answer uses it, and how a mixed figure is marked. |
| Read first | [02_ARCHITECTURE.md](../02_ARCHITECTURE.md), [03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md) |

## Context

- One screen mixes three kinds of numbers: real public figures, synthetic stand-ins and simulated outputs. A fourth case is a figure that the privacy rules withhold.
- An answer also has a logical structure: what was observed, what is inferred from it, and what is still to test.
- An earlier design mixed the two ideas. Its tool statuses included "SIMULATED" and "SYNTHETIC" beside "OK" and "NO_DATA", so a status said both how a call ended and where data came from.

## Decision

1. Two axes, never merged. Provenance says where the data comes from: `public`, `synthetic`, `simulated` or `suppressed`. Evidence status says how the answer uses it: `observed`, `inferred` or `still_to_test`.
2. Words on screen. Provenance: Public, Synthetic, Simulated, Suppressed (Arabic proposals, pending native review: عام · اصطناعي · محاكاة · محجوب). Evidence status has exactly three values: Observed, Inferred, Still to test (Arabic proposals, pending native review: مرصود · مستنتج · يحتاج إلى اختبار). "Not measured" is a coverage label meaning the person has no pay in the wage records; it is shown from coverage metadata, never as an evidence status and never as zero ([03_DATA_CONTRACTS.md](../03_DATA_CONTRACTS.md)).
3. The least-real rule is computed in code. Public is more real than Synthetic, which is more real than Simulated. A composite shows the least-real class of its inputs on its chip and lists every input class in the evidence drawer.
4. A figure computed from the user's own inputs is `inferred`, carries a "your inputs" tag, and is never stored in the release.
5. Provenance is carried by texture and line style as well as by the word, never by colour alone: solid for Public, dotted for Synthetic, moving dashes for Simulated, grey hatch with a lock for Suppressed.
6. Tool status is a third and separate thing: `OK`, `SUPPRESSED`, `NO_DATA`, `OUT_OF_SCOPE`.

## Evidence

- Minister-impact judge (2026-11-11): keep the two axes separate; "Observed" must never read as "real" when the figure is Synthetic.
- Engineering judge (2026-11-11): one mark per number is easier to read on a wall screen than two, and listing every input in the drawer hides nothing. This is the origin of the least-real rule.
- Feasibility judge (2026-11-11): a synthetic or simulated number mistaken for a fact about a real place is among the outcomes most likely to make the audience refuse the product.
- The master design (2026-11-11) pins the fact fields, the two word lists and the four marks, and requires the least-real rule to be computed in code (capability M5).
- These are design judgements. No user test of the marks has been run; the design audit of slice S3 and the visual tests are the first checks.

## Consequences

- The fact object carries `provenance`, `input_classes` and `evidence_status` as separate fields.
- The class is never asserted by the model and never chosen by the front end. One function in the shared library computes it.
- A Synthetic count read through an area built with simulated speed factors is Simulated.
- Exports, screenshots and the briefing pack inherit the marks.
- Displays that wash out colour, and viewers who do not see it, still tell the classes apart.

## What would change this decision

- Real feeds. Protected statistics from real records fit none of the four classes, so a fifth class and a new record would be needed. "Synthetic" must not be relabelled. This is an inference of this record, not a decision of the master design.
- Native Arabic review changing the Arabic words (open item OI-09). The words change; the axes do not.
- The owner's decision on the label for live ledger rows (open item OI-08), which fit the four classes poorly.

## Open questions and assumptions

- OI-08: label for live ledger rows on the oversight seat. Default: tagged "this session"; seeded history is marked Synthetic.
- OI-09: native Arabic reviewer for all prepared strings.
- This record makes no ASSUMPTION beyond the inference marked above.

## Sources

- Master design, fact object and interface vocabulary (project record held by the owner, 2026-11-11).
- EII minister-impact judgement, engineering-and-delivery-risk judgement and feasibility-and-cost judgement, 2026-11-11 (project records held by the owner).
