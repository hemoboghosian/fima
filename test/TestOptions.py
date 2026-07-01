import pandas as pd
import numpy as np
import pytest
import jdatetime as jd

from fima.Options import (get_greeks, get_implied_volatility, black_scholes_merton, download_chain_contracts,
                          download_market_watch, download_all_underlying_assets, download_historical_data,)


EXPECTED_HISTORICAL_COLUMNS = ['Date', 'Quantity', 'Volume', 'Value', 'MinPrice', 'MaxPrice', 'FirstPrice', 'LastPrice',
                               'ClosePrice']


@pytest.fixture(scope="session")
def sample_option_info():
    return pd.DataFrame([{"Ticker": "TEST", "UATicker": "TESTUA", "StrikePrice": 100,
                          "MaturityDate": jd.date.today() + jd.timedelta(days=90), "DaysToMaturity": 90, "Type": "Call",
                          "LastPrice": 5, "LastPrice-UA": 100}])


@pytest.fixture(scope="session")
def sample_ua_historical_data():
    dates = [jd.date.today() - jd.timedelta(days=i) for i in range(80, 0, -1)]
    prices = np.linspace(90, 110, 80)
    return pd.DataFrame({"Date": dates, "ClosePrice": prices})


@pytest.fixture(scope="session")
def market_watch_horizontal():
    market_watch = download_market_watch(market="All", stack="Horizontal", j_date=True, bsm=False, greeks=False,
                                         implied_volatility=False)
    assert market_watch is not None
    assert isinstance(market_watch, pd.DataFrame)
    assert not market_watch.empty
    return market_watch


def test_download_all_underlying_assets_from_existing_market_watch(market_watch_horizontal):
    all_underlying_assets = download_all_underlying_assets(_all_options_market_watch=market_watch_horizontal)
    assert all_underlying_assets is not None
    assert isinstance(all_underlying_assets, pd.DataFrame)
    assert not all_underlying_assets.empty
    expected_columns = ['Ticker', 'InstrumentCode', 'ClosePrice', 'LastPrice', 'YesterdayPrice', 'URL']
    assert all(column in all_underlying_assets.columns for column in expected_columns)


@pytest.mark.parametrize("market", ["All", "IFB", "TSE"])
def test_download_market_watch_basic_by_market(market):
    market_watch = download_market_watch(market=market, stack="Horizontal", j_date=True, bsm=False, greeks=False,
                                         implied_volatility=False)
    assert market_watch is not None
    assert isinstance(market_watch, pd.DataFrame)
    assert not market_watch.empty


@pytest.mark.parametrize(["stack", "j_date"], [("Horizontal", True), ("Horizontal", False), ("Vertical", True),
                                               ("Vertical", False)])
def test_download_market_watch_basic_stack_and_date(stack, j_date):
    market_watch = download_market_watch(market="TSE", stack=stack, j_date=j_date, bsm=False, greeks=False,
                                         implied_volatility=False)
    assert market_watch is not None
    assert isinstance(market_watch, pd.DataFrame)
    assert not market_watch.empty
    if stack == "Horizontal":
        expected_columns = ['Ticker-C', 'Ticker-P', 'Ticker-UA', 'StrikePrice', 'DaysToMaturity', 'LastPrice-C',
                            'LastPrice-P', 'LastPrice-UA']
    else:
        expected_columns = ['Ticker', 'Ticker-UA', 'StrikePrice', 'DaysToMaturity', 'LastPrice', 'Type']
    assert all(column in market_watch.columns for column in expected_columns)


def test_download_historical_data_one_known_option():
    option_historical_data, ua_historical_data = download_historical_data(ticker="ضهرم4018", start_date="1404-02-01",
                                                                          end_date="1404-02-31")
    assert option_historical_data is not None
    assert ua_historical_data is not None
    assert isinstance(option_historical_data, pd.DataFrame)
    assert isinstance(ua_historical_data, pd.DataFrame)
    assert not option_historical_data.empty
    assert not ua_historical_data.empty
    assert all(column in option_historical_data.columns for column in EXPECTED_HISTORICAL_COLUMNS)
    assert all(column in ua_historical_data.columns for column in EXPECTED_HISTORICAL_COLUMNS)


def test_get_greeks_with_injected_data(sample_option_info, sample_ua_historical_data):
    greeks = get_greeks(ticker="TEST_OPTION", _ticker_info_df=sample_option_info, r_f=0.05,
                        _ua_historical_data=sample_ua_historical_data)
    assert greeks is not None
    assert isinstance(greeks, pd.Series)
    expected_greeks = ['Delta', 'Gamma', 'Theta', 'Vega', 'Rho']
    assert all(greek in greeks.index for greek in expected_greeks)
    assert all(pd.notna(greeks[greek]) for greek in expected_greeks)


def test_black_scholes_merton_with_injected_data(sample_option_info, sample_ua_historical_data):
    volatility, bsm_price = black_scholes_merton(ticker="TEST_OPTION", _ticker_info_df=sample_option_info, r_f=0.05,
                                                 _ua_historical_data=sample_ua_historical_data)
    assert volatility is not None
    assert bsm_price is not None
    assert isinstance(volatility, float)
    assert isinstance(bsm_price, float)
    assert 0 <= volatility <= 2
    assert bsm_price >= 0


def test_get_implied_volatility_with_injected_data(sample_option_info, sample_ua_historical_data):
    implied_volatility = get_implied_volatility(ticker="TEST_OPTION", _ticker_info_df=sample_option_info, r_f=0.05,
                                                _ua_historical_data=sample_ua_historical_data)
    assert implied_volatility is not None
    assert isinstance(implied_volatility, float)
    assert implied_volatility >= 0


@pytest.mark.parametrize(["j_date", "bsm", "greeks", "implied_volatility"],
                         [(True, False, False, False), (False, False, False, False),])
def test_download_chain_contracts_limited(j_date, bsm, greeks, implied_volatility):
    chain_contracts = download_chain_contracts(underlying_ticker="اهرم", j_date=j_date, bsm=bsm, greeks=greeks,
                                               implied_volatility=implied_volatility)
    assert chain_contracts is not None
    assert isinstance(chain_contracts, pd.DataFrame)
    assert not chain_contracts.empty
    basic_columns = ['Ticker-C', 'Ticker-P', 'Ticker-UA', 'StrikePrice', 'DaysToMaturity', 'LastPrice-C', 'LastPrice-P',
                     'LastPrice-UA']
    assert all(column in chain_contracts.columns for column in basic_columns)
    if bsm:
        assert all(column in chain_contracts.columns for column in ['BSMPrice-C', 'BSMPrice-P', 'Volatility-C', 'Volatility-P'])
    if greeks:
        assert all(column in chain_contracts.columns for column in ['Delta-C', 'Gamma-C', 'Theta-C', 'Vega-C', 'Rho-C',
                                                                    'Delta-P', 'Gamma-P', 'Theta-P', 'Vega-P', 'Rho-P'])

    if implied_volatility:
        assert all(column in chain_contracts.columns for column in ['ImpliedVolatility-C', 'ImpliedVolatility-P'])


@pytest.mark.slow
def test_download_chain_contracts_with_calculations():
    chain_contracts = download_chain_contracts(underlying_ticker="اهرم", j_date=True, bsm=True, greeks=True,
                                               implied_volatility=True)
    assert chain_contracts is not None
    assert isinstance(chain_contracts, pd.DataFrame)
    assert not chain_contracts.empty
    assert all(column in chain_contracts.columns for column in ['BSMPrice-C', 'BSMPrice-P', 'Volatility-C',
                                                                'Volatility-P', 'Delta-C', 'Gamma-C', 'Theta-C',
                                                                'Vega-C', 'Rho-C', 'Delta-P', 'Gamma-P', 'Theta-P',
                                                                'Vega-P', 'Rho-P', 'ImpliedVolatility-C',
                                                                'ImpliedVolatility-P'])