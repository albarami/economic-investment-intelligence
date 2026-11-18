"""Invented validation inputs for S2-T29 page-schema survivor groups."""

from decimal import Decimal

import pytest
from custodian.tests.test_s2_t29_live_shapes import (
    classified,
    declaration,
    embedded,
    tariff,
    tariffs,
    workbook,
)

from eii_custodian.publicdata.fetch.page_schema import (
    json_body,
    keys,
    path,
    period,
    scalar,
    typed,
    validate,
    validate_schema,
)
from eii_custodian.publicdata.fetch.page_shapes import blocks, parse

SCHOOL_FIELDS = (
    "objectid,name,aname,category,category_a,eng_type,type,adoptedcurriculum,"
    "operationalstatus,mncp_code,mncp_name,mncp_name_en,district_code,"
    "district_name,district_name_en,lat,long_"
).split(",")


def raises_missing(call, *args):
    with pytest.raises(ValueError, match=r"^schema_missing$"):
        call(*args)


def refutes(call, *args, message="schema_missing"):
    with pytest.raises(ValueError, match=r"^" + message + "$"):
        call(*args)


def plain(kind="string", **kwargs):
    return dict(kind=kind, **{"nullable": False, "optional": False} | kwargs)


# keys


def test_keys_refusals_and_identity():
    raises_missing(keys, "SYN", {"a"})
    raises_missing(keys, {}, {"a"})
    raises_missing(keys, {"a": 1, "SYN": 2}, {"a"})
    assert keys({"a": 1}, {"a"}) == {"a": 1}


# path


def test_path_token_and_value_refusals():
    raises_missing(path, {}, "SYN-not-a-list")
    raises_missing(path, {}, [5])
    raises_missing(path, {}, [""])
    raises_missing(path, {}, [[]])
    raises_missing(path, "SYN", ["a"])
    raises_missing(path, {"a": 1}, ["a", "b"])
    raises_missing(path, {"a": 1}, ["a", 0])
    raises_missing(path, {"": 7}, [""])
    assert path({"a": {"b": 7}}, ["a", "b"]) == 7
    assert path({}, []) == {}


# validate_schema


def test_validate_schema_scalars_and_unknown_kind():
    for kind in ("string", "integer", "number", "boolean"):
        validate_schema(plain(kind))
    refutes(validate_schema, "SYN-not-a-dict")
    refutes(validate_schema, plain("SYN-unknown"))


def test_validate_schema_array_branch():
    validate_schema(plain("array", items=plain()))
    refutes(validate_schema, plain("array", items={"SYN": "unknown"}))
    refutes(validate_schema, plain("array"))


def test_validate_schema_object_branch():
    validate_schema(plain("object", fields={"a": plain()}))
    refutes(validate_schema, plain("object", fields=[]))
    refutes(validate_schema, plain("object", fields={"": plain()}))
    refutes(validate_schema, plain("object", fields={5: plain()}))
    refutes(validate_schema, plain("object", fields={"a": "SYN-bad-child"}))


def test_validate_schema_nullable_optional_types():
    refutes(validate_schema, {"kind": "string", "nullable": 1, "optional": True})
    refutes(validate_schema, {"kind": "string", "nullable": True, "optional": 1})
    refutes(validate_schema, {"kind": "string", "nullable": "True", "optional": True})


# typed


def test_typed_nullability_is_declared_not_assumed():
    typed(None, plain(nullable=True))
    refutes(typed, None, plain())
    refutes(typed, "SYN", plain("integer", nullable=True))


def object_spec():
    return plain(
        "object",
        fields={"kept": plain(), "wanted": plain(optional=True)},
    )


def test_typed_object_branches():
    refutes(typed, 5, object_spec())
    typed({"kept": "SYN"}, object_spec())
    typed({"kept": "SYN", "wanted": "SYN"}, object_spec())
    refutes(typed, {}, object_spec())
    refutes(typed, {"kept": "SYN", "SYN": "SYN"}, object_spec())
    refutes(typed, {"kept": 5}, object_spec())


def test_typed_array_branches():
    spec = plain("array", items=plain())
    typed(["SYN"], spec)
    refutes(typed, [5], spec)
    refutes(typed, "SYN", spec)


def test_typed_scalar_kinds():
    typed("SYN", plain("string"))
    refutes(typed, 5, plain("string"))
    refutes(typed, {}, plain("string"))
    typed(True, plain("boolean"))
    refutes(typed, 1, plain("boolean"))
    typed(5, plain("integer"))
    refutes(typed, 5.0, plain("integer"))
    refutes(typed, True, plain("integer"))
    typed(5, plain("number"))
    typed(Decimal("5"), plain("number"))
    refutes(typed, "SYN", plain("number"))
    refutes(typed, True, plain("number"))
    refutes(typed, float("nan"), plain("number"))


# scalar


def test_scalar_conversion_contract():
    assert scalar(None, "string") is None
    assert scalar("", "integer") is None
    assert scalar("SYN", "string") == "SYN"
    refutes(scalar, 5, "string")
    assert scalar("7", "integer") == 7
    assert scalar("-7", "integer") == -7
    assert scalar(7, "integer") == 7
    refutes(scalar, 7.0, "integer")
    refutes(scalar, True, "integer")
    refutes(scalar, "7.5", "integer")
    refutes(scalar, "SYN", "integer")
    assert scalar("7.5", "number") == "7.5"
    refutes(scalar, "SYN", "number")
    refutes(scalar, "SYN", "SYN-kind")


# json_body


def test_json_body_types_and_constants():
    assert json_body(b'{"a": 1.5}')["a"] == Decimal("1.5")
    assert isinstance(json_body(b'{"a": 1.5}')["a"], Decimal)
    assert json_body(b'{"a": 7}')["a"] == 7
    raises_missing(json_body, b'{"a": 1, "a": 2}')
    raises_missing(json_body, b'{"a": NaN}')
    raises_missing(json_body, b'{"a": Infinity}')
    raises_missing(json_body, b"SYN not json")
    raises_missing(json_body, b'{"a": "\xff\xfe"}')
    assert json_body(b"[]") == []


# validate


def review(kind="embedded_json", shape=None, columns=None, **changes):
    dec = embedded()[0]
    if kind != "embedded_json":
        dec = declaration(kind, shape, columns or [["SYN", "string"]])
    elif shape is not None:
        dec["shape"] = shape
    if columns is not None:
        dec["columns"] = columns
    for name, value in changes.items():
        if value is ...:
            dec.pop(name, None)
        else:
            dec[name] = value
    return dec


def test_validate_accepts_the_reviewed_shapes():
    validate(review())
    validate(review(kind="html_blocks", shape=tariffs()["shape"]))
    validate(classified()[0])
    validate(workbook()[0])
    with_profile = review()
    with_profile["profile"] = "SYN"
    validate(with_profile)


def test_validate_as_of_gate():
    refutes(validate, review(as_of="SYN"), message="snapshot_date_missing")
    refutes(validate, review(as_of=...), message="snapshot_date_missing")


def test_validate_version_and_kind():
    refutes(validate, review(version=3))
    refutes(validate, review(version=2.0))
    refutes(validate, review(version=True))
    refutes(validate, review(kind="SYN-unknown"))
    refutes(validate, review(kind=5))
    refutes(validate, review(kind=...))


def test_validate_evidence_max_bytes_and_profile():
    refutes(validate, review(evidence=""))
    refutes(validate, review(evidence=5))
    refutes(validate, review(max_bytes=True))
    refutes(validate, review(max_bytes=0))
    refutes(validate, review(max_bytes="7"))
    validate(review(max_bytes=1))
    validate(review(max_bytes=None))


def test_validate_columns_contract():
    refutes(validate, review(columns="SYN"))
    refutes(validate, review(columns=()))
    refutes(validate, review(columns=[["SYN", "SYN-kind"]]))
    refutes(validate, review(columns=[["SYN", "string", "SYN"]]))
    refutes(validate, review(columns=[("SYN", "string")]))
    refutes(validate, review(columns=[[5, "string"]]))
    refutes(validate, review(columns=[["SYN", "string"], ["SYN", "number"]]))
    validate(review())


def blocks_review(columns):
    """The columns guard alone: html_blocks carries no fields cross-check."""
    return review(
        kind="html_blocks",
        shape=tariffs()["shape"],
        columns=columns,
        period_fields=[],
    )


def test_validate_columns_each_disjunct_refused():
    refutes(validate, blocks_review([["SYN", "string"], ["SYN", "number"]]))
    refutes(validate, blocks_review(()))
    refutes(validate, blocks_review([[5, "string"]]))
    refutes(validate, blocks_review([["SYN", "string", "SYN"]]))
    refutes(validate, blocks_review([("SYN", "string")]))
    validate(blocks_review([["SYN", "string"]]))


def test_validate_period_fields():
    validate(review(period_fields=["start"]))
    refutes(validate, review(period_fields=("start",)))
    refutes(validate, review(period_fields="SYN"))
    refutes(validate, review(period_fields=["start", "SYN"]))


def test_validate_publisher_date():
    validate(review(publisher_date="2031-02-03"))
    refutes(
        validate, review(publisher_date="2031-2-3"), message="snapshot_date_missing"
    )
    refutes(validate, review(publisher_date="SYN"), message="snapshot_date_missing")
    refutes(validate, review(publisher_date=5), message="snapshot_date_missing")
    refutes(validate, review(publisher_date=""), message="snapshot_date_missing")


def arcgis(**shape_changes):
    shape = {
        "layer": "https://invented.invalid/SYN",
        "fields": list(SCHOOL_FIELDS),
        "record_path": ["features"],
        "attribute_path": ["attributes"],
        "geometry": "esriGeometryPoint",
        "spatial_reference": "SYN",
        "order_by": "objectid",
        "page_size": 1,
        "where": "1=1",
        "record_schema": {
            **plain("object", nullable=True, optional=True),
            "fields": {
                name: plain(nullable=True, optional=True) for name in SCHOOL_FIELDS
            },
        },
    }
    shape.update(shape_changes)
    dec = review(
        kind="arcgis_query",
        shape=shape,
        columns=[["SYN-field", "string"]],
        url="https://invented.invalid/SYN?f=json",
    )
    return dec


def test_validate_arcgis_contract():
    validate(arcgis())
    refutes(
        validate,
        arcgis(layer="https://invented.invalid/SYN-other"),
        message="blocked_host",
    )
    refutes(validate, arcgis(record_path=["SYN"]))
    refutes(validate, arcgis(attribute_path=["SYN"]))
    refutes(validate, arcgis(order_by="SYN"), message="school_field_refused")
    refutes(validate, arcgis(where="SYN"), message="school_field_refused")
    refutes(validate, arcgis(fields=["SYN-other"]), message="school_field_refused")
    refutes(
        validate,
        arcgis(record_schema={"kind": "string"}),
        message="school_field_refused",
    )
    refutes(validate, arcgis(page_size=0))
    refutes(validate, arcgis(page_size=True))
    refutes(validate, arcgis(geometry="SYN"))
    refutes(validate, arcgis(page_size=1.0))


def test_validate_embedded_contract():
    shape = embedded()[0]["shape"]
    refutes(validate, review(shape=dict(shape, page_bound=2)))
    refutes(validate, review(shape=dict(shape, copies=3)))
    refutes(validate, review(shape=dict(shape, copies="SYN")))
    columns = [["title", "string"], ["start", "string"]]
    refutes(validate, review(columns=columns, period_fields=["start"]))


def test_validate_discovery_contract():
    shape = dict(tariffs()["shape"])
    shape["discovery"] = {"SYN": "SYN"}
    refutes(validate, review(kind="html_blocks", shape=shape))
    shape["discovery"] = {
        "url": "https://invented.invalid/SYN",
        "record_path": [],
        "link_path": [],
        "length_path": [],
        "modified_path": [],
        "count_header": "SYN",
        "pages_header": "SYN",
    }
    validate(review(kind="html_blocks", shape=shape))


def test_validate_blocks_contract():
    shape = dict(tariffs()["shape"])
    refutes(validate, review(kind="html_blocks", shape=dict(shape, layouts=["SYN"])))
    refutes(
        validate,
        review(kind="html_blocks", shape=dict(shape, layouts="SYN-not-a-list")),
    )
    refutes(
        validate,
        review(
            kind="html_blocks",
            shape=dict(shape, pages=[{"url": "SYN", "state": "SYN", "layout": None}]),
        ),
    )
    refutes(
        validate,
        review(
            kind="html_blocks",
            shape=dict(
                shape, pages=[{"url": "SYN", "state": "tariff", "layout": "SYN"}]
            ),
        ),
    )
    refutes(
        validate,
        review(
            kind="html_blocks",
            shape=dict(
                shape,
                pages=[{"url": "SYN", "state": "no tariff on page", "layout": "SYN"}],
            ),
        ),
    )
    refutes(
        validate,
        review(
            kind="html_blocks",
            shape=dict(shape, pages=[{"url": "SYN", "state": "tariff"}]),
        ),
    )


def test_validate_table_contract():
    dec = classified()[0]
    validate(dec)
    shape = dict(dec["shape"])
    refutes(validate, review(kind="html_table", shape=dict(shape, profile="SYN")))
    bad_section = dict(shape["sections"][0], SYN="SYN")
    refutes(
        validate,
        review(kind="html_table", shape=dict(shape, sections=[bad_section])),
    )
    non_bool = dict(shape["sections"][0], date_in_heading=1)
    refutes(
        validate,
        review(kind="html_table", shape=dict(shape, sections=[non_bool])),
    )
    off_host = dict(shape, path_template="https://invented.invalid/SYN/{page}")
    refutes(
        validate,
        review(kind="html_table", shape=off_host),
        message="blocked_host",
    )


def test_validate_xlsx_contract():
    dec = workbook()[0]
    validate(dec)
    sheet = dict(dec["shape"]["sheets"][0], SYN="SYN")
    refutes(
        validate, review(kind="xlsx_sheet", shape=dict(dec["shape"], sheets=[sheet]))
    )
    guessed = dict(dec["shape"]["sheets"][0], carry_year="SYN")
    refutes(
        validate, review(kind="xlsx_sheet", shape=dict(dec["shape"], sheets=[guessed]))
    )


def test_validate_hold_vocabulary():
    for hold in (
        "schema_evidence_pending",
        "acquisition_bound_unconfirmed",
        "awards_profile_pending",
    ):
        validate(review(hold=hold))
    refutes(validate, review(hold="SYN-invented"))
    refutes(validate, review(hold=True))


def test_validate_record_schema_hold_release():
    dec = embedded()[0]
    dec["shape"]["record_schema"] = "SYN-pending-evidence"
    refutes(validate, dec)
    dec["hold"] = "schema_evidence_pending"
    validate(dec)


def test_parse_hold_refusal_name():
    dec = embedded()[0]
    body = embedded()[1]
    dec["hold"] = "schema_evidence_pending"
    with pytest.raises(ValueError, match=r"^schema_evidence_pending$"):
        parse(body, dec)


# period


def row(**changes):
    base = {"SYN-date": "2031-02-03"}
    base.update(changes)
    return base


def test_period_accepts_years_quarters_and_datetimes():
    assert period([row()], ["SYN-date"]) == ("2031-02-03", "2031-02-03")
    assert period(
        [row(**{"SYN-date": "2031-Q2"}), row(**{"SYN-date": "2030"})], ["SYN-date"]
    ) == ("2030", "2031-Q2")
    assert period([row(**{"SYN-date": "2031-02-03T00:00:00Z"})], ["SYN-date"]) == (
        "2031-02-03T00:00:00Z",
        "2031-02-03T00:00:00Z",
    )
    assert period([row(**{"SYN-date": "0001"})], ["SYN-date"]) == ("0001", "0001")
    assert period([row(**{"SYN-date": "9999"})], ["SYN-date"]) == ("9999", "9999")
    assert period(
        [row(**{"SYN-date": "2031-Q1"}), row(**{"SYN-date": "2031-Q4"})], ["SYN-date"]
    ) == ("2031-Q1", "2031-Q4")
    assert period([], ["SYN-date"]) == (None, None)
    assert period([row()], []) == (None, None)


def test_period_refusals():
    def missing(value):
        refutes(
            lambda r, f: period(r, f),
            [row(**{"SYN-date": value})],
            ["SYN-date"],
            message="snapshot_date_missing",
        )

    missing("")
    missing(5)
    missing(None)
    missing("0000")
    missing("SYN")
    missing("2031-Q5")
    missing("10000")
    missing("2031-02-03T00:00:00z")


def test_tariff_parse_reaches_the_block_contract():
    dec = tariffs()
    rows = blocks(tariff(), dec["shape"], dec["url"])
    assert rows[0]["currency"] == "QR"
    assert rows[0]["unit"] == "per square meter per year"
