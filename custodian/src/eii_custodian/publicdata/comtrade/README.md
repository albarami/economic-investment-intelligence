# UN Comtrade fetch

This adapter is the keyed provider interface of decision 0040 item 2. The committed registry row is unconfirmed: terms are still "terms to be read", hosts are not on the allow-list, and `skip_reason` is `metadata_unconfirmed`.

## What the lead checks before any fetch

1. The source's own landing page, documentation and terms: publisher, dataset title, the publisher's terms in the publisher's words, the basis, the date read, the page hash, the version and the free tier.
2. Daily allowance, its scope, reset and exhaustion signal; keyed and public per-call limits; endpoint families; filter meaning; schema; units; flags; source host and redirect hosts.
3. The closed selection: years, frequencies, one classification revision aligned with S2-T24, flows, chapters and the mirror partners. The selection is a registry value. It is not chosen from a ranking of fetched rows.
4. Count bounds and the last periods, checked equal to the policy.

Until that reading is recorded, activation refuses the fetch.

## Confirmed mapping

None. Field names in the tests are invented. The release columns are the contract in document 03, section 7.3, table `pub_comtrade_trade`. A production row copies each dimension from the response through the closed schema mapping. A dimension the answer does not hold is refused. A null source measure stays null only when the answer states null. The mapping stays unreviewed, and activation refuses, until the lead records the source schema. Measure and unit pairs come only from the reviewed mapping. No currency is converted.

## Limits

Budgets and record caps are fields of `comtrade_policy`, not constants in code. A response whose count equals the cap is split again on the next subdivision field. An indivisible exact cap is unresolved truncation and does not write a complete manifest. The secondary slot is used only after the primary daily counter reaches the recorded allowance and the exhaustion signal is `calls_reached`. There is no Deliver, Bulk or Async family, and the run returns instead of sleeping into the next day. Resume reads `data/public_cache/un_comtrade/state.json`.

## Credentials

Only `scripts/commands/build_public.py` can read the two environment names, and only when that command itself opens the connection. It passes an accessor that reads the selected slot's variable at the moment of that slot's permitted request. A skipped row, a failed activation and an injected transport read neither name. The header name is `Ocp-Apim-Subscription-Key`. Tests pass an invented marker in memory and never open a socket. There is no automatic retry: a throttle stops the run with the ledger written, and the next permitted run continues.

## Failure text

A failure names `un_comtrade`, the failed check, a canonical URL built from the allow-listed host and path and the closed selectors, and an endpoint id. Provider error text, redirect targets and header echoes are not written.
