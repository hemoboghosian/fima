"""Deterministic completeness contracts for the existing futures/export APIs."""
from copy import deepcopy
from types import SimpleNamespace

import pandas as pd
import pytest
import requests

import fima
import fima.IME as ime


def futures_row(code='ETCFA04', date='1404/01/26'):
    # Synthetic values in the official report schema; trade metrics may be absent.
    return dict(ContractDay=22, ContractCode=code, ContractDescription='Future',
                TradesVolume=453, TradesValue=218604100000, MaxPrice=496100,
                MinPrice=466400, LastPrice=473100, FirstPrice=496100,
                ChangeOpenInterest=0, ActiveBrokers=22, C_Buy=40, C_Sell=39,
                Vol_Hoghooghi_Sell=117, Val_Hoghooghi_Sell=56529000000,
                Vol_Haghighi_Buy=453, Val_Haghighi_Buy=218604100000,
                Vol_Haghighi_Sell=336, Val_Haghighi_Sell=162075100000,
                LastSettlementPrice=472500, TodaySettlementPrice=471772,
                SettlementPricePercent=-0.15, DT=date, DeliveryDate='1404/01/26',
                WeeklyOpenInterests=999, WeeklyOpenInterestsPercent=-14.62,
                MonthlyOpenInterests=1215, MonthlyOpenInterestsPercent=4.02,
                WeeklySettlementPrice=533475, WeeklySettlementPricePercent=-17.37,
                MonthlySettlementPrice=603447, MonthlySettlementPricePercent=1.55)


def export_row(identifier=1393500, date='1405/08/16'):
    return dict(cBrokerSpcName='Broker', ID=identifier, GoodsName='Product - صادراتی',
                Symbol='001', ProducerName='Producer', ContractType='Cash',
                DeliveryDate='1405/08/30', MinPrice=75166, Price=75166, MaxPrice=75166,
                arze=2000, BasePrice=75166, arzeMinPrice=75166, taghaza=2000,
                taghazaMaxPrice=75166, Quantity=2000, TotalPrice=150332000000,
                BasketDetail='0', GroupName='Group', SubGroupName='Subgroup',
                Warehouse='EXW', date=date, typeName='Industrial', TaghazaVoroudi=2000,
                ArzeBasePrice=75166, ArzehKonandeh='Supplier', bArzehRadifTarSarresid=None,
                xKala_xGrouhAsliKalaPK=1, xKala_xGrouhKalaPK=41,
                xKala_xZirGrouhKalaPK=170, xNamad_xTolidKonandehPK=5291,
                xRingPK=6, xRingName='Export hall', ModeDescription='Wholesale',
                MethodDescription='Normal', NerkhArz=None, Currency='Source currency',
                Unit='1000 kg', arzehPk='1355858', Talar='Export hall')


@pytest.fixture(params=['futures', 'export'])
def report(request):
    if request.param == 'futures':
        return ime.get_all_ime_futures_trades, futures_row, '1404-01-26', 'DT'
    return ime.get_all_ime_export_trades, export_row, '1405-08-16', 'date'


def serve(monkeypatch, responses):
    calls = []
    items = iter(responses)

    def get(url, **kwargs):
        calls.append((url, deepcopy(kwargs)))
        item = next(items)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: item)

    monkeypatch.setattr(ime.requests, 'get', get)
    return calls


def history(report, **kwargs):
    function, _, date, _ = report
    return function(start_date=date, end_date=date, **kwargs)


@pytest.mark.parametrize('failure', [requests.Timeout('timeout'), requests.HTTPError('500'),
                                   requests.exceptions.SSLError('TLS'), ValueError('invalid JSON'),
                                   {}, {'total': 1}])
def test_failed_later_window_cannot_return_partial_history(monkeypatch, report, failure):
    _, row, date, _ = report
    serve(monkeypatch, [dict(total=1, rows=[row()]), failure])
    end = str(ime.jd.date(*map(int, date.split('-'))) + ime.jd.timedelta(days=1))
    with pytest.raises(RuntimeError) as error:
        report[0](start_date=date, end_date=end, _chunk_size=0)
    assert error.value.__cause__ is not None


@pytest.mark.parametrize('envelope', [{}, {'total': 0}, {'total': True, 'rows': []},
    {'total': -1, 'rows': []}, {'total': 0, 'rows': None}, {'total': 1, 'rows': [None]}])
def test_malformed_envelope_is_not_valid_empty(monkeypatch, report, envelope):
    serve(monkeypatch, [envelope])
    with pytest.raises(RuntimeError):
        history(report)


def test_missing_page_is_rejected(monkeypatch, report):
    serve(monkeypatch, [dict(total=2, rows=[report[1]()]), dict(total=2, rows=[])])
    with pytest.raises(RuntimeError):
        history(report)


def test_duplicates_are_not_complete_history(monkeypatch, report):
    row = report[1]()
    serve(monkeypatch, [dict(total=2, rows=[row, row])])
    with pytest.raises(RuntimeError, match='duplicate'):
        history(report)


@pytest.mark.parametrize('defect', ['date', 'identity', 'field', 'number', 'delivery'])
def test_invalid_observation_fails_clearly(monkeypatch, report, defect):
    _, factory, _, date_field = report
    row = factory()
    if defect == 'date':
        row[date_field] = '1403/01/01'
    elif defect == 'identity':
        row['ContractCode' if date_field == 'DT' else 'ID'] = None
    elif defect == 'field':
        del row['DeliveryDate' if date_field == 'DT' else 'Price']
    elif defect == 'number':
        row['TradesValue' if date_field == 'DT' else 'TotalPrice'] = 'broken'
    else:
        row['DeliveryDate'] = 'invalid'
    serve(monkeypatch, [dict(total=1, rows=[row])])
    with pytest.raises(RuntimeError):
        history(report)


def test_empty_and_existing_reversed_range(monkeypatch, report):
    serve(monkeypatch, [dict(total=0, rows=[])])
    assert history(report).empty
    assert report[0](start_date='1405-08-17', end_date='1405-08-16') is None


def test_futures_pagination_and_source_financial_semantics(monkeypatch):
    row = futures_row('0001')
    other = futures_row('0002')
    calls = serve(monkeypatch, [dict(total=2, rows=[row]), dict(total=2, rows=[other])])
    frame = ime.get_all_ime_futures_trades(True, '1404-01-26', '1404-01-26', 100, 7, (2, 3))
    assert list(frame.ContractCode) == ['0001', '0002']
    assert [call[1]['params']['offset'] for call in calls] == [0, 1]
    assert all(call[1]['params']['c'] == -1 and call[1]['timeout'] == (2, 3) for call in calls)
    item = frame.iloc[0]
    assert item.TradeVolume == 453 and item.TradeValue == 218604100000
    assert item.OpeningPrice == 496100 and item.LastPrice == 473100
    assert item.LastSettlementPrice == 472500 and item.TodaySettlementPrice == 471772
    assert item.SettlementPricePercent == -0.15 and item.OpenInterestChange == 0
    assert item.RetailBuyVolume == 453 and item.InstitutionalSellValue == 56529000000
    assert item.JalaliDate == item.DeliveryJalaliDate == '1404-01-26'
    assert fima.get_all_ime_futures_trades is ime.get_all_ime_futures_trades


@pytest.mark.parametrize('page', [dict(total=3, rows=[futures_row('OTHER')]),
                                dict(total=2, rows=[futures_row()])])
def test_futures_changed_total_or_repeated_page(monkeypatch, page):
    serve(monkeypatch, [dict(total=2, rows=[futures_row()]), page])
    with pytest.raises(RuntimeError):
        ime.get_all_ime_futures_trades(start_date='1404-01-26', end_date='1404-01-26')


def test_futures_source_omissions_are_not_invented_zeros(monkeypatch):
    row = futures_row()
    for field in ['TradesVolume', 'TradesValue', 'FirstPrice', 'LastPrice', 'MaxPrice', 'MinPrice',
                  'WeeklyOpenInterests', 'MonthlyOpenInterests', 'ActiveBrokers', 'ContractDescription']:
        del row[field]
    serve(monkeypatch, [dict(total=1, rows=[row])])
    frame = ime.get_all_ime_futures_trades(start_date='1404-01-26', end_date='1404-01-26')
    assert 'TradeVolume' not in frame and 'OpeningPrice' not in frame
    assert frame.iloc[0].TodaySettlementPrice == 471772


def test_export_whole_report_preserves_currency_quantity_value_and_identifiers(monkeypatch):
    calls = serve(monkeypatch, [dict(total=1, rows=[export_row('00012')])])
    frame = ime.get_all_ime_export_trades('1405-08-16', '1405-08-16', 100, 4, (2, 3))
    item = frame.iloc[0]
    assert item.ID == '00012' and item.Symbol == '001'
    assert item.GoodsName == 'Product' and item.ProducerName == 'Producer'
    assert item.TradeVolume == 2000 and item.TradeValue == 150332000000
    assert item.ClosingPrice == 75166 and item.SupplyBasePrice == 75166
    assert item.Unit == '1000 kg' and item.Currency == 'Source currency' and pd.isna(item.FXRate)
    assert item.JalaliDate == '1405-08-16' and item.DeliveryJalaliDate == '1405-08-30'
    assert calls[0][1]['timeout'] == (2, 3)
    assert not {'limit', 'offset'} & calls[0][1]['params'].keys()
    assert fima.get_all_ime_export_trades is ime.get_all_ime_export_trades


def test_export_null_prices_and_zero_quantities_remain_distinct(monkeypatch):
    row = export_row()
    row.update(Price=None, MinPrice=None, Quantity=0, TotalPrice=0)
    serve(monkeypatch, [dict(total=1, rows=[row])])
    item = ime.get_all_ime_export_trades(start_date='1405-08-16', end_date='1405-08-16').iloc[0]
    assert pd.isna(item.ClosingPrice) and pd.isna(item.LowPrice)
    assert item.TradeVolume == 0 and item.TradeValue == 0


@pytest.mark.parametrize('chunk_size', [-1, 1.5, True])
def test_invalid_window_size_fails_without_network(monkeypatch, report, chunk_size):
    calls = serve(monkeypatch, [])
    with pytest.raises(ValueError):
        history(report, _chunk_size=chunk_size)
    assert not calls
