"""Fix-pass plants for held dispatch, scoped transport and closed refusals."""

import json
from dataclasses import replace

import pytest
from custodian.tests.test_s2_t29_awards import profile, row
from custodian.tests.test_s2_t29_pages import BODY, STAMP, URL, page_entry, review
from custodian.tests.test_s2_t29_transport import pin

from eii_custodian.publicdata.fetch import award_checks, certificate_pins, page_records
from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import SnapshotError
from eii_custodian.publicdata.fetch.transport import Response


@pytest.mark.parametrize("source", ["insurance_tables", "awards_owner_scrape"])
def test_held_dispatch_continues(tmp_path, source):
    held = replace(
        next(e for e in load_registry() if e.source_id == source),
        skip_reason="SYN-held",
    )
    following = replace(page_entry(), key="SYN-next", skip_reason="SYN-held")

    def forbidden(url):
        pytest.fail("held entry requested transport")

    outcome = run_build(
        (held, following), forbidden, tmp_path, lambda: STAMP, lambda _: None
    )
    assert outcome.failure is None
    assert any(line.startswith(f"SKIP {held.key}") for line in outcome.lines)
    assert any(line.startswith("SKIP SYN-next") for line in outcome.lines)
    assert not (tmp_path / held.key).exists()
    assert not (tmp_path / following.key).exists()


@pytest.mark.parametrize("source", ["insurance_tables", "awards_owner_scrape"])
def test_cleared_hold_keeps_evidence_refusal(tmp_path, source, monkeypatch):
    if source == "awards_owner_scrape":
        from eii_custodian.publicdata.fetch import awards

        # Plant the original held profile explicitly now that the real one is active.
        monkeypatch.setattr(
            awards, "load_declaration", lambda _: {"profile": "[LEAD: evidence 3]"}
        )
    held = next(e for e in load_registry() if e.source_id == source)
    outcome = run_build(
        (replace(held, skip_reason=""),),
        lambda _: pytest.fail("request"),
        tmp_path,
        lambda: STAMP,
        lambda _: None,
    )
    assert outcome.failure.check == (
        "acquisition_bound_unconfirmed"
        if source == "insurance_tables"
        else "awards_profile_pending"
    )
    assert not (tmp_path / held.key).exists()


@pytest.mark.parametrize("school", [False, True])
def test_browser_scope_in_page_and_terms(tmp_path, school):
    entry = replace(page_entry(), terms_url="https://www.data.gov.qa/syn-terms")
    if school:
        entry = replace(
            entry,
            source_id="schools_private_directory",
            key="schools_private_directory",
        )
    calls = []

    def transport(url):
        calls.append((url, certificate_pins.browser_agent()))
        return Response(url, b"SYN terms" if url == entry.terms_url else BODY, ())

    page_records.fetch_page(
        entry,
        transport,
        tmp_path,
        lambda: STAMP,
        lambda _: None,
        declaration=review(entry),
        pin=pin() if school else None,
    )
    assert calls == [(URL, school), (entry.terms_url, False)]
    assert certificate_pins.browser_agent() is False


def test_page_transport_browser_default():
    with certificate_pins.page_transport(None):
        assert certificate_pins.browser_agent() is False


@pytest.mark.parametrize(
    "error",
    [
        certificate_pins.PinError("certificate_chain_incomplete"),
        certificate_pins.PinError("certificate_host_mismatch"),
        certificate_pins.PinError("certificate_review_pending"),
        certificate_pins.PinError("tls_verification_disabled"),
        award_checks.AwardError("blocked_host"),
        SnapshotError("snapshot_conflict"),
        SnapshotError("snapshot_hash_mismatch"),
    ],
)
def test_award_security_refusal_propagates(error):
    def proof(_):
        raise error

    with pytest.raises(type(error), match=f"^{error}$"):
        award_checks.check_awards([row()], profile(), 73, proof)


@pytest.mark.parametrize(
    "registration,count,reason",
    [(" \t ", 1, "registration_unmatched"), ("SYN-reg", 2, "registration_ambiguous")],
)
def test_registration_blank_or_duplicate(registration, count, reason):
    result = award_checks.match_register(
        [dict(row(), syn_reg=registration)],
        profile(),
        [{"registration": registration, "name": row()["syn_company"]}] * count,
    )
    assert result["matched"] == 0
    assert result["unmatched"] == 1
    assert result["rows"][0]["reason"] == reason


def test_stale_period_no_request(tmp_path):
    with pytest.raises(page_records.PageError, match=r"^stale_period$"):
        page_records.fetch_page(
            replace(page_entry(), period_last="2025"),
            lambda _: pytest.fail("stale request"),
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=review(),
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("kind", ["integer", "number"])
def test_empty_numeric_cell_is_null(tmp_path, kind):
    entry = replace(page_entry(), columns=(("syn_name", "string"), ("syn_count", kind)))
    result = page_records.fetch_page(
        entry,
        lambda url: Response(url, BODY.replace(b">7<", b"><"), ()),
        tmp_path,
        lambda: STAMP,
        lambda _: None,
        declaration=review(entry),
    )
    assert json.loads(result.body)["rows"][0]["syn_count"] is None


def test_missing_coverage_zero_claim_refused():
    with pytest.raises(page_records.PageError, match=r"^unsupported_source_claim$"):
        page_records.validate_claim("events_visit_qatar", "missing_coverage_as_zero")


def award_intake(tmp_path, monkeypatch):
    """One invented active intake and two reviewed proof URLs."""
    from eii_custodian.publicdata.fetch import awards

    entry = replace(
        next(e for e in load_registry() if e.source_id == "awards_owner_scrape"),
        skip_reason="",
        url=row()["report_url"],
        fetch_host="www.data.gov.qa",
    )
    schema = profile()
    declaration = {
        "url": entry.url,
        "reviewed_urls": [row(i)["report_url"] for i in range(2)],
        "table_id": "syn",
        "columns": [[c, "string"] for c in schema["columns"]],
        "profile": schema,
    }
    monkeypatch.setattr(awards, "load_declaration", lambda _: declaration)
    folder = tmp_path / "intake" / entry.key
    folder.mkdir(parents=True)
    body = (
        ",".join(schema["columns"])
        + "\n"
        + "\n".join(",".join(row(i)[c] for c in schema["columns"]) for i in range(2))
        + "\n"
    ).encode()
    from hashlib import sha256

    (folder / "syn.csv").write_bytes(body)
    (folder / "intake.json").write_text(
        json.dumps(
            {
                "file": "syn.csv",
                "sha256": sha256(body).hexdigest(),
                "seed": 73,
                "register_selections": [],
            }
        )
    )

    def proof(url):
        cells = row(int(url.rsplit("/", 1)[1]))
        body = (
            '<table id="syn"><tr>'
            + "".join(f"<th>{c}</th>" for c in schema["columns"])
            + "</tr><tr>"
            + "".join(f"<td>{cells[c]}</td>" for c in schema["columns"])
            + "</tr></table>"
        ).encode()
        return Response(url, body, ())

    return entry, declaration, proof


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("unreviewed", "blocked_host"),
        ("offhost", "blocked_host"),
        ("redirect", "blocked_host"),
        ("bounded_host", "blocked_host"),
        ("pin", "certificate_chain_incomplete"),
        ("disabled", "tls_verification_disabled"),
        ("conflict", "snapshot_conflict"),
        ("tamper", "snapshot_hash_mismatch"),
    ],
)
def test_awards_intake_security_refuses(tmp_path, monkeypatch, plant, reason):
    from eii_custodian.publicdata.fetch import awards
    from eii_custodian.publicdata.fetch.transport import TransportFault

    entry, declaration, proof = award_intake(tmp_path, monkeypatch)
    if plant == "unreviewed":
        declaration["reviewed_urls"] = []
    if plant == "offhost":
        import hashlib

        folder = tmp_path / "intake" / entry.key
        body = (
            (folder / "syn.csv")
            .read_bytes()
            .replace(b"https://www.data.gov.qa/", b"https://example.invalid/")
        )
        (folder / "syn.csv").write_bytes(body)
        manifest = json.loads((folder / "intake.json").read_text())
        manifest["sha256"] = hashlib.sha256(body).hexdigest()
        (folder / "intake.json").write_text(json.dumps(manifest))
    if plant in {"conflict", "tamper"}:

        def refuse(*args, **kwargs):
            raise SnapshotError(reason)

        monkeypatch.setattr(awards, "publish_snapshot", refuse)

    def transport(url):
        if plant in {"unreviewed", "offhost"}:
            pytest.fail("refused URL requested")
        if plant in {"pin", "disabled"}:
            raise certificate_pins.PinError(reason)
        if plant == "bounded_host":
            raise TransportFault("blocked_host", "https://example.invalid/syn")
        response = proof(url)
        return (
            replace(response, final_url="https://www.data.gov.qa/syn-unreviewed")
            if plant == "redirect"
            else response
        )

    outcome = run_build((entry,), transport, tmp_path, lambda: STAMP, lambda _: None)
    assert outcome.failure is not None
    assert outcome.failure.check == reason
    assert not (tmp_path / entry.key).exists()


def test_awards_proof_browser_default(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.awards import fetch_awards

    entry, _, proof = award_intake(tmp_path, monkeypatch)
    seen = []

    def transport(url):
        seen.append(certificate_pins.browser_agent())
        return proof(url)

    fetch_awards(entry, transport, tmp_path, lambda: STAMP, lambda _: None)
    assert seen == [False, False]


@pytest.mark.parametrize("date", [None, "", "2024-02-03", "2024-02-03T00:00:00+01:00"])
def test_awards_row_date_missing(tmp_path, date):
    from hashlib import sha256

    from eii_custodian.publicdata.fetch.awards import AwardBatch, publish_awards

    entry = next(e for e in load_registry() if e.source_id == "awards_owner_scrape")
    records = (
        {"original": row(), "retrieved_utc": STAMP},
        {"original": row(), "retrieved_utc": date},
    )
    batch = AwardBatch(records, {}, sha256(b"SYN").hexdigest(), b"SYN", "csv")
    with pytest.raises(SnapshotError, match=r"^snapshot_date_missing$"):
        publish_awards(
            entry,
            tmp_path,
            batch,
            profile(),
            STAMP,
            73,
            lambda _: pytest.fail("invalid batch checked proof"),
            [],
        )
    assert not (tmp_path / entry.key).exists()


@pytest.mark.parametrize("kind", ["integer", "number"])
def test_awards_retains_parsed_blank(tmp_path, kind):
    from hashlib import sha256

    from eii_custodian.publicdata.fetch.awards import ingest_awards

    folder = tmp_path / "intake/awards_owner_scrape"
    folder.mkdir(parents=True)
    path = folder / "syn.csv"
    schema = profile()
    schema["types"][2] = kind
    body = (
        ",".join(schema["columns"]) + "\nSYN Company,SYN-reg,,03/02/2024,\n"
    ).encode()
    path.write_bytes(body)
    batch = ingest_awards(tmp_path, path, sha256(body).hexdigest(), schema, STAMP)
    assert batch.rows[0]["original"]["syn_value"] == ""
    assert batch.rows[0]["parsed"]["syn_value"] is None


@pytest.mark.parametrize(
    "source,phase",
    [
        ("page", "terms"),
        ("page", "raw"),
        ("page", "parsed"),
        ("awards", "proofs"),
        ("awards", "raw"),
        ("awards", "parsed"),
    ],
)
def test_interrupted_publication_has_no_partial(tmp_path, monkeypatch, source, phase):
    from eii_custodian.publicdata.fetch import awards

    if source == "page":
        entry = replace(page_entry(), terms_url="https://www.data.gov.qa/syn-terms")
        monkeypatch.setattr(page_records, "load_declaration", lambda _: review(entry))

        def transport(url):
            return Response(url, BODY if url == URL else b"SYN terms", ())

        module = page_records
    else:
        entry, _, transport = award_intake(tmp_path, monkeypatch)
        module = awards
    original = module.publish_snapshot

    def publish(directory, *args, **kwargs):
        result = original(directory, *args, **kwargs)
        if directory.name == (entry.key if phase == "parsed" else phase):
            raise OSError("SYN-secret-write-error")
        return result

    monkeypatch.setattr(module, "publish_snapshot", publish)
    if phase == "terms":
        original_terms = page_records.archive_auxiliary

        def terms(*args, **kwargs):
            original_terms(*args, **kwargs)
            raise OSError("SYN-secret-write-error")

        monkeypatch.setattr(page_records, "archive_auxiliary", terms)
    outcome = run_build((entry,), transport, tmp_path, lambda: STAMP, lambda _: None)
    assert outcome.failure is not None
    assert outcome.failure.check == (
        "snapshot_write_failed" if phase == "proofs" else "page_validation_failed"
    )
    assert not (tmp_path / entry.key).exists()
    assert not list(tmp_path.glob(".page-stage-*"))
    assert "SYN-secret-write-error" not in repr(outcome)


@pytest.mark.parametrize("source", ["page", "intake"])
def test_secret_error_is_sanitized(tmp_path, monkeypatch, capsys, source):
    from commands import build_public

    cache = tmp_path / "data/public_cache"
    if source == "page":
        entry = page_entry()
        monkeypatch.setattr(page_records, "load_declaration", lambda _: review())
    else:
        entry, _, _ = award_intake(cache, monkeypatch)
    monkeypatch.setattr(build_public, "load_registry", lambda: (entry,))

    def broken(_):
        raise OSError("SYN-secret-bearing-error")

    if source == "intake":
        from eii_custodian.publicdata.fetch import awards

        monkeypatch.setattr(awards, "ingest_awards", lambda *args: broken(None))
    assert (
        build_public.run(tmp_path, {}, [], transport=broken, sleep=lambda _: None) == 1
    )
    assert "SYN-secret-bearing-error" not in capsys.readouterr().out
    for path in cache.rglob("*"):
        if path.is_file():
            assert b"SYN-secret-bearing-error" not in path.read_bytes()


def test_awards_existing_identity_conflict(tmp_path):
    from hashlib import sha256

    from eii_custodian.publicdata.fetch.awards import AwardBatch, publish_awards
    from eii_custodian.publicdata.fetch.snapshots import publish_snapshot, read_snapshot

    entry = next(e for e in load_registry() if e.source_id == "awards_owner_scrape")
    batch = AwardBatch(
        ({"original": row(), "retrieved_utc": STAMP},),
        {},
        sha256(b"SYN").hexdigest(),
        b"SYN",
        "csv",
    )
    first = publish_awards(
        entry, tmp_path, batch, profile(), STAMP, 73, lambda _: row(), []
    )
    changed = first.body + b" "
    side = dict(first.sidecar, sha256=sha256(changed).hexdigest(), bytes=len(changed))
    before = {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    with pytest.raises(SnapshotError, match=r"^snapshot_conflict$"):
        publish_snapshot(
            tmp_path / entry.key, "json", changed, side, identity=first.sha256
        )
    assert read_snapshot(tmp_path / entry.key, first.sha256).body == first.body
    assert {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    } == before


@pytest.mark.parametrize("fault", ["tamper", "conflict"])
def test_existing_proof_integrity_refusal_preserves_archive(
    tmp_path, monkeypatch, fault
):
    from eii_custodian.publicdata.fetch.snapshots import publish_snapshot

    entry, _, proof = award_intake(tmp_path, monkeypatch)
    response = proof(entry.url)
    archived = publish_snapshot(
        tmp_path / entry.key / "proofs",
        "html",
        response.body,
        {
            "source_id": "SYN-wrong-source" if fault == "conflict" else entry.source_id,
            "key": entry.key,
            "retrieved_utc": STAMP,
        },
    )
    if fault == "tamper":
        archived.path.write_bytes(b"SYN-tampered")
    before = {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    outcome = run_build((entry,), proof, tmp_path, lambda: STAMP, lambda _: None)
    assert outcome.failure.check == (
        "snapshot_conflict" if fault == "conflict" else "snapshot_hash_mismatch"
    )
    after = {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.name not in {"build-log.json", "terms_state.json"}
    }
    assert all(after[key] == body for key, body in before.items())
    assert not list((tmp_path / entry.key / "index").glob("*.json"))
    assert not list((tmp_path / entry.key / "raw").rglob("*"))


@pytest.mark.parametrize("kind", ["unreachable", "http", "metadata_bytes"])
def test_proof_fetch_failures_remain_counted(tmp_path, monkeypatch, kind):
    from eii_custodian.publicdata.fetch.awards import fetch_awards
    from eii_custodian.publicdata.fetch.transport import TransportFault

    entry, _, _ = award_intake(tmp_path, monkeypatch)

    def failed(url):
        raise TransportFault(kind, url)

    result = fetch_awards(entry, failed, tmp_path, lambda: STAMP, lambda _: None)
    check = result.sidecar["award_check"]
    assert check["failed_fetches"] == 2
    assert check["match_rate"] == "0"
    assert check["incomplete"] is True
    assert all(item["result"] == "fetch_failed" for item in check["results"])


def test_successful_intake_keeps_every_proof(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch.awards import fetch_awards
    from eii_custodian.publicdata.fetch.snapshots import read_snapshot

    entry, declaration, _ = award_intake(tmp_path, monkeypatch)
    schema = profile()

    def proof(url):
        cells = dict(row(int(url.rsplit("/", 1)[1])))
        cells["syn_value"] = "13" if url.endswith("/1") else "12.50"
        body = (
            '<table id="syn"><tr>'
            + "".join(f"<th>{c}</th>" for c in schema["columns"])
            + "</tr><tr>"
            + "".join(f"<td>{cells[c]}</td>" for c in schema["columns"])
            + "</tr></table>"
        ).encode()
        return Response(url, body, ())

    result = fetch_awards(entry, proof, tmp_path, lambda: STAMP, lambda _: None)
    assert result.sidecar["award_check"]["selected_count"] == 2
    directory = tmp_path / entry.key / "proofs"
    indices = list((directory / "index").glob("*.json"))
    assert len(indices) == 2
    assert {
        read_snapshot(directory, p.stem).sidecar["fetch_url"] for p in indices
    } == set(declaration["reviewed_urls"])
