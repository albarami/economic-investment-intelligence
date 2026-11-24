"""C8 replay proofs on INVENTED OOXML and paged-layer cache pairs only."""

import io
import json
import re
from dataclasses import replace
from decimal import Decimal as D
from fractions import Fraction
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZipFile

import pytest
from custodian.data_tests import test_pinned_methods as methods
from custodian.tests.test_pinned_wilson import CHILD, SENTINEL, summary
from custodian.tests.test_restricted_expectation_guards import child_run
from hypothesis import given
from hypothesis import strategies as st

from eii_core.calc.facts import NoData
from eii_custodian.publicdata.fetch.page_html import ShapeError
from eii_custodian.publicdata.fetch.page_workbook import NS, read_sheet
from eii_custodian.publicdata.fetch.receipts import commit_pair, sha256_hex, sidecar_for
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.frame import census
from eii_custodian.publicdata.frame.layers import COUNTS, SCHEMAS
from eii_custodian.publicdata.review.activity import SpineError

C8_CHILD = CHILD.replace(
    "methods.pinned = invented.child_pinned({shamal!r}, {parts!r})\n",
    "from custodian.tests import test_pinned_c8 as c8\n"
    "c8.plant_c8(methods, Path(__file__).parent / 'invented_cache', {config!r})\n",
).replace(
    "from custodian.data_tests.test_pinned_methods import (\n"
    "    test_pinned_c2_wilson_period,\n"
    "    test_pinned_c2_wilson_stock,\n"
    ")\n",
    "from custodian.data_tests.test_pinned_methods import test_pinned_c8\n",
)


def workbook(*, both_row=8, plant=""):
    """Lead-described Table 76 structure; every numeric value is INVENTED."""
    headers = (
        "Household",
        "Non-Profit",
        "Diplomatic \\ International \\ Regional",
        "Private",
        "Mixed",
        "Government Establishment \\ Company",
        "Ministry \\ Government Department",
        "Total",
    )
    cells = {
        "B1": "INVENTED title",
        "J2": "Table No (76)",
        "B3": "Employed Population (15+) by Sector, Sex and Main Economic Activity",
        "B4": "INVENTED subtitle",
        "A5": "ISIC",
        "B5": "Main Economic Activity",
        "C5": "Sector",
        "K5": "رأس مُختلق",
        "L5": "ISIC",
        **{
            f"{column}7": text for column, text in zip("CDEFGHIJ", headers, strict=True)
        },
    }
    # Twenty coded activity rows per block. Distribute invented counts by plain
    # integer arithmetic, keeping every activity and block total internally exact.
    male = (1, 2, 3, 9, 4, 5, 6)
    female = (2, 0, 1, 21, 1, 2, 3)
    activity_values = [
        [
            tuple(value // 20 + (index < value % 20) for value in sex)
            for index in range(20)
        ]
        for sex in (male, female)
    ]
    both = [
        tuple(a + b for a, b in zip(m, f, strict=True))
        for m, f in zip(*activity_values, strict=True)
    ]
    values = {}
    for offset, label, activities in (
        (0, "Both Sexes", both),
        (21, "Male", activity_values[0]),
        (42, "Female", activity_values[1]),
    ):
        start = both_row + offset
        cells[f"B{start}"] = label
        cells[f"K{start}"] = "INVENTED mirrored block label"
        totals = tuple(sum(row[index] for row in activities) for index in range(7))
        values[start] = (*totals, sum(totals))
        for index, sectors in enumerate(activities):
            number = start + index + 1
            code = "45..47 " if index == 1 else f"{index + 1:02}..{index + 1:02}"
            cells[f"A{number}"] = code
            cells[f"B{number}"] = f"INVENTED activity {index}"
            cells[f"K{number}"] = "نشاط مُختلق"
            cells[f"L{number}"] = code
            values[number] = (*sectors, sum(sectors))
    formula_cells = {f"{column}{number}" for number in values for column in "CDEFGHIJ"}
    cells.update(
        {
            f"{column}{number}": str(value)
            for number, row in values.items()
            for column, value in zip("CDEFGHIJ", row, strict=True)
        }
    )
    if plant == "header":
        cells["F7"] = "INVENTED wrong column"
    elif plant == "missing_block":
        del cells[f"B{both_row}"]
    elif plant == "duplicate_block":
        cells[f"B{both_row + 1}"] = "Both Sexes"
    elif plant.startswith("misplaced_"):
        _, label, column = plant.split("_")
        offset = {"both": 0, "male": 21, "female": 42}[label]
        ref = f"{column}{both_row + offset}"
        cells[ref] = cells.pop(f"B{both_row + offset}")
        formula_cells.discard(ref)
    elif plant in {"missing_male", "missing_female"}:
        del cells[f"B{both_row + (21 if plant == 'missing_male' else 42)}"]
    elif plant == "national_denominator":
        cells[f"J{both_row}"] = "0"
    elif plant == "national_non_numeric":
        cells[f"F{both_row}"] = "INVENTED"
        formula_cells.remove(f"F{both_row}")
    elif plant == "national_missing_cell":
        del cells[f"J{both_row}"]
    elif plant == "national_fraction":
        cells[f"F{both_row}"] = "30.5"
    elif plant == "national_negative":
        cells[f"F{both_row}"] = "-1"
    elif plant.startswith("national_total_"):
        cells[f"J{both_row}"] = {
            "fraction": "60.5",
            "negative": "-1",
            "infinite": "inf",
            "nan": "NaN",
        }[plant.removeprefix("national_total_")]
    elif plant in {"sex_private", "sex_total"} or plant.startswith("sex_sum_"):
        # Keep each affected block internally reconciled to isolate the sex check.
        column = (
            plant.removeprefix("sex_sum_")
            if plant.startswith("sex_sum_")
            else "F"
            if plant == "sex_private"
            else "J"
        )
        for number in (both_row + 21, both_row + 22):
            cells[f"{column}{number}"] = str(int(cells[f"{column}{number}"]) + 1)
    elif plant == "sex_duplicate_block":
        cells[f"B{both_row + 43}"] = "Female"
    elif plant == "duplicate_male":
        cells[f"B{both_row + 22}"] = "Male"
    elif plant == "sex_values_absent":
        for offset in (21, 42):
            for column in "CDEFGHIJ":
                del cells[f"{column}{both_row + offset}"]
    elif plant in {"sex_non_numeric", "sex_missing_cell"}:
        ref = f"F{both_row + 21}"
        if plant == "sex_non_numeric":
            cells[ref] = "INVENTED invalid value"
            formula_cells.remove(ref)
        else:
            del cells[ref]
    elif plant.startswith("count_"):
        _, scope, kind = plant.split("_")
        delta = (
            D("-4")
            if kind == "negative"
            else D("-0.5" if scope in {"female", "activity21"} else "0.5")
        )
        # Fractional transfers must not also make a count negative. The first
        # two female activities have no Non-Profit counts; balance in Household.
        balancing_column = "I" if (scope, kind) == ("activity42", "fraction") else "D"

        def transfer(number, amount):
            for column, change in (("C", amount), (balancing_column, -amount)):
                ref = f"{column}{number}"
                cells[ref] = str(D(cells[ref]) + change)

        # Preserve all block/activity, sex and sector sums. Without count
        # validation these invalid values would pass every reconciliation.
        if scope == "national":
            for offset in (0, 1, 21, 22):
                transfer(both_row + offset, delta)
        elif scope in {"male", "female"}:
            offset = 21 if scope == "male" else 42
            other = 42 if scope == "male" else 21
            for step in (0, 1):
                transfer(both_row + offset + step, delta)
                transfer(both_row + other + step, -delta)
        else:
            offset = int(scope.removeprefix("activity"))
            transfer(both_row + offset + 1, delta)
            transfer(both_row + offset + 2, -delta)
    elif plant.startswith("activity_"):
        _, offset, column, kind = plant.split("_")
        ref = f"{column}{both_row + int(offset) + 1}"
        if kind == "sum":
            cells[ref] = str(int(cells[ref]) + 1)
        elif kind == "missing":
            del cells[ref]
        elif kind == "text":
            cells[ref] = "INVENTED invalid count"
            formula_cells.remove(ref)
    elif plant == "national_sector_sum":
        # Keep all block/activity and sex equalities, changing only J vs C..I.
        for offset in (0, 21):
            for number in (both_row + offset, both_row + offset + 1):
                cells[f"J{number}"] = str(int(cells[f"J{number}"]) + 1)
    rows = {}
    for reference, value in cells.items():
        number = int("".join(c for c in reference if c.isdigit()))
        rows.setdefault(number, []).append((reference, value))

    def cell_xml(ref, value):
        if ref in formula_cells:
            cached = (
                ""
                if plant == "uncached_formula" and ref == f"F{both_row}"
                else f"<v>{value}</v>"
            )
            return f'<c r="{ref}"><f>SUM({value},0)</f>{cached}</c>'
        return f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'

    row_xml = "".join(
        f'<row r="{number}">'
        + "".join(cell_xml(ref, value) for ref, value in sorted(row))
        + "</row>"
        for number, row in sorted(rows.items())
    )
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="76" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{row_xml}</sheetData><mergeCells count="3">'
            '<mergeCell ref="A5:A7"/><mergeCell ref="B5:B7"/>'
            '<mergeCell ref="C5:J5"/></mergeCells></worksheet>',
        )
    return output.getvalue()


def zones(null_field="Private", *, mixed=0):
    result = []
    source = "census_zone_sector"
    for zone, private, mixed_count in ((101, 10, mixed), (102, 20, 0), (103, 15, 0)):
        attrs = {
            name: "INVENTED" if kinds == (str,) else 0
            for name, kinds in SCHEMAS[source].items()
        }
        attrs.update(
            ZONE_NO=zone,
            Private=private,
            Mixed=mixed_count,
            Government=30 - private - mixed_count,
        )
        attrs[COUNTS[source][0]] = 30
        result.append({"attributes": attrs, "geometry": {"rings": []}})
    result[-1]["attributes"][null_field] = None
    return {"count": len(result), "features": result}


@given(st.integers(min_value=0, max_value=20))
def test_c8_zone_nonprivate_parameter_preserves_valid_counts(mixed):
    baseline = zones()
    payload = zones(mixed=mixed)
    attrs = payload["features"][0]["attributes"]
    original = baseline["features"][0]["attributes"]
    fields = COUNTS["census_zone_sector"]
    assert attrs["Mixed"] == mixed
    assert sum(Fraction(attrs[field]) for field in fields[1:]) == attrs[fields[0]]
    assert all(attrs[field] >= 0 for field in fields)
    assert attrs[fields[0]] > 0
    assert attrs["Private"] == original["Private"] <= attrs[fields[0]]
    assert attrs[fields[0]] == original[fields[0]]
    assert payload["features"][1:] == baseline["features"][1:]


def write_source(cache, key, body):
    entry = next(row for row in load_registry() if row.key == key)
    digest = sha256_hex(body)
    receipt = sidecar_for(
        entry,
        digest=digest,
        nbytes=len(body),
        fetch_url=entry.url,
        fetch_host=entry.fetch_host,
        retrieved_utc="2026-11-21T00:00:00Z",
        publisher=entry.publisher,
        source_modified="",
        row_count=None,
        terms_sha256="",
    )
    commit_pair(cache / key, digest, entry.extension, body, receipt)
    return digest


def invented_cache(
    tmp_path, monkeypatch, *, both_row=8, null_field="Private", plant=""
):
    payload = zones(null_field)
    if plant == "sector_sum":
        payload["features"][0]["attributes"]["Government"] += 1
    elif plant == "zone_zero":
        for field in ("Private", "Government", COUNTS["census_zone_sector"][0]):
            payload["features"][0]["attributes"][field] = 0
    elif plant == "zone_negative":
        payload = zones(null_field, mixed=-1)
        attrs = payload["features"][0]["attributes"]
        fields = COUNTS["census_zone_sector"]
        assert sum(attrs[field] for field in fields[1:]) == attrs[fields[0]]
        assert attrs[fields[0]] > 0
        assert 0 <= attrs["Private"] <= attrs[fields[0]]
        baseline = zones(null_field)["features"][0]["attributes"]
        assert attrs["Private"] == baseline["Private"]
        assert attrs[fields[0]] == baseline[fields[0]]
        assert all(attrs[field] >= 0 for field in fields if field != "Mixed")
    elif plant == "zone_empty":
        payload = {"count": 0, "features": []}
    elif plant == "zone_duplicate_key":
        payload["features"][1]["attributes"]["ZONE_NO"] = payload["features"][0][
            "attributes"
        ]["ZONE_NO"]
    elif plant == "no_complete_zones":
        for feature in payload["features"]:
            feature["attributes"]["Private"] = None
    pins = {
        "census_zone_sector": write_source(
            tmp_path, "census_zone_sector", json.dumps(payload).encode()
        ),
        "census_2020_workbook": write_source(
            tmp_path, "census_2020_workbook", workbook(both_row=both_row, plant=plant)
        ),
    }
    (tmp_path / "method_pins.json").write_text(json.dumps(pins))
    monkeypatch.setattr(methods._cache, "CACHE", tmp_path)
    return pins


def _c8_raiser(error):
    def raise_it(*_args, **_kwargs):
        raise error

    return raise_it


def _c8_missing_lineage(original, slot):
    def missing(private, employed):
        result = original(private, employed)
        if not isinstance(result, NoData) and (
            (private.geography == "national") == (slot == "national")
        ):
            object.__setattr__(result["percent"], "sources", ())
        return result

    return missing


def _c8_wrong_value(original, slot):
    def wrong(private, employed):
        result = original(private, employed)
        if not isinstance(result, NoData) and (
            private.geography == "national"
            if slot == "national"
            else private.geography != "national"
        ):
            result["percent"] = replace(result["percent"], value=D(SENTINEL))
        return result

    return wrong


def plant_c8(methods_module, cache, config):
    """Build an invented cache and plant exactly one named C8 failure."""
    kind = config.get("kind", "pass")
    if kind in {"source_invalid", "spine_refused"}:
        error = {
            "source_invalid": KeyError(str(SENTINEL)),
            "spine_refused": SpineError(f"INVENTED {SENTINEL}"),
        }[kind]
        methods_module._cache.pinned_body = _c8_raiser(error)
        return
    cache.mkdir()
    patch = pytest.MonkeyPatch()
    pins = invented_cache(
        cache,
        patch,
        both_row=config.get("both_row", 8),
        null_field=config.get("null_field", "Private"),
        plant=config.get("plant", ""),
    )
    if kind == "null_zone":
        original = methods_module.c8_zone_share

        def wrong(row, chain):
            return {} if row["Private"] is None else original(row, chain)

        patch.setattr(methods_module, "c8_zone_share", wrong)
    elif kind in {"national_lineage", "zone_lineage"}:
        slot = kind.removesuffix("_lineage")
        patch.setattr(
            methods_module,
            "coverage_share",
            _c8_missing_lineage(methods_module.coverage_share, slot),
        )
    elif kind in {"national", "zone"}:
        patch.setattr(
            methods_module,
            "coverage_share",
            _c8_wrong_value(methods_module.coverage_share, kind),
        )
    elif kind in {"range", "range_high"}:
        if kind == "range":
            patch.setattr(methods_module, "share_range", lambda _values: (D(0), D(100)))
        else:
            patch.setattr(
                methods_module,
                "share_range",
                lambda values: (min(values), D(SENTINEL)),
            )
    elif kind in {"pin", "bytes", "receipt", "snapshot", "index", "path"}:
        key = config["key"]
        digest = pins[key]
        if kind == "pin":
            del pins[key]
            (cache / "method_pins.json").write_text(json.dumps(pins))
        elif kind == "bytes":
            extension = "xlsx" if key == "census_2020_workbook" else "json"
            (cache / key / f"{digest}.{extension}").write_bytes(b"INVENTED wrong bytes")
        elif kind == "receipt":
            path = cache / key / f"{digest}.meta.json"
            receipt = json.loads(path.read_text())
            receipt["source_id"] = "est_census"
            path.write_text(json.dumps(receipt))
        else:
            index_path = cache / key / "index" / f"{digest}.json"
            if kind == "index":
                index_path.unlink()
            elif kind == "path":
                index = json.loads(index_path.read_text())
                index["path"] = "INVENTED invalid path"
                index_path.write_text(json.dumps(index))
            else:
                index = json.loads(index_path.read_text())
                (cache / key / index["path"]).unlink()


def assert_c8_closed(tmp_path, config, reason):
    failing = child_run(tmp_path, C8_CHILD.format(config=config))
    output = failing.stdout + failing.stderr
    assert failing.returncode == 1, "child_not_failed"
    assert str(SENTINEL) not in output, "sentinel_leaked"
    assert summary(failing) == {f"C8:{reason}"}


def test_c8_source_binding_and_attribution():
    entries = {entry.key: entry for entry in load_registry()}
    assert census.C8_SOURCES == {
        "national": "census_2020_workbook",
        "zone": "census_zone_sector",
    }
    fixture = json.loads(
        (
            methods._cache.ROOT / "core/tests/fixtures/methods/public_methods.json"
        ).read_text()
    )
    for geography, key in census.C8_SOURCES.items():
        table = f"pub_census_{geography}"
        assert census.SOURCES[key] == table
        entry = entries[key]
        assert table in entry.release_tables
        assert fixture["sources"][key] == {
            "publisher": entry.publisher,
            "dataset": entry.title_en,
            "url": entry.url,
            "licence": entry.licence_id,
            "licence_basis": entry.licence_basis,
            "licence_url": entry.licence_url,
            "terms_read_on": entry.terms_read_on,
            "retrieval_date": "pinned receipt: retrieved_utc",
        }
    assert fixture["invented"]["C8"]["sources"] == census.C8_SOURCES


@pytest.mark.parametrize("binding", ["national", "zone"])
def test_c8_wrong_source_binding_plant(monkeypatch, binding):
    monkeypatch.setitem(census.C8_SOURCES, binding, "est_census")
    with pytest.raises(AssertionError):
        test_c8_source_binding_and_attribution()


@pytest.mark.parametrize("both_row", [8, 11])
@pytest.mark.parametrize("null_field", COUNTS["census_zone_sector"])
def test_c8_full_pinned_replay_on_invented_cache(
    tmp_path, monkeypatch, both_row, null_field
):
    invented_cache(tmp_path, monkeypatch, both_row=both_row, null_field=null_field)
    methods.test_pinned_c8()


@pytest.mark.parametrize("both_row", [8, 11])
def test_c8_invented_values_are_cached_formulas(both_row):
    body = workbook(both_row=both_row)
    with ZipFile(io.BytesIO(body)) as archive:
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    cells = {cell.get("r"): cell for cell in root.findall("s:sheetData/s:row/s:c", NS)}
    for row in range(both_row, both_row + 63):
        for column in "CDEFGHIJ":
            cell = cells[f"{column}{row}"]
            assert cell.find("s:f", NS) is not None
            assert cell.findtext("s:v", "", NS)
    with pytest.raises(ShapeError, match=r"^schema_missing$"):
        read_sheet(body, "76")


@pytest.mark.parametrize("both_row", [8, 11])
def test_c8_total_is_selected_from_both_sexes_block_row(both_row):
    sheet = read_sheet(workbook(both_row=both_row), "76", cached_formulas=True)
    assert methods.c8_national_counts(sheet) == (both_row, D(30), D(60))


def test_c8_invented_table_matches_lead_described_structure():
    sheet = read_sheet(workbook(), "76", cached_formulas=True)
    assert max(sheet.rows) == 70
    assert set(sheet.merges) == {"A5:A7", "B5:B7", "C5:J5"}
    assert [sheet.cells[f"B{row}"] for row in (8, 29, 50)] == [
        "Both Sexes",
        "Male",
        "Female",
    ]
    assert not any(
        value == "Total" for ref, value in sheet.cells.items() if ref.startswith("B")
    )
    for start in (8, 29, 50):
        assert f"A{start}" not in sheet.cells
        assert sheet.cells[f"A{start + 2}"] == "45..47 "
        for row in range(start + 1, start + 21):
            assert sheet.cells[f"A{row}"].strip()
            assert sheet.cells[f"L{row}"] == sheet.cells[f"A{row}"]
            assert sheet.cells[f"K{row}"] == "نشاط مُختلق"
    # The mirror columns remain text, rather than being mistaken for counts.
    assert all(sheet.cells[f"K{row}"] for row in range(8, 71))


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("duplicate_block", "national_block"),
        ("missing_male", "sex_block"),
        ("missing_female", "sex_block"),
        ("duplicate_male", "sex_block"),
        ("sex_values_absent", "sex_count"),
        ("sex_missing_cell", "sex_count"),
        *[(f"misplaced_both_{column}", "national_block") for column in "ACKL"],
        *[
            (f"misplaced_{sex}_{column}", "sex_block")
            for sex in ("male", "female")
            for column in "ACKL"
        ],
    ],
)
def test_c8_block_row_schema_plants(tmp_path, monkeypatch, plant, reason):
    assert_c8_closed(tmp_path, {"plant": plant}, reason)


@pytest.mark.parametrize("offset", [0, 21, 42])
@pytest.mark.parametrize("column", list("CDEFGHIJ"))
def test_c8_each_block_equals_its_activity_sum(tmp_path, monkeypatch, offset, column):
    assert_c8_closed(
        tmp_path, {"plant": f"activity_{offset}_{column}_sum"}, "activity_sum_mismatch"
    )


@pytest.mark.parametrize("offset", [0, 21, 42])
@pytest.mark.parametrize("kind", ["missing", "text"])
def test_c8_activity_counts_are_required(tmp_path, monkeypatch, offset, kind):
    assert_c8_closed(
        tmp_path, {"plant": f"activity_{offset}_C_{kind}"}, "activity_count"
    )


@pytest.mark.parametrize(
    "scope,reason",
    [
        ("national", "national_count"),
        ("male", "sex_count"),
        ("female", "sex_count"),
        *[(f"activity{offset}", "activity_count") for offset in (0, 21, 42)],
    ],
)
@pytest.mark.parametrize("kind", ["negative", "fraction"])
def test_c8_counts_are_nonnegative_whole_numbers(
    tmp_path, monkeypatch, scope, reason, kind
):
    plant = f"count_{scope}_{kind}"
    assert _fixture_equalities(plant) == (True, True, True)
    sheet = read_sheet(workbook(plant=plant), "76", cached_formulas=True)
    values = [
        Fraction(sheet.cells[f"{column}{row}"])
        for start in (8, 29, 50)
        for row in range(start, start + 21)
        for column in "CDEFGHIJ"
    ]
    if kind == "negative":
        assert any(value < 0 for value in values)
        assert all(value.denominator == 1 for value in values)
    else:
        assert all(value >= 0 for value in values)
        assert any(value.denominator != 1 for value in values)
    assert_c8_closed(tmp_path, {"plant": plant}, reason)


@pytest.mark.parametrize("column", list("CDEFGHIJ"))
def test_c8_sex_totals_reconcile_every_column(tmp_path, monkeypatch, column):
    assert_c8_closed(tmp_path, {"plant": f"sex_sum_{column}"}, "sex_sum_mismatch")


def test_c8_national_sectors_equal_total(tmp_path, monkeypatch):
    assert_c8_closed(tmp_path, {"plant": "national_sector_sum"}, "national_sector_sum")


def _fixture_equalities(plant):
    """Independent fixture audit: each arithmetic plant breaks one equality only."""
    sheet = read_sheet(workbook(plant=plant), "76", cached_formulas=True)

    def value(column, row):
        return Fraction(sheet.cells[f"{column}{row}"])

    return (
        all(
            value(column, start)
            == sum(
                (value(column, row) for row in range(start + 1, start + 21)),
                Fraction(0),
            )
            for start in (8, 29, 50)
            for column in "CDEFGHIJ"
        ),
        all(
            value(column, 8) == value(column, 29) + value(column, 50)
            for column in "CDEFGHIJ"
        ),
        value("J", 8) == sum((value(column, 8) for column in "CDEFGHI"), Fraction(0)),
    )


@pytest.mark.parametrize(
    "plant,expected",
    [
        ("", (True, True, True)),
        *[
            (f"activity_{offset}_{column}_sum", (False, True, True))
            for offset in (0, 21, 42)
            for column in "CDEFGHIJ"
        ],
        *[(f"sex_sum_{column}", (True, False, True)) for column in "CDEFGHIJ"],
        ("national_sector_sum", (True, True, False)),
    ],
)
def test_c8_arithmetic_plants_isolate_the_named_equality(plant, expected):
    assert _fixture_equalities(plant) == expected


def test_c8_formula_without_cached_value_refuses(tmp_path, monkeypatch):
    assert_c8_closed(tmp_path, {"plant": "uncached_formula"}, "source_invalid")


@pytest.mark.parametrize(
    "plant,reason",
    [("sex_private", "sex_sum_mismatch"), ("sex_total", "sex_sum_mismatch")],
)
@pytest.mark.parametrize("both_row", [8, 11])
def test_c8_sex_totals_must_reconcile(tmp_path, monkeypatch, plant, reason, both_row):
    assert_c8_closed(tmp_path, {"plant": plant, "both_row": both_row}, reason)


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("sex_duplicate_block", "sex_block"),
        ("sex_non_numeric", "sex_count"),
    ],
)
def test_c8_sex_reconciliation_schema_plants(tmp_path, monkeypatch, plant, reason):
    assert_c8_closed(tmp_path, {"plant": plant}, reason)


def test_c8_zone_null_and_lineage_are_observable(tmp_path, monkeypatch):
    pins = invented_cache(tmp_path, monkeypatch)
    _, chain = methods._cache.pinned_body("census_zone_sector")
    rows = [feature["attributes"] for feature in zones()["features"]]
    assert methods.c8_zone_share(rows[-1], chain) == NoData("no_denominator")
    result = methods.c8_zone_share(rows[0], chain)
    assert result["percent"].value == D("33.3")
    assert result["percent"].geography == "zone:101"
    assert result["percent"].sources == (chain,)
    assert chain.sha256 == pins["census_zone_sector"]
    assert chain.retrieved == "2026-11-21"


def test_c8_null_zone_must_never_return_a_share(tmp_path):
    assert_c8_closed(tmp_path, {"kind": "null_zone"}, "null_zone_mismatch")


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("sector_sum", "sector_sum"),
        ("header", "national_header"),
        ("missing_block", "national_block"),
        ("national_denominator", "national_denominator"),
        ("national_non_numeric", "national_count"),
        ("national_missing_cell", "national_count"),
        ("national_fraction", "national_denominator"),
        ("national_negative", "national_denominator"),
        ("national_total_fraction", "national_denominator"),
        ("national_total_negative", "national_denominator"),
        ("national_total_infinite", "national_denominator"),
        ("national_total_nan", "national_denominator"),
        ("zone_zero", "zone_denominator"),
        ("zone_negative", "zone_denominator"),
        ("zone_empty", "zone_keys"),
        ("zone_duplicate_key", "zone_keys"),
        ("no_complete_zones", "no_complete_zones"),
    ],
)
def test_c8_raw_schema_plants(tmp_path, monkeypatch, plant, reason):
    assert_c8_closed(tmp_path, {"plant": plant}, reason)


@pytest.mark.parametrize("slot", ["national", "zone"])
def test_c8_lineage_plants(tmp_path, slot):
    assert_c8_closed(tmp_path, {"kind": slot + "_lineage"}, slot + "_lineage")


@pytest.mark.parametrize("slot", ["national", "zone", "range", "range_high"])
def test_c8_planted_wrong_calculated_value_fails(tmp_path, slot):
    reason = {"range": "range_low"}.get(slot, slot)
    assert_c8_closed(tmp_path, {"kind": slot}, reason + "_mismatch")


@pytest.mark.parametrize("key", ["census_zone_sector", "census_2020_workbook"])
@pytest.mark.parametrize(
    "plant", ["pin", "bytes", "receipt", "snapshot", "index", "path"]
)
def test_c8_each_pin_and_receipt_is_required(tmp_path, key, plant):
    reason = {
        "pin": "public_cache_missing",
        "bytes": "receipt_hash_mismatch",
        "receipt": "receipt_hash_mismatch",
        "snapshot": "public_cache_missing",
        "index": "public_cache_missing",
        "path": "public_cache_missing",
    }[plant]
    assert_c8_closed(tmp_path, {"kind": plant, "key": key}, reason)


def test_c8_case_passes_on_invented_child_setup(tmp_path):
    passing = child_run(tmp_path, C8_CHILD.format(config={}))
    assert passing.returncode == 0, passing.stdout + passing.stderr


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        ("source_invalid", "source_invalid"),
        ("spine_refused", "spine_refused"),
    ],
)
def test_c8_unexpected_and_cache_errors_are_closed(tmp_path, kind, reason):
    assert_c8_closed(tmp_path, {"kind": kind}, reason)


@given(
    st.data(),
    st.sampled_from([ValueError, KeyError, TypeError, SpineError, AssertionError]),
)
def test_c8_reason_map_is_closed(data, kind):
    message = data.draw(
        st.one_of(st.sampled_from(sorted(methods.C8_REASONS)), st.text())
    )
    reason = methods.closed_reason(kind(message), methods.C8_REASONS)
    admitted = methods.C8_REASONS.get(message)
    if kind is SpineError:
        expected = "spine_refused"
    elif kind is ValueError and admitted:
        expected = admitted
    else:
        expected = "source_invalid"
    assert reason == expected
    assert re.fullmatch(r"[a-z_]+", reason)
