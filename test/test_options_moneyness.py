"""Missing observations are not equality: public schema regressions for #161."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import requests

import fima.Options as options
from test.test_tsetmc_options_contracts import option_record


@pytest.fixture
def source(monkeypatch):
    payload = {'instrumentOptMarketWatch': [option_record()]}
    def forbidden(*args, **kwargs):
        pytest.fail('Moneyness regression tests must not make network requests')
    monkeypatch.setattr(requests.Session, 'request', forbidden)
    def get(url, **kwargs):
        assert kwargs['timeout'] == 30
        assert url == 'https://cdn.tsetmc.com/api/Instrument/GetInstrumentOptionMarketWatch/0'
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)
    monkeypatch.setattr(options.requests, 'get', get)
    return payload


def download(layout, j_date=True):
    return (options.download_chain_contracts('BASE', j_date=j_date) if layout == 'chain'
            else options.download_market_watch(stack=layout, j_date=j_date))


def statuses(result, layout):
    if layout == 'Vertical':
        return {row.OptionType: row.Status for row in result.itertuples()}
    return {'Call': result.iloc[0].CallStatus, 'Put': result.iloc[0].PutStatus}


@pytest.mark.parametrize('layout', ['Horizontal', 'Vertical', 'chain'])
@pytest.mark.parametrize('j_date', [True, False])
@pytest.mark.parametrize('field,value', [
    ('pDrCotVal_UA', None), ('pDrCotVal_UA', np.nan), ('pDrCotVal_UA', 0),
    ('pDrCotVal_UA', -1), ('pDrCotVal_UA', np.inf),
    ('strikePrice', None), ('strikePrice', np.nan), ('strikePrice', 0),
    ('strikePrice', -1), ('strikePrice', np.inf),
])
def test_missing_or_invalid_prices_have_unknown_status(source, layout, j_date, field, value):
    expected = download(layout, j_date)
    source['instrumentOptMarketWatch'][0][field] = value
    result = download(layout, j_date)
    assert list(result) == list(expected)
    assert len(result) == len(expected)
    assert all(pd.isna(status) for status in statuses(result, layout).values())
    assert all(status is pd.NA for status in statuses(result, layout).values())
    status_columns = ['Status'] if layout == 'Vertical' else ['CallStatus', 'PutStatus']
    assert all(result[c].dtype == expected[c].dtype == object for c in status_columns)
    codes = ['InstrumentCode', 'UnderlyingInstrumentCode'] if layout == 'Vertical' else [
        'CallInstrumentCode', 'PutInstrumentCode', 'UnderlyingInstrumentCode']
    pd.testing.assert_frame_equal(result[codes], expected[codes])
    # Missing spot must not fall back to the still-present underlying closing price.
    assert result.UnderlyingClosingPrice.eq(105).all()


@pytest.mark.parametrize('layout', ['Horizontal', 'Vertical', 'chain'])
@pytest.mark.parametrize('j_date', [True, False])
@pytest.mark.parametrize('spot,call,put', [(90, 'OTM', 'ITM'), (100, 'ATM', 'ATM'), (110, 'ITM', 'OTM')])
def test_valid_moneyness_and_price_basis_are_preserved(source, layout, j_date, spot, call, put):
    source['instrumentOptMarketWatch'][0]['pDrCotVal_UA'] = spot
    result = download(layout, j_date)
    assert statuses(result, layout) == {'Call': call, 'Put': put}
    assert result.UnderlyingLastPrice.eq(spot).all()
    assert result.UnderlyingClosingPrice.eq(105).all()
    numeric = 'LastPrice' if layout == 'Vertical' else 'CallLastPrice'
    assert pd.api.types.is_numeric_dtype(result[numeric])


@pytest.mark.parametrize('layout', ['Horizontal', 'Vertical', 'chain'])
@pytest.mark.parametrize('j_date', [True, False])
def test_empty_schema_preserved(source, layout, j_date):
    expected = download(layout, j_date)
    source['instrumentOptMarketWatch'] = []
    result = download(layout, j_date)
    assert result.empty and list(result) == list(expected)
    columns = ['Status'] if layout == 'Vertical' else ['CallStatus', 'PutStatus']
    assert all(result[c].dtype == expected[c].dtype == object for c in columns)


@pytest.mark.parametrize('layout', ['Horizontal', 'Vertical', 'chain'])
def test_malformed_prices_still_raise_instead_of_becoming_unknown(source, layout):
    source['instrumentOptMarketWatch'][0]['pDrCotVal_UA'] = 'bad price'
    with pytest.raises(ValueError):
        download(layout)


@pytest.mark.parametrize('layout', ['Horizontal', 'Vertical', 'chain'])
def test_unknown_status_with_iv_enrichment(source, monkeypatch, layout):
    source['instrumentOptMarketWatch'][0]['pDrCotVal_UA'] = None
    history = pd.DataFrame({'ClosingPrice': np.linspace(90, 110, 60)},
                           index=pd.Index(pd.date_range('2026-01-01', periods=60), name='JalaliDate'))
    monkeypatch.setattr(options, 'get_ticker_historical_data', lambda **k: history)
    monkeypatch.setattr(options, 'get_risk_free_rate', lambda: .05)
    result = (options.download_chain_contracts('BASE', implied_volatility=True) if layout == 'chain'
              else options.download_market_watch(stack=layout, implied_volatility=True))
    assert all(status is pd.NA for status in statuses(result, layout).values())
    iv_columns = ['ImpliedVolatility'] if layout == 'Vertical' else ['CallImpliedVolatility', 'PutImpliedVolatility']
    assert result[iv_columns].isna().all().all()
