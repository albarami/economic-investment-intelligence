"""The release-spec draft over invented phase records passes the producer."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import public_release_fixture as fixture
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from public_assembly_fixture import dump, inputs

from eii_core.manifest import CATALOGUE
from eii_custodian.release import producer
from eii_custodian.release.spec_draft import DRAFT, draft

PHASE = "assembly/gis_property_singles.json"


def setup(cache: Path) -> tuple[dict, dict]:
    """Invented inputs without a spec: the paths listing carries no hash."""
    spec = inputs(cache)
    (cache / producer.SPEC).unlink()
    listing = {
        key: dict(
            format=ref["format"],
            receipt=ref["receipt"]["path"],
            body=ref["body"]["path"],
        )
        for key, ref in spec["sources"].items()
    }
    return spec, listing


def promote(cache: Path) -> dict:
    """The lead's two steps: fill the scalars and rename the reviewed draft."""
    document = json.loads((cache / DRAFT).read_bytes())
    document["scalars"] = dict(fixture._scalars(), code_version="cd" * 20)
    dump(cache / producer.SPEC, document)
    (cache / DRAFT).unlink()
    return producer.prepare(cache)


def test_draft_passes_the_producer_spec_checks_unchanged(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    spec, listing = setup(cache)
    document = draft(cache, listing)
    assert document["scalars"] == dict(release_contract_version="release.v1")
    assert document["sources"] == spec["sources"]
    assert document["tables"] == [
        dict(
            name="pub_bank_credit",
            phase="gis_property_singles",
            columns=[
                dict(name="period", logical_type="string", nullable=False),
                dict(name="value", logical_type="string", nullable=False),
            ],
            source_keys=["INVENTED-source"],
        )
    ]
    assert document["artefacts"] == []
    assert not (cache / producer.APPROVAL).exists()
    candidate = promote(cache)
    assert {table["name"] for table in candidate["tables"]} == {
        "pub_bank_credit",
        "source_registry",
        "fact_lineage",
    }
    assert not (cache / producer.APPROVAL).exists()


def test_missing_receipt_is_refused(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    _, listing = setup(cache)
    (cache / listing["INVENTED-source"]["receipt"]).unlink()
    with pytest.raises(ValueError, match=r"\Aproducer_receipt_missing\Z"):
        draft(cache, listing)
    assert not (cache / DRAFT).exists()


def test_body_hash_mismatch_is_refused(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    _, listing = setup(cache)
    (cache / listing["INVENTED-source"]["body"]).write_bytes(b"INVENTED-changed")
    with pytest.raises(ValueError, match=r"\Aproducer_hash_mismatch\Z"):
        draft(cache, listing)
    assert not (cache / DRAFT).exists()


def test_unknown_table_is_refused(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    _, listing = setup(cache)
    phase = json.loads((cache / PHASE).read_bytes())
    phase["tables"]["INVENTED_table"] = [dict(period="2026")]
    dump(cache / PHASE, phase)
    with pytest.raises(ValueError, match=r"\Aunknown_table\Z"):
        draft(cache, listing)
    assert not (cache / DRAFT).exists()


def test_existing_draft_is_never_overwritten(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    _, listing = setup(cache)
    dump(cache / DRAFT, dict(INVENTED="earlier"))
    before = (cache / DRAFT).read_bytes()
    with pytest.raises(ValueError, match=r"\Aspec_draft_exists\Z"):
        draft(cache, listing)
    assert (cache / DRAFT).read_bytes() == before


def test_listing_key_absent_from_phase_records_is_refused(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    _, listing = setup(cache)
    listing["INVENTED-other"] = listing["INVENTED-source"]
    with pytest.raises(ValueError, match=r"\Aproducer_chain_incomplete\Z"):
        draft(cache, listing)


def test_table_source_absent_from_listing_is_refused(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    _, _listing = setup(cache)
    with pytest.raises(ValueError, match=r"\Aproducer_chain_incomplete\Z"):
        draft(cache, {})


@pytest.mark.parametrize(
    "rows",
    [[], [dict(value=1.5)], [dict(value=1), dict(value="1")], [dict(value=None)]],
    ids=["empty", "decimal", "mixed", "all-null"],
)
def test_untypable_column_is_refused(tmp_path, rows):
    cache = tmp_path / "INVENTED-cache"
    _, listing = setup(cache)
    phase = json.loads((cache / PHASE).read_bytes())
    phase["tables"]["pub_bank_credit"] = rows
    (cache / PHASE).write_text(json.dumps(phase))  # a float, as a JSON number
    with pytest.raises(ValueError, match=r"\Acolumn_type_unknown\Z"):
        draft(cache, listing)


def rewrite(cache, mutate):
    phase = json.loads((cache / PHASE).read_bytes())
    mutate(phase)
    dump(cache / PHASE, phase)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda phase: phase["tables"].update(pub_bank_credit=["INVENTED-row"]),
        lambda phase: phase.update(tables=["INVENTED-table"]),
        lambda phase: phase["source_chain"].update({"INVENTED-source": "INVENTED"}),
    ],
    ids=["row-not-object", "tables-not-object", "chain-link-not-object"],
)
def test_malformed_phase_record_is_refused(tmp_path, mutate):
    cache = tmp_path / "INVENTED-cache"
    _, listing = setup(cache)
    rewrite(cache, mutate)
    with pytest.raises(ValueError, match=r"\Aproducer_schema_refused\Z"):
        draft(cache, listing)


def test_listing_entry_with_a_hash_is_refused(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    _, listing = setup(cache)
    listing["INVENTED-source"]["sha256"] = "ab" * 32
    with pytest.raises(ValueError, match=r"\Aproducer_schema_refused\Z"):
        draft(cache, listing)


def test_phase_records_without_tables_are_refused(tmp_path):
    cache = tmp_path / "INVENTED-cache"
    _, listing = setup(cache)
    rewrite(cache, lambda phase: phase.update(tables={}))
    with pytest.raises(ValueError, match=r"\Aproducer_chain_incomplete\Z"):
        draft(cache, listing)


def test_command_mode_never_writes_the_approval(tmp_path, capsys):
    from commands.main import main

    cache = tmp_path / "data/public_cache"
    _, listing = setup(cache)
    paths = tmp_path / "INVENTED-listing.json"
    paths.write_text(json.dumps(listing))
    assert main(["build-release", "--spec-draft", str(paths)], {}, tmp_path) == 0
    assert (cache / DRAFT).is_file()
    assert not (cache / producer.APPROVAL).exists()
    capsys.readouterr()
    assert main(["build-release", "--spec-draft", str(paths)], {}, tmp_path) == 4
    shown = capsys.readouterr()
    assert "spec_draft_exists" in shown.out + shown.err


_PUBLIC = sorted(
    row.name
    for row in CATALOGUE
    if row.manifest_class == "public" and row.writer == "publicdata"
)
_KINDS = (
    st.booleans(),
    st.integers(-(2**31), 2**31),
    st.text(alphabet="INVETDab-", min_size=1, max_size=6).map("INVENTED-".__add__),
)


@st.composite
def phase_sets(draw):
    """Distinct catalogue tables spread over phases, each with typed columns."""
    names = draw(
        st.lists(st.sampled_from(_PUBLIC), min_size=1, max_size=3, unique=True)
    )
    phases = {}
    for name in names:
        phase = draw(st.sampled_from(["frame", "gis_property_singles", "fsq"]))
        width = draw(st.integers(1, 3))
        kinds = [draw(st.sampled_from(_KINDS)) for _ in range(width)]
        rows = []
        for _ in range(draw(st.integers(1, 3))):
            row = {}
            for index, kind in enumerate(kinds):
                row["c" + str(index)] = draw(kind)
            rows.append(row)
        phases.setdefault(phase, {})[name] = rows
    return phases


@settings(max_examples=25)
@given(phase_sets())
def test_any_phase_record_set_drafts_a_spec_the_producer_accepts(phases):
    with tempfile.TemporaryDirectory(prefix="INVENTED-draft-") as folder:
        cache = Path(folder) / "INVENTED-cache"
        _, listing = setup(cache)
        chain = json.loads((cache / PHASE).read_bytes())["source_chain"]
        (cache / PHASE).unlink()
        for phase, tables in phases.items():
            dump(
                cache / "assembly" / (phase + ".json"),
                dict(
                    method="public-assembly." + phase,
                    method_version="1",
                    source_chain=chain,
                    tables=tables,
                ),
            )
        document = draft(cache, listing)
        owners = {item["name"]: item["phase"] for item in document["tables"]}
        assert owners == {
            name: phase for phase, tables in phases.items() for name in tables
        }
        candidate = promote(cache)
        assert {table["name"] for table in candidate["tables"]} == {
            *owners,
            "source_registry",
            "fact_lineage",
        }
        assert not (cache / producer.APPROVAL).exists()
