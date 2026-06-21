import pandas as pd
import requests
import jdatetime as jd
from fima.IFB import get_risk_free_rate
from mibian import BS
from scipy.stats import norm
import numpy as np
from typing import Tuple
from fima.TSETMC import _find_instrument_code, get_ticker_historical_data


def _calculate_d1(s, k, t, r_f, sigma) -> float:
    return (np.log(s / k) + (r_f + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))


def _calculate_d2(s, k, t, r_f, sigma) -> float:
    return _calculate_d1(s, k, t, r_f, sigma) - sigma * np.sqrt(t)


def calculate_delta(s, k, t, r_f, sigma, option_type) -> float:
    if option_type == 'Call':
        return norm.cdf(_calculate_d1(s, k, t, r_f, sigma))
    elif option_type == 'Put':
        return -norm.cdf(-(np.log(s / k) + (r_f + sigma ** 2 / 2) * t) / (sigma * np.sqrt(t)))
    return None


def calculate_theta(s, k, t, r_f, sigma, option_type) -> float:
    if option_type == 'Call':
        p1 = - s * norm.pdf(_calculate_d1(s, k, t, r_f, sigma)) * sigma / (2 * np.sqrt(t))
        p2 = r_f * k * np.exp(-r_f * t) * norm.cdf(_calculate_d2(s, k, t, r_f, sigma))
        return p1 - p2
    elif option_type == 'Put':
        p1 = - s * norm.pdf(_calculate_d1(s, k, t, r_f, sigma)) * sigma / (2 * np.sqrt(t))
        p2 = r_f * k * np.exp(-r_f * t) * norm.cdf(-_calculate_d2(s, k, t, r_f, sigma))
        return p1 + p2
    return None


def calculate_gamma(s, k, t, r_f, sigma) -> float:
    return norm.pdf(_calculate_d1(s, k, t, r_f, sigma)) / (s * sigma * np.sqrt(t))


def calculate_vega(s, k, t, r_f, sigma) -> float:
    return s * np.sqrt(t) * norm.pdf(_calculate_d1(s, k, t, r_f, sigma))


def calculate_rho(s, k, t, r_f, sigma, option_type) -> float:
    if option_type == 'Call':
        return k * t * np.exp(-r_f * t) * norm.cdf(_calculate_d2(s, k, t, r_f, sigma))
    elif option_type == 'Put':
        return -k * t * np.exp(-r_f * t) * norm.cdf(-_calculate_d2(s, k, t, r_f, sigma))
    return None


def ticker_info(ticker: str) -> dict:
    ticker_info_df = pd.DataFrame(columns=['UATicker', 'StrikePrice', 'MaturityDate', 'DaysToMaturity', 'Type'], index=[0])
    ticker_instrument_code = _find_instrument_code(search_key=ticker, trade_type='Ordinary')
    ticker_info_url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/{ticker_instrument_code}"
    instrument_code_info = requests.get(url=ticker_info_url, timeout=15).json()['instrumentInfo']
    ticker_info_df.loc[0, 'UATicker'] = instrument_code_info['lVal30'].split('-')[0].split(' ')[1]
    ticker_info_df.loc[0, 'StrikePrice'] = int(instrument_code_info['lVal30'].split('-')[1])
    maturity_date = instrument_code_info['lVal30'].split('-')[2].split('/')
    ticker_info_df.loc[0, 'MaturityDate'] = jd.date(year=int(maturity_date[0]), month=int(maturity_date[1]), day=int(maturity_date[2]))
    ticker_info_df.loc[0, 'DaysToMaturity'] = (ticker_info_df.loc[0, 'MaturityDate'] - jd.date.today()).days
    ticker_info_df.loc[0, 'Type'] = 'Call' if instrument_code_info['lVal30'].split('-')[0].split(' ')[0][-1] == 'خ' else 'Put'

    ticker_instrument_info_url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{ticker_instrument_code}"
    ticker_instrument_info = requests.get(ticker_instrument_info_url).json()['closingPriceInfo']
    ticker_info_df.loc[0, 'LastPrice'] = ticker_instrument_info['pDrCotVal']

    ua_ticker_instrument_code = _find_instrument_code(search_key=ticker_info_df.loc[0, 'UATicker'], trade_type='Ordinary')
    ua_ticker_instrument_info_url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{ua_ticker_instrument_code}"
    ua_ticker_instrument_info = requests.get(ua_ticker_instrument_info_url).json()['closingPriceInfo']
    ticker_info_df.loc[0, 'UALastPrice'] = ua_ticker_instrument_info['pDrCotVal']

    return ticker_info_df


def _calculate_row_wise_implied_volatility(row) -> float:
    # print(f"Calculating {row['Ticker']} implied volatility...")
    return get_implied_volatility(ticker=row['Ticker'], _ticker_info_df=row.to_frame().T, r_f=row['RiskFreeRate'],
                                  _ua_historical_data=row['HistoricalData-UA'])


def get_implied_volatility(ticker: str, _ticker_info_df: pd.DataFrame = None, volatility_window_size: int = None,
                       r_f: float = None, minimum_required_history: int = 30, _ua_historical_data: pd.DataFrame = None) -> float:

    if _ticker_info_df is None:
        _ticker_info_df = ticker_info(ticker=ticker)

    if _ua_historical_data is None:
        try:
            _, _ua_historical_data = download_historical_data(ticker)
        except requests.exceptions.HTTPError:
            print(f'Couldn\'t download historical data for: {ticker}')
            return None

        if _ua_historical_data is None:
            return None

    if r_f is None:
        r_f = get_risk_free_rate()

    stock_days_available = len(_ua_historical_data)
    if stock_days_available < minimum_required_history:
        print(
            f"Not enough stock history for {_ticker_info_df['UATicker']} ({stock_days_available} days available, "
            f"{minimum_required_history} days required).")
        return None

    days_to_maturity = _ticker_info_df['DaysToMaturity'].values[0]
    if days_to_maturity < 10:
        print(f"Option {ticker} expires too soon ({days_to_maturity} days left). Calculated implied volatility may not be reliable.")
        return None

    max_safe_window = min(stock_days_available, days_to_maturity)
    if volatility_window_size is None:
        volatility_window_size = min(30, max(5, max_safe_window // 2))  # dynamic choice
    else:
        volatility_window_size = min(volatility_window_size, max_safe_window)  # force safe

    if volatility_window_size < 5:
        print(f"Volatility window too small ({volatility_window_size} days). Cannot calculate meaningful volatility for {ticker}.")
        return None

    sigma = _calculate_volatility(_ua_historical_data, volatility_window_size)
    s = _ticker_info_df['LastPrice-UA'].values[0]
    k = _ticker_info_df['StrikePrice'].values[0]
    t = days_to_maturity / 365
    option_type = _ticker_info_df['Type'].values[0]
    premium = _ticker_info_df['LastPrice'].values[0]

    if sigma == 0 or t == 0:
        print("Zero volatility or expired option.")
        return None

    try:
        if option_type == 'Call':
            ticker_implied_volatility = BS([s, k, r_f, t * 365], callPrice=premium)
        elif option_type == 'Put':
            ticker_implied_volatility = BS([s, k, r_f, t * 365], putPrice=premium)
        else:
            print('Option type is not a valid one.')
            return None
    except (UnboundLocalError, IndexError):
        print('mibian library error.')
        return None
    return ticker_implied_volatility.impliedVolatility / 100


def get_greeks(ticker: str, _ticker_info_df: pd.DataFrame = None, volatility_window_size: int = None, r_f: float = None,
           minimum_required_history: int = 30, _ua_historical_data: pd.DataFrame = None) -> pd.Series:

    delta, gamma, theta, vega, rho = (None, None, None, None, None)

    if _ticker_info_df is None:
        _ticker_info_df = ticker_info(ticker=ticker)

    if _ua_historical_data is None:
        try:
            _, _ua_historical_data = download_historical_data(ticker)
        except requests.exceptions.HTTPError:
            print(f'Couldn\'t download historical data for: {ticker}')
            return pd.Series({'Delta': delta, 'Gamma': gamma, 'Theta': theta, 'Vega': vega, 'Rho': rho})

        if _ua_historical_data is None:
            return pd.Series({'Delta': delta, 'Gamma': gamma, 'Theta': theta, 'Vega': vega, 'Rho': rho})

    if r_f is None:
        r_f = get_risk_free_rate()

    stock_days_available = len(_ua_historical_data)
    if stock_days_available < minimum_required_history:
        print(
            f"Not enough stock history for {_ticker_info_df['UATicker']} ({stock_days_available} days available, "
            f"{minimum_required_history} days required).")
        return pd.Series({'Delta': delta, 'Gamma': gamma, 'Theta': theta, 'Vega': vega, 'Rho': rho})

    days_to_maturity = _ticker_info_df['DaysToMaturity'].values[0]
    if days_to_maturity < 10:
        print(f"Option {ticker} expires too soon ({days_to_maturity} days left). Calculated greeks may not be reliable.")
        return pd.Series({'Delta': delta, 'Gamma': gamma, 'Theta': theta, 'Vega': vega, 'Rho': rho})

    max_safe_window = min(stock_days_available, days_to_maturity)
    if volatility_window_size is None:
        volatility_window_size = min(30, max(5, max_safe_window // 2))  # dynamic choice
    else:
        volatility_window_size = min(volatility_window_size, max_safe_window)  # force safe

    if volatility_window_size < 5:
        print(
            f"Volatility window too small ({volatility_window_size} days). Cannot calculate meaningful volatility for {ticker}.")
        return pd.Series({'Delta': delta, 'Gamma': gamma, 'Theta': theta, 'Vega': vega, 'Rho': rho})

    sigma = _calculate_volatility(_ua_historical_data, volatility_window_size)
    s = _ticker_info_df['LastPrice-UA'].values[0]
    k = _ticker_info_df['StrikePrice'].values[0]
    t = days_to_maturity / 365
    option_type = _ticker_info_df['Type'].values[0]

    if sigma == 0 or t == 0:
        print("Zero volatility or expired option.")
        return pd.Series({'Delta': delta, 'Gamma': gamma, 'Theta': theta, 'Vega': vega, 'Rho': rho})

    delta = calculate_delta(s, k, t, sigma, r_f, option_type)
    gamma = calculate_gamma(s, k, t, sigma, r_f)
    theta = calculate_theta(s, k, t, sigma, r_f, option_type)
    vega = calculate_vega(s, k, t, sigma, r_f)
    rho = calculate_rho(s, k, t, sigma, r_f, option_type)

    return pd.Series({'Delta': delta, 'Gamma': gamma, 'Theta': theta, 'Vega': vega, 'Rho': rho})


def _calculate_row_wise_greeks(row) -> pd.Series:
    # print(f"Calculating {row['Ticker']} greeks...")
    return get_greeks(ticker=row['Ticker'], _ticker_info_df=row.to_frame().T, r_f=row['RiskFreeRate'], _ua_historical_data=row['HistoricalData-UA'])


def _calculate_row_wise_bsm(row) -> pd.Series:
    # print(f"Calculating {row['Ticker']} price with Black, Scholes and Merton model...")
    volatility, bsm_price = black_scholes_merton(ticker=row['Ticker'], _ticker_info_df=row.to_frame().T,
                                                 r_f=row['RiskFreeRate'], _ua_historical_data=row['HistoricalData-UA'])
    return pd.Series({'Volatility': volatility, 'BSMPrice': bsm_price})


def _calculate_volatility(ua_historical_data, window_size) -> float:
    log_returns = np.log(ua_historical_data['ClosePrice'] / ua_historical_data['ClosePrice'].shift(1))
    volatility = np.sqrt(window_size) * log_returns.std()
    return volatility


def calculate_black_scholes_merton(s, k, t, sigma, r_f, option_type) \
        -> Tuple[float, float]:
    d1 = _calculate_d1(s, k, t, r_f, sigma)
    d2 = _calculate_d2(s, k, t, r_f, sigma)

    if option_type == 'Call':
        price = s * norm.cdf(d1) - k * np.exp(-r_f * t) * norm.cdf(d2)
    elif option_type == 'Put':
        price = k * np.exp(-r_f * t) * norm.cdf(-d2) - s * norm.cdf(-d1)
    else:
        raise ValueError(f"Unknown option type '{option_type}'. Expected 'Call' or 'Put'.")
    return price


def black_scholes_merton(ticker: str, _ticker_info_df: pd.DataFrame = None, volatility_window_size: int = None,
                         r_f: float = None, minimum_required_history: int = 30,
                         _ua_historical_data: pd.DataFrame = None) -> Tuple[float, float]:

    if _ticker_info_df is None:
        _ticker_info_df = ticker_info(ticker=ticker)

    if _ua_historical_data is None:
        try:
            _, _ua_historical_data = download_historical_data(ticker)
        except requests.exceptions.HTTPError:
            print(f'Couldn\'t download historical data for: {ticker}')
            return None, None

        if _ua_historical_data is None:
            return None, None

    if r_f is None:
        r_f = get_risk_free_rate()

    stock_days_available = len(_ua_historical_data)
    if stock_days_available < minimum_required_history:
        print(
            f"Not enough stock history for {_ticker_info_df['UATicker']} ({stock_days_available} days available, "
            f"{minimum_required_history} days required).")
        return None, None

    days_to_maturity = _ticker_info_df['DaysToMaturity'].values[0]
    if days_to_maturity < 10:
        print(f"Option {ticker} expires too soon ({days_to_maturity} days left). BSM model may not be reliable.")
        return None, None

    max_safe_window = min(stock_days_available, days_to_maturity)
    if volatility_window_size is None:
        volatility_window_size = min(30, max(5, max_safe_window // 2))  # dynamic choice
    else:
        volatility_window_size = min(volatility_window_size, max_safe_window)  # force safe

    if volatility_window_size < 5:
        print(
            f"Volatility window too small ({volatility_window_size} days). Cannot calculate meaningful volatility for {ticker}.")
        return None, None

    sigma = _calculate_volatility(_ua_historical_data, volatility_window_size)
    s = _ticker_info_df['LastPrice-UA'].values[0]
    k = _ticker_info_df['StrikePrice'].values[0]
    t = days_to_maturity / 365
    option_type = _ticker_info_df['Type'].values[0]

    if sigma == 0 or t == 0:
        print("Zero volatility or expired option. Returning price = 0.")
        return 0, 0

    price = calculate_black_scholes_merton(s, k, t, sigma, r_f, option_type)

    return sigma, price


def download_all_underlying_assets(_all_options_market_watch: pd.DataFrame = None, market: str = 'All') -> pd.DataFrame:
    if _all_options_market_watch is None:
        _all_options_market_watch = download_market_watch(market=market, stack='Horizontal', j_date=True)
    all_underlying_assets = _all_options_market_watch.loc[:, [column for column in _all_options_market_watch.columns if column.endswith('-UA')]]
    all_underlying_assets.drop_duplicates(inplace=True)
    all_underlying_assets.reset_index(inplace=True, drop=True)
    all_underlying_assets.columns = [column.replace('-UA', '') for column in all_underlying_assets.columns]
    return all_underlying_assets


def download_historical_data(ticker: str, start_date: str = None, end_date: str = None) -> Tuple[pd.DataFrame, pd.DataFrame]:

    ticker_instrument_code = _find_instrument_code(search_key=ticker, trade_type='Ordinary')
    ticker_historical_data_url = f'https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/{ticker_instrument_code}/0'

    response = requests.get(ticker_historical_data_url)
    response.raise_for_status()

    data = response.json()
    ticker_historical_data = pd.json_normalize(data["closingPriceDaily"])

    if ticker_historical_data.empty:
        print(f'Couldn\'t download historical data for ticker: {ticker}')
        return None, None

    ticker_historical_data.columns = ['PriceChange', 'MinPrice', 'MaxPrice', 'YesterdayPrice', 'FirstPrice', 'Last', 'ID',
                                      'InstrumentCode', 'Date', 'H', 'ClosePrice', 'I', 'Y', 'LastPrice', 'Quantity', 'Volume', 'Value']
    ticker_historical_data = ticker_historical_data.loc[:, ['Date', 'Quantity', 'Volume', 'Value', 'MinPrice', 'MaxPrice',
                                                            'FirstPrice', 'LastPrice', 'ClosePrice']]
    ticker_historical_data['Date'] =  pd.to_datetime(ticker_historical_data['Date'].astype(str), format='%Y%m%d')
    ticker_historical_data['Date'] = ticker_historical_data['Date'].dt.date
    ticker_historical_data['Date'] = \
        ticker_historical_data['Date'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))

    # underlying asset
    ticker_info_url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/{ticker_instrument_code}"
    underlying_asset_ticker = requests.get(url=ticker_info_url, timeout=15).json()['instrumentInfo']['lVal30'].split('-')[0].split(' ')[1]
    ua_instrument_code = _find_instrument_code(search_key=underlying_asset_ticker, trade_type='Ordinary')
    ua_ticker_historical_data_url = f'https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/{ua_instrument_code}/0'
    response = requests.get(url=ua_ticker_historical_data_url, timeout=15)
    response.raise_for_status()
    data = response.json()
    ua_ticker_historical_data = pd.json_normalize(data["closingPriceDaily"])

    if ua_ticker_historical_data.empty:
        print(f'Couldn\'t download historical data for ticker: {ticker}')
        return None, None

    ua_ticker_historical_data.columns = ['PriceChange', 'MinPrice', 'MaxPrice', 'YesterdayPrice', 'FirstPrice', 'Last', 'ID',
                                      'InstrumentCode', 'Date', 'H', 'ClosePrice', 'I', 'Y', 'LastPrice', 'Quantity', 'Volume', 'Value']
    ua_ticker_historical_data = ua_ticker_historical_data.loc[:, ['Date', 'Quantity', 'Volume', 'Value', 'MinPrice', 'MaxPrice',
                                                            'FirstPrice', 'LastPrice', 'ClosePrice']]
    ua_ticker_historical_data['Date'] =  pd.to_datetime(ua_ticker_historical_data['Date'].astype(str), format='%Y%m%d')
    ua_ticker_historical_data['Date'] = ua_ticker_historical_data['Date'].dt.date
    ua_ticker_historical_data['Date'] = \
        ua_ticker_historical_data['Date'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))

    if start_date is not None and end_date is not None:
        start_date_year, start_date_month, start_date_day = [int(date) for date in start_date.split('-')]
        start_date = jd.date(start_date_year, start_date_month, start_date_day)

        end_date_year, end_date_month, end_date_day = [int(date) for date in end_date.split('-')]
        end_date = jd.date(end_date_year, end_date_month, end_date_day)

        ticker_historical_data = ticker_historical_data[(ticker_historical_data['Date'] >= start_date) & (ticker_historical_data['Date'] <= end_date)]
        ua_ticker_historical_data = ua_ticker_historical_data[(ua_ticker_historical_data['Date'] >= start_date) & (ua_ticker_historical_data['Date'] <= end_date)]

    ticker_historical_data.reset_index(inplace=True, drop=True)
    ua_ticker_historical_data.reset_index(inplace=True, drop=True)

    return ticker_historical_data, ua_ticker_historical_data


def download_chain_contracts(underlying_ticker: str, j_date: str = True, bsm: bool = False, greeks: bool = False,
                             implied_volatility: bool = False) -> pd.DataFrame:
    try:
        url = "https://cdn.tsetmc.com/api/Instrument/GetInstrumentOptionMarketWatch/0"
        response = requests.get(url)
        response.raise_for_status()

        data = response.json()
        all_options_market_watch = pd.json_normalize(data["instrumentOptMarketWatch"])

        all_options_market_watch.columns = ['InstrumentCode-P', 'InstrumentCode-C', 'ContractSize', 'InstrumentCode-UA',
                                            'Ticker-P', 'Name-P', 'Volume-P', 'Quantity-P', 'Value-P', 'NotionalValue-P',
                                            'ClosePrice-P', 'YesterdayPrice-P', 'OpenPositions-P', 'LastPrice-P',
                                            'Ticker-UA', 'ClosePrice-UA', 'LastPrice-UA', 'YesterdayPrice-UA',
                                            'BeginDate', 'EndDate', 'StrikePrice', 'DaysToMaturity', 'LastPrice-C', 'OpenPositions-C',
                                            'ClosePrice-C', 'YesterdayPrice-C', 'NotionalValue-C', 'Value-C', 'Quantity-C',
                                            'Volume-C', 'Name-C', 'Ticker-C', 'BidPrice-P', 'BidVolume-P', 'AskPrice-P',
                                            'AskVolume-P', 'BidPrice-C', 'BidVolume-C', 'AskPrice-C', 'AskVolume-C',
                                            'YesterdayOpenPositions-C', 'YesterdayOpenPositions-P']
        chain_contracts = all_options_market_watch[all_options_market_watch['Ticker-UA'] == underlying_ticker].copy()

        chain_contracts['URL-P'] = chain_contracts['InstrumentCode-P'].apply(lambda ins_code: f'https://tsetmc.ir/instInfo/{ins_code}')
        chain_contracts['URL-C'] = chain_contracts['InstrumentCode-C'].apply(lambda ins_code: f'https://tsetmc.ir/instInfo/{ins_code}')
        chain_contracts['URL-UA'] = chain_contracts['InstrumentCode-UA'].apply(lambda ins_code: f'https://tsetmc.ir/instInfo/{ins_code}')

        chain_contracts['BeginDate'] =  pd.to_datetime(chain_contracts['BeginDate'].astype(str), format='%Y%m%d')
        chain_contracts['BeginDate'] = chain_contracts['BeginDate'].dt.date
        chain_contracts['EndDate'] =  pd.to_datetime(chain_contracts['EndDate'].astype(str), format='%Y%m%d')
        chain_contracts['EndDate'] = chain_contracts['EndDate'].dt.date

        if j_date:
            chain_contracts['BeginDate'] = \
                chain_contracts['BeginDate'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
            chain_contracts['EndDate'] = \
                chain_contracts['EndDate'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))

        conditions = [chain_contracts['LastPrice-UA'] > chain_contracts['StrikePrice'],
                      chain_contracts['LastPrice-UA'] < chain_contracts['StrikePrice']]
        choices = ['ITM', 'OTM']
        default = 'ATM'
        chain_contracts['Status-C'] = np.select(conditions, choices, default=default)

        conditions = [chain_contracts['LastPrice-UA'] > chain_contracts['StrikePrice'],
                      chain_contracts['LastPrice-UA'] < chain_contracts['StrikePrice']]
        choices = ['OTM', 'ITM']
        default = 'ATM'
        chain_contracts['Status-P'] = np.select(conditions, choices, default=default)

        call_chain_contracts_columns = ['Ticker-C', 'Name-C', 'InstrumentCode-C', 'Status-C', 'Volume-C', 'Quantity-C', 'Value-C',
                                             'NotionalValue-C', 'OpenPositions-C', 'ClosePrice-C', 'LastPrice-C', 'YesterdayPrice-C',
                                             'BidPrice-C', 'BidVolume-C', 'AskPrice-C', 'AskVolume-C', 'URL-C']
        ua_chain_contracts_columns = ['ContractSize', 'StrikePrice', 'DaysToMaturity', 'BeginDate', 'EndDate',
                                            'Ticker-UA', 'InstrumentCode-UA', 'ClosePrice-UA', 'LastPrice-UA',
                                            'YesterdayPrice-UA', 'URL-UA']
        put_chain_contracts_columns = ['Ticker-P', 'Name-P', 'InstrumentCode-P', 'Status-P', 'Volume-P', 'Quantity-P', 'Value-P',
                                             'NotionalValue-P', 'OpenPositions-P', 'ClosePrice-P', 'LastPrice-P', 'YesterdayPrice-P',
                                             'BidPrice-P', 'BidVolume-P', 'AskPrice-P', 'AskVolume-P', 'URL-P']


        if bsm or greeks or implied_volatility:
            print(f'Downloading {underlying_ticker} historical data...')
            ua_historical_data = get_ticker_historical_data(
                ticker=underlying_ticker).reset_index().rename(columns={'JDate': 'Date'}).loc[:, ['Date', 'ClosePrice']].copy()
            print(f'Historical data downloaded for {underlying_ticker}.')

            chain_contracts['HistoricalData-UA'] = None
            for index, row in chain_contracts.iterrows():
                chain_contracts.at[index, 'HistoricalData-UA'] = ua_historical_data.copy()
            ua_chain_contracts_columns.append('HistoricalData-UA')

            call_chain_contracts = chain_contracts.loc[:, call_chain_contracts_columns + ua_chain_contracts_columns].copy()
            put_chain_contracts = chain_contracts.loc[:, put_chain_contracts_columns + ua_chain_contracts_columns].copy()
            call_chain_contracts['Type'] = 'Call'
            call_chain_contracts.columns = call_chain_contracts.columns.map(lambda column: column.replace('-C', ''))
            call_chain_contracts_columns.append('Type')
            put_chain_contracts['Type'] = 'Put'
            put_chain_contracts.columns = put_chain_contracts.columns.map(lambda column: column.replace('-P', ''))
            put_chain_contracts_columns.append('Type')

            risk_free_rate = get_risk_free_rate()
            call_chain_contracts['RiskFreeRate'] = risk_free_rate
            put_chain_contracts['RiskFreeRate'] = risk_free_rate
            ua_chain_contracts_columns.append('RiskFreeRate')

            if bsm:
                call_chain_contracts[['Volatility', 'BSMPrice']] = call_chain_contracts.apply(_calculate_row_wise_bsm, axis=1)
                call_chain_contracts_columns.append(['Volatility', 'BSMPrice'])
                put_chain_contracts[['Volatility', 'BSMPrice']] = put_chain_contracts.apply(_calculate_row_wise_bsm, axis=1)
                put_chain_contracts_columns.append(['Volatility', 'BSMPrice'])

            if greeks:
                call_chain_contracts[['Delta', 'Gamma', 'Theta', 'Vega', 'Rho']] = call_chain_contracts.apply(_calculate_row_wise_greeks, axis=1)
                call_chain_contracts_columns.append(['Delta', 'Gamma', 'Theta', 'Vega', 'Rho'])
                put_chain_contracts[['Delta', 'Gamma', 'Theta', 'Vega', 'Rho']] = put_chain_contracts.apply(_calculate_row_wise_greeks, axis=1)
                put_chain_contracts_columns.append(['Delta', 'Gamma', 'Theta', 'Vega', 'Rho'])

            if implied_volatility:
                call_chain_contracts['ImpliedVolatility'] = call_chain_contracts.apply(_calculate_row_wise_implied_volatility, axis=1)
                call_chain_contracts_columns.append(['ImpliedVolatility'])
                put_chain_contracts['ImpliedVolatility'] = put_chain_contracts.apply(_calculate_row_wise_implied_volatility, axis=1)
                put_chain_contracts_columns.append(['ImpliedVolatility'])

            call_chain_contracts.drop('HistoricalData-UA', inplace=True, axis=1)
            put_chain_contracts.drop('HistoricalData-UA', inplace=True, axis=1)
            ua_chain_contracts_columns.remove('HistoricalData-UA')

            call_chain_contracts.columns = [f"{column}-C" for column in call_chain_contracts.columns]
            put_chain_contracts.columns = [f"{column}-P" for column in put_chain_contracts.columns]
            chain_contracts = pd.merge(call_chain_contracts, put_chain_contracts,
                                                left_index=True, right_index=True, how='inner')
            chain_contracts.drop([f"{column}-P" for column in ua_chain_contracts_columns], axis=1, inplace=True)
            chain_contracts.columns = [column.replace('-C', '')
                                                if column[:-2] in ua_chain_contracts_columns else column for column in chain_contracts.columns]
            chain_contracts.drop(['Type-C', 'Type-P'], axis=1, inplace=True)
        else:
            chain_contracts = chain_contracts.loc[:, call_chain_contracts_columns + ua_chain_contracts_columns + put_chain_contracts_columns]

        chain_contracts.reset_index(inplace=True, drop=True)
        chain_contracts.sort_values(by=['EndDate', 'StrikePrice'], inplace=True, ignore_index=True)
        return chain_contracts
    except Exception as e:
        print(f"Failed to get the market watch with the error:\n {e}")
        return None


def download_market_watch(market: str = 'All', stack: str = 'Horizontal', j_date: bool = True,
                          bsm: str = False, greeks: bool = False, implied_volatility: bool = False) -> pd.DataFrame:

    if market == 'TSE':
        url = "https://cdn.tsetmc.com/api/Instrument/GetInstrumentOptionMarketWatch/1"
    elif market == 'IFB':
        url = "https://cdn.tsetmc.com/api/Instrument/GetInstrumentOptionMarketWatch/2"
    else:       # 'All'
        url = "https://cdn.tsetmc.com/api/Instrument/GetInstrumentOptionMarketWatch/0"

    try:
        response = requests.get(url)
        response.raise_for_status()

        data = response.json()
        all_options_market_watch = pd.json_normalize(data["instrumentOptMarketWatch"])

        all_options_market_watch.columns = ['InstrumentCode-P', 'InstrumentCode-C', 'ContractSize', 'InstrumentCode-UA',
                                            'Ticker-P', 'Name-P', 'Volume-P', 'Quantity-P', 'Value-P', 'NotionalValue-P',
                                            'ClosePrice-P', 'YesterdayPrice-P', 'OpenPositions-P', 'LastPrice-P',
                                            'Ticker-UA', 'ClosePrice-UA', 'LastPrice-UA', 'YesterdayPrice-UA',
                                            'BeginDate', 'EndDate', 'StrikePrice', 'DaysToMaturity', 'LastPrice-C', 'OpenPositions-C',
                                            'ClosePrice-C', 'YesterdayPrice-C', 'NotionalValue-C', 'Value-C', 'Quantity-C',
                                            'Volume-C', 'Name-C', 'Ticker-C', 'BidPrice-P', 'BidVolume-P', 'AskPrice-P',
                                            'AskVolume-P', 'BidPrice-C', 'BidVolume-C', 'AskPrice-C', 'AskVolume-C',
                                            'YesterdayOpenPositions-C', 'YesterdayOpenPositions-P']
        all_options_market_watch['URL-P'] = all_options_market_watch['InstrumentCode-P'].apply(lambda ins_code: f'https://tsetmc.ir/instInfo/{ins_code}')
        all_options_market_watch['URL-C'] = all_options_market_watch['InstrumentCode-C'].apply(lambda ins_code: f'https://tsetmc.ir/instInfo/{ins_code}')
        all_options_market_watch['URL-UA'] = all_options_market_watch['InstrumentCode-UA'].apply(lambda ins_code: f'https://tsetmc.ir/instInfo/{ins_code}')

        all_options_market_watch['BeginDate'] =  pd.to_datetime(all_options_market_watch['BeginDate'].astype(str), format='%Y%m%d')
        all_options_market_watch['BeginDate'] = all_options_market_watch['BeginDate'].dt.date
        all_options_market_watch['EndDate'] =  pd.to_datetime(all_options_market_watch['EndDate'].astype(str), format='%Y%m%d')
        all_options_market_watch['EndDate'] = all_options_market_watch['EndDate'].dt.date

        if j_date:
            all_options_market_watch['BeginDate'] = \
                all_options_market_watch['BeginDate'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
            all_options_market_watch['EndDate'] = \
                all_options_market_watch['EndDate'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))

        conditions = [all_options_market_watch['LastPrice-UA'] > all_options_market_watch['StrikePrice'],
                      all_options_market_watch['LastPrice-UA'] < all_options_market_watch['StrikePrice']]
        choices = ['ITM', 'OTM']
        default = 'ATM'
        all_options_market_watch['Status-C'] = np.select(conditions, choices, default=default)

        conditions = [all_options_market_watch['LastPrice-UA'] > all_options_market_watch['StrikePrice'],
                      all_options_market_watch['LastPrice-UA'] < all_options_market_watch['StrikePrice']]
        choices = ['OTM', 'ITM']
        default = 'ATM'
        all_options_market_watch['Status-P'] = np.select(conditions, choices, default=default)

        call_options_market_watch_columns = ['Ticker-C', 'Name-C', 'InstrumentCode-C', 'Status-C', 'Volume-C', 'Quantity-C', 'Value-C',
                                             'NotionalValue-C', 'OpenPositions-C', 'ClosePrice-C', 'LastPrice-C', 'YesterdayPrice-C',
                                             'BidPrice-C', 'BidVolume-C', 'AskPrice-C', 'AskVolume-C', 'URL-C']
        ua_market_watch_columns = ['ContractSize', 'StrikePrice', 'DaysToMaturity', 'BeginDate', 'EndDate',
                                            'Ticker-UA', 'InstrumentCode-UA', 'ClosePrice-UA', 'LastPrice-UA',
                                            'YesterdayPrice-UA', 'URL-UA']
        put_options_market_watch_columns = ['Ticker-P', 'Name-P', 'InstrumentCode-P', 'Status-P', 'Volume-P', 'Quantity-P', 'Value-P',
                                             'NotionalValue-P', 'OpenPositions-P', 'ClosePrice-P', 'LastPrice-P', 'YesterdayPrice-P',
                                             'BidPrice-P', 'BidVolume-P', 'AskPrice-P', 'AskVolume-P', 'URL-P']


        if bsm or greeks or implied_volatility:
            uas_historical_data = {}
            all_uas = download_all_underlying_assets(all_options_market_watch.copy(), market=market)
            print('Starting to download historical data for all tickers...')
            for ua in all_uas['Ticker']:
                print(f'Downloading {ua} historical data...')
                uas_historical_data[ua] = get_ticker_historical_data(
                    ticker=ua).reset_index().rename(columns={'JDate': 'Date'}).loc[:, ['Date', 'ClosePrice']].copy()
            print('Historical data downloaded for all underlying assets.')

            all_options_market_watch['HistoricalData-UA'] = None
            for index, row in all_options_market_watch.iterrows():
                all_options_market_watch.at[index, 'HistoricalData-UA'] = uas_historical_data[row['Ticker-UA']].copy()
            ua_market_watch_columns.append('HistoricalData-UA')

            call_options_market_watch = all_options_market_watch.loc[:, call_options_market_watch_columns + ua_market_watch_columns].copy()
            put_options_market_watch = all_options_market_watch.loc[:, put_options_market_watch_columns + ua_market_watch_columns].copy()
            call_options_market_watch['Type'] = 'Call'
            call_options_market_watch.columns = call_options_market_watch.columns.map(lambda column: column.replace('-C', ''))
            call_options_market_watch_columns.append('Type')
            put_options_market_watch['Type'] = 'Put'
            put_options_market_watch.columns = put_options_market_watch.columns.map(lambda column: column.replace('-P', ''))
            put_options_market_watch_columns.append('Type')

            risk_free_rate = get_risk_free_rate()
            call_options_market_watch['RiskFreeRate'] = risk_free_rate
            put_options_market_watch['RiskFreeRate'] = risk_free_rate
            ua_market_watch_columns.append('RiskFreeRate')

            if bsm:
                print('\n\nCalculating BSMs...')
                call_options_market_watch[['Volatility', 'BSMPrice']] = call_options_market_watch.apply(_calculate_row_wise_bsm, axis=1)
                call_options_market_watch_columns.append(['Volatility', 'BSMPrice'])
                put_options_market_watch[['Volatility', 'BSMPrice']] = put_options_market_watch.apply(_calculate_row_wise_bsm, axis=1)
                put_options_market_watch_columns.append(['Volatility', 'BSMPrice'])

            if greeks:
                print('\n\nCalculating Greeks...')
                call_options_market_watch[['Delta', 'Gamma', 'Theta', 'Vega', 'Rho']] = call_options_market_watch.apply(_calculate_row_wise_greeks, axis=1)
                call_options_market_watch_columns.append(['Delta', 'Gamma', 'Theta', 'Vega', 'Rho'])
                put_options_market_watch[['Delta', 'Gamma', 'Theta', 'Vega', 'Rho']] = put_options_market_watch.apply(_calculate_row_wise_greeks, axis=1)
                put_options_market_watch_columns.append(['Delta', 'Gamma', 'Theta', 'Vega', 'Rho'])

            if implied_volatility:
                print('\n\nCalculating IVs...')
                call_options_market_watch['ImpliedVolatility'] = call_options_market_watch.apply(_calculate_row_wise_implied_volatility, axis=1)
                call_options_market_watch_columns.append(['ImpliedVolatility'])
                put_options_market_watch['ImpliedVolatility'] = put_options_market_watch.apply(_calculate_row_wise_implied_volatility, axis=1)
                put_options_market_watch_columns.append(['ImpliedVolatility'])

            call_options_market_watch.drop('HistoricalData-UA', inplace=True, axis=1)
            put_options_market_watch.drop('HistoricalData-UA', inplace=True, axis=1)
            ua_market_watch_columns.remove('HistoricalData-UA')

            if stack == 'Vertical':
                all_options_market_watch = pd.concat([call_options_market_watch, put_options_market_watch], axis=0, ignore_index=True)
            else:   # 'Horizontal'
                call_options_market_watch.columns = [f"{column}-C" for column in call_options_market_watch.columns]
                put_options_market_watch.columns = [f"{column}-P" for column in put_options_market_watch.columns]
                all_options_market_watch = pd.merge(call_options_market_watch, put_options_market_watch,
                                                    left_index=True, right_index=True, how='inner')
                all_options_market_watch.drop([f"{column}-P" for column in ua_market_watch_columns], axis=1, inplace=True)
                all_options_market_watch.columns = [column.replace('-C', '')
                                                    if column[:-2] in ua_market_watch_columns else column for column in all_options_market_watch.columns]
                all_options_market_watch.drop(['Type-C', 'Type-P'], axis=1, inplace=True)
        else:
            if stack == 'Vertical':
                call_options_market_watch = all_options_market_watch.loc[:, call_options_market_watch_columns + ua_market_watch_columns].copy()
                put_options_market_watch = all_options_market_watch.loc[:, put_options_market_watch_columns + ua_market_watch_columns].copy()
                call_options_market_watch['Type'] = 'Call'
                call_options_market_watch.columns = call_options_market_watch.columns.map(lambda column: column.replace('-C', ''))
                call_options_market_watch_columns.append('Type')
                put_options_market_watch['Type'] = 'Put'
                put_options_market_watch.columns = put_options_market_watch.columns.map(lambda column: column.replace('-P', ''))
                put_options_market_watch_columns.append('Type')
                all_options_market_watch = pd.concat([call_options_market_watch, put_options_market_watch], axis=0, ignore_index=True)
            else:   # Horizontal
                all_options_market_watch = all_options_market_watch.loc[:, call_options_market_watch_columns +
                                                                           ua_market_watch_columns +
                                                                           put_options_market_watch_columns]

        all_options_market_watch.reset_index(inplace=True, drop=True)
        all_options_market_watch.sort_values(by=['Ticker-UA', 'EndDate', 'StrikePrice'], inplace=True, ignore_index=True)
        return all_options_market_watch

    except Exception as e:
        print(f"Failed to get the market watch with the error:\n {e}")
        return None
