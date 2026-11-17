"""Invented review records for S2-T16 rulings G2 to G4; no provider answers."""

from pathlib import Path

import pytest

from eii_custodian.publicdata.busyness.review import (
    ReviewError,
    load_crosswalk,
    load_requests,
    load_venues,
)

REQUESTS = (
    "forecast_credits: 2\nquery_credits: 1\n"
    'source_page: "https://docs.example/invented"\nread_on: "2026-11-16"\n'
)
VENUES = "place_id,category_group,reviewer_role,reviewed_on\n"
CROSSWALK = "place_id,venue_key,reviewer_role,reviewed_on,match\n"


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "review"
    path.write_text(text, encoding="utf-8")
    return path


def test_besttime_request_costs_are_reviewed_positive_integers(tmp_path: Path) -> None:
    assert load_requests(write(tmp_path, REQUESTS)) == (2, 1)


@pytest.mark.parametrize("field", ["forecast_credits", "query_credits"])
@pytest.mark.parametrize("value", ["", "0", "-1", "true", "1.5", '"2"'])
def test_besttime_invalid_cost_names_field(
    tmp_path: Path, field: str, value: str
) -> None:
    original = "2" if field == "forecast_credits" else "1"
    text = REQUESTS.replace(f"{field}: {original}", f"{field}: {value}")
    with pytest.raises(ReviewError, match=f"busy_besttime_requests.yaml {field}"):
        load_requests(write(tmp_path, text))


@pytest.mark.parametrize(
    "text",
    ["[]", "[", REQUESTS + "extra: false\n", REQUESTS.split("query_credits:")[0]],
)
def test_besttime_request_schema_closed(tmp_path: Path, text: str) -> None:
    with pytest.raises(ReviewError):
        load_requests(write(tmp_path, text))


@pytest.mark.parametrize(
    "value", ['""', '"2026-02-30"', '"2026-1-1"', "2026-11-16", "true"]
)
def test_besttime_request_date_is_iso_text(tmp_path: Path, value: str) -> None:
    with pytest.raises(ReviewError, match="read_on"):
        load_requests(write(tmp_path, REQUESTS.replace('"2026-11-16"', value)))


@pytest.mark.parametrize(
    "value",
    [
        '""',
        "false",
        '"http://docs.example/page"',
        '"https:///page"',
        '"https://docs.example/page?query=planted"',
        '"https://docs.example/page#fragment"',
        '"https://invented' + "@" + 'docs.example/page"',
    ],
)
def test_besttime_source_page_is_key_free(tmp_path: Path, value: str) -> None:
    with pytest.raises(ReviewError, match="source_page"):
        load_requests(
            write(tmp_path, REQUESTS.replace('"https://docs.example/invented"', value))
        )


def test_besttime_header_only_files_are_empty(tmp_path: Path) -> None:
    assert load_venues(write(tmp_path, VENUES)) == ()
    assert load_crosswalk(write(tmp_path, CROSSWALK)) == ()


def test_besttime_review_rows_preserved(tmp_path: Path) -> None:
    assert load_venues(
        write(tmp_path, VENUES + "SYN-place-a,cafe,data-reviewer,2026-11-16\n")
    ) == (
        {
            "place_id": "SYN-place-a",
            "category_group": "cafe",
            "reviewer_role": "data-reviewer",
            "reviewed_on": "2026-11-16",
        },
    )
    for match in ("matched", "no_match"):
        assert (
            load_crosswalk(
                write(
                    tmp_path,
                    CROSSWALK
                    + f"SYN-place-a,SYN-venue-a,data-reviewer,2026-11-16,{match}\n",
                )
            )[0]["match"]
            == match
        )


@pytest.mark.parametrize(
    "loader,header,row",
    [
        (load_venues, VENUES, "SYN-place-a,cafe,data-reviewer,2026-11-16"),
        (
            load_crosswalk,
            CROSSWALK,
            "SYN-place-a,SYN-venue-a,data-reviewer,2026-11-16,matched",
        ),
    ],
)
@pytest.mark.parametrize(
    "break_kind",
    [
        "extra-column",
        "missing-column",
        "extra-cell",
        "missing-cell",
        "blank",
        "duplicate",
        "date",
    ],
)
def test_besttime_csv_schema_guards(
    tmp_path: Path, loader, header: str, row: str, break_kind: str
) -> None:
    text = header + row + "\n"
    if break_kind == "extra-column":
        text = header.rstrip() + ",extra\n" + row + ",value\n"
    elif break_kind == "missing-column":
        text = header.split(",", 1)[1] + row.split(",", 1)[1] + "\n"
    elif break_kind == "extra-cell":
        text = header + row + ",extra\n"
    elif break_kind == "missing-cell":
        text = header + row.rsplit(",", 1)[0] + "\n"
    elif break_kind == "blank":
        text = text.replace("data-reviewer", " ")
    elif break_kind == "duplicate":
        text += row + "\n"
    elif break_kind == "date":
        text = text.replace("2026-11-16", "2026-02-30")
    with pytest.raises(ReviewError):
        loader(write(tmp_path, text))


def test_besttime_crosswalk_match_is_closed(tmp_path: Path) -> None:
    with pytest.raises(ReviewError, match="match"):
        load_crosswalk(
            write(
                tmp_path,
                CROSSWALK + "SYN-place-a,SYN-venue-a,data-reviewer,2026-11-16,maybe\n",
            )
        )


def test_besttime_committed_reviews_are_unfilled() -> None:
    root = Path(__file__).resolve().parents[1] / "publicdata/review"
    assert load_venues(root / "busy_besttime_venues.csv") == ()
    assert load_crosswalk(root / "venue_busyness_crosswalk.csv") == ()
    with pytest.raises(ReviewError, match="forecast_credits"):
        load_requests(root / "busy_besttime_requests.yaml")


def test_besttime_week_date_is_not_calendar_date(tmp_path: Path) -> None:
    with pytest.raises(ReviewError, match="read_on"):
        load_requests(write(tmp_path, REQUESTS.replace("2026-11-16", "2026-W47-1")))


def test_besttime_same_width_wrong_header_refused(tmp_path: Path) -> None:
    with pytest.raises(ReviewError, match="columns"):
        load_venues(
            write(
                tmp_path,
                VENUES.replace("category_group", "unknown")
                + "SYN-place-a,cafe,data-reviewer,2026-11-16\n",
            )
        )


def test_besttime_source_page_empty_username_with_password_refused(
    tmp_path: Path,
) -> None:
    page = '"https://:invented' + "@" + 'docs.example/page"'
    with pytest.raises(ReviewError, match="source_page"):
        load_requests(
            write(tmp_path, REQUESTS.replace('"https://docs.example/invented"', page))
        )


def test_besttime_null_root_and_numeric_source_page_refused(tmp_path: Path) -> None:
    with pytest.raises(ReviewError):
        load_requests(write(tmp_path, "null"))
    with pytest.raises(ReviewError, match="source_page"):
        load_requests(
            write(tmp_path, REQUESTS.replace('"https://docs.example/invented"', "3"))
        )
