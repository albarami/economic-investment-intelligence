"""INVENTED rows only; never run the lead's real-cache data tests here."""

import json
from decimal import Decimal as D

import pytest
from custodian.data_tests import cache
from custodian.data_tests import test_pinned_methods as methods
from custodian.tests.test_method_cache import _write_cached_source


def c1_fixture(tmp_path):
    review = tmp_path / "review"
    review.mkdir()
    (review / "municipality_names.csv").write_text(
        "name,municipality_code\nINVENTED first,INV-A\nINVENTED second,INV-B\n"
    )
    (review / "population_indicators.csv").write_text(
        "indicator,mapped_indicator\nPopulation,residents\nEmployed,employed\n"
    )
    active = []
    for name, counts in (
        ("INVENTED first", (40, 20, 140)),
        ("INVENTED second", (60, 30, 710)),
    ):
        for code, count in zip(("5610101", "5630112", "561000"), counts, strict=True):
            active.append(
                {
                    "lbldy": name,
                    "rmz_lnsht_ltjry": code,
                    "lnsht_ltjry": "INVENTED activity",
                    "dd_lrkhs_lnsht": count,
                }
            )
    population = []
    for name, count in (("INVENTED first", 1000), ("INVENTED second", 4000)):
        for year, indicator, value in (
            ("2025", "Population", count),
            ("2020", "Population", 999),
            ("2025", "Employed", 777),
        ):
            population.append(
                {
                    "year": year,
                    "municipality": name,
                    "lbldy": name,
                    "indicator": indicator,
                    "lmw_shr": indicator,
                    "count": value,
                }
            )
    return review, active, population


def c1_readings(tmp_path):
    review, active, population = c1_fixture(tmp_path)
    pins = {
        source: _write_cached_source(tmp_path, source, rows)
        for source, rows in (("lic_active", active), ("pop_muni", population))
    }
    (tmp_path / "method_pins.json").write_text(json.dumps(pins))
    active_rows, active_chain = cache.cached(tmp_path, "lic_active", pins["lic_active"])
    population_rows, population_chain = cache.cached(
        tmp_path, "pop_muni", pins["pop_muni"]
    )
    return review, active_rows, active_chain, population_rows, population_chain


def test_c1_replay_uses_population_schema_and_all_activities(tmp_path):
    review, active, active_chain, population, population_chain = c1_readings(tmp_path)
    result = methods.c1_replay(
        active, active_chain, population, population_chain, review, "INVENTED first"
    )
    assert result["local_all"] == D(200)
    assert result["national_all"] == D(1000)
    assert result["local_restaurants"] == D(40)
    assert result["national_restaurants"] == D(100)
    assert result["local_coffee"] == D(20)
    assert result["national_coffee"] == D(50)
    assert result["local_population"] == D(1000)
    assert result["national_population"] == D(5000)
    assert [fact.value for fact in result["density"]] == [D(400), D(200)]
    assert [fact.value for fact in result["lq"]] == [D("2.00"), D("2.00")]
    for fact in (*result["density"], *result["lq"]):
        assert fact.period == "2025"
    assert result["density"][0].sources == (active_chain, population_chain)
    assert result["lq"][0].sources == (active_chain,)
    assert result["density"][0].geography == "municipality:INV-A"
    assert result["density"][1].geography == "national"


@pytest.mark.parametrize(
    "plant", ["missing", "duplicate", "wrong_year", "wrong_indicator"]
)
def test_c1_population_plants(tmp_path, plant):
    review, active, active_chain, population, population_chain = c1_readings(tmp_path)
    methods.c1_replay(
        active, active_chain, population, population_chain, review, "INVENTED first"
    )
    target = next(
        row
        for row in population
        if row["municipality"] == "INVENTED first"
        and row["year"] == "2025"
        and row["indicator"] == "Population"
    )
    if plant == "missing":
        population.remove(target)
    elif plant == "duplicate":
        population.append(dict(target))
    elif plant == "wrong_year":
        target["year"] = "2024"
    else:
        target["indicator"] = "Employed"
    with pytest.raises(ValueError, match=r"C1:population_(missing|duplicate)"):
        methods.c1_replay(
            active, active_chain, population, population_chain, review, "INVENTED first"
        )


def test_c1_national_population_requires_other_municipalities(tmp_path):
    review, active, active_chain, population, population_chain = c1_readings(tmp_path)
    population = [r for r in population if r["municipality"] == "INVENTED first"]
    with pytest.raises(ValueError, match="C1:population_missing"):
        methods.c1_replay(
            active, active_chain, population, population_chain, review, "INVENTED first"
        )


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("missing_active_target", "C1:municipality_missing"),
        ("unreviewed_population", "C1:population_indicator_unreviewed"),
    ],
)
def test_c1_replay_requires_reviewed_target_and_indicator(tmp_path, plant, reason):
    review, active, active_chain, population, population_chain = c1_readings(tmp_path)
    methods.c1_replay(
        active, active_chain, population, population_chain, review, "INVENTED first"
    )
    if plant == "missing_active_target":
        active = [r for r in active if r["lbldy"] != "INVENTED first"]
    else:
        population[0]["indicator"] = "INVENTED unreviewed indicator"
    with pytest.raises(ValueError, match=reason):
        methods.c1_replay(
            active, active_chain, population, population_chain, review, "INVENTED first"
        )


@pytest.mark.parametrize("plant", ["unknown_field", "wrong_type", "missing_field"])
def test_c1_population_cache_refuses_wrong_shape(tmp_path, plant):
    _, _, population = c1_fixture(tmp_path)
    if plant == "unknown_field":
        population[0]["INVENTED extra"] = "INVENTED"
    elif plant == "wrong_type":
        population[0]["count"] = "1000"
    else:
        del population[0]["municipality"]
    digest = _write_cached_source(tmp_path, "pop_muni", population)
    with pytest.raises(ValueError, match="pop_muni:"):
        cache.cached(tmp_path, "pop_muni", digest)


def test_c1_population_uses_pinned_older_snapshot(tmp_path, monkeypatch):
    _, _, population = c1_fixture(tmp_path)
    digest = _write_cached_source(tmp_path, "pop_muni", population)
    population[0]["count"] = 2000
    _write_cached_source(tmp_path, "pop_muni", population)
    (tmp_path / "method_pins.json").write_text(json.dumps({"pop_muni": digest}))
    monkeypatch.setattr(cache, "CACHE", tmp_path)
    rows, chain = cache.pinned("pop_muni")
    assert rows[0]["count"] == 1000
    assert chain.sha256 == digest
    (tmp_path / "pop_muni" / f"{digest}.json").write_text("[]")
    with pytest.raises(ValueError, match="receipt_hash_mismatch:pop_muni"):
        cache.pinned("pop_muni")


def test_c1_card_prints_both_missing_denominators():
    card = (
        (cache.ROOT / "docs/07_ECONOMIC_METHODS.md")
        .read_text()
        .split("### C1 Licence density and location quotient", 1)[1]
        .split("### C2 Licence churn", 1)[0]
    )
    assert "| All licence-activities, Al Daayen | 13,600 |" in card
    assert "| Coffee shops (5630112), national | 1,042 |" in card
