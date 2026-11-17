"""Invented inputs only; any files live under pytest's tmp_path directory."""

from dataclasses import replace

import pytest

from eii_custodian.publicdata import completeness as c
from eii_custodian.publicdata.fetch.receipts import sidecar_for
from eii_custodian.publicdata.fetch.registry import Entry


def entry(source="invented", **changes):
    row = Entry(
        key=source,
        source_id=source,
        slug="",
        kind="https_file",
        title_en="Invented dataset",
        publisher="Invented publisher",
        licence_id="Invented open licence",
        licence_basis="dataset",
        decision_record="",
        fetch_host="example.org",
        url="https://example.org/source",
        terms_url="https://example.org/terms",
        nightly_live_fetch=False,
        public_splits=(),
        commit_allowed=False,
        release_tables=("pub_invented",),
        caveat_keys=("invented_caveat",),
        columns=(),
        row_count_min=None,
        row_count_max=None,
        period_first="",
        period_last="",
        period_field="",
        reconciliation="none",
        skip_reason="",
        extension="json",
        landing_url="",
        terms_words="Invented terms",
        terms_read_on="2026-11-17",
    )
    return replace(row, **changes)


def receipt(row):
    return sidecar_for(
        row,
        digest="a" * 64,
        nbytes=3,
        fetch_url=row.url,
        fetch_host=row.fetch_host,
        retrieved_utc="2026-11-17T00:00:00Z",
        publisher=row.publisher,
        source_modified="",
        row_count=None,
        terms_sha256="b" * 64,
    )


def inputs():
    row = entry()
    return dict(
        entries=[row],
        pack=c.Pack({row.source_id: ()}, frozenset()),
        inventory={row.source_id: ()},
        catalogue={"pub_invented"},
        receipts={row.key: receipt(row)},
        outputs={row.key: ("pub_invented",)},
        absences={},
        cached_source_ids=(),
    )


def failures(record):
    return [row for row in record if row["state"] == "failed"]


def test_pack_registry_receipts_and_outputs_agree():
    record = c.check(**inputs())
    assert not failures(record)
    assert {"id": "invented", "state": "in use", "reason": ""} in record
    assert {r["id"] for r in record if r["state"] == "not yet read"} == {
        "biz_register",
        "fc_register",
    }


@pytest.mark.parametrize(
    "plant",
    [
        "pack",
        "registry",
        "both",
        "extra",
        "duplicate",
        "receipt",
        "output",
        "table",
        "orphan",
    ],
)
def test_independent_checks(plant):
    args = inputs()
    if plant in {"pack", "both"}:
        args["pack"] = c.Pack({}, frozenset())
    if plant in {"registry", "both"}:
        args["entries"] = []
    if plant == "extra":
        args["entries"].append(entry("extra"))
    if plant == "duplicate":
        args["entries"].append(entry(key="other"))
    if plant == "receipt":
        args["receipts"] = {}
    if plant == "output":
        args["outputs"] = {}
    if plant == "table":
        args["catalogue"] = set()
    if plant == "orphan":
        args["receipts"]["biz_register"] = receipt(entry("biz_register"))
    assert failures(c.check(**args))


@pytest.mark.parametrize(
    "field",
    [
        "sha256",
        "retrieved_utc",
        "publisher",
        "licence_id",
        "title_en",
        "fetch_url",
        "terms_read_on",
        "key",
        "source_id",
        "release_tables",
        "switched_off",
    ],
)
def test_missing_or_substituted_receipt_chain(field):
    args = inputs()
    args["receipts"]["invented"].pop(field)
    assert failures(c.check(**args))


def test_absence_is_exact_and_terms_do_not_exclude():
    args = inputs()
    args["receipts"] = {}
    args["outputs"] = {}
    args["absences"] = {
        "invented": c.Absence("Invented access failure", "invented_caveat")
    }
    assert {
        "id": "invented",
        "state": "NO_DATA",
        "reason": "Invented access failure",
    } in c.check(**args)
    assert not failures(c.check(**args))
    for absence in (c.Absence("", "invented_caveat"), c.Absence("reason", "")):
        args["absences"]["invented"] = absence
        assert failures(c.check(**args))
    for words in ("Invented prohibitive terms", "not yet read"):
        args = inputs()
        args["entries"] = [
            entry(
                terms_words=words,
                licence_basis="owner_decision",
                decision_record="0026",
            )
        ]
        args["receipts"] = {"invented": receipt(args["entries"][0])}
        assert not failures(c.check(**args))
        args["receipts"]["invented"]["switched_off"] = True
        assert failures(c.check(**args))


@pytest.mark.parametrize(
    "source", ["traffic_tomtom_flow", "traffic_tomtom_range", "tiles3d_google"]
)
def test_forbidden_rows_and_files(source):
    args = inputs()
    args["cached_source_ids"] = (source,)
    assert failures(c.check(**args))
    args["cached_source_ids"] = ()
    args["entries"].append(entry(source))
    assert failures(c.check(**args))


def test_citation_only_and_component_rows():
    args = inputs()
    row = entry(kind="citation_only", release_tables=())
    args["entries"] = [row]
    args["receipts"] = {row.key: {**receipt(row), "sha256": "CITATION_ONLY"}}
    args["outputs"] = {}
    assert not failures(c.check(**args))
    args = inputs()
    component = entry(key="invented/part")
    args["entries"].append(component)
    args["receipts"][component.key] = receipt(component)
    args["outputs"][component.key] = ("pub_invented",)
    assert failures(c.check(**args))
    assert not failures(
        c.check(**args, component_keys={"invented": frozenset({"invented/part"})})
    )


def test_pack_reader_covers_all_three_inventory_sections():
    text = """## 2. Source registry
`traffic_tomtom_flow` has no row in `source_registry` and no file.
### 2.1 Identity, fetch and licence
| source_id | Dataset | Publisher | How fetched | Licence |
|---|---|---|---|---|
| `invented` | invented | invented | file | invented |
| `family` | invented | invented | portal `slug-a`, `slug-b` | invented |
### 2.2 Coverage
| `wrong` | not an inventory |
### 2.3 Trade and benchmark source plan — invented
| Planned source_id | Publisher | Use |
| `trade` | invented | invented |
### 2.4 Public pages outside the registry — invented
| Planned source ID | Publisher | Use |
| `pages` | invented | invented |
## 3. Other
| `later` | excluded |
"""
    pack = c.pack_sources(text, {"family": 2})
    assert pack.sources == {
        "invented": (),
        "family": ("slug-a", "slug-b"),
        "trade": (),
        "pages": (),
    }
    assert "traffic_tomtom_flow" in pack.forbidden
    with pytest.raises(ValueError, match="pack_section_missing"):
        c.pack_sources(text.replace("### 2.4", "### absent"), {"family": 2})


def test_family_each_side_and_total_have_independent_checks():
    args = inputs()
    rows = [
        entry("family", key=f"family/slug-{i}", slug=f"slug-{i}") for i in range(77)
    ]
    args.update(
        entries=rows,
        pack=c.Pack({"family": tuple(r.slug for r in rows)}, frozenset()),
        inventory={"family": tuple(r.slug for r in rows)},
        receipts={r.key: receipt(r) for r in rows},
        outputs={r.key: ("pub_invented",) for r in rows},
    )
    assert not failures(c.check(**args, family_counts={"family": 77}))
    args["entries"] = rows[:-1]
    args["pack"] = c.Pack({"family": tuple(r.slug for r in rows[:-1])}, frozenset())
    assert failures(c.check(**args, family_counts={"family": 77}))


def test_duplicate_slugs_cannot_satisfy_family_counts():
    args = inputs()
    rows = [
        entry("family", key=f"family/part-{i}", slug="same-slug") for i in range(77)
    ]
    args.update(
        entries=rows,
        pack=c.Pack({"family": tuple(r.slug for r in rows)}, frozenset()),
        inventory={"family": tuple(r.slug for r in rows)},
        receipts={r.key: receipt(r) for r in rows},
        outputs={r.key: ("pub_invented",) for r in rows},
    )
    assert failures(c.check(**args, family_counts={"family": 77}))


def test_table_catalogue_is_read_from_its_anchor_only():
    assert c.table_catalogue(
        "### 7.2 Table catalogue\n| `pub_invented` | Public |\n### 7.3 Next\n| `wrong` | Public |"
    ) == {"pub_invented"}


def test_existing_expectations_are_imported_and_not_copied():
    from custodian.tests import test_publicdata_registry as existing

    families, required = c.independent_inventory()
    assert families is existing.FAMILY_COUNTS
    assert existing.DECISION_0019 | existing.CITATIONS <= required
    assert {
        "insurance_tables",
        "awards_owner_scrape",
        "accident",
        "un_comtrade",
        "bldg_wsf3d",
    } <= required


def test_committed_derived_policy_only_for_declared_sources():
    assert c.committed_derived_check({"ordinary": {"text": "invented"}}, []) == []
    for row in (entry(), entry(commit_allowed=True, licence_basis="owner_decision")):
        assert c.committed_derived_check(
            {"derived": {"source_id": "invented", "value": "9"}}, [row]
        )
    assert not c.committed_derived_check(
        {"derived": {"source_id": "invented", "value": "9"}},
        [entry(commit_allowed=True)],
    )
    assert c.committed_derived_check(
        {"derived": {"nested": [{"source_id": "missing"}]}}, []
    )
