"""S3-P06: producer-built map assets through the embedded serving seam."""

from __future__ import annotations

import importlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, cast

import pytest
from public_release_fixture import _cards_sources, _cards_tables, _scalars
from routing_release_fixture import TILES, invented_extract
from test_live_public_release_load import _RecordingPostgres

from eii_custodian.release.artefacts import RECORD
from eii_custodian.release.public_only import write_public_only
from eii_product.store.loader import _parquet_rows, run_load
from eii_product.store.release_check import check_release, manifest_rows
from operations.development import serve_embedded

BASEMAP = "artefacts/tiles/basemap.pmtiles"
FONT = "artefacts/fonts/Noto Sans Medium/0-255.pbf"


class _Response(Protocol):
    status_code: int
    content: bytes

    def json(self) -> Any: ...


class _Client(Protocol):
    def get(self, path: str) -> _Response: ...


def _client(app: Any) -> _Client:
    module = importlib.import_module("product.tests.public_http_support")
    factory = cast(Callable[[Any], _Client], module.Client)
    return factory(app)


def _source(root: Path, relative: str, body: bytes) -> Path:
    path = root / "INVENTED-source" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


def _release(root: Path, *, basemap: bool = True, fonts: bool = True) -> Path:
    cache = root / "INVENTED-cache"
    cache.mkdir()
    _, place = _writer()
    basemap_source = (
        _source(root, "qatar-invented.pmtiles", b"INVENTED-pmtiles")
        if basemap
        else root / "absent-basemap.pmtiles"
    )
    font_source = root / "INVENTED-source/fonts"
    if fonts:
        _source(root, "fonts/Noto Sans Medium/0-255.pbf", b"INVENTED-glyph")
    else:
        font_source = root / "absent-fonts"
    expected: dict[str, str] = {}
    if not basemap:
        expected["basemap"] = "basemap_missing"
    if not fonts:
        expected["fonts"] = "fonts_missing"
    assert place(cache, basemap_source, font_source) == expected
    entries = cast(
        list[dict[str, str]],
        json.loads((cache / RECORD).read_bytes())["artefacts"]
        if cache.exists()
        else [],
    )
    entries.append(invented_extract(cache / TILES))
    release = root / "INVENTED-release"
    identity = write_public_only(
        release,
        _scalars(),
        _cards_sources(),
        _cards_tables(),
        artefacts=entries,
    )
    if entries:
        shutil.copytree(cache / "artefacts", release / "artefacts")
    checked = check_release(release)
    tables = cast(list[dict[str, str]], checked.document["tables"])
    rows = {
        entry["name"]: _parquet_rows(
            release / entry["file"], checked.schemas[entry["name"]]
        )
        for entry in tables
    }
    rows["release_manifest"] = manifest_rows(checked.document)
    connection = _RecordingPostgres(rows, names=tuple(rows), columns=checked.schemas)
    assert (
        run_load(
            release,
            host="invented.invalid",
            port=1,
            database="INVENTED",
            connect=lambda **kw: connection,
        )
        == 0
    )
    target = root / "development/releases" / identity
    target.parent.mkdir(parents=True)
    shutil.copytree(release, target)
    web = root / "web/dist/assets"
    web.mkdir(parents=True)
    (web / "interface.woff2").write_bytes(b"INVENTED-interface-font")
    return target


def _serve(root: Path, release: Path, inspect: Callable[[_Client], None]) -> None:
    serve_embedded(
        root,
        {
            "EII_ENVIRONMENT": "development",
            "EII_RELEASE_DIR": str(release),
            "EII_STATE_DIR": str(root / "development/state"),
        },
        server=lambda app, **options: inspect(_client(app)),
    )


def test_embedded_serves_producer_built_map_assets(tmp_path: Path) -> None:
    release = _release(tmp_path)

    def inspect(client: _Client) -> None:
        summary = client.get("/api/release")
        assert summary.status_code == 200
        assert summary.json()["basemap_url"] == "/tiles/basemap.pmtiles"
        glyph = client.get("/fonts/Noto%20Sans%20Medium/0-255.pbf")
        assert glyph.status_code == 200
        assert glyph.content == b"INVENTED-glyph"
        health = client.get("/health")
        assert health.status_code == 200
        assert (health.json()["tiles"], health.json()["fonts"]) == ("ok", "ok")

    _serve(tmp_path, release, inspect)


def _writer() -> tuple[
    Callable[[Path], tuple[Path, Path]],
    Callable[[Path, Path, Path], dict[str, str]],
]:
    try:
        from eii_custodian.release.map_assets import (
            configured_sources,
            place_map_assets,
        )
    except ImportError:
        pytest.fail("map asset writer is missing")
    return configured_sources, place_map_assets


def test_writer_places_configured_basemap_and_every_glyph_range(tmp_path: Path) -> None:
    _, place = _writer()
    cache = tmp_path / "cache"
    cache.mkdir()
    basemap = _source(tmp_path, "input/qatar.pmtiles", b"INVENTED-pmtiles")
    fonts = tmp_path / "INVENTED-source/font-input"
    _source(tmp_path, "font-input/Noto Sans Medium/0-255.pbf", b"INVENTED-one")
    _source(tmp_path, "font-input/Noto Sans Medium/256-511.pbf", b"INVENTED-two")
    _source(tmp_path, "font-input/Noto Sans Arabic/0-255.pbf", b"INVENTED-arabic")

    assert place(cache, basemap, fonts) == {}
    assert (cache / BASEMAP).read_bytes() == b"INVENTED-pmtiles"
    assert (cache / "artefacts/fonts/Noto Sans Medium/256-511.pbf").read_bytes() == (
        b"INVENTED-two"
    )
    assert (cache / "artefacts/fonts/Noto Sans Arabic/0-255.pbf").read_bytes() == (
        b"INVENTED-arabic"
    )


def test_writer_missing_basemap_has_its_own_coverage_and_places_fonts(
    tmp_path: Path,
) -> None:
    _, place = _writer()
    cache = tmp_path / "cache"
    cache.mkdir()
    fonts = tmp_path / "INVENTED-source/font-input"
    _source(tmp_path, "font-input/Noto Sans Medium/0-255.pbf", b"INVENTED-glyph")

    assert place(cache, tmp_path / "absent.pmtiles", fonts) == {
        "basemap": "basemap_missing"
    }
    assert not (cache / BASEMAP).exists()
    assert (cache / FONT).read_bytes() == b"INVENTED-glyph"


def test_writer_missing_fonts_has_its_own_coverage_and_places_basemap(
    tmp_path: Path,
) -> None:
    _, place = _writer()
    cache = tmp_path / "cache"
    cache.mkdir()
    basemap = _source(tmp_path, "input/qatar.pmtiles", b"INVENTED-pmtiles")

    assert place(cache, basemap, tmp_path / "absent-fonts") == {
        "fonts": "fonts_missing"
    }
    assert (cache / BASEMAP).read_bytes() == b"INVENTED-pmtiles"
    assert not (cache / "artefacts/fonts").exists()


def test_writer_empty_font_directory_records_fonts_missing(tmp_path: Path) -> None:
    _, place = _writer()
    cache = tmp_path / "cache"
    cache.mkdir()
    basemap = _source(tmp_path, "input/qatar.pmtiles", b"INVENTED-pmtiles")
    fonts = tmp_path / "empty-fonts"
    fonts.mkdir()

    assert place(cache, basemap, fonts) == {"fonts": "fonts_missing"}
    assert (cache / BASEMAP).read_bytes() == b"INVENTED-pmtiles"
    assert not (cache / "artefacts/fonts").exists()


def test_writer_refuses_a_font_range_of_the_wrong_type(tmp_path: Path) -> None:
    _, place = _writer()
    cache = tmp_path / "cache"
    cache.mkdir()
    basemap = _source(tmp_path, "input/qatar.pmtiles", b"INVENTED-pmtiles")
    (tmp_path / "font-input/Noto Sans Medium/0-255.pbf").mkdir(parents=True)

    with pytest.raises(ValueError, match=r"\Aartefact_not_regular\Z"):
        place(cache, basemap, tmp_path / "font-input")


def test_writer_refuses_a_symlinked_font_stack(tmp_path: Path) -> None:
    _, place = _writer()
    cache = tmp_path / "cache"
    cache.mkdir()
    basemap = _source(tmp_path, "input/qatar.pmtiles", b"INVENTED-pmtiles")
    outside = tmp_path / "outside/Noto Sans Medium"
    outside.mkdir(parents=True)
    (outside / "0-255.pbf").write_bytes(b"INVENTED-outside")
    (tmp_path / "font-input").mkdir()
    (tmp_path / "font-input/Noto Sans Medium").symlink_to(
        outside, target_is_directory=True
    )

    with pytest.raises(ValueError, match=r"\Aartefact_not_regular\Z"):
        place(cache, basemap, tmp_path / "font-input")
    assert not (cache / FONT).exists()


def test_configured_sources_refuse_an_ambiguous_basemap(tmp_path: Path) -> None:
    configured, _ = _writer()
    _source(tmp_path, "data/basemap/qatar-2026-01-01.pmtiles", b"INVENTED-one")
    _source(tmp_path, "data/basemap/qatar-2026-01-02.pmtiles", b"INVENTED-two")

    with pytest.raises(ValueError, match=r"\Abasemap_source_ambiguous\Z"):
        configured(tmp_path / "INVENTED-source")


@pytest.mark.parametrize(
    ("basemap", "fonts", "expected_url", "expected_health"),
    [
        (False, True, None, ("missing", "ok")),
        (True, False, "/tiles/basemap.pmtiles", ("ok", "missing")),
    ],
)
def test_embedded_missing_map_assets_start_and_health_reports_each_asset(
    tmp_path: Path,
    basemap: bool,
    fonts: bool,
    expected_url: str | None,
    expected_health: tuple[str, str],
) -> None:
    release = _release(tmp_path, basemap=basemap, fonts=fonts)

    def inspect(client: _Client) -> None:
        summary = client.get("/api/release")
        assert summary.status_code == 200
        assert summary.json()["basemap_url"] == expected_url
        glyph = client.get("/fonts/Noto%20Sans%20Medium/0-255.pbf")
        assert glyph.status_code == (200 if fonts else 404)
        health = client.get("/health")
        assert health.status_code == 503
        assert (health.json()["tiles"], health.json()["fonts"]) == expected_health

    _serve(tmp_path, release, inspect)


def test_duplicate_basemap_entries_refuse_basemap_missing(tmp_path: Path) -> None:
    from eii_product.api.map_assets import map_asset_paths
    from eii_product.config import ConfigError
    from eii_product.store.release_check import CheckedRelease

    checked = CheckedRelease(
        tmp_path,
        {
            "artefacts": [
                {"path": BASEMAP, "sha256": "ab" * 32},
                {"path": BASEMAP, "sha256": "ab" * 32},
                {"path": FONT, "sha256": "cd" * 32},
            ]
        },
        {},
    )
    with pytest.raises(ConfigError, match=r"\Abasemap_missing\Z"):
        map_asset_paths(checked)


def test_unlisted_font_is_refused_as_startup_inventory_mismatch(tmp_path: Path) -> None:
    from eii_product.store.startup import StartupRefusal

    release = _release(tmp_path)
    (release / "artefacts/fonts/Noto Sans Medium/256-511.pbf").write_bytes(
        b"INVENTED-unlisted"
    )
    with pytest.raises(StartupRefusal, match=r"\Astartup_inventory_mismatch\Z"):
        _serve(tmp_path, release, lambda client: None)


def test_listed_font_of_the_wrong_type_is_an_artefact_mismatch(tmp_path: Path) -> None:
    from eii_product.store.startup import StartupRefusal

    release = _release(tmp_path)
    font = release / FONT
    font.unlink()
    font.mkdir()
    with pytest.raises(StartupRefusal, match=r"\Astartup_artefact_mismatch\Z"):
        _serve(tmp_path, release, lambda client: None)


def test_unrelated_manifest_entries_never_change_map_asset_selection(
    tmp_path: Path,
) -> None:
    from hypothesis import given
    from hypothesis import strategies as st

    from eii_product.store.release_check import CheckedRelease

    @given(extra=st.text().filter(lambda value: value not in {BASEMAP, FONT}))
    def check(extra: str) -> None:
        try:
            from eii_product.api.map_assets import map_asset_paths
        except ImportError:
            pytest.fail("manifest map asset selection is missing")
        checked = CheckedRelease(
            tmp_path,
            {
                "artefacts": [
                    {"path": BASEMAP, "sha256": "ab" * 32},
                    {"path": FONT, "sha256": "cd" * 32},
                    {"path": extra, "sha256": "ef" * 32},
                ]
            },
            {},
        )
        selected = map_asset_paths(checked)
        assert selected.tile_dir == tmp_path / "artefacts/tiles"
        assert selected.font_dir == tmp_path / "artefacts/fonts"
        assert selected.basemap_name == "basemap.pmtiles"

    check()


@pytest.mark.parametrize("kind", ["file", "symlink"])
def test_writer_refuses_a_font_root_of_the_wrong_type(
    tmp_path: Path, kind: str
) -> None:
    _, place = _writer()
    cache = tmp_path / "cache"
    cache.mkdir()
    basemap = _source(tmp_path, "input/qatar.pmtiles", b"INVENTED-pmtiles")
    target = tmp_path / "font-target"
    target.write_bytes(b"INVENTED-not-a-directory")
    fonts = tmp_path / "fonts"
    if kind == "file":
        fonts.write_bytes(b"INVENTED-not-a-directory")
    else:
        fonts.symlink_to(target)

    with pytest.raises(ValueError, match=r"\Aartefact_not_regular\Z"):
        place(cache, basemap, fonts)


def test_health_reports_a_listed_font_of_the_wrong_type_as_invalid(
    tmp_path: Path,
) -> None:
    from eii_product.api.health import local_assets

    release = _release(tmp_path)
    checked = check_release(release)
    font = release / FONT
    font.unlink()
    font.mkdir()

    assert local_assets(checked, tmp_path / "web/dist") == ("ok", "invalid", "ok")


@pytest.mark.parametrize(
    ("basemap", "fonts", "expected"),
    [(False, True, ("missing", "ok", "ok")), (True, False, ("ok", "missing", "ok"))],
)
def test_health_reports_each_missing_manifest_asset(
    tmp_path: Path, basemap: bool, fonts: bool, expected: tuple[str, str, str]
) -> None:
    from eii_product.api.health import local_assets

    checked = check_release(_release(tmp_path, basemap=basemap, fonts=fonts))
    assert local_assets(checked, tmp_path / "web/dist") == expected


def test_health_reports_missing_interface_font_with_map_assets_valid(
    tmp_path: Path,
) -> None:
    from eii_product.api.health import local_assets

    release = _release(tmp_path)
    (tmp_path / "web/dist/assets/interface.woff2").unlink()
    assert local_assets(check_release(release), tmp_path / "web/dist") == (
        "ok",
        "missing",
        "ok",
    )
