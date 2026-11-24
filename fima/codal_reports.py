"""Read structured CODAL report HTML from local files."""

from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
from json import JSONDecoder
from os import PathLike
from pathlib import Path
import re

from bs4 import BeautifulSoup
import pandas as pd


__all__ = ["get_codal_report", "get_codal_tables"]

_DATASOURCE = re.compile(r"(?m)^[ \t]*var[ \t]+datasource[ \t]*=\s*")
_FORMAT = "CodalDatasourceHTML"
_LETTER_REF = "ctl00_cphBody_ucDynamicFinancialStatement_hdfLetterRef"
_REVISION_PREFIX = "ctl00_cphBody_ucNavigateToNextPrevLetter_"
_PAGE_FIELDS = {
    "Title": "ctl00_h1MasterTitle",
    "CompanyName": "ctl00_txbCompanyName",
    "Symbol": "ctl00_txbSymbol",
    "DisplaySymbol": "ctl00_lblDisplaySymbol",
    "Isic": "ctl00_lblISIC",
    "ReportName": "ctl00_lblReportName",
    "PeriodLabel": "ctl00_lblPeriod",
    "PeriodEndDate": "ctl00_lblPeriodEndToDate",
    "FiscalYearEndDate": "ctl00_lblYearEndToDate",
    "AuditLabel": "ctl00_lblIsAudited",
    "PriceNote": "ctl00_pPriceNote",
}
_CELL_FIELDS = {
    "RowSequence": "rowSequence",
    "ColumnSequence": "columnSequence",
    "RowCode": "rowCode",
    "ColumnCode": "columnCode",
    "Address": "address",
    "Value": "value",
    "RowSpan": "rowSpan",
    "ColumnSpan": "colSpan",
    "IsVisible": "isVisible",
    "CellGroup": "cellGroupName",
}
_CELL_COLUMNS = (
    "SheetId", "TableId", "CellOrder", *_CELL_FIELDS, "ValuePresent", "ProviderMetadata"
)


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key {key!r}")
        obj[key] = value
    return obj


def _reject_constant(value):
    raise ValueError(f"invalid JSON number {value!r}")


def _integer(value):
    return Decimal(value) if value == "-0" else int(value)


_DECODER = JSONDecoder(
    parse_float=Decimal, parse_int=_integer, parse_constant=_reject_constant,
    object_pairs_hook=_unique_object,
)


def _read_datasource(page):
    assignments = []
    for script in page.find_all("script"):
        if script.has_attr("src") or script.get("type") not in (None, "text/javascript"):
            continue
        source = script.string or ""
        match = _DATASOURCE.search(source)
        if match:
            assignments.append(source[match.end():])
    if len(assignments) != 1:
        raise ValueError("Expected one embedded CODAL datasource assignment in saved HTML")
    expression = assignments[0]
    try:
        payload, end = _DECODER.raw_decode(expression)
    except (ValueError, ArithmeticError) as exc:
        raise ValueError(f"Malformed embedded CODAL datasource: {exc}") from exc
    if expression[end:].strip() != ";":
        raise ValueError("Expected CODAL datasource to end with a JSON value and semicolon")
    if not isinstance(payload, dict):
        raise ValueError("Expected a CODAL datasource object")
    return payload


def _identifier(value, field):
    if type(value) is int or (isinstance(value, str) and value.strip()):
        return str(value)
    raise ValueError(f"{field} must be a non-empty string or an integer")


def _validate_identity(record, key, expected, location):
    if key in record and _identifier(record[key], f"{location} {key}") != expected:
        raise ValueError(f"{location} {key} disagrees with its containing sheet or table")


def _validate_table(table, sheet_id, order):
    location = f"CODAL sheet {sheet_id!r} table at position {order}"
    if not isinstance(table, dict) or not isinstance(table.get("cells"), list):
        raise ValueError(f"{location} must contain a cells array")
    table_id = _identifier(table.get("code"), f"{location} code")
    _validate_identity(table, "sheetCode", sheet_id, location)
    meta_id = table.get("metaTableId")
    if meta_id is not None:
        meta_id = _identifier(meta_id, f"{location} metaTableId")
    for cell_order, cell in enumerate(table["cells"]):
        cell_location = f"{location} cell at position {cell_order}"
        if not isinstance(cell, dict) or any(
            type(cell.get(key)) is not int for key in ("rowSequence", "columnSequence")
        ):
            raise ValueError(f"{cell_location} must have integer rowSequence and columnSequence")
        _validate_identity(cell, "metaTableCode", table_id, cell_location)
        if meta_id is not None:
            _validate_identity(cell, "metaTableId", meta_id, cell_location)


def _read_sheets(payload):
    sheets = payload.get("sheets")
    if not isinstance(sheets, list) or not sheets:
        raise ValueError("CODAL datasource must contain a non-empty sheets array")
    loaded = {}
    for order, sheet in enumerate(sheets):
        if not isinstance(sheet, dict):
            raise ValueError(f"CODAL sheet at position {order} must be an object")
        sheet_id = _identifier(sheet.get("code"), f"CODAL sheet at position {order} code")
        if sheet_id in loaded:
            raise ValueError(f"Duplicate loaded CODAL sheet ID {sheet_id!r}")
        tables = sheet.get("tables")
        if not isinstance(tables, list) or not tables:
            raise ValueError(f"CODAL sheet {sheet_id!r} must contain a non-empty tables array")
        for table_order, table in enumerate(tables):
            _validate_table(table, sheet_id, table_order)
        loaded[sheet_id] = {
            "SheetId": sheet_id,
            "ProviderMetadata": {key: value for key, value in sheet.items() if key != "tables"},
            "Tables": tables,
        }
    return loaded


def _read_coverage(page, loaded, requested):
    if requested is not None and requested not in loaded:
        raise ValueError(f"CODAL sheet {requested!r} is not loaded in this file")
    menu = page.find("select", id="ctl00_ddlTable")
    options = [] if menu is None else [
        {
            "SheetId": option["value"],
            "Title": option.get_text().strip(),
            "IsSelected": option.has_attr("selected"),
        }
        for option in menu.find_all("option")
        if option.get("value")
    ]
    selected = [item["SheetId"] for item in options if item["IsSelected"]]
    if len(selected) > 1 or (selected and selected[0] not in loaded):
        raise ValueError("The selected CODAL sheet disagrees with the embedded sheet IDs")
    return {
        "LoadedSheetIds": list(loaded),
        "SheetOptions": options if menu is not None else None,
        "UnloadedSheetIds": [item["SheetId"] for item in options if item["SheetId"] not in loaded],
        "SelectedSheetId": selected[0] if selected else None,
        "RequestedSheetId": requested,
    }


def _page_metadata(page):
    metadata = {}
    for name, element_id in _PAGE_FIELDS.items():
        element = page.find(id=element_id)
        if element is not None:
            metadata[name] = element.get_text().strip()
    version = page.find("input", id="ctl00_hdfVersion")
    if version is not None and version.has_attr("value"):
        metadata["FilingVersion"] = version["value"]
    links = page.select(f'a[id^="{_REVISION_PREFIX}"]')
    if links:
        metadata["RevisionLinks"] = [
            {"ElementId": link["id"], "Text": link.get_text().strip(), "Href": link.get("href")}
            for link in links
        ]
    return metadata


def get_codal_report(path: str | PathLike[str], sheet_id: str | int | None = None) -> dict:
    """Read a saved UTF-8 CODAL HTML filing containing the structured datasource.

    Parameters
    ----------
    path : str or path-like
        Path to the saved HTML file. The reader only reads this file.
    sheet_id : str, int or None
        Select a loaded sheet for table extraction. None includes all loaded sheets.

    Returns
    -------
    dict
        Source, Content, ProviderMetadata, PageMetadata, Coverage and Sheets.

    Raises
    ------
    OSError
        The file cannot be read.
    ValueError
        The content is unsupported, malformed, or does not contain the requested sheet.
    """
    requested = None if sheet_id is None else _identifier(sheet_id, "sheet_id")
    local_path = Path(path).absolute()
    content = local_path.read_bytes()
    try:
        source_text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Expected a UTF-8 CODAL HTML document") from exc
    page = BeautifulSoup(source_text, "lxml")
    payload = _read_datasource(page)
    loaded = _read_sheets(payload)
    coverage = _read_coverage(page, loaded, requested)
    letter_ref = page.find("input", id=_LETTER_REF)
    form = page.find("form", id="aspnetForm")
    return {
        "Source": {
            "Provider": "CODAL",
            "Format": _FORMAT,
            "Path": str(local_path),
            "ContentSha256": sha256(content).hexdigest(),
            "LetterSerial": letter_ref.get("value") if letter_ref is not None else None,
            "FormAction": form.get("action") if form is not None else None,
        },
        "Content": content,
        "ProviderMetadata": {key: value for key, value in payload.items() if key != "sheets"},
        "PageMetadata": _page_metadata(page),
        "Coverage": coverage,
        "Sheets": list(loaded.values()),
    }


def _table_record(table, sheet_id, order, report):
    table_id = str(table["code"])
    rows = []
    for cell_order, source_cell in enumerate(table["cells"]):
        cell = deepcopy(source_cell)
        rows.append({
            "SheetId": sheet_id,
            "TableId": table_id,
            "CellOrder": cell_order,
            **{name: cell.get(key) for name, key in _CELL_FIELDS.items()},
            "ValuePresent": "value" in cell,
            "ProviderMetadata": cell,
        })
    return {
        "SheetId": sheet_id,
        "TableId": table_id,
        "TableOrder": order,
        "TitleFa": table.get("title_Fa"),
        "TitleEn": table.get("title_En"),
        "Version": table.get("versionNo"),
        "Description": table.get("description"),
        "PagePriceNote": report["PageMetadata"].get("PriceNote"),
        "ProviderMetadata": deepcopy({key: value for key, value in table.items() if key != "cells"}),
        "Source": report["Source"].copy(),
        "Cells": pd.DataFrame(rows, columns=_CELL_COLUMNS, dtype=object),
    }


def get_codal_tables(report: dict) -> list[dict]:
    """Extract the tables in the selected or loaded sheets of a CODAL report.

    Parameters
    ----------
    report : dict
        Report returned by get_codal_report.

    Returns
    -------
    list of dict
        Tables in source order, each with source metadata and a Cells DataFrame
        containing one record per original cell, with object dtype throughout.

    Raises
    ------
    TypeError
        report is not a CODAL report from get_codal_report.
    """
    required = {"Source", "Sheets", "PageMetadata", "Coverage"}
    if not isinstance(report, dict) or not required <= report.keys():
        raise TypeError("report must be returned by get_codal_report")
    if not isinstance(report["Source"], dict) or report["Source"].get("Format") != _FORMAT:
        raise TypeError("report must be returned by get_codal_report")
    requested = report["Coverage"]["RequestedSheetId"]
    return [
        _table_record(table, sheet["SheetId"], order, report)
        for sheet in report["Sheets"]
        if requested is None or sheet["SheetId"] == requested
        for order, table in enumerate(sheet["Tables"])
    ]
