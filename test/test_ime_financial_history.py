"""Complete certificate/salaf histories using the official financial handler."""
from types import SimpleNamespace

import pandas as pd
import pytest
import requests

import fima
import fima.IME as ime


def financial_row(code='IRK1A12405A6', ticker='زعف0510پ20', date='1405/08/16'):
    # id=1 repeats across instruments/dates in the real provider response.
    return dict(id=1, Namad=code, LVal18AFC=ticker, DT=date,
        NamadDescription='Instrument', PClosing=2607721.0, PDrCotVal=2621599.0,
        ZTotTran=127.0, QTotTran5J=51689.0, QTotCap=134790495252.0,
        PriceMin=2585000.0, PriceMax=2650000.0, PriceYesterday=2546476.0,
        LastTradeChangePrice=75123.0, LastTradeChangePricePercent=0.0,
        LastPriceChangePrice=61245.0, LastPriceChangePricePercent=0.0,
        DT_En='2026-11-07T00:00:00')


@pytest.fixture(params=[ime.get_all_ime_cd_trades, ime.get_all_ime_salaf_trades])
def function(request):
    return request.param


def serve(monkeypatch, items):
    calls, iterator = [], iter(items)

    def get(url, **kwargs):
        calls.append((url, kwargs))
        item = next(iterator)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(json=lambda: item, raise_for_status=lambda: None)

    monkeypatch.setattr(ime.requests, 'get', get)
    return calls


def history(function, **kwargs):
    return function(start_date='1405-08-16', end_date='1405-08-16', **kwargs)


def test_complete_pages_allow_repeated_row_id_and_filter_by_stable_code(monkeypatch, function):
    calls = serve(monkeypatch, [dict(total=2, rows=[financial_row()]),
        dict(total=2, rows=[financial_row('IRBKKATD05A7', 'عكاتد')])])
    result = history(function, instrument_code='IRBKKATD05A7')
    assert result.Code.tolist() == ['IRBKKATD05A7']
    assert [call[1]['params']['offset'] for call in calls] == [0, 1]
    assert all(call[1]['params']['ot'] == 0 for call in calls)  # Local selection.
    assert all(call[1]['params']['sort'] == 'LVal18AFC' for call in calls)
    assert all(call[1]['timeout'] == (10, 45) for call in calls)
    assert result.iloc[0].ID == '1'
    assert result.iloc[0].ClosingPrice == 2607721
    assert result.iloc[0].LastPrice == 2621599
    assert result.iloc[0].TransactionCount == 127
    assert result.iloc[0].TradeVolume == 51689
    assert result.iloc[0].TradeValue == 134790495252
    assert result.iloc[0].ClosingPriceChange == 61245
    assert result.iloc[0].ClosingPricePercentageChange == 0
    assert result.iloc[0].LastPricePercentageChange == 0
    assert result.iloc[0].JalaliDate == '1405-08-16'
    assert result.iloc[0].GregorianDate == pd.Timestamp('2026-11-07')
    assert getattr(fima, function.__name__) is function
    assert calls[0][1]['params']['c'] == (1 if function is ime.get_all_ime_cd_trades else 0)


def test_exact_ticker_and_typed_empty_match_full_schema(monkeypatch, function):
    serve(monkeypatch, [dict(total=1, rows=[financial_row()]), dict(total=0, rows=[]),
                        dict(total=1, rows=[financial_row()])])
    selected = history(function, ticker='زعف0510پ20')
    empty = history(function)
    unknown = history(function, ticker='Unknown')
    assert len(selected) == 1 and empty.empty and unknown.empty
    assert empty.columns.tolist() == selected.columns.tolist() == unknown.columns.tolist()
    assert str(empty.GregorianDate.dtype) == 'datetime64[ns]'
    assert str(empty.Code.dtype) == 'string'


@pytest.mark.parametrize('bad', [{}, {'total': 1, 'rows': []}, {'total': 0, 'rows': None},
    {'total': 1, 'rows': [dict(id=1)]}])
def test_malformed_and_truncated_history_fails(monkeypatch, function, bad):
    serve(monkeypatch, [bad])
    with pytest.raises(RuntimeError):
        history(function)


@pytest.mark.parametrize('error', [requests.Timeout('timeout'), requests.HTTPError('429'),
    requests.exceptions.SSLError('TLS'), ValueError('HTML response')])
def test_failed_later_window_never_returns_partial_data(monkeypatch, function, error):
    serve(monkeypatch, [dict(total=1, rows=[financial_row()]), error])
    with pytest.raises(RuntimeError, match='1405/08/17'):
        function(start_date='1405-08-16', end_date='1405-08-17', _chunk_size=0)


@pytest.mark.parametrize('next_page', [dict(total=3, rows=[financial_row('OTHER')]),
    dict(total=2, rows=[]), dict(total=2, rows=[financial_row()])])
def test_changed_missing_repeated_pages_fail(monkeypatch, function, next_page):
    serve(monkeypatch, [dict(total=2, rows=[financial_row()]), next_page])
    with pytest.raises(RuntimeError):
        history(function)


@pytest.mark.parametrize('changes', [dict(Namad=None), dict(Namad=''), dict(Namad='null'),
    dict(Namad=float('nan')), dict(Namad={}), dict(DT='1405/08/15'),
    dict(DT_En='2026-11-06'), dict(QTotCap='broken')])
def test_identity_date_and_financial_errors_precede_local_filter(monkeypatch, function, changes):
    row = financial_row()
    row.update(changes)
    serve(monkeypatch, [dict(total=1, rows=[row])])
    with pytest.raises(RuntimeError):
        history(function, ticker='Unknown')


@pytest.mark.parametrize('kwargs', [dict(ticker=''), dict(ticker=123), dict(instrument_code=''),
    dict(instrument_code=123), dict(ticker='X', instrument_code='Y'), dict(_chunk_size=-1)])
def test_invalid_selection_fails_without_http(monkeypatch, function, kwargs):
    calls = serve(monkeypatch, [])
    with pytest.raises(ValueError):
        history(function, **kwargs)
    assert not calls


def test_date_defaults_normalization_and_legacy_reversed_range(monkeypatch, function):
    calls = serve(monkeypatch, [dict(total=0, rows=[])])
    function(_chunk_size=100000)
    floor = '1394/03/01' if function is ime.get_all_ime_cd_trades else '1393/05/01'
    assert calls[0][1]['params']['f'] == floor
    assert calls[0][1]['params']['t'] == str(ime.jd.date.today()).replace('-', '/')
    assert function(start_date='1405/08/17', end_date='1405/08/16') is None


@pytest.mark.integration
@pytest.mark.parametrize('function, market, code', [
    (ime.get_all_ime_cd_trades, 1, 'IRK1A12405A6'),
    (ime.get_all_ime_salaf_trades, 0, 'IRBKKATD05A7')])
def test_live_financial_history_matches_source_over_multiple_pages(monkeypatch, function, market, code):
    url = 'https://www.ime.co.ir/subsystems/ime/bazaremali/bazaremalidata.ashx'
    get = requests.get
    params = dict(f='1405/08/16', t='1405/08/17', c=market, ot=0, lang=8, order='asc')
    response = get(url, params=params, timeout=(10, 45))
    response.raise_for_status()
    raw = response.json()
    assert len(raw['rows']) == raw['total'] > 2
    calls = []

    def small_pages(url, **kwargs):
        kwargs['params'] = dict(kwargs['params'], limit=2)
        calls.append(kwargs['params']['offset'])
        return get(url, **kwargs)

    # Exercise genuine public limit/offset requests even for a small source report.
    monkeypatch.setattr(ime.requests, 'get', small_pages)
    result = function(start_date='1405-08-16', end_date='1405-08-17', instrument_code=code)
    expected = {(row['Namad'], row['DT'].replace('/', '-')): row for row in raw['rows'] if row['Namad'] == code}
    assert len(calls) > 1 and len(result) == len(expected) == 2  # Both inclusive dates.
    for row in result.itertuples():
        source = expected[row.Code, row.JalaliDate]
        for public, provider in [('ClosingPrice', 'PClosing'), ('LastPrice', 'PDrCotVal'),
            ('TransactionCount', 'ZTotTran'), ('TradeVolume', 'QTotTran5J'), ('TradeValue', 'QTotCap')]:
            assert getattr(row, public) == source[provider]
