"""Invented MTH-109 values; no fetched observations."""

import http.client
import io
import json
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.fixtures.grids.invented import (
    entry,
    night_file,
    store,
    write_night_root,
    write_scale_offset,
)
from custodian.tests.repository_root import repository_root
from shapely.geometry import box

from eii_custodian.publicdata.fetch.allowlist import (
    ALLOWED_HOSTS,
    NAMED_RADIANCE_HOST,
    approve,
)
from eii_custodian.publicdata.fetch.registry import load_registry, nightly_blocked
from eii_custodian.publicdata.fetch.transport import (
    Response,
    TransportFault,
    authorization_header,
    open_https,
)
from eii_custodian.publicdata.grids.build import build_grids
from eii_custodian.publicdata.grids.contracts import GridError
from eii_custodian.publicdata.grids.fetch import (
    ARCHIVE,
    day_folder,
    granule_name,
    prepare_grid,
)
from eii_custodian.publicdata.grids.night_lights import (
    Pixel,
    aggregate,
    area_mean,
    read_night_lights,
)

_SCRIPTS = repository_root(Path(__file__)) / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def test_night_mth109():
    pixels = [
        Pixel("SYN-a", 0.1, 0.5, Decimal(2), 0),
        Pixel("SYN-b", 0.2, 0.5, Decimal(4), 0),
        Pixel("SYN-c", 0.3, 0.5, Decimal(6), 0),
        Pixel("SYN-fill", 0.4, 0.5, None, 255),
        Pixel("SYN-d", 1.5, 0.5, Decimal(10), 0),
        Pixel("SYN-empty", 2.5, 0.5, None, 255),
    ]
    cells = {1: box(0, 0, 1, 1), 2: box(1, 0, 2, 1), 3: box(2, 0, 3, 1)}
    result = aggregate(pixels, cells, "2024-01")
    assert [row["radiance"] for row in result.rows] == [Decimal(4), Decimal(10)]
    assert result.missing == {3: "NO_DATA"}
    assert area_mean(result.rows) == Decimal(7)
    assert area_mean([]) is None


@pytest.mark.parametrize("offset_name", ["offset", "add_offset"])
def test_night_local_layout(tmp_path, offset_name):
    """Read one invented row. ``add_offset`` is a planted name the product does not ship."""
    pixels = read_night_lights(
        tmp_path, night_file(tmp_path / "SYN.h5", offset_name), "2024-01"
    )
    assert [p.value for p in pixels] == [
        Decimal(4),
        Decimal(6),
        Decimal(8),
        None,
        Decimal(10),
        Decimal(2),
    ]
    result = aggregate(pixels, {1: box(0, 0, 4, 1)}, "2024-01")
    assert result.rows[0]["radiance"] == Decimal("5.3333")
    assert result.excluded == {
        "poor": 1,
        "history": 1,
        "quality_fill": 1,
        "radiance_fill": 1,
    }


@pytest.mark.parametrize(
    "path",
    [
        "https://example.invalid/file",
        "file:///tmp/file",
        "/vsicurl/https://example.invalid/file",
        "/vsizip/file",
    ],
)
def test_night_refuses_remote_before_library(tmp_path, monkeypatch, path):
    monkeypatch.setattr(
        "eii_custodian.publicdata.grids.night_lights.import_module",
        lambda _: pytest.fail("library called"),
    )
    with pytest.raises(GridError, match="remote or virtual"):
        read_night_lights(tmp_path, path, "2024-01")


def test_night_escape_and_nonfile(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    outside = tmp_path / "SYN.h5"
    outside.write_bytes(b"invented")
    link = cache / "link"
    link.symlink_to(outside)
    with pytest.raises(GridError, match="outside cache"):
        read_night_lights(cache, link, "2024-01")
    with pytest.raises(GridError, match="regular file"):
        read_night_lights(cache, cache, "2024-01")


def test_night_month_and_product(tmp_path):
    import h5py

    path = night_file(tmp_path / "SYN.h5")
    with pytest.raises(GridError, match=r"^ntl_blackmarble: period mismatch$"):
        read_night_lights(tmp_path, path, "2024-02")
    with h5py.File(path, "r+") as source:
        source.attrs["VersionID"] = "001"
    with pytest.raises(GridError, match=r"^ntl_blackmarble: unsupported product$"):
        read_night_lights(tmp_path, path, "2024-01")


def test_night_edges_zero_duplicates_and_overlap():
    pixel = Pixel("SYN-a", 1, 0.5, Decimal(0), 0)
    cells = {2: box(1, 0, 2, 1), 1: box(0, 0, 1, 1)}
    result = aggregate([pixel], cells, "2024-01")
    assert result.rows[0]["cell"] == 1
    assert result.rows[0]["radiance"] == 0
    assert result.missing == {2: "NO_DATA"}
    with pytest.raises(GridError, match=r"^ntl_blackmarble: duplicate pixel$"):
        aggregate([pixel, pixel], cells, "2024-01")
    with pytest.raises(GridError, match=r"^ntl_blackmarble: overlapping ownership$"):
        aggregate([pixel], {1: box(0, 0, 2, 1), 2: box(0, 0, 3, 1)}, "2024-01")
    with pytest.raises(GridError, match=r"^ntl_blackmarble: duplicate cell$"):
        area_mean(result.rows * 2)
    assert (
        aggregate([Pixel("SYN-out", 10, 10, Decimal(1), 0)], cells, "2024-01").rows
        == []
    )


@pytest.mark.parametrize(
    "value,quality,reason",
    [
        (Decimal(-1), 0, "ntl_blackmarble: invalid radiance"),
        (Decimal("NaN"), 0, "ntl_blackmarble: invalid radiance"),
        (Decimal(1), 3, "ntl_blackmarble: unknown quality code"),
    ],
)
def test_night_invalid_pixel(value, quality, reason):
    with pytest.raises(GridError, match=rf"^{reason}$"):
        aggregate([Pixel("SYN-a", 0, 0, value, quality)], {}, "2024-01")


@pytest.mark.parametrize(
    "change,reason",
    [
        ("name", "ntl_blackmarble: unsupported product"),
        ("granule", "ntl_blackmarble: granule period or tile mismatch"),
        ("shape", "ntl_blackmarble: array shape mismatch"),
        ("quality_shape", "ntl_blackmarble: array shape mismatch"),
    ],
)
def test_night_metadata_plants(tmp_path, change, reason):
    import h5py

    from eii_custodian.publicdata.grids.night_lights import FIELD, GROUP

    path = night_file(tmp_path / "SYN.h5")
    with h5py.File(path, "r+") as source:
        attrs = source.attrs
        if change == "name":
            attrs["ShortName"] = "SYN-other"
        if change == "granule":
            attrs["LocalGranuleID"] = "SYN-other"
        if change == "shape":
            del source[GROUP + "lon"]
            source[GROUP].create_dataset("lon", data=[0.5])
        if change == "quality_shape":
            del source[GROUP + FIELD + "_Quality"]
            source[GROUP].create_dataset(FIELD + "_Quality", data=[[0]])
    with pytest.raises(GridError, match=rf"^{reason}$"):
        read_night_lights(tmp_path, path, "2024-01")


def test_night_good_fill_is_missing():
    result = aggregate(
        [Pixel("SYN-fill", 0, 0, None, 0)], {1: box(-1, -1, 1, 1)}, "2024-01"
    )
    assert result.rows == []
    assert result.excluded["radiance_fill"] == 1


def _sleep(_seconds: float) -> None:
    return None


YEAR_URL = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5200/VNP46A3/2024/"
PRODUCT_DOI = "10.5067/VIIRS/VNP46A3.002"
NASA_ACK = "NASA should be acknowledged as the source of the material where applicable."
DAY_URL = YEAR_URL + "001/"
GRANULE = "VNP46A3.A2024001.h23v06.002.SYN.h5"
FILE_URL = DAY_URL + GRANULE
YEAR_LISTING = (
    b"<!DOCTYPE html>\n"
    b"<html><head><title>Index of /archive/allData/5200/VNP46A3/2024/"
    b"</title></head><body>\n"
    b"<h1>Index of /archive/allData/5200/VNP46A3/2024/</h1>\n"
    b'<table><tr><th><a href="?C=N;O=D">Name</a></th>'
    b'<th><a href="?C=M;O=A">Last modified</a></th>'
    b'<th><a href="?C=S;O=A">Size</a></th></tr>\n'
    b'<tr><td><a href="https://www.nasa.gov/">Parent Directory</a></td>'
    b'<td>&nbsp;</td><td align="right">-</td></tr>\n'
    b'<tr><th colspan="3"><hr></th></tr>\n'
    b"</table>\n"
    b'<pre><a href="../">Parent Directory</a>\n'
    b'<a href="001/">SYN-not-the-day-folder</a> 2024-01-02 03:04  5.0K\n'
    b'<a href="002/">001/</a> 2024-02-03 04:05  6.0K\n'
    b'<a href="https://www.nasa.gov/">002/</a>\n'
    b"</pre>\n"
    b"</body></html>\n"
)
FULL_YEAR_LISTING = YEAR_LISTING.replace(
    b'<a href="002/">001/</a> 2024-02-03 04:05  6.0K\n', b""
).replace(
    b"</pre>",
    b"".join(
        f'<a href="{YEAR_URL}{day}/">SYN-month</a>\n'.encode("ascii")
        for day in (
            "032",
            "061",
            "092",
            "122",
            "153",
            "183",
            "214",
            "245",
            "275",
            "306",
            "336",
        )
    )
    + b"</pre>",
)
DAY_LISTING = (
    b"<!DOCTYPE html>\n"
    b"<html><head><title>Index of /archive/allData/5200/VNP46A3/2024/001/"
    b"</title></head><body>\n"
    b"<h1>Index of /archive/allData/5200/VNP46A3/2024/001/</h1>\n"
    b'<table><tr><th><a href="?C=N;O=D">Name</a></th>'
    b'<th><a href="?C=M;O=A">Last modified</a></th>'
    b'<th><a href="?C=S;O=A">Size</a></th></tr>\n'
    b'<tr><td><a href="https://www.nasa.gov/">Parent Directory</a></td>'
    b'<td>&nbsp;</td><td align="right">-</td></tr>\n'
    b'<tr><th colspan="3"><hr></th></tr>\n'
    b"</table>\n"
    b'<pre><a href="../">Parent Directory</a>\n'
    + (b'<a href="' + GRANULE.encode("ascii") + b'">SYN-not-the-granule</a>\n') * 3
    + (
        b'<a href="VNP46A3.A2024001.h22v06.002.SYN.h5">'
        + GRANULE.encode("ascii")
        + b"</a>\n"
    )
    * 3
    + b'<a href="https://www.nasa.gov/">h23v06</a>\n'
    + b"</pre>\n"
    + b"</body></html>\n"
)


def _radiance_row():
    return entry(
        "ntl_blackmarble",
        "ntl_blackmarble/2024-01",
        period="2024-01",
        tile="h23v06",
        release="VNP46A3.002",
        doi=PRODUCT_DOI,
        acknowledgement=NASA_ACK,
        extension="h5",
        licence_id="NASA-guidance",
        url=YEAR_URL,
        fetch_host="ladsweb.modaps.eosdis.nasa.gov",
        release_tables=("pub_night_lights",),
        caveat_keys=("night_lights_not_activity",),
    )


def test_night_bearer_header_only_on_the_archive_host():
    token = "SYN-invented-token"
    assert authorization_header(FILE_URL, token) == {"Authorization": f"Bearer {token}"}
    assert authorization_header("https://data.worldpop.org/SYN.tif", token) == {}
    assert authorization_header(FILE_URL, "") == {}
    assert authorization_header("https://evil.example/SYN.h5", token) == {}


def test_night_open_https_sends_the_header_and_returns_no_token(monkeypatch):
    token = "SYN-invented-token"
    payload = (
        "HTTP/1.1 200 OK\r\nContent-Length: 8\r\nConnection: close\r\n\r\ninvented"
    ).encode("ascii")
    sent: list[bytes] = []

    class _Socket:
        def sendall(self, data: bytes) -> None:
            sent.append(data)

        def send(self, data: bytes) -> int:
            return len(data)

        def makefile(
            self, mode: str = "rb", *_args: object, **_kwargs: object
        ) -> io.BytesIO:
            return io.BytesIO(payload)

        def close(self) -> None:
            return None

    def connect(connection: http.client.HTTPSConnection) -> None:
        connection.sock = _Socket()

    monkeypatch.setattr(http.client.HTTPSConnection, "connect", connect)
    response = open_https(FILE_URL, token)
    assert response.body == b"invented"
    request = b"".join(sent)
    assert b"Authorization: Bearer " + token.encode("ascii") in request
    assert token.encode("ascii") not in response.body


def test_night_open_https_strips_the_header_on_an_unrelated_redirect(monkeypatch):
    token = "SYN-invented-token"
    payloads = [
        b"HTTP/1.1 302 Found\r\nLocation: https://data.worldpop.org/SYN.tif\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nContent-Length: 8\r\nConnection: close\r\n\r\ninvented",
    ]
    sent: list[bytes] = []

    class _Socket:
        def __init__(self, payload: bytes) -> None:
            self.payload = payload

        def sendall(self, data: bytes) -> None:
            sent.append(data)

        def makefile(self, mode: str = "rb", *_args: object, **_kwargs: object):
            return io.BytesIO(self.payload)

        def close(self) -> None:
            return None

    def connect(connection: http.client.HTTPSConnection) -> None:
        connection.sock = _Socket(payloads.pop(0))

    monkeypatch.setattr(http.client.HTTPSConnection, "connect", connect)
    response = open_https(FILE_URL, token)
    assert response.body == b"invented"
    assert len(sent) == 2
    assert token.encode("ascii") in sent[0]
    assert token.encode("ascii") not in sent[1]


def test_night_year_listing_picks_the_day_folder():
    assert day_folder(YEAR_LISTING, YEAR_URL, "2024-01") == DAY_URL
    assert day_folder(YEAR_LISTING, YEAR_URL, "2024-02") is None
    assert day_folder(b"\xff\xfe", YEAR_URL, "2024-01") is None
    assert day_folder(b"<html>no links</html>", YEAR_URL, "2024-01") is None


@pytest.mark.parametrize(
    "listing",
    [
        b'<a href="001/">001/</a><a href="001/?SYN=other">001/</a>',
        b'<a href="https://evil.example/001/">001/</a>',
        b'<a href="https://evil.example/archive/allData/5200/VNP46A3/2024/001/">001/</a>',
        b'<a href="001/">SYN-valid</a><a href="https://evil.example/001/">001/</a>',
        b'<a href="001/">SYN-valid</a><a href="https://evil.example/archive/allData/5200/VNP46A3/2024/001/">001/</a>',
    ],
)
def test_night_year_listing_refuses_ambiguity_and_off_host(listing):
    assert day_folder(listing, YEAR_URL, "2024-01") is None


def test_night_listing_refuses_a_wanted_row_outside_the_folder():
    """A wanted row that leaves the current folder is refused, by href."""
    outside_day = b'<a href="../001/">001/</a>'
    assert day_folder(outside_day, YEAR_URL, "2024-01") is None
    outside_granule = (
        b'<a href="../001/' + GRANULE.encode("ascii") + b'">SYN-not-the-granule</a>'
    )
    assert granule_name(outside_granule, DAY_URL, "2024-01", "h23v06") is None
    absolute_day = b'<a href="/archive/allData/5200/VNP46A3/001/">001/</a>'
    assert day_folder(absolute_day, YEAR_URL, "2024-01") is None
    absolute_granule = (
        b'<a href="/archive/allData/5200/VNP46A3/001/'
        + GRANULE.encode("ascii")
        + b'">SYN-not-the-granule</a>'
    )
    assert granule_name(absolute_granule, DAY_URL, "2024-01", "h23v06") is None


def test_night_day_listing_picks_the_month_and_tile():
    assert granule_name(DAY_LISTING, DAY_URL, "2024-01", "h23v06") == FILE_URL
    assert granule_name(DAY_LISTING, DAY_URL, "2024-02", "h23v06") is None
    assert granule_name(DAY_LISTING, DAY_URL, "2024-01", "h21v06") is None
    assert granule_name(b"not-html", DAY_URL, "2024-01", "h23v06") is None


def test_night_day_listing_matches_the_product_suffix_after_the_tile():
    name = "VNP46A3.A2024001.h23v06.003.SYN.h5"
    listing = b'<a href="' + name.encode("ascii") + b'">SYN-other-suffix</a>'
    assert granule_name(listing, DAY_URL, "2024-01", "h23v06") == DAY_URL + name


@pytest.mark.parametrize("prefix", ["", "./"])
def test_night_day_listing_accepts_one_distinct_address(prefix):
    twice = (f'<a href="{GRANULE}">a</a><a href="{prefix}{GRANULE}">b</a>').encode(
        "ascii"
    )
    assert granule_name(twice, DAY_URL, "2024-01", "h23v06") == FILE_URL


@pytest.mark.parametrize("prefix", ["", "./"])
def test_night_year_listing_accepts_one_distinct_address(prefix):
    twice = f'<a href="001/">a</a><a href="{prefix}001/">b</a>'.encode("ascii")
    assert day_folder(twice, YEAR_URL, "2024-01") == DAY_URL


def test_night_day_listing_refuses_ambiguity():
    other = GRANULE.replace(".SYN.h5", ".SYN-other.h5")
    twice = f'<a href="{GRANULE}">a</a><a href="{other}">b</a>'.encode("ascii")
    assert granule_name(twice, DAY_URL, "2024-01", "h23v06") is None
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == YEAR_URL:
            return Response(url, FULL_YEAR_LISTING, ())
        if url == DAY_URL:
            return Response(url, twice, ())
        raise AssertionError("ambiguous granules must never fetch a file")

    prepared = prepare_grid(_radiance_row(), transport, _sleep, "SYN-invented-token")
    assert prepared.failure is not None
    assert prepared.failure.check == "granule_missing"
    assert seen == [YEAR_URL, DAY_URL]


def test_night_prepare_refuses_ambiguous_day_addresses():
    listing = b'<a href="001/">a</a><a href="001/?SYN=other">b</a>'
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        assert url == YEAR_URL
        return Response(url, listing, ())

    prepared = prepare_grid(_radiance_row(), transport, _sleep, "SYN-invented-token")
    assert prepared.failure is not None
    assert prepared.failure.check == "day_missing"
    assert seen == [YEAR_URL]


def test_night_prepare_browses_year_then_day_then_file():
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == YEAR_URL:
            return Response(url, FULL_YEAR_LISTING, ())
        if url == DAY_URL:
            return Response(url, DAY_LISTING, ())
        return Response(url, b"invented-h5", ())

    prepared = prepare_grid(_radiance_row(), transport, _sleep, "SYN-invented-token")
    assert prepared.failure is None
    assert prepared.body == b"invented-h5"
    assert seen == [YEAR_URL, DAY_URL, FILE_URL]
    assert prepared.fetch_host == "ladsweb.modaps.eosdis.nasa.gov"


def test_night_prepare_refuses_without_a_token():
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        return Response(url, b"invented", ())

    prepared = prepare_grid(_radiance_row(), transport, _sleep, "")
    assert prepared.failure is not None
    assert prepared.failure.check == "credential_absent"
    assert seen == []


def test_night_refused_credential_is_not_retried():
    """A missing or refused credential is one attempt, never a retry."""
    calls = 0

    def transport(url: str) -> Response:
        nonlocal calls
        calls += 1
        raise TransportFault("credential_missing_or_not_accepted", url)

    prepared = prepare_grid(_radiance_row(), transport, _sleep, "SYN-invented-token")
    assert prepared.failure is not None
    assert prepared.failure.check == "credential_missing_or_not_accepted"
    assert calls == 1


def test_night_prepare_refuses_a_missing_granule():
    def transport(url: str) -> Response:
        if url == YEAR_URL:
            return Response(url, FULL_YEAR_LISTING, ())
        return Response(url, b"<html>no granules</html>", ())

    prepared = prepare_grid(_radiance_row(), transport, _sleep, "SYN-invented-token")
    assert prepared.failure is not None
    assert prepared.failure.check == "granule_missing"


def test_night_prepare_refuses_an_off_host_matching_granule():
    seen: list[str] = []
    poisoned = DAY_LISTING.replace(
        b"</pre>",
        b'<a href="https://evil.example/'
        + GRANULE.encode("ascii")
        + b'">SYN-off-host-match</a></pre>',
    )

    def transport(url: str) -> Response:
        seen.append(url)
        if url == YEAR_URL:
            return Response(url, FULL_YEAR_LISTING, ())
        if url == DAY_URL:
            return Response(url, poisoned, ())
        raise AssertionError("a poisoned listing must never fetch the file")

    prepared = prepare_grid(_radiance_row(), transport, _sleep, "SYN-invented-token")
    assert prepared.failure is not None
    assert prepared.failure.check == "granule_missing"
    assert seen == [YEAR_URL, DAY_URL]


def test_night_prepare_refuses_a_missing_day_folder():
    def transport(url: str) -> Response:
        return Response(url, b'<a href="002/">002/</a>', ())

    prepared = prepare_grid(_radiance_row(), transport, _sleep, "SYN-invented-token")
    assert prepared.failure is not None
    assert prepared.failure.check == "day_missing"


def test_night_frame_table_and_manifest(tmp_path):
    row = _radiance_row()
    body = night_file(tmp_path / "SYN.h5").read_bytes()
    digest = store(tmp_path, row, body)
    cells = {1: box(0, 0, 1, 1), 3: box(2, 0, 3, 1), 4: box(3, 0, 4, 1)}
    result = build_grids(tmp_path, (row,), cells)
    rows = result.tables["pub_night_lights"]
    assert [(item["cell"], item["radiance"]) for item in rows] == [
        (1, Decimal(4)),
        (3, Decimal(10)),
        (4, Decimal(2)),
    ]
    assert all(item["period"] == "2024-01" for item in rows)
    assert all(item["source_key"] == row.key for item in rows)
    assert all(item["source_sha256"] == digest for item in rows)
    assert all(item["method"] == "C36" for item in rows)
    assert all(item["method_version"] == "MTH-109" for item in rows)
    assert all(item["provenance"] == "Public" for item in rows)
    assert all(item["evidence_status"] == "Observed" for item in rows)
    assert all(item["caveat_keys"] == ["night_lights_not_activity"] for item in rows)
    manifest = json.loads((tmp_path / "grids" / "manifest.json").read_text("utf-8"))
    assert manifest["files"][0]["sha256"] == digest
    assert manifest["files"][0]["period"] == "2024-01"
    assert manifest["files"][0]["tile"] == "h23v06"
    assert manifest["tables"]["pub_night_lights"] == 3
    assert result.sources[row.key]["method"] == "C36"
    assert result.sources[row.key]["method_version"] == "MTH-109"
    lineage = result.tables["fact_lineage"]
    assert [item["table"] for item in lineage] == ["pub_night_lights"]
    assert lineage[0]["source_key"] == row.key
    assert lineage[0]["source_sha256"] == digest
    assert lineage[0]["method"] == "C36"
    assert lineage[0]["method_version"] == "MTH-109"
    assert lineage[0]["licence_id"] == "NASA-guidance"
    assert lineage[0]["licence_url"] == ""
    assert lineage[0]["retrieved_utc"] == "2026-11-14T00:00:00Z"
    assert lineage[0]["period"] == "2024-01"
    assert lineage[0]["provenance"] == "Public"
    assert lineage[0]["evidence_status"] == "Observed"
    registry = result.tables["source_registry"]
    assert [item["source_key"] for item in registry] == [row.key]
    assert registry[0]["source_sha256"] == digest
    assert registry[0]["dataset"] == row.url
    assert {
        reason: result.coverage[f"{row.key}:quality:{reason}"]
        for reason in ("poor", "history", "quality_fill", "radiance_fill")
    } == {"poor": "1", "history": "1", "quality_fill": "0", "radiance_fill": "0"}


def test_night_frame_table_refuses_a_tampered_file(tmp_path):
    row = _radiance_row()
    body = night_file(tmp_path / "SYN.h5").read_bytes()
    digest = store(tmp_path, row, body)
    (tmp_path / row.key / f"{digest}.h5").write_bytes(b"tampered")
    with pytest.raises(GridError, match="content hash mismatch"):
        build_grids(tmp_path, (row,), {1: box(0, 0, 1, 1)})


def test_night_frame_table_refuses_a_diverged_receipt(tmp_path):
    row = _radiance_row()
    body = night_file(tmp_path / "SYN.h5").read_bytes()
    digest = store(tmp_path, row, body)
    path = tmp_path / row.key / f"{digest}.meta.json"
    loaded = json.loads(path.read_text("utf-8"))
    loaded["file"]["tile"] = "h22v06"
    path.write_text(json.dumps(loaded), encoding="utf-8")
    with pytest.raises(GridError, match="receipt file mismatch"):
        build_grids(tmp_path, (row,), {1: box(0, 0, 1, 1)})


def test_night_frame_table_omits_an_absent_cache(tmp_path):
    row = _radiance_row()
    result = build_grids(tmp_path, (row,), {1: box(0, 0, 1, 1)})
    assert result.tables["pub_night_lights"] == []
    assert result.coverage == {f"{row.key}:omitted": "NO_CACHE"}
    assert result.manifest["files"] == []
    assert not (tmp_path / "grids" / "manifest.json").exists()


def test_night_registry_activation():
    entries = load_registry()
    months = [
        item
        for item in entries
        if item.source_id == "ntl_blackmarble" and "/" in item.key
    ]
    expected = [
        f"{year}-{month:02d}" for year in (2024, 2025) for month in range(1, 13)
    ]
    assert [item.period for item in months] == expected
    assert {item.tile for item in months} == {"h23v06"}
    assert all(item.url == ARCHIVE.format(year=item.period[:4]) for item in months)
    assert all("/allData/5200/VNP46A3/" in item.url for item in months)
    assert {item.doi for item in months} == {PRODUCT_DOI}
    assert {item.acknowledgement for item in months} == {NASA_ACK}
    assert months[0].period_first == months[0].period
    assert months[0].period_last == months[0].period
    assert months[0].release == "VNP46A3.002"
    assert all(item.nightly_live_fetch is False for item in months)
    assert months[0].public_splits == ()
    assert months[0].release_tables == ("pub_night_lights",)
    assert months[0].caveat_keys == ("night_lights_not_activity",)
    assert months[0].fetch_host == "ladsweb.modaps.eosdis.nasa.gov"
    assert approve(months[0].url).ok
    assert nightly_blocked(entries, ("ntl_blackmarble",)) == ("ntl_blackmarble",)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"period": "2024-2"}, "recorded form"),
        ({"tile": "bad"}, "recorded form"),
        ({"release": ""}, "release is empty"),
    ],
)
def test_night_registry_refuses_bad_optional_fields(tmp_path, change, reason):
    import yaml

    from eii_custodian.publicdata.fetch.registry import RegistryError, registry_path

    document = yaml.safe_load(registry_path().read_text(encoding="utf-8"))
    existing = next(row for row in document["sources"] if row["key"] == "lic_active")
    existing_before = existing.copy()
    row = next(
        row for row in document["sources"] if row["key"] == "ntl_blackmarble/2024-01"
    )
    row.update(change)
    assert existing == existing_before
    path = tmp_path / "bad-night.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(RegistryError, match=reason):
        load_registry(path)


def test_night_hosts_are_allow_listed():
    assert NAMED_RADIANCE_HOST in ALLOWED_HOSTS
    assert approve(YEAR_URL).ok
    assert approve(FILE_URL).ok
    for refused in (
        "https://cmr.earthdata.nasa.gov/search/granules.json",
        "https://data.laadsdaac.earthdatacloud.nasa.gov/SYN.h5",
        "https://www.earthdata.nasa.gov/engage/open-data-services-software-policies",
        "https://d13j1jds5ybppo.cloudfront.net/prod-lads/VNP46A3/SYN.h5",
    ):
        assert approve(refused).ok is False
        assert approve(refused).reason == "host_refused"


def test_night_absent_key_continues_and_omits_the_layer(tmp_path, monkeypatch, capsys):
    import commands.build_public as build_public

    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        return Response(url, b"invented", ())

    second = replace(_radiance_row(), key="ntl_blackmarble/2024-02", period="2024-02")
    monkeypatch.setattr(
        build_public, "load_registry", lambda: (_radiance_row(), second)
    )
    monkeypatch.setattr(build_public, "utc_now", lambda: "2026-11-14T00:00:00Z")
    code = build_public.run(tmp_path, {}, (), transport=transport, sleep=_sleep)
    captured = capsys.readouterr()
    assert code == 0
    assert (
        "OMIT ntl_blackmarble: EARTHDATA_API_KEY absent; night-lights layer left out"
        in captured.out
    )
    assert "EARTHDATA_API_KEY" in captured.out
    assert "night-lights" in captured.out
    assert captured.out.count("EARTHDATA_API_KEY") == 1
    assert seen == []
    assert not (tmp_path / "data" / "public_cache" / "grids").exists()
    assert (
        list((tmp_path / "data" / "public_cache" / "ntl_blackmarble").glob("*")) == []
    )


def test_skipped_month_keeps_its_skip_line_and_one_omit(tmp_path, monkeypatch, capsys):
    """A skipped month still gets its skip line; other months share one omit line."""
    import commands.build_public as build_public

    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        return Response(url, b"invented", ())

    skipped = replace(
        _radiance_row(),
        key="ntl_blackmarble/2024-03",
        period="2024-03",
        skip_reason="invented-month-not-fetched",
    )
    second = replace(_radiance_row(), key="ntl_blackmarble/2024-02", period="2024-02")
    monkeypatch.setattr(
        build_public,
        "load_registry",
        lambda: (skipped, _radiance_row(), second),
    )
    monkeypatch.setattr(build_public, "utc_now", lambda: "2026-11-14T00:00:00Z")
    code = build_public.run(tmp_path, {}, (), transport=transport, sleep=_sleep)
    captured = capsys.readouterr()
    assert code == 0
    assert f"SKIP {skipped.key} {skipped.skip_reason}" in captured.out
    assert (
        captured.out.count(
            "OMIT ntl_blackmarble: EARTHDATA_API_KEY absent; "
            "night-lights layer left out"
        )
        == 1
    )
    assert seen == []


def test_night_present_key_fetches_the_month(tmp_path, monkeypatch, capsys):
    import commands.build_public as build_public

    body = night_file(tmp_path / "SYN.h5").read_bytes()
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        if url == YEAR_URL:
            return Response(url, FULL_YEAR_LISTING, ())
        if url == DAY_URL:
            return Response(url, DAY_LISTING, ())
        return Response(url, body, ())

    monkeypatch.setattr(build_public, "load_registry", lambda: (_radiance_row(),))
    monkeypatch.setattr(build_public, "utc_now", lambda: "2026-11-14T00:00:00Z")
    code = build_public.run(
        tmp_path,
        {"EARTHDATA_API_KEY": "SYN-invented-token"},
        (),
        transport=transport,
        sleep=_sleep,
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "absent" not in captured.out
    assert seen == [YEAR_URL, DAY_URL, FILE_URL]
    cache = tmp_path / "data" / "public_cache"
    assert not (cache / "grids").exists()
    blob = "\n".join(path.read_text("utf-8") for path in cache.rglob("*.json"))
    assert "SYN-invented-token" not in blob
    assert "SYN-invented-token" not in captured.out


def test_night_live_frame_merges_the_grid_tables(tmp_path, monkeypatch):
    import json as json_module
    from pathlib import Path

    from custodian.tests.fixtures.frame.invented import (
        invented_archive,
        invented_layer,
    )

    from eii_custodian.publicdata.fetch.receipts import (
        commit_pair,
        sha256_hex,
        sidecar_for,
    )
    from eii_custodian.publicdata.frame import live
    from eii_custodian.publicdata.frame.build import build_frame
    from eii_custodian.publicdata.grids.build import build_grids as real_grids

    review = tmp_path / "review"
    review.mkdir()
    arabic = "اسم تجريبي"
    (review / "municipality_names.csv").write_text(
        "name,municipality_code\n"
        "Invented municipality,9\n"
        f"{arabic},9\n"
        "Different invented spelling,9\n"
    )
    (review / "zone_crosswalk.csv").write_text(
        "zone_code,bnd_hdx,bnd_zone_2020,bnd_district_2020,census_district_pop,"
        "census_zone_sector,census_zone_occ,census_zone_hh,census_zone_lab,status\n"
        "42,42,42,42,42,42,42,42,42,matched\n"
    )
    (review / "district_layer_aliases.csv").write_text(
        "zone_code,layer_name,hdx_name\n"
    )
    (review / "greater_doha_municipalities.csv").write_text(
        "name\nDifferent invented spelling\n"
    )
    (review / "zones_without_districts.csv").write_text("zone_code,reason\n")
    for filename in ("showcase_gazetteer.yaml", "flagship_candidates.yaml"):
        (review / filename).write_text("[]")
    names = (
        "bnd_hdx",
        "bnd_zone_2020",
        "bnd_district_2020",
        "census_district_pop",
        "census_zone_sector",
        "census_zone_occ",
        "census_zone_hh",
        "census_zone_lab",
    )
    by_id = {item.source_id: item for item in load_registry()}
    entries = tuple(by_id[name] for name in names)
    payloads = {name: invented_layer(name) for name in names if name != "bnd_hdx"}
    payloads["census_zone_sector"]["features"][0]["attributes"][
        "Total_Economic_active___15"
    ] = 16
    payloads["census_zone_hh"]["features"][0]["attributes"].update(
        Qatari=5, Non_Qatari=12
    )
    cache = tmp_path / "cache"
    for source in entries:
        body = (
            invented_archive()
            if source.source_id == "bnd_hdx"
            else json_module.dumps(payloads[source.source_id]).encode()
        )
        digest = sha256_hex(body)
        receipt = sidecar_for(
            source,
            digest=digest,
            nbytes=len(body),
            fetch_url=source.url,
            fetch_host=source.fetch_host,
            retrieved_utc="2026-11-14T00:00:00Z",
            publisher=source.publisher,
            source_modified="",
            row_count=None,
            terms_sha256="",
        )
        commit_pair(cache / source.key, digest, source.extension, body, receipt)
    row = _radiance_row()
    store(cache, row, night_file(tmp_path / "SYN.h5").read_bytes())
    seen: list[dict[int, object]] = []

    def spy(cache_path, rows, cells):
        seen.append(cells)
        return real_grids(cache_path, rows, cells)

    monkeypatch.setattr(live, "build_grids", spy)
    result = build_frame(cache, (*entries, row), review)
    assert len(seen) == 1
    assert sorted(seen[0]) == sorted(
        item["cell"] for item in result.tables["grid_cell"]
    )
    assert result.tables["pub_night_lights"] == []
    assert sorted(result.tables["fact_lineage"], key=lambda item: item["table"]) == [
        {
            "table": "pub_night_lights",
            "method": "C36",
            "method_version": "MTH-109",
            "source_key": row.key,
            "publisher": "SYN-publisher",
            "dataset": row.url,
            "licence_id": "NASA-guidance",
            "licence_url": "",
            "retrieved_utc": "2026-11-14T00:00:00Z",
            "source_sha256": result.tables["source_registry"][0]["source_sha256"],
            "release": "VNP46A3.002",
            "period": "2024-01",
            "period_first": "2024-01",
            "period_last": "2024-01",
            "provenance": "Public",
            "evidence_status": "Observed",
            "caveat_keys": ["night_lights_not_activity"],
            "doi": PRODUCT_DOI,
            "acknowledgement": NASA_ACK,
        }
    ]
    assert [item["source_key"] for item in result.tables["source_registry"]] == [
        row.key
    ]
    assert result.sources[row.key]["method"] == "C36"
    assert any(line.startswith("grids: ") for line in result.report)
    assert Path(cache / "grids" / "manifest.json").is_file()
    import shutil

    from custodian.tests.fixtures.grids.invented import population_file

    grid_rows = tuple(
        item
        for item in load_registry()
        if item.source_id
        in {"ntl_blackmarble", "worldpop_qat_agesex", "weather_openmeteo"}
    )
    shutil.rmtree(cache / row.key)
    empty = build_frame(cache, (*entries, *grid_rows), review)
    assert empty.tables["municipality"]
    assert empty.tables["zone"]
    assert empty.tables["pub_pop_agesex_grid"] == []
    assert empty.tables["pub_night_lights"] == []
    assert any(line.endswith("NO_CACHE") for line in empty.report)
    real_pop = next(
        item for item in grid_rows if item.key == "worldpop_qat_agesex/2025/f/25"
    )
    store(
        cache,
        real_pop,
        population_file(tmp_path / "qat_f_25_2025_SYN.tif").read_bytes(),
        publisher=real_pop.publisher,
    )
    cached = build_frame(cache, (*entries, *grid_rows), review)
    assert cached.tables["municipality"]
    assert cached.tables["pub_pop_agesex_grid"] == []
    assert any(
        line == "grids: worldpop_qat_agesex units or DOI unconfirmed"
        for line in cached.report
    )


def test_night_archive_path_follows_the_facts_pattern():
    """The archive path is the facts-file collection, built by hand."""
    hand = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5200/VNP46A3/2024/"
    assert ARCHIVE.format(year="2024") == hand
    row = next(
        item for item in load_registry() if item.key == "ntl_blackmarble/2024-01"
    )
    assert row.url == hand


def test_night_listing_request_carries_no_authorization_header(monkeypatch):
    """A directory listing on the archive host carries no credential header."""
    token = "SYN-invented-token"
    payload = (
        "HTTP/1.1 200 OK\r\nContent-Length: 5\r\nConnection: close\r\n\r\nSYN-l"
    ).encode("ascii")
    sent: list[bytes] = []

    class _Socket:
        def sendall(self, data: bytes) -> None:
            sent.append(data)

        def makefile(self, mode: str = "rb", *_args: object, **_kwargs: object):
            return io.BytesIO(payload)

        def close(self) -> None:
            return None

    def connect(connection: http.client.HTTPSConnection) -> None:
        connection.sock = _Socket()

    monkeypatch.setattr(http.client.HTTPSConnection, "connect", connect)
    open_https(YEAR_URL, token)
    request = b"".join(sent)
    assert b"Authorization" not in request
    assert token.encode("ascii") not in request


def test_night_sign_in_hop_names_a_missing_or_refused_credential(monkeypatch):
    """A hop to the publisher sign-in host fails under its own name."""
    token = "SYN-invented-token"
    location = (
        "https://urs.earthdata.nasa.gov/oauth/authorize?Signature=invented-signature"
    )
    payload = (
        "HTTP/1.1 302 Found\r\n"
        f"Location: {location}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
    ).encode("ascii")

    class _Socket:
        def sendall(self, data: bytes) -> None:
            return None

        def makefile(self, mode: str = "rb", *_args: object, **_kwargs: object):
            return io.BytesIO(payload)

        def close(self) -> None:
            return None

    def connect(connection: http.client.HTTPSConnection) -> None:
        connection.sock = _Socket()

    monkeypatch.setattr(http.client.HTTPSConnection, "connect", connect)
    with pytest.raises(
        TransportFault, match="credential_missing_or_not_accepted"
    ) as caught:
        open_https(FILE_URL, token)
    text = f"{caught.value}"
    assert "urs.earthdata.nasa.gov" in text
    assert "Signature" not in text
    assert "invented-signature" not in text
    assert token not in text


def test_night_refused_hop_names_host_and_path_only(monkeypatch):
    """A refused hop drops the query, which is where a storage host signs."""
    token = "SYN-invented-token"
    location = "https://evil.example/store/SYN.h5?Signature=invented-signature"
    payload = (
        "HTTP/1.1 302 Found\r\n"
        f"Location: {location}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
    ).encode("ascii")

    class _Socket:
        def sendall(self, data: bytes) -> None:
            return None

        def makefile(self, mode: str = "rb", *_args: object, **_kwargs: object):
            return io.BytesIO(payload)

        def close(self) -> None:
            return None

    def connect(connection: http.client.HTTPSConnection) -> None:
        connection.sock = _Socket()

    monkeypatch.setattr(http.client.HTTPSConnection, "connect", connect)
    with pytest.raises(TransportFault, match="blocked_host") as caught:
        open_https(FILE_URL, token)
    text = f"{caught.value}"
    assert "evil.example" in text
    assert "/store/SYN.h5" in text
    assert "Signature" not in text
    assert "invented-signature" not in text
    assert token not in text


def test_night_echoed_request_error_holds_no_header(monkeypatch):
    """A transport that echoes its request into an error leaves the header out."""
    token = "SYN-invented-token"

    class _Socket:
        def sendall(self, data: bytes) -> None:
            raise OSError(data.decode("ascii", "replace"))

        def makefile(self, mode: str = "rb", *_args: object, **_kwargs: object):
            return io.BytesIO(b"")

        def close(self) -> None:
            return None

    def connect(connection: http.client.HTTPSConnection) -> None:
        connection.sock = _Socket()

    monkeypatch.setattr(http.client.HTTPSConnection, "connect", connect)
    with pytest.raises(TransportFault) as caught:
        open_https(FILE_URL, token)
    text = f"{caught.value}"
    cause = caught.value.__cause__
    if cause is not None:
        text = f"{text} {cause}"
    context = caught.value.__context__
    if context is not None and not caught.value.__suppress_context__:
        text = f"{text} {context}"
    assert "Authorization" not in text
    assert token not in text


def test_night_plain_oserror_is_unreachable_and_keeps_the_query_out(monkeypatch):
    """A plain OSError is unreachable, and the query never reaches the fault."""
    token = "SYN-invented-token"
    query = "?Signature=invented-signature&token=SYN-invented-query-token"

    class _Opener:
        def open(self, request, timeout=None):
            raise OSError("SYN-invented socket failure")

    monkeypatch.setattr(
        "eii_custodian.publicdata.fetch.transport.urllib.request.build_opener",
        lambda *handlers: _Opener(),
    )
    with pytest.raises(TransportFault) as caught:
        open_https(FILE_URL + query, token)
    fault = caught.value
    assert fault.kind == "unreachable"
    assert fault.url == FILE_URL
    text = f"{fault}"
    cause = fault.__cause__
    if cause is not None:
        text = f"{text} {cause}"
    context = fault.__context__
    if context is not None and not fault.__suppress_context__:
        text = f"{text} {context}"
    assert "Signature" not in text
    assert "invented-signature" not in text
    assert "SYN-invented-query-token" not in text
    assert token not in text
    assert "Authorization" not in text


def test_night_lineage_and_source_cite_doi_and_acknowledgement(tmp_path):
    """The night-lights lineage and source rows carry the product DOI and NASA."""
    row = _radiance_row()
    body = night_file(tmp_path / "SYN.h5").read_bytes()
    store(tmp_path, row, body)
    result = build_grids(tmp_path, (row,), {1: box(0, 0, 1, 1)})
    lineage = result.tables["fact_lineage"][0]
    assert lineage["table"] == "pub_night_lights"
    assert lineage["doi"] == PRODUCT_DOI
    assert lineage["acknowledgement"] == NASA_ACK
    assert result.sources[row.key]["doi"] == PRODUCT_DOI
    assert result.sources[row.key]["acknowledgement"] == NASA_ACK


def test_night_record_without_doi_or_acknowledgement_fails(tmp_path):
    """A cached night-lights record without the DOI or the acknowledgement fails."""
    row = replace(_radiance_row(), doi="", acknowledgement="")
    body = night_file(tmp_path / "SYN.h5").read_bytes()
    store(tmp_path, row, body)
    with pytest.raises(GridError, match="DOI or acknowledgement"):
        build_grids(tmp_path, (row,), {1: box(0, 0, 1, 1)})


def test_night_refuses_a_wrong_array_type(tmp_path):
    """Radiance, quality, latitude and longitude must be the published types."""
    import h5py
    import numpy as np

    from eii_custodian.publicdata.grids.night_lights import FIELD, GROUP

    def written(name, radiance, quality, lat, lon):
        path = tmp_path / name
        with h5py.File(path, "w") as source:
            write_night_root(source)
            fields = source.create_group(GROUP)
            fields.create_dataset("lat", data=np.array(lat, dtype=lat.dtype))
            fields.create_dataset("lon", data=np.array(lon, dtype=lon.dtype))
            data = fields.create_dataset(FIELD, data=radiance)
            write_scale_offset(data, offset=0.0)
            fields.create_dataset(FIELD + "_Quality", data=quality)
        return path

    radiance = np.array([[1]], dtype="float32")
    quality = np.array([[0]], dtype="uint8")
    lat = np.array([0.5], dtype="float64")
    lon = np.array([0.1], dtype="float64")
    wrong = (
        (
            "ntl_blackmarble: radiance type",
            written("r.h5", radiance.astype("float64"), quality, lat, lon),
        ),
        (
            "ntl_blackmarble: quality type",
            written("q.h5", radiance, quality.astype("int16"), lat, lon),
        ),
        (
            "ntl_blackmarble: coordinate type",
            written("c.h5", radiance, quality, lat.astype("float32"), lon),
        ),
    )
    for reason, path in wrong:
        with pytest.raises(GridError, match=rf"^{reason}$"):
            read_night_lights(tmp_path, path, "2024-01")


def _requirement(text: str, anchor: str) -> str:
    found = [line for line in text.splitlines() if line.startswith(f"| {anchor} |")]
    assert len(found) == 1
    return found[0]


def test_pack_names_the_hosts_this_fetch_contacts():
    """PUB-03, ARC-13 and OPS-65 name the hosts this task's fetch contacts."""
    root = __import__(
        "custodian.tests.repository_root", fromlist=["repository_root"]
    ).repository_root(__import__("pathlib").Path(__file__))
    pack = (root / "docs" / "04_PUBLIC_DATA_PACK.md").read_text(encoding="utf-8")
    architecture = (root / "docs" / "02_ARCHITECTURE.md").read_text(encoding="utf-8")
    operations = (root / "docs" / "13_DEPLOYMENT_AND_OPERATIONS.md").read_text(
        encoding="utf-8"
    )
    rows = {
        "PUB-03": _requirement(pack, "PUB-03"),
        "ARC-13": _requirement(architecture, "ARC-13"),
        "OPS-65": _requirement(operations, "OPS-65"),
    }
    for host in (
        "ladsweb.modaps.eosdis.nasa.gov",
        "archive-api.open-meteo.com",
    ):
        assert all(host in row for row in rows.values())
    assert "S2-T14" in rows["PUB-03"]
    assert "download host ladsweb.modaps.eosdis.nasa.gov" in pack
    assert "host data.worldpop.org" in pack
    assert "host archive-api.open-meteo.com" in pack
    assert "download host to be recorded at the first fetch" not in pack
    assert "host and year to be recorded at the first fetch" not in pack
    assert "host, location and variables to be recorded at the first fetch" not in pack


def _invented_window_file(path, lat, lon, values, flags):
    import h5py
    import numpy as np

    from eii_custodian.publicdata.grids.night_lights import FIELD, GROUP

    with h5py.File(path, "w") as source:
        write_night_root(source)
        fields = source.create_group(GROUP)
        fields.create_dataset("lat", data=np.asarray(lat, dtype="float64"))
        fields.create_dataset("lon", data=np.asarray(lon, dtype="float64"))
        data = fields.create_dataset(
            FIELD, data=values, dtype="float32", compression="gzip"
        )
        write_scale_offset(data, offset=0.0)
        fields.create_dataset(
            FIELD + "_Quality", data=flags, dtype="uint8", compression="gzip"
        )
    return path


def test_night_window_equivalence(tmp_path):
    import numpy as np
    from shapely.geometry import Polygon

    # Integer centres; outside-box pixels and hole/gap pixels must not count.
    values = np.full((12, 12), 10, dtype="float32")
    flags = np.zeros((12, 12), dtype="uint8")
    for y, x, flag in (
        (2, 2, 1),
        (2, 3, 2),
        (2, 4, 255),
        (5, 5, 1),
        (5, 6, 2),
        (6, 5, 255),
    ):
        flags[y, x] = flag
    values[2, 4] = values[6, 6] = -999.9
    values[3, 3] = 30  # Shared edge belongs to key 1, not key 9.
    values[2, 7] = 90  # In triangular cell's bounds, but outside its geometry.
    cells = {
        9: box(2, 2, 3, 4),
        1: box(3, 2, 4, 4),
        3: Polygon([(6, 2), (8, 4), (6, 4)]),
        4: box(2, 6, 3, 7),
        5: box(7, 6, 8, 7),
        6: box(4.1, 7.1, 4.2, 7.2),  # No centre.
    }
    path = _invented_window_file(
        tmp_path / "SYN-window.h5", range(12), range(12), values, flags
    )
    pixels = read_night_lights(tmp_path, path, "2024-01", (2, 2, 8, 7.2))
    assert len(pixels) == 42  # 7 columns (2..8), 6 rows (2..7), inclusive.
    assert pixels[0].key == "2:2"
    result = aggregate(pixels, cells, "2024-01")
    assert result.rows == [
        {
            "cell": 1,
            "period": "2024-01",
            "radiance": Decimal("15.0000"),
            "source_id": "ntl_blackmarble",
        },
        {
            "cell": 3,
            "period": "2024-01",
            "radiance": Decimal("10.0000"),
            "source_id": "ntl_blackmarble",
        },
        {
            "cell": 4,
            "period": "2024-01",
            "radiance": Decimal("10.0000"),
            "source_id": "ntl_blackmarble",
        },
        {
            "cell": 5,
            "period": "2024-01",
            "radiance": Decimal("10.0000"),
            "source_id": "ntl_blackmarble",
        },
        {
            "cell": 9,
            "period": "2024-01",
            "radiance": Decimal("10.0000"),
            "source_id": "ntl_blackmarble",
        },
    ]
    assert result.missing == {6: "NO_DATA"}
    assert result.excluded == {
        "poor": 1,
        "history": 1,
        "quality_fill": 1,
        "radiance_fill": 1,
    }


def test_night_real_shape_window(tmp_path, monkeypatch):
    """Read a product-shaped tile whose latitude descends from the north edge."""
    import numpy as np

    from eii_custodian.publicdata.grids import night_lights

    # Invented ten-degree tile, 15 arc-second spacing, descending latitudes.
    centres = (np.arange(2400) + 0.5) / 240
    path = _invented_window_file(
        tmp_path / "SYN-real-shape.h5",
        centres[::-1],
        centres,
        np.full((2400, 2400), 12, dtype="float32"),
        np.zeros((2400, 2400), dtype="uint8"),
    )
    # 40 x 50 = 2000 cells, box [2, 4] x [2, 3.5].
    cells = {
        y * 40 + x: box(2 + x / 20, 2 + y * 0.03, 2 + (x + 1) / 20, 2 + (y + 1) * 0.03)
        for y in range(50)
        for x in range(40)
    }
    made = 0
    original = night_lights.Pixel

    def counted(*args):
        nonlocal made
        made += 1
        assert made <= 172800, "Pixel count exceeds frame window"
        return original(*args)

    monkeypatch.setattr(night_lights, "Pixel", counted)
    row = _radiance_row()
    store(tmp_path, row, path.read_bytes())
    result = build_grids(tmp_path, (row,), cells)
    # 2 degrees * 240 = 480 columns; 1.5 * 240 = 360 rows.
    # 480 * 360 = 172800 centres, versus 5760000 in the entire tile.
    assert made == 172800
    assert len(result.tables["pub_night_lights"]) == 2000
    assert result.tables["pub_night_lights"][0]["radiance"] == Decimal("12.0000")
    assert result.coverage == {
        row.key + ":quality:poor": "0",
        row.key + ":quality:history": "0",
        row.key + ":quality:quality_fill": "0",
        row.key + ":quality:radiance_fill": "0",
    }


def test_night_empty_frame_reads_no_pixels(tmp_path, monkeypatch):
    from eii_custodian.publicdata.grids import night_lights

    row = _radiance_row()
    store(tmp_path, row, night_file(tmp_path / "SYN-empty.h5").read_bytes())
    monkeypatch.setattr(
        night_lights, "Pixel", lambda *args: pytest.fail("empty frame made a Pixel")
    )
    result = build_grids(tmp_path, (row,), {})
    assert result.tables["pub_night_lights"] == []
    assert result.coverage == {
        row.key + ":quality:poor": "0",
        row.key + ":quality:history": "0",
        row.key + ":quality:quality_fill": "0",
        row.key + ":quality:radiance_fill": "0",
    }
