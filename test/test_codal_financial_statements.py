"""Synthetic grids for the verified offline CODAL statement contract."""

from copy import deepcopy
from decimal import Decimal
import json

import pytest

from fima import get_codal_financial_statements, get_codal_report, get_codal_tables


_LAYOUTS = {
    "0": (
        899, "5", "Balance Sheet", "BalanceSheet", "1",
        (2, 12, 17, 15, 16, 14, 13, 45, 18, 19, 3, 9, 8, 44, 5, 4, 34, 10, 11, 33, 35,
         36, 21, 22, 23, 37, 25, 26, 28, 38, 31, 24, 39, 40, 13, 14, 16, 46, 17, 18, 3, 41,
         6, 7, 8, 9, 10, 42, 11, 12, 19, 43),
        {3: "دارايي‌ها", 4: "دارايي‌هاي غيرجاري", 13: "دارايي‌هاي جاري",
         23: "حقوق مالکانه و بدهي‌ها", 24: "حقوق مالکانه", 36: "بدهي‌ها",
         37: "بدهي‌هاي غيرجاري", 43: "بدهي‌هاي جاري"},
        {19: "", 50: ""}, None,
    ),
    "1": (
        904, "7", "Income Statement", "IncomeStatement", "0",
        (49, 3, 4, 5, 6, 44, 7, 8, 9, 10, 52, 13, 50, 45, 46, 15, 51, 21, 17, 18,
         19, 20, 47, 48, 21, 41, 42, 43),
        {3: "عمليات در حال تداوم:", 15: "هزينه ماليات بر درآمد:", 19: "عمليات متوقف شده:",
         22: "سود(زيان) پايه هر سهم:"},
        {23: "عملياتي (ريال)", 24: "غيرعملياتي (ريال)", 25: "ناشي از عمليات در حال تداوم",
         26: "ناشي از عمليات متوقف شده", 27: "سود(زيان) پايه هر سهم",
         28: "سود (زيان) خالص هر سهم – ريال", 29: "سرمايه", 30: "1000"}, 941,
    ),
    "9": (
        906, "4", "Cash Flow", "CashFlow", "1",
        (2, 56, 13, 5, 0, 15, 16, 41, 17, 18, 19, 22, 25, 26, 23, 24, 20, 21, 42, 7, 9,
         27, 28, 29, 30, 31, 43, 32, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 35,
         36, 37, 38, 39, 40),
        {3: "جريان\u00adهاي نقدي حاصل از فعاليت‌هاي عملياتي:",
         7: "جريان\u00adهاي نقدي حاصل از فعاليت‌هاي سرمايه‌گذاري:",
         26: "جريان\u00adهاي نقدي حاصل از فعاليت‌هاي تامين مالي:"},
        {45: "مانده موجودي نقد در ابتداي سال", 47: "مانده موجودي نقد در پايان سال",
         48: "معاملات غيرنقدي"}, 909,
    ),
}
_AMOUNTS = {
    "0": {12: "59", 19: "17", 21: "17", 22: "76", 35: "50", 42: "16",
          50: "10", 52: "10", 53: "26", 54: "76"},
    "1": {4: "12.125", 5: "-2.125", 6: "10", 7: "-1", 11: "9", 12: "-2",
          14: "7", 16: "-1", 18: "6", 20: "-2", 21: "4", 27: "274", 28: "275", 29: "100"},
    "9": {4: "20", 5: "-2", 6: "18", 8: "-3", 24: "-3", 25: "15", 27: "4",
          43: "4", 44: "19", 45: "10", 46: "1", 47: "30", 48: "13"},
}


def _sheet(sheet_id, current, period):
    code, version, title, alias, sheet_version, row_codes, sections, labels, auxiliary = _LAYOUTS[sheet_id]
    balance = sheet_id == "0"
    visible = {1, 2, 3, 4, 5} if period == 6 else {1, 2, 4, 6}
    if balance:
        visible.add(3)
    prior_close = "1403/09/30"
    dates = {2: current, 3: prior_close if balance or period == 12 else "1403/03/31",
             4: "1402/10/01" if balance else prior_close}
    fiscal = {2: "1404/09/30", 3: prior_close, 4: prior_close}
    titles = {1: "شرح", 5: "درصد تغيير", 6: "درصد تغيير"}
    date_label = "به تاريخ" if balance else "دوره منتهي به"
    for col, date in dates.items():
        restated = "تجديد ارائه شده " if col != 2 else ""
        titles[col] = f"{restated}{date_label} {date}"
    column_codes = (1, 2, 3, 4, 5, 6) if balance else (1, 2, 3, 5, 4, 6)
    cells = []
    for row in range(1, len(row_codes) + 3):
        for col in range(1, 7):
            if row == 2 and col not in dates:
                continue
            audited = col != 2 or period == 12
            shown = col in visible and not (sheet_id == "1" and row == 30)
            if row == 1:
                value = titles[col]
            elif row == 2:
                value = ("حسابرسی شده" if audited else "حسابرسی نشده") if shown else ""
            elif col == 1:
                value = sections.get(row, labels.get(row, f"حساب {row}"))
            elif row in sections or row == 30 and sheet_id == "1":
                value = ""
            elif col >= 5:
                value = "--" if row == 4 else "0"
            else:
                value = _AMOUNTS[sheet_id].get(row, "0")
            cells.append({
                "address": f"{chr(64 + col)}{row}",
                "rowSequence": row, "columnSequence": col, "columnCode": column_codes[col - 1],
                "rowCode": row_codes[row - 3] if row >= 3 else row - 1,
                "cellGroupName": "Body" if row > 2 else "Header", "rowTypeName": "FixedRow",
                "rowSpan": 2 if row == 1 and col in (1, 5, 6) else 1, "colSpan": 1,
                "isVisible": shown, "value": value, "isAudited": row == 2 and shown and audited,
                "periodEndToDate": dates.get(col, ""), "yearEndToDate": fiscal.get(col, ""),
            })
    tables = [{
        "code": code, "versionNo": version, "title_En": title, "aliasName": alias,
        "description": "کليه مبالغ به ميليون ريال است", "cells": cells,
    }]
    if auxiliary is not None:
        tables.append({"code": auxiliary, "cells": []})
    return {"code": int(sheet_id), "versionNo": sheet_version, "title_En": title,
            "aliasName": alias, "tables": tables}


def _payload(period=6, sheets=("1",)):
    end = "1404/03/31" if period == 6 else "1404/09/30"
    template = ("FinancialStatement-Registered-Product-V5" if period == 6 else
                "Financial Statement - Product - Other - Child Companies - V2")
    return {
        "title_En": template, "type": 6, "tracingNo": 1010123, "kind": 0, "period": period,
        "periodExtraDay": 0, "subject": "شرکت موضوع گزارش", "isConsolidated": False,
        "periodEndToDate": end, "yearEndToDate": "1404/09/30", "isAudited": period == 12,
        "sheets": [_sheet(sheet_id, end, period) for sheet_id in sheets],
    }


def _report(tmp_path, payload, sheet_id=None):
    audit = "حسابرسی شده" if payload["isAudited"] else "حسابرسی نشده"
    path = tmp_path / "statement.html"
    path.write_text(
        f'<span id="ctl00_txbCompanyName">شرکت نمونه</span>'
        f'<span id="ctl00_txbSymbol">نمونه</span>'
        f'<span id="ctl00_lblPeriodEndToDate">{payload["periodEndToDate"]}</span>'
        f'<span id="ctl00_lblYearEndToDate">{payload["yearEndToDate"]}</span>'
        f'<span id="ctl00_lblIsAudited">({audit})</span>'
        f'<span id="ctl00_pPriceNote">کلیه مبالغ درج شده به میلیون ریال می باشد</span>'
        f'<a id="ctl00_cphBody_ucNavigateToNextPrevLetter_hlPrevVersion" href="?LetterSerial=prior">اصل</a>'
        f'<script>var datasource = {json.dumps(payload)};</script>',
        encoding="utf-8",
    )
    return get_codal_report(path, sheet_id=sheet_id)


def _cell(payload, address):
    return next(cell for cell in payload["sheets"][0]["tables"][0]["cells"] if cell["address"] == address)


def test_interim_income_preserves_dates_assurance_units_and_exact_values(tmp_path):
    report = _report(tmp_path, _payload())
    result = get_codal_financial_statements(report)
    rows = result.set_index("Address")
    assert len(rows) == 92
    assert all(dtype == object for dtype in result.dtypes)
    assert rows.loc["B5", [
        "TracingNo", "CompanyName", "SubjectName", "Symbol", "FilingKind", "StatementType", "Scope",
        "Value", "RawValue", "ValuePresent", "Currency", "Unit", "Scale",
        "PeriodBasis", "ColumnEndJalaliDate", "FiscalYearEndJalaliDate", "AsOfJalaliDate",
        "DurationMonths", "IsRestated", "FilingIsAudited", "ColumnIsAudited",
        "SheetId", "TableId", "RowSequence", "ColumnSequence",
    ]].tolist() == [
        1010123, "شرکت نمونه", "شرکت موضوع گزارش", "نمونه", 0, "IncomeStatement", "Separate",
        Decimal("-2.125"), "-2.125", True, "IRR", "IRR", 1_000_000,
        "Current", "1404/03/31", "1404/09/30", None, 6, False, False, False, "1", "904", 5, 2,
    ]
    assert rows.loc["C5", ["PeriodBasis", "DurationMonths", "ColumnEndJalaliDate",
                           "IsRestated", "FilingIsAudited", "ColumnIsAudited"]].tolist() == [
        "ComparativeInterim", 6, "1403/03/31", True, False, True,
    ]
    assert rows.loc["D5", ["PeriodBasis", "DurationMonths", "ColumnEndJalaliDate"]].tolist() == [
        "PriorFiscalYear", 12, "1403/09/30",
    ]
    assert rows.loc["B27", ["Measurement", "Value", "Unit", "Scale"]].tolist() == [
        "BasicEPS", Decimal(274), "IRR/Share", 1,
    ]
    assert rows.loc["B28", ["Measurement", "Value", "Unit", "Scale", "AccountLabel"]].tolist() == [
        "NetProfitPerShare", Decimal(275), "IRR/Share", 1, "سود (زيان) خالص هر سهم – ريال",
    ]
    assert rows.loc["E4", ["PeriodBasis", "Value", "RawValue", "ValuePresent", "Unit", "Currency",
                          "DurationMonths", "ColumnEndJalaliDate", "ColumnIsAudited"]].tolist() == [
        "ReportedChange", None, "--", True, "Percent", None, None, None, None,
    ]
    raw_cells = get_codal_tables(report)[0]["Cells"]
    assert rows.loc["B5", "CellOrder"] == raw_cells.loc[raw_cells.Address.eq("B5"), "CellOrder"].item()
    assert set(result["ContentSha256"]) == {report["Source"]["ContentSha256"]}
    assert result.attrs["PageMetadata"]["RevisionLinks"][0]["Href"] == "?LetterSerial=prior"
    assert result.attrs["PageMetadata"] is not report["PageMetadata"]
    assert len(result.attrs["Reconciliations"]) == 15
    assert {check["Status"] for check in result.attrs["Reconciliations"]} == {"Passed"}


def test_annual_loaded_sheets_and_positions_are_distinct_from_flows(tmp_path):
    payload = _payload(12, ("9", "0", "1"))
    result = get_codal_financial_statements(_report(tmp_path, payload))
    assert list(result["SheetId"].unique()) == ["9", "0", "1"]
    assert result.groupby("SheetId").size().to_dict() == {"0": 176, "1": 69, "9": 129}
    rows = result.set_index(["SheetId", "Address"])
    assert rows.loc[("0", "D22"), ["Measurement", "AsOfJalaliDate", "DurationMonths", "PeriodBasis"]].tolist() == [
        "Stock", "1402/10/01", None, "PriorFiscalYearOpening",
    ]
    assert rows.loc[("0", "C22"), "PeriodBasis"] == "PriorFiscalYearEnd"
    assert rows.loc[("0", "B19"), ["AccountLabel", "Value"]].tolist() == ["", Decimal(17)]
    assert rows.loc[("9", "B45"), ["Measurement", "AsOfJalaliDate", "DurationMonths"]].tolist() == [
        "OpeningCash", None, None,
    ]
    assert rows.loc[("9", "B47"), ["Measurement", "AsOfJalaliDate", "Value"]].tolist() == [
        "ClosingCash", "1404/09/30", Decimal(30),
    ]
    assert rows.loc[("9", "B48"), "Measurement"] == "NonCashTransactions"
    assert rows.loc[("1", "B21"), "DurationMonths"] == 12
    assert rows.loc[("1", "D21"), "PeriodBasis"] == "PriorFiscalYear"
    assert rows.loc[("1", "F21"), "PeriodBasis"] == "ReportedChange"
    assert ("1", "C21") not in rows.index
    assert ("1", "E21") not in rows.index
    assert ("1", "B30") not in rows.index
    assert {check["Status"] for check in result.attrs["Reconciliations"]} == {"Passed"}
    selected = get_codal_financial_statements(_report(tmp_path, payload, sheet_id=0))
    assert set(selected["SheetId"]) == {"0"}
    assert selected.attrs["Coverage"]["RequestedSheetId"] == "0"


def test_blank_missing_and_reported_zero_survive(tmp_path):
    payload = _payload()
    _cell(payload, "B8")["value"] = ""
    _cell(payload, "C8")["value"] = None
    del _cell(payload, "D8")["value"]
    result = get_codal_financial_statements(_report(tmp_path, payload))
    rows = result.set_index("Address")
    cols = ["RawValue", "Value", "ValuePresent"]
    assert rows.loc["B8", cols].tolist() == ["", None, True]
    assert rows.loc["C8", cols].tolist() == [None, None, True]
    assert rows.loc["D8", cols].tolist() == [None, None, False]
    assert rows.loc["B9", cols].tolist() == ["0", Decimal(0), True]
    assert [check["Address"] for check in result.attrs["Reconciliations"] if check["Status"] == "Missing"] == [
        "B11", "C11", "D11",
    ]


@pytest.mark.parametrize(("sheet_id", "address"), [("0", "B54"), ("1", "B6"), ("9", "B47")])
def test_accounting_disagreement_fails_and_raw_value_is_available(tmp_path, sheet_id, address):
    payload = _payload(sheets=(sheet_id,))
    _cell(payload, address)["value"] = "123456"
    report = _report(tmp_path, payload)
    with pytest.raises(ValueError, match=f"reconciliation failed at {address}"):
        get_codal_financial_statements(report)
    raw = get_codal_tables(report)[0]["Cells"].set_index("Address")
    assert raw.loc[address, "Value"] == "123456"


@pytest.mark.parametrize(("address", "field", "value", "message"), [
    ("B27", "isVisible", False, "visibility"),
    ("B5", "rowCode", 0, "body cell"),
    ("B5", "periodEndToDate", "1404/03/30", "inconsistent dates"),
    ("B1", "value", "دوره منتهي به 1404/03/30", "period or assurance"),
    ("B2", "isAudited", True, "period or assurance"),
    ("B5", "value", "--", "unrecognized value"),
    ("A27", "value", "سود تقلیل یافته هر سهم", "account heading"),
    ("A28", "value", "سود سهام", "account heading"),
])
def test_unverified_grid_fails(tmp_path, address, field, value, message):
    payload = _payload()
    _cell(payload, address)[field] = value
    with pytest.raises(ValueError, match=message):
        get_codal_financial_statements(_report(tmp_path, payload))


def test_unsupported_filing_table_units_and_selected_sheet(tmp_path):
    with pytest.raises(TypeError, match="get_codal_report"):
        get_codal_financial_statements(None)
    for patch in ({"title_En": "Financial Statement"}, {"isConsolidated": True}, {"period": 3}):
        with pytest.raises(ValueError, match="verified separate production filing"):
            get_codal_financial_statements(_report(tmp_path, {**_payload(), **patch}))
    payload = _payload()
    original = payload["sheets"][0]["tables"][0]
    changed = deepcopy(payload)
    changed["sheets"][0]["tables"][0]["versionNo"] = "8"
    with pytest.raises(ValueError, match="unverified layout"):
        get_codal_financial_statements(_report(tmp_path, changed))
    original["description"] = "کليه مبالغ به هزار ريال است"
    with pytest.raises(ValueError, match="unverified monetary units"):
        get_codal_financial_statements(_report(tmp_path, payload))
    payload = _payload()
    payload["sheets"].append({"code": 2, "tables": [{"code": 7, "cells": []}]})
    with pytest.raises(ValueError, match="no supported loaded or requested"):
        get_codal_financial_statements(_report(tmp_path, payload, sheet_id=2))
