"""Kills of the activity graph that a count, a label, a path or a refusal changes.

Expected texts are hand-written literals. Expected orders are the node-id order.
"""

from __future__ import annotations

import locale
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.review.activity import (
    ActivityRow,
    IsicClass,
    Spine,
    SpineRow,
)
from eii_custodian.publicdata.review.graph import (
    AllowlistRow,
    GraphError,
    GraphRefused,
    build_graph,
    parse_place_categories,
    read_allowlist,
)

_HEADER = "isic_class,category,reviewed_by_role,reviewed_on"
_NAME = "اسم مخترع"


def _refuses(call: object, message: str, kind: type[GraphError] = GraphError) -> None:
    """The call raises exactly this type and this full text."""
    assert callable(call)
    with pytest.raises(kind) as caught:
        call()
    found = caught.value
    assert str(found) == message
    assert found.detail == message


@contextmanager
def _c_locale() -> Iterator[None]:
    """Run the body with the C locale, then restore the previous one."""
    previous = locale.setlocale(locale.LC_ALL)
    locale.setlocale(locale.LC_ALL, "C")
    try:
        yield
    finally:
        locale.setlocale(locale.LC_ALL, previous)


def _activity(
    code: str, *, active: int = 2, sources: tuple[str, ...] = ()
) -> ActivityRow:
    """One invented activity row."""
    return ActivityRow(code, _NAME, active, 0, sources)


def _spine(activity: ActivityRow) -> Spine:
    """A one-row spine that is not a mapped edge."""
    row = SpineRow(
        activity.code,
        len(activity.code),
        activity.name_ar,
        "",
        "out_of_scope",
        "outside_scope",
        "",
        "",
    )
    return Spine(rows=(row,), coverage=(), queue=())


def _allowlist(folder: Path, body: str) -> Path:
    """Write an allow-list file and return its path."""
    path = folder / "allowlist.csv"
    path.write_bytes(body.encode("utf-8"))
    return path


def test_graph_error_keeps_the_detail_it_was_given() -> None:
    """A refusal exposes the same text on the exception and on its detail."""
    error = GraphError("invented detail")
    assert error.detail == "invented detail"
    assert str(error) == "invented detail"


def test_allowlist_refuses_a_header_that_is_not_the_fixed_one(tmp_path: Path) -> None:
    """The allow-list header is the four fixed columns, in that order."""
    path = _allowlist(tmp_path, "a,b,c,d\n")
    _refuses(
        lambda: read_allowlist(path),
        "allow-list header is not the fixed header",
    )


def test_allowlist_refuses_a_repeated_class_and_category(tmp_path: Path) -> None:
    """The same class and category on two rows is a duplicate pair."""
    body = _HEADER + "\n5610,cafe,reader,2026-11-01\n5610,cafe,reader,2026-11-02\n"
    path = _allowlist(tmp_path, body)
    _refuses(lambda: read_allowlist(path), "duplicate allow-list pair")


def test_allowlist_reads_utf8_when_the_locale_is_c(tmp_path: Path) -> None:
    """A non-ASCII category is read as UTF-8 even under the C locale."""
    body = _HEADER + "\n5610,مقهى,reader,2026-11-01\n"
    with _c_locale():
        path = _allowlist(tmp_path, body)
        rows = read_allowlist(path)
    assert rows[0].category == "مقهى"
    assert rows[0].isic_class == "5610"


def test_allowlist_keeps_a_quoted_carriage_return(tmp_path: Path) -> None:
    """A quoted field keeps the carriage return the file stored."""
    body = _HEADER + '\n5610,"line\r\nbreak",reader,2026-11-01\n'
    path = _allowlist(tmp_path, body)
    rows = read_allowlist(path)
    assert rows[0].category == "line\r\nbreak"
    assert rows[0].reviewed_by_role == "reader"


def test_place_row_without_a_category_names_that_refusal() -> None:
    """A place row with neither nested nor flat category is refused."""
    _refuses(
        lambda: parse_place_categories(({"place": "invented"},)),
        "place row has no primary category",
    )


def test_place_category_xxxx_is_a_category() -> None:
    """The marker text is a category when a row actually carries it."""
    found = parse_place_categories(({"category": "XXXX"},))
    assert found == ("XXXX",)


def test_nested_primary_category_is_kept() -> None:
    """The nested primary is the category, and the rows come back sorted."""
    found = parse_place_categories(
        (
            {"categories": {"primary": "zoo"}},
            {"categories": {"primary": "cafe"}},
        )
    )
    assert found == ("cafe", "zoo")


def test_blank_place_category_is_refused() -> None:
    """A category of spaces is an empty category."""
    _refuses(
        lambda: parse_place_categories(({"category": "   "},)),
        "place row has no primary category",
    )


def test_spine_and_activities_must_name_the_same_codes() -> None:
    """A spine code with no activity row is refused by name."""
    activity = _activity("5610001")
    other = _activity("5610002")
    _refuses(
        lambda: build_graph(_spine(activity), (other,), (), (), (), load_registry()),
        "spine and activities name different codes",
    )


def test_labels_stay_blank_and_each_lineage_edge_names_its_source() -> None:
    """Activity English labels and source Arabic labels stay empty."""
    activity = _activity("5610001", active=2, sources=("lic_active", "lic_cancelled"))
    graph = build_graph(_spine(activity), (activity,), (), (), (), load_registry())
    node = next(item for item in graph.nodes if item.node_type == "activity")
    assert node.label_en == ""
    assert node.source_id == "lic_active"
    unmappable = next(item for item in graph.nodes if item.code == "UNMAPPABLE")
    assert unmappable.label_ar == ""
    assert unmappable.label_en == "UNMAPPABLE"
    for source in graph.nodes:
        if source.node_type == "source":
            assert source.label_ar == ""
    lineage = {
        edge.to_node_id: edge.source_id
        for edge in graph.edges
        if edge.edge_type == "sourced_from" and edge.from_node_id == "activity:5610001"
    }
    assert lineage["source:lic_active"] == "lic_active"
    assert lineage["source:lic_cancelled"] == "lic_cancelled"


def test_one_active_count_uses_the_active_feed() -> None:
    """An activity with no feed id and one active count is sourced from the active feed."""
    activity = _activity("5610001", active=1)
    graph = build_graph(_spine(activity), (activity,), (), (), (), load_registry())
    node = next(item for item in graph.nodes if item.node_type == "activity")
    assert node.source_id == "lic_active"


def test_unknown_activity_source_names_the_code() -> None:
    """A feed id outside the two licence feeds is refused with the code."""
    activity = _activity("5610001", sources=("not_a_feed",))
    _refuses(
        lambda: build_graph(_spine(activity), (activity,), (), (), (), load_registry()),
        "unknown activity source: 5610001",
    )


def test_duplicate_activity_source_names_the_code() -> None:
    """The same feed id twice on one activity is refused with the code."""
    activity = _activity("5610001", sources=("lic_active", "lic_active"))
    _refuses(
        lambda: build_graph(_spine(activity), (activity,), (), (), (), load_registry()),
        "duplicate activity source: 5610001",
    )


def test_allowlist_class_missing_from_the_titles_is_named() -> None:
    """An allow-list class that the class list does not hold is refused."""
    activity = _activity("5610001")
    link = AllowlistRow("4100", "cafe", "reader", "2026-11-01")
    classes = (IsicClass("5610", "Restaurants", ""),)
    _refuses(
        lambda: build_graph(
            _spine(activity),
            (activity,),
            classes,
            (link,),
            ("cafe",),
            load_registry(),
        ),
        "allow-list class is not in cls_isic4",
    )


def test_allowlist_category_missing_from_places_is_named() -> None:
    """An allow-list category absent from the place list is refused."""
    activity = _activity("5610001")
    link = AllowlistRow("5610", "cafe", "reader", "2026-11-01")
    classes = (IsicClass("5610", "Restaurants", ""),)
    _refuses(
        lambda: build_graph(
            _spine(activity),
            (activity,),
            classes,
            (link,),
            (),
            load_registry(),
        ),
        "allow-list category is not in the places cache",
    )


def test_blank_allowlist_role_is_refused_even_with_a_date() -> None:
    """A blank reviewer role refuses the row even when the date is present."""
    activity = _activity("5610001")
    link = AllowlistRow("5610", "cafe", "", "2026-11-01")
    classes = (IsicClass("5610", "Restaurants", ""),)
    _refuses(
        lambda: build_graph(
            _spine(activity),
            (activity,),
            classes,
            (link,),
            ("cafe",),
            load_registry(),
        ),
        "allow-list row without sign-off",
    )


def test_allowlist_blank_date_with_a_role_is_unsigned() -> None:
    """A blank date is a missing sign-off even when the role is present."""
    activity = _activity("5610001")
    link = AllowlistRow("5610", "cafe", "reader", "")
    classes = (IsicClass("5610", "Restaurants", ""),)
    _refuses(
        lambda: build_graph(
            _spine(activity),
            (activity,),
            classes,
            (link,),
            ("cafe",),
            load_registry(),
        ),
        "allow-list row without sign-off",
    )


def test_allowlist_role_xxxx_is_a_signed_role() -> None:
    """The marker text is a role when the row actually carries it."""
    activity = _activity("5610001")
    link = AllowlistRow("5610", "cafe", "XXXX", "2026-11-01")
    classes = (IsicClass("5610", "Restaurants", ""),)
    graph = build_graph(
        _spine(activity),
        (activity,),
        classes,
        (link, link),
        ("cafe",),
        load_registry(),
    )
    listed = [edge for edge in graph.edges if edge.edge_type == "listed_as"]
    assert len(listed) == 1
    assert listed[0].to_node_id == "place_category:cafe"


def test_allowlist_date_that_is_not_a_day_names_the_malformed_date() -> None:
    """A calendar-invalid ISO date is refused as a malformed date."""
    activity = _activity("5610001")
    link = AllowlistRow("5610", "cafe", "reader", "2026-02-31")
    classes = (IsicClass("5610", "Restaurants", ""),)
    _refuses(
        lambda: build_graph(
            _spine(activity),
            (activity,),
            classes,
            (link,),
            ("cafe",),
            load_registry(),
        ),
        "allow-list row with a malformed date",
    )


def test_place_source_missing_from_the_registry_names_the_source() -> None:
    """A place node whose source was removed from the registry is refused."""
    activity = _activity("5610001")
    link = AllowlistRow("5610", "cafe", "reader", "2026-11-01")
    classes = (IsicClass("5610", "Restaurants", ""),)
    registry = tuple(
        entry for entry in load_registry() if entry.source_id != "places_ovt"
    )
    _refuses(
        lambda: build_graph(
            _spine(activity),
            (activity,),
            classes,
            (link,),
            ("cafe",),
            registry,
        ),
        "source is not in the registry: places_ovt",
    )


def test_unknown_graph_mode_is_named() -> None:
    """A mode other than fixture or release is refused by name."""
    activity = _activity("5610001")
    _refuses(
        lambda: build_graph(
            _spine(activity),
            (activity,),
            (),
            (),
            (),
            load_registry(),
            mode="preview",
        ),
        "unknown graph mode",
    )


def test_release_without_cls_isic4_names_the_missing_source() -> None:
    """Release mode names a registry that has no cls_isic4 row."""
    activity = _activity("5610001")
    registry = tuple(
        entry for entry in load_registry() if entry.source_id != "cls_isic4"
    )
    _refuses(
        lambda: build_graph(
            _spine(activity),
            (activity,),
            (),
            (),
            (),
            registry,
            mode="release",
        ),
        "cls_isic4 is not in the registry",
    )


def test_release_of_the_real_registry_names_the_unreleased_title() -> None:
    """Release mode names the unreleased cls_isic4 title."""
    activity = _activity("5610001")
    _refuses(
        lambda: build_graph(
            _spine(activity),
            (activity,),
            (),
            (),
            (),
            load_registry(),
            mode="release",
        ),
        "cls_isic4 title is not released",
        GraphRefused,
    )
