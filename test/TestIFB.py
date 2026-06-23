import pytest
from fima.IFB import (get_risk_free_rate, get_all_bonds_without_coupons, get_all_bonds_with_coupons,
                      get_ifb_equally_weighted_total_index_historical_data, get_ifb_equally_weighted_price_index_historical_data,
                      get_ifb_price_index_historical_data, get_ifb_total_index_historical_data, get_ifb_total_sukuk_index_historical_data,
                      get_sukuk_daily_trades_based_on_bs, get_sukuk_daily_trades_based_on_ct, get_all_crowdfunding_platforms,
                      get_all_crowdfunding_plans, get_ticker_info, get_all_standard_financing_instruments, get_all_special_financing_instruments)


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


def test_get_all_crowdfunding_platforms():
    all_crowdfunding_platforms = get_all_crowdfunding_platforms()
    assert all_crowdfunding_platforms is not None
    assert not all_crowdfunding_platforms.empty
    for column in ['Platform', 'Operator', 'Institute', 'ActivityStartDate', 'LicenseExpiryDate', 'Status',
                   'PhoneNumber', 'Domain']:
        assert column in all_crowdfunding_platforms.columns


@pytest.mark.parametrize("include_descriptions", [True, False])
def test_get_all_crowdfunding_plans(include_descriptions: bool):
    all_crowdfunding_plans = get_all_crowdfunding_plans(include_descriptions=include_descriptions)
    assert all_crowdfunding_plans is not None
    assert not all_crowdfunding_plans.empty
    if include_descriptions:
        for column in ['PlanName', 'Company', 'NationalID', 'Domain', 'Status', 'StartDate', 'EndDate', 'Description',
                       'Platform', 'Operator', 'Institute', 'Description']:
            assert column in all_crowdfunding_plans.columns
    else:
        for column in ['PlanName', 'Company', 'NationalID', 'Domain', 'Status', 'StartDate', 'EndDate', 'Description',
                       'Platform', 'Operator', 'Institute']:
            assert column in all_crowdfunding_plans.columns


@pytest.mark.parametrize("ticker", ['گام051122', 'اخزا402', 'کیش05', 'کارون073'])
def test_get_ticker_info(ticker: str):
    ticker_info, ticker_payments = get_ticker_info(ticker=ticker)
    assert ticker_info is not None
    assert ticker_payments is not None
    assert not ticker_info.empty
    assert not ticker_payments.empty
    for column in ['Section', 'Label', 'Value']:
        assert column in ticker_info.columns
    for column in ['PaymentDate', 'PaymentAmountPerUnit']:
        assert column in ticker_payments.columns


def test_get_all_standard_financing_instruments():
    all_standard_financing_instruments = get_all_standard_financing_instruments()
    assert all_standard_financing_instruments is not None
    assert not all_standard_financing_instruments.empty
    for column in ['Ticker', 'TickerID', 'DetailURL', 'IssueVolume', 'AcceptVolume', 'ParValue', 'CouponPercent',
                   'IssueDate', 'MarketMaker', 'MarketMakingMethod', 'VolatilityRange']:
        assert column in all_standard_financing_instruments.columns


def test_get_all_special_financing_instruments():
    all_special_financing_instruments = get_all_special_financing_instruments()
    assert all_special_financing_instruments is not None
    assert not all_special_financing_instruments.empty
    for column in ['Ticker', 'TickerID', 'DetailURL', 'IssueVolume', 'AcceptVolume', 'ParValue', 'NominalCouponType',
                   'IssueDate', 'MarketMaker', 'Description']:
        assert column in all_special_financing_instruments.columns

