"""Bounded observations describe lexical columns, never semantic guesses."""

import hashlib
from pathlib import Path

import pytest

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_profile import bounded_input, observe_profile


@pytest.mark.parametrize("body", [b"", b"a,a\n1,2", b",a\n1,2", b"a,b\n1", b"\xff"])
def test_invalid_profiles_refuse(body: bytes) -> None:
    with pytest.raises(AssemblyError, match="assembly_intake_invalid"):
        observe_profile(body, "csv", "")


def test_lexical_types_and_original_columns_have_no_values() -> None:
    body = b"integer,number,text,blank\n12,1.5,SYN-secret,\n-2,1e3,12,\n"
    profile = observe_profile(body, "csv", "")
    assert profile["original_columns"] == ["integer", "number", "text", "blank"]
    assert profile["inferred_types"] == ["integer", "number", "string", "string"]
    assert profile["row_count"] == 2
    assert "SYN-secret" not in str(profile)


def test_bounded_profile_exact_limit_overflow_and_hash(tmp_path: Path) -> None:
    path = tmp_path / "SYN.csv"
    path.write_bytes(b"a\n1\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert bounded_input(path, 4, digest) == b"a\n1\n"
    with pytest.raises(AssemblyError, match="assembly_intake_bound"):
        bounded_input(path, 3, digest)
    with pytest.raises(AssemblyError, match="assembly_intake_invalid"):
        bounded_input(path, 4, "0" * 64)


def test_xlsx_profile_requires_explicit_sheet_and_reads_real_workbook() -> None:
    from io import BytesIO
    from zipfile import ZipFile

    stream = BytesIO()
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with ZipFile(stream, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets><sheet name="Awards" r:id="syn"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="syn" Target="worksheets/syn.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/syn.xml",
            f'<worksheet xmlns="{ns}"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>SYN-column</t></is></c></row><row r="2"><c r="A2"><v>12</v></c></row></sheetData></worksheet>',
        )
    body = stream.getvalue()
    profile = observe_profile(body, "xlsx", "Awards")
    assert profile["row_count"] == 1
    assert profile["inferred_types"] == ["integer"]
    with pytest.raises(AssemblyError, match="assembly_intake_invalid"):
        observe_profile(body, "xlsx", "")
