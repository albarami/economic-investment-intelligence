"""Closed identity of the source that has its own acquisition run (decision 0084)."""

from .registry import Entry

OWN_RUN_KEYS = frozenset({"tenders_pub"})
OWN_RUN_REASON = "own_run_pending"
OWN_RUN_CAVEAT = "tender_fetch_own_run"
# Until the pinned pick-up of decision 0084 item 3 is built, any tender pin in
# the main cache refuses; it never downgrades to the pending absence.
OWN_RUN_PIN_REFUSAL = "own_run_pickup_unbuilt"


def is_own_run_entry(entry: Entry) -> bool:
    return (
        entry.key in OWN_RUN_KEYS
        and entry.source_id == "tenders_pub"
        and entry.kind == "paged_cards"
        and entry.skip_reason == ""
    )
