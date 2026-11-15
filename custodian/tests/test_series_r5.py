"""L-222/L-235 plants use only invented customs lines and descriptions."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from custodian.tests.test_baskets import invented_review
from custodian.tests.test_public_series import series_cache

from eii_custodian.publicdata.series.baskets import reviewed_inputs
from eii_custodian.publicdata.series.figures import (
    basket_exclusion_review,
    build_series,
)
from eii_custodian.publicdata.series.parse import country_crosswalk, selected_source


def source_rows():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text()
    )["cus_imp_2025"][0]
    return [
        dict(
            fixture,
            harmonized_system_code=int(code.replace(".", "")),
            details=en,
            ltfsyl=ar,
        )
        for code, en, ar in [
            ("19.02.11.10.00.01", "invented pasta", "معكرونة تجريبية"),
            ("19.02.11.10.00.02", "invented excluded", "مستبعد تجريبي"),
        ]
    ]


def write_review(tmp_path, doc):
    path = tmp_path / "review.json"
    path.write_text(json.dumps(doc, ensure_ascii=False))
    return path


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("missing_code", "basket_line_source_mismatch"),
        ("description", "basket_line_source_mismatch"),
        ("pair", "basket_line_source_mismatch"),
        ("unreviewed", "basket_line_unreviewed"),
        ("duplicate", "basket_line_duplicate"),
    ],
)
def test_source_review_plants(tmp_path, plant, reason):
    doc, rows = invented_review(), source_rows()
    item = doc["activities"][0]["inputs"][0]
    if plant == "missing_code":
        item["excluded_lines"].append(
            {"code": "99.99.99.99.00.01", "reason": "invented exclusion"}
        )
    elif plant == "description":
        item["lines"][0]["description_ar"] += " changed"
    elif plant == "pair":
        rows.append(dict(rows[0], details="invented other", ltfsyl="تجريبي آخر"))
        item["lines"][0]["description_ar"] = "تجريبي آخر"
    elif plant == "unreviewed":
        rows.append(dict(rows[0], harmonized_system_code=int("190211100003")))
    else:
        doc["activities"][0]["inputs"].append(deepcopy(item))
    path = write_review(tmp_path, doc)
    with pytest.raises(ValueError, match=reason) as error:
        basket_exclusion_review(rows, path)
    assert "5610" in str(error.value) and "invented pasta" in str(error.value)


@pytest.mark.parametrize("text", ['"invented', 'invented "middle', 'invented ""double'])
def test_quotes_end_to_end(tmp_path, text):
    rows, doc = source_rows(), invented_review()
    rows[0].update(details=text, ltfsyl=text + " تجريبي")
    for activity in doc["activities"]:
        activity["inputs"][0]["lines"][0].update(
            description_en=" " + text + " ", description_ar=" " + text + " تجريبي "
        )
    review = write_review(tmp_path, doc)
    assert basket_exclusion_review(rows, review)
    entry, digest = series_cache(tmp_path, "cus_imp_2025", rows)
    loaded, _ = selected_source(tmp_path, entry, digest)
    assert loaded == rows
    build_series(tmp_path, [entry], {entry.key: digest}, basket_review=review)
    table = json.loads(
        (tmp_path / "series/internal/pub_customs_import.json").read_text()
    )
    assert table["rows"][0]["description_en"] == text
    assert table["rows"][0]["description_ar"] == text + " تجريبي"
    assert json.loads(review.read_text()) == doc


def test_review_no_keyword_or_current_hash_gate(tmp_path):
    doc, rows = invented_review(), source_rows()
    rows[0].update(details="invented shapes", ltfsyl="أشكال تجريبية")
    for activity in doc["activities"]:
        activity["inputs"][0]["lines"][0].update(
            description_en=rows[0]["details"], description_ar=rows[0]["ltfsyl"]
        )
    assert basket_exclusion_review(rows, write_review(tmp_path, doc))


def test_installed_review_has_metadata():
    doc = json.loads(
        (
            Path(__file__).resolve().parents[1] / "publicdata/review/baskets.yaml"
        ).read_text()
    )
    assert "owner's confirmation" in doc["status"]
    items = [
        item
        for activity in ("5610", "5630", "5510")
        for item in reviewed_inputs(doc, activity)
    ]
    assert len(items) == 24
    assert sum(len(item["lines"]) for item in items) == 74
    assert sum(len(item["excluded_lines"]) for item in items) == 96


@pytest.mark.parametrize(
    "reason",
    ["ambiguous", "no_code_in_reference", "not_a_country", "part_of_a_country"],
)
def test_explicit_null_alias(tmp_path, reason):
    path = tmp_path / "aliases.csv"
    path.write_text(
        "name_en,iso3,human_reviewed,reason\nItaly invented part,,false,"
        + reason
        + "\n"
    )
    crosswalk = country_crosswalk(aliases=path)
    assert "Italy invented part" in crosswalk
    assert crosswalk["Italy invented part"] is None
    assert crosswalk["Italy"] == "ITA"


@pytest.mark.parametrize("reason", ["", "invented_reason"])
def test_empty_alias_requires_closed_reason(tmp_path, reason):
    path = tmp_path / "aliases.csv"
    path.write_text(
        "name_en,iso3,human_reviewed,reason\nInvented sixth,,false," + reason + "\n"
    )
    with pytest.raises(ValueError, match="country alias: invalid unattributed reason"):
        country_crosswalk(aliases=path)


@pytest.mark.parametrize("source", ["cus_imp_2025", "cus_imp_2019"])
def test_country_totals_preserve_unattributed_rows(tmp_path, source, monkeypatch):
    # Invented source spellings; an explicit null must never prefix-match Italy.
    import eii_custodian.publicdata.series.figures as figures

    monkeypatch.setattr(
        figures,
        "country_crosswalk",
        lambda: {"invented mapped": "ITA", "Italy invented part": None},
    )
    fixtures = json.loads(
        (Path(__file__).parent / "fixtures/series/confirmed_shapes.json").read_text()
    )
    row = fixtures[source][0]
    if source == "cus_imp_2019":
        row["hs8"] = "1" * 8
    rows = [
        dict(row, country_of_origin=name)
        for name in (
            "invented mapped",
            "Italy invented part",
            "Italy invented part",
            None,
        )
    ]
    review = write_review(
        tmp_path,
        {
            "activities": [
                {"activity": a, "inputs": []} for a in ("5610", "5630", "5510")
            ]
        },
    )
    entry, digest = series_cache(tmp_path, source, rows)
    build_series(tmp_path, [entry], {entry.key: digest}, basket_review=review)
    table = json.loads(
        (tmp_path / "series/internal/pub_customs_import.json").read_text()
    )
    assert [r["origin_iso3"] for r in table["rows"]] == ["ITA", None, None, None]
    totals = json.loads(
        (tmp_path / ("series/internal/" + source + ".country_totals.json")).read_text()
    )
    assert [r["country"] for r in totals["rows"]] == [
        "ITA",
        "not attributed to a country",
    ]
    assert [r["row_count"] for r in totals["rows"]] == [1, 3]
    from decimal import Decimal

    value = Decimal(
        str(row["value_qr" if source == "cus_imp_2019" else "value_in_qatari_riyals"])
    )
    assert [Decimal(r["value_qar"]) for r in totals["rows"]] == [value, value * 3]
    weight = Decimal(
        str(row["weight_kg" if source == "cus_imp_2019" else "weight_in_kilograms"])
    )
    quantity = Decimal(str(row["quantity"]))
    assert [Decimal(r["weight_kg"]) for r in totals["rows"]] == [weight, weight * 3]
    assert [Decimal(r["quantity"]) for r in totals["rows"]] == [quantity, quantity * 3]
    assert totals["source_chain"][0]["sha256"] == digest


def test_build_source_review_is_not_conditional_on_pub65(tmp_path):
    rows, doc = source_rows(), invented_review()
    rows[0]["year"] = "2026"
    doc["activities"][2]["inputs"][0]["lines"][0]["description_en"] = (
        "invented mismatch"
    )
    entry, digest = series_cache(tmp_path, "cus_imp_2025", rows)
    with pytest.raises(ValueError, match="basket_line_source_mismatch: 5510"):
        build_series(
            tmp_path,
            [entry],
            {entry.key: digest},
            basket_review=write_review(tmp_path, doc),
        )
    assert not list((tmp_path / "series/display").iterdir())


@pytest.mark.parametrize("activity", ["5610", "5630", "5510"])
def test_each_activity_source_checked(tmp_path, activity):
    doc, rows = invented_review(), source_rows()
    next(a for a in doc["activities"] if a["activity"] == activity)["inputs"][0][
        "lines"
    ][0]["description_en"] += " altered"
    with pytest.raises(ValueError, match="basket_line_source_mismatch: " + activity):
        basket_exclusion_review(rows, write_review(tmp_path, doc))


def test_source_trims_only_ends_and_accepts_alternative_pair(tmp_path):
    rows, doc = source_rows(), invented_review()
    rows[0].update(details="  invented pasta\t", ltfsyl="\nمعكرونة تجريبية ")
    rows.append(dict(rows[0], details="invented alternative", ltfsyl="بديل تجريبي"))
    rows.append(dict(rows[0], harmonized_system_code=1))
    assert basket_exclusion_review(rows, write_review(tmp_path, doc))
    for activity in doc["activities"]:
        activity["inputs"][0]["lines"][0].update(
            description_en="invented alternative", description_ar="بديل تجريبي"
        )
    assert basket_exclusion_review(rows, write_review(tmp_path, doc))
    for value in ("Invented alternative", "invented  alternative"):
        doc["activities"][0]["inputs"][0]["lines"][0]["description_en"] = value
        with pytest.raises(ValueError, match="basket_line_source_mismatch"):
            basket_exclusion_review(rows, write_review(tmp_path, doc))


@pytest.mark.parametrize("kind", ["included_twice", "excluded_twice", "both"])
def test_duplicates_within_input(tmp_path, kind):
    rows, doc = source_rows(), invented_review()
    item = doc["activities"][0]["inputs"][0]
    if kind == "included_twice":
        item["lines"].append(deepcopy(item["lines"][0]))
    elif kind == "excluded_twice":
        item["excluded_lines"].append(deepcopy(item["excluded_lines"][0]))
    else:
        item["excluded_lines"].append(
            {"code": item["lines"][0]["code"], "reason": "invented exclusion"}
        )
    with pytest.raises(ValueError, match="basket_line_duplicate"):
        basket_exclusion_review(rows, write_review(tmp_path, doc))


def test_pub65_uses_source_review_result(tmp_path):
    rows, doc = source_rows(), invented_review()
    rows[0]["country_of_origin"] = "Italy"
    rows[1]["country_of_origin"] = "Saudi Arabia"
    entry, digest = series_cache(tmp_path, "cus_imp_2025", rows)
    result = build_series(
        tmp_path,
        [entry],
        {entry.key: digest},
        basket_review=write_review(tmp_path, doc),
    )
    assert result["checks"]["PUB-65"]["basket_excludes_noodles"] == "true"
    for activity in doc["activities"]:
        activity["inputs"] = []
    result = build_series(
        tmp_path,
        [entry],
        {entry.key: digest},
        basket_review=write_review(tmp_path, doc),
    )
    assert result["checks"]["PUB-65"]["basket_excludes_noodles"] == "false"
