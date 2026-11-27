# 0120 — A year range is not a phone shape

| | |
|---|---|
| Status | Accepted by the owner, 2026-11-27 ("ACCEPT 0116, 0117, 0118, 0120, 0121 and 0122", relayed by the advisor in note owner-relayed-20261127-060429), on the lead's confirmation (ruling L-2272) that its review still stands on main `bc9bb749`: the record's text is byte-equal to its text at `247c6dc` (S2-DREC.fx1), which S2-DREC.cf2 (Cursor, grok-4.7-high, a maker other than the builders) CONFIRMED |
| Date | 2026-11-25 |
| Owner | Project owner |
| Amends | Only the telephone-shape reading of a year range in decision 0029 item 5. |
| Purpose | Admit exact ascending ASCII year ranges while retaining the existing contact refusals. |
| Read first | [Decision 0029](0029-the-agencys-pages-as-verbatim-quotations.md) item 5; [OI-414](../../OPEN_ITEMS.md#oi-414--three-agency-pages-have-no-pub_investqa_page-row); [S2-T39](../../TASKS.md#s2-t39--the-investment-sources-in-full) box 1. |

## Context

OI-414 records three refusals among 54 saved agency pages: two pages contain
published e-mail shapes; one contains an ASCII-hyphen year range read as a
telephone shape. Its other-language counterpart uses an en dash and passes.
These counts come from that recorded lead rerun; no saved page is read or
copied into this change.

The owner chose option B on 2026-11-25, in the exact words "option b",
as relayed in the S2-T39B b1 task brief. This record proposes the year-range
part of that choice; [decision 0121](0121-agency-pages-box-1-covers-pages-that-pass-the-release-check.md)
records the acceptance scope.

## Decision

1. In the telephone-shape test only, exempt a complete match that is exactly
   two four-digit ASCII years joined by one ASCII hyphen. Each year is `19NN`
   or `20NN`, where `N` is an ASCII digit, and the second is not earlier than
   the first. Equal years are allowed. The exception applies to the whole
   existing match, never a substring of a longer match.
2. Every other telephone match keeps the existing rule: seven to fifteen
   Unicode decimal digits in the existing digit-group shape refuse as
   `page_contact_shape`. A plus prefix, additional digit groups, parentheses,
   a space separator, reversed years, non-ASCII digits or an out-of-century
   year do not qualify for the exception.
3. The e-mail test, bare eight- or eleven-digit-run test and release-token
   test are unchanged. A refused page still has no quotation row; its typed
   record and link remain. Nothing is redacted, and no other part of
   decision 0029 changes.

## Evidence and cases

Invented fixtures exercise the existing extractor and release refusal codes.
Ascending ASCII-hyphen ranges pass unchanged in Arabic and English text,
including equal years and century boundaries; the en-dash form still passes.
An eight-digit non-year number split by a hyphen, plus-prefixed country-code
groups, parenthesized groups, a year range followed by more groups, reversed
years and years joined by a space each refuse as `page_contact_shape`.
Additional cases cover non-ASCII digits, outside-century years and a separate
phone before or after an allowed range. A property-based digit-group
generator compares the old matcher with an independent year oracle: the
only newly admitted old-rule contact matches are those of item 1.

Commands, red/green exits and the exception-removal plant are recorded in
[PROGRESS.md](../../PROGRESS.md#s2-t39b-b1--year-range-contact-reading--2026-11-25).
Invented fixtures establish no real-page release coverage.

## Consequences

The year-range page of OI-414 is expected to pass on the lead's next real
rerun. The two e-mail pages remain refused. No evidence flag or acceptance
box is changed by this proposal.

Residual risk: a real telephone-shaped number whose whole match is two
four-digit groups, each `19NN` or `20NN`, joined by one ASCII hyphen with
the second not earlier than the first, is now admitted, not refused. Every
other telephone shape, including any such pair with a plus sign, a space,
a parenthesis or a further digit group, still refuses as
`page_contact_shape`. The release check never claimed to find every
contact. Here the residual is limited to this single exact shape.

## What would change this decision

A planted non-year contact admitted by this exception, a changed source
shape requiring a different rule, or a further owner decision requires a
reviewed amendment with its own negative cases. This proposal does not
authorize exemptions for any further contact shape.
