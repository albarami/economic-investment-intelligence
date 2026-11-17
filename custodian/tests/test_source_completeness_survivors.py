"""In-process mutation plants; all records are invented and contain no source values."""

from dataclasses import replace

import pytest
from custodian.tests.test_source_completeness import entry, inputs, receipt

from eii_custodian.publicdata import completeness as c


def assert_message(error, expected):
    assert str(error.value) == expected


def failed(records):
    return [row for row in records if row["state"] == "failed"]


def test_section_boundaries_and_exact_missing_refusal():
    text = "## Invented\nfirst\n### Child\nsecond\n## Next\nexcluded"
    assert c.section(text, "## Invented") == "first\n### Child\nsecond"
    assert c.section("## Invented\n## Next\nexcluded", "## Invented") == ""
    assert c.section("## Invented\nfirst\nlast", "## Invented") == "first\nlast"
    with pytest.raises(ValueError) as error:
        c.section(text, "## Missing")
    assert_message(error, "pack_section_missing")


def pack_text(block):
    return "### 2.1 Invented\n" + block + "\n### 2.3 Invented\n### 2.4 Invented\n"


def test_pack_empty_blocks_short_rows_and_header_width():
    assert c.pack_sources(pack_text(""), {}).sources == {}
    assert c.pack_sources(pack_text("| `invented` | text |"), {}).sources == {
        "invented": ()
    }
    text = pack_text(
        "| ID | title | publisher | fetch | licence |\n"
        "| `short` | ignored |\n"
        "| `invented` | text | text | `not_a_family_slug` | text |"
    )
    assert c.pack_sources(text, {}).sources == {"invented": ()}
    for text in (
        "",
        "### 2.1 Invented\n",
        "### 2.1 Invented\n### 2.3 Invented\n",
        "XXXX\n### 2.3 Invented\n### 2.4 Invented\n",
    ):
        with pytest.raises(ValueError) as error:
            c.pack_sources(text, {})
        assert_message(error, "pack_section_missing")


def test_pack_four_cell_family_row_refuses_with_exact_text():
    with pytest.raises(ValueError) as error:
        c.pack_sources(pack_text("| `invented` | text |"), {"invented": 1})
    assert_message(error, "pack_family_row_truncated")


@pytest.mark.parametrize("header", ["| ID | title |", "| ID | title | fetch |"])
def test_pack_five_cell_family_row_keeps_exact_slugs(header):
    text = pack_text(header + "\n| `invented` | text | text | `slug-a`, `slug-b`")
    assert c.pack_sources(text, {"invented": 2}).sources == {
        "invented": ("slug-a", "slug-b")
    }


def test_catalogue_reads_multiple_lines_and_excludes_next_section():
    assert c.table_catalogue(
        "### 7.2 Table catalogue\n"
        "| `pub_invented_a` | text |\n| `pub_invented_b` | text |\n"
        "### 7.3 Next\n| `excluded` | text |"
    ) == {"pub_invented_a", "pub_invented_b"}


@pytest.mark.parametrize(
    "plant, expected",
    [
        (
            "pack",
            [
                ("invented", "source_completeness: missing pack source"),
                ("invented", "source_completeness: extra registry source"),
            ],
        ),
        (
            "registry",
            [
                ("invented", "source_completeness: missing registry source"),
                ("invented", "source_completeness: duplicate or missing row"),
                ("invented", "source_receipt_missing: receipt without registry row"),
                ("invented", "source_completeness: evidence without registry row"),
            ],
        ),
        (
            "receipt",
            [("invented", "source_receipt_missing: missing or invalid receipt")],
        ),
        ("output", [("invented", "source_completeness: output tables")]),
        ("table", [("invented", "source_table_uncatalogued: pub_invented")]),
        (
            "orphan_receipt",
            [("orphan", "source_receipt_missing: receipt without registry row")],
        ),
        (
            "orphan_output",
            [("orphan", "source_completeness: evidence without registry row")],
        ),
        (
            "orphan_absence",
            [("orphan", "source_completeness: evidence without registry row")],
        ),
        (
            "extra",
            [
                ("extra", "source_completeness: extra registry source"),
                ("extra", "source_receipt_missing: missing or invalid receipt"),
            ],
        ),
        (
            "duplicate_key",
            [
                ("invented", "source_completeness: duplicate or missing row"),
                ("invented", "source_completeness: duplicate key"),
                ("invented", "source_completeness: duplicate key"),
            ],
        ),
    ],
)
def test_exact_independent_refusals(plant, expected):
    args = inputs()
    if plant == "pack":
        args["pack"] = c.Pack({}, frozenset())
    elif plant == "registry":
        args["entries"] = []
    elif plant == "receipt":
        args["receipts"] = {}
    elif plant == "output":
        args["outputs"] = {}
    elif plant == "table":
        args["catalogue"] = set()
    elif plant == "orphan_receipt":
        args["receipts"]["orphan"] = receipt(entry("orphan"))
    elif plant == "orphan_output":
        args["outputs"]["orphan"] = ("pub_invented",)
    elif plant == "orphan_absence":
        args["absences"]["orphan"] = c.Absence("Invented absence", "invented_caveat")
    elif plant == "extra":
        args["entries"].append(entry("extra"))
    elif plant == "duplicate_key":
        args["entries"].append(entry())
    assert failed(c.check(**args)) == [
        {"id": key, "state": "failed", "reason": reason} for key, reason in expected
    ]


@pytest.mark.parametrize(
    "source", ["traffic_tomtom_flow", "traffic_tomtom_range", "tiles3d_google"]
)
@pytest.mark.parametrize("plant", ["receipt", "cache", "row", "row_absence"])
def test_exact_forbidden_refusals(source, plant):
    args = inputs()
    if plant == "receipt":
        args["receipts"]["invented"]["source_id"] = source
        expected = [
            {
                "id": "invented",
                "state": "failed",
                "reason": "source_completeness: forbidden receipt",
            },
            {
                "id": "invented",
                "state": "failed",
                "reason": "source_receipt_missing: missing or invalid receipt",
            },
        ]
    elif plant == "cache":
        args["cached_source_ids"] = (source,)
        expected = [
            {
                "id": source,
                "state": "failed",
                "reason": "source_completeness: forbidden cached file",
            }
        ]
    else:
        row = entry(source)
        args["entries"].append(row)
        args["receipts"][source] = receipt(row)
        args["outputs"][source] = ("pub_invented",)
        if plant == "row_absence":
            args["outputs"][source] = ()
            args["absences"][source] = c.Absence(
                "Invented unavailable", "invented_caveat"
            )
        expected = [
            {
                "id": source,
                "state": "failed",
                "reason": "source_completeness: forbidden receipt",
            },
            {
                "id": source,
                "state": "failed",
                "reason": "source_completeness: forbidden row",
            },
        ]
    records = c.check(**args)
    assert failed(records) == expected
    if plant in {"row", "row_absence"}:
        assert all(
            record["state"] == "failed" for record in records if record["id"] == source
        )


@pytest.mark.parametrize(
    "source", ["traffic_tomtom_flow", "traffic_tomtom_range", "tiles3d_google"]
)
def test_forbidden_rows_keep_duplicate_key_refusals(source):
    args = inputs()
    args["entries"].extend([entry(source), entry(source)])
    expected = [
        {"id": source, "state": "failed", "reason": reason}
        for reason in (
            "source_completeness: forbidden row",
            "source_completeness: duplicate key",
            "source_completeness: forbidden row",
            "source_completeness: duplicate key",
        )
    ]
    records = c.check(**args)
    assert failed(records) == expected
    assert [record for record in records if record["id"] == source] == expected


@pytest.mark.parametrize(
    "source", ["traffic_tomtom_flow", "traffic_tomtom_range", "tiles3d_google"]
)
def test_forbidden_row_keeps_uncatalogued_table_refusal(source):
    args = inputs()
    args["entries"].append(entry(source, release_tables=("pub_uncatalogued",)))
    expected = [
        {"id": source, "state": "failed", "reason": reason}
        for reason in (
            "source_completeness: forbidden row",
            "source_table_uncatalogued: pub_uncatalogued",
        )
    ]
    records = c.check(**args)
    assert failed(records) == expected
    assert [record for record in records if record["id"] == source] == expected


@pytest.mark.parametrize(
    "source", ["traffic_tomtom_flow", "traffic_tomtom_range", "tiles3d_google"]
)
def test_valid_row_after_forbidden_row_is_in_use(source):
    args = inputs()
    args["entries"].insert(0, entry(source))
    records = c.check(**args)
    refusal = {
        "id": source,
        "state": "failed",
        "reason": "source_completeness: forbidden row",
    }
    assert failed(records) == [refusal]
    assert [record for record in records if record["id"] == source] == [refusal]
    assert {"id": "invented", "state": "in use", "reason": ""} in records


@pytest.mark.parametrize(
    "pack_slugs, inventory_slugs, row_slugs, reasons",
    [
        (("a",), (), ("a",), []),
        (("a", "b"), (), ("a", "b"), []),
        (("a",), ("a",), ("a",), []),
        (
            ("a",),
            ("a", "b"),
            ("a",),
            ["source_completeness: pack slugs", "source_completeness: registry slugs"],
        ),
        (("a", "b"), ("a",), ("a",), ["source_completeness: pack slugs"]),
        (("a",), ("a", "a"), ("a", "a"), ["source_completeness: duplicate slug"]),
        (("a", "a"), ("a",), ("a",), ["source_completeness: duplicate slug"]),
        (("a",), ("a",), ("b",), ["source_completeness: registry slugs"]),
    ],
)
def test_slug_inventory_sides_and_pack_fallback(
    pack_slugs, inventory_slugs, row_slugs, reasons
):
    args = inputs()
    rows = [
        entry(slug=slug, key=f"invented/part-{i}") for i, slug in enumerate(row_slugs)
    ]
    args.update(
        entries=rows,
        pack=c.Pack({"invented": pack_slugs}, frozenset()),
        inventory={"invented": inventory_slugs},
        receipts={row.key: receipt(row) for row in rows},
        outputs={row.key: ("pub_invented",) for row in rows},
    )
    assert failed(c.check(**args)) == [
        {"id": "invented", "state": "failed", "reason": reason} for reason in reasons
    ]


def test_inventory_slugs_when_pack_source_is_absent():
    args = inputs()
    row = entry(slug="a")
    args.update(
        entries=[row], pack=c.Pack({}, frozenset()), inventory={"invented": ("a",)}
    )
    args["receipts"] = {row.key: receipt(row)}
    assert failed(c.check(**args)) == [
        {
            "id": "invented",
            "state": "failed",
            "reason": "source_completeness: missing pack source",
        },
        {
            "id": "invented",
            "state": "failed",
            "reason": "source_completeness: pack slugs",
        },
        {
            "id": "invented",
            "state": "failed",
            "reason": "source_completeness: extra registry source",
        },
    ]


@pytest.mark.parametrize("pack_count,row_count", [(76, 77), (77, 76)])
def test_family_counts_refuse_each_side_independently(pack_count, row_count):
    args = inputs()
    slugs = tuple(f"invented-{i}" for i in range(pack_count))
    rows = [
        entry(slug=f"invented-{i}", key=f"invented/part-{i}") for i in range(row_count)
    ]
    args.update(
        entries=rows,
        pack=c.Pack({"invented": slugs}, frozenset()),
        inventory={"invented": slugs},
        receipts={row.key: receipt(row) for row in rows},
        outputs={row.key: ("pub_invented",) for row in rows},
    )
    expected = [
        {
            "id": "invented",
            "state": "failed",
            "reason": "source_completeness: registry slugs",
        },
        {
            "id": "invented",
            "state": "failed",
            "reason": "source_completeness: family count",
        },
    ]
    if pack_count == 76:
        expected.append(
            {
                "id": "PUB-85",
                "state": "failed",
                "reason": "source_completeness: family total",
            }
        )
    assert failed(c.check(**args, family_counts={"invented": 77})) == expected


@pytest.mark.parametrize(
    "skip, absence, output, expected",
    [
        ("Invented unavailable", None, (), "source_absence_reason_missing"),
        ("", c.Absence(" ", "invented_caveat"), (), "source_absence_reason_missing"),
        (
            "",
            c.Absence("Invented unavailable", " "),
            (),
            "source_absence_reason_missing",
        ),
        (
            "Invented unavailable",
            c.Absence("Invented other reason", "invented_caveat"),
            (),
            "source_completeness: absence reason mismatch",
        ),
        (
            "Invented unavailable",
            c.Absence("Invented unavailable", "invented_caveat"),
            (),
            None,
        ),
        (
            "",
            c.Absence("Invented unavailable", "invented_caveat"),
            ("pub_invented",),
            "source_completeness: output for absent source",
        ),
    ],
)
def test_absence_exact_refusals_and_verbatim_reason(skip, absence, output, expected):
    args = inputs()
    args.update(
        entries=[entry(skip_reason=skip)], receipts={}, outputs={"invented": output}
    )
    args["absences"] = {} if absence is None else {"invented": absence}
    records = c.check(**args)
    assert failed(records) == (
        []
        if expected is None
        else [{"id": "invented", "state": "failed", "reason": expected}]
    )
    if expected is None:
        assert {
            "id": "invented",
            "state": "NO_DATA",
            "reason": "Invented unavailable",
            "caveat": "invented_caveat",
        } in records


def test_register_rows_are_exempt_from_pack_inventory():
    args = inputs()
    for source in ("biz_register", "fc_register"):
        row = entry(source)
        args["entries"].append(row)
        args["receipts"][source] = receipt(row)
        args["outputs"][source] = ("pub_invented",)
    assert c.check(**args) == [
        {"id": "invented", "state": "in use", "reason": ""},
        {"id": "biz_register", "state": "in use", "reason": ""},
        {"id": "fc_register", "state": "in use", "reason": ""},
    ]


@pytest.mark.parametrize("shape", ["direct", "dict", "list"])
def test_committed_policy_reports_exact_file_at_every_depth(shape):
    value = {"source_id": "invented", "value": "invented placeholder"}
    if shape == "dict":
        value = {"nested": value}
    elif shape == "list":
        value = {"nested": [value]}
    assert c.committed_derived_check({"invented.json": value}, [entry()]) == [
        {"id": "invented.json", "state": "failed", "reason": "committed_source_value"}
    ]
    assert (
        c.committed_derived_check(
            {"invented.json": value}, [replace(entry(), commit_allowed=True)]
        )
        == []
    )
