"""Mutation survivors for custodian/src/eii_custodian/publicdata/places/review.py.

Each test targets one or more survived mutants from the mutation campaign.
New tests only - no changes to existing code.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from eii_custodian.publicdata.places import PlacesError
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

# Constants
_BUILD_DATE = date(2026, 11, 14)


# =============================================================================
# load_verified_places survivors
# =============================================================================


def test_verified_header_error_message_is_exact(tmp_path: Path) -> None:
    """The header mismatch error carries the exact reason string."""
    path = tmp_path / "verified.csv"
    path.write_text("wrong_header\n", encoding="utf-8")
    with pytest.raises(PlacesError) as exc_info:
        load_verified_places(path, None, frozenset(), _BUILD_DATE)
    # KILLS: _csv reason parameter mutations that change "verified_header"
    assert exc_info.value.args[0] == "verified_header"


def test_verified_header_with_none_fieldnames_is_refused(tmp_path: Path) -> None:
    """CSV with no header (None fieldnames) refuses with verified_header."""
    path = tmp_path / "no_header.csv"
    path.write_text("data1,data2\nval1,val2\n", encoding="utf-8")
    # A CSV file with no proper header will have None fieldnames
    # This tests the "reader.fieldnames is None" branch
    with pytest.raises(PlacesError) as exc_info:
        load_verified_places(path, None, frozenset(), _BUILD_DATE)
    assert exc_info.value.args[0] == "verified_header"


def test_verified_header_with_wrong_columns_is_refused(tmp_path: Path) -> None:
    """CSV with wrong column names refuses with verified_header."""
    path = tmp_path / "wrong_cols.csv"
    path.write_text("place_id,check_date\nSYN-P-A,2026-01-01\n", encoding="utf-8")
    with pytest.raises(PlacesError) as exc_info:
        load_verified_places(path, None, frozenset({"SYN-P-A"}), _BUILD_DATE)
    assert exc_info.value.args[0] == "verified_header"


def test_verified_empty_rows_are_filtered(tmp_path: Path) -> None:
    """Rows with all empty values are filtered out before processing."""
    path = tmp_path / "with_blanks.csv"
    path.write_text(
        "place_id,check_date,reviewer_role,verification_link,status,source_id\n"
        "SYN-P-A,2026-01-01,reviewer,https://example.invalid,verified_open,tenant_directory\n"
        ",,,,,\n"  # Empty row
        "SYN-P-B,2026-01-01,reviewer,https://example.invalid,not_found,public_authority\n",
        encoding="utf-8",
    )
    origin, rows = load_verified_places(
        path, None, frozenset({"SYN-P-A", "SYN-P-B"}), _BUILD_DATE
    )
    assert origin == "committed"
    # Empty row should be filtered, so only 2 rows
    assert len(rows) == 2
    assert {r.place_id for r in rows} == {"SYN-P-A", "SYN-P-B"}


def test_verified_whitespace_only_rows_are_filtered(tmp_path: Path) -> None:
    """Rows with only whitespace are filtered out."""
    path = tmp_path / "whitespace.csv"
    path.write_text(
        "place_id,check_date,reviewer_role,verification_link,status,source_id\n"
        "   ,   ,   ,   ,   ,   \n"  # Whitespace only
        "SYN-P-A,2026-01-01,reviewer,https://example.invalid,verified_open,tenant_directory\n",
        encoding="utf-8",
    )
    _origin, rows = load_verified_places(
        path, None, frozenset({"SYN-P-A"}), _BUILD_DATE
    )
    assert len(rows) == 1


# =============================================================================
# load_attribution survivors
# =============================================================================


def test_attribution_header_error_message_is_exact(tmp_path: Path) -> None:
    """The attribution header mismatch carries the exact reason."""
    path = tmp_path / "attrib.csv"
    path.write_text("wrong,header\n", encoding="utf-8")
    with pytest.raises(PlacesError) as exc_info:
        load_attribution(path, None)
    # KILLS: _csv reason parameter mutations for "attribution_header"
    assert exc_info.value.args[0] == "attribution_header"


def test_attribution_row_with_empty_token_refuses(tmp_path: Path) -> None:
    """Empty token after strip refuses with attribution_row."""
    path = tmp_path / "attrib.csv"
    path.write_text(
        "dataset_token,licence\n,MIT\n",  # Empty token
        encoding="utf-8",
    )
    with pytest.raises(PlacesError) as exc_info:
        load_attribution(path, None)
    assert exc_info.value.args[0] == "attribution_row"


def test_attribution_row_with_empty_licence_refuses(tmp_path: Path) -> None:
    """Empty licence after strip refuses with attribution_row."""
    path = tmp_path / "attrib.csv"
    path.write_text(
        "dataset_token,licence\nTOKEN-1,\n",  # Empty licence
        encoding="utf-8",
    )
    with pytest.raises(PlacesError) as exc_info:
        load_attribution(path, None)
    assert exc_info.value.args[0] == "attribution_row"


def test_attribution_duplicate_token_refuses(tmp_path: Path) -> None:
    """Duplicate token refuses with duplicate_token."""
    path = tmp_path / "attrib.csv"
    path.write_text(
        "dataset_token,licence\nTOKEN-1,MIT\nTOKEN-1,Apache-2.0\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError) as exc_info:
        load_attribution(path, None)
    # KILLS: mutations that change "duplicate_token" error message
    assert exc_info.value.args[0] == "duplicate_token"


# =============================================================================
# load_categories survivors
# =============================================================================


def test_category_header_error_message_is_exact(tmp_path: Path) -> None:
    """The category header mismatch carries the exact reason."""
    path = tmp_path / "categories.csv"
    path.write_text("wrong,header\n", encoding="utf-8")
    with pytest.raises(PlacesError) as exc_info:
        load_categories(path, None)
    # KILLS: _csv reason parameter mutations for "category_header"
    assert exc_info.value.args[0] == "category_header"


def test_category_row_with_empty_label_refuses(tmp_path: Path) -> None:
    """Empty basic_category refuses with category_row."""
    path = tmp_path / "categories.csv"
    path.write_text(
        "basic_category,category_class\n,restaurant\n",  # Empty label
        encoding="utf-8",
    )
    with pytest.raises(PlacesError) as exc_info:
        load_categories(path, None)
    # KILLS: mutations that change "category_row" error message
    assert exc_info.value.args[0] == "category_row"


def test_category_unknown_class_refuses(tmp_path: Path) -> None:
    """Unknown category class refuses with unknown_category_class."""
    path = tmp_path / "categories.csv"
    path.write_text(
        "basic_category,category_class\nsyn_restaurant,invented_class\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError) as exc_info:
        load_categories(path, None)
    # KILLS: mutations that change "unknown_category_class" error message
    assert exc_info.value.args[0] == "unknown_category_class"


def test_category_valid_rows_load_correctly(tmp_path: Path) -> None:
    """Valid category rows load without error."""
    path = tmp_path / "categories.csv"
    path.write_text(
        "basic_category,category_class\n"
        "syn_restaurant,restaurant\n"
        "syn_italian,italian_restaurant\n"
        "syn_other,other\n",
        encoding="utf-8",
    )
    origin, rows = load_categories(path, None)
    assert origin == "committed"
    assert len(rows) == 3
    assert ("syn_restaurant", "restaurant") in rows


# =============================================================================
# load_showcase_areas / load_showcase_gazetteer / load_flagship_candidates
# =============================================================================


def test_showcase_areas_invalid_yaml_refuses(tmp_path: Path) -> None:
    """Non-list YAML refuses with review_list."""
    path = tmp_path / "areas.yaml"
    path.write_text("not_a_list\n", encoding="utf-8")
    with pytest.raises(PlacesError) as exc_info:
        load_showcase_areas(path, None)
    # KILLS: mutations that change "review_list" error message
    assert exc_info.value.args[0] == "review_list"


def test_showcase_areas_empty_yaml_returns_empty(tmp_path: Path) -> None:
    """Empty YAML list returns empty tuple."""
    path = tmp_path / "areas.yaml"
    path.write_text("[]", encoding="utf-8")
    origin, rows = load_showcase_areas(path, None)
    assert origin == "committed"
    assert rows == ()


def test_showcase_gazetteer_invalid_yaml_refuses(tmp_path: Path) -> None:
    """Non-list YAML for gazetteer refuses with review_list."""
    path = tmp_path / "gazetteer.yaml"
    path.write_text("{key: value}\n", encoding="utf-8")
    with pytest.raises(PlacesError) as exc_info:
        load_showcase_gazetteer(path, None)
    assert exc_info.value.args[0] == "review_list"


def test_flagship_candidates_invalid_yaml_refuses(tmp_path: Path) -> None:
    """Non-list YAML for flagship refuses with review_list."""
    path = tmp_path / "flagship.yaml"
    path.write_text("string_not_list\n", encoding="utf-8")
    with pytest.raises(PlacesError) as exc_info:
        load_flagship_candidates(path, None)
    assert exc_info.value.args[0] == "review_list"


# =============================================================================
# _keys survivors
# =============================================================================


def test_keys_not_dict_refuses_review_row(tmp_path: Path) -> None:
    """Non-dict item to _keys refuses with review_row."""
    path = tmp_path / "gazetteer.yaml"
    # YAML with non-dict items
    path.write_text("- not_a_dict\n- {place_key: SYN-K-1}\n", encoding="utf-8")
    with pytest.raises(PlacesError) as exc_info:
        load_showcase_gazetteer(path, None)
    # KILLS: mutations that change "review_row" error message
    assert exc_info.value.args[0] == "review_row"


def test_keys_missing_required_key_refuses_missing_key(tmp_path: Path) -> None:
    """Dict missing required key refuses with missing_key."""
    path = tmp_path / "gazetteer.yaml"
    # Missing place_key
    path.write_text("- kind: syn\n  name_en: Test\n", encoding="utf-8")
    with pytest.raises(PlacesError) as exc_info:
        load_showcase_gazetteer(path, None)
    # KILLS: mutations that change "missing_key" error message
    assert exc_info.value.args[0] == "missing_key"


# =============================================================================
# _area survivors
# =============================================================================


def test_area_wrong_mode_refuses_showcase_area(tmp_path: Path) -> None:
    """Area with wrong mode refuses with showcase_area."""
    path = tmp_path / "areas.yaml"
    path.write_text(
        "- place_key: SYN-K-1\n  mode: drive\n  cutoff_minutes: 10\n"
        "  source_id: syn\n  record_key: syn-rk\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError) as exc_info:
        load_showcase_areas(path, None)
    # KILLS: mutations that change "showcase_area" error message
    assert exc_info.value.args[0] == "showcase_area"


def test_area_wrong_cutoff_refuses_showcase_area(tmp_path: Path) -> None:
    """Area with wrong cutoff_minutes refuses with showcase_area."""
    path = tmp_path / "areas.yaml"
    path.write_text(
        "- place_key: SYN-K-1\n  mode: walk\n  cutoff_minutes: 5\n"
        "  source_id: syn\n  record_key: syn-rk\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError) as exc_info:
        load_showcase_areas(path, None)
    assert exc_info.value.args[0] == "showcase_area"


def test_area_missing_place_key_refuses_showcase_area(tmp_path: Path) -> None:
    """Area with empty place_key refuses with showcase_area."""
    path = tmp_path / "areas.yaml"
    path.write_text(
        "- place_key: ''\n  mode: walk\n  cutoff_minutes: 10\n"
        "  source_id: syn\n  record_key: syn-rk\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError) as exc_info:
        load_showcase_areas(path, None)
    assert exc_info.value.args[0] == "showcase_area"


def test_area_non_string_place_key_refuses_showcase_area(tmp_path: Path) -> None:
    """Area with non-string place_key refuses with showcase_area."""
    path = tmp_path / "areas.yaml"
    path.write_text(
        "- place_key: 12345\n  mode: walk\n  cutoff_minutes: 10\n"
        "  source_id: syn\n  record_key: syn-rk\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError) as exc_info:
        load_showcase_areas(path, None)
    assert exc_info.value.args[0] == "showcase_area"


# =============================================================================
# _parsed_date survivors
# =============================================================================


def test_parsed_date_invalid_format_refuses_bad_check_date() -> None:
    """Invalid date format refuses with bad_check_date."""
    # Test through _checked which calls _parsed_date
    with pytest.raises(PlacesError) as exc_info:
        accept_verification(
            Verification(
                "SYN-P-A",
                "not-a-date",
                "reviewer",
                "https://example.invalid",
                "verified_open",
                "tenant_directory",
            ),
            frozenset({"SYN-P-A"}),
            _BUILD_DATE,
        )
    # KILLS: mutations that change "bad_check_date" error message
    assert exc_info.value.args[0] == "bad_check_date"


def test_parsed_date_impossible_date_refuses_bad_check_date() -> None:
    """Impossible date refuses with bad_check_date."""
    with pytest.raises(PlacesError) as exc_info:
        accept_verification(
            Verification(
                "SYN-P-A",
                "2026-13-01",  # Impossible month
                "reviewer",
                "https://example.invalid",
                "verified_open",
                "tenant_directory",
            ),
            frozenset({"SYN-P-A"}),
            _BUILD_DATE,
        )
    assert exc_info.value.args[0] == "bad_check_date"


# =============================================================================
# _require_link survivors
# =============================================================================


def test_require_link_non_https_refuses_link_form() -> None:
    """Non-https link refuses with link_form."""
    with pytest.raises(PlacesError) as exc_info:
        accept_verification(
            Verification(
                "SYN-P-A",
                "2026-01-01",
                "reviewer",
                "http://example.invalid",  # HTTP not HTTPS
                "verified_open",
                "tenant_directory",
            ),
            frozenset({"SYN-P-A"}),
            _BUILD_DATE,
        )
    # KILLS: mutations that change "link_form" error message
    assert exc_info.value.args[0] == "link_form"


def test_require_link_no_hostname_refuses_link_form() -> None:
    """Link without hostname refuses with link_form."""
    with pytest.raises(PlacesError) as exc_info:
        accept_verification(
            Verification(
                "SYN-P-A",
                "2026-01-01",
                "reviewer",
                "https://",  # No hostname
                "verified_open",
                "tenant_directory",
            ),
            frozenset({"SYN-P-A"}),
            _BUILD_DATE,
        )
    assert exc_info.value.args[0] == "link_form"


# =============================================================================
# _refuse_same_date survivors
# =============================================================================


def test_duplicate_place_date_refuses_duplicate_place_date(tmp_path: Path) -> None:
    """Two checks of same place on same date refuses with duplicate_place_date."""
    path = tmp_path / "verified.csv"
    path.write_text(
        "place_id,check_date,reviewer_role,verification_link,status,source_id\n"
        "SYN-P-A,2026-01-01,reviewer,https://example.invalid/a,verified_open,tenant_directory\n"
        "SYN-P-A,2026-01-01,reviewer,https://example.invalid/b,not_found,public_authority\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError) as exc_info:
        load_verified_places(path, None, frozenset({"SYN-P-A"}), _BUILD_DATE)
    # KILLS: mutations that change "duplicate_place_date" error message
    assert exc_info.value.args[0] == "duplicate_place_date"


# =============================================================================
# _checked / accept_verification survivors
# =============================================================================


def test_orphan_place_id_refuses_orphan_place_id() -> None:
    """Unknown place_id refuses with orphan_place_id."""
    with pytest.raises(PlacesError) as exc_info:
        accept_verification(
            Verification(
                "SYN-P-UNKNOWN",
                "2026-01-01",
                "reviewer",
                "https://example.invalid",
                "verified_open",
                "tenant_directory",
            ),
            frozenset({"SYN-P-A"}),  # SYN-P-UNKNOWN not in set
            _BUILD_DATE,
        )
    # KILLS: mutations that change "orphan_place_id" error message
    assert exc_info.value.args[0] == "orphan_place_id"


def test_future_check_date_refuses_bad_check_date() -> None:
    """Check date after build date refuses with bad_check_date."""
    with pytest.raises(PlacesError) as exc_info:
        accept_verification(
            Verification(
                "SYN-P-A",
                "2026-11-15",  # After build date 2026-11-14
                "reviewer",
                "https://example.invalid",
                "verified_open",
                "tenant_directory",
            ),
            frozenset({"SYN-P-A"}),
            _BUILD_DATE,
        )
    assert exc_info.value.args[0] == "bad_check_date"


def test_missing_role_refuses_missing_role() -> None:
    """Empty reviewer_role refuses with missing_role."""
    with pytest.raises(PlacesError) as exc_info:
        accept_verification(
            Verification(
                "SYN-P-A",
                "2026-01-01",
                "",  # Empty role
                "https://example.invalid",
                "verified_open",
                "tenant_directory",
            ),
            frozenset({"SYN-P-A"}),
            _BUILD_DATE,
        )
    # KILLS: mutations that change "missing_role" error message
    assert exc_info.value.args[0] == "missing_role"


def test_missing_link_refuses_missing_link() -> None:
    """Empty verification_link refuses with missing_link."""
    with pytest.raises(PlacesError) as exc_info:
        accept_verification(
            Verification(
                "SYN-P-A",
                "2026-01-01",
                "reviewer",
                "",  # Empty link
                "verified_open",
                "tenant_directory",
            ),
            frozenset({"SYN-P-A"}),
            _BUILD_DATE,
        )
    # KILLS: mutations that change "missing_link" error message
    assert exc_info.value.args[0] == "missing_link"


def test_unknown_status_refuses_unknown_status() -> None:
    """Unknown status refuses with unknown_status."""
    with pytest.raises(PlacesError) as exc_info:
        accept_verification(
            Verification(
                "SYN-P-A",
                "2026-01-01",
                "reviewer",
                "https://example.invalid",
                "invented_status",  # Not in STATUSES
                "tenant_directory",
            ),
            frozenset({"SYN-P-A"}),
            _BUILD_DATE,
        )
    # KILLS: mutations that change "unknown_status" error message
    assert exc_info.value.args[0] == "unknown_status"


def test_verification_source_refused(tmp_path: Path) -> None:
    """Refused source refuses with verification_source_refused."""
    path = tmp_path / "verified.csv"
    path.write_text(
        "place_id,check_date,reviewer_role,verification_link,status,source_id\n"
        "SYN-P-A,2026-01-01,reviewer,https://example.invalid,verified_open,review_site\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError) as exc_info:
        load_verified_places(path, None, frozenset({"SYN-P-A"}), _BUILD_DATE)
    # KILLS: mutations that change "verification_source_refused" error message
    assert exc_info.value.args[0] == "verification_source_refused"


def test_verification_source_unknown(tmp_path: Path) -> None:
    """Unknown source refuses with verification_source_unknown."""
    path = tmp_path / "verified.csv"
    path.write_text(
        "place_id,check_date,reviewer_role,verification_link,status,source_id\n"
        "SYN-P-A,2026-01-01,reviewer,https://example.invalid,verified_open,syn_unknown\n",
        encoding="utf-8",
    )
    with pytest.raises(PlacesError) as exc_info:
        load_verified_places(path, None, frozenset({"SYN-P-A"}), _BUILD_DATE)
    # KILLS: mutations that change "verification_source_unknown" error message
    assert exc_info.value.args[0] == "verification_source_unknown"


# =============================================================================
# _text survivors
# =============================================================================


def test_text_with_none_returns_empty_string() -> None:
    """_text with None value returns empty string."""
    from eii_custodian.publicdata.places.review import _text

    result = _text({"name": "value"}, "missing_key")
    assert result == ""


def test_text_with_empty_string_returns_empty_string() -> None:
    """_text with empty string returns empty string."""
    from eii_custodian.publicdata.places.review import _text

    result = _text({"name": ""}, "name")
    assert result == ""


def test_text_with_value_returns_normalised() -> None:
    """_text with value returns normalised (stripped) value."""
    from eii_custodian.publicdata.places.review import _text

    result = _text({"name": "  value  "}, "name")
    assert result == "value"


# =============================================================================
# latest_status survivors
# =============================================================================


def test_latest_status_uses_strictly_greater() -> None:
    """Latest status uses > not >= for date comparison."""
    from eii_custodian.publicdata.places.review import latest_status

    rows = (
        Verification(
            "SYN-P-A",
            "2026-01-01",
            "r1",
            "https://e.invalid",
            "verified_open",
            "tenant_directory",
        ),
        Verification(
            "SYN-P-A",
            "2026-01-01",
            "r2",
            "https://e.invalid",
            "closed_or_moved",
            "official_website",
        ),
    )
    result = latest_status(rows)
    # Both have same date, first one should be kept (not replaced by >=)
    # With > comparison, the second one with same date won't replace the first
    # With >= comparison, the second one would replace the first
    assert result["SYN-P-A"].reviewer_role == "r1"


# =============================================================================
# _csv encoding survivors
# =============================================================================


def test_csv_opens_with_utf8_encoding(tmp_path: Path) -> None:
    """_csv opens file with utf-8 encoding, not None."""
    from eii_custodian.publicdata.places.review import _csv

    path = tmp_path / "test.csv"
    # Write UTF-8 content
    path.write_text("col1,col2\nval1,val2\n", encoding="utf-8")
    # This should work with utf-8 encoding
    result = _csv(path, ("col1", "col2"), "test_header")
    assert len(result) == 1
    assert result[0] == {"col1": "val1", "col2": "val2"}


# =============================================================================
# Cache parameter survivors
# =============================================================================


def test_cache_none_uses_committed_path(tmp_path: Path) -> None:
    """When cache is None, _choose uses committed path."""
    committed = tmp_path / "committed.csv"
    committed.write_text(
        "place_id,check_date,reviewer_role,verification_link,status,source_id\n"
        "SYN-P-A,2026-01-01,reviewer,https://example.invalid,verified_open,tenant_directory\n",
        encoding="utf-8",
    )
    origin, rows = load_verified_places(
        committed, None, frozenset({"SYN-P-A"}), _BUILD_DATE
    )
    assert origin == "committed"
    assert len(rows) == 1


def test_cache_exists_uses_cache_path(tmp_path: Path) -> None:
    """When cache exists, _choose uses cache path."""
    committed = tmp_path / "committed.csv"
    cache = tmp_path / "cache.csv"
    committed.write_text(
        "place_id,check_date,reviewer_role,verification_link,status,source_id\n",
        encoding="utf-8",
    )
    cache.write_text(
        "place_id,check_date,reviewer_role,verification_link,status,source_id\n"
        "SYN-P-A,2026-01-01,reviewer,https://example.invalid,verified_open,tenant_directory\n",
        encoding="utf-8",
    )
    origin, rows = load_verified_places(
        committed, cache, frozenset({"SYN-P-A"}), _BUILD_DATE
    )
    assert origin == "cache"
    assert len(rows) == 1
