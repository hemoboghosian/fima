"""Fund output contracts use source-key meanings, not inferred magnitudes."""
import pandas as pd
import pytest

import fima.Funds as funds
from .test_funds_http import response


@pytest.mark.parametrize("provider,records", [
    ("rayan_hamafza", [{"jalaliDate": "1405/07/25", "purchaseNAVPerShare": 26820,
                        "sellNAVPerShare": 26797, "statisticalNAVPerShare": 27020,
                        "units": 104304884, "nav": 2795098878700}]),
    ("noavaran", [{"Date": "1405/07/25", "SubscriptionValue": 26820,
                   "RedemptionValue": 26797, "StatisticalValue": 27020,
                   "TotalQuantity": 104304884, "NetAssetValue": 2795098878700}]),
])
def test_per_unit_nav_is_not_multiplied_by_unit_count(monkeypatch, provider, records):
    monkeypatch.setattr(funds, "_get_fund_website_address", lambda _: "fund.example")
    method = "_get_rayan_hamafza_nav_records" if provider == "rayan_hamafza" else "_get_noavaran_nav_records"
    monkeypatch.setattr(funds, method, lambda *a: records)
    parsed = getattr(funds, "_get_daily_navs_" + provider)("A")
    result = funds._nav_frame(parsed)
    assert result.iloc[0].SubscriptionNAV == 26820
    assert result.iloc[0].RedemptionNAV == 26797
    assert result.iloc[0].StatisticalNAV == 27020
    assert result.iloc[0].TotalNAV == 2795098878700
    assert result.JalaliDate.tolist() == ["1405-07-25"]


def test_nika_statistical_nav_is_per_unit(monkeypatch):
    # Provider website labels nominalNAV as قیمت آماری and unit chart قیمت هر واحد.
    monkeypatch.setattr(funds, "_get_fund_website_address", lambda _: "fund.example")
    monkeypatch.setattr(funds, "_build_nika_nav_url", lambda **k: "https://fund.example/nav")
    item = dict(date="2026-10-17", issuanceNav=49376, redemptionNav=49019, nominalNAV=48992,
                totalUnit="2291513338", redemptionNetAssetValue=112328299492908)
    monkeypatch.setattr(funds, "_request", lambda *a, **k: response({"items": [item]}))
    result = funds._nav_frame(funds._get_daily_navs_nika("A"))
    assert result.iloc[0][["SubscriptionNAV", "RedemptionNAV", "StatisticalNAV"]].tolist() == [49376, 49019, 48992]
    assert result.iloc[0].TotalNAV == 112328299492908


def test_tsetmc_fund_name_group_dates_and_registration_are_semantic(monkeypatch):
    item = dict(regNo=11172.0, mfName="Actual Fund", name=None, fundType=0, fixIncome=7,
                recordDate="2026-10-17T00:00:00", initiationDate="2016-05-17T00:00:00",
                navSub="۱٬۲۳۴", navRed=1200, navStat=1199, netAsset=120000, units=100,
                portfolioFiveBest=22.18, portfolioDeposit=None, stats=None, fundProfits=[])
    monkeypatch.setattr(funds, "_request", lambda *a, **k: response({"funds": [item]}))
    result = funds.get_tsetmc_funds("mixed")
    assert result.iloc[0].FundName == "Actual Fund"
    assert result.iloc[0].RegistrationNumber == "11172"
    assert result.iloc[0].FundTypeID == "7"
    assert result.iloc[0].ProviderFundTypeCode == "0"
    assert str(result.UpdateGregorianDate.dtype) == "datetime64[ns]"
    assert result.iloc[0].SubscriptionNAV == 1234
    assert result.iloc[0].TopFiveStocksWeight == 22.18
    assert pd.isna(result.iloc[0].DepositWeight)


def test_allocation_numeric_missing_and_top_five_name():
    result = funds._allocation_frame(pd.DataFrame({"Date": ["۱۴۰۵/۷/۲۵"],
        "Upper5%Stocks": ["۱٬۰۰۰"], "Upper5%Stocks Weight": ["۲٫۵٪"],
        "Stocks": [0], "Stocks Weight": ["-"]}))
    assert result.JalaliDate.tolist() == ["1405-07-25"]
    assert result.iloc[0].TopFiveStocks == 1000
    assert result.iloc[0].TopFiveStocksWeight == 2.5
    assert result.iloc[0].Stocks == 0
    assert pd.isna(result.iloc[0].StocksWeight)


def test_catalog_preserves_ids_missing_zero_and_unknown_investment_type(monkeypatch):
    item = dict(name="Fund", regNo="0007", fundType=6, typeOfInvest="FutureProviderCategory",
                fundSize="۱٬۰۰۰", initiationDate=None, date="2026-10-17", dividendIntervalPeriod=0,
                investedUnits="100", insCode="000001", stock=None, cash=0)
    monkeypatch.setattr(funds, "_request", lambda *a, **k: response({"items": [item]}))
    monkeypatch.setattr(funds, "_get_fund_types", lambda: pd.DataFrame(
        [{"FundTypeID": 6, "FundTypeName": "Equity", "IsActive": True}]))
    result = funds.get_all_funds()
    assert result.iloc[0].RegistrationNumber == "0007"
    assert result.iloc[0].InstrumentCode == "000001"
    assert result.iloc[0].FundTypeID == "6"
    assert result.iloc[0].FundTypeName == "Equity"
    assert result.iloc[0].TotalNAV == 1000
    assert result.iloc[0].DividendFrequencyMonths == 0
    assert result.iloc[0].InvestmentType == "FutureProviderCategory"
    assert pd.isna(result.iloc[0].InceptionJalaliDate)
    assert result.iloc[0].CashWeight == 0
    assert pd.isna(result.iloc[0].StocksWeight)
    assert pd.isna(result.iloc[0].FundUnitsWeight)


def test_unknown_allocation_labels_remain_source_metadata():
    result = funds._allocation_frame(pd.DataFrame({"Date": ["1405/07/25"], "دارایی ناشناخته": [12],
                                                   "دارایی ناشناخته Weight": [3]}))
    assert result.columns.tolist() == ["JalaliDate", "ProviderAssets"]
    assert result.iloc[0].ProviderAssets == {"دارایی ناشناخته": {"Value": 12, "Weight": 3}}
