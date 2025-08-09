import pytest
from fima.IFB import (get_risk_free_rate, get_all_bonds_without_coupons, get_all_bonds_with_coupons,
                      get_ifb_equally_weighted_total_index_historical_data, get_ifb_equally_weighted_price_index_historical_data,
                      get_ifb_price_index_historical_data, get_ifb_total_index_historical_data, get_ifb_total_sukuk_index_historical_data,
                      get_sukuk_daily_trades_based_on_bs, get_sukuk_daily_trades_based_on_ct)


def test_get_risk_free_rate_range():
    risk_free_rate = get_risk_free_rate()
    assert isinstance(risk_free_rate, float)
    assert 0.25 <= risk_free_rate <= 0.5  # Typical YTM for Iranian T-bills


@pytest.mark.parametrize("deprecated", [True, False])
def test_get_all_bonds_without_coupons(deprecated):
    all_bonds_without_coupons = get_all_bonds_without_coupons(deprecated=deprecated)
    assert all_bonds_without_coupons is not None
    assert not all_bonds_without_coupons.empty
    for column in ['Ticker', 'LastTradedPrice', 'LastTradedDate', 'MaturityDate', 'YTM', 'SimpleReturn']:
        assert column in all_bonds_without_coupons.columns


@pytest.mark.parametrize("deprecated", [True, False])
def test_get_all_bonds_with_coupons(deprecated):
    all_bonds_with_coupons = get_all_bonds_with_coupons(deprecated=deprecated)
    assert all_bonds_with_coupons is not None
    assert not all_bonds_with_coupons.empty
    for column in ['Ticker', 'LastTradedPrice', 'LastTradedDate', 'MaturityDate', 'YTM']:
        assert column in all_bonds_with_coupons.columns


def test_get_ifb_equally_weighted_total_index_historical_data():
    ifb_equally_weighted_total_index_historical_data = get_ifb_equally_weighted_total_index_historical_data()
    assert ifb_equally_weighted_total_index_historical_data is not None
    assert not ifb_equally_weighted_total_index_historical_data.empty
    for column in ['EquallyWeightedTotalIndex', 'GDate', 'JDate']:
        assert column in ifb_equally_weighted_total_index_historical_data.columns


def test_get_ifb_equally_weighted_price_index_historical_data():
    ifb_equally_weighted_price_index_historical_data = get_ifb_equally_weighted_price_index_historical_data()
    assert ifb_equally_weighted_price_index_historical_data is not None
    assert not ifb_equally_weighted_price_index_historical_data.empty
    for column in ['EquallyWeightedPriceIndex', 'GDate', 'JDate']:
        assert column in ifb_equally_weighted_price_index_historical_data.columns


def test_get_ifb_price_index_historical_data():
    ifb_price_index_historical_data = get_ifb_price_index_historical_data()
    assert ifb_price_index_historical_data is not None
    assert not ifb_price_index_historical_data.empty
    for column in ['PriceIndex', 'GDate', 'JDate']:
        assert column in ifb_price_index_historical_data.columns


def test_get_ifb_total_index_historical_data():
    ifb_total_index_historical_data = get_ifb_total_index_historical_data()
    assert ifb_total_index_historical_data is not None
    assert not ifb_total_index_historical_data.empty
    for column in ['TotalIndex', 'GDate', 'JDate']:
        assert column in ifb_total_index_historical_data.columns


def test_get_ifb_total_sukuk_index_historical_data():
    ifb_total_sukuk_index_historical_data = get_ifb_total_sukuk_index_historical_data()
    assert ifb_total_sukuk_index_historical_data is not None
    assert not ifb_total_sukuk_index_historical_data.empty
    for column in ['TotalSukukIndex', 'GDate', 'JDate']:
        assert column in ifb_total_sukuk_index_historical_data.columns


def test_get_sukuk_daily_trades_based_on_bs():
    sukuk_daily_trades_based_on_bs = get_sukuk_daily_trades_based_on_bs()
    assert sukuk_daily_trades_based_on_bs is not None
    assert not sukuk_daily_trades_based_on_bs.empty
    for column in ['Date', 'Buyer/Seller', 'Government', 'CentralBank', 'Funds', 'Banks', 'Others']:
        assert column in sukuk_daily_trades_based_on_bs.columns


def test_get_sukuk_daily_trades_based_on_ct():
    sukuk_daily_trades_based_on_ct = get_sukuk_daily_trades_based_on_ct()
    assert sukuk_daily_trades_based_on_ct is not None
    assert not sukuk_daily_trades_based_on_ct.empty
    for column in ['Date', 'OpenMarketOperations', 'GovernmentSubscription', 'Others']:
        assert column in sukuk_daily_trades_based_on_ct.columns
