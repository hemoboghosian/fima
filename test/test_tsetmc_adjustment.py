from datetime import date
from unittest.mock import Mock

import jdatetime as jd
import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from fima import TSETMC


PRICE_COLUMNS = ['ClosingPrice', 'LastPrice', 'OpeningPrice', 'LowPrice', 'HighPrice']


def history(close=(100, 90, 50), reference=(100, 80, 45)):
    frame = pd.DataFrame({
        'GregorianDate': [date(2024, 1, day) for day in range(1, len(close) + 1)],
        'YesterdayPrice': reference,
        **{column: close for column in PRICE_COLUMNS},
        'TransactionCount': 1, 'TradeVolume': 10, 'TradeValue': 1000,
        'PriceChange': 3, 'NumberOfShares': 200, 'MarketCap': 20000,
        'InstrumentCode': '123',
    }, index=pd.Index([f'row-{i}' for i in range(len(close))], name='original'))
    return frame


@pytest.mark.parametrize(('close', 'reference', 'factors'), [
    ((100, 110, 120), (100, 100, 110), (1, 1, 1)),
    ((100, 90), (100, 80), (.8, 1)),  # cash-dividend-like gap
    ((100, 55), (100, 50), (.5, 1)),  # split-like gap
    ((100, 90, 50), (100, 80, 45), (.4, .5, 1)),
    ((2000, 1100), (2000, 1000), (.5, 1)),
])
def test_reference_ratios(close, reference, factors):
    raw = history(close, reference)
    before = raw.copy(deep=True)
    adjusted = TSETMC.adjust_historical_prices(raw)
    np.testing.assert_allclose(adjusted.AdjustmentFactor, factors)
    for column in PRICE_COLUMNS:
        np.testing.assert_allclose(adjusted['Adjusted' + column], raw[column] * factors)
    assert_frame_equal(adjusted[raw.columns], before)
    assert_frame_equal(raw, before)


@pytest.mark.parametrize('positions', [[0, 1, 2], [2, 1, 0], [1, 2, 0]])
def test_order_and_duplicate_non_date_index_preserved(positions):
    raw = history().iloc[positions].copy()
    raw.index = pd.Index(['same', 'same', 'other'], name='labels')
    adjusted = TSETMC.adjust_historical_prices(raw)
    assert_frame_equal(adjusted[raw.columns], raw)
    np.testing.assert_allclose(adjusted.AdjustmentFactor, np.array([.4, .5, 1])[positions])


@pytest.mark.parametrize('dates', ['gregorian_index', 'jalali_index', 'jalali_column'])
def test_actual_dates(dates):
    raw = history()
    if dates == 'gregorian_index':
        raw.index = pd.DatetimeIndex(raw.pop('GregorianDate'), name='date')
    else:
        jalali = raw.pop('GregorianDate').map(lambda d: jd.date.fromgregorian(date=d))
        if dates == 'jalali_index':
            raw.index = pd.Index(jalali, name='JalaliDate')
        else:
            raw['JalaliDate'] = jalali.map(str).to_numpy()
    adjusted = TSETMC.adjust_historical_prices(raw.iloc[::-1])
    np.testing.assert_allclose(adjusted.AdjustmentFactor, [1, .5, .4])
    assert_frame_equal(adjusted[raw.columns], raw.iloc[::-1])


def test_zero_trade_changes_and_halt_reopening_preserve_every_row():
    raw = history((100, 80, 40, 45), (100, 80, 40, 40))
    raw['GregorianDate'] = [date(2024, 1, d) for d in [1, 2, 3, 20]]
    raw.iloc[1:3, raw.columns.get_loc('TransactionCount')] = 0
    raw.iloc[1:3, raw.columns.get_loc('TradeVolume')] = 0
    for column in ['OpeningPrice', 'LowPrice', 'HighPrice']:
        raw.iloc[1:3, raw.columns.get_loc(column)] = 0
    adjusted = TSETMC.adjust_historical_prices(raw)
    np.testing.assert_allclose(adjusted.AdjustmentFactor, [.4, .5, 1, 1])
    assert_frame_equal(adjusted[raw.columns], raw)
    assert adjusted.loc['row-1', 'AdjustedOpeningPrice'] == 0


def test_precision_and_subset_endpoint():
    raw = history((7, 11, 13), (7, 3, 5))
    adjusted = TSETMC.adjust_historical_prices(raw)
    assert adjusted.loc['row-0', 'AdjustmentFactor'] == pytest.approx(3 / 7 * 5 / 11)
    assert adjusted.loc['row-0', 'AdjustedClosingPrice'] == pytest.approx(15 / 11)
    earlier = TSETMC.adjust_historical_prices(raw.iloc[:2])
    np.testing.assert_allclose(earlier.AdjustmentFactor, [3 / 7, 1])
    assert earlier.loc['row-0', 'AdjustedClosingPrice'] == pytest.approx(3)
    assert earlier.loc['row-1', 'AdjustedClosingPrice'] == 11


@pytest.mark.parametrize('length', [0, 1])
def test_empty_and_single(length):
    raw = history().iloc[:length]
    adjusted = TSETMC.adjust_historical_prices(raw)
    assert_frame_equal(adjusted[raw.columns], raw)
    assert adjusted.AdjustmentFactor.tolist() == [1] * length
    assert all('Adjusted' + column in adjusted for column in PRICE_COLUMNS)


@pytest.mark.parametrize('bad', [0, -1, np.nan, np.inf, -np.inf, 'bad', None])
@pytest.mark.parametrize('column', ['ClosingPrice', 'YesterdayPrice'])
def test_invalid_chain_prices(column, bad):
    raw = history().astype({column: object})
    raw.loc['row-1', column] = bad
    with pytest.raises(ValueError, match=column):
        TSETMC.adjust_historical_prices(raw)


def test_oldest_reference_is_unused_but_later_missing_reference_rejected():
    raw = history()
    raw.loc['row-0', 'YesterdayPrice'] = np.nan
    np.testing.assert_allclose(TSETMC.adjust_historical_prices(raw).AdjustmentFactor, [.4, .5, 1])
    raw.loc['row-2', 'YesterdayPrice'] = np.nan
    with pytest.raises(ValueError, match='YesterdayPrice'):
        TSETMC.adjust_historical_prices(raw)


@pytest.mark.parametrize(('column', 'bad'), [
    (column, bad) for column in ['LastPrice', 'OpeningPrice', 'LowPrice', 'HighPrice']
    for bad in [0, -1, np.nan, np.inf]
    if (column, bad) != ('OpeningPrice', 0)  # Zero opening is a supported provider value.
])
def test_invalid_traded_prices(column, bad):
    raw = history().astype({column: float})
    raw.loc['row-1', column] = bad
    with pytest.raises(ValueError, match=column):
        TSETMC.adjust_historical_prices(raw)


@pytest.mark.parametrize('problem', ['duplicate_date', 'missing_date', 'bad_date',
                                    'missing_column', 'mixed_instruments', 'unknown_instrument',
                                    'mixed_tickers', 'no_dates', 'duplicate_columns'])
def test_ambiguous_or_incomplete_history(problem):
    raw = history()
    if problem == 'duplicate_date':
        raw.loc['row-1', 'GregorianDate'] = raw.loc['row-0', 'GregorianDate']
    elif problem in ['missing_date', 'bad_date']:
        raw.loc['row-1', 'GregorianDate'] = None if problem == 'missing_date' else 'not-a-date'
    elif problem == 'missing_column':
        raw = raw.drop(columns='YesterdayPrice')
    elif problem == 'mixed_instruments':
        raw.loc['row-1', 'InstrumentCode'] = '456'
    elif problem == 'unknown_instrument':
        raw.loc['row-1', 'InstrumentCode'] = None
    elif problem == 'mixed_tickers':
        raw = raw.drop(columns='InstrumentCode')
        raw['Ticker'] = ['A', 'B', 'A']
    elif problem == 'no_dates':
        raw = raw.drop(columns='GregorianDate').reset_index(drop=True)
    else:
        raw = pd.concat([raw, raw[['ClosingPrice']]], axis=1)
    with pytest.raises(ValueError):
        TSETMC.adjust_historical_prices(raw)


def test_nonfinite_cumulative_factor_rejected():
    raw = history((1e-300, 1, 1), (1, 1e300, 1))
    with pytest.raises(ValueError, match='finite'):
        TSETMC.adjust_historical_prices(raw)


@pytest.mark.parametrize('count', [None, pd.NA, 1])
def test_zero_price_requires_explicit_zero_transaction_count(count):
    raw = history().astype({'TransactionCount': 'Int64'})
    raw.loc['row-1', 'TransactionCount'] = count
    raw.loc['row-1', 'LowPrice'] = 0
    with pytest.raises(ValueError, match='LowPrice'):
        TSETMC.adjust_historical_prices(raw)


def test_zero_trade_close_is_still_required_positive():
    raw = history()
    raw.loc['row-1', ['TransactionCount', 'ClosingPrice']] = 0
    with pytest.raises(ValueError, match='ClosingPrice'):
        TSETMC.adjust_historical_prices(raw)


def test_underflow_and_adjusted_price_overflow_rejected():
    raw = history((1e300, 1, 1), (1, 1e-300, 1))
    with pytest.raises(ValueError, match='finite'):
        TSETMC.adjust_historical_prices(raw)
    raw = history((1, 1), (1, 2)).astype({'LastPrice': float})
    raw.loc['row-0', 'LastPrice'] = 1e308
    with pytest.raises(ValueError, match='AdjustedLastPrice'):
        TSETMC.adjust_historical_prices(raw)


def test_numeric_gregorian_dates_and_same_ticker_different_instruments():
    raw = history()
    raw['GregorianDate'] = [20240101, 20240102, 20240103]
    np.testing.assert_allclose(TSETMC.adjust_historical_prices(raw).AdjustmentFactor, [.4, .5, 1])
    raw['Ticker'] = 'same-ticker'
    raw.loc['row-1', 'InstrumentCode'] = '456'
    with pytest.raises(ValueError, match='instrument'):
        TSETMC.adjust_historical_prices(raw)


def provider_records():
    return [{
        'dEven': 20240101 + i, 'insCode': '123', 'priceYesterday': reference,
        'pClosing': close, 'pDrCotVal': close + 1, 'priceFirst': close - 1,
        'priceMin': close - 2, 'priceMax': close + 2,
        'priceChange': 2, 'zTotTran': 5, 'qTotTran5J': 100, 'qTotCap': 1000,
        'iClose': False, 'id': 0, 'hEven': 123000, 'yClose': True, 'last': False,
    } for i, (close, reference) in enumerate([(100, 100), (90, 80), (50, 45)])][::-1]


def test_download_default_compatibility_and_opt_in(monkeypatch):
    get = Mock(return_value=Mock(json=lambda: {'closingPriceDaily': provider_records()}))
    monkeypatch.setattr(TSETMC.requests, 'get', get)
    monkeypatch.setattr(TSETMC, '_find_instrument_code', lambda ticker: '123')
    raw = TSETMC.get_ticker_historical_data('example')
    adjusted = TSETMC.get_ticker_historical_data(None, '123', adjust_prices=True)
    assert raw.columns.tolist() == ['YesterdayPrice', 'ClosingPrice', 'LastPrice',
                                   'OpeningPrice', 'LowPrice', 'HighPrice', 'PriceChange',
                                   'TransactionCount', 'TradeVolume', 'TradeValue']
    assert_frame_equal(adjusted[raw.columns], raw)
    np.testing.assert_allclose(adjusted.AdjustmentFactor, [1, .5, .4])
    assert adjusted.AdjustedLastPrice.iloc[-1] == pytest.approx(40.4)
    assert get.call_count == 2
    get.assert_called_with('https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/123/0', timeout=15)
    import fima
    assert fima.get_ticker_historical_data is TSETMC.get_ticker_historical_data
    assert fima.adjust_historical_prices is TSETMC.adjust_historical_prices


@pytest.mark.parametrize('adjust', [False, True])
def test_empty_download(monkeypatch, adjust):
    monkeypatch.setattr(TSETMC.requests, 'get', lambda *a, **k: Mock(json=lambda: {'closingPriceDaily': []}))
    result = TSETMC.get_ticker_historical_data(ticker_instrument_code='123', adjust_prices=adjust)
    assert result.empty
    assert result.index.name == 'JalaliDate'
    assert 'ClosingPrice' in result
    assert ('AdjustmentFactor' in result) == adjust


def test_download_rejects_mixed_instrument_payload(monkeypatch):
    records = provider_records()
    records[1]['insCode'] = '456'
    monkeypatch.setattr(TSETMC.requests, 'get', lambda *a, **k: Mock(json=lambda: {'closingPriceDaily': records}))
    with pytest.raises(ValueError, match='instrument'):
        TSETMC.get_ticker_historical_data(ticker_instrument_code='123', adjust_prices=True)


@pytest.mark.parametrize('descending', [False, True])
def test_zero_opening_on_traded_observation_preserves_ratios(descending):
    raw = history()
    raw.loc['row-1', 'OpeningPrice'] = 0
    if descending:
        raw = raw.iloc[::-1]
    adjusted = TSETMC.adjust_historical_prices(raw)
    expected = [1, .5, .4] if descending else [.4, .5, 1]
    np.testing.assert_allclose(adjusted.AdjustmentFactor, expected)
    assert adjusted.loc['row-1', 'AdjustedOpeningPrice'] == 0
    assert adjusted.loc['row-1', 'TransactionCount'] == 1
    np.testing.assert_allclose(adjusted.AdjustedClosingPrice, raw.ClosingPrice * expected)
    assert_frame_equal(adjusted[raw.columns], raw)


def test_mocked_official_traded_row_with_zero_opening(monkeypatch):
    # Official Shasta daily record observed on 2026-10-13, not a live CI request.
    record = {
        'priceChange': 22.0, 'priceMin': 1244.0, 'priceMax': 1285.0,
        'priceYesterday': 1251.0, 'priceFirst': 0.0, 'last': False,
        'id': 0, 'insCode': '2400322364771558', 'dEven': 20231009,
        'hEven': 123000, 'pClosing': 1267.0, 'iClose': False,
        'yClose': True, 'pDrCotVal': 1273.0, 'zTotTran': 5605.0,
        'qTotTran5J': 361020673.0, 'qTotCap': 457514177348.0,
    }
    get = Mock(return_value=Mock(json=lambda: {'closingPriceDaily': [record]}))
    monkeypatch.setattr(TSETMC.requests, 'get', get)
    monkeypatch.setattr(TSETMC, '_find_instrument_code', lambda ticker: '2400322364771558')
    raw = TSETMC.get_ticker_historical_data(ticker='شستا')
    adjusted = TSETMC.get_ticker_historical_data(ticker='شستا', adjust_prices=True)
    assert_frame_equal(adjusted[raw.columns], raw)
    assert adjusted.AdjustmentFactor.iloc[0] == 1
    assert adjusted.OpeningPrice.iloc[0] == adjusted.AdjustedOpeningPrice.iloc[0] == 0
    assert adjusted.ClosingPrice.iloc[0] == adjusted.AdjustedClosingPrice.iloc[0] == 1267
    assert adjusted.LastPrice.iloc[0] == adjusted.AdjustedLastPrice.iloc[0] == 1273
    assert adjusted.TransactionCount.iloc[0] == 5605
    assert get.call_count == 2


@pytest.mark.parametrize('transaction_count', [None, pd.NA, 0, 1])
def test_zero_opening_does_not_require_transaction_count(transaction_count):
    raw = history().astype({'TransactionCount': 'Int64'})
    raw.loc['row-1', 'TransactionCount'] = transaction_count
    raw.loc['row-1', 'OpeningPrice'] = 0
    adjusted = TSETMC.adjust_historical_prices(raw)
    assert adjusted.loc['row-1', 'AdjustedOpeningPrice'] == 0
    np.testing.assert_allclose(adjusted.AdjustmentFactor, [.4, .5, 1])
    without_counts = TSETMC.adjust_historical_prices(raw.drop(columns='TransactionCount'))
    np.testing.assert_allclose(without_counts.AdjustmentFactor, adjusted.AdjustmentFactor)


def test_negative_opening_on_zero_trade_row_is_rejected():
    raw = history()
    raw.loc['row-1', ['TransactionCount', 'OpeningPrice']] = [0, -1]
    with pytest.raises(ValueError, match='OpeningPrice'):
        TSETMC.adjust_historical_prices(raw)
