"""A standalone benchmark read hides the date-parser diagnostic."""

import hashlib
import json

import pytest


def test_unparseable_retrieval_date_uses_the_fixed_reason(tmp_path):
    from eii_custodian.publicdata.benchmarks.contracts import read_selected

    from .test_benchmarks_fetch import benchmark_release

    source, _selected, manifest = benchmark_release(tmp_path)
    manifest["receipt"]["retrieved_utc"] = "not-a-date"
    body = json.dumps(manifest).encode()
    digest = hashlib.sha256(body).hexdigest()
    (tmp_path / source / f"{digest}.manifest.json").write_bytes(body)
    with pytest.raises(ValueError) as caught:
        read_selected(tmp_path, source, digest)
    assert str(caught.value) == "retrieval_date"
    assert "format" not in str(caught.value)
