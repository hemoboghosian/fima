import pandas as pd
import pytest
from fima.Options import (get_greeks, get_implied_volatility, black_scholes_merton, download_chain_contracts,
                          download_market_watch, download_all_underlying_assets, download_historical_data)


@pytest.mark.parametrize("market", ["All", "IFB", "TSE"])
def test_download_all_underlying_assets(market):
    all_underlying_assets = download_all_underlying_assets(market=market)
    assert all_underlying_assets is not None
    assert not all_underlying_assets.empty
    assert isinstance(all_underlying_assets, pd.DataFrame)
    for column in ['Ticker', 'InstrumentCode', 'ClosePrice', 'LastPrice', 'YesterdayPrice', 'URL']:
        assert column in all_underlying_assets


@pytest.mark.parametrize(["ticker", "start_date", "end_date"], [("ضهرم4018", '1404-02-01', '1404-02-31'),
                                                                ("طهرم4018", '1404-02-01', '1404-02-31'),
                                                                ("ضهرم4018", None, None),
                                                                ("طهرم4018", None, None)])
def test_download_historical_data(ticker, start_date, end_date):
    option_historical_data, ua_historical_data = download_historical_data(ticker=ticker, start_date=start_date, end_date=end_date)
    assert option_historical_data is not None
    assert ua_historical_data is not None
    assert not option_historical_data.empty
    assert not ua_historical_data.empty
    assert isinstance(option_historical_data, pd.DataFrame)
    assert isinstance(ua_historical_data, pd.DataFrame)
    for column in ['Date', 'Quantity', 'Volume', 'Value', 'MinPrice', 'MaxPrice', 'FirstPrice', 'LastPrice', 'ClosePrice']:
        assert column in option_historical_data
    for column in ['Date', 'Quantity', 'Volume', 'Value', 'MinPrice', 'MaxPrice', 'FirstPrice', 'LastPrice', 'ClosePrice']:
        assert column in option_historical_data


@pytest.mark.parametrize("ticker", ["ضهرم4018", "ظهرم4018"])
def test_get_greeks(ticker):
    greeks = get_greeks(ticker)
    assert greeks is not None
    assert isinstance(greeks, pd.Series)  # pandas Series
    for greek in ['Delta', 'Gamma', 'Theta', 'Vega', 'Rho']:
        assert greek in greeks


@pytest.mark.parametrize("ticker", ["ضهرم4018", "طهرم4018"])
def test_black_scholes_merton(ticker):
    volatility, bsm_price = black_scholes_merton(ticker)
    assert all(isinstance(v, float) for v in [volatility, bsm_price])
    assert 0 <= volatility <= 2
    assert isinstance(bsm_price, float)
    assert 0 <= bsm_price
    assert all(v is not None for v in [volatility, bsm_price])


@pytest.mark.parametrize("ticker", ["ضهرم4018", "طهرم4018"])
def test_get_implied_volatility(ticker):
    implied_volatility = get_implied_volatility(ticker)
    assert isinstance(implied_volatility, float)
    assert 0 <= implied_volatility <= 2


@pytest.mark.parametrize(["underlying_ticker", "j_date", "bsm", "greeks", "implied_volatility"],
                         [('اهرم', True, True, True, True), ('اهرم', True, True, True, False),
                          ('اهرم', True, True, False, True), ('اهرم', True, True, False, False),
                          ('اهرم', True, False, True, True), ('اهرم', True, False, True, False),
                          ('اهرم', True, False, False, True), ('اهرم', True, False, False, False),
                          ('اهرم', False, True, True, True), ('اهرم', False, True, True, False),
                          ('اهرم', False, True, False, True), ('اهرم', False, True, False, False),
                          ('اهرم', False, False, True, True), ('اهرم', False, False, True, False),
                          ('اهرم', False, False, False, True), ('اهرم', False, False, False, False)])
def test_download_chain_contracts(underlying_ticker, j_date, bsm, greeks, implied_volatility):
    chain_contracts = download_chain_contracts(underlying_ticker=underlying_ticker, j_date=j_date, bsm=bsm,
                                               greeks=greeks, implied_volatility=implied_volatility)
    assert chain_contracts is not None
    assert not chain_contracts.empty
    assert isinstance(chain_contracts, pd.DataFrame)

    if bsm:
        assert all(column in chain_contracts.columns for column in ['BSMPrice-C', 'BSMPrice-P', 'Volatility-C', 'Volatility-P']), "Horizontal, BSM"
    if greeks:
        assert all(column in chain_contracts.columns for column in ['Delta-C', 'Gamma-C', 'Theta-C', 'Vega-C', 'Rho-C',
                                                                    'Delta-P', 'Gamma-P', 'Theta-P', 'Vega-P', 'Rho-P']), "Horizontal, Greeks"
    if implied_volatility:
        assert all(column in chain_contracts.columns for column in ['ImpliedVolatility-C', 'ImpliedVolatility-P']), "Horizontal, IV"


@pytest.mark.parametrize(["market", "stack", "j_date", "bsm", "greeks", "implied_volatility"],
                         [('TSE', 'Horizontal', False, False, False, False), ('TSE', 'Vertical', False, False, False, False),
                          ('TSE', 'Horizontal', False, False, False, True), ('TSE', 'Vertical', False, False, False, True),
                          ('TSE', 'Horizontal', True, True, True, True), ('TSE', 'Horizontal', True, True, True, False),
                          ('TSE', 'Horizontal', True, True, False, True), ('TSE', 'Horizontal', True, True, False, False),
                          ('TSE', 'Horizontal', True, False, True, True), ('TSE', 'Horizontal', True, False, True, False),
                          ('TSE', 'Horizontal', True, False, False, True), ('TSE', 'Horizontal', True, False, False, False),
                          ('TSE', 'Horizontal', False, True, True, True), ('TSE', 'Horizontal', False, True, True, False),
                          ('TSE', 'Horizontal', False, True, False, True), ('TSE', 'Horizontal', False, True, False, False),
                          ('TSE', 'Horizontal', False, False, True, True), ('TSE', 'Horizontal', False, False, True, False),
                          ('TSE', 'Vertical', True, True, True, True), ('TSE', 'Vertical', True, True, True, False),
                          ('TSE', 'Vertical', True, True, False, True), ('TSE', 'Vertical', True, True, False, False),
                          ('TSE', 'Vertical', True, False, True, True), ('TSE', 'Vertical', True, False, True, False),
                          ('TSE', 'Vertical', True, False, False, True), ('TSE', 'Vertical', True, False, False, False),
                          ('TSE', 'Vertical', False, True, True, True), ('TSE', 'Vertical', False, True, True, False),
                          ('TSE', 'Vertical', False, True, False, True), ('TSE', 'Vertical', False, True, False, False),
                          ('TSE', 'Vertical', False, False, True, True), ('TSE', 'Vertical', False, False, True, False)])
def test_download_market_watch(market, stack, j_date, bsm, greeks, implied_volatility):
    market_watch = download_market_watch(market=market, j_date=j_date, bsm=bsm, greeks=greeks, implied_volatility=implied_volatility)
    assert market_watch is not None
    assert not market_watch.empty
    assert isinstance(market_watch, pd.DataFrame)

    if stack == 'Horizontal':
        if bsm:
            assert all(column in market_watch.columns for column in ['BSMPrice-C', 'BSMPrice-P', 'Volatility-C', 'Volatility-P']), "Horizontal, BSM"
        if greeks:
            assert all(column in market_watch.columns for column in ['Delta-C', 'Gamma-C', 'Theta-C', 'Vega-C', 'Rho-C',
                                                                        'Delta-P', 'Gamma-P', 'Theta-P', 'Vega-P', 'Rho-P']), "Horizontal, Greeks"
        if implied_volatility:
            assert all(column in market_watch.columns for column in ['ImpliedVolatility-C', 'ImpliedVolatility-P']), "Horizontal, IV"
    if stack == 'Vertical':
        if bsm:
            assert all(column in market_watch.columns for column in ['BSMPrice', 'Volatility']), "Vertical, BSM"
        if greeks:
            assert all(column in market_watch.columns for column in ['Delta', 'Gamma', 'Theta', 'Vega', 'Rho']), "Vertical, Greeks"
        if implied_volatility:
            assert all(column in market_watch.columns for column in ['ImpliedVolatility']), "Vertical, IV"
