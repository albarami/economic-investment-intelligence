# Decision 0132: Short register card text meets the content scan as whole tokens

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-27 |
| Scope | Slice S2, task S2-T49; register metadata card-content matching only |
| Amends | Decision 0124 item 5 for content-match length only |
| Read first | Decision 0124 item 5; decision 0131 false-refusal clause; document 03, **Register file projections (S2-T49)** |

## Reason and bounded ruling

The lead's real-shell register projection refused with `register_content_egress`
before any bundle was written. The counts-only probe, with values never printed,
found refusals from card text so short that it occurs inside ordinary approved
metadata words. Genuine cards can have short English names, including a single
letter or punctuation only. Substring matching then falsely refuses ordinary
manifest and report strings. Decision 0131 requires fixing a false refusal with
review by a different maker, never switching off the scan; every real company
must stay in the release. This record contains no real register values.

## Matching rule

1. Card text remains each non-empty `name_en`, `name_ar` and
   `registered_address`. Its length here counts only characters for which
   Python `str.isalnum()` is true.
2. Text with four or more such characters retains case-sensitive substring
   matching, unchanged.
3. Text with one to three such characters matches only when its token sequence
   occurs consecutively in the scanned string, case-sensitively. Tokens are
   maximal Unicode Python `re` `\w` runs: letters, digits and underscore.
   Spaces, hyphens, dots and every other non-word character separate tokens.
   Thus `pub` does not match `pub_register_company`, and `a b` does not match
   `a_b` or `a x b`, but does match `x a-b`.
4. Text with no letters or digits matches only an exactly equal string.
5. One small matcher serves the string branch of `scan_content`. A frozen
   structure prepares short token sequences once per build; recursive scans
   reuse it. Registration/licence token rules, digit runs, prefixes, typed
   formats, decision 0124 exact checks and their order, table value scans,
   bundle loading, attack sizes and tolerances remain unchanged.

## Plants and evidence

Invented `e`, `re`, `pub` and `-` cards first fail on the unchanged build with
`register_content_egress`; `Q`, `QZ` and `a b` remain passing controls.
One-input unlisted-leaf plants refuse each short whole-token name. A
four-letter invented name inside a longer word still refuses. Punctuation
inside a longer leaf passes; an equal whole leaf refuses. Every negative
asserts the exact reason. Existing decision 0124 label and schema-key plants
retain their reasons unchanged. Unicode property tests check the short and
punctuation relations and the long substring relation against independent
oracles. The short-token and punctuation guards are deleted separately and
restored by byte comparison; commands and exits are in PROGRESS.md.

## Limits and admission

A card text with four or more letters or digits that occurs inside an approved
metadata word still refuses. It fails closed and goes to review; it is never
absorbed. A short name may now occur inside a longer token without refusal;
a punctuation-only name may occur inside a longer string without refusal.
Short multi-token names ignore separator spelling but require consecutive
whole tokens. Case-sensitive behavior and existing exact-field exemptions
remain. No normalization, case folding or metadata exemption is added.

Different-maker review and the lead's real-register replay remain required;
these offline invented tests do not establish a real release or pass a gate.
Sources: S2-REGSHORT.b2 brief, ruling L-2199 and round-two ruling L-2201;
decision 0124 item 5; decision 0131 false-refusal clause.
