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

## Offline requalification command (S1-T08)

`uv run --locked python evals/typed_decisions/requalify.py --provider none`
visits the complete case set without a key or network. Its aggregate and gateway
records are made under a standard-library temporary repository and removed when
the command finishes. `--provider recorded --fixtures SYNTHETIC_REPLAY.json`
uses an explicitly supplied synthetic replay fixture in the gateway's existing
format; tests generate one from the closed expected labels. It is not measured
provider performance. The tests use temporary roots for both offline forms.

The harness sends only state, instructions and labelled criteria from `cases.json`.
Expected answers and authors' notes are never sent. Activity choice labels become
`isic-<class>` and are decoded in the aggregate; descriptions remain in the rubric.
The unchanged gateway supplies both hash-derived option orders, acceptance and
memoisation. The aggregate separates two blocks:
- `raw_answers` counts the answer in the first hash-derived order (one answer for
  yes/no), over cases answered by the configured model, independently of scores or second-order agreement. A first reply naming another model or no model is excluded from both the overall and per-test totals; its observation remains in the case rows.
  Each per-test row places current counts beside admitted counts without judgement.
- `gateway_accepted` keeps the gateway's both-order agreement and thresholds,
  over all cases including unavailable and disabled decisions.
  Its case fields are exactly `id`, `test`, `label`, `accepted`, `correct`,
  `outcome` and `orders`.

The one admitted overall interval is read unchanged from the admitted provider
arm. `admitted_measurement_reproduced` is true exactly for a keyed run whose
responses all report the pinned admitted model identifier, whose first answers
cover the full admitted set, and whose unrounded raw-answer rate lies inside
that interval, including its bounds. `reproduction_reason` is one of
`not_keyed`, `model_family_mismatch`, `incomplete_answers`,
`outside_stated_interval` or `reproduced`. No per-test interval is invented.
The result names the protocol differences: hash-derived rather than
original option orders, activity labels sent with the prefix, and an admitted
run made before the gateway existed, and the adapter cutting the yes/no label
at a weight of 0.5. This comparison implements the lead's C2
ruling; it does not supply fresh human ground truth (OI-15).

The aggregate also reports `model_replies`: counts of replies naming the configured model (`pinned`) and replies naming another model or none (`other_or_missing`), across both choice orders. A missing second response is no reply and adds no count. Closed gateway records do not change (L-99).

Counts, percent rates and Wilson intervals are computed by tested code. Each
raw row records response model identifiers and the first valid answer observed
during this run, even if the second order is unavailable. A gateway memo hit
supplies no new response observations and cannot establish a fresh reproduction.
The admitted aggregate and any existing output are never overwritten.
Per-case gateway records remain in `evals/typed_decisions/runs/` under the run
root; offline aggregates are never committed as measurements.

Identity covers provider, model, rubric digest, case-byte digest, thresholds and
route digest. The endpoint contributes only a hash and changes the memo context.
The final identity uses the validated gateway record; raw rows additionally
retain each response's reported model, including a differing second response.
Changed identity prints `requalify` and exits 2; a matching configured identity
exits 0. The verified route is stored only as its digest; another endpoint
triggers route review.
That route review and the C2 reproduction flag are separate evidence.

The keyed command, **run by the lead alone under OI-18**, is:

```sh
: "${JEV_PRO_API_KEY:?Set in the process environment}"
: "${EII_QUALIFICATION_ENDPOINT:?Set in the process environment}"
uv run --locked python evals/typed_decisions/requalify.py --provider jev --token-cap 2000000 --authorised --endpoint "$EII_QUALIFICATION_ENDPOINT"
```

The endpoint must be the owner's explicitly supplied, credential-free route;
the repository retains only its digest. Both variables come from the process
environment; no file named `.env` is read. Missing authorisation, missing key,
invalid cap or planned use above the cap produces a fixed `REFUSED` reason and
exit 3 before gateway construction, adapter import, DNS or writes. The planned
reserve is the admitted mean tokens multiplied by planned option-order calls,
rounded upwards; it is a planning estimate, not a guaranteed maximum.
The adapter's encoded-body byte guard precedes each call; actual accounting
remains the unchanged gateway's responsibility after the call.

A `jev` run must be fresh: before the first call, any existing record with one
of this run's memo keys yields `REFUSED: earlier records exist` and exit 3.
The harness never deletes records. On the first gateway `ERROR` or `UNAVAILABLE`,
it sends no further case, writes no aggregate, prints the following line and
exits 4 (HTTP status, transport exception class, `invalid response` or `model drift`):

```text
STOPPED: provider failure at case <id>; status <status>; calls made <n>; tokens used <n>
```

No error body, headers, address or key enter that diagnostic. There is no retry;
a timeout leaves the outcome uncertain. `none` and `recorded` retain their
existing behaviour. For a completed `jev` run, `calls_made` counts provider
attempts and `tokens_used` sums returned input and output token counts alongside
the existing result fields. An adapter refusal before transport is not a call.

Before the first gateway call the command's first line still prints provider,
model, digests, thresholds, case count, planned calls, planned tokens and cap.
A completed run writes a fresh timestamped aggregate beside the admitted file,
keeps gateway records under `runs/`, and prints `match` (exit 0) or `requalify`
(exit 2), followed by `live run recorded; reproduction_reason=<reason>`.
Refusal is exit 3; provider failure is exit 4. Ruling L-69 settles the earlier
contradiction: a completed run reports `requalify`, exit 2, for another endpoint,
rubric, case set or thresholds. A reply naming another model is rejected by the
unchanged gateway as `ERROR` and stops the run with exit 4 and `model drift`.
Requalification with a decision on the pin is required before another keyed run.

The owner allowed the keyed run on 2026-11-13 under OI-18: the run cap is
5 million tokens for one run and 20 million for the build; rotate the key before go-live
and immediately on exposure; evaluate only public or invented cases.
CI and the builder never perform that run. The completed run is recorded below;
fresh human ground truth remains open under OI-15. Nothing a user types live
goes to the provider (decision record 0014, item 7).

## Keyed run of 2026-11-13

- Result: [results_2026-11-13T04-19-15-163796.json](results_2026-11-13T04-19-15-163796.json).
- Provider: `jev`; model: `jev-1.14.0`.
- Reply model identifiers: 340 named the pinned model; 0 named another model or none. Replies outside the pin are excluded from the result (L-99).
- Case digest: `1e728d77bc99e2bfad09efb980a5bf147e7f7c52c0404dfdb747498a8da77d76`.
- Rubric digest: `032d1563aedb1dad27fae2e444b8bc6780797251750b3015013f955600086ebc`.
- Route digest: `d4207e9f26433022974df0ae94512b2846baccef21b1d9e2749bbeba8cc01159`.
- Thresholds: high 0.9; low 0.1.
- Route status: `match`; reproduction reason: `reproduced`.
- First answers: 250 of 260, 96.15384615384616%; interval [93.1, 97.9]; admitted: 248 of 260, 95.4%; stated interval [92.1, 97.3].
- A_choice: current 29 of 30; admitted 28 of 30.
- A_match: current 94 of 100; admitted 94 of 100.
- B_route: current 50 of 50; admitted 50 of 50.
- C_qc: current 58 of 60; admitted 57 of 60.
- D_parity: current 19 of 20; admitted 19 of 20.
- Gateway outcomes: DECIDED 176; BELOW_THRESHOLD 84.
- Wrong decided cases: A-M-048, A-M-049.
- Calls made: 340; tokens used: 147969.
- Option orders are hash-derived, not the original order.
- Activity labels are sent with the isic- prefix.
- The admitted run was made before the gateway existed.
- The adapter cuts the yes/no label at a weight of 0.5.

Figures and digests above are copied from the linked result, with the admitted overall figure from `results_2026-11-11.json`. Run records under `runs/` are not committed.
The committed aggregate omits each case's memo key because it identifies an uncommitted run record and supplies no task-criterion evidence (OI-117; ruling L-75).
Aggregate SHA-256 before conversion: `80c34464b1883061ce68391e2af4b974ab258e4a8b52190ee5b6a63dad768c72`; after conversion: `842ca362ccc9f97408904e824a809e83947ed556ffb66c3079c6da20bbfdcf5f`.
The lead made this run under the owner's answer to OI-18, on public and invented cases only (task brief, keyed-run record). This records this set and this version only; fresh human qualification remains OI-15.
