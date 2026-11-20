"""Discovery, school query and classified pagination survivor regressions."""

import json
from urllib.parse import parse_qs, urlsplit

import pytest
from custodian.tests.test_page_acquire_survivors_1 import refused, run
from custodian.tests.test_s2_t29_live_acquire import FIELDS, school, school_transport
from custodian.tests.test_s2_t29_live_shapes import (
    URL,
    classified,
    entry,
    tariff,
    tariffs,
    workbook,
)

from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.fetch.transport import Response, TransportFault


def discovery_case(kind):
    if kind == "xlsx":
        dec, body = workbook()
        source = "insurance_tables"
    else:
        dec, body = tariffs(), tariff()
        source = "manateq_tariffs"
    listing_url = URL + "/SYN-list"
    dec["reviewed_urls"].append(listing_url)
    dec["shape"]["discovery"] = dict(
        url=listing_url,
        record_path=["d", "results"],
        link_path=["link"],
        length_path=["length"],
        modified_path=["modified"],
        count_header=None,
        pages_header=None,
    )
    record = {"link": URL, "length": str(len(body)), "modified": "2031-02-03T00:00:00Z"}
    listing = {"d": {"results": [record]}}
    return dec, body, source, listing, record


@pytest.mark.parametrize("kind", ["xlsx", "tariff"])
def test_discovery_projection(tmp_path, kind):
    dec, body, source, listing, record = discovery_case(kind)
    record["SYN-private-extra"] = "SYN-discard"
    result = run(
        tmp_path,
        dec,
        body,
        row=entry(dec, source),
        send=lambda u: Response(
            u, json.dumps(listing).encode() if u.endswith("SYN-list") else body, ()
        ),
    )
    payload = json.loads(result.body)
    first = payload["inputs"][0]
    raw = read_snapshot(tmp_path / source / first["key"], first["identity"])
    assert (
        raw.body
        == json.dumps(
            [{"url": URL, "length": len(body), "source_modified": record["modified"]}],
            sort_keys=True,
        ).encode()
    )
    assert (
        first["extension"] == "json"
        and first["representation"] == "reviewed_projection"
    )
    assert len(payload["inputs"]) == 2
    if kind == "tariff":
        assert payload["rows"][0]["page_url"] == URL
        assert payload["rows"][0]["source_modified"] == record["modified"]
        assert payload["coverage"] == [{"url": URL, "state": "tariff"}]


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("not_list", "schema_missing"),
        ("header_missing", "paging_incomplete"),
        ("header_count", "paging_incomplete"),
        ("header_pages", "paging_incomplete"),
        ("next", "paging_incomplete"),
        ("count", "paging_incomplete"),
        ("link", "schema_missing"),
        ("length_ascii", "schema_missing"),
        ("length_unicode", "schema_missing"),
        ("modified", "schema_missing"),
        ("duplicate", "paging_incomplete"),
        ("selected_missing", "blocked_host"),
        ("length_mismatch", "schema_missing"),
    ],
)
def test_discovery_refusals(tmp_path, plant, reason):
    dec, body, source, listing, record = discovery_case("xlsx")
    headers = {}
    if plant == "not_list":
        listing["d"]["results"] = {}
    elif plant.startswith("header"):
        dec["shape"]["discovery"].update(count_header="x-count", pages_header="x-pages")
        headers = {"x-count": "1", "x-pages": "1"}
        if plant == "header_missing":
            headers = {}
        elif plant == "header_count":
            headers["x-count"] = "2"
        else:
            headers["x-pages"] = "2"
    elif plant in {"next", "count"}:
        listing["d"]["__" + plant] = "SYN"
    elif plant == "link":
        record["link"] = None
    elif plant == "length_ascii":
        record["length"] = "x"
    elif plant == "length_unicode":
        record["length"] = "\u0661"
    elif plant == "modified":
        record["modified"] = None
    elif plant == "duplicate":
        listing["d"]["results"].append(record.copy())
    elif plant == "selected_missing":
        record["link"] = URL + "/SYN-other"
    else:
        record["length"] = str(len(body) + 1)

    def send(u):
        return Response(
            u,
            json.dumps(listing).encode() if u.endswith("SYN-list") else body,
            (),
            headers=headers,
        )

    refused(reason, lambda: run(tmp_path, dec, body, row=entry(dec, source), send=send))
    assert not list(tmp_path.rglob("index/*.json"))


def test_discovery_header_success(tmp_path):
    dec, body, source, listing, _ = discovery_case("tariff")
    dec["shape"]["discovery"].update(count_header="x-count", pages_header="x-pages")

    def send(u):
        return Response(
            u,
            json.dumps(listing).encode() if u.endswith("SYN-list") else body,
            (),
            headers={"x-count": "1", "x-pages": "1"},
        )

    assert json.loads(run(tmp_path, dec, body, row=entry(dec, source), send=send).body)[
        "rows"
    ] == [
        {
            "label": "SYN  rate",
            "value": "7",
            "currency": "QR",
            "unit": "per square meter per year",
            "page_url": URL,
            "source_modified": "2031-02-03T00:00:00Z",
        }
    ]


def school_send(dec, attrs, calls, *, change=None, count=3):
    """Use the existing fake, validating exact outgoing query parameters."""
    original = school_transport(attrs, [])

    def send(url):
        calls.append(url)
        if url != dec["url"]:
            assert urlsplit(url).path == urlsplit(URL).path + "/query"
        q = parse_qs(urlsplit(url).query)
        assert q.get("f") == ["json"]
        if url == dec["url"]:
            obj = json.loads(original(url).body)
            obj["maxRecordCount"] = 2
            role = "metadata"
        elif "returnCountOnly" in q:
            assert q == {"where": ["1=1"], "returnCountOnly": ["true"], "f": ["json"]}
            obj, role = {"count": count}, "count"
        else:
            offset = int(q["resultOffset"][0])
            size = min(2, count - offset)
            assert q == {
                "where": ["1=1"],
                "outFields": [",".join(FIELDS)],
                "orderByFields": ["objectid"],
                "returnGeometry": ["true"],
                "resultOffset": [str(offset)],
                "resultRecordCount": [str(size)],
                "f": ["json"],
            }
            obj = {
                "geometryType": "esriGeometryPoint",
                "spatialReference": {"wkid": 2932},
                "fields": [{"name": f} for f in FIELDS],
                "features": [
                    {
                        "attributes": dict(attrs, objectid=i + 1),
                        "geometry": {"x": 1.5, "y": 2},
                    }
                    for i in range(offset, offset + size)
                ],
                "exceededTransferLimit": offset + size < count,
            }
            role = "page"
        if change:
            change(role, obj)
        return Response(url, json.dumps(obj).encode(), ())

    return send


def test_school_exact_query_and_geometry(tmp_path):
    dec, attrs = school()
    dec["shape"]["page_size"] = 2
    calls = []
    result = run(
        tmp_path,
        dec,
        b"",
        row=entry(dec, "schools_private_directory"),
        send=school_send(dec, attrs, calls),
    )
    payload = json.loads(result.body)
    assert len(calls) == 4 and len(payload["inputs"]) == 4
    assert [r["objectid"] for r in payload["rows"]] == [1, 2, 3]
    assert all(r["geometry"] == {"x": "1.5", "y": "2"} for r in payload["rows"])
    assert payload["rows"][0]["lat"] == "1.5"
    assert payload["rows"][0]["eng_type"] is None


@pytest.mark.parametrize("count", [0, -1, True])
def test_school_count_boundary(tmp_path, count):
    dec, attrs = school()
    calls = []
    send = school_send(dec, attrs, calls, count=count)
    if type(count) is int and count == 0:
        result = run(
            tmp_path, dec, b"", row=entry(dec, "schools_private_directory"), send=send
        )
        assert json.loads(result.body)["rows"] == [] and len(calls) == 2
    else:
        refused(
            "paging_incomplete",
            lambda: run(
                tmp_path,
                dec,
                b"",
                row=entry(dec, "schools_private_directory"),
                send=send,
            ),
        )


def test_school_count_fields_taken_as_published_integers():
    from eii_custodian.publicdata.fetch.page_schema import ShapeError, scalar, typed

    dec, _ = school()
    fields = dec["shape"]["record_schema"]["fields"]
    int_spec = {"kind": "integer", "nullable": True, "optional": False}
    assert scalar(412, "integer") == 412
    assert scalar(37, "integer") == 37
    assert scalar(None, "integer") is None
    for value in (412.5, "412", True, 412.0):
        with pytest.raises(ShapeError, match="schema_missing"):
            typed(value, int_spec)
    for name in ("students_n", "staff_num"):
        assert fields[name]["kind"] == "integer"
        typed(412 if name == "students_n" else 37, fields[name])


@pytest.mark.parametrize("field", ["director", "phone", "email"])
def test_school_personal_field_refused(tmp_path, field):
    dec, attrs = school()
    dec["shape"]["page_size"] = 2
    calls: list[str] = []

    def change(role, obj):
        if role == "page":
            obj["features"][0]["attributes"][field] = "SYN-personal"

    refused(
        "school_field_refused",
        lambda: run(
            tmp_path,
            dec,
            b"",
            row=entry(dec, "schools_private_directory"),
            send=school_send(dec, attrs, calls, change=change),
        ),
    )


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("objectid", "schema_missing"),
        ("geometry_type", "schema_missing"),
        ("order", "schema_missing"),
        ("pagination", "schema_missing"),
        ("maximum_small", "schema_missing"),
        ("maximum_type", "schema_missing"),
        ("metadata_missing", "schema_missing"),
        ("page_geometry", "schema_missing"),
        ("page_reference", "schema_missing"),
        ("fields_names", "school_field_refused"),
        ("fields_type", "school_field_refused"),
        ("empty", "paging_incomplete"),
        ("record_extra", "schema_missing"),
        ("attribute_extra", "school_field_refused"),
        ("geometry_extra", "schema_missing"),
        ("coordinate", "schema_missing"),
        ("duplicate", "paging_incomplete"),
        ("terminal", "paging_incomplete"),
    ],
)
def test_school_refusals(tmp_path, plant, reason):
    dec, attrs = school()
    dec["shape"]["page_size"] = 2

    def change(role, obj):
        if role == "metadata":
            if plant == "objectid":
                obj["objectIdField"] = "SYN-wrong"
            if plant == "geometry_type":
                obj["geometryType"] = "SYN-wrong"
            if plant == "order":
                obj["advancedQueryCapabilities"]["supportsOrderBy"] = False
            if plant == "pagination":
                obj["advancedQueryCapabilities"]["supportsPagination"] = False
            if plant == "maximum_small":
                obj["maxRecordCount"] = 1
            if plant == "maximum_type":
                obj["maxRecordCount"] = 2.5
            if plant == "metadata_missing":
                del obj["extent"]
        if role == "page":
            if plant == "page_geometry":
                obj["geometryType"] = "SYN-wrong"
            if plant == "page_reference":
                del obj["spatialReference"]
            if plant == "fields_names":
                obj["fields"][0]["name"] = "owner"
            if plant == "fields_type":
                obj["fields"] = {}
            if plant == "empty":
                obj["features"] = []
            if plant == "record_extra":
                obj["features"][0]["SYN-extra"] = 1
            if plant == "attribute_extra":
                obj["features"][0]["attributes"]["owner"] = "SYN"
            if plant == "geometry_extra":
                obj["features"][0]["geometry"]["z"] = 1
            if plant == "coordinate":
                obj["features"][0]["geometry"]["x"] = "1.5"
            if plant == "duplicate":
                for r in obj["features"]:
                    r["attributes"]["objectid"] = 1
            if plant == "terminal":
                obj["exceededTransferLimit"] = False

    refused(
        reason,
        lambda: run(
            tmp_path,
            dec,
            b"",
            row=entry(dec, "schools_private_directory"),
            send=school_send(dec, attrs, [], change=change),
        ),
    )
    assert not list(tmp_path.rglob("index/*.json"))


def test_school_failure_receipt(tmp_path):
    dec, _ = school()

    def send(url):
        raise TransportFault("unreachable", url)

    refused(
        "unreachable",
        lambda: run(
            tmp_path, dec, b"", row=entry(dec, "schools_private_directory"), send=send
        ),
    )
    records = [
        json.loads(p.read_text(encoding="utf-8")) for p in tmp_path.rglob("*.json")
    ]
    assert any(
        r.get("attempted_utc") == "2024-02-03T00:00:00Z"
        and r.get("reason") == "unreachable"
        for r in records
    )


@pytest.mark.parametrize(
    "plant,reason",
    [
        ("success", None),
        ("changed_end", "paging_incomplete"),
        ("duplicate", "paging_incomplete"),
        ("early_total", "paging_incomplete"),
        ("final_short", "paging_incomplete"),
        ("empty", "paging_incomplete"),
        ("overfull", "paging_incomplete"),
        ("last_over_total", "paging_incomplete"),
    ],
)
def test_classified_pages(tmp_path, plant, reason):
    dec, base = classified()
    first = base.replace(b"SYN total: 1", b"SYN total: 2").replace(
        b'/syn-shape/1">1</a>', b'/syn-shape/2">2</a>'
    )
    second = first.replace(b"SYN-profile", b"SYN-second")
    if plant == "changed_end":
        second = second.replace(b"SYN total: 2", b"SYN total: 3")
    if plant == "duplicate":
        second = first
    if plant == "final_short":
        first = first.replace(b"SYN total: 2", b"SYN total: 3")
        second = second.replace(b"SYN total: 2", b"SYN total: 3")
    if plant == "early_total":
        # Two records on first page, yet two pages declared.
        tr = b"<tr><td>1</td><td>SYN-profile</td>"
        begin = first.index(tr)
        end = first.index(b"</tr>", begin) + 5
        extra = (
            first[begin:end]
            .replace(b"SYN-profile", b"SYN-extra")
            .replace(b"openCompanyDataModel(7)", b"openCompanyDataModel(8)")
        )
        first = first[:end] + extra + first[end:]
        mstart = first.index(b'<div class="modal')
        mend = first.index(b'<div class="d-flex', mstart)
        first = (
            first[:mend]
            + first[mstart:mend].replace(b"CompanyData-7", b"CompanyData-8")
            + first[mend:]
        )
    if plant == "empty":
        begin = first.index(b"<tbody>") + len(b"<tbody>")
        end = first.index(b"</tbody>", begin)
        first = first[:begin] + first[end:]
        mstart = first.index(b'<div class="modal')
        mend = first.index(b'<div class="d-flex', mstart)
        first = first[:mstart] + first[mend:]
    if plant == "overfull":
        first = first.replace(b"SYN total: 2", b"SYN total: 1").replace(
            b'/syn-shape/2">2</a>', b'/syn-shape/1">1</a>'
        )
        begin = first.index(b"<tr><td>1</td>")
        end = first.index(b"</tr>", begin) + 5
        extra = (
            first[begin:end]
            .replace(b"SYN-profile", b"SYN-extra")
            .replace(b"openCompanyDataModel(7)", b"openCompanyDataModel(8)")
        )
        first = first[:end] + extra + first[end:]
        mstart = first.index(b'<div class="modal')
        mend = first.index(b'<div class="d-flex', mstart)
        first = (
            first[:mend]
            + first[mstart:mend].replace(b"CompanyData-7", b"CompanyData-8")
            + first[mend:]
        )
    if plant == "last_over_total":
        first = first.replace(b'/syn-shape/2">2</a>', b'/syn-shape/3">3</a>')
    calls = []

    def send(u):
        calls.append(u)
        return Response(u, first if u.endswith("/1") else second, ())

    if reason:
        refused(
            reason,
            lambda: run(
                tmp_path, dec, b"", row=entry(dec, "monaqasat_classified"), send=send
            ),
        )
        if plant in {"empty", "last_over_total", "early_total", "overfull"}:
            assert calls == [dec["url"]]
    else:
        assert (
            len(
                json.loads(
                    run(
                        tmp_path,
                        dec,
                        b"",
                        row=entry(dec, "monaqasat_classified"),
                        send=send,
                    ).body
                )["rows"]
            )
            == 2
        )


def test_classified_single_page(tmp_path):
    dec, body = classified()
    assert (
        len(
            json.loads(
                run(tmp_path, dec, body, row=entry(dec, "monaqasat_classified")).body
            )["rows"]
        )
        == 1
    )


def test_classified_overrun_stops_before_next_request(tmp_path):
    dec, first = classified()
    first = first.replace(b"SYN total: 1", b"SYN total: 2").replace(
        b'/syn-shape/1">1</a>', b'/syn-shape/2">2</a>'
    )
    begin = first.index(b"<tr><td>1</td>")
    end = first.index(b"</tr>", begin) + 5
    row = first[begin:end]
    mstart = first.index(b'<div class="modal')
    mend = first.index(b'<div class="d-flex', mstart)
    modal = first[mstart:mend]
    extra_rows = b"".join(
        row.replace(b"SYN-profile", b"SYN-" + n).replace(
            b"openCompanyDataModel(7)", b"openCompanyDataModel(" + n + b")"
        )
        for n in (b"8", b"9")
    )
    first = first[:end] + extra_rows + first[end:]
    mend = first.index(b'<div class="d-flex')
    first = (
        first[:mend]
        + b"".join(
            modal.replace(b"CompanyData-7", b"CompanyData-" + n) for n in (b"8", b"9")
        )
        + first[mend:]
    )
    calls = []

    def send(url):
        calls.append(url)
        return Response(url, first, ())

    refused(
        "paging_incomplete",
        lambda: run(
            tmp_path, dec, b"", row=entry(dec, "monaqasat_classified"), send=send
        ),
    )
    assert calls == [dec["url"]]
