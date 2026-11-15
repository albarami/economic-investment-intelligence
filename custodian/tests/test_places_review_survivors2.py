"""Second mutation pass for committed and cached place-review loaders."""

from __future__ import annotations

import locale
from datetime import date
from pathlib import Path

from eii_custodian.publicdata.places.review import (
    Verification,
    accept_verification,
    load_attribution,
    load_categories,
    load_flagship_candidates,
    load_showcase_areas,
    load_showcase_gazetteer,
    load_verified_places,
)

_BUILD_DATE = date(2026, 11, 14)
_VERIFIED_HEADER = (
    "place_id,check_date,reviewer_role,verification_link,status,source_id\n"
)
_GAZETTEER_ROW = (
    "- place_key: SYN-K-CACHE\n"
    "  kind: place\n"
    "  name_en: SYN Cache Place\n"
    "  name_ar: 'مكان تجريبي'\n"
    "  aliases: ''\n"
    "  source_id: syn-source\n"
    "  record_key: SYN-P-CACHE\n"
    "  arabic_review: reviewed\n"
)


def test_verified_loader_utf8_does_not_depend_on_locale(tmp_path: Path) -> None:
    path = tmp_path / "verified.csv"
    path.write_text(
        _VERIFIED_HEADER
        + "SYN-P-AR,2026-01-01,مراجع تجريبي,https://syn.example/check,verified_open,tenant_directory\n",
        encoding="utf-8",
    )
    previous = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, "C")
        origin, rows = load_verified_places(
            path, None, frozenset({"SYN-P-AR"}), _BUILD_DATE
        )
    finally:
        locale.setlocale(locale.LC_ALL, previous)
    assert origin == "committed"
    assert rows == (
        Verification(
            "SYN-P-AR",
            "2026-01-01",
            "مراجع تجريبي",
            "https://syn.example/check",
            "verified_open",
            "tenant_directory",
        ),
    )


def test_verified_loader_preserves_csv_crlf_inside_a_field(tmp_path: Path) -> None:
    path = tmp_path / "verified.csv"
    path.write_bytes(
        _VERIFIED_HEADER.encode()
        + b'SYN-P-CRLF,2026-01-01,"reviewer\r\nrole",https://syn.example/check,verified_open,tenant_directory\r\n'
    )
    _origin, rows = load_verified_places(
        path, None, frozenset({"SYN-P-CRLF"}), _BUILD_DATE
    )
    assert rows[0].reviewer_role == "reviewer\r\nrole"


def test_every_auxiliary_loader_prefers_an_existing_cache(tmp_path: Path) -> None:
    committed = tmp_path / "committed"
    cache = tmp_path / "cache"
    committed.mkdir()
    cache.mkdir()

    (committed / "attribution.csv").write_text(
        "dataset_token,licence\n", encoding="utf-8"
    )
    (cache / "attribution.csv").write_text(
        "dataset_token,licence\nsyn-cache,SYN-LICENCE\n", encoding="utf-8"
    )
    assert load_attribution(
        committed / "attribution.csv", cache / "attribution.csv"
    ) == ("cache", (("syn-cache", "SYN-LICENCE"),))

    (committed / "categories.csv").write_text(
        "basic_category,category_class\n", encoding="utf-8"
    )
    (cache / "categories.csv").write_text(
        "basic_category,category_class\nsyn-cache,other\n", encoding="utf-8"
    )
    assert load_categories(committed / "categories.csv", cache / "categories.csv") == (
        "cache",
        (("syn-cache", "other"),),
    )

    area = (
        "- place_key: SYN-K-CACHE\n"
        "  mode: walk\n"
        "  cutoff_minutes: 10\n"
        "  source_id: syn-source\n"
        "  record_key: SYN-P-CACHE\n"
    )
    (committed / "areas.yaml").write_text("[]\n", encoding="utf-8")
    (cache / "areas.yaml").write_text(area, encoding="utf-8")
    area_origin, areas = load_showcase_areas(
        committed / "areas.yaml", cache / "areas.yaml"
    )
    assert area_origin == "cache"
    assert len(areas) == 1
    assert areas[0]["place_key"] == "SYN-K-CACHE"

    (committed / "gazetteer.yaml").write_text("[]\n", encoding="utf-8")
    (cache / "gazetteer.yaml").write_text(_GAZETTEER_ROW, encoding="utf-8")
    gazetteer_origin, gazetteer = load_showcase_gazetteer(
        committed / "gazetteer.yaml", cache / "gazetteer.yaml"
    )
    assert gazetteer_origin == "cache"
    assert len(gazetteer) == 1
    assert gazetteer[0]["record_key"] == "SYN-P-CACHE"

    (committed / "candidates.yaml").write_text("[]\n", encoding="utf-8")
    (cache / "candidates.yaml").write_text(_GAZETTEER_ROW, encoding="utf-8")
    candidate_origin, candidates = load_flagship_candidates(
        committed / "candidates.yaml", cache / "candidates.yaml"
    )
    assert candidate_origin == "cache"
    assert len(candidates) == 1
    assert candidates[0]["name_ar"] == "مكان تجريبي"


def test_accept_verification_returns_every_normalised_field() -> None:
    row = Verification(
        " SYN-P-COMPLETE ",
        " 2026-01-02 ",
        " reviewer ",
        " https://syn.example/check ",
        " verified_open ",
        " tenant_directory ",
    )
    assert accept_verification(
        row, frozenset({"SYN-P-COMPLETE"}), _BUILD_DATE
    ) == Verification(
        "SYN-P-COMPLETE",
        "2026-01-02",
        "reviewer",
        "https://syn.example/check",
        "verified_open",
        "tenant_directory",
    )


def test_csv_blank_rows_stay_filtered(tmp_path: Path) -> None:
    path = tmp_path / "attribution.csv"
    path.write_text(
        "dataset_token,licence\n,\nsyn-valid,SYN-LICENCE\n", encoding="utf-8"
    )
    assert load_attribution(path, None) == (
        "committed",
        (("syn-valid", "SYN-LICENCE"),),
    )


def test_csv_utf8_does_not_depend_on_locale(tmp_path: Path) -> None:
    path = tmp_path / "attribution.csv"
    path.write_text(
        "dataset_token,licence\nsyn-arabic,رخصة تجريبية\n", encoding="utf-8"
    )
    previous = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, "C")
        result = load_attribution(path, None)
    finally:
        locale.setlocale(locale.LC_ALL, previous)
    assert result == ("committed", (("syn-arabic", "رخصة تجريبية"),))


def test_csv_preserves_crlf_inside_a_field(tmp_path: Path) -> None:
    path = tmp_path / "attribution.csv"
    path.write_bytes(b'dataset_token,licence\r\nsyn-crlf,"SYN-LICENCE\r\nSECOND"\r\n')
    assert load_attribution(path, None) == (
        "committed",
        (("syn-crlf", "SYN-LICENCE\r\nSECOND"),),
    )


def test_yaml_utf8_does_not_depend_on_locale(tmp_path: Path) -> None:
    path = tmp_path / "gazetteer.yaml"
    path.write_text(_GAZETTEER_ROW, encoding="utf-8")
    previous = locale.setlocale(locale.LC_ALL)
    try:
        locale.setlocale(locale.LC_ALL, "C")
        origin, rows = load_showcase_gazetteer(path, None)
    finally:
        locale.setlocale(locale.LC_ALL, previous)
    assert origin == "committed"
    assert len(rows) == 1
    assert rows[0]["name_ar"] == "مكان تجريبي"
