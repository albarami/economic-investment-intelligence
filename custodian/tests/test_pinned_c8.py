"""C8 replay proofs on INVENTED OOXML and paged-layer cache pairs only."""

import io
import json
from dataclasses import replace
from decimal import Decimal as D
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZipFile

import pytest
from custodian.data_tests import test_pinned_methods as methods

from eii_core.calc.facts import NoData
from eii_custodian.publicdata.fetch.page_html import ShapeError
from eii_custodian.publicdata.fetch.page_workbook import NS, read_sheet
from eii_custodian.publicdata.fetch.receipts import commit_pair, sha256_hex, sidecar_for
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.frame import census
from eii_custodian.publicdata.frame.layers import COUNTS, SCHEMAS


def workbook(*, total_row=12, plant=""):
    """Physical header/block coordinates match the lead's table-76 description."""
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
        "B3": "Employed Population (15+) by Sector, Sex and Main Economic Activity",
        "J2": "Table No (76)",
        "B8": "Both Sexes",
        "B9": "INVENTED activity",
        f"B{total_row}": "Total",
        f"B{total_row + 2}": "Males",
        f"B{total_row + 3}": "Total",
        f"B{total_row + 5}": "Females",
        f"B{total_row + 6}": "Total",
        **{
            f"{column}7": text for column, text in zip("CDEFGHIJ", headers, strict=True)
        },
    }
    # INVENTED values only. Every C..J value is a formula with a cached value,
    # as in the published shape described by the lead; no formula is evaluated.
    values = {
        9: (0, 0, 0, 1, 0, 0, 99, 100),
        total_row: (3, 2, 4, 30, 5, 7, 9, 60),
        total_row + 3: (1, 2, 3, 9, 4, 5, 6, 30),
        total_row + 6: (2, 0, 1, 21, 1, 2, 3, 30),
    }
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
    elif plant == "missing_total":
        del cells[f"B{total_row}"]
    elif plant == "duplicate_total":
        cells[f"B{total_row + 1}"] = "Total"
        cells[f"F{total_row + 1}"] = "6"
        cells[f"J{total_row + 1}"] = "10"
    elif plant == "missing_block":
        cells["B8"] = "Males"
    elif plant == "national_denominator":
        cells[f"J{total_row}"] = "0"
    elif plant == "sex_private":
        cells[f"F{total_row + 3}"] = "10"
    elif plant == "sex_total":
        cells[f"J{total_row + 6}"] = "31"
    elif plant == "sex_duplicate_total":
        cells[f"B{total_row + 4}"] = "Total"
    elif plant == "sex_duplicate_block":
        cells[f"B{total_row + 7}"] = "Females"
    elif plant == "sex_non_numeric":
        cells[f"F{total_row + 3}"] = "INVENTED invalid value"
        formula_cells.remove(f"F{total_row + 3}")
    elif plant in {"sex_summary_rows", "sex_values_absent"}:
        for offset in (3, 6):
            for column in "CDEFGHIJ":
                ref = f"{column}{total_row + offset}"
                value = cells.pop(ref)
                formula_cells.remove(ref)
                if plant == "sex_summary_rows":
                    summary_ref = f"{column}{total_row + offset - 1}"
                    cells[summary_ref] = value
                    formula_cells.add(summary_ref)
            if plant == "sex_summary_rows":
                del cells[f"B{total_row + offset}"]
    rows = {}
    for reference, value in cells.items():
        number = int("".join(c for c in reference if c.isdigit()))
        rows.setdefault(number, []).append((reference, value))

    def cell_xml(ref, value):
        if ref in formula_cells:
            cached = (
                ""
                if plant == "uncached_formula" and ref == f"F{total_row}"
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
            f"<sheetData>{row_xml}</sheetData></worksheet>",
        )
    return output.getvalue()


def zones(null_field="Private"):
    result = []
    source = "census_zone_sector"
    for zone, private in ((101, 10), (102, 20), (103, 15)):
        attrs = {
            name: "INVENTED" if kinds == (str,) else 0
            for name, kinds in SCHEMAS[source].items()
        }
        attrs.update(ZONE_NO=zone, Private=private, Government=30 - private)
        attrs[COUNTS[source][0]] = 30
        result.append({"attributes": attrs, "geometry": {"rings": []}})
    result[-1]["attributes"][null_field] = None
    return {"count": len(result), "features": result}


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
    tmp_path, monkeypatch, *, total_row=12, null_field="Private", plant=""
):
    payload = zones(null_field)
    if plant == "sector_sum":
        payload["features"][0]["attributes"]["Government"] += 1
    pins = {
        "census_zone_sector": write_source(
            tmp_path, "census_zone_sector", json.dumps(payload).encode()
        ),
        "census_2020_workbook": write_source(
            tmp_path, "census_2020_workbook", workbook(total_row=total_row, plant=plant)
        ),
    }
    (tmp_path / "method_pins.json").write_text(json.dumps(pins))
    monkeypatch.setattr(methods._cache, "CACHE", tmp_path)
    return pins


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


@pytest.mark.parametrize("total_row", [12, 18])
@pytest.mark.parametrize("null_field", COUNTS["census_zone_sector"])
def test_c8_full_pinned_replay_on_invented_cache(
    tmp_path, monkeypatch, total_row, null_field
):
    invented_cache(tmp_path, monkeypatch, total_row=total_row, null_field=null_field)
    methods.test_pinned_c8()


@pytest.mark.parametrize("total_row", [12, 18])
def test_c8_invented_values_are_cached_formulas(total_row):
    body = workbook(total_row=total_row)
    with ZipFile(io.BytesIO(body)) as archive:
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    cells = {cell.get("r"): cell for cell in root.findall("s:sheetData/s:row/s:c", NS)}
    for row in (9, total_row, total_row + 3, total_row + 6):
        for column in "CDEFGHIJ":
            cell = cells[f"{column}{row}"]
            assert cell.find("s:f", NS) is not None
            assert cell.findtext("s:v", "", NS)
    with pytest.raises(ShapeError, match=r"^schema_missing$"):
        read_sheet(body, "76")


@pytest.mark.parametrize("total_row", [12, 18])
def test_c8_total_is_selected_by_label_in_both_sexes_block(total_row):
    sheet = read_sheet(workbook(total_row=total_row), "76", cached_formulas=True)
    assert methods.c8_national_counts(sheet) == (total_row, D(30), D(60))


def test_c8_formula_without_cached_value_refuses(tmp_path, monkeypatch):
    invented_cache(tmp_path, monkeypatch, plant="uncached_formula")
    with pytest.raises(ShapeError, match=r"^schema_missing$"):
        methods.test_pinned_c8()


@pytest.mark.parametrize("plant", ["sex_private", "sex_total"])
@pytest.mark.parametrize("total_row", [12, 18])
def test_c8_sex_totals_must_reconcile(tmp_path, monkeypatch, plant, total_row):
    invented_cache(tmp_path, monkeypatch, plant=plant, total_row=total_row)
    with pytest.raises(ValueError, match=r"^C8:sex_sum_mismatch$"):
        methods.test_pinned_c8()


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("sex_duplicate_total", "sex_total_label"),
        ("sex_duplicate_block", "sex_block"),
        ("sex_non_numeric", "sex_count"),
    ],
)
def test_c8_sex_reconciliation_schema_plants(tmp_path, monkeypatch, plant, reason):
    invented_cache(tmp_path, monkeypatch, plant=plant)
    with pytest.raises(ValueError, match="^C8:" + reason + "$"):
        methods.test_pinned_c8()


@pytest.mark.parametrize("plant", ["sex_summary_rows", "sex_values_absent"])
def test_c8_sex_reconciliation_available_layouts(tmp_path, monkeypatch, plant):
    invented_cache(tmp_path, monkeypatch, plant=plant)
    methods.test_pinned_c8()


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


def test_c8_null_zone_must_never_return_a_share(tmp_path, monkeypatch):
    invented_cache(tmp_path, monkeypatch)
    original = methods.c8_zone_share

    def wrong(row, chain):
        if row["Private"] is None:
            return {}
        return original(row, chain)

    monkeypatch.setattr(methods, "c8_zone_share", wrong)
    with pytest.raises(ValueError, match="C8:null_zone_mismatch"):
        methods.test_pinned_c8()


@pytest.mark.parametrize(
    "plant",
    [
        "sector_sum",
        "header",
        "missing_total",
        "duplicate_total",
        "missing_block",
        "national_denominator",
    ],
)
def test_c8_raw_schema_plants(tmp_path, monkeypatch, plant):
    invented_cache(tmp_path, monkeypatch, plant=plant)
    with pytest.raises((AssertionError, ValueError), match="C8:"):
        methods.test_pinned_c8()


@pytest.mark.parametrize("slot", ["national", "zone", "range"])
def test_c8_planted_wrong_calculated_value_fails(tmp_path, monkeypatch, slot):
    invented_cache(tmp_path, monkeypatch)
    if slot == "range":
        monkeypatch.setattr(methods, "share_range", lambda values: (D(0), D(100)))
    else:
        original = methods.coverage_share

        def wrong(private, employed):
            result = original(private, employed)
            if not isinstance(result, NoData) and (
                private.geography == "national"
                if slot == "national"
                else private.geography != "national"
            ):
                result["percent"] = replace(result["percent"], value=D(1))
            return result

        monkeypatch.setattr(methods, "coverage_share", wrong)
    with pytest.raises(ValueError, match=r"C8:.*mismatch"):
        methods.test_pinned_c8()


@pytest.mark.parametrize("key", ["census_zone_sector", "census_2020_workbook"])
@pytest.mark.parametrize("plant", ["pin", "bytes", "receipt"])
def test_c8_each_pin_and_receipt_is_required(tmp_path, monkeypatch, key, plant):
    pins = invented_cache(tmp_path, monkeypatch)
    digest = pins[key]
    if plant == "pin":
        del pins[key]
        (tmp_path / "method_pins.json").write_text(json.dumps(pins))
    elif plant == "bytes":
        extension = "xlsx" if key == "census_2020_workbook" else "json"
        (tmp_path / key / f"{digest}.{extension}").write_bytes(b"INVENTED wrong bytes")
    else:
        path = tmp_path / key / f"{digest}.meta.json"
        receipt = json.loads(path.read_text())
        receipt["source_id"] = "est_census"
        path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        methods.test_pinned_c8()
