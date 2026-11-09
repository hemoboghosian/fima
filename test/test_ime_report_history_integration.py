"""Opt-in comparisons against the two established official IME report consumers."""
import pandas as pd
import pytest
import requests

import fima.IME as ime


pytestmark = pytest.mark.integration


def test_live_futures_complete_pages_and_native_financial_fields(monkeypatch):
    url = 'https://www.ime.co.ir/subsystems/ime/futurereports/FutureAmareMoamelatHnadler.ashx'
    get = requests.get
    response = get(url, params=dict(f='1404/01/01', t='1404/02/01', c=0, lang=8, order='asc'),
                   timeout=(10, 45))
    response.raise_for_status()
    raw = response.json()
    assert len(raw['rows']) == raw['total'] > 200
    offsets = []

    def small_pages(url, **kwargs):
        kwargs['params'] = dict(kwargs['params'], limit=200)
        offsets.append(kwargs['params']['offset'])
        return get(url, **kwargs)

    monkeypatch.setattr(ime.requests, 'get', small_pages)
    frame = ime.get_all_ime_futures_trades(start_date='1404-01-01', end_date='1404-02-01')
    source = {(r['ContractCode'], r['DT'].replace('/', '-')): r for r in raw['rows']}
    assert len(offsets) > 1 and len(frame) == len(source) == raw['total']
    assert set(zip(frame.ContractCode, frame.JalaliDate)) == set(source)
    for row in frame.itertuples():
        original = source[row.ContractCode, row.JalaliDate]
        for public, native in [('TradeVolume', 'TradesVolume'), ('TradeValue', 'TradesValue'),
            ('OpeningPrice', 'FirstPrice'), ('LastPrice', 'LastPrice'), ('HighPrice', 'MaxPrice'),
            ('LowPrice', 'MinPrice'), ('TodaySettlementPrice', 'TodaySettlementPrice'),
            ('LastSettlementPrice', 'LastSettlementPrice'), ('OpenInterest', 'OpenInterest'),
            ('SettlementPricePercent', 'SettlementPricePercent')]:
            value = getattr(row, public)
            if native not in original or original[native] is None:
                assert pd.isna(value)
            else:
                assert value == original[native]
        assert row.DeliveryJalaliDate == original['DeliveryDate'].replace('/', '-')


def test_live_export_complete_windows_currency_units_prices_and_value():
    url = 'https://www.ime.co.ir/subsystems/ime/fiziki/export.ashx'
    response = requests.get(url, params=dict(f='1405/08/16', t='1405/08/17', m=0, c=0, s=0, p=0,
                                            lang=8, order='asc'), timeout=(10, 45))
    response.raise_for_status()
    raw = response.json()
    assert len(raw['rows']) == raw['total'] > 0
    frame = ime.get_all_ime_export_trades(start_date='1405-08-16', end_date='1405-08-17', _chunk_size=0)
    source = {str(r['ID']): r for r in raw['rows']}
    assert len(frame) == len(source) == raw['total'] and set(frame.ID) == set(source)
    for row in frame.itertuples():
        original = source[row.ID]
        for public, native in [('TradeVolume', 'Quantity'), ('TradeValue', 'TotalPrice'),
            ('ClosingPrice', 'Price'), ('HighPrice', 'MaxPrice'), ('LowPrice', 'MinPrice'),
            ('SupplyVolume', 'arze'), ('SupplyBasePrice', 'ArzeBasePrice'), ('Demand', 'taghaza')]:
            if original[native] is None:
                assert pd.isna(getattr(row, public))
            else:
                assert getattr(row, public) == original[native]
        assert row.Currency == original['Currency'] and row.Unit == original['Unit']
        assert row.Symbol == original['Symbol']
        assert row.JalaliDate == original['date'].replace('/', '-')
        assert row.DeliveryJalaliDate == original['DeliveryDate'].replace('/', '-')
        if original['NerkhArz'] is None:
            assert pd.isna(row.FXRate)
        else:
            assert row.FXRate == original['NerkhArz']
