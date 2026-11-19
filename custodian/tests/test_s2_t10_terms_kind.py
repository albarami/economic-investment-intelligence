"""Benchmark receipts name a terms-digest kind distinct from visible text."""

import hashlib
import json

import pytest


def test_benchmark_receipt_names_recorded_terms(tmp_path):
    from eii_custodian.publicdata.benchmarks.contracts import read_selected
    from eii_custodian.publicdata.fetch.terms_text import FINGERPRINT_VISIBLE_TEXT

    from .test_benchmarks_fetch import benchmark_release

    source, selected, _manifest = benchmark_release(tmp_path)
    released = read_selected(tmp_path, source, selected)
    kind = released.receipt.get("terms_fingerprint")
    assert kind != FINGERPRINT_VISIBLE_TEXT
    assert kind == "recorded_terms"


def test_visible_text_kind_on_a_benchmark_receipt_is_refused(tmp_path):
    from eii_custodian.publicdata.benchmarks.contracts import read_selected
    from eii_custodian.publicdata.fetch.terms_text import FINGERPRINT_VISIBLE_TEXT

    from .test_benchmarks_fetch import benchmark_release

    source, _selected, manifest = benchmark_release(tmp_path)
    manifest["receipt"]["terms_fingerprint"] = FINGERPRINT_VISIBLE_TEXT
    body = json.dumps(manifest).encode()
    digest = hashlib.sha256(body).hexdigest()
    (tmp_path / source / f"{digest}.manifest.json").write_bytes(body)
    with pytest.raises(ValueError, match=r"^terms_fingerprint$"):
        read_selected(tmp_path, source, digest)
