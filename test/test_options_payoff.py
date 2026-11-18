"""Expiration scenarios use supplied premiums and multipliers, with no HTTP."""
import numpy as np
import pandas as pd
import pytest
import requests

import fima
import fima.Options as options


COLUMNS = ['UnderlyingPrice', 'IntrinsicValue', 'ExpirationPayoff', 'PremiumCashFlow', 'GrossProfit']


@pytest.fixture(autouse=True)
def no_http(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Expiration scenarios must not request HTTP')
    monkeypatch.setattr(requests.Session, 'request', forbidden)


@pytest.mark.parametrize('option_type,position,intrinsic,payoff,profit', [
    ('Call', 'Long', [0, 0, 200], [0, 0, 501600], [-200640, -200640, 300960]),
    ('Call', 'Short', [0, 0, 200], [0, 0, -501600], [200640, 200640, -300960]),
    ('Put', 'Long', [200, 0, 0], [501600, 0, 0], [300960, -200640, -200640]),
    ('Put', 'Short', [200, 0, 0], [-501600, 0, 0], [-300960, 200640, 200640]),
])
def test_independent_cash_flows(option_type, position, intrinsic, payoff, profit):
    result = options.calculate_expiration_payoff(
        [800, 1000, 1200], 1000, 80, option_type,
        contract_size=1254, contracts=2, position=position)
    assert list(result) == COLUMNS
    assert all(str(result[c].dtype) == 'float64' for c in result)
    assert result.UnderlyingPrice.tolist() == [800., 1000., 1200.]
    assert result.IntrinsicValue.tolist() == intrinsic
    assert result.ExpirationPayoff.tolist() == payoff
    assert result.GrossProfit.tolist() == profit
    expected_flow = -200640 if position == 'Long' else 200640
    assert result.PremiumCashFlow.tolist() == [expected_flow] * 3
    pd.testing.assert_series_equal(result.GrossProfit,
                                  (result.ExpirationPayoff + result.PremiumCashFlow).rename('GrossProfit'))


@pytest.mark.parametrize('option_type,breakeven', [('Call', 1080), ('Put', 920)])
def test_breakeven_and_multiplier_scaling(option_type, breakeven):
    result = options.calculate_expiration_payoff([breakeven], 1000, 80, option_type, contract_size=1000)
    assert result.GrossProfit.iloc[0] == 0
    scaled = options.calculate_expiration_payoff([breakeven + 10], 1000, 80, option_type,
                                               contract_size=1254, contracts=2)
    base = options.calculate_expiration_payoff([breakeven + 10], 1000, 80, option_type, contract_size=1)
    assert scaled.GrossProfit.iloc[0] == base.GrossProfit.iloc[0] * 2508


def test_zero_prices_premium_order_duplicates_and_input_immutability():
    prices = pd.Series([0., 120., 0., 100.], index=[3, 2, 1, 0])
    before = prices.copy(deep=True)
    result = options.calculate_expiration_payoff(prices, 100, 0, 'Put', contract_size=np.int64(1254))
    pd.testing.assert_series_equal(prices, before)
    assert result.UnderlyingPrice.tolist() == prices.tolist()
    assert result.IntrinsicValue.tolist() == [100., 0., 100., 0.]
    assert result.PremiumCashFlow.eq(0).all()
    assert result.index.equals(pd.RangeIndex(4))


def test_empty_schema_and_export():
    result = options.calculate_expiration_payoff([], 100, 2, 'Call', contract_size=1000)
    assert result.empty and list(result) == COLUMNS
    assert all(str(result[c].dtype) == 'float64' for c in result)
    assert fima.calculate_expiration_payoff is options.calculate_expiration_payoff


@pytest.mark.parametrize('overrides', [
    {'underlying_prices': [-1]}, {'underlying_prices': [np.nan]},
    {'underlying_prices': [np.inf]}, {'underlying_prices': [[100]]},
    {'underlying_prices': '100'}, {'underlying_prices': 100},
    {'underlying_prices': [True]}, {'underlying_prices': [100 + 1j]},
    {'underlying_prices': [None]}, {'underlying_prices': [pd.NA]},
    {'strike_price': 0}, {'strike_price': -1}, {'strike_price': np.inf},
    {'strike_price': True}, {'strike_price': '100'},
    {'premium': -1}, {'premium': np.nan}, {'premium': None}, {'premium': True},
    {'option_type': 'call'}, {'position': 'long'},
    {'contract_size': 0}, {'contract_size': 1254.5}, {'contract_size': True},
    {'contract_size': 1000.0}, {'contracts': -1}, {'contracts': 0},
    {'contracts': 1.5}, {'contracts': True},
])
def test_invalid_arguments(overrides):
    args = dict(underlying_prices=[100], strike_price=100, premium=2,
                option_type='Call', contract_size=1254)
    args.update(overrides)
    with pytest.raises(ValueError):
        options.calculate_expiration_payoff(**args)


def test_nonfinite_cash_flows_raise_instead_of_returning_infinity():
    with pytest.raises(ValueError, match='finite'):
        options.calculate_expiration_payoff([1e308], 100, 1e308, 'Call', contract_size=1000)
