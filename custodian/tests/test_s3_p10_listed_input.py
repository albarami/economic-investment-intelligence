"""S3-P10 round 2 (L-1509): the release build lists the register file's hash.

Invented envelopes and invented hashes only. The hash reaches the release
document as a computed producer argument; the spec cannot carry one.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import public_release_fixture as fixture
import pytest
from public_assembly_fixture import approve, dump, inputs

from eii_core.manifest import canonical_json
from eii_custodian.release import producer
from eii_custodian.release.assembly import build, read_assembly
from eii_custodian.release.public_only import WriterRefusal, write_public_only
from eii_product.store.release_check import check_release, manifest_rows

DIGEST = hashlib.sha256(b"INVENTED-register-bytes").hexdigest()
ENTRY = {"name": "fc_register", "sha256": DIGEST}


def _write(folder: Path, **options: object) -> str:
    return write_public_only(
        folder,
        fixture._scalars(),
        fixture._manifest_sources(),
        fixture.fixture_tables(),
        **options,  # type: ignore[arg-type]
    )


def test_the_writer_lists_the_entry_and_the_checker_reads_it(tmp_path: Path) -> None:
    folder = tmp_path / "listed"
    identity = _write(folder, listed_inputs=[ENTRY])
    document = json.loads((folder / "manifest.json").read_bytes())
    assert document["listed_inputs"] == [ENTRY]
    checked = check_release(folder)
    assert checked.document["release_id"] == identity
    assert {row["fc_register_sha256"] for row in manifest_rows(checked.document)} == {
        DIGEST
    }


def test_the_writer_omits_the_field_when_nothing_is_listed(tmp_path: Path) -> None:
    listed = _write(tmp_path / "listed", listed_inputs=[ENTRY])
    plain = _write(tmp_path / "plain")
    document = json.loads((tmp_path / "plain/manifest.json").read_bytes())
    assert "listed_inputs" not in document
    assert listed != plain


@pytest.mark.parametrize(
    ("value", "reason"),
    (
        ([{"name": "biz_register", "sha256": DIGEST}], "unknown_manifest_key"),
        ([{"name": "fc_register", "sha256": "AB" * 32}], "manifest_type_invalid"),
        ([dict(ENTRY, path="x")], "unknown_manifest_key"),
        ([ENTRY, ENTRY], "duplicate_key"),
    ),
)
def test_the_writer_refuses_one_bad_entry(
    tmp_path: Path, value: object, reason: str
) -> None:
    folder = tmp_path / "refused"
    with pytest.raises(WriterRefusal, match="^" + reason + "$"):
        _write(folder, listed_inputs=value)
    assert not (folder / "manifest.json").exists()


def test_prepare_lists_the_computed_hash(tmp_path: Path) -> None:
    inputs(tmp_path)
    assert "listed_inputs" not in producer.prepare(tmp_path)
    candidate = producer.prepare(tmp_path, fc_register_sha256=DIGEST)
    assert candidate["listed_inputs"] == [ENTRY]


@pytest.mark.parametrize("value", ("AB" * 32, "ab" * 31, "", 7))
def test_prepare_refuses_a_hash_that_is_not_lowercase_hex(
    tmp_path: Path, value: object
) -> None:
    inputs(tmp_path)
    with pytest.raises(ValueError, match=r"^producer_schema_refused$"):
        producer.prepare(tmp_path, fc_register_sha256=value)  # type: ignore[arg-type]


def test_the_spec_cannot_type_a_hash(tmp_path: Path) -> None:
    spec = inputs(tmp_path)
    spec["listed_inputs"] = [ENTRY]
    dump(tmp_path / "review/release_spec.json", spec)
    with pytest.raises(ValueError, match=r"^producer_schema_refused$"):
        producer.prepare(tmp_path, fc_register_sha256=DIGEST)


def test_the_reviewed_envelope_carries_the_entry(tmp_path: Path) -> None:
    inputs(tmp_path)
    expected = approve(tmp_path, fc_register_sha256=DIGEST)
    producer.produce(tmp_path, fc_register_sha256=DIGEST)
    envelope = read_assembly(tmp_path)
    assert envelope == expected
    assert envelope["listed_inputs"] == [ENTRY]


def test_a_changed_file_after_review_needs_another_review(tmp_path: Path) -> None:
    inputs(tmp_path)
    approve(tmp_path, fc_register_sha256=DIGEST)
    other = hashlib.sha256(b"INVENTED-changed-bytes").hexdigest()
    with pytest.raises(ValueError, match=r"^approval_hash_mismatch$"):
        producer.produce(tmp_path, fc_register_sha256=other)
    with pytest.raises(ValueError, match=r"^approval_hash_mismatch$"):
        producer.produce(tmp_path)


def test_the_assembly_build_writes_the_reviewed_entry(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    inputs(cache)
    approve(cache, fc_register_sha256=DIGEST)
    producer.produce(cache, fc_register_sha256=DIGEST)
    destination = tmp_path / "release"
    build(cache, destination)
    document = json.loads((destination / "manifest.json").read_bytes())
    assert document["listed_inputs"] == [ENTRY]
    check_release(destination)


def test_the_reader_admits_no_other_extra_envelope_key(tmp_path: Path) -> None:
    inputs(tmp_path)
    approve(tmp_path, fc_register_sha256=DIGEST)
    producer.produce(tmp_path, fc_register_sha256=DIGEST)
    envelope = json.loads((tmp_path / "assembly/release.json").read_bytes())
    review = json.loads((tmp_path / "assembly/release_review.json").read_bytes())
    envelope["unlisted_extra"] = []
    # Reseal the review so only the key-set guard can refuse.
    review["input_sha256"] = hashlib.sha256(
        canonical_json(envelope).encode()
    ).hexdigest()
    dump(tmp_path / "assembly/release.json", envelope)
    dump(tmp_path / "assembly/release_review.json", review)
    with pytest.raises(ValueError, match=r"^assembly_input_refused$"):
        read_assembly(tmp_path)
