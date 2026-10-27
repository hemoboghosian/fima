import pandas as pd
import requests
import jdatetime as jd
from fima.IFB import get_risk_free_rate
from mibian import BS
from scipy.stats import norm
import numpy as np
from typing import Tuple
from ._data import number_series, identifier_series, jalali_date, gregorian_series
from fima.TSETMC import _find_instrument_code, get_ticker_historical_data


def _option_market_records(data):
    mapping = {
        'insCode_P': 'InstrumentCode-P', 'insCode_C': 'InstrumentCode-C',
        'contractSize': 'ContractSize', 'uaInsCode': 'InstrumentCode-UA',
        'lval30_UA': 'Ticker-UA', 'beginDate': 'BeginDate', 'endDate': 'EndDate',
        'strikePrice': 'StrikePrice', 'remainedDay': 'DaysToMaturity',
        'pClosing_UA': 'ClosePrice-UA', 'pDrCotVal_UA': 'LastPrice-UA',
        'priceYesterday_UA': 'YesterdayPrice-UA',
    }
    for side in ('P', 'C'):
        for source, target in {
            'lVal18AFC': 'Ticker', 'lVal30': 'Name', 'zTotTran': 'TransactionCount',
            'qTotTran5J': 'TradeVolume', 'qTotCap': 'Value', 'notionalValue': 'NotionalValue',
            'pClosing': 'ClosePrice', 'priceYesterday': 'YesterdayPrice', 'oP': 'OpenPositions',
            'pDrCotVal': 'LastPrice', 'pMeDem': 'BidPrice', 'qTitMeDem': 'BidVolume',
            'pMeOf': 'AskPrice', 'qTitMeOf': 'AskVolume', 'yesterdayOP': 'YesterdayOpenPositions',
        }.items():
            mapping[source + '_' + side] = target + '-' + side
    if not isinstance(data, list):
        raise ValueError('TSETMC option market response must be a list of records.')
    frame = pd.DataFrame(data) if data else pd.DataFrame(columns=list(mapping))
    missing = set(mapping) - set(frame)
    if missing:
        raise ValueError(f'TSETMC option market response missing fields: {sorted(missing)}')
    frame = frame[list(mapping)].rename(columns=mapping)
    for column in frame:
        if column.startswith('InstrumentCode'):
            frame[column] = identifier_series(frame[column])
        elif not column.startswith(('Ticker', 'Name', 'BeginDate', 'EndDate')):
            frame[column] = number_series(frame[column])
    return frame


def _option_frame(frame, j_date=True):
    names = {'ClosePrice': 'ClosingPrice', 'FirstPrice': 'OpeningPrice', 'MinPrice': 'LowPrice',
             'MaxPrice': 'HighPrice', 'Value': 'TradeValue', 'Name': 'InstrumentName',
             'Type': 'OptionType', 'UATicker': 'UnderlyingTicker'}
    result = frame.copy()
    rename = {}
    for column in result:
        base, prefix = column, ''
        for suffix, label in [('-C', 'Call'), ('-P', 'Put'), ('-UA', 'Underlying')]:
            if base.endswith(suffix):
                base, prefix = base[:-len(suffix)], label
                break
        name = prefix + names.get(base, base)
        if base in ('BeginDate', 'EndDate', 'MaturityDate'):
            name = prefix + base[:-4] + ('JalaliDate' if j_date else 'GregorianDate')
            result[column] = result[column].map(jalali_date) if j_date else gregorian_series(result[column])
        elif base == 'InstrumentCode':
            result[column] = identifier_series(result[column])
        elif base not in ('Ticker', 'UATicker', 'Name', 'Type', 'Status', 'URL'):
            result[column] = number_series(result[column])
            if base in ('RiskFreeRate', 'Volatility', 'ImpliedVolatility'):
                result[column] *= 100
        rename[column] = name
    return result.rename(columns=rename)


def _model_info(frame):
    # Public output may also be injected into the analytical convenience APIs.
    return frame.rename(columns={'UnderlyingTicker': 'UATicker', 'UnderlyingLastPrice': 'LastPrice-UA',
                                 'OptionType': 'Type'})


def _apply_option_rows(frame, function, columns):
    if frame.empty:
        return pd.DataFrame(index=frame.index, columns=columns, dtype=float)
    return frame.apply(function, axis=1)


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


def ticker_info(ticker: str, j_date: bool = True) -> pd.DataFrame:
    """Return option metadata and last prices for an exact option ticker.

    The seven columns are UnderlyingTicker, StrikePrice, MaturityJalaliDate
    (or MaturityGregorianDate when ``j_date=False``), DaysToMaturity,
    OptionType, LastPrice and UnderlyingLastPrice. Prices remain source rials.
    Request/HTTP and JSON errors propagate; invalid provider option names raise
    ValueError. The restored date selector does not restore the pre-0.4 full
    market-watch row; use ``download_market_watch(stack='Vertical')`` for that.
    """
    ticker_info_df = pd.DataFrame(columns=['UATicker', 'StrikePrice', 'MaturityDate', 'DaysToMaturity', 'Type'], index=[0])
    ticker_instrument_code = _find_instrument_code(search_key=ticker, trade_type='Ordinary')
    ticker_info_url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/{ticker_instrument_code}"
    response = requests.get(url=ticker_info_url, timeout=30)
    response.raise_for_status()
    instrument_code_info = response.json()['instrumentInfo']
    name = instrument_code_info['lVal30']
    try:
        header, strike, expiry = name.rsplit('-', 2)
        kind, underlying = header.split(maxsplit=1)
        if kind[-1] not in ('خ', 'ف'):
            raise ValueError('Unknown option type')
        maturity = jalali_date(expiry)
        if pd.isna(maturity):
            raise ValueError('Missing expiry')
        maturity_date = jd.date(*map(int, maturity.split('-')))
        strike_price = int(strike)
    except (ValueError, IndexError) as error:
        raise ValueError(f'Invalid TSETMC option instrument name: {name!r}') from error
    ticker_info_df.loc[0, 'UATicker'] = underlying.strip()
    ticker_info_df.loc[0, 'StrikePrice'] = strike_price
    ticker_info_df.loc[0, 'MaturityDate'] = maturity_date
    ticker_info_df.loc[0, 'DaysToMaturity'] = (ticker_info_df.loc[0, 'MaturityDate'] - jd.date.today()).days
    ticker_info_df.loc[0, 'Type'] = 'Call' if kind[-1] == 'خ' else 'Put'

    ticker_instrument_info_url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{ticker_instrument_code}"
    response = requests.get(ticker_instrument_info_url, timeout=30)
    response.raise_for_status()
    ticker_instrument_info = response.json()['closingPriceInfo']
    ticker_info_df.loc[0, 'LastPrice'] = ticker_instrument_info['pDrCotVal']

    ua_ticker_instrument_code = _find_instrument_code(search_key=ticker_info_df.loc[0, 'UATicker'], trade_type='Ordinary')
    ua_ticker_instrument_info_url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{ua_ticker_instrument_code}"
    response = requests.get(ua_ticker_instrument_info_url, timeout=30)
    response.raise_for_status()
    ua_ticker_instrument_info = response.json()['closingPriceInfo']
    ticker_info_df.loc[0, 'LastPrice-UA'] = ua_ticker_instrument_info['pDrCotVal']

    if not j_date:
        ticker_info_df['MaturityDate'] = ticker_info_df['MaturityDate'].map(lambda date: date.togregorian())
    return _option_frame(ticker_info_df, j_date)


def _calculate_row_wise_implied_volatility(row) -> float:
    # print(f"Calculating {row['Ticker']} implied volatility...")
    return get_implied_volatility(ticker=row['Ticker'], _ticker_info_df=row.to_frame().T, r_f=row['RiskFreeRate'],
                                  _ua_historical_data=row['HistoricalData-UA'])


def get_implied_volatility(ticker: str, _ticker_info_df: pd.DataFrame = None, volatility_window_size: int = None,
                       r_f: float = None, minimum_required_history: int = 30, _ua_historical_data: pd.DataFrame = None) -> float:

    if _ticker_info_df is None:
        _ticker_info_df = ticker_info(ticker=ticker)

    _ticker_info_df = _model_info(_ticker_info_df)

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
            ticker_implied_volatility = BS([s, k, r_f * 100, t * 365], callPrice=premium)
        elif option_type == 'Put':
            ticker_implied_volatility = BS([s, k, r_f * 100, t * 365], putPrice=premium)
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

    _ticker_info_df = _model_info(_ticker_info_df)

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

    delta = calculate_delta(s=s, k=k, t=t, r_f=r_f, sigma=sigma, option_type=option_type)
    gamma = calculate_gamma(s=s, k=k, t=t, r_f=r_f, sigma=sigma)
    theta = calculate_theta(s=s, k=k, t=t, r_f=r_f, sigma=sigma, option_type=option_type)
    vega = calculate_vega(s=s, k=k, t=t, r_f=r_f, sigma=sigma)
    rho = calculate_rho(s=s, k=k, t=t, r_f=r_f, sigma=sigma, option_type=option_type)

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
    """Trailing sample daily log-return volatility, annualized with 252 sessions."""
    data = ua_historical_data
    for date in ('GregorianDate', 'JalaliDate', 'Date'):
        if date in data:
            data = data.sort_values(date)
            break
    else:
        if data.index.name in ('JalaliDate', 'GregorianDate') or isinstance(data.index, pd.DatetimeIndex):
            data = data.sort_index()
    column = 'ClosingPrice' if 'ClosingPrice' in data else 'ClosePrice'
    prices = number_series(data[column]).tail(window_size + 1)
    if not (np.isfinite(prices) & (prices > 0)).all():
        raise ValueError('Historical closing prices must be finite and positive for volatility.')
    return float(np.log(prices).diff().std() * np.sqrt(252))


def calculate_black_scholes_merton(s, k, t, sigma, r_f, option_type) \
        -> float:
    """European option price; t in years, r_f and sigma in decimal annual units."""
    if option_type not in ('Call', 'Put'):
        raise ValueError(f"Unknown option type '{option_type}'. Expected 'Call' or 'Put'.")
    if s <= 0 or k <= 0 or t < 0 or sigma < 0 or not np.isfinite([s, k, t, sigma, r_f]).all():
        raise ValueError('Prices must be positive; time/volatility nonnegative; inputs finite.')
    if t == 0 or sigma == 0:
        discounted_strike = k * np.exp(-r_f * t)
        return float(max(s - discounted_strike, 0) if option_type == 'Call' else max(discounted_strike - s, 0))
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

    _ticker_info_df = _model_info(_ticker_info_df)

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

    price = calculate_black_scholes_merton(s, k, t, sigma, r_f, option_type)

    return sigma, price


def download_all_underlying_assets(_all_options_market_watch: pd.DataFrame = None, market: str = 'All') -> pd.DataFrame:
    if _all_options_market_watch is None:
        _all_options_market_watch = download_market_watch(market=market, stack='Horizontal', j_date=True)
    columns = [column for column in _all_options_market_watch if column.startswith('Underlying')]
    result = _all_options_market_watch[columns].drop_duplicates().reset_index(drop=True)
    return result.rename(columns={column: column.removeprefix('Underlying') for column in columns})


def download_historical_data(ticker: str, start_date: str = None, end_date: str = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Option and underlying raw daily history, filtered by optional Jalali bounds.

    Returns two frames with JalaliDate strings, TransactionCount, TradeVolume,
    TradeValue and distinct opening/low/high/last/closing prices. Prices/value
    remain in source rial units. HTTP errors propagate; unavailable history
    retains the legacy (None, None) result. Bounds are inclusive and independent.
    """
    code = _find_instrument_code(search_key=ticker, trade_type='Ordinary')
    info = requests.get(f'https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/{code}', timeout=30)
    info.raise_for_status()
    underlying = info.json()['instrumentInfo']['lVal30'].split('-')[0].split(' ')[1]
    ua_code = _find_instrument_code(search_key=underlying, trade_type='Ordinary')
    mapping = {'dEven': 'GregorianDate', 'zTotTran': 'TransactionCount', 'qTotTran5J': 'TradeVolume',
               'qTotCap': 'TradeValue', 'priceMin': 'LowPrice', 'priceMax': 'HighPrice',
               'priceFirst': 'OpeningPrice', 'pDrCotVal': 'LastPrice', 'pClosing': 'ClosingPrice'}
    frames = []
    bounds = [jalali_date(x) if x is not None else None for x in (start_date, end_date)]
    for instrument in (code, ua_code):
        response = requests.get(f'https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/{instrument}/0', timeout=30)
        response.raise_for_status()
        frame = pd.DataFrame(response.json()['closingPriceDaily'])
        if frame.empty:
            return None, None
        frame = frame[list(mapping)].rename(columns=mapping)
        dates = pd.to_datetime(frame.pop('GregorianDate').astype(str), format='%Y%m%d')
        frame.insert(0, 'JalaliDate', dates.map(lambda date: jd.date.fromgregorian(date=date.date()).isoformat()))
        for column in frame.columns[1:]:
            frame[column] = number_series(frame[column])
        for bound, lower in zip(bounds, (True, False)):
            if bound is not None:
                frame = frame[frame.JalaliDate.ge(bound) if lower else frame.JalaliDate.le(bound)]
        frames.append(frame.sort_values('JalaliDate').reset_index(drop=True))
    return tuple(frames)


def download_chain_contracts(underlying_ticker: str, j_date: str = True, bsm: bool = False, greeks: bool = False,
                             implied_volatility: bool = False) -> pd.DataFrame:
    """Return the current option chain for an exact underlying ticker.

    ``j_date`` selects Jalali string or Gregorian datetime event dates. Optional
    analytics use the underlying history. An unmatched ticker returns an empty
    table. Request/HTTP, JSON, schema and analytical errors propagate instead
    of returning ``None``. Prices and trade values retain provider rial units.
    """
    url = "https://cdn.tsetmc.com/api/Instrument/GetInstrumentOptionMarketWatch/0"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()
    all_options_market_watch = _option_market_records(data["instrumentOptMarketWatch"])
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

    call_chain_contracts_columns = ['Ticker-C', 'Name-C', 'InstrumentCode-C', 'Status-C', 'TransactionCount-C', 'TradeVolume-C', 'Value-C',
                                         'NotionalValue-C', 'OpenPositions-C', 'ClosePrice-C', 'LastPrice-C', 'YesterdayPrice-C',
                                         'BidPrice-C', 'BidVolume-C', 'AskPrice-C', 'AskVolume-C', 'URL-C']
    ua_chain_contracts_columns = ['ContractSize', 'StrikePrice', 'DaysToMaturity', 'BeginDate', 'EndDate',
                                        'Ticker-UA', 'InstrumentCode-UA', 'ClosePrice-UA', 'LastPrice-UA',
                                        'YesterdayPrice-UA', 'URL-UA']
    put_chain_contracts_columns = ['Ticker-P', 'Name-P', 'InstrumentCode-P', 'Status-P', 'TransactionCount-P', 'TradeVolume-P', 'Value-P',
                                         'NotionalValue-P', 'OpenPositions-P', 'ClosePrice-P', 'LastPrice-P', 'YesterdayPrice-P',
                                         'BidPrice-P', 'BidVolume-P', 'AskPrice-P', 'AskVolume-P', 'URL-P']


    if bsm or greeks or implied_volatility:
        ua_historical_data = pd.DataFrame(columns=['JalaliDate', 'ClosingPrice'])
        if not chain_contracts.empty:
            print(f'Downloading {underlying_ticker} historical data...')
            ua_historical_data = get_ticker_historical_data(
                ticker=underlying_ticker).reset_index().loc[:, ['JalaliDate', 'ClosingPrice']].copy()
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

        risk_free_rate = get_risk_free_rate() if not chain_contracts.empty else np.nan
        call_chain_contracts['RiskFreeRate'] = risk_free_rate
        put_chain_contracts['RiskFreeRate'] = risk_free_rate
        ua_chain_contracts_columns.append('RiskFreeRate')

        if bsm:
            call_chain_contracts[['Volatility', 'BSMPrice']] = _apply_option_rows(call_chain_contracts, _calculate_row_wise_bsm, ['Volatility', 'BSMPrice'])
            call_chain_contracts_columns.append(['Volatility', 'BSMPrice'])
            put_chain_contracts[['Volatility', 'BSMPrice']] = _apply_option_rows(put_chain_contracts, _calculate_row_wise_bsm, ['Volatility', 'BSMPrice'])
            put_chain_contracts_columns.append(['Volatility', 'BSMPrice'])

        if greeks:
            call_chain_contracts[['Delta', 'Gamma', 'Theta', 'Vega', 'Rho']] = _apply_option_rows(call_chain_contracts, _calculate_row_wise_greeks, ['Delta', 'Gamma', 'Theta', 'Vega', 'Rho'])
            call_chain_contracts_columns.append(['Delta', 'Gamma', 'Theta', 'Vega', 'Rho'])
            put_chain_contracts[['Delta', 'Gamma', 'Theta', 'Vega', 'Rho']] = _apply_option_rows(put_chain_contracts, _calculate_row_wise_greeks, ['Delta', 'Gamma', 'Theta', 'Vega', 'Rho'])
            put_chain_contracts_columns.append(['Delta', 'Gamma', 'Theta', 'Vega', 'Rho'])

        if implied_volatility:
            call_chain_contracts['ImpliedVolatility'] = _apply_option_rows(call_chain_contracts, _calculate_row_wise_implied_volatility, ['ImpliedVolatility'])
            call_chain_contracts_columns.append(['ImpliedVolatility'])
            put_chain_contracts['ImpliedVolatility'] = _apply_option_rows(put_chain_contracts, _calculate_row_wise_implied_volatility, ['ImpliedVolatility'])
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
    return _option_frame(chain_contracts, j_date)


def download_market_watch(market: str = 'All', stack: str = 'Horizontal', j_date: bool = True,
                          bsm: str = False, greeks: bool = False, implied_volatility: bool = False) -> pd.DataFrame:
    """Return TSETMC options for ``All``, ``TSE`` or ``IFB``.

    ``stack='Horizontal'`` pairs Call/Put columns; ``Vertical`` returns one row
    per side with ``OptionType``. ``j_date`` selects Jalali string or Gregorian
    datetime event dates. Optional analytics use the underlying history.
    Request/HTTP, JSON, schema and analytical errors propagate; a valid empty
    provider list returns an empty table. Prices/values retain source rial units.
    """

    if market == 'TSE':
        url = "https://cdn.tsetmc.com/api/Instrument/GetInstrumentOptionMarketWatch/1"
    elif market == 'IFB':
        url = "https://cdn.tsetmc.com/api/Instrument/GetInstrumentOptionMarketWatch/2"
    else:       # 'All'
        url = "https://cdn.tsetmc.com/api/Instrument/GetInstrumentOptionMarketWatch/0"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    data = response.json()
    all_options_market_watch = _option_market_records(data["instrumentOptMarketWatch"])
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

    call_options_market_watch_columns = ['Ticker-C', 'Name-C', 'InstrumentCode-C', 'Status-C', 'TransactionCount-C', 'TradeVolume-C', 'Value-C',
                                         'NotionalValue-C', 'OpenPositions-C', 'ClosePrice-C', 'LastPrice-C', 'YesterdayPrice-C',
                                         'BidPrice-C', 'BidVolume-C', 'AskPrice-C', 'AskVolume-C', 'URL-C']
    ua_market_watch_columns = ['ContractSize', 'StrikePrice', 'DaysToMaturity', 'BeginDate', 'EndDate',
                                        'Ticker-UA', 'InstrumentCode-UA', 'ClosePrice-UA', 'LastPrice-UA',
                                        'YesterdayPrice-UA', 'URL-UA']
    put_options_market_watch_columns = ['Ticker-P', 'Name-P', 'InstrumentCode-P', 'Status-P', 'TransactionCount-P', 'TradeVolume-P', 'Value-P',
                                         'NotionalValue-P', 'OpenPositions-P', 'ClosePrice-P', 'LastPrice-P', 'YesterdayPrice-P',
                                         'BidPrice-P', 'BidVolume-P', 'AskPrice-P', 'AskVolume-P', 'URL-P']


    if bsm or greeks or implied_volatility:
        uas_historical_data = {}
        all_uas = all_options_market_watch[['Ticker-UA']].drop_duplicates().rename(columns={'Ticker-UA': 'Ticker'})
        print('Starting to download historical data for all tickers...')
        for ua in all_uas['Ticker']:
            print(f'Downloading {ua} historical data...')
            uas_historical_data[ua] = get_ticker_historical_data(
                ticker=ua).reset_index().loc[:, ['JalaliDate', 'ClosingPrice']].copy()
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

        risk_free_rate = get_risk_free_rate() if not all_options_market_watch.empty else np.nan
        call_options_market_watch['RiskFreeRate'] = risk_free_rate
        put_options_market_watch['RiskFreeRate'] = risk_free_rate
        ua_market_watch_columns.append('RiskFreeRate')

        if bsm:
            print('\n\nCalculating BSMs...')
            call_options_market_watch[['Volatility', 'BSMPrice']] = _apply_option_rows(call_options_market_watch, _calculate_row_wise_bsm, ['Volatility', 'BSMPrice'])
            call_options_market_watch_columns.append(['Volatility', 'BSMPrice'])
            put_options_market_watch[['Volatility', 'BSMPrice']] = _apply_option_rows(put_options_market_watch, _calculate_row_wise_bsm, ['Volatility', 'BSMPrice'])
            put_options_market_watch_columns.append(['Volatility', 'BSMPrice'])

        if greeks:
            print('\n\nCalculating Greeks...')
            call_options_market_watch[['Delta', 'Gamma', 'Theta', 'Vega', 'Rho']] = _apply_option_rows(call_options_market_watch, _calculate_row_wise_greeks, ['Delta', 'Gamma', 'Theta', 'Vega', 'Rho'])
            call_options_market_watch_columns.append(['Delta', 'Gamma', 'Theta', 'Vega', 'Rho'])
            put_options_market_watch[['Delta', 'Gamma', 'Theta', 'Vega', 'Rho']] = _apply_option_rows(put_options_market_watch, _calculate_row_wise_greeks, ['Delta', 'Gamma', 'Theta', 'Vega', 'Rho'])
            put_options_market_watch_columns.append(['Delta', 'Gamma', 'Theta', 'Vega', 'Rho'])

        if implied_volatility:
            print('\n\nCalculating IVs...')
            call_options_market_watch['ImpliedVolatility'] = _apply_option_rows(call_options_market_watch, _calculate_row_wise_implied_volatility, ['ImpliedVolatility'])
            call_options_market_watch_columns.append(['ImpliedVolatility'])
            put_options_market_watch['ImpliedVolatility'] = _apply_option_rows(put_options_market_watch, _calculate_row_wise_implied_volatility, ['ImpliedVolatility'])
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
    return _option_frame(all_options_market_watch, j_date)
