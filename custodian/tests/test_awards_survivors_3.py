"""Offline v1/v2 proof acquisition, pin selection and retained evidence plants."""

import json
import ssl
from collections import UserDict
from dataclasses import replace

import pytest
import yaml
from custodian.tests.test_s2_t29_awards import STAMP, profile
from custodian.tests.test_s2_t29_fix import award_intake
from custodian.tests.test_s2_t29_fix10 import config_file, make_pin
from custodian.tests.test_s2_t29_fix10 import invented_certs as invented_certs
from custodian.tests.test_s2_t29_live_awards import report

from eii_custodian.publicdata.fetch import (
    awards,
    certificate_pins,
    page_records,
    page_requests,
)
from eii_custodian.publicdata.fetch.award_checks import AwardError
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.fetch.transport import _METADATA_LIMIT, Response


@pytest.fixture
def isolated_trust(tmp_path, monkeypatch, invented_certs):
    """Keep every SSL context in these pin tests on invented trust only."""
    root = tmp_path / "SYN-root.pem"
    root.write_text(ssl.DER_cert_to_PEM_cert(invented_certs["root"]), encoding="utf-8")
    empty = tmp_path / "SYN-empty-certificates"
    empty.mkdir()
    monkeypatch.setenv("SSL_CERT_FILE", str(root))
    monkeypatch.setenv("SSL_CERT_DIR", str(empty))
    assert ssl.create_default_context().get_ca_certs(binary_form=True) == [
        invented_certs["root"]
    ]
    return invented_certs


def setup(tmp_path, monkeypatch, *, version=2, host="www.data.gov.qa"):
    entry, old, proof = award_intake(tmp_path, monkeypatch)
    if version == 1:
        dec = old
        body = proof(entry.url).body
    else:
        dec, body = report()
        dec.update(
            url=entry.url,
            reviewed_urls=old["reviewed_urls"],
            profile=dict(
                profile(),
                proof_columns={
                    "company": "SYN company",
                    "registration": "SYN registration",
                    "value": "SYN amount",
                },
            ),
        )
        body = body.replace(b"SYN first", b"SYN Company").replace(b"1,007.00", b"12.50")
        # Removal must visibly change bytes and hash, not merely a label.
        body += b'<form><input type="hidden" name="__RequestVerificationToken" value="SYN discard"></form>'
    if host != "www.data.gov.qa":
        previous = "https://www.data.gov.qa"
        current = "https://" + host
        entry = replace(
            entry, url=entry.url.replace(previous, current), fetch_host=host
        )
        dec["url"] = entry.url
        dec["reviewed_urls"] = [
            url.replace(previous, current) for url in dec["reviewed_urls"]
        ]
        folder = tmp_path / "intake" / awards.SOURCE
        intake_body = (
            (folder / "syn.csv")
            .read_bytes()
            .replace(previous.encode(), current.encode())
        )
        (folder / "syn.csv").write_bytes(intake_body)
        manifest = json.loads((folder / "intake.json").read_text(encoding="utf-8"))
        manifest["sha256"] = sha256_hex(intake_body)
        (folder / "intake.json").write_text(json.dumps(manifest), encoding="utf-8")
    path = tmp_path / "SYN-declaration.yaml"
    real_load = page_records.load_declaration
    calls = []

    def load(source):
        calls.append((source, path))
        # Tests change dec after setup; persist that exact case before loading.
        document = {"sources": {"awards_owner_scrape": dec}}
        mapping = dec["profile"].get("proof_columns")
        if isinstance(mapping, UserDict):
            document = {
                "sources": {
                    "awards_owner_scrape": dict(
                        dec, profile=dict(dec["profile"], proof_columns=dict(mapping))
                    )
                }
            }
        path.write_text(yaml.safe_dump(document), encoding="utf-8")
        loaded = real_load(source, path)
        assert calls == [("awards_owner_scrape", path)]
        if isinstance(mapping, UserDict):
            # YAML yields dicts. Preserve this separate in-memory type plant
            # after the real loader has checked the document and source.
            loaded["profile"]["proof_columns"] = UserDict(
                loaded["profile"]["proof_columns"]
            )
        return loaded

    monkeypatch.setattr(awards, "load_declaration", load)
    return entry, dec, body


def fetch(entry, tmp_path, body):
    return awards.fetch_awards(
        entry,
        lambda url: Response(url, body, ()),
        tmp_path,
        lambda: STAMP,
        lambda _: None,
    )


def test_v2_proof_full_receipt_and_scope(tmp_path, monkeypatch):
    entry, dec, body = setup(tmp_path, monkeypatch)
    dec["max_bytes"] = len(body)
    calls = []

    def send(url):
        assert page_requests.active()
        assert _METADATA_LIMIT.get() == len(body)
        assert certificate_pins.current_pin() is None
        page_requests.check_target(url)
        calls.append(url)
        return Response(url, body, ())

    result = awards.fetch_awards(entry, send, tmp_path, lambda: STAMP, lambda _: None)
    assert calls == dec["reviewed_urls"]
    assert result.sidecar["award_check"]["matched"] == 2
    directory = tmp_path / entry.key / "proofs"
    snapshots = [
        read_snapshot(directory, p.stem) for p in (directory / "index").glob("*.json")
    ]
    assert len(snapshots) == 1  # Equal proof bytes share a single identity.
    proof = snapshots[0]
    assert b"SYN discard" not in proof.body and proof.body != body
    side = proof.sidecar
    for key, expected in {
        "fetch_host": entry.fetch_host,
        "publisher": entry.publisher,
        "source_modified": None,
        "terms_sha256": None,
        "row_count": 2,
        "sha256": sha256_hex(proof.body),
        "bytes": len(proof.body),
        "upstream_sha256": sha256_hex(body),
        "representation": "form_secret_removed",
    }.items():
        assert side[key] == expected, key
    assert not page_requests.active()


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("schema", "snapshot_date_missing"),
        ("hold", "schema_evidence_pending"),
        ("bound", "acquisition_bound_unconfirmed"),
        ("mapping_missing", "awards_profile_pending"),
        ("mapping_keys", "awards_profile_pending"),
        ("mapping_value", "awards_profile_pending"),
        ("mapping_type", "awards_profile_pending"),
    ],
)
def test_v2_declaration_closed_refusals(tmp_path, monkeypatch, plant, reason):
    entry, dec, _ = setup(tmp_path, monkeypatch)
    if plant == "schema":
        dec["as_of"] = "SYN missing"
    elif plant == "hold":
        dec["hold"] = "schema_evidence_pending"
    elif plant == "bound":
        dec["max_bytes"] = None
    elif plant == "mapping_missing":
        dec["profile"].pop("proof_columns")
    elif plant == "mapping_keys":
        dec["profile"]["proof_columns"].pop("company")
    elif plant == "mapping_value":
        dec["profile"]["proof_columns"]["company"] = "SYN missing"
    else:
        dec["profile"]["proof_columns"] = UserDict(dec["profile"]["proof_columns"])
    with pytest.raises(AwardError, match=f"^{reason}$"):
        awards.fetch_awards(
            entry,
            lambda _: pytest.fail("refused input requested proof"),
            tmp_path,
            lambda: STAMP,
            lambda _: None,
        )


@pytest.mark.parametrize("plant", ["url", "basis", "commit", "publisher"])
def test_fetch_entry_independent_refusals(tmp_path, monkeypatch, plant):
    entry, _, body = setup(tmp_path, monkeypatch)
    entry = replace(
        entry,
        **{
            "url": {"url": "https://www.data.gov.qa/SYN-wrong"},
            "basis": {"licence_basis": ""},
            "commit": {"commit_allowed": True},
            "publisher": {"publisher": ""},
        }[plant],
    )
    (tmp_path / "intake" / awards.SOURCE / "intake.json").unlink()
    with pytest.raises(AwardError, match=r"^receipt_missing$"):
        fetch(entry, tmp_path, body)


def test_manifest_missing_reason(tmp_path, monkeypatch):
    entry, _, body = setup(tmp_path, monkeypatch)
    (tmp_path / "intake" / awards.SOURCE / "intake.json").unlink()
    with pytest.raises(AwardError, match=r"^intake_missing$"):
        fetch(entry, tmp_path, body)


@pytest.mark.parametrize("version", [1, 2])
def test_pin_selection_and_request_context(
    tmp_path, monkeypatch, version, isolated_trust
):
    entry, dec, body = setup(
        tmp_path, monkeypatch, version=version, host="monaqasat.mof.gov.qa"
    )
    der = isolated_trust["intermediate"]
    configured = config_file(tmp_path, der, entry.fetch_host, awards.SOURCE)
    real_load = awards.load_pin
    chosen = real_load(tmp_path, awards.SOURCE, configured)
    assert chosen == make_pin(der, entry.fetch_host)
    if version == 2:
        dec["pins"] = [
            config_file(tmp_path, der, "www.edu.gov.qa", awards.SOURCE),
            configured,
        ]
    else:
        dec["pin"] = configured
    loaded = []

    def load(cache, source, config):
        assert cache == tmp_path and source == "awards_owner_scrape"
        assert config == configured
        loaded.append(config)
        return real_load(cache, source, config)

    monkeypatch.setattr(awards, "load_pin", load)

    def send(url):
        if version == 2:
            assert page_requests.active()
            assert certificate_pins.current_pin() is None
            assert page_requests._PINS.get() == {chosen.host: chosen}
        else:
            assert not page_requests.active()
            assert certificate_pins.current_pin() == chosen
        return Response(url, body, ())

    result = awards.fetch_awards(entry, send, tmp_path, lambda: STAMP, lambda _: None)
    assert len(loaded) == 1
    assert result.sidecar["award_check"]["matched"] == 2


def test_legacy_explicit_pin_off_tender_host(tmp_path, monkeypatch, isolated_trust):
    entry, dec, body = setup(tmp_path, monkeypatch, version=1, host="www.edu.gov.qa")
    der = isolated_trust["intermediate"]
    dec["pin"] = config_file(tmp_path, der, entry.fetch_host, awards.SOURCE)
    real_load = awards.load_pin
    chosen = real_load(tmp_path, "awards_owner_scrape", dec["pin"])
    assert chosen == make_pin(der, entry.fetch_host)
    loaded = []

    def load(cache, source, config):
        assert (cache, source, config) == (tmp_path, "awards_owner_scrape", dec["pin"])
        loaded.append(config)
        return real_load(cache, source, config)

    monkeypatch.setattr(awards, "load_pin", load)

    def send(url):
        assert certificate_pins.current_pin() == chosen
        return Response(url, body, ())

    awards.fetch_awards(entry, send, tmp_path, lambda: STAMP, lambda _: None)
    assert len(loaded) == 1


@pytest.mark.parametrize(
    "version,host",
    [(1, "monaqasat.mof.gov.qa"), (2, "monaqasat.mof.gov.qa"), (1, "www.edu.gov.qa")],
)
@pytest.mark.parametrize(
    "plant,reason",
    [
        ("digest", "certificate_chain_incomplete"),
        ("review", "certificate_review_pending"),
    ],
)
def test_configured_pin_refuses_before_send(
    tmp_path, monkeypatch, isolated_trust, version, host, plant, reason
):
    entry, dec, body = setup(tmp_path, monkeypatch, version=version, host=host)
    configured = config_file(
        tmp_path, isolated_trust["intermediate"], host, awards.SOURCE
    )
    if plant == "digest":
        configured["sha256"] = "0" * 64
    else:
        configured["security_review"] = "PENDING"
    if version == 2:
        dec["pins"] = [configured]
    else:
        dec["pin"] = configured
    calls = []

    def send(url):
        calls.append(url)
        return Response(url, body, ())

    with pytest.raises(certificate_pins.PinError, match=f"^{reason}$"):
        awards.fetch_awards(entry, send, tmp_path, lambda: STAMP, lambda _: None)
    assert calls == []


@pytest.mark.parametrize("version", [1, 2])
def test_proof_null_and_nonnull_projection(tmp_path, monkeypatch, version):
    entry, dec, body = setup(tmp_path, monkeypatch, version=version)
    from eii_custodian.publicdata.fetch import award_checks

    original = award_checks.check_awards
    key = "SYN company" if version == 2 else "syn_company"
    monkeypatch.setattr(
        awards,
        "parse_body",
        lambda *args: [
            {
                key: None,
                ("SYN registration" if version == 2 else "syn_reg"): "SYN-reg",
                ("SYN amount" if version == 2 else "syn_value"): "12.50",
            }
        ],
    )
    seen = []

    def check(rows, schema, seed, proof_reader):
        def proof(url):
            projected = proof_reader(url)
            assert projected == [
                {"syn_company": "", "syn_reg": "SYN-reg", "syn_value": "12.50"}
            ]
            seen.append(url)
            return projected

        return original(rows, schema, seed, proof)

    monkeypatch.setattr(awards, "check_awards", check)
    result = fetch(entry, tmp_path, body)
    assert seen == dec["reviewed_urls"]
    assert result.sidecar["award_check"]["mismatched"] == 2


@pytest.mark.parametrize(
    "plant,reason", [("oversize", "metadata_bytes"), ("empty", "schema_missing")]
)
def test_proof_read_refusals(tmp_path, monkeypatch, plant, reason):
    entry, dec, body = setup(tmp_path, monkeypatch)
    if plant == "oversize":
        dec["max_bytes"] = len(body) - 1
    else:
        monkeypatch.setattr(awards, "parse_body", lambda *args: [])
    with pytest.raises(AwardError, match=f"^{reason}$"):
        fetch(entry, tmp_path, body)


def test_fetch_register_inputs_survive(tmp_path, monkeypatch):
    from custodian.tests.test_awards_survivors_2 import register

    entry, _, body = setup(tmp_path, monkeypatch, version=1)
    snap, selection = register(tmp_path)
    path = tmp_path / "intake" / awards.SOURCE / "intake.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["register_selections"] = [selection]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = fetch(entry, tmp_path, body)
    assert result.sidecar["registration_inputs"] == [
        {
            "key": selection["key"],
            "identity": snap.sha256,
            "sha256": snap.sha256,
            "retrieved_utc": STAMP,
        }
    ]
    assert result.sidecar["registration_match"]["matched"] == 2


def test_missing_matching_pin_refuses(tmp_path, monkeypatch):
    entry, _, body = setup(tmp_path, monkeypatch, host="monaqasat.mof.gov.qa")
    with pytest.raises(
        certificate_pins.PinError, match=r"^certificate_chain_incomplete$"
    ):
        fetch(entry, tmp_path, body)


def test_missing_host_pin_closed_refusal(tmp_path, monkeypatch):
    entry, dec, body = setup(tmp_path, monkeypatch, host="monaqasat.mof.gov.qa")
    dec["pins"] = []
    with pytest.raises(
        certificate_pins.PinError, match=r"^certificate_chain_incomplete$"
    ):
        fetch(entry, tmp_path, body)
