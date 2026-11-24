"""Same-origin static serving and path/type refusal plants."""

from pathlib import Path

import pytest
from product.tests import map_assets
from product.tests.public_http_support import Client
from starlette.middleware.cors import CORSMiddleware

from eii_product.api.app import create_app


@pytest.fixture
def web(tmp_path):
    root = tmp_path / "web"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<main>INVENTED-bundle</main>")
    for suffix in ("js", "css", "woff2", "svg", "png", "json"):
        (root / "assets" / ("bundle." + suffix)).write_bytes(b"INVENTED-asset")
    for name in (".hidden.js", "bundle.txt", "bundle.js.map", "\\bundle.js"):
        (root / "assets" / name).write_bytes(b"INVENTED-disallowed")
    return root


def client(web):
    return Client(
        create_app(
            Path("product/tests/fixtures/tiles"),
            web_dir=web,
            fc_setting_reader=lambda: None,
        )
    )


def error(response):
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message_key", "error_id"}
    assert body["error"]["code"] == "NOT_FOUND"


def test_index_exact_types_nosniff_no_cors(web):
    with client(web) as http:
        assert http.get("/").text == "<main>INVENTED-bundle</main>"
        for suffix, kind in [
            ("js", "text/javascript"),
            ("css", "text/css"),
            ("woff2", "font/woff2"),
            ("svg", "image/svg+xml"),
            ("png", "image/png"),
            ("json", "application/json"),
        ]:
            response = http.get(
                "/assets/bundle." + suffix,
                headers={"Origin": "https://invented.invalid"},
            )
            assert response.status_code == 200
            assert response.content == b"INVENTED-asset"
            assert response.headers["content-type"].split(";")[0] == kind
            assert response.headers["x-content-type-options"] == "nosniff"
            assert "access-control-allow-origin" not in response.headers
        assert http.get("/api/nope").status_code == 404
        assert "INVENTED-bundle" not in http.get("/api/nope").text


@pytest.mark.parametrize(
    "name",
    [
        "..",
        "%2e%2e",
        "%2e%2e%2fbundle.js",
        "%5cbundle.js",
        "%2fbundle.js",
        ".hidden.js",
        "bundle.txt",
        "bundle.js.map",
        "missing.js",
        "bundle.js/extra",
        "bundle%00.js",
    ],
)
def test_invalid_asset_names(web, name):
    # Normalized dot/slash paths can miss the route entirely; never serve bytes.
    response = client(web).get("/assets/" + name)
    assert response.status_code == 404
    assert "INVENTED-" not in response.text


def test_missing_bundle_and_symlink_escape(web, tmp_path):
    outside = tmp_path / "outside.js"
    outside.write_text("INVENTED-outside")
    (web / "assets" / "escape.js").symlink_to(outside)
    error(client(web).get("/assets/escape.js"))
    error(client(None).get("/"))
    error(client(None).get("/assets/bundle.js"))
    (web / "index.html").unlink()
    error(client(web).get("/"))
    (web / "index.html").symlink_to(outside)
    error(client(web).get("/"))


def test_cors_plant_is_observable(web):
    app = create_app(
        Path("product/tests/fixtures/tiles"),
        web_dir=web,
        fc_setting_reader=lambda: None,
    )
    app.add_middleware(CORSMiddleware, allow_origins=["*"])
    response = Client(app).get(
        "/assets/bundle.js", headers={"Origin": "https://invented.invalid"}
    )
    assert response.headers["access-control-allow-origin"] == "*"


GLYPH_PATH = "/fonts/Noto%20Sans%20Medium/0-255.pbf"
GLYPH_BYTES = map_assets.glyph_pbf(map_assets.FONT_STACK, 0, 255)


@pytest.fixture
def fonts(tmp_path):
    root = tmp_path / "fonts"
    stack = root / map_assets.FONT_STACK
    stack.mkdir(parents=True)
    for start, end in map_assets.GLYPH_RANGES:
        name = f"{start}-{end}.pbf"
        (stack / name).write_bytes(
            map_assets.glyph_pbf(map_assets.FONT_STACK, start, end)
        )
    (stack / "0-255.woff2").write_bytes(b"INVENTED-wrong-type")
    (stack / "00-0255.pbf").write_bytes(b"INVENTED-padded-range")
    (root / "Other Stack").mkdir()
    (root / "Other Stack" / "0-255.pbf").write_bytes(b"INVENTED-other-stack")
    return root


def font_client(web, fonts):
    return Client(
        create_app(
            Path("product/tests/fixtures/tiles"),
            web_dir=web,
            font_dir=fonts,
            fc_setting_reader=lambda: None,
        )
    )


def test_font_range_files_serve_exact_bytes_nosniff_no_cors(web, fonts):
    response = font_client(web, fonts).get(
        GLYPH_PATH,
        headers={"Origin": "https://invented.invalid"},
    )
    assert response.status_code == 200
    assert response.content == GLYPH_BYTES
    assert response.headers["content-type"].split(";")[0] == "application/x-protobuf"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "access-control-allow-origin" not in response.headers
    assert "location" not in response.headers
    response = font_client(web, fonts).get(
        "/fonts/Noto%20Sans%20Medium/65024-65279.pbf"
    )
    assert response.status_code == 200
    assert response.content == map_assets.glyph_pbf(map_assets.FONT_STACK, 65024, 65279)


@pytest.mark.parametrize(
    "path",
    [
        "Noto%20Sans%20Medium/0-254.pbf",
        "Noto%20Sans%20Medium/1-256.pbf",
        "Noto%20Sans%20Medium/65536-65791.pbf",
        "Noto%20Sans%20Medium/0-255.txt",
        "Noto%20Sans%20Medium/0-255.woff2",
        "Noto%20Sans%20Medium/0-255.pbf/extra",
        "Noto%20Sans%20Medium",
        "0-255.pbf",
        "Other%20Stack/0-255.pbf",
        "%2e%2e/Noto%20Sans%20Medium/0-255.pbf",
        "Noto%20Sans%20Medium/..%2F0-255.pbf",
        "Noto%20Sans%20Medium/00-0255.pbf",
    ],
)
def test_invalid_font_paths_are_refused(web, fonts, path):
    response = font_client(web, fonts).get("/fonts/" + path)
    assert response.status_code == 404, path
    assert b"INVENTED" not in response.content
    assert b"Noto" not in response.content
    assert str(fonts).encode() not in response.content


def test_font_symlink_escape_and_missing_inventory_fail(web, fonts, tmp_path):
    outside = tmp_path / "outside.pbf"
    outside.write_bytes(b"INVENTED-outside-glyph")
    (fonts / map_assets.FONT_STACK / "999-1254.pbf").write_bytes(b"INVENTED-bad")
    (fonts / map_assets.FONT_STACK / "256-511.pbf").unlink(missing_ok=True)
    (fonts / map_assets.FONT_STACK / "256-511.pbf").symlink_to(outside)

    http = font_client(web, fonts)
    error(http.get("/fonts/Noto%20Sans%20Medium/256-511.pbf"))
    error(http.get("/fonts/Noto%20Sans%20Medium/999-1254.pbf"))
    error(http.get("/fonts/Noto%20Sans%20Medium/768-1023.pbf"))
    error(font_client(web, None).get(GLYPH_PATH))

    stack = fonts / map_assets.FONT_STACK
    escaped = tmp_path / "escaped-stack"
    escaped.mkdir()
    (escaped / "0-255.pbf").write_bytes(b"INVENTED-escaped-stack")
    stack.rename(fonts / "held")
    stack.symlink_to(escaped)
    error(http.get(GLYPH_PATH))


def test_missing_font_file_is_refused(web, fonts):
    (fonts / map_assets.FONT_STACK / "1536-1791.pbf").unlink()
    error(font_client(web, fonts).get("/fonts/Noto%20Sans%20Medium/1536-1791.pbf"))
