"""Synthetic bounded acquisition, exact request frames and host isolation."""

import json
from urllib.parse import parse_qs, urlsplit

import pytest
from custodian.tests.test_s2_t29_live_shapes import (
    STAMP,
    URL,
    classified,
    declaration,
    embedded,
    entry,
    schema,
    tariff,
    tariffs,
)

from eii_custodian.publicdata.fetch.page_records import fetch_page
from eii_custodian.publicdata.fetch.transport import Response

FIELDS = "objectid,name,aname,category,category_a,eng_type,type,adoptedcurriculum,operationalstatus,mncp_code,mncp_name,mncp_name_en,district_code,district_name,district_name_en,lat,long_".split(
    ","
)
FORBIDDEN = "subcategor subcateg_a streetname arbstreetn buildingn qars elec_num w_num pin_plotn createdate date_modfd remarks coord_x coord_y pobox email email_p website floor_num area students_n staff_num secname secnum source emp_num owner owner_tel director ncc_id studentno schoolno gis_comment finalplotarea_m2 final_plotpin students2014 currentlevelofservice mappingno designedcap allocationstatus vacancy schoollocation coord_x_qng coord_y_qng zone_code zone_name zone_name_en streetnum zonenum haseducationalvouchers phone phone2 mobile fax director_t".split()


def school():
    kinds = {f: "string" for f in FIELDS}
    kinds.update(
        objectid="integer",
        mncp_code="integer",
        district_code="integer",
        lat="number",
        long_="number",
    )
    nullable = {
        "eng_type",
        "type",
        "mncp_code",
        "mncp_name",
        "mncp_name_en",
        "district_code",
        "district_name",
        "district_name_en",
        "lat",
        "long_",
    }
    dec = declaration(
        "arcgis_query",
        {
            "layer": URL,
            "fields": FIELDS.copy(),
            "record_path": ["features"],
            "attribute_path": ["attributes"],
            "geometry": "esriGeometryPoint",
            "spatial_reference": 2932,
            "order_by": "objectid",
            "page_size": 1,
            "where": "1=1",
            "record_schema": schema(
                "object",
                fields={
                    f: dict(schema(kinds[f]), nullable=f in nullable) for f in FIELDS
                },
            ),
        },
        [[f, kinds[f]] for f in FIELDS],
    )
    dec["url"] = URL + "?f=json"
    dec["reviewed_urls"] = [dec["url"]]
    attrs = {f: "SYN-" + f for f in FIELDS}
    attrs.update(
        objectid=1,
        mncp_code=2,
        district_code=3,
        lat=1.5,
        long_=2.5,
        eng_type=None,
        type=None,
    )
    return dec, attrs


def test_non_capture_source_accepts_registration_required_text(tmp_path):
    dec, body, _ = embedded()
    body = body.replace(b"SYN &gt; event", b"SYN registration required")
    calls = []

    def read(url):
        calls.append(url)
        return Response(url, body, ())

    result = fetch_page(
        entry(dec),
        read,
        tmp_path,
        lambda: STAMP,
        lambda _: None,
        declaration=dec,
    )
    assert json.loads(result.body)["rows"][0]["title"] == "SYN registration required"
    assert calls == [dec["url"]]


def school_transport(attrs, calls, plant=""):
    def read(url):
        calls.append(url)
        query = parse_qs(urlsplit(url).query)
        if url == URL + "?f=json":
            body = {
                "geometryType": "esriGeometryPoint",
                "extent": {"spatialReference": {"wkid": 2932}},
                "objectIdField": "objectid",
                "maxRecordCount": 1,
                "advancedQueryCapabilities": {
                    "supportsPagination": True,
                    "supportsOrderBy": True,
                },
            }
        elif query.get("returnCountOnly") == ["true"]:
            body = {"count": 2}
        else:
            assert query["where"] == ["1=1"]
            assert query["outFields"] == [",".join(FIELDS)]
            assert query["orderByFields"] == ["objectid"]
            offset = int(query["resultOffset"][0])
            assert offset < 2
            assert query["resultRecordCount"] == ["1"]
            item = dict(attrs, objectid=offset + 1)
            if plant == "extra":
                item["owner"] = "SYN forbidden"
            if plant == "duplicate":
                item["objectid"] = 1
            body = {
                "geometryType": "esriGeometryPoint",
                "spatialReference": {"wkid": 2932},
                "features": [{"attributes": item, "geometry": {"x": 1.5, "y": 2.5}}],
                "exceededTransferLimit": offset == 0,
            }
            if plant == "past_count" and offset == 1:
                body["exceededTransferLimit"] = True
            if plant == "early_terminal":
                body["exceededTransferLimit"] = False
            if plant == "empty":
                body["features"] = []
        return Response(url, json.dumps(body).encode(), ())

    return read


def test_school_bounded_offsets(tmp_path):
    dec, attrs = school()
    calls = []
    result = fetch_page(
        entry(dec, "schools_private_directory"),
        school_transport(attrs, calls),
        tmp_path,
        lambda: STAMP,
        lambda _: None,
        declaration=dec,
    )
    payload = json.loads(result.body)
    assert len(payload["rows"]) == 2 and len(calls) == 4
    assert payload["period_first"] is None and payload["period_last"] is None
    assert len(payload["inputs"]) == 4


@pytest.mark.parametrize("field", [*FORBIDDEN, "*", "Name", "name AS owner"])
def test_school_request_field_refused_before_any_fetch(tmp_path, field):
    dec, _ = school()
    dec["shape"]["fields"].append(field)
    calls = []
    with pytest.raises(ValueError, match="school_field_refused"):
        fetch_page(
            entry(dec, "schools_private_directory"),
            lambda u: calls.append(u),
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=dec,
        )
    assert calls == [] and not list(tmp_path.rglob("index/*.json"))


@pytest.mark.parametrize(
    "plant", ["extra", "duplicate", "past_count", "early_terminal", "empty"]
)
def test_school_response_and_paging_refused_atomically(tmp_path, plant):
    dec, attrs = school()
    calls = []
    with pytest.raises(ValueError, match=r"school_field_refused|paging_incomplete"):
        fetch_page(
            entry(dec, "schools_private_directory"),
            school_transport(attrs, calls, plant),
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=dec,
        )
    assert not list(tmp_path.rglob("index/*.json"))
    assert all("resultOffset=2" not in u for u in calls)


def test_classified_paging_uses_page_total(tmp_path):
    dec, body = classified()
    calls = []
    first = body.replace(b"SYN total: 1", b"SYN total: 2").replace(
        b'/syn-shape/1">1</a>', b'/syn-shape/2">2</a>'
    )
    second = first.replace(b"SYN-profile", b"SYN-other")

    def read(url):
        calls.append(url)
        return Response(url, first if url.endswith("/1") else second, ())

    result = fetch_page(
        entry(dec, "monaqasat_classified"),
        read,
        tmp_path,
        lambda: STAMP,
        lambda _: None,
        declaration=dec,
    )
    assert len(json.loads(result.body)["rows"]) == 2
    assert calls == [URL + "/1", URL + "/2"]


@pytest.mark.parametrize("plant", ["over_count", "changed_end", "duplicate"])
def test_classified_paging_plants(tmp_path, plant):
    dec, body = classified()
    first = body.replace(b"SYN total: 1", b"SYN total: 2").replace(
        b'/syn-shape/1">1</a>', b'/syn-shape/2">2</a>'
    )
    second = first.replace(b"SYN-profile", b"SYN-other")
    if plant == "over_count":
        first = first.replace(b"SYN total: 2", b"SYN total: 1")
    if plant == "changed_end":
        second = second.replace(b"SYN total: 2", b"SYN total: 3")
    if plant == "duplicate":
        second = first
    calls = []

    def read(url):
        calls.append(url)
        return Response(url, first if url.endswith("/1") else second, ())

    with pytest.raises(ValueError, match="paging_incomplete"):
        fetch_page(
            entry(dec, "monaqasat_classified"),
            read,
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=dec,
        )
    assert len(calls) <= 2 and not list(tmp_path.rglob("index/*.json"))


def test_unreviewed_path_refuses_before_send(tmp_path):
    dec, body, _ = embedded()
    calls = []
    dec["reviewed_urls"] = [URL + "/SYN-other"]
    with pytest.raises(ValueError, match="blocked_host"):
        fetch_page(
            entry(dec),
            lambda u: calls.append(u) or Response(u, body, ()),
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=dec,
        )
    assert calls == []


def test_multi_input_failure_preserves_previous_tree(tmp_path):
    dec = tariffs()
    dec["shape"]["discovery"] = {
        "url": URL,
        "record_path": [],
        "link_path": ["link"],
        "length_path": None,
        "modified_path": ["modified"],
        "count_header": "x-wp-total",
        "pages_header": "x-wp-totalpages",
    }
    dec["shape"]["pages"] = [
        {"url": URL + "/SYN-location", "state": "tariff", "layout": "single"}
    ]
    dec["reviewed_urls"].append(URL + "/SYN-location")

    def read(url):
        if url == URL:
            return Response(
                url,
                json.dumps(
                    [
                        {
                            "link": URL + "/SYN-location",
                            "modified": "2031-02-03T01:00:00",
                            "title": {"rendered": "SYN"},
                        }
                    ]
                ).encode(),
                (),
                headers={"x-wp-total": "1", "x-wp-totalpages": "1"},
            )
        return Response(url, tariff(), ())

    result = fetch_page(
        entry(dec, "manateq_tariffs"),
        read,
        tmp_path,
        lambda: STAMP,
        lambda _: None,
        declaration=dec,
    )
    assert len(json.loads(result.body)["inputs"]) == 2
    before = {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }

    def broken(url):
        response = read(url)
        return response if url == URL else Response(url, b"SYN wrong page", ())

    with pytest.raises(ValueError):
        fetch_page(
            entry(dec, "manateq_tariffs"),
            broken,
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=dec,
        )
    assert before == {
        str(p.relative_to(tmp_path)): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }


def test_v2_school_browser_scope_and_terms(tmp_path):
    from dataclasses import replace

    from eii_custodian.publicdata.fetch.certificate_pins import browser_agent

    dec, attrs = school()
    terms = URL + "/SYN-terms"
    dec["reviewed_urls"].append(terms)
    calls = []
    flags = []
    original = school_transport(attrs, calls)

    def read(url):
        flags.append((url, browser_agent()))
        return Response(url, b"<p>SYN terms</p>", ()) if url == terms else original(url)

    row = replace(entry(dec, "schools_private_directory"), terms_url=terms)
    result = fetch_page(
        row, read, tmp_path, lambda: STAMP, lambda _: None, declaration=dec
    )
    assert all(flag is (url != terms) for url, flag in flags)
    assert result.sidecar["terms_sha256"]


@pytest.mark.parametrize(
    "plant", ["layer", "where", "order", "record_path", "attribute_path"]
)
def test_school_unreviewed_query_shape_refuses_before_fetch(tmp_path, plant):
    dec, _ = school()
    if plant == "layer":
        dec["shape"]["layer"] = URL + "/SYN-unreviewed"
    if plant == "where":
        dec["shape"]["where"] = "SYN-not-closed"
    if plant == "order":
        dec["shape"]["order_by"] = "name"
    if plant == "record_path":
        dec["shape"]["record_path"] = ["SYN-records"]
    if plant == "attribute_path":
        dec["shape"]["attribute_path"] = ["SYN-attrs"]
    calls = []
    with pytest.raises(
        ValueError, match=r"blocked_host|school_field_refused|schema_missing"
    ):
        fetch_page(
            entry(dec, "schools_private_directory"),
            lambda u: calls.append(u),
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=dec,
        )
    assert calls == []


def test_insurance_discovery_uses_file_url_and_string_length(tmp_path):
    from custodian.tests.test_s2_t29_live_shapes import workbook

    dec, body = workbook()
    listing_url = URL + "/SYN-list"
    dec["reviewed_urls"].append(listing_url)
    dec["shape"]["discovery"] = dict(
        url=listing_url,
        record_path=["d", "results"],
        link_path=["File", "ServerRelativeUrl"],
        length_path=["File", "Length"],
        modified_path=["Modified"],
        count_header=None,
        pages_header=None,
    )
    listing = {
        "d": {
            "results": [
                {
                    "Link": None,
                    "File": {
                        "ServerRelativeUrl": "/syn-shape",
                        "Length": str(len(body)),
                    },
                    "Modified": "2031-02-03T00:00:00Z",
                    "FieldValuesAsText": {"Author": "SYN omitted metadata"},
                }
            ]
        }
    }
    calls = []

    def read(url):
        calls.append(url)
        return Response(
            url, json.dumps(listing).encode() if url == listing_url else body, ()
        )

    result = fetch_page(
        entry(dec, "insurance_tables"),
        read,
        tmp_path,
        lambda: STAMP,
        lambda _: None,
        declaration=dec,
    )
    payload = json.loads(result.body)
    assert calls == [listing_url, URL]
    assert [x["extension"] for x in payload["inputs"]] == ["json", "xlsx"]
    assert payload["inputs"][0]["representation"] == "reviewed_projection"
    assert all(
        b"SYN omitted metadata" not in p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    )
    listing["d"]["results"][0]["File"]["Length"] = len(body)
    with pytest.raises(ValueError, match="schema_missing"):
        fetch_page(
            entry(dec, "insurance_tables"),
            read,
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=dec,
        )


@pytest.mark.parametrize(
    "source,reason",
    [
        ("suppliers_tawteen", "anonymous_access_not_approved"),
        ("schools_private_directory", "schema_missing"),
        ("insurance_tables", "schema_missing"),
    ],
)
def test_source_kind_cannot_be_redeclared_to_bypass_its_guard(tmp_path, source, reason):
    dec, body, _ = embedded()
    calls = []
    with pytest.raises(ValueError, match=reason):
        fetch_page(
            entry(dec, source),
            lambda u: calls.append(u) or Response(u, body, ()),
            tmp_path,
            lambda: STAMP,
            lambda _: None,
            declaration=dec,
        )
    assert calls == []
