"""Decision 0119 item 6: only a named digest field is exempt from the scans.

A string that merely looks like a SHA-256 (64 lowercase hexadecimal
characters) in any other place, a free-text card field, a nested value, a list
item, a mapping key, a column name or decoded bytes, meets the token scan and
the content scan like any other text. A named digest field holds exactly one
valid digest or refuses `digest_field_format`. Every value is invented; no run
of exactly eight or eleven digits is used.
"""

import copy
from dataclasses import replace

import pytest
from custodian.tests.test_registers import capture, commerce, inputs
from custodian.tests.test_registers_input_only_scan import (
    FRAME,
    KEY,
    PLAIN,
    _input_only,
    _scan,
    _tables,
)
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.registers.build import build
from eii_custodian.publicdata.registers.contracts import (
    DIGEST_FIELDS,
    ROLES,
    RegisterError,
)
from eii_custodian.publicdata.registers.validate import (
    scan_content,
    scan_metadata,
)

# A licence of 64 decimal digits: the intake integer grammar admits it, and it
# fully matches the digest shape.
LICENCE = "7" * 64
# The input-only number KEY padded to the digest shape with hex letters.
PADDED = "a" * 60 + KEY
assert len(LICENCE) == len(PADDED) == 64
# Every place in another release table where an ordinary string can sit.
ORDINARY = {
    "free_text": lambda s: {"name_en": s},
    "nested": lambda s: {"value": {"k": {"j": s}}},
    "list_item": lambda s: {"value": ["SYN", s]},
    "mapping_key": lambda s: {"value": {s: None}},
    "column_name": lambda s: {s: "SYN"},
    "bytes": lambda s: {"value": s.encode()},
    "nested_bytes": lambda s: {"value": {"k": [s.encode()]}},
    # A column named like a digest field in a table that has no such field.
    "unlisted_sha256": lambda s: {"sha256": s},
}
RELEASE_DIGESTS = sorted(f for f in DIGEST_FIELDS if not f.startswith("manifest."))
METADATA_DIGESTS = sorted(f for f in DIGEST_FIELDS if f.startswith("manifest."))


def _place(plant, value):
    return {**_tables(None, None), "pub_place": [ORDINARY[plant](value)]}


def _digest_row(field, value):
    table, column = field.split(".")
    return {**_tables(None, None), table: [{column: value}]}


# --- R1: a digest-shaped string in an ordinary field is scanned -------------


def test_register_digest_field_set_is_sourced():
    """The closed set: the release columns of document 03 section 7.3 that
    hold a SHA-256, and the manifest digests that `build.py`, the receipt
    files of `provenance.py` and storage's table descriptors write."""
    roles = {role for names in ROLES.values() for role in names}
    assert METADATA_DIGESTS == sorted(
        {"manifest.frame_sha256", "manifest.receipts.receipt_sha256"}
        | {"manifest.tables.sha256"}
        | {f"manifest.receipts.receipt.files.{role}.sha256" for role in roles}
    )
    assert set(RELEASE_DIGESTS) | set(METADATA_DIGESTS) == DIGEST_FIELDS


def test_register_64_digit_licence_in_name_en_refuses():
    """Rv1 R1's counterexample: the licence `7` * 64 in a card's `name_en`."""
    tables = _tables("biz_register", None)
    tables["pub_register_company"][0]["name_en"] = LICENCE
    _scan(tables)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan(tables, licences=(LICENCE,))


@pytest.mark.parametrize("role", ["licence", "withheld"])
def test_register_padded_key_in_card_free_text_refuses(role):
    tables = _tables("biz_register", None)
    tables["pub_register_company"][0]["name_en"] = PADDED
    _scan(tables)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan(tables, **_input_only(role))


@pytest.mark.parametrize("plant", sorted(ORDINARY))
@pytest.mark.parametrize("role", ["licence", "withheld"])
def test_register_padded_key_in_ordinary_place_refuses(plant, role):
    tables = _place(plant, PADDED)
    _scan(tables)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan(tables, **_input_only(role))


@pytest.mark.parametrize("plant", sorted(ORDINARY))
def test_register_64_digit_licence_in_ordinary_place_refuses(plant):
    tables = _place(plant, LICENCE)
    _scan(tables)
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan(tables, licences=(LICENCE,))


@pytest.mark.parametrize("plant", sorted(ORDINARY))
def test_register_digest_shaped_digit_run_in_ordinary_place_refuses(plant):
    """Rule 9's digit-run check also reaches a digest-shaped string."""
    _scan(_place(plant, "a" * 56 + "1" * 7 + "b"))
    with pytest.raises(RegisterError, match=r"^identifier_digit_run$"):
        _scan(_place(plant, "a" * 56 + "1" * 8))


def test_register_digest_shaped_value_in_fact_lineage_is_scanned():
    """The base's former exemption case: `fact_lineage` has no digest column."""
    row = {"lineage_id": "a" * 56 + "1" * 7 + "b"}
    _scan({**_tables(None, None), "fact_lineage": [row]})
    row = {"lineage_id": "a" * 28 + "1" * 8 + "b" * 28}
    with pytest.raises(RegisterError, match=r"^identifier_digit_run$"):
        _scan({**_tables(None, None), "fact_lineage": [row]})
    row = {"sha256": PADDED}
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        _scan({**_tables(None, None), "fact_lineage": [row]}, withheld=(KEY,))


# --- Passing controls: real digest fields still build -----------------------


@pytest.mark.parametrize("field", RELEASE_DIGESTS)
@pytest.mark.parametrize("value", [PADDED, LICENCE, "a" * 28 + "1" * 8 + "b" * 28])
def test_register_release_digest_field_builds(field, value):
    """A valid digest in a named digest column is not scanned, so even one
    holding an input-only key or a digit run publishes."""
    _scan(_digest_row(field, value), licences=(KEY, LICENCE), withheld=(KEY,))


BAD_DIGESTS = {
    "upper": "A" * 64,
    "short": "a" * 63,
    "long": "a" * 65,
    "non_hex": "g" * 64,
    "trailing_newline": "a" * 64 + "\n",
    "empty": "",
    "none": None,
    "int": 7,
    "bool": True,
    "bytes": b"a" * 64,
    "list": ["a" * 64],
    "mapping": {"a" * 64: "a" * 64},
    "str_subclass": type("Text", (str,), {})("a" * 64),
}


@pytest.mark.parametrize("field", RELEASE_DIGESTS)
@pytest.mark.parametrize("bad", BAD_DIGESTS.values(), ids=BAD_DIGESTS.keys())
def test_register_release_digest_field_format_refuses(field, bad):
    _scan(_digest_row(field, "b" * 64))
    with pytest.raises(RegisterError, match=r"^digest_field_format$"):
        _scan(_digest_row(field, bad))


# --- Metadata: the manifest's digest fields ---------------------------------


@pytest.fixture(scope="module")
def manifest(tmp_path_factory):
    """The published manifest, storage's table descriptors included."""
    built = build(
        tmp_path_factory.mktemp("digest"),
        "public_only",
        FRAME,
        (capture(), capture("fc_register")),
        (),
    )
    return built.manifest


def _set(manifest, field, value):
    """Set the first occurrence of a metadata field; lists are walked."""
    body = copy.deepcopy(manifest)
    *names, last = field.split(".")[1:]
    nodes = [body]
    for name in names:
        children = [node[name] for node in nodes if name in node]
        nodes = [n for c in children for n in (c if isinstance(c, list) else [c])]
    # StopIteration if the field does not occur in the published manifest.
    next(node for node in nodes if last in node)[last] = value
    return body


@pytest.mark.parametrize("field", METADATA_DIGESTS)
def test_register_manifest_holds_every_digest_field(manifest, field):
    _set(manifest, field, "c" * 64)


@pytest.mark.parametrize("field", METADATA_DIGESTS)
def test_register_manifest_digest_field_builds(manifest, field):
    keys = frozenset({KEY, "54321", "65432"})
    body = _set(manifest, field, PADDED)
    scan_metadata(body, keys, "manifest")
    scan_content(body, frozenset({"aaaa"}), "manifest")


@pytest.mark.parametrize("field", METADATA_DIGESTS)
@pytest.mark.parametrize("bad", BAD_DIGESTS.values(), ids=BAD_DIGESTS.keys())
def test_register_manifest_digest_field_format_refuses(manifest, field, bad):
    with pytest.raises(RegisterError, match=r"^digest_field_format$"):
        scan_metadata(_set(manifest, field, bad), frozenset(), "manifest")
    with pytest.raises(RegisterError, match=r"^digest_field_format$"):
        scan_content(_set(manifest, field, bad), frozenset(), "manifest")


ORDINARY_METADATA = {
    "method": lambda m, s: {**m, "method": s},
    "basis_note": lambda m, s: _set(m, "manifest.receipts.receipt.basis_note", s),
    "file_bytes": lambda m, s: _set(
        m, "manifest.receipts.receipt.files.establishments.bytes", s
    ),
    "unlisted_sha256": lambda m, s: {**m, "extra": {"sha256": s}},
    "list_item": lambda m, s: {**m, "extra": [s]},
    "mapping_key": lambda m, s: {**m, s: None},
    "bytes": lambda m, s: {**m, "extra": s.encode()},
}


@pytest.mark.parametrize("plant", sorted(ORDINARY_METADATA))
def test_register_padded_key_in_ordinary_metadata_refuses(manifest, plant):
    body = ORDINARY_METADATA[plant](manifest, PADDED)
    scan_metadata(body, frozenset({"54321"}), "manifest")
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        scan_metadata(body, frozenset({KEY}), "manifest")


@pytest.mark.parametrize("plant", sorted(ORDINARY_METADATA))
def test_register_digest_shaped_card_text_in_metadata_refuses(manifest, plant):
    """The content scan also meets a digest-shaped string outside a digest
    field: a card name of the digest shape copied into metadata refuses."""
    body = ORDINARY_METADATA[plant](manifest, PADDED)
    scan_content(body, frozenset({"SYN Plaza Zeta"}), "manifest")
    with pytest.raises(RegisterError, match=r"^register_content_egress$"):
        scan_content(body, frozenset({PADDED}), "manifest")


def test_register_build_passes_metadata_paths_to_content_scan(tmp_path):
    """End to end: a card name that is a piece of the frame digest builds,
    because `manifest.frame_sha256` is a named digest field; the same text in
    the receipt's `basis_note`, an ordinary manifest field, refuses."""
    name = FRAME.sha256[:12]
    item = capture(files=inputs(rows=[commerce(**PLAIN, name_en=name)]))
    centre = capture("fc_register")
    build(tmp_path / "pass", "public_only", FRAME, (item, centre), ())
    item = replace(item, receipt={**item.receipt, "basis_note": "SYN " + name})
    with pytest.raises(RegisterError, match=r"^register_content_egress$"):
        build(tmp_path / "refuse", "public_only", FRAME, (item, centre), ())
    assert not (tmp_path / "refuse" / "current").exists()


def test_register_report_has_no_digest_field():
    """A report path never matches a manifest digest field."""
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        scan_metadata({"frame_sha256": PADDED}, frozenset({KEY}), "report")
    with pytest.raises(RegisterError, match=r"^registration_egress$"):
        scan_metadata({"frame_sha256": PADDED}, frozenset({KEY}), "")


# --- A generator over digest-shaped strings ---------------------------------


@st.composite
def _digest_shaped(draw):
    """A 64-hex string holding one whole number token, padded with letters."""
    number = draw(st.from_regex(r"[1-9][0-9]{0,5}", fullmatch=True))
    left = draw(st.integers(0, 64 - len(number)))
    pad = st.text("abcdef", min_size=64, max_size=64)
    text = draw(pad)
    value = text[:left] + number + text[left + len(number) :]
    assert len(value) == 64
    return number, value


_PLANTS = {
    **{name: (lambda s, f=f: ("pub_place", f(s))) for name, f in ORDINARY.items()},
    "card_name_en": lambda s: ("pub_register_company", {"name_en": s}),
    "digest_field": lambda s: ("source_registry", {"sha256": s}),
}


@given(
    _digest_shaped(),
    st.sampled_from(sorted(_PLANTS)),
    st.sampled_from(["released", "licence", "withheld"]),
)
def test_register_digest_shaped_ordinary_value_property(drawn, plant, role):
    """Oracle: only a named digest field is exempt; elsewhere an input-only
    key inside a digest-shaped string refuses and a released one publishes."""
    number, value = drawn
    if number in {"54321", "65432"}:
        return  # a key slot itself or a cross-source key, tested elsewhere
    table, row = _PLANTS[plant](value)
    tables = _tables(None, None, registration=number if role == "released" else "54321")
    if table == "pub_register_company":
        tables[table][0].update(row)
    else:
        tables[table] = [row]
    sets = {
        "released": {},
        "licence": dict(licences=(number,)),
        "withheld": dict(withheld=(number,)),
    }[role]
    if role != "released" and plant != "digest_field":
        with pytest.raises(RegisterError, match=r"^registration_egress$"):
            _scan(tables, **sets)
    else:
        _scan(tables, **sets)
