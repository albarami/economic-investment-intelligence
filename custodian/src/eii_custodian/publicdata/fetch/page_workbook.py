"""One named-sheet OOXML reader for awards and insurance; no formula evaluation."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from .page_html import ShapeError

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RELNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


@dataclass(frozen=True)
class Sheet:
    cells: dict[str, str]
    rows: dict[int, list[str]]
    merges: tuple[str, ...]
    part: str
    relationship: str
    sheet_id: str
    stored_dates: dict[str, str] = field(default_factory=dict)


def read_sheet(
    body: bytes, name: str, *, cached_formulas: bool = False, date_cells: bool = False
) -> Sheet:
    """Preserve physical coordinates; reject aliases, duplicate cells and externals."""
    try:
        with ZipFile(io.BytesIO(body)) as archive:
            if len(set(archive.namelist())) != len(archive.namelist()):
                raise ShapeError("schema_missing")
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared = [
                    "".join(t.text or "" for t in item.findall(".//s:t", NS))
                    for item in ET.fromstring(archive.read("xl/sharedStrings.xml"))
                ]
            book = ET.fromstring(archive.read("xl/workbook.xml"))
            styles = _date_styles(archive) if date_cells else set()
            properties = book.find("s:workbookPr", NS)
            epoch_1904 = properties is not None and properties.get("date1904") in {
                "1",
                "true",
            }
            sheets = [
                s for s in book.findall("s:sheets/s:sheet", NS) if s.get("name") == name
            ]
            if len(sheets) != 1:
                raise ShapeError("schema_missing")
            rid = sheets[0].get("{" + RELNS + "}id", "")
            rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            targets = [
                r.get("Target", "")
                for r in rels
                if r.get("Id") == rid and r.get("TargetMode") != "External"
            ]
            if len(targets) != 1 or ".." in PurePosixPath(targets[0]).parts:
                raise ShapeError("schema_missing")
            part = targets[0].lstrip("/")
            if not part.startswith("xl/"):
                part = "xl/" + part
            if not part.startswith("xl/worksheets/") or not part.endswith(".xml"):
                raise ShapeError("schema_missing")
            root = ET.fromstring(archive.read(part))
            cells: dict[str, str] = {}
            rows: dict[int, list[str]] = {}
            stored_dates: dict[str, str] = {}
            previous = 0
            for node in root.findall("s:sheetData/s:row", NS):
                row: list[str] = []
                row_number = int(node.get("r", str(previous + 1)))
                if row_number <= previous:
                    raise ShapeError("schema_missing")
                previous = row_number
                if node.get("hidden", "0") not in {"0", "false"}:
                    raise ShapeError("schema_missing")
                for cell in node.findall("s:c", NS):
                    reference = cell.get("r", "")
                    match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", reference)
                    if (
                        match is None
                        or int(match[2]) != row_number
                        or reference in cells
                    ):
                        raise ShapeError("schema_missing")
                    formula = cell.find("s:f", NS)
                    if formula is not None and (
                        not cached_formulas or cell.find("s:v", NS) is None
                    ):
                        raise ShapeError("schema_missing")
                    column = 0
                    for letter in match[1]:
                        column = column * 26 + ord(letter) - ord("A") + 1
                    if column <= len(row):
                        raise ShapeError("schema_missing")
                    row.extend([""] * (column - len(row)))
                    kind = cell.get("t", "n")
                    value = cell.findtext("s:v", "", NS)
                    if kind == "s":
                        index = int(value)
                        if index < 0:
                            raise ShapeError("schema_missing")
                        value = shared[index]
                    elif kind == "inlineStr":
                        value = "".join(
                            t.text or "" for t in cell.findall("s:is//s:t", NS)
                        )
                    elif kind == "d" and date_cells:
                        stored_dates[reference] = (
                            datetime.fromisoformat(value).date().isoformat()
                        )
                    elif kind not in {"n", "str"}:
                        raise ShapeError("schema_missing")
                    if (
                        date_cells
                        and kind == "n"
                        and value
                        and int(cell.get("s", "0")) in styles
                    ):
                        stored_dates[reference] = _serial_date(value, epoch_1904)
                    if formula is not None and not value:
                        raise ShapeError("schema_missing")
                    cells[reference] = value
                    row[column - 1] = value
                rows[row_number] = row
            merges = tuple(
                m.get("ref", "") for m in root.findall("s:mergeCells/s:mergeCell", NS)
            )
            return Sheet(
                cells,
                rows,
                merges,
                part,
                rid,
                sheets[0].get("sheetId", ""),
                stored_dates,
            )
    except (BadZipFile, KeyError, ValueError, IndexError, ET.ParseError, OSError):
        raise ShapeError("schema_missing") from None


def _date_styles(archive: ZipFile) -> set[int]:
    """Recognise date storage from OOXML styles, never infer it from a number."""
    if "xl/styles.xml" not in archive.namelist():
        return set()
    root = ET.fromstring(archive.read("xl/styles.xml"))
    formats = {14, 15, 16, 17, 22}
    for node in root.findall("s:numFmts/s:numFmt", NS):
        code = re.sub(r'"[^"]*"|\\.|\[[^]]*\]', "", node.get("formatCode", "")).lower()
        if all(letter in code for letter in ("y", "m", "d")):
            formats.add(int(node.get("numFmtId", "-1")))
    return {
        index
        for index, node in enumerate(root.findall("s:cellXfs/s:xf", NS))
        if int(node.get("numFmtId", "0")) in formats
    }


def _serial_date(value: str, epoch_1904: bool) -> str:
    try:
        serial = Decimal(value)
        if (
            not serial.is_finite()
            or serial < 0
            or (not epoch_1904 and int(serial) == 60)
        ):
            raise ValueError
        days = int(serial)
        base = date(1904, 1, 1) if epoch_1904 else date(1899, 12, 31)
        if not epoch_1904 and days > 60:
            days -= 1
        return (base + timedelta(days=days)).isoformat()
    except (ValueError, OverflowError, InvalidOperation):
        raise ShapeError("schema_missing") from None
