import pytest
from fima.TSETMC import (get_share_changes, get_price_adjustments, get_supervision_lists, get_ticker_historical_shareholders,
                         get_ticker_historical_trades_client_type, get_ticker_historical_market_caps, get_ticker_historical_data,
                         get_ticker_intraday_trades, get_indexes_status, get_index_historical_data, get_index_last_intraday_data,
                         get_index_companies, get_tickers)


def test_get_share_changes():
    share_changes = get_share_changes()
    assert share_changes is not None
    assert not share_changes.empty
    for column in ['NewNumberOfShares', 'OldNumberOfShares', 'Name', 'Ticker', 'JDate']:
        assert column in share_changes.columns


def test_get_price_adjustments():
    price_adjustments = get_price_adjustments()
    assert price_adjustments is not None
    assert not price_adjustments.empty
    for column in ['ClosePrice', 'NotAdjustedClosePrice', 'Ticker', 'Name', 'InstrumentCode', 'JDate']:
        assert column in price_adjustments.columns


def test_get_supervision_lists():
    supervision_lists = get_supervision_lists()
    assert supervision_lists is not None
    assert not supervision_lists.empty
    for column in ['InstrumentCode', 'Reasons', 'Ticker', 'Name']:
        assert column in supervision_lists.columns


@pytest.mark.parametrize("ticker", ['فملی', 'شستا'])
def test_get_ticker_historical_shareholders(ticker):
    ticker_historical_shareholders = get_ticker_historical_shareholders(ticker=ticker)
    assert ticker_historical_shareholders is not None
    assert not ticker_historical_shareholders.empty
    for column in ['Name', 'SharesNo', 'SharePercentage', 'JDate']:
        assert column in ticker_historical_shareholders.columns


@pytest.mark.parametrize("ticker", ['فملی', 'شستا'])
def test_get_ticker_historical_trades_client_type(ticker):
    ticker_historical_trades_client_type = get_ticker_historical_trades_client_type(ticker=ticker)
    assert ticker_historical_trades_client_type is not None
    assert not ticker_historical_trades_client_type.empty
    for column in ['InstitutionalBuyVolume', 'RetailBuyVolume', 'InstitutionalBuyValue', 'RetailBuyValue',
                   'RetailBuyCount', 'InstitutionalSellVolume', 'InstitutionalBuyCount', 'RetailSellVolume',
                   'InstitutionalSellValue', 'RetailSellValue', 'RetailSellCount', 'InstitutionalSellCount']:
        assert column in ticker_historical_trades_client_type.columns


@pytest.mark.parametrize("ticker", ['فملی', 'شستا'])
def test_get_ticker_historical_market_caps(ticker):
    ticker_historical_market_caps = get_ticker_historical_market_caps(ticker=ticker)
    assert ticker_historical_market_caps is not None
    assert not ticker_historical_market_caps.empty
    for column in ['ClosePrice', 'SharesNo', 'MarketCap']:
        assert column in ticker_historical_market_caps.columns


@pytest.mark.parametrize("ticker", ['فملی', 'شستا'])
def test_get_ticker_historical_data(ticker):
    ticker_historical_data = get_ticker_historical_data(ticker=ticker)
    assert ticker_historical_data is not None
    assert not ticker_historical_data.empty
    for column in ['PriceChange', 'MinPrice', 'MaxPrice', 'YesterdayPrice', 'FirstPrice', 'ClosePrice', 'LastPrice',
                   'TransactionNo', 'Volume', 'Value']:
        assert column in ticker_historical_data.columns


@pytest.mark.parametrize("ticker", ['فملی', 'شستا'])
def test_get_ticker_intraday_trades(ticker):
    ticker_intraday_trades = get_ticker_intraday_trades(ticker=ticker)
    assert ticker_intraday_trades is not None
    assert not ticker_intraday_trades.empty
    for column in ['TransitionsNo', 'Time', 'Volume', 'Price', 'Canceled']:
        assert column in ticker_intraday_trades.columns


def test_get_indexes_status():
    indexes_status = get_indexes_status()
    assert indexes_status is not None
    assert not indexes_status.empty
    for column in ['InstrumentCode', 'HourMinute', 'Value', 'MinValue', 'MaxValue', 'PercentageChange', 'Change']:
        assert column in indexes_status.columns


@pytest.mark.parametrize("index", ['شاخص کل', 'شاخص کل فرابورس'])
def test_get_index_historical_data(index):
    index_historical_data = get_index_historical_data(index=index)
    assert index_historical_data is not None
    assert not index_historical_data.empty
    for column in ['Value']:
        assert column in index_historical_data.columns


@pytest.mark.parametrize("index", ['شاخص کل', 'شاخص کل فرابورس'])
def test_get_index_last_intraday_data(index):
    index_last_intraday_data = get_index_last_intraday_data(index=index)
    assert index_last_intraday_data is not None
    assert not index_last_intraday_data.empty
    for column in ['JDate', 'Time', 'Value', 'MinValue', 'MaxValue', 'PercentageChange']:
        assert column in index_last_intraday_data.columns


@pytest.mark.parametrize(["index", "thirty_days_history"],
                         [('شاخص کل', True),
                          ('شاخص کل', False),
                          ('شاخص کل فرابورس', True),
                          ('شاخص کل فرابورس', False)])
def test_get_index_companies(index, thirty_days_history):
    index_companies, index_companies_past_30_days = get_index_companies(index=index, thirty_days_history=thirty_days_history)
    assert index_companies is not None
    assert not index_companies.empty
    for column in ['Name', 'InstrumentCode', 'YesterdayPrice', 'FirstPrice', 'MinPrice', 'MaxPrice', 'ClosePrice',
                   'PriceChange', 'LastPrice', 'TransactionsNo', 'Value', 'Value', 'Value', 'Value']:
        assert column in index_companies.columns
    if thirty_days_history:
        assert index_companies_past_30_days is not None
        assert not index_companies_past_30_days.empty
        for column in ['Ticker', 'JDate', 'ClosePrice']:
            assert column in index_companies_past_30_days.columns


@pytest.mark.parametrize(["tse", "ifb", "details"],
                         [(True, True, True),
                          (True, False, True),
                          (False, True, True,),
                          (True, True, False),
                          (False, True, False),
                          (True, False, False)])
def test_get_tickers(tse, ifb, details):
    tickers = get_tickers(tse=tse, ifb=ifb, details=details)
    if not tse and not ifb:
        assert tickers.empty
    assert tickers is not None
    assert not tickers.empty
    if details:
        for column in ['InstrumentCode', 'Name', 'Market', 'FiscalYear', 'Auditor', 'Website',
           'Capital', 'ActivitySubject']:
            assert column in tickers.columns
    else:
        for column in ['InstrumentCode', 'Name', 'Market']:
            assert column in tickers.columns
