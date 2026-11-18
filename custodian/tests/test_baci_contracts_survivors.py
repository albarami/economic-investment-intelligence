"""Selected-release metadata oracles using the existing invented builder."""

from contextlib import contextmanager
from dataclasses import replace

import pytest
from custodian.tests.test_baci import (
    _baci_selected_fixture,
    _baci_write_manifest,
    configuration,
)
from custodian.tests.test_baci_fetch import build, entry, metadata

from eii_custodian.publicdata.baci import contracts
from eii_custodian.publicdata.baci.config import BaciError
from eii_custodian.publicdata.baci.contracts import read_selected


@contextmanager
def refusal(message):
    with pytest.raises(BaciError) as caught:
        yield
    assert str(caught.value) == message


def test_baci_registry_and_lineage(tmp_path):
    outcome = build(tmp_path)
    assert outcome.failure is None
    selected = outcome.manifests["cepii_baci"]
    release = read_selected(tmp_path, selected)
    assert release.source_registry == {
        "source_id": "cepii_baci",
        "kind": "public_dataset",
        "title": "Invented BACI",
        "publisher": "Invented publisher",
        "url": "https://www.data.gov.qa/invented-baci-page",
        "licence": "unconfirmed",
        "licence_basis": "owner_decision",
        "retrieved_on": "2026-11-16",
        "sha256": selected,
        "commit_allowed": False,
        "attribution": "Invented publisher, invented release",
        "public_splits": None,
    }
    assert release.fact_lineage == tuple(
        {
            "lineage_id": "lin_" + table,
            "table_name": table,
            "source_id": "cepii_baci",
            "input_class": "public",
            "transform": "eii_custodian.publicdata.baci.parse.parse_archive@v1",
            "partition_id": None,
            "measure": None,
            "breakdown": None,
            "family_role": None,
            "rules_version_id": None,
        }
        for table in ("pub_baci_trade", "pub_baci_country", "pub_baci_product")
    )


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("complete", False, "manifest_complete"),
        ("method", "invented", "lineage"),
        ("attribution", "invented", "lineage"),
    ],
)
def test_baci_manifest_messages(tmp_path, field, value, reason):
    directory, _, manifest = _baci_selected_fixture(tmp_path)
    manifest[field] = value
    selected = _baci_write_manifest(directory, manifest)
    with refusal(reason):
        read_selected(tmp_path, selected)


def test_baci_missing_selected_message(tmp_path):
    with refusal("selected_manifest_invalid"):
        read_selected(tmp_path, "a" * 64)


def test_baci_output_corruption_message(tmp_path):
    directory, selected, manifest = _baci_selected_fixture(tmp_path)
    digest = manifest["outputs"]["pub_baci_trade"]["sha256"]
    (directory / f"{digest}.jsonl").write_text("invented")
    with refusal("output_hash"):
        read_selected(tmp_path, selected)


def test_baci_terms_receipt_present(tmp_path):
    source = replace(entry(), terms_url=entry().url + "-terms")
    raw = configuration()
    raw["reviewed_urls"].append(source.terms_url)
    result = build(tmp_path, source=source, config=raw, byte_transport=metadata)
    assert result.failure is None
    release = read_selected(tmp_path, result.manifests["cepii_baci"])
    assert release.manifest["terms_unread"] == ""
    assert release.manifest["receipt"]["terms_sha256"] is not None


def test_baci_verification_stays_in_cache(tmp_path, monkeypatch):
    directory, selected, _ = _baci_selected_fixture(tmp_path)
    original = contracts.parse_archive
    observed = []

    def checked(archive, config, output):
        assert output.parent == directory
        assert output.name.startswith(".verify-")
        assert output.is_dir()
        observed.append(output)
        return original(archive, config, output)

    monkeypatch.setattr(contracts, "parse_archive", checked)
    read_selected(tmp_path, selected)
    assert len(observed) == 1
    assert not observed[0].exists()


def test_baci_selected_explicit_encoding(tmp_path):
    class OtherDefaultPath(type(tmp_path)):
        def read_text(self, encoding=None, errors=None, newline=None):
            return super().read_text(
                encoding=encoding or "cp037", errors=errors, newline=newline
            )

    result = build(tmp_path)
    assert result.failure is None
    release = read_selected(OtherDefaultPath(tmp_path), result.manifests["cepii_baci"])
    assert release.country[0].source_name == "Invented target"
