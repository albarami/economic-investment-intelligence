# Typed-decision qualification set

260 labelled cases for the jobs the typed-decision gateway may do in this product
(see [decision record 0014](../../docs/decisions/0014-typed-decision-gateway.md)).
Everything here is public data or invented text. No real person, company or identifier appears.

## Files

| File | Content |
|---|---|
| `cases.json` | The 260 cases: `id`, `test`, `lang`, `state` (the only text given to the model), `question_type` (`noul` = yes/no, `choice` = pick one label), `instructions`, `criteria`, `expected`, `kind`, `note` |
| `blind_labels.json` | Two blind answer sets from general models: a small model (the baseline) and a strong model (the label check). The strong model agreed with the authors' label on all 260 cases |
| `results_2026-11-11.json` | Aggregate results of the first qualification run, with caveats and the authors' recorded doubts |

## The five tests

| Test | Cases | Question |
|---|---|---|
| `A_match` | 100 | Does this Arabic licence activity name belong to this international activity class? 40 true matches, 30 sibling-class negatives, 10 unrelated negatives, 20 legacy codes whose prefix only looks like a class |
| `A_choice` | 30 | Which of four classes does the activity belong to? |
| `B_route` | 50 | Which category does a user request belong to: `site_check`, `staffing_and_pay`, `costs_and_suppliers`, `must_decline`, `out_of_scope`? 25 English, 25 Arabic; 12 must-decline, 6 of them disguised, 3 instruction-injection attempts |
| `C_qc` | 60 | A yes/no check of a draft paragraph against listed evidence: recommends go or no-go; presents a synthetic figure as real; states the pay of a named person or company; makes an unsupported claim. 30 English, 30 Arabic |
| `D_parity` | 20 | Do the English and Arabic sentences say the same thing? |

## How it was built

- Activity names come from the open dataset of active commercial licences by municipality and
  business activity (Ministry of Commerce and Industry, on the Qatar Open Data Portal, CC BY;
  retrieved 2026-11-11). Names were tidied into standard spelling without changing their meaning.
- Class titles are the official English titles of ISIC Rev.4 (United Nations Statistics Division,
  structure file retrieved 2026-11-11).
- The code-prefix rule was not trusted when choosing true matches: every pair was read.
- Requests, drafts and sentence pairs are invented. Names of people and companies are fictional.
- Labels were written by one model and confirmed blind by a second model on all 260 cases.

## Rules for using it

1. A provider qualifies for a decision class only by reproducing the recorded result within its
   interval, on a pinned model version, with the thresholds of decision record 0014.
2. Rerun after any change of model version, rubric, language or route. Record the run beside the
   earlier ones; never overwrite a result file.
3. Continuous integration never calls a live provider. It runs the recorded provider.
4. The set is small. Treat every percentage as indicative and keep the caveats with the numbers.
