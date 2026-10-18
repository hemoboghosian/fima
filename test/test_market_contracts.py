"""Deterministic contracts for older market adapters and cross-module types."""
from types import SimpleNamespace

import pandas as pd
import pytest

import fima.IME as ime
import fima.IFB as ifb
import fima.TSEInstitutions as institutions


def physical_record():
    # Named fields from the current official physical report, deliberately reordered.
    return dict(reversed(list(dict(GoodsName="Product", Symbol="001", ProducerName="Producer",
        ContractType="Cash", MinPrice="۱٬۰۰۰", Price=1200, MaxPrice=1300, arze=80,
        ArzeBasePrice=900, arzeMinPrice=900, taghaza=90, taghazaMaxPrice=1300,
        Quantity=75, TotalPrice=90000, date="1405/07/20", DeliveryDate="1405/07/22",
        Warehouse="Warehouse", ArzehKonandeh="Supplier", SettlementDate=None,
        cBrokerSpcName="Broker", ModeDescription="Wholesale", MethodDescription="Normal",
        Currency="IRR", Unit="ton", Talar="Hall", PacketName="Bag", Tasvieh="Cash").items())))


def test_physical_keys_volume_value_prices_and_dates():
    result = ime._clean_ime_physical_records([physical_record()])
    assert result.iloc[0].TradeVolume == 75
    assert result.iloc[0].TradeValue == 90000
    assert result.iloc[0].ClosingPrice == 1200
    assert result.iloc[0].LowPrice == 1000
    assert result.iloc[0].HighPrice == 1300
    assert result.iloc[0].JalaliDate == "1405-07-20"
    assert result.iloc[0].DeliveryJalaliDate == "1405-07-22"
    assert pd.isna(result.iloc[0].SettlementJalaliDate)
    assert result.iloc[0].Unit == "ton"
    assert result.iloc[0].Symbol == "001"


def test_ime_option_timestamp_and_numeric_ids(monkeypatch):
    row = dict(id="00012", DT="1405/07/20", DT_en="2026-10-12", DeliveryDate="1405/08/01",
               CreateDateTime="2026-10-12T09:30:45", TradesVolume="۱٬۲۳۴", TradesValue="12,340",
               MaxPrice="12", MinPrice=0, LastPrice=10, FirstPrice=9, IsActive=True)
    monkeypatch.setattr(ime.requests, "get", lambda *a, **k: SimpleNamespace(
        json=lambda: {"rows": [row]}, raise_for_status=lambda: None))
    result = ime.get_all_ime_option_trades(start_date="1405-07-20", end_date="1405-07-20")
    assert result.iloc[0].CreateDateTime == pd.Timestamp("2026-10-12T09:30:45")
    assert str(result.CreateDateTime.dtype) == "datetime64[ns]"
    assert str(result.GregorianDate.dtype) == "datetime64[ns]"
    assert result.iloc[0].ID == "00012"
    assert result.iloc[0].TradeVolume == 1234
    assert result.iloc[0].TradeValue == 12340
    assert result.iloc[0].LowPrice == 0


@pytest.mark.parametrize("function", [ifb.get_ifb_equally_weighted_total_index_historical_data,
    ifb.get_ifb_equally_weighted_price_index_historical_data, ifb.get_ifb_price_index_historical_data,
    ifb.get_ifb_total_index_historical_data, ifb.get_ifb_total_sukuk_index_historical_data])
def test_ifb_indexes_share_date_and_level_contract(monkeypatch, function):
    values = [[pd.Timestamp("2026-10-17").timestamp() * 1000, "1,234"]]
    payload = [values] if function is ifb.get_ifb_total_sukuk_index_historical_data else values
    monkeypatch.setattr(ifb.requests, "post", lambda *a, **k: SimpleNamespace(json=lambda: {"d": payload}))
    result = function()
    assert result.iloc[0].IndexValue == 1234
    assert result.iloc[0].JalaliDate == "1405-07-25"
    assert str(result.GregorianDate.dtype) == "datetime64[ns]"


def test_ifb_risk_free_scalar_retains_decimal_units(monkeypatch):
    monkeypatch.setattr(ifb, "get_all_bonds_without_coupons", lambda **k: pd.DataFrame({
        "Ticker": ["اخزا1", "اخزا2", "Other"], "LastTradeJalaliDate": ["1405-07-24", "1405-07-25", "1405-07-25"],
        "YTM": [25, 30, 90]}))
    assert ifb.get_risk_free_rate() == .30


def test_institution_ids_are_text_and_names_are_specific(monkeypatch):
    row = dict(InstituteTypeId=1, InstituteKindId=2, StateId=3, Id=4, InquiryStatus=0,
               Name="Institution", NationalId="001234", SEORegisterNo=123.0,
               CEOMobileNo="09120000000", InstituteKind="Kind")
    monkeypatch.setattr(institutions.requests, "get", lambda *a, **k: SimpleNamespace(
        json=lambda: {"data": [row]}, raise_for_status=lambda: None))
    result = institutions.get_all_institutions()
    assert result.iloc[0].InstitutionName == "Institution"
    assert result.iloc[0].NationalID == "001234"
    assert result.iloc[0].SEORegisterNo == "123"
    assert result.iloc[0].CEOMobileNo == "09120000000"


def test_ime_cd_count_volume_value_and_closing_last_are_distinct(monkeypatch):
    row = dict(id=12, Namad="0001", LVal18AFC="Ticker", DT="1405/07/20", DT_En="2026-10-12",
               NamadDescription="Instrument", PClosing=100, PDrCotVal=110, ZTotTran=7,
               QTotTran5J="۱٬۲۳۴", QTotCap="123,400", PriceMin=90, PriceMax=120,
               PriceYesterday=98, LastTradeChangePrice=12, LastTradeChangePricePercent=2.5,
               LastPriceChangePrice=2, LastPriceChangePricePercent=1.2)
    monkeypatch.setattr(ime.requests, "get", lambda *a, **k: SimpleNamespace(
        json=lambda: {"rows": [row]}, raise_for_status=lambda: None))
    result = ime.get_all_ime_cd_trades(start_date="1405-07-20", end_date="1405-07-20")
    assert result.iloc[0][["ClosingPrice", "LastPrice", "TransactionCount", "TradeVolume", "TradeValue"]].tolist() == [100, 110, 7, 1234, 123400]
    assert result.iloc[0].Code == "0001"
    assert result.iloc[0].LastPricePercentageChange == 2.5
    assert result.iloc[0].ClosingPricePercentageChange == 1.2


def test_producer_filters_consume_canonical_jalali_strings():
    data = pd.DataFrame({"ProducerName": ["A", "A", "B"], "GoodsName": ["X", "Y", "Z"],
                         "JalaliDate": ["1405-07-20", "1405-07-21", "1405-07-20"]})
    result = ime.get_producer_physical_trades("A", start_date="1405-07-21", all_ime_physical_trades=data)
    assert result.GoodsName.tolist() == ["Y"]
    products = ime.get_all_physical_producer_products(all_ime_physical_trades=data)
    assert products.columns.tolist() == ["ProducerName", "Products"]
    assert products.iloc[0].Products == ["X", "Y"]


@pytest.mark.parametrize("coupons", [False, True])
def test_ifb_bond_public_yields_are_percent_points(monkeypatch, coupons):
    table_id = "ContentPlaceHolder1_grdytm" if coupons else "ContentPlaceHolder1_grdytmforkhazaneh"
    table_class = "mGrid" if coupons else "KhazanehGrid"
    headers = ["Index", "Ticker", "Price", "LastDate", "Maturity", "YTM"] + ([] if coupons else ["SimpleReturn"])
    values = ["1", "اخزا1", "1,234", "1405/07/25", "1406/07/25", "۳۰٫۵٪"] + ([] if coupons else ["2/5%"])
    html = f'<table id="{table_id}" class="{table_class}"><tr>' + ''.join(f'<th>{x}</th>' for x in headers) + '</tr><tr>' + ''.join(f'<td>{x}</td>' for x in values) + '</tr></table>'
    monkeypatch.setattr(ifb.requests.Session, "get", lambda *a, **k: SimpleNamespace(status_code=200, content=html.encode()))
    result = (ifb.get_all_bonds_with_coupons if coupons else ifb.get_all_bonds_without_coupons)()
    assert result.iloc[0].YTM == 30.5
    assert result.iloc[0].LastPrice == 1234
    assert result.iloc[0].LastTradeJalaliDate == "1405-07-25"
    assert result.iloc[0].MaturityJalaliDate == "1406-07-25"
    if not coupons:
        assert result.iloc[0].SimpleReturn == 2.5


def test_missing_boolean_flags_are_not_truthy_strings():
    from fima._data import boolean_series
    result = boolean_series(pd.Series([True, "true", "false", 0, 1, None]))
    assert result.iloc[:5].tolist() == [True, True, False, False, True]
    assert pd.isna(result.iloc[5])
    assert not boolean_series(pd.Series([0, None])).iloc[0]
    from fima._data import identifier_series
    assert identifier_series(pd.Series(["001.0"])).iloc[0] == "001.0"
    with pytest.raises(ValueError):
        boolean_series(pd.Series(["not-a-flag"]))


def test_valid_empty_gold_history_is_an_empty_typed_table(monkeypatch):
    monkeypatch.setattr(ime.requests, "post", lambda *a, **k: SimpleNamespace(
        status_code=200, json=lambda: {"Data": [], "HasNextPage": False}))
    result = ime.get_gold_and_silver_cd_trades("gold_bar_cd", "1405-07-20", "1405-07-21")
    assert result.empty
    assert str(result.GregorianDate.dtype) == "datetime64[ns]"
    assert {"JalaliDate", "TradeVolume", "TradeValue"}.issubset(result.columns)
