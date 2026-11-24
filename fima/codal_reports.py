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


__all__ = ["get_codal_report", "get_codal_tables", "get_codal_monthly_activity"]

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


_MONTHLY_SHEET_VERSIONS = {
    "Monthly Activity Product - V3": ("3", 5),
    "Monthly Activity Product - V4": ("4", 3),
}
_MONTHLY_METRICS = {
    "تعداد تولید": ("ProductionQuantity", None, 1),
    "تعداد فروش": ("SalesQuantity", None, 1),
    "نرخ فروش (ریال)": ("SalesRate", "IRR", 1),
    "مبلغ فروش (میلیون ریال)": ("SalesAmount", "IRR", 1_000_000),
}
_MONTHLY_PERIODS = (
    (3, "PreviousYTD", "از ابتدای سال مالی تا تاریخ {date}", tuple(_MONTHLY_METRICS)),
    (7, "Adjustment", "اصلاحات", ("تعداد تولید", "تعداد فروش", "مبلغ فروش (میلیون ریال)")),
    (10, "AdjustedYTD", "از ابتدای سال مالی تا تاریخ {date} (اصلاح شده)", tuple(_MONTHLY_METRICS)),
    (14, "CurrentMonth", "دوره یک ماهه منتهی به {date}", tuple(_MONTHLY_METRICS)),
    (18, "CurrentYTD", "از ابتدای سال مالی تا تاریخ {date}", tuple(_MONTHLY_METRICS)),
    (22, "PriorYearYTD", "از ابتدای سال مالی تا تاریخ {date}", tuple(_MONTHLY_METRICS)),
)
_MONTHLY_SECTIONS = (
    ("DomesticSales", "Domestic", "فروش داخلی:", "جمع فروش داخلی"),
    ("ExportSales", "Export", "فروش صادراتی:", "جمع فروش صادراتی"),
    ("Services", None, "درآمد ارائه خدمات:", "جمع درآمد ارائه خدمات"),
    ("SalesReturns", None, "برگشت از فروش:", "جمع برگشت از فروش"),
)
_JALALI_DATE = re.compile(r"[0-9]{4}/(?:0[1-9]|1[0-2])/(?:0[1-9]|[12][0-9]|3[01])")
_REPORTED_DECIMAL = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?")
_PERSIAN_LETTERS = str.maketrans("يك", "یک")


def _monthly_error(detail):
    return ValueError(f"Unsupported or ambiguous CODAL manufacturing report: {detail}")


def _heading(value):
    return " ".join(value.translate(_PERSIAN_LETTERS).split()) if isinstance(value, str) else ""


def _monthly_date(value):
    if not isinstance(value, str) or not _JALALI_DATE.fullmatch(value):
        raise _monthly_error(f"expected a Jalali date, got {value!r}")
    return value


def _monthly_grid(cells, first_body_row):
    grid = {}
    for cell in cells.itertuples(index=False):
        row, column = key = cell.RowSequence, cell.ColumnSequence
        if (key in grid or not 1 <= column <= 26 or cell.IsVisible is not True
                or cell.Address != f"{chr(64 + column)}{row}"):
            raise _monthly_error(f"invalid, hidden or duplicate cell at {key}")
        grid[key] = cell

    header_columns = {1, 3, 7, 10, 14, 18, 22, 26}
    expected = {(1, column) for column in header_columns}
    expected.update((2, column) for column in range(1, 26))
    if {(row, column) for row, column in grid if row <= 2} != expected:
        raise _monthly_error("unexpected header coordinates")
    body_rows = sorted({row for row, _ in grid if row > 2})
    if body_rows != list(range(first_body_row, first_body_row + len(body_rows))):
        raise _monthly_error("unexpected production and sales row coordinates")
    rows = []
    for row in body_rows:
        body = [grid.get((row, column)) for column in range(1, 27)]
        if any(cell is None or cell.CellGroup != "Body" or (cell.RowSpan, cell.ColumnSpan) != (1, 1)
               for cell in body):
            raise _monthly_error(f"incomplete or merged body row {row}")
        rows.append(body)
    if len(grid) != len(expected) + 26 * len(rows):
        raise _monthly_error("unexpected body columns")
    return grid, rows


def _check_monthly_heading(cell, label, height=1, width=1):
    if (cell.CellGroup, cell.RowSpan, cell.ColumnSpan) != ("Header", height, width) or (
        _heading(cell.Value) != label
    ):
        raise _monthly_error(f"unexpected heading or span at {cell.Address}")


def _monthly_columns(grid, report_date):
    _check_monthly_heading(grid[1, 1], "شرح", width=2)
    _check_monthly_heading(grid[1, 26], "وضعیت محصول-واحد", height=2)
    _check_monthly_heading(grid[2, 1], "نام محصول")
    _check_monthly_heading(grid[2, 2], "واحد")
    columns = {}
    dates = {}
    for start, basis, template, headings in _MONTHLY_PERIODS:
        cell = grid[1, start]
        date = None
        if "{date}" in template:
            date = _monthly_date(cell.ProviderMetadata.get("periodEndToDate"))
        _check_monthly_heading(cell, template.format(date=date), width=len(headings))
        dates[basis] = date
        for column, heading in enumerate(headings, start):
            _check_monthly_heading(grid[2, column], heading)
            columns[column] = (basis, date, *_MONTHLY_METRICS[heading])

    year, month = map(int, report_date.split("/")[:2])
    previous_year, previous_month = (year, month - 1) if month > 1 else (year - 1, 12)
    if (
        dates["CurrentMonth"] != report_date
        or dates["CurrentYTD"] != report_date
        or dates["PreviousYTD"] != dates["AdjustedYTD"]
        or dates["PreviousYTD"][:7] != f"{previous_year:04d}/{previous_month:02d}"
        or dates["PriorYearYTD"][:7] != f"{year - 1:04d}/{month:02d}"
    ):
        raise _monthly_error("period headings disagree with the filing period")
    return columns


def _monthly_rows(rows):
    fixed = [
        (index, _heading(row[0].Value)) for index, row in enumerate(rows)
        if row[0].ProviderMetadata.get("rowTypeName") == "FixedRow"
    ]
    labels = [label for _, _, start, end in _MONTHLY_SECTIONS for label in (start, end)]
    if [label for _, label in fixed] != [*labels, "تخفیفات", "جمع"] or (
        fixed[0][0] != 0 or fixed[-1][0] != len(rows) - 1 or fixed[-2][0] != len(rows) - 2
    ):
        raise _monthly_error("unexpected production and sales section rows")

    for position, (section, market, _, _) in enumerate(_MONTHLY_SECTIONS):
        start, end = fixed[2 * position][0], fixed[2 * position + 1][0]
        if position and start != fixed[2 * position - 1][0] + 1:
            raise _monthly_error("data between production and sales sections")
        if any(cell.Value not in (None, "") for cell in rows[start][1:]):
            raise _monthly_error(f"values on section heading {rows[start][0].Address}")
        for row in rows[start + 1:end]:
            label, unit, status = row[0].Value, row[1].Value, row[-1].Value
            kind = row[0].ProviderMetadata.get("rowTypeName")
            if kind == "NewRow" and (label, unit, status) == ("", "", ""):
                if any(cell.Value not in (None, "", "0") for cell in row[2:-1]):
                    raise _monthly_error(f"observations without a product at {row[0].Address}")
                continue
            if kind != "CustomRow" or not _heading(label) or not _heading(unit):
                raise _monthly_error(f"unidentified detail row at {row[0].Address}")
            if status is not None and not isinstance(status, str):
                raise _monthly_error(f"invalid product status at {row[-1].Address}")
            yield row, section, market, "Detail"
        yield rows[end], section, market, "Subtotal"

    if fixed[-2][0] != fixed[-3][0] + 1:
        raise _monthly_error("data between the last subtotal and discounts")
    yield rows[-2], "Discounts", None, "Discount"
    yield rows[-1], "Total", None, "Total"


def _monthly_value(cell):
    value = cell.Value
    if value is None or value == "":
        return None
    if type(value) is int or isinstance(value, Decimal):
        return Decimal(value)
    if isinstance(value, str) and _REPORTED_DECIMAL.fullmatch(value):
        return Decimal(value)
    raise _monthly_error(f"unrecognized financial value at {cell.Address}: {value!r}")


def get_codal_monthly_activity(report: dict) -> pd.DataFrame:
    """Normalize the verified production and sales grid in a saved CODAL filing.

    Parameters
    ----------
    report : dict
        A Monthly Activity Product V3 or V4 report from get_codal_report.

    Returns
    -------
    pandas.DataFrame
        One row per reported metric cell for each named detail and total row,
        in source grid order. Values are exact Decimal or None, with original
        values, scales, period bases and coordinates. Filing metadata and source
        identity are also available in DataFrame.attrs.

    Raises
    ------
    TypeError
        report is not a CODAL report from get_codal_report.
    ValueError
        The report or grid is unsupported, incomplete or ambiguous.
    """
    tables = get_codal_tables(report)
    provider = report["ProviderMetadata"]
    page = report["PageMetadata"]
    title = provider.get("title_En")
    layout = _MONTHLY_SHEET_VERSIONS.get(title) if isinstance(title, str) else None
    candidates = [table for table in tables if table["TableId"] == "1197"]
    if (not layout or provider.get("type") != 58 or provider.get("period") != 1
            or provider.get("isConsolidated") is not False or len(candidates) != 1):
        raise _monthly_error("expected a standalone one-month V3 or V4 filing with table 1197")
    sheet_version, first_body_row = layout
    table = candidates[0]
    if (table["SheetId"], table["Version"], table["TitleEn"]) != (
        "1000000", "4", "Production and sales"
    ):
        raise _monthly_error("expected production and sales table 1197 v4 on sheet 1000000")
    sheet = next(sheet for sheet in report["Sheets"] if sheet["SheetId"] == table["SheetId"])
    sheet_metadata = sheet["ProviderMetadata"]
    if (sheet_metadata.get("aliasName"), sheet_metadata.get("versionNo")) != (
        "MonthlyActivity", sheet_version
    ):
        raise _monthly_error("unexpected monthly activity sheet version")

    tracing_no = provider.get("tracingNo")
    if type(tracing_no) is not int or tracing_no <= 0:
        raise _monthly_error("missing or invalid filing tracing number")
    report_date = _monthly_date(provider.get("periodEndToDate"))
    fiscal_end = _monthly_date(provider.get("yearEndToDate"))
    if page.get("PeriodEndDate", report_date) != report_date or (
        page.get("FiscalYearEndDate", fiscal_end) != fiscal_end
    ):
        raise _monthly_error("page dates disagree with the filing metadata")
    grid, rows = _monthly_grid(table["Cells"], first_body_row)
    columns = _monthly_columns(grid, report_date)

    filing = {
        "TracingNo": tracing_no,
        "CompanyName": page.get("CompanyName"),
        "SubjectName": provider.get("subject"),
        "Symbol": page.get("Symbol") or page.get("DisplaySymbol") or None,
        "FilingKind": provider.get("kind"),
        "ReportPeriodEndJalaliDate": report_date,
        "ContentSha256": report["Source"]["ContentSha256"],
        "SheetId": table["SheetId"],
        "TableId": table["TableId"],
    }
    records = []
    prior_fiscal_end = None
    for row, section, market, row_kind in _monthly_rows(rows):
        detail = row_kind == "Detail"
        label, product_unit, product_status = row[0].Value, row[1].Value, row[-1].Value
        if not detail and (product_unit not in (None, "") or product_status not in (None, "")):
            raise _monthly_error(f"unexpected product fields on total or discount {row[0].Address}")
        for cell in row[2:-1]:
            basis, date, metric, currency, scale = columns[cell.ColumnSequence]
            meta = cell.ProviderMetadata
            cell_date = meta.get("periodEndToDate") or None
            cell_fiscal_end = meta.get("yearEndToDate") or None
            if basis == "PriorYearYTD":
                if prior_fiscal_end is None:
                    prior_fiscal_end = _monthly_date(cell_fiscal_end)
                expected_fiscal_end = prior_fiscal_end
            else:
                expected_fiscal_end = fiscal_end if date else None
            if cell_date != date or cell_fiscal_end != expected_fiscal_end:
                raise _monthly_error(f"inconsistent period metadata at {cell.Address}")
            unit = currency or (product_unit if detail else None)
            records.append({
                **filing,
                "PeriodBasis": basis, "PeriodEndJalaliDate": date, "FiscalYearEndJalaliDate": cell_fiscal_end,
                "ActivitySection": section, "MarketSegment": market, "RowKind": row_kind,
                "RowLabel": label, "ProductName": label if detail else None,
                "ProductUnit": product_unit if detail else None, "ProductStatus": product_status if detail else None,
                "Metric": metric, "Value": _monthly_value(cell), "Unit": unit, "Scale": scale if unit else None,
                "RawValue": cell.Value, "ValuePresent": cell.ValuePresent,
                "RowSequence": cell.RowSequence, "ColumnSequence": cell.ColumnSequence, "Address": cell.Address,
                "CellOrder": cell.CellOrder,
            })

    result = pd.DataFrame(records, dtype=object)
    result.attrs = {key: deepcopy(report[key]) for key in ("Source", "ProviderMetadata", "PageMetadata", "Coverage")}
    return result
