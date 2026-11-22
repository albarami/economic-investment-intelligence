"""Invented generator inputs; committed citation metadata integration, without data/."""

import json
from copy import deepcopy
from decimal import Decimal

import pytest
import yaml
from hypothesis import example, given
from hypothesis import strategies as st

import landmark_citation_rows as generator
from eii_custodian.publicdata.fetch import allowlist, page_records, registry
from eii_custodian.publicdata.fetch.page_acquire import validate_entry
from eii_custodian.publicdata.fetch.page_schema import validate
from eii_custodian.publicdata.heights import landmarks
from eii_custodian.publicdata.heights.model import HeightError

URL = "https://syn.example.invalid/one"
OPEN_WORDS = (
    "Text is available under the Creative Commons Attribution-ShareAlike "
    "4.0 License; additional terms may apply."
)


def research():
    return {
        "publishers": [
            {
                "publisher": "SYN Publisher",
                "terms_url": "https://syn.example.invalid/terms",
                "terms_words": "SYN all rights reserved",
                "checked_on": "2026-11-22",
                "note": "SYN reading only",
            }
        ],
        "landmarks": [
            {
                "page_url": URL,
                "publisher": "SYN Publisher",
                "second_page": {
                    "page_url": URL + "-two",
                    "publisher": "SYN Publisher",
                },
                # Source records must never be copied into citation metadata.
                "name_en": "SYN landmark",
                "height_m": "123.4",
                "height_excerpt": "SYN roof: 123.4 m",
            }
        ],
    }


def test_generator_emits_distinct_pages_same_publisher_and_closed_declarations():
    document = research()
    original = deepcopy(document)
    output = generator.generate(document)
    rows = output["sources"]
    assert document == original
    assert {row["url"] for row in rows} == {URL, URL + "-two"}
    assert len({row["key"] for row in rows}) == 2
    assert {row["source_id"] for row in rows} == {"landmark_syn_publisher"}
    assert output["hosts"] == ["syn.example.invalid"]
    assert "SYN landmark" not in str(output)
    assert "123.4" not in str(output)
    for row in rows:
        assert row["kind"] == "public_page"
        assert row["licence_basis"] == "owner_decision"
        assert row["decision_record"] == "0026"
        assert row["commit_allowed"] is False
        assert row["columns"] == row["release_tables"] == []
        assert row["period_first"] == row["period_last"] == row["period_field"] == ""
        assert row["terms_words"] == "SYN all rights reserved"
        declaration = output["declarations"][row["key"]]
        validate(declaration)
        assert declaration["kind"] == "citation_snapshot"
        assert declaration["columns"] == declaration["period_fields"] == []
        assert declaration["shape"] == {}
        assert declaration["url"] == row["url"]


def test_open_licence_and_unread_terms_remain_truthful():
    document = research()
    publisher = document["publishers"][0]
    publisher["terms_words"] = OPEN_WORDS
    row = generator.generate(document)["sources"][0]
    assert (row["licence_id"], row["licence_basis"], row["decision_record"]) == (
        "CC-BY-SA-4.0",
        "dataset",
        "",
    )
    assert row["commit_allowed"] is False
    publisher.update(terms_url=None, terms_words="terms_not_found")
    row = generator.generate(document)["sources"][0]
    assert row["terms_url"] == ""
    assert row["terms_words"] == registry.TERMS_WORDS_PENDING
    assert row["terms_read_on"] == "2026-11-22"
    assert row["licence_basis"] == "owner_decision"
    assert row["skip_reason"] == ""


@pytest.mark.parametrize(
    "case,reason",
    [
        ("root", "citation_research_shape"),
        ("publishers", "citation_research_shape"),
        ("landmarks", "citation_research_shape"),
        ("candidate", "citation_research_shape"),
        ("publisher", "citation_publisher_shape"),
        ("publisher_row", "citation_publisher_shape"),
        ("words", "citation_publisher_shape"),
        ("date", "citation_publisher_shape"),
        ("date_shape", "citation_publisher_shape"),
        ("note", "citation_publisher_shape"),
        ("terms_type", "citation_publisher_shape"),
        ("slug_empty", "citation_publisher_shape"),
        ("duplicate", "citation_publisher_duplicate"),
        ("slug_collision", "citation_publisher_duplicate"),
        ("page_type", "citation_page_shape"),
        ("page_publisher_type", "citation_page_shape"),
        ("unknown", "citation_publisher_unknown"),
        ("page_url", "citation_url_shape"),
        ("terms_url", "citation_url_shape"),
        ("conflict", "citation_page_publisher_conflict"),
    ],
)
def test_generator_refusals_change_one_input(case, reason):
    document = research()
    publisher = document["publishers"][0]
    page = document["landmarks"][0]
    if case == "root":
        document = []
    elif case in {"publishers", "landmarks"}:
        document[case] = None
    elif case == "candidate":
        document["landmarks"][0] = None
    elif case == "publisher":
        publisher["publisher"] = None
    elif case == "publisher_row":
        document["publishers"][0] = None
    elif case == "words":
        publisher["terms_words"] = None
    elif case == "date":
        publisher["checked_on"] = "2026-02-30"
    elif case == "date_shape":
        publisher["checked_on"] = "2026-W47-7"
    elif case == "note":
        publisher["note"] = []
    elif case == "terms_type":
        publisher["terms_url"] = []
    elif case == "slug_empty":
        publisher["publisher"] = "!!!"
    elif case == "duplicate":
        document["publishers"].append(dict(publisher))
    elif case == "slug_collision":
        document["publishers"].append(dict(publisher, publisher="SYN-Publisher"))
    elif case == "page_type":
        page["page_url"] = None
    elif case == "page_publisher_type":
        page["publisher"] = None
    elif case == "unknown":
        page["publisher"] = "SYN unknown"
    elif case == "page_url":
        page["page_url"] = "http://syn.example.invalid/one"
    elif case == "terms_url":
        publisher["terms_url"] = "http://syn.example.invalid/terms"
    elif case == "conflict":
        document["publishers"].append(dict(publisher, publisher="SYN other"))
        # The primary and secondary initially cite the same URL and publisher.
        page["second_page"]["page_url"] = URL
        assert generator.generate(document)
        page["second_page"]["publisher"] = "SYN other"
    with pytest.raises(ValueError, match="^" + reason + "$"):
        generator.generate(document)


@given(st.lists(st.text(alphabet="abcxyz-_", min_size=1, max_size=15), max_size=12))
@example([])
@example(["a"])
@example(["a", "a"])
@example(["b", "a"])
def test_page_set_and_order_invariant(paths):
    document = research()
    document["landmarks"] = [
        {"publisher": "SYN Publisher", "page_url": URL + "/" + path} for path in paths
    ]
    output = generator.generate(document)
    assert {row["url"] for row in output["sources"]} == {
        URL + "/" + path for path in paths
    }
    assert len(output["sources"]) == len(set(paths))
    document["landmarks"].reverse()
    assert generator.generate(document) == output


@pytest.mark.parametrize(
    "url",
    [
        "http://syn.example.invalid/one",
        "https:///one",
        "https://syn.example.invalid/one?x=y",
        "https://syn.example.invalid/one#x",
        "https://" + "@".join(("user", "syn.example.invalid/one")),
        "https://syn.example.invalid:444/one",
        "https://syn.example.invalid/one two",
        "https://syn.example.invalid:bad/one",
    ],
)
def test_page_url_boundary_classes(url):
    document = research()
    document["landmarks"][0]["page_url"] = url
    with pytest.raises(ValueError, match=r"^citation_url_shape$"):
        generator.generate(document)


def test_publisher_order_and_shared_page():
    document = research()
    document["publishers"].append(
        dict(document["publishers"][0], publisher="SYN other")
    )
    document["landmarks"].append({"page_url": URL + "-other", "publisher": "SYN other"})
    output = generator.generate(document)
    document["publishers"].reverse()
    document["landmarks"].reverse()
    assert generator.generate(document) == output
    document["landmarks"].append(dict(document["landmarks"][0]))
    assert generator.generate(document) == output


def test_empty_research_and_cli(tmp_path):
    assert generator.generate({"publishers": [], "landmarks": []}) == {
        "sources": [],
        "declarations": {},
        "hosts": [],
    }
    source, output = tmp_path / "research.yaml", tmp_path / "output.json"
    source.write_text(yaml.safe_dump(research()))
    assert generator.main([str(source), str(output)]) == 0
    assert json.loads(output.read_text()) == generator.generate(research())


def citation(url, publisher, basis):
    return landmarks.LandmarkHeight(
        "SYN-landmark",
        "SYN-building",
        "SYN name",
        Decimal("123.4"),
        "roof",
        landmarks.LandmarkCitation(
            url, publisher, "2026-11-22", basis, "a" * 64, "SYN roof: 123.4 m"
        ),
    )


def test_host_refuses_at_registry_load(tmp_path, monkeypatch):
    output = generator.generate(research())
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": output["sources"]}))
    monkeypatch.setattr(
        allowlist, "ALLOWED_HOSTS", allowlist.ALLOWED_HOSTS | {"syn.example.invalid"}
    )
    assert len(registry.load_registry(path)) == 2
    monkeypatch.setattr(
        allowlist, "ALLOWED_HOSTS", allowlist.ALLOWED_HOSTS - {"syn.example.invalid"}
    )
    with pytest.raises(registry.RegistryError, match=r"^host_refused$"):
        registry.load_registry(path)


@pytest.mark.parametrize("field", ["url", "landing_url", "terms_url"])
def test_each_registry_url_requires_admitted_host(tmp_path, monkeypatch, field):
    output = generator.generate(research())
    monkeypatch.setattr(
        allowlist, "ALLOWED_HOSTS", allowlist.ALLOWED_HOSTS | {"syn.example.invalid"}
    )
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"sources": output["sources"]}))
    assert registry.load_registry(path)
    output["sources"][0][field] = "https://syn-other.invalid/page"
    path.write_text(yaml.safe_dump({"sources": output["sources"]}))
    with pytest.raises(registry.RegistryError, match=r"^host_refused$"):
        registry.load_registry(path)


def test_committed_landmark_pages_resolve_exactly_once(monkeypatch):
    entries = registry.load_registry()
    declarations = registry.read_yaml(page_records.REVIEW)["sources"]
    pages = {
        key: dec for key, dec in declarations.items() if key.startswith("landmark_")
    }
    assert len(pages) == 70
    rows = [entry for entry in entries if entry.source_id.startswith("landmark_")]
    assert len(rows) == len(pages)
    assert len({entry.source_id for entry in rows}) == 15
    assert len({entry.url for entry in rows}) == len(rows)
    # Keep the real registry-to-URL binding; avoid reparsing it for each page.
    monkeypatch.setattr(registry, "load_registry", lambda: entries)
    for key, declaration in pages.items():
        matching = [
            entry
            for entry in entries
            if declaration["url"] in {entry.url, entry.landing_url}
        ]
        assert len(matching) == 1
        entry = matching[0]
        assert entry.key == key
        assert (
            landmarks._registry_entry(
                citation(entry.url, entry.publisher, entry.licence_basis)
            )
            == entry
        )
        validate_entry(entry, declaration)
        assert (
            not entry.columns and not entry.release_tables and not entry.commit_allowed
        )


def test_missing_page_refuses_registry_row(monkeypatch):
    entries = registry.load_registry()
    row = next(entry for entry in entries if entry.source_id.startswith("landmark_"))
    target = citation(row.url, row.publisher, row.licence_basis)
    monkeypatch.setattr(registry, "load_registry", lambda: entries)
    assert landmarks._registry_entry(target) == row
    monkeypatch.setattr(
        registry,
        "load_registry",
        lambda: tuple(entry for entry in entries if entry != row),
    )
    with pytest.raises(HeightError, match=r"^landmark_heights_citation$") as error:
        landmarks._registry_entry(target)
    assert error.value.detail == "registry_row"
