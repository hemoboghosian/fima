"""Opt-in smoke tests against CODAL's public HTTPS service."""

from decimal import Decimal

import pytest

from fima import get_codal_data, search_codal_filings

pytestmark = pytest.mark.integration


def test_foolad_monthly_correction():
    result = get_codal_data("فولاد", "گزارش عملکرد ماهانه", period="1405/06")
    assert result.attrs["RevisionTracingNos"] == [1605314, 1618061]
    assert set(result.TracingNo) == {1618061}
    assert set(result.Symbol) == {"فولاد"}
    assert set(result.ReportPeriodEndJalaliDate) == {"1405/06/31"}
    assert len(result) == 460
    totals = result.set_index("Address")
    monthly, ytd = totals.loc["Q30"], totals.loc["U30"]
    assert (monthly.Value, monthly.PeriodBasis, monthly.Unit, monthly.Scale) == (
        Decimal("639418160"), "CurrentMonth", "IRR", 1_000_000,
    )
    assert (ytd.Value, ytd.PeriodBasis) == (Decimal("2509422184"), "CurrentYTD")
    assert all(isinstance(value, Decimal) for value in result.Value if value is not None)


def test_bemepna_income_sheet():
    result = get_codal_data("بمپنا", "صورت‌های مالی", period="1402/06", statement="سود و زیان", audited=True)
    assert len(result) == 92
    assert set(result.TracingNo) == {1106536}
    assert set(result.StatementType) == {"IncomeStatement"}
    assert set(result.Scope) == {"Separate"}
    assert result.loc[result.Address.eq("B5"), "Value"].item() == Decimal("-2402795")
    assert len(result.attrs["Reconciliations"]) == 15


def test_bemepna_cash_flow_sheet():
    result = get_codal_data("بمپنا", "صورت جریان وجوه نقد", period="1402/06", audited=True)
    assert set(result.TracingNo) == {1106536}
    assert set(result.StatementType) == {"CashFlow"}
    assert result.attrs["Coverage"]["SelectedSheetId"] == result.attrs["Coverage"]["RequestedSheetId"]
    current = result.loc[result.Measurement.eq("ClosingCash") & result.PeriodBasis.eq("Current")]
    assert current.Value.item() == Decimal("181717")


def test_folazh_corrections_and_raw_financial_template():
    monthly = get_codal_data("فولاژ", "گزارش ماهانه", period="شهریور ۱۴۰۵")
    assert monthly.attrs["RevisionTracingNos"] == [1602474, 1615157]
    raw = get_codal_data("فولاژ", "صورت سود و زیان", period="۱۴۰۵/۰۶", audited=False, raw=True)
    assert raw.attrs["RevisionTracingNos"] == [1609270, 1619870]
    assert raw.attrs["Filing"]["TracingNo"] == 1619870
    assert raw.attrs["ProviderMetadata"]["title_En"].endswith("V9")
    assert len(raw) > 0


def test_monthly_search_across_pages():
    filings = search_codal_filings("فولاد", "گزارش فعالیت ماهانه")
    assert len(filings) > 20
    assert filings.TracingNo.is_unique
    assert {1605314, 1618061} <= set(filings.TracingNo)
