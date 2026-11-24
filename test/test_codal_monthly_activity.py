"""Offline normalization contracts for a synthetic manufacturing grid."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from fima import get_codal_monthly_activity, get_codal_report



CURRENT = "1404/07/30"
PREVIOUS = "1404/06/31"
PRIOR_YEAR = "1403/07/30"
FISCAL_END = "1404/12/29"
PRIOR_FISCAL_END = "1403/12/30"


@pytest.fixture
def payload():
    cells = []

    def add(row, column, value, *, height=1, width=1, date="", year="", kind=None):
        cells.append({
            "address": f"{chr(64 + column)}{row}",
            "rowSequence": row, "columnSequence": column, "value": value,
            "rowSpan": height, "colSpan": width, "isVisible": True,
            "cellGroupName": "Body" if kind else "Header", "rowTypeName": kind,
            "periodEndToDate": date, "yearEndToDate": year,
        })

    add(1, 1, "شرح", width=2)
    add(1, 26, "وضعیت محصول-واحد", height=2)
    add(2, 1, "نام محصول")
    add(2, 2, "واحد")
    metrics = ("تعداد توليد", "تعداد فروش", "نرخ فروش (ريال)", "مبلغ فروش (ميليون ريال)")
    period_columns = []
    for column, label, date, year in (
        (3, f"از ابتدای سال مالی تا تاریخ {PREVIOUS}", PREVIOUS, FISCAL_END),
        (7, "اصلاحات", "", ""),
        (10, f"از ابتدای سال مالی تا تاریخ {PREVIOUS} (اصلاح شده)", PREVIOUS, FISCAL_END),
        (14, f"دوره یک ماهه منتهی به {CURRENT}", CURRENT, FISCAL_END),
        (18, f"از ابتدای سال مالی تا تاریخ {CURRENT}", CURRENT, FISCAL_END),
        (22, f"از ابتدای سال مالی تا تاریخ {PRIOR_YEAR}", PRIOR_YEAR, PRIOR_FISCAL_END),
    ):
        headings = metrics if column != 7 else metrics[:2] + metrics[3:]
        add(1, column, label, width=len(headings), date=date)
        for position, heading in enumerate(headings, column):
            add(2, position, heading)
            period_columns.append((position, date, year))

    for row, (label, unit, kind, observations) in enumerate((
        ("فروش داخلی:", "", "FixedRow", {}),
        ("محصول الف ", "تن", "CustomRow", {
            3: "20", 7: "-3", 10: "17", 14: "3.125", 15: "0", 16: "12345678901234567890",
            17: "75", 18: "20.125", 22: "7",
        }),
        ("محصول الف ", "کيلوگرم", "CustomRow", {14: "100", 15: None}),
        ("", "", "NewRow", {16: "0", 17: "0"}),
        ("جمع فروش داخلی", "", "FixedRow", {14: "0", 17: "75"}),
        ("فروش صادراتی:", "", "FixedRow", {}),
        ("محصول الف ", "تن", "CustomRow", {14: "2", 15: "1", 16: "44000000", 17: "44"}),
        ("جمع فروش صادراتی", "", "FixedRow", {17: "44"}),
        ("درآمد ارائه خدمات:", "", "FixedRow", {}),
        ("جمع درآمد ارائه خدمات", "", "FixedRow", {17: "0"}),
        ("برگشت از فروش:", "", "FixedRow", {}),
        ("محصول الف ", "تن", "CustomRow", {15: "-0.010000000000000001", 17: "-4"}),
        ("جمع برگشت از فروش", "", "FixedRow", {17: "-4"}),
        ("تخفيفات", "", "FixedRow", {17: "-5"}),
        ("جمع", "", "FixedRow", {17: "110"}),
    ), start=3):
        add(row, 1, label, kind=kind)
        add(row, 2, unit, kind=kind)
        add(row, 26, "توليد" if kind == "CustomRow" else "", kind=kind)
        for column, date, year in period_columns:
            add(row, column, observations.get(column, ""), date=date, year=year, kind=kind)

    del next(cell for cell in cells if cell["address"] == "P5")["value"]
    return {
        "title_En": "Monthly Activity Product - V4", "type": 58, "period": 1,
        "tracingNo": 456789, "subject": None, "kind": 1, "isConsolidated": False,
        "periodEndToDate": CURRENT, "yearEndToDate": FISCAL_END,
        "sheets": [{"code": 1000000, "versionNo": "4", "aliasName": "MonthlyActivity",
                    "tables": [{"code": 1197, "versionNo": "4", "title_En": "Production and sales",
                                "cells": list(reversed(cells))}]}],
    }


def read_monthly(tmp_path, payload, v3=False):
    symbol = "ctl00_lblDisplaySymbol" if v3 else "ctl00_txbSymbol"
    page = f'<span id="{symbol}">نمونه</span><span id="ctl00_txbCompanyName">شرکت نمونه</span>'
    page += '<a id="ctl00_cphBody_ucNavigateToNextPrevLetter_hlPrevVersion" href="?LetterSerial=prev">قبلی</a>'
    path = tmp_path / "monthly.html"
    path.write_text(
        f"<html>{page}<script>\nvar datasource = {json.dumps(payload)};\n</script></html>",
        encoding="utf-8",
    )
    return get_codal_report(path)


@pytest.mark.parametrize("v3", [False, True])
def test_exact_observations_and_provenance(tmp_path, payload, v3):
    if v3:
        sheet = payload["sheets"][0]
        sheet["versionNo"] = "3"
        payload["title_En"] = "Monthly Activity Product - V3"
        for cell in sheet["tables"][0]["cells"]:
            if cell["cellGroupName"] == "Body":
                cell["rowSequence"] += 2
                cell["address"] = cell["address"][0] + str(cell["rowSequence"])
    report = read_monthly(tmp_path, payload, v3)
    activity = get_codal_monthly_activity(report)

    assert len(activity) == 10 * 23
    assert list(activity.iloc[:4].ColumnSequence) == [3, 4, 5, 6]
    assert all(dtype == object for dtype in activity.dtypes)
    assert set(activity.TracingNo) == {456789}
    assert set(activity.FilingKind) == {1}
    assert set(activity.Symbol) == {"نمونه"}
    assert set(activity.SubjectName) == {None}
    assert set(activity.ContentSha256) == {report["Source"]["ContentSha256"]}
    assert activity.attrs["PageMetadata"]["RevisionLinks"] == report["PageMetadata"]["RevisionLinks"]
    assert activity.attrs["ProviderMetadata"] == report["ProviderMetadata"]
    assert activity.attrs["Source"] == report["Source"]

    def obs(row, column):
        sequence = row + 2 if v3 else row
        return activity[(activity.RowSequence == sequence) & (activity.ColumnSequence == column)].iloc[0]

    production, quantity, rate, amount = [obs(4, c) for c in range(14, 18)]
    assert production.Value == Decimal("3.125")
    assert production.RawValue == "3.125"
    assert production.ProductName == "محصول الف "
    assert production.ProductStatus == "توليد"
    assert production.Unit == production.ProductUnit == "تن"
    assert (production.Address, production.SheetId, production.TableId) == (
        "N6" if v3 else "N4", "1000000", "1197"
    )
    assert quantity.Value == Decimal("0")
    assert (rate.Value, rate.Unit, rate.Scale) == (Decimal("12345678901234567890"), "IRR", 1)
    assert (amount.Value, amount.Unit, amount.Scale) == (Decimal("75"), "IRR", 1_000_000)
    assert obs(5, 14).ProductUnit == "کيلوگرم"
    assert (obs(5, 15).Value, obs(5, 15).RawValue, obs(5, 15).ValuePresent) == (None, None, True)
    assert (obs(5, 16).Value, obs(5, 16).RawValue, obs(5, 16).ValuePresent) == (None, None, False)
    assert (obs(5, 17).Value, obs(5, 17).RawValue, obs(5, 17).ValuePresent) == (None, "", True)
    assert obs(9, 14).MarketSegment == "Export"
    assert production.MarketSegment == "Domestic"
    assert (obs(7, 14).RowKind, obs(7, 14).Value, obs(7, 14).Unit) == ("Subtotal", Decimal("0"), None)
    assert obs(14, 15).Value == Decimal("-0.010000000000000001")
    assert obs(14, 15).ActivitySection == "SalesReturns"
    assert obs(17, 17).Value == Decimal("110")
    assert obs(17, 17).ProductName is None
    assert set(activity.PeriodBasis) == {
        "PreviousYTD", "Adjustment", "AdjustedYTD", "CurrentMonth", "CurrentYTD", "PriorYearYTD"
    }
    assert (obs(4, 7).Value, obs(4, 7).PeriodEndJalaliDate) == (Decimal("-3"), None)
    assert obs(4, 10).PeriodEndJalaliDate == PREVIOUS
    assert obs(4, 18).Value == Decimal("20.125")
    assert obs(4, 22).PeriodEndJalaliDate == PRIOR_YEAR
    assert obs(4, 22).FiscalYearEndJalaliDate == PRIOR_FISCAL_END
    assert obs(4, 22).ReportPeriodEndJalaliDate == CURRENT
    assert (8 if v3 else 6) not in set(activity.RowSequence)


@pytest.mark.parametrize(("address", "field", "value"), [
    ("Q2", "value", "مبلغ فروش (ریال)"),
    ("N1", "colSpan", 3),
    ("V1", "value", f"از ابتدای سال مالی تا تاریخ {CURRENT}"),
    ("Q4", "periodEndToDate", PREVIOUS),
    ("Q4", "value", "75,000"),
    ("Q4", "isVisible", False),
    ("A7", "value", "جمع ناشناخته"),
    ("Q6", "value", "9000"),
    ("B4", "value", ""),
])
def test_ambiguous_grid_raises(tmp_path, payload, address, field, value):
    cells = payload["sheets"][0]["tables"][0]["cells"]
    next(cell for cell in cells if cell["address"] == address)[field] = value
    with pytest.raises(ValueError, match="CODAL manufacturing"):
        get_codal_monthly_activity(read_monthly(tmp_path, payload))


def test_duplicate_and_missing_coordinates_raise(tmp_path, payload):
    cells = payload["sheets"][0]["tables"][0]["cells"]
    first = cells.pop(0)
    with pytest.raises(ValueError, match="CODAL manufacturing"):
        get_codal_monthly_activity(read_monthly(tmp_path, payload))
    cells.extend([first, first.copy()])
    with pytest.raises(ValueError, match="CODAL manufacturing"):
        get_codal_monthly_activity(read_monthly(tmp_path, payload))


def test_rejects_other_report_types_and_versions(tmp_path, payload):
    with pytest.raises(TypeError, match="get_codal_report"):
        get_codal_monthly_activity({})
    with pytest.raises(ValueError, match="CODAL manufacturing"):
        get_codal_monthly_activity(get_codal_report(Path(__file__).parent / "fixtures" / "codal_structured.html"))
    payload["sheets"][0]["tables"][0]["versionNo"] = "5"
    with pytest.raises(ValueError, match="CODAL manufacturing"):
        get_codal_monthly_activity(read_monthly(tmp_path, payload))
