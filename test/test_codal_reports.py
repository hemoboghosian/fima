"""Contracts for local CODAL HTML with synthetic provider data."""

from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import socket

import pandas as pd
import pytest

from fima import get_codal_report, get_codal_tables


FIXTURE = Path(__file__).parent / "fixtures" / "codal_structured.html"


def save_payload(tmp_path, expression, menu=""):
    path = tmp_path / "report.html"
    path.write_text(f"<html>{menu}<script>\nvar datasource = {expression};\n</script></html>", encoding="utf-8")
    return path


def test_saved_report_metadata_and_coverage():
    report = get_codal_report(str(FIXTURE), sheet_id="0")
    assert report["Content"] == FIXTURE.read_bytes()
    assert report["Source"] == {
        "Provider": "CODAL",
        "Format": "CodalDatasourceHTML",
        "Path": str(FIXTURE.absolute()),
        "ContentSha256": sha256(FIXTURE.read_bytes()).hexdigest(),
        "LetterSerial": "sample==",
        "FormAction": "./InterimStatement.aspx?LetterSerial=sample%3D%3D&SheetId=0",
    }
    metadata = report["ProviderMetadata"]
    assert metadata["subject"] == "شرکت موضوع گزارش"
    assert metadata["tracingNo"] == 123456
    assert metadata["type"] == 6
    assert metadata["period"] == 6
    assert metadata["periodEndToDate"] == "1404/06/31"
    assert metadata["publishDateTime"] == "1404/08/30 07:00:00"
    page = report["PageMetadata"]
    assert page["CompanyName"] == "شرکت نمونه"
    assert page["Symbol"] == "نمونه"
    assert page["DisplaySymbol"] == ""
    assert page["Isic"] == "001234"
    assert page["FilingVersion"] == "1"
    assert page["Title"] == "گزارش نمونه (اصلاحیه)"
    assert page["RevisionLinks"] == [{
        "ElementId": "ctl00_cphBody_ucNavigateToNextPrevLetter_hlNewVersion",
        "Text": "نسخه جدیدتر", "Href": "?LetterSerial=other",
    }]
    assert report["Coverage"] == {
        "LoadedSheetIds": ["0"],
        "SheetOptions": [
            {"SheetId": "1", "Title": "صورت سود و زیان", "IsSelected": False},
            {"SheetId": "0", "Title": "صورت وضعیت مالی", "IsSelected": True},
            {"SheetId": "9", "Title": "صورت جریان های نقدی", "IsSelected": False},
        ],
        "UnloadedSheetIds": ["1", "9"],
        "SelectedSheetId": "0",
        "RequestedSheetId": "0",
    }
    assert report["Sheets"][0]["ProviderMetadata"]["sheetComponents"] == {"101": ["نمونه"]}


def test_tables_preserve_source_order_financial_values_and_grid():
    report = get_codal_report(FIXTURE, sheet_id=0)
    tables = get_codal_tables(report)
    assert [(table["SheetId"], table["TableId"], table["TableOrder"]) for table in tables] == [
        ("0", "21", 0), ("0", "19", 1),
    ]
    balance, shares = tables
    assert balance["TitleFa"] == "وضعیت مالی"
    assert balance["TitleEn"] == "Balance Sheet"
    assert balance["Version"] == "7"
    assert balance["Description"] == "مبالغ به میلیون ریال"
    assert shares["Description"] == "واحد: سهم"
    assert shares["Cells"].at[0, "Value"] == "0010"
    assert balance["PagePriceNote"] == "ارقام به میلیون ریال"
    assert balance["ProviderMetadata"]["sequence"] == 3
    assert balance["ProviderMetadata"]["metaTableId"] == 901
    assert balance["Source"] == report["Source"]
    cells = balance["Cells"]
    assert isinstance(cells, pd.DataFrame)
    assert all(dtype == object for dtype in cells.dtypes)
    assert cells["CellOrder"].tolist() == list(range(9))
    assert cells.loc[:2, ["RowSequence", "ColumnSequence"]].values.tolist() == [[2, 1], [1, 6], [1, 6]]
    assert cells.loc[0, ["Address", "RowCode", "ColumnCode", "RowSpan", "ColumnSpan", "CellGroup"]].tolist() == [
        "A2", 0, 7, 2, 3, "Header",
    ]
    assert cells.at[0, "Value"] == "شرح; {ریال}"
    assert cells.at[1, "IsVisible"] is False
    assert cells.at[2, "IsVisible"] is None
    assert cells.at[1, "ProviderMetadata"]["periodEndToDate"] == "1404/06/31"
    assert cells.at[1, "ProviderMetadata"]["financialConcept"] == "sample"
    assert cells.at[1, "Value"] == Decimal("-0.100000000000000000001")
    assert type(cells.at[2, "Value"]) is int
    assert cells.at[2, "Value"] == 900719925474099312345
    assert cells["Value"].tolist()[3:8] == [0, None, None, "", "(۱٬۲۳۴)"]
    assert cells["ValuePresent"].tolist()[3:7] == [True, False, True, True]
    assert cells.at[8, "Value"].is_signed()


def test_multiple_loaded_sheets_keep_payload_order(tmp_path):
    payload = {
        "sheets": [
            {"code": code, "tables": [{"code": 21, "cells": []}]}
            for code in ("07", 0)
        ],
    }
    path = save_payload(tmp_path, json.dumps(payload))
    report = get_codal_report(path)
    assert report["Coverage"]["SheetOptions"] is None
    assert report["Coverage"]["SelectedSheetId"] is None
    assert report["Coverage"]["LoadedSheetIds"] == ["07", "0"]
    assert [(table["SheetId"], table["TableId"]) for table in get_codal_tables(report)] == [
        ("07", "21"), ("0", "21"),
    ]
    picked = get_codal_report(path, "07")
    assert picked["Coverage"]["LoadedSheetIds"] == ["07", "0"]
    assert [table["SheetId"] for table in get_codal_tables(picked)] == ["07"]
    assert get_codal_tables(picked)[0]["Cells"].empty
    with pytest.raises(ValueError, match="not loaded"):
        get_codal_report(path, 7)


@pytest.mark.parametrize(("expression", "message"), [
    ("null", "datasource object"),
    ('{"tables":[]}', "sheets array"),
    ('{"sheets":[{"tables":[]}]}', "position 0 code"),
    ('{"sheets":[{"code":0,"tables":[]}]}', "tables array"),
    ('{"sheets":[{"code":0,"tables":[{"code":9}]}]}', "cells array"),
    ('{"sheets":[{"code":0,"tables":[{"cells":[]}]}]}', "position 0 code"),
    ('{"sheets":[{"code":0,"tables":[{"code":9,"sheetCode":1,"cells":[]}]}]}', "sheetCode disagrees"),
    ('{"sheets":[{"code":0,"tables":[{"code":9,"cells":[{"rowSequence":1}]}]}]}', "columnSequence"),
    ('{"sheets":[{"code":0,"tables":[{"code":9,"cells":[]}]},{"code":"0","tables":[]}]}', "Duplicate loaded"),
    ('{"sheets": [}', "Malformed embedded"),
    ('{"sheets":[],"sheets":[]}', "duplicate JSON key"),
    ('{"sheets":[],"other":NaN}', "invalid JSON number"),
    ('{"sheets":[]} + anotherObject', "end with a JSON value"),
])
def test_rejects_malformed_or_unknown_datasource(tmp_path, expression, message):
    with pytest.raises(ValueError, match=message):
        get_codal_report(save_payload(tmp_path, expression))


@pytest.mark.parametrize("contents", [
    b"<html><table><tr><td>9</td></tr></table></html>",
    b"<html><!-- <script>\nvar datasource = {};\n</script> --></html>",
    b"<html><script src='https://example.invalid/data.js'></script></html>",
    b"%PDF-1.7",
])
def test_missing_embedded_data(tmp_path, contents):
    path = tmp_path / "report.html"
    path.write_bytes(contents)
    with pytest.raises(ValueError, match="one embedded CODAL datasource"):
        get_codal_report(path)


def test_conflicting_sheet_selection(tmp_path):
    menu = '<select id="ctl00_ddlTable"><option value="1" selected>Other</select>'
    payload = '{"sheets":[{"code":0,"tables":[{"code":9,"cells":[]}]}]}'
    with pytest.raises(ValueError, match="selected CODAL sheet disagrees"):
        get_codal_report(save_payload(tmp_path, payload, menu))
    with pytest.raises(ValueError, match="not loaded"):
        get_codal_report(FIXTURE, "1")
    with pytest.raises(ValueError, match="sheet_id"):
        get_codal_report(FIXTURE, False)


def test_local_path_failure_and_offline_execution(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Local CODAL parser tried to use the network")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    assert len(get_codal_tables(get_codal_report(FIXTURE))) == 2
    with pytest.raises(FileNotFoundError):
        get_codal_report(tmp_path / "missing.html")
    with pytest.raises(OSError):
        get_codal_report(tmp_path)
    invalid = tmp_path / "invalid.html"
    invalid.write_bytes(b"\xff\xff")
    with pytest.raises(ValueError, match="UTF-8"):
        get_codal_report(invalid)
    with pytest.raises(TypeError, match="get_codal_report"):
        get_codal_tables({})
