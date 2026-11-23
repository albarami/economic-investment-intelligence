"""Deterministic parsers bound to the reviewed round-two live source shapes."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from .award_checks import AWARD_ABSENT, DATE_ABSENT
from .page_html import ShapeError, Tree, table_rows
from .page_schema import json_body, path, scalar, typed, validate
from .page_workbook import read_sheet


def embedded(
    body: bytes, shape: Mapping[str, Any], columns: list[list[str]]
) -> list[dict[str, object]]:
    root = Tree(body).root
    holders = root.find(shape["element"])
    if shape["attribute"] is None:
        holders = [
            n
            for n in holders
            if n.attrs.get("id") == shape["id"] and n.attrs.get("type") == shape["type"]
        ]
        values = [json_body(n.text().encode()) for n in holders]
    else:
        values = [
            json_body((n.attrs.get(shape["attribute"]) or "").encode()) for n in holders
        ]
    if len(values) != shape["copies"] or any(v != values[0] for v in values):
        raise ShapeError("schema_missing")
    if (
        shape["more_path"] is not None
        and path(values[0], shape["more_path"]) is not False
    ):
        raise ShapeError("paging_incomplete")
    records = path(values[0], shape["record_path"])
    if not isinstance(records, list):
        raise ShapeError("schema_missing")
    result = []
    for record in records:
        typed(record, shape["record_schema"])
        row = {
            name: scalar(path(record, shape["fields"][name]), kind)
            for name, kind in columns
        }
        row["published_record"] = record
        result.append(row)
    return result


def workbook(body: bytes, shape: Mapping[str, Any]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for spec in shape["sheets"]:
        sheet = read_sheet(body, spec["name"], cached_formulas=True)
        if (
            sheet.part != spec["part"]
            or sheet.relationship != spec["relationship"]
            or sheet.sheet_id != spec["sheet_id"]
            or set(sheet.merges) != set(spec["merged_cells"])
            or len(sheet.merges) != len(spec["merged_cells"])
            or spec["period_cell"] not in spec["header_cells"]
            or spec["header_cells"][spec["period_cell"]] != "End of Period"
            or any(
                sheet.cells.get(c) != text for c, text in spec["header_cells"].items()
            )
        ):
            raise ShapeError("schema_missing")
        cells = sheet.cells
        header_row = max(int(re.sub("[A-Z]", "", c)) for c in spec["header_cells"])
        declared = {
            c: text
            for c, text in spec["header_cells"].items()
            if int(re.sub("[A-Z]", "", c)) == header_row
        }
        observed = {
            c: text
            for c, text in cells.items()
            if int(re.sub("[A-Z]", "", c)) == header_row and text
        }
        if declared != observed:
            raise ShapeError("schema_missing")
        footer = spec["footer_row"]
        if (
            cells.get("A" + str(footer)) != "*Primary Data"
            or cells.get(spec["footer_last_column"] + str(footer)) != "*بيانات أولية"
        ):
            raise ShapeError("schema_missing")
        if any(
            text
            for ref, text in cells.items()
            if int(re.sub("[A-Z]", "", ref)) > footer
        ):
            raise ShapeError("schema_missing")
        if any(sheet.rows.get(spec["blank_row"], [])):
            raise ShapeError("schema_missing")
        annual, quarters = spec["annual_rows"], spec["quarter_rows"]
        if any(
            not isinstance(r, list)
            or len(r) != 2
            or any(type(v) is not int or v < 1 for v in r)
            or r[0] > r[1]
            for r in (annual, quarters)
        ):
            raise ShapeError("schema_missing")
        if (
            annual[1] + 1 != spec["blank_row"]
            or spec["blank_row"] + 1 != quarters[0]
            or quarters[1] + 1 != footer
        ):
            raise ShapeError("schema_missing")
        year: str | None = None
        previous_quarter: int | None = None
        for first, last, quarterly in [
            (annual[0], annual[1], False),
            (quarters[0], quarters[1], True),
        ]:
            for row in range(first, last + 1):
                raw_year = cells.get(spec["year_column"] + str(row), "")
                quarter = cells.get(spec["quarter_column"] + str(row), "")
                preliminary = False
                if quarterly:
                    match = re.fullmatch(r"Q([1-4])(\*)?", quarter)
                    if match is None or not cells.get(
                        spec["quarter_label_column"] + str(row)
                    ):
                        raise ShapeError("schema_missing")
                    q = int(match[1])
                    preliminary = bool(match[2])
                    if q == 1 and previous_quarter not in (None, 4):
                        raise ShapeError("schema_missing")
                    # The first observation may be any quarter; no evidence for
                    # requiring Q1 was found (document 03, section "S2-T29
                    # cached page and awards contracts").
                    if previous_quarter is None or q == 1:
                        if re.fullmatch(r"[1-9][0-9]{3}", raw_year) is None:
                            raise ShapeError("schema_missing")
                        if year is not None and int(raw_year) != int(year) + 1:
                            raise ShapeError("schema_missing")
                        year = raw_year
                    elif raw_year or q != previous_quarter + 1:
                        raise ShapeError("schema_missing")
                    previous_quarter = q
                    label = str(year) + "-Q" + str(q)
                else:
                    if (
                        quarter
                        or cells.get(spec["quarter_label_column"] + str(row), "")
                        or re.fullmatch(r"[1-9][0-9]{3}", raw_year) is None
                    ):
                        raise ShapeError("schema_missing")
                    label = raw_year
                # Undeclared data columns cannot be silently accepted.
                allowed = {
                    spec[k]
                    for k in ("year_column", "quarter_column", "quarter_label_column")
                } | set(spec["columns"].values())
                if any(
                    text and re.sub("[0-9]", "", ref) not in allowed
                    for ref, text in cells.items()
                    if int(re.sub("[A-Z]", "", ref)) == row
                ):
                    raise ShapeError("schema_missing")
                for measure, column in spec["columns"].items():
                    value = cells.get(column + str(row))
                    if value is None or value == "":
                        raise ShapeError("schema_missing")
                    result.append(
                        {
                            "sheet": spec["name"],
                            "period": label,
                            "measure": measure,
                            "value": scalar(value, "number"),
                            "preliminary": "true" if preliminary else "false",
                        }
                    )
    return result


def blocks(body: bytes, shape: Mapping[str, Any], url: str) -> list[dict[str, object]]:
    root = Tree(body).root
    pages = [p for p in shape["pages"] if p["url"] == url]
    if len(pages) != 1:
        raise ShapeError("blocked_host")
    spec = pages[0]
    all_blocks = root.find("div.price")
    headings = [n for n in root.find("h3") if n.text().strip() == shape["heading"]]
    if spec["state"] == "no tariff on page":
        if all_blocks or headings:
            raise ShapeError("schema_missing")
        return []
    if len(headings) != 1:
        raise ShapeError("schema_missing")
    heading = headings[0]
    parent = heading.parent
    scopes = root.find(shape["scope"])
    if parent is None or parent.parent not in scopes:
        raise ShapeError("schema_missing")
    layout = spec["layout"]
    expected = "div.col-lg-3" if layout == "single" else "div.col-12"
    if not parent.matches(expected):
        raise ShapeError("schema_missing")
    found = parent.find("div.price")
    if len(found) != (1 if layout == "single" else 2) or len(all_blocks) != len(found):
        raise ShapeError("schema_missing")
    if parent.nodes()[0] is not heading:
        raise ShapeError("schema_missing")
    if layout == "single" and any(
        n.parent is not parent or not n.matches("div.price.mb-4") for n in found
    ):
        raise ShapeError("schema_missing")
    if layout == "double":
        containers = parent.find("div.row.mb-4 > div.col-md-6 > div.price")
        if len(containers) != 2 or {id(n) for n in containers} != {
            id(n) for n in found
        }:
            raise ShapeError("schema_missing")
    result = []
    for node in found:
        label = node.one("div.priceHeader").text().strip()
        amount = node.one("div.priceDetails > h4")
        currency = amount.one("span").text().strip()
        text = "".join(c for c in amount.children if isinstance(c, str)).strip()
        unit = node.one("div.priceDetails > p.text-gold > i").text().strip()
        if (
            re.fullmatch(r"[0-9]+", text) is None
            or currency != shape["currency"]
            or unit != shape["unit"]
            or not label
        ):
            raise ShapeError("schema_missing")
        result.append(
            {
                "label": label,
                "value": scalar(text, "number"),
                "currency": currency,
                "unit": unit,
            }
        )
    return result


def classified(
    body: bytes, shape: Mapping[str, Any], columns: list[list[str]]
) -> list[dict[str, object]]:
    root = Tree(body).root
    table = root.one(shape["selector"])
    result: list[dict[str, object]] = []
    bindings = set()
    for cells in table_rows(table, shape["headers"]):
        links = cells[-1].find("a")
        if len(links) != 1:
            raise ShapeError("schema_missing")
        match = re.fullmatch(
            r"javascript:openCompanyDataModel\(([0-9]+)\);",
            links[0].attrs.get("href") or "",
        )
        if match is None or match[1] in bindings:
            raise ShapeError("schema_missing")
        bindings.add(match[1])
        modal = root.one("div#CompanyData-" + match[1])
        if (
            not modal.matches("div.modal.fade.bd-example-modal-lg")
            or table.parent is None
            or modal.parent is not table.parent.parent
        ):
            raise ShapeError("schema_missing")
        row = {
            name: scalar(c.text().strip(), kind)
            for (name, kind), c in zip(columns, cells, strict=True)
        }
        activities: list[dict[str, object]] = []
        tables = modal.find("table.custom--table.mb-5")
        headings = modal.find("div.alert.alert-success")
        if not tables or len(headings) != len(tables):
            raise ShapeError("schema_missing")
        for heading in headings:
            siblings = heading.parent.nodes() if heading.parent else []
            index = next(i for i, n in enumerate(siblings) if n is heading)
            if index + 1 >= len(siblings) or not siblings[index + 1].matches(
                "table.custom--table.mb-5"
            ):
                raise ShapeError("schema_missing")
            sub = siblings[index + 1]
            matches = [
                s
                for s in shape["sections"]
                if (
                    heading.text().strip().startswith(s["heading"])
                    if s["date_in_heading"]
                    else heading.text().strip() == s["heading"]
                )
            ]
            if len(matches) != 1:
                raise ShapeError("schema_missing")
            section = matches[0]
            expiry = None
            if section["date_in_heading"]:
                try:
                    expiry = (
                        datetime.strptime(
                            heading.text().strip()[len(section["heading"]) :],
                            "%d/%m/%Y",
                        )
                        .date()
                        .isoformat()
                    )
                except ValueError:
                    raise ShapeError("schema_missing") from None
            for raw in table_rows(sub, section["headers"]):
                values = {
                    h: c.text().strip()
                    for h, c in zip(section["headers"], raw, strict=True)
                }
                row_expiry = expiry
                if not section["date_in_heading"]:
                    try:
                        row_expiry = (
                            datetime.strptime(raw[-1].text().strip(), "%d/%m/%Y")
                            .date()
                            .isoformat()
                        )
                    except ValueError:
                        raise ShapeError("schema_missing") from None
                activities.append(
                    {
                        "section": section["heading"],
                        "expiry": row_expiry,
                        "fields": values,
                    }
                )
        row["activities"] = activities
        result.append(row)
    modals = [
        n
        for n in root.find("div")
        if (n.attrs.get("id") or "").startswith("CompanyData-")
    ]
    if len(modals) != len(bindings):
        raise ShapeError("schema_missing")
    return result


def page_end(body: bytes, shape: Mapping[str, Any]) -> tuple[int, int]:
    root = Tree(body).root
    text = root.one(shape["total_selector"]).text().strip()
    if not text.startswith(shape["total_prefix"]):
        raise ShapeError("paging_incomplete")
    total = text[len(shape["total_prefix"]) :].strip()
    links = root.one('nav[aria-label="Page navigation"]').find(shape["last_selector"])
    if len(links) != 1 or not total.isascii() or not total.isdigit():
        raise ShapeError("paging_incomplete")
    last = links[0].text().strip()
    if not last.isascii() or not last.isdigit() or int(last) < 1:
        raise ShapeError("paging_incomplete")
    if (
        urlsplit(links[0].attrs.get("href") or "").path
        != urlsplit(shape["path_template"].format(page=int(last))).path
    ):
        raise ShapeError("paging_incomplete")
    return int(total), int(last)


def awards(
    body: bytes, shape: Mapping[str, Any], columns: list[list[str]]
) -> list[dict[str, object]]:
    root = Tree(body).root
    headings = root.find("h3")
    headers = [n for n in headings if n.text().strip() == shape["headers"][0]]
    date_text = root.one("span#lblAwardedDate").text().strip()
    if not headers:
        reviewed = {section["heading"] for section in shape["sections"]}
        if any(heading.text().strip() not in reviewed for heading in headings):
            raise ShapeError("schema_missing")
        return [dict(AWARD_ABSENT)]
    if len(headers) != 1:
        raise ShapeError("schema_missing")
    heading = headers[0]
    siblings = heading.parent.nodes() if heading.parent else []
    index = next(i for i, n in enumerate(siblings) if n is heading)
    if index + 1 >= len(siblings):
        raise ShapeError("schema_missing")
    table = siblings[index + 1].one(shape["selector"])
    rows = table_rows(table, shape["headers"][1:])
    if not rows:
        raise ShapeError("schema_missing")
    awarded_date = None
    if date_text:
        try:
            awarded_date = datetime.strptime(date_text, "%d/%m/%Y").date().isoformat()
        except ValueError:
            raise ShapeError("snapshot_date_missing") from None
    result = []
    for raw in rows:
        record = {}
        for (name, kind), node in zip(columns, raw, strict=True):
            text = node.text().strip()
            if kind == "number" and text == "رق":
                text = ""
            if kind == "number" and text:
                # Source uses comma groups, two decimals and the literal currency suffix.
                m = re.fullmatch(
                    r"([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2}|[0-9]+\.[0-9]{2}) رق", text
                )
                if m is None:
                    raise ShapeError("schema_missing")
                text = m[1].replace(",", "")
            record[name] = scalar(text, kind)
        record["award_date"] = awarded_date
        if awarded_date is None:
            record["proof_date_status"] = DATE_ABSENT
        result.append(record)
    return result


def parse(
    body: bytes, review: Mapping[str, Any], *, url: str | None = None
) -> list[dict[str, object]]:
    validate(review)
    if review["hold"] is not None:
        raise ShapeError(review["hold"])
    kind, shape, columns = review["kind"], review["shape"], review["columns"]
    if kind == "citation_snapshot":
        return []
    if kind == "fc_company_cards":
        from ..fc_register.parse import fragment, project

        projected = body if body.startswith(b"{") else project(body, shape).body
        rows: list[dict[str, object]] = fragment(projected)["rows"]
        return rows
    if kind == "embedded_json":
        return embedded(body, shape, columns)
    if kind == "xlsx_sheet":
        return workbook(body, shape)
    if kind == "html_blocks":
        return blocks(body, shape, url or review["url"])
    if kind == "html_table":
        if shape["profile"] == "classified":
            return classified(body, shape, columns)
        if shape["profile"] == "awards":
            return awards(body, shape, columns)
    raise ShapeError("schema_missing")


def award_cards(body: bytes) -> list[dict[str, str]]:
    """Read the evidenced invalid div-inside-tr cards, without following any link."""
    root = Tree(body).root
    table = root.one("div.custom--table--responsive.py-2 > table.custom--table")
    result = []
    for tr in table.find("tbody > tr"):
        cards = [n for n in tr.nodes() if n.matches("div.row.custom-cards")]
        if len(cards) != 1:
            raise ShapeError("schema_missing")
        card = cards[0]
        number = (
            card.one(
                "div.col-md-7.cards-col > div.col-header > span.card-label > label"
            )
            .text()
            .strip()
        )
        titles = [
            n
            for n in card.find("span.card-title > a")
            if (n.attrs.get("href") or "").startswith(
                "/TendersOnlineServices/TenderDetails/"
            )
        ]
        if len(titles) != 1:
            raise ShapeError("schema_missing")
        dates = [
            n
            for n in card.find("div.cards-row")
            if any(
                c.text().strip() == "تاريخ الترسية"
                for c in n.find("span.card-label > label")
            )
        ]
        if len(dates) != 1:
            raise ShapeError("schema_missing")
        text = dates[0].one("span.card-title > span > label").text().strip()
        try:
            date_value = datetime.strptime(text, "%d/%m/%Y").date().isoformat()
        except ValueError:
            raise ShapeError("snapshot_date_missing") from None
        proof = (
            card.one("div.col-md-2.circle-container > a.btn.btn-primary").attrs.get(
                "href"
            )
            or ""
        )
        if not proof.startswith("/TendersOnlineServices/TenderCompaniesDetails/"):
            raise ShapeError("schema_missing")
        result.append(
            {
                "number": number,
                "title": titles[0].text().strip(),
                "award_date": date_value,
                "report_path": proof,
            }
        )
    return result
