"""Offline schedules use invented UTC clocks, never source-period frequency."""

from datetime import UTC, datetime

import pytest
import yaml

from eii_custodian.publicdata.fetch.registry import (
    RegistryError,
    load_registry,
    registry_path,
)


def test_registry_cadence_closed():
    entries = load_registry()
    assert all(entry.refetch for entry in entries)
    assert next(e for e in entries if e.key == "prop_sales").refetch.value == "weekly"


@pytest.mark.parametrize(
    "value", ["unknown", "as_published", "monthly", "weekly", "quarterly", "annual"]
)
def test_unconfirmed_cannot_acquire_schedule(tmp_path, value):
    doc = yaml.safe_load(registry_path().read_text())
    next(row for row in doc["sources"] if row["source_id"] == "cpi_group")[
        "refetch"
    ] = {"value": value, "reason": "frequency_unconfirmed"}
    path = tmp_path / "syn-registry.yaml"
    path.write_text(yaml.safe_dump(doc))
    with pytest.raises(RegistryError, match="cadence_"):
        load_registry(path)


@pytest.mark.parametrize(
    "value", [None, {}, {"value": "none"}, {"value": "monthly", "evidence": ""}]
)
def test_cadence_requires_explicit_confirmation(value):
    from eii_custodian.publicdata.fetch.cadence import parse_cadence

    with pytest.raises(ValueError, match="cadence_"):
        parse_cadence(value)


@pytest.mark.parametrize(
    "cadence,start,due",
    [
        ("monthly", "2024-01-31T00:00:00Z", "2024-02-29T00:00:00Z"),
        ("quarterly", "2024-01-31T00:00:00Z", "2024-04-30T00:00:00Z"),
        ("annual", "2024-02-29T00:00:00Z", "2025-02-28T00:00:00Z"),
        ("weekly", "2024-01-31T00:00:00Z", "2024-02-07T00:00:00Z"),
    ],
)
def test_due_with_planted_clock(cadence, start, due):
    from eii_custodian.publicdata.fetch.cadence import due_source, parse_cadence

    rule = parse_cadence({"value": cadence, "evidence": "syn-publisher-statement"})
    at = datetime.fromisoformat(due.replace("Z", "+00:00"))
    result = due_source(rule, [start], clock=lambda: at)
    assert result.due_at == at
    assert result.status == "due"
    assert due_source(rule, [start, due], clock=lambda: at).status == "not_due"
    assert due_source(rule, [], clock=lambda: at).status == "due"


def test_publication_none_and_invalid_clock():
    from eii_custodian.publicdata.fetch.cadence import due_source, parse_cadence

    def clock():
        return datetime(2024, 1, 1, tzinfo=UTC)

    publication = parse_cadence(
        {"value": "as_published", "evidence": "syn-publisher-statement"}
    )
    assert (
        due_source(publication, [], clock=clock).status == "publication_check_required"
    )
    none = parse_cadence({"value": "none", "reason": "frequency_unconfirmed"})
    assert due_source(none, [], clock=clock).reason == "frequency_unconfirmed"
    with pytest.raises(ValueError, match="clock_invalid"):
        due_source(none, [], clock=lambda: datetime(2024, 1, 1))


def test_due_registry_verifies_equal_byte_check_events(tmp_path):
    from dataclasses import replace

    from eii_custodian.publicdata.fetch.cadence import due_registry, parse_cadence
    from eii_custodian.publicdata.fetch.snapshots import publish_snapshot

    entry = replace(
        load_registry()[0],
        key="syn_source",
        refetch=parse_cadence({"value": "monthly", "evidence": "syn-statement"}),
    )
    for stamp in ("2024-01-31T00:00:00Z", "2024-02-29T00:00:00Z"):
        publish_snapshot(
            tmp_path / entry.key,
            "json",
            b"syn-body",
            {"source_id": entry.source_id, "key": entry.key, "retrieved_utc": stamp},
        )
    listing = due_registry(
        (entry,), tmp_path, clock=lambda: datetime(2024, 3, 1, tzinfo=UTC)
    )
    assert listing[entry.key].status == "not_due"
    check = next((tmp_path / entry.key / "checks").glob("*.json"))
    check.write_text("{}")
    with pytest.raises(ValueError, match="snapshot_"):
        due_registry((entry,), tmp_path, clock=lambda: datetime(2024, 3, 1, tzinfo=UTC))


@pytest.mark.parametrize(
    "cadence,start,boundary",
    [
        ("daily", "2024-01-31T00:00:00Z", "2024-02-01T00:00:00Z"),
        ("weekly", "2024-01-31T00:00:00Z", "2024-02-07T00:00:00Z"),
        ("monthly", "2023-01-31T00:00:00Z", "2023-02-28T00:00:00Z"),
        ("monthly", "2024-01-31T00:00:00Z", "2024-02-29T00:00:00Z"),
        ("quarterly", "2024-01-31T00:00:00Z", "2024-04-30T00:00:00Z"),
        ("annual", "2024-02-29T00:00:00Z", "2025-02-28T00:00:00Z"),
    ],
)
def test_exact_due_boundary(cadence, start, boundary):
    from datetime import timedelta

    from eii_custodian.publicdata.fetch.cadence import due_source, parse_cadence

    rule = parse_cadence({"value": cadence, "evidence": "syn-statement"})
    at = datetime.fromisoformat(boundary.replace("Z", "+00:00"))
    before = due_source(rule, [start], clock=lambda: at - timedelta(seconds=1))
    assert before.due_at == at
    assert before.status == "not_due"
    assert due_source(rule, [start], clock=lambda: at).status == "due"


def test_recorded_family_assignments():
    families = {
        "fdi_projects": ("investment_pages", "daily"),
        "investqa_pages": ("investment_pages", "daily"),
        "lic_active": ("registers", "weekly"),
        "lic_cancelled": ("registers", "weekly"),
        "lic_issued": ("registers", "weekly"),
        "places_ovt": ("overture_release", "monthly"),
        "bldg_ovt": ("overture_release", "monthly"),
    }
    for row in load_registry():
        expected = families.get(row.source_id)
        if expected:
            assert (row.refetch.family, row.refetch.value) == expected
        else:
            assert row.refetch.family == ""


@pytest.mark.parametrize(
    "family,cadence",
    [
        ("investment_pages", "daily"),
        ("registers", "weekly"),
        ("overture_release", "monthly"),
        ("tender_notices", "daily"),
        ("event_pages", "daily"),
        ("incentive_windows", "daily"),
        ("gis_layers", "weekly"),
        ("supplier_credentials", "weekly"),
        ("register_snapshots", "monthly"),
        ("statistical_series", "as_published"),
    ],
)
def test_closed_family_schedules(family, cadence):
    from eii_custodian.publicdata.fetch.cadence import parse_cadence

    assert (
        parse_cadence(
            {"family": family, "value": cadence, "evidence": "syn-recorded-schedule"}
        ).family
        == family
    )


@pytest.mark.parametrize(
    "rule,reason",
    [
        (
            {"family": "registers", "value": "monthly", "evidence": "syn"},
            "cadence_family_mismatch",
        ),
        ({"family": "registers"}, "cadence_family_mismatch"),
        (
            {"family": "syn-unknown", "value": "daily", "evidence": "syn"},
            "cadence_family_unknown",
        ),
        (
            {"family": "statistical_series", "value": "as_published"},
            "cadence_frequency_unconfirmed",
        ),
    ],
)
def test_family_refusals(rule, reason):
    from eii_custodian.publicdata.fetch.cadence import parse_cadence

    with pytest.raises(ValueError, match="^" + reason + "$"):
        parse_cadence(rule)


@pytest.mark.parametrize(
    "source,rule",
    [
        ("lic_active", {"value": "weekly", "evidence": "syn"}),
        ("syn_source", {"family": "registers", "value": "weekly", "evidence": "syn"}),
        (
            "cpi_group",
            {
                "family": "statistical_series",
                "value": "as_published",
                "evidence": "syn",
            },
        ),
    ],
)
def test_family_registry_assignment_refused(source, rule):
    from eii_custodian.publicdata.fetch.cadence import parse_cadence

    with pytest.raises(ValueError, match=r"^cadence_family_assignment$"):
        parse_cadence(rule, source_id=source)


@pytest.mark.parametrize("kind", ["atlas", "baci", "gravity"])
def test_trade_manifest_omits_absent_family(tmp_path, kind):
    import importlib
    import json

    from eii_custodian.publicdata.fetch.build import run_build

    fixture = importlib.import_module("custodian.tests.fixtures." + kind + ".invented")
    config = importlib.import_module("eii_custodian.publicdata." + kind + ".config")
    stream_key = "stream_transport" if kind == "baci" else kind + "_stream"
    entry = fixture.entry()
    outcome = run_build(
        [entry],
        fixture.metadata,
        tmp_path,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        **{
            stream_key: fixture.stream,
            kind + "_config": config.Config.from_mapping(fixture.configuration()),
        },
    )
    assert outcome.failure is None
    digest = outcome.manifests[entry.source_id]
    manifest = json.loads(
        (tmp_path / entry.key / (digest + ".manifest.json")).read_text()
    )
    assert "family" not in manifest["entry"]["refetch"]
    reader = importlib.import_module("eii_custodian.publicdata." + kind + ".contracts")
    assert reader.read_selected(tmp_path, digest).manifest == manifest
