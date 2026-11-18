from typing import Literal as _Literal
import pandas as pd
import requests
import jdatetime as jd
from fima.IFB import get_risk_free_rate
from mibian import BS
from scipy.stats import norm
from scipy.optimize import brentq as _brentq
import numpy as np
from typing import Tuple
from typing import Sequence as _Sequence
from numbers import Real as _Real, Integral as _Integral
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


def calculate_delta(s, k, t, r_f, sigma, option_type: str) -> float:
    """Calculate delta for the no-dividend European option model.

    Parameters
    ----------
    s, k : numeric
        Required spot and strike in the same price unit; strictly positive.
    t : numeric
        Required time to expiry in years; the regular formula needs t > 0.
    r_f : numeric
        Required continuously compounded annual decimal rate (.05 means 5%).
    sigma : numeric
        Required annual decimal volatility (.20 means 20%); needs sigma > 0.
    option_type : str
        Required exact Call or Put; other values retain the legacy None result.

    Returns
    -------
    numeric or None
        Delta: change per unit underlying price. NumPy-compatible inputs
        retain existing broadcasting behavior. This function makes no network
        requests and does not validate the full numerical domain: zero time/
        volatility or invalid inputs can warn, raise or produce NaN/infinity.
        See docs/options.md#analytics; prefer keyword arguments because pricing
        orders sigma/r_f differently from the Greek functions.
    """
    if option_type == 'Call':
        return norm.cdf(_calculate_d1(s, k, t, r_f, sigma))
    elif option_type == 'Put':
        return -norm.cdf(-(np.log(s / k) + (r_f + sigma ** 2 / 2) * t) / (sigma * np.sqrt(t)))
    return None


def calculate_theta(s, k, t, r_f, sigma, option_type: str) -> float:
    """Calculate theta for the no-dividend European option model.

    Parameters
    ----------
    s, k : numeric
        Required spot and strike in the same price unit; strictly positive.
    t : numeric
        Required time to expiry in years; the regular formula needs t > 0.
    r_f : numeric
        Required continuously compounded annual decimal rate (.05 means 5%).
    sigma : numeric
        Required annual decimal volatility (.20 means 20%); needs sigma > 0.
    option_type : str
        Required exact Call or Put; other values retain the legacy None result.

    Returns
    -------
    numeric or None
        Theta: price change per year, not per day. NumPy-compatible inputs
        retain existing broadcasting behavior. This function makes no network
        requests and does not validate the full numerical domain: zero time/
        volatility or invalid inputs can warn, raise or produce NaN/infinity.
        See docs/options.md#analytics; prefer keyword arguments because pricing
        orders sigma/r_f differently from the Greek functions.
    """
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
    """Calculate gamma for the no-dividend European option model.

    Parameters
    ----------
    s, k : numeric
        Required spot and strike in the same price unit; strictly positive.
    t : numeric
        Required time to expiry in years; the regular formula needs t > 0.
    r_f : numeric
        Required continuously compounded annual decimal rate (.05 means 5%).
    sigma : numeric
        Required annual decimal volatility (.20 means 20%); needs sigma > 0.

    Returns
    -------
    numeric
        Gamma: delta change per unit underlying price. NumPy-compatible inputs
        retain existing broadcasting behavior. This function makes no network
        requests and does not validate the full numerical domain: zero time/
        volatility or invalid inputs can warn, raise or produce NaN/infinity.
        See docs/options.md#analytics; prefer keyword arguments because pricing
        orders sigma/r_f differently from the Greek functions.
    """
    return norm.pdf(_calculate_d1(s, k, t, r_f, sigma)) / (s * sigma * np.sqrt(t))


def calculate_vega(s, k, t, r_f, sigma) -> float:
    """Calculate vega for the no-dividend European option model.

    Parameters
    ----------
    s, k : numeric
        Required spot and strike in the same price unit; strictly positive.
    t : numeric
        Required time to expiry in years; the regular formula needs t > 0.
    r_f : numeric
        Required continuously compounded annual decimal rate (.05 means 5%).
    sigma : numeric
        Required annual decimal volatility (.20 means 20%); needs sigma > 0.

    Returns
    -------
    numeric
        Vega: price change per whole decimal volatility unit, not 1 percentage
        point. NumPy-compatible inputs
        retain existing broadcasting behavior. This function makes no network
        requests and does not validate the full numerical domain: zero time/
        volatility or invalid inputs can warn, raise or produce NaN/infinity.
        See docs/options.md#analytics; prefer keyword arguments because pricing
        orders sigma/r_f differently from the Greek functions.
    """
    return s * np.sqrt(t) * norm.pdf(_calculate_d1(s, k, t, r_f, sigma))


def calculate_rho(s, k, t, r_f, sigma, option_type: str) -> float:
    """Calculate rho for the no-dividend European option model.

    Parameters
    ----------
    s, k : numeric
        Required spot and strike in the same price unit; strictly positive.
    t : numeric
        Required time to expiry in years; the regular formula needs t > 0.
    r_f : numeric
        Required continuously compounded annual decimal rate (.05 means 5%).
    sigma : numeric
        Required annual decimal volatility (.20 means 20%); needs sigma > 0.
    option_type : str
        Required exact Call or Put; other values retain the legacy None result.

    Returns
    -------
    numeric or None
        Rho: price change per whole decimal rate unit, not 1 percentage point.
        NumPy-compatible inputs
        retain existing broadcasting behavior. This function makes no network
        requests and does not validate the full numerical domain: zero time/
        volatility or invalid inputs can warn, raise or produce NaN/infinity.
        See docs/options.md#analytics; prefer keyword arguments because pricing
        orders sigma/r_f differently from the Greek functions.
    """
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

    Usage
    -----
    ticker is required; select CallTicker/PutTicker from a chain or Ticker from
    a Vertical watch. j_date defaults True and selects the output calendar only.
    This is option metadata, unlike IFB get_ticker_info.
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


def _validated_implied_volatility(s, k, t, r_f, premium, option_type):
    """Validate the existing Mibian candidate against fima's pricing formula."""
    with np.errstate(over='ignore', under='ignore', invalid='ignore'):
        discounted_strike = k * np.exp(-r_f * t)
    if not np.isfinite(discounted_strike) or discounted_strike <= 0:
        return None
    lower = max(s - discounted_strike, 0) if option_type == 'Call' else max(discounted_strike - s, 0)
    upper = s if option_type == 'Call' else discounted_strike
    # Allow only floating-point roundoff below the zero-volatility boundary.
    roundoff = 64 * np.finfo(float).eps * max(s, discounted_strike)
    if premium < lower - roundoff or premium >= upper:
        return None  # The exact upper bound requires infinite, not finite, IV.
    if premium <= lower:
        return 0.
    tolerance = 1e-8 * premium + roundoff

    def residual(volatility):
        return calculate_black_scholes_merton(s, k, t, volatility, r_f, option_type) - premium

    upper_volatility = 5.
    upper_residual = residual(upper_volatility)
    if not np.isfinite(upper_residual):
        return None
    candidate = np.nan
    rounded = round(premium, 6)
    # Do not send rounded-zero/boundary/out-of-range targets into Mibian's
    # 10,000-iteration loop: they cannot have an interior root in its interval.
    if lower < rounded < upper and rounded < upper_residual + premium:
        try:
            kwargs = {'callPrice' if option_type == 'Call' else 'putPrice': premium}
            candidate = float(BS([s, k, r_f * 100, t * 365], **kwargs).impliedVolatility) / 100
        except (TypeError, ValueError, ArithmeticError, UnboundLocalError, IndexError):
            pass  # The original premium can still have a verifiable root.
    if np.isfinite(candidate) and candidate >= 0 and abs(residual(candidate)) <= tolerance:
        return candidate
    # Expand a numerical bracket, never impose Mibian's 500% ceiling as a
    # financial cutoff. Both expansion and the subsequent root search are finite.
    for _ in range(16):
        if upper_residual >= 0:
            break
        upper_volatility *= 2
        upper_residual = residual(upper_volatility)
        if not np.isfinite(upper_residual):
            return None
    if upper_residual < 0:
        return None
    try:
        candidate = _brentq(residual, 0., upper_volatility, xtol=1e-12,
                            rtol=8 * np.finfo(float).eps, maxiter=100)
    except (ValueError, RuntimeError, ArithmeticError):
        return None
    if not np.isfinite(candidate) or candidate < 0:
        return None
    return float(candidate) if abs(residual(candidate)) <= tolerance else None


def get_implied_volatility(ticker: str, _ticker_info_df: pd.DataFrame | None = None, volatility_window_size: int | None = None,
                       r_f: float | None = None, minimum_required_history: int = 30, _ua_historical_data: pd.DataFrame | None = None) -> float | None:

    """Estimate decimal implied volatility from the option's observed premium.

    Parameters
    ----------
    ticker : str
        Required exact option Ticker from a Vertical download_market_watch or
        CallTicker/PutTicker from download_chain_contracts, not the underlying.
    _ticker_info_df : pandas.DataFrame or None, default None
        Legacy injected one-row metadata; ticker_info output avoids that lookup.
    volatility_window_size : int or None, default None
        Trailing daily-return window. None uses min(30, max(5, safe_window//2));
        an explicit value is capped at min(history rows, days to maturity).
    r_f : float or None, default None
        Annual decimal model rate (.30 means 30%). None calls the IFB treasury
        proxy directly, without a compounding conversion. BSM discounting uses
        a continuous rate; the proxy is not certified equivalent to that convention.
    minimum_required_history : int, default 30
        Minimum underlying-history row count, even for implied volatility.
    _ua_historical_data : pandas.DataFrame or None, default None
        Legacy injected underlying daily data; otherwise history is downloaded.
        Requires ClosingPrice (legacy ClosePrice also works) and ordered dates.

    Notes
    -----
    Historical volatility uses raw closing-price daily log returns, the trailing
    window and sqrt(252); corporate-action jumps are not removed. Expiry uses
    calendar days/365, and less than 10 remaining days or a window below 5 yields
    missing estimates with a printed diagnostic. No dividend yield is modeled.
    Other metadata/network/schema errors can propagate. See docs/options.md#analytics.

    Returns
    -------
    Decimal annual volatility (.20 means 20%), or None for
    unavailable/insufficient history, near expiry, zero historical volatility,
    invalid model inputs/premiums or unverified solver results. The zero-model-
    volatility premium returns 0.0 after the existing history/expiry checks.
    The exact positive-time upper price bound has no finite IV and returns None.
    Candidates must independently reprice within 1e-8*premium plus 64 machine
    epsilons times max(spot, discounted strike), in premium units. Coarse Mibian
    results use bounded refinement with at most 16 bracket doublings from 500%
    and 100 root iterations. A high IV is accepted when verified, without a
    financial volatility cutoff; an unbracketed/unverified root remains missing.
    See docs/options.md#iv-validation for boundaries and missing-result examples.
    """
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

    option_type = _ticker_info_df['Type'].values[0]
    raw = [_ticker_info_df[column].values[0] for column in
           ('LastPrice-UA', 'StrikePrice', 'DaysToMaturity', 'LastPrice')]
    raw.append(r_f)
    try:
        if any(isinstance(value, (bool, np.bool_, complex, np.complexfloating)) for value in raw):
            raise ValueError('Nonreal model input')
        s, k, days_to_maturity, premium, r_f = map(float, raw)
    except (TypeError, ValueError, OverflowError):
        print(f'Invalid option model inputs for {ticker}.')
        return None
    if (not np.isfinite([s, k, days_to_maturity, premium, r_f]).all()
            or s <= 0 or k <= 0 or premium < 0
            or not isinstance(option_type, str) or option_type not in ('Call', 'Put')):
        print(f'Invalid option model inputs for {ticker}.')
        return None
    if days_to_maturity < 10:
        print(f"Option {ticker} expires too soon ({days_to_maturity} days left). Calculated implied volatility may not be reliable.")
        return None

    max_safe_window = min(stock_days_available, int(days_to_maturity))
    if volatility_window_size is None:
        volatility_window_size = min(30, max(5, max_safe_window // 2))  # dynamic choice
    else:
        volatility_window_size = min(volatility_window_size, max_safe_window)  # force safe

    if volatility_window_size < 5:
        print(f"Volatility window too small ({volatility_window_size} days). Cannot calculate meaningful volatility for {ticker}.")
        return None

    sigma = _calculate_volatility(_ua_historical_data, volatility_window_size)
    t = days_to_maturity / 365

    if sigma == 0 or t == 0:
        print("Zero volatility or expired option.")
        return None

    result = _validated_implied_volatility(s, k, t, r_f, premium, option_type)
    if result is None:
        print(f'No verified model-consistent implied volatility for {ticker}.')
    return result


def get_greeks(ticker: str, _ticker_info_df: pd.DataFrame | None = None, volatility_window_size: int | None = None, r_f: float | None = None,
           minimum_required_history: int = 30, _ua_historical_data: pd.DataFrame | None = None) -> pd.Series:

    """Estimate an option's Greeks using historical underlying volatility.

    Parameters
    ----------
    ticker : str
        Required exact option Ticker from a Vertical download_market_watch or
        CallTicker/PutTicker from download_chain_contracts, not the underlying.
    _ticker_info_df : pandas.DataFrame or None, default None
        Legacy injected one-row metadata; ticker_info output avoids that lookup.
    volatility_window_size : int or None, default None
        Trailing daily-return window. None uses min(30, max(5, safe_window//2));
        an explicit value is capped at min(history rows, days to maturity).
    r_f : float or None, default None
        Annual decimal model rate (.30 means 30%). None calls the IFB treasury
        proxy directly, without a compounding conversion. BSM discounting uses
        a continuous rate; the proxy is not certified equivalent to that convention.
    minimum_required_history : int, default 30
        Minimum underlying-history row count, even for implied volatility.
    _ua_historical_data : pandas.DataFrame or None, default None
        Legacy injected underlying daily data; otherwise history is downloaded.
        Requires ClosingPrice (legacy ClosePrice also works) and ordered dates.

    Notes
    -----
    Historical volatility uses raw closing-price daily log returns, the trailing
    window and sqrt(252); corporate-action jumps are not removed. Expiry uses
    calendar days/365, and less than 10 remaining days or a window below 5 yields
    missing estimates with a printed diagnostic. No dividend yield is modeled.
    Other metadata/network/schema errors can propagate. See docs/options.md#analytics.

    Returns
    -------
    Series labeled Delta, Gamma, Theta, Vega, Rho. Insufficient inputs yield
    missing labels with a diagnostic. Theta is per year; Vega/Rho are per whole
    decimal volatility/rate unit, not per percentage point.
    """
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


def calculate_black_scholes_merton(s: float, k: float, t: float, sigma: float, r_f: float, option_type: _Literal["Call", "Put"]) \
        -> float:
    """Calculate a no-dividend European option price without network requests.

    Parameters
    ----------
    s, k : float
        Required positive finite spot and strike in the same price unit.
    t : float
        Required nonnegative finite years to expiry.
    sigma : float
        Required nonnegative finite annual decimal volatility (.20 means 20%).
    r_f : float
        Required finite continuously compounded annual decimal rate (.05 = 5%).
    option_type : {'Call', 'Put'}
        Required exact side, case-sensitive.

    Returns
    -------
    float
        Price in spot/strike units. At expiry returns intrinsic value; zero
        volatility uses discounted intrinsic value. No dividend yield is modeled.

    Raises
    ------
    ValueError
        Unsupported side or invalid numerical domain. Malformed types can raise
        TypeError. Prefer keywords: sigma/r_f order differs from Greeks.
        See docs/options.md#analytics.
    """
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


def black_scholes_merton(ticker: str, _ticker_info_df: pd.DataFrame | None = None, volatility_window_size: int | None = None,
                         r_f: float | None = None, minimum_required_history: int = 30,
                         _ua_historical_data: pd.DataFrame | None = None) -> Tuple[float | None, float | None]:

    """Estimate an option price using historical underlying volatility.

    Parameters
    ----------
    ticker : str
        Required exact option Ticker from a Vertical download_market_watch or
        CallTicker/PutTicker from download_chain_contracts, not the underlying.
    _ticker_info_df : pandas.DataFrame or None, default None
        Legacy injected one-row metadata; ticker_info output avoids that lookup.
    volatility_window_size : int or None, default None
        Trailing daily-return window. None uses min(30, max(5, safe_window//2));
        an explicit value is capped at min(history rows, days to maturity).
    r_f : float or None, default None
        Annual decimal model rate (.30 means 30%). None calls the IFB treasury
        proxy directly, without a compounding conversion. BSM discounting uses
        a continuous rate; the proxy is not certified equivalent to that convention.
    minimum_required_history : int, default 30
        Minimum underlying-history row count, even for implied volatility.
    _ua_historical_data : pandas.DataFrame or None, default None
        Legacy injected underlying daily data; otherwise history is downloaded.
        Requires ClosingPrice (legacy ClosePrice also works) and ordered dates.

    Notes
    -----
    Historical volatility uses raw closing-price daily log returns, the trailing
    window and sqrt(252); corporate-action jumps are not removed. Expiry uses
    calendar days/365, and less than 10 remaining days or a window below 5 yields
    missing estimates with a printed diagnostic. No dividend yield is modeled.
    Other metadata/network/schema errors can propagate. See docs/options.md#analytics.

    Returns
    -------
    (decimal_volatility, price), in that order; insufficient/unavailable history
    or near expiry returns (None, None). Price uses the same unit as spot and
    strike.
    """
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


def download_all_underlying_assets(_all_options_market_watch: pd.DataFrame | None = None, market: str = 'All') -> pd.DataFrame:
    """Discover underlying assets from an options market watch.

    Parameters
    ----------
    _all_options_market_watch : pandas.DataFrame or None, default None
        Reuse a current-format watch with Underlying-prefixed columns. None
        downloads a Horizontal watch; supplied data avoids that request.
    market : str, default 'All'
        Used only when downloading: supported All, TSE, IFB. Other values retain
        the watch's legacy All fallback. This is not an underlying ticker.

    Returns
    -------
    pandas.DataFrame
        Distinct Ticker, InstrumentCode, ClosingPrice, LastPrice, YesterdayPrice,
        URL rows from the watch. Prices retain rials; codes are strings. Choose
        Ticker for download_chain_contracts. A supplied frame's columns determine
        extraction; malformed input can raise. Download errors propagate.
        See docs/options.md#discover-underlyings-and-contracts.
    """
    if _all_options_market_watch is None:
        _all_options_market_watch = download_market_watch(market=market, stack='Horizontal', j_date=True)
    columns = [column for column in _all_options_market_watch if column.startswith('Underlying')]
    result = _all_options_market_watch[columns].drop_duplicates().reset_index(drop=True)
    return result.rename(columns={column: column.removeprefix('Underlying') for column in columns})


def download_historical_data(ticker: str, start_date: str | None = None, end_date: str | None = None) -> Tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Option and underlying raw daily history, filtered by optional Jalali bounds.

    Returns two frames with JalaliDate strings, TransactionCount, TradeVolume,
    TradeValue and distinct opening/low/high/last/closing prices. Prices/value
    remain in source rial units. HTTP errors propagate; unavailable history
    retains the legacy (None, None) result. Bounds are inclusive and independent.

    Usage
    -----
    ticker is required; choose CallTicker/PutTicker from a discovered chain.
    start_date/end_date default None (unbounded) and accept Jalali YYYY-MM-DD,
    YYYY/MM/DD or compact YYYYMMDD forms normalized by the shared parser. Each
    returned frame has an ordinary index and JalaliDate column. Both histories
    are raw; reversed bounds yield empty filtered frames when source histories
    exist.
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


def download_chain_contracts(underlying_ticker: str, j_date: bool = True, bsm: bool = False, greeks: bool = False,
                             implied_volatility: bool = False) -> pd.DataFrame:
    """Return the current option chain for an exact underlying ticker.

    ``j_date`` selects Jalali string or Gregorian datetime event dates. Optional
    analytics use the underlying history. An unmatched ticker returns an empty
    table. Request/HTTP, JSON, schema and analytical errors propagate instead
    of returning ``None``. Prices and trade values retain provider rial units.

    Usage
    -----
    underlying_ticker is required; discover Ticker using
    download_all_underlying_assets. j_date defaults True. bsm, greeks and
    implied_volatility default False; enabling them adds model columns and
    history/rate requests. Rate/volatility table fields use percentage points;
    see docs/options.md#analytics for model assumptions and missing estimates.
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
                          bsm: bool = False, greeks: bool = False, implied_volatility: bool = False) -> pd.DataFrame:
    """Return TSETMC options for ``All``, ``TSE`` or ``IFB``.

    ``stack='Horizontal'`` pairs Call/Put columns; ``Vertical`` returns one row
    per side with ``OptionType``. ``j_date`` selects Jalali string or Gregorian
    datetime event dates. Optional analytics use the underlying history.
    Request/HTTP, JSON, schema and analytical errors propagate; a valid empty
    provider list returns an empty table. Prices/values retain source rial units.

    Usage
    -----
    market defaults All; stack defaults Horizontal. Unsupported market/stack
    strings retain the legacy All/Horizontal fallback rather than raising.
    j_date defaults True; bsm, greeks and implied_volatility default False.
    Flags add model columns and history/rate requests. Rate/volatility table
    fields use percentage points; see docs/options.md#analytics for raw-history
    and rate assumptions.
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


def _option_metric_numbers(values: pd.Series) -> pd.Series:
    """Read a numeric column without treating malformed observations as missing."""
    if (pd.api.types.is_datetime64_any_dtype(values.dtype)
            or pd.api.types.is_timedelta64_dtype(values.dtype)
            or values.map(lambda value: isinstance(value, (bool, np.bool_, complex, np.complexfloating))).any()):
        raise ValueError(f'{values.name} must contain real numbers or missing values.')
    try:
        numbers = pd.to_numeric(values, errors='raise').to_numpy(dtype=float, na_value=np.nan)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f'{values.name} must contain real numbers or missing values.') from error
    result = pd.Series(numbers, index=values.index)
    return result.where(np.isfinite(result) & (result >= 0))


def calculate_contract_metrics(
        watch: pd.DataFrame, *,
        price: _Literal['Ask', 'Bid', 'Mid', 'Last', 'Closing'] = 'Ask',
        underlying_price: _Literal['Last', 'Closing'] = 'Last') -> pd.DataFrame:
    """Compare option quotes, valuation components and contract premium exposure.

    Parameters
    ----------
    watch : pandas.DataFrame
        Required existing Vertical download_market_watch output, or a filtered
        subset. Discover UnderlyingTicker and exact option Ticker/InstrumentCode
        in that watch (download_all_underlying_assets also lists underlyings).
        Requires OptionType (Call/Put), StrikePrice, ContractSize, BidPrice,
        BidVolume, AskPrice, AskVolume, TradeVolume, OpenPositions and the selected
        underlying/premium columns. Identity, expiry and other columns are kept.
    price : {'Ask', 'Bid', 'Mid', 'Last', 'Closing'}, default 'Ask'
        Premium basis: AskPrice, BidPrice, valid midpoint, LastPrice or ClosingPrice.
        Ask is an indicative buy/cover basis; Bid is an indicative sell basis.
        No missing price is replaced by another basis. A quote needs positive
        price and quantity. Crossed books invalidate Ask/Bid/Mid calculations;
        an independently known side remains usable when the opposite is missing.
    underlying_price : {'Last', 'Closing'}, default 'Last'
        Select UnderlyingLastPrice or UnderlyingClosingPrice, without fallback.

    Returns
    -------
    pandas.DataFrame
        A copy retaining rows, index, source columns and attrs, with these added
        columns in order (numeric additions are float64 with NaN):
        QuoteStatus (string: TwoSided/Locked/Crossed/BidOnly/AskOnly/NoQuote/Incomplete),
        MidPrice=(ask+bid)/2, Spread=ask-bid, SpreadPercent=100*Spread/MidPrice,
        ReferencePrice, UnderlyingReferencePrice, SpotStrikeRatio=S/K,
        IntrinsicValue=max(S-K,0) for calls or max(K-S,0) for puts,
        TimeValue=ReferencePrice-IntrinsicValue, BreakevenPrice=K+P for calls or
        K-P for puts, PremiumPerContract=P*ContractSize, and
        VolumeOpenPositionsRatio=TradeVolume/OpenPositions. Prices/values are
        rials per underlying unit except PremiumPerContract (rials per contract).
        SpreadPercent is percentage points; both ratios are dimensionless.

    Notes
    -----
    This function makes no network requests or expiry filtering. Missing,
    negative or nonfinite observations invalidate only dependent results; zero
    snapshot prices/strike/size and zero OI denominators are unavailable. Zero
    volume is valid. A locked book has zero spread; incomplete/one-sided/crossed
    books have no midpoint or spread. Negative time-value residuals are retained.
    A negative put breakeven is missing because no nonnegative spot reaches it.
    Existing Status is unchanged and may use a different underlying basis.
    QuoteStatus does not establish freshness, trading permission, liquidity or
    execution. Breakeven excludes fees, financing and settlement constraints and
    assumes economic exercise at expiration. No conversion to tomans, assumed
    1000-unit multiplier, automatic exercise or arbitrage inference is made.
    See docs/options.md#contract-comparison for a discovery/selection example.

    Raises
    ------
    ValueError
        Invalid selector, non-DataFrame/Horizontal input, missing/duplicate
        columns, unknown OptionType, malformed numeric values, or existing
        metric column names. Use the original watch to change the price basis.
    """
    if price not in ('Ask', 'Bid', 'Mid', 'Last', 'Closing'):
        raise ValueError('price must be Ask, Bid, Mid, Last or Closing.')
    if underlying_price not in ('Last', 'Closing'):
        raise ValueError('underlying_price must be Last or Closing.')
    metric_columns = [
        'QuoteStatus', 'MidPrice', 'Spread', 'SpreadPercent', 'ReferencePrice',
        'UnderlyingReferencePrice', 'SpotStrikeRatio', 'IntrinsicValue', 'TimeValue',
        'BreakevenPrice', 'PremiumPerContract', 'VolumeOpenPositionsRatio',
    ]
    if not isinstance(watch, pd.DataFrame) or not watch.columns.is_unique:
        raise ValueError('watch must be a DataFrame with unique Vertical watch columns.')
    spot_column = 'Underlying' + underlying_price + 'Price'
    required = {'OptionType', 'StrikePrice', 'ContractSize', 'BidPrice', 'BidVolume',
                'AskPrice', 'AskVolume', 'TradeVolume', 'OpenPositions', spot_column}
    if price in ('Last', 'Closing'):
        required.add(price + 'Price')
    missing = required - set(watch.columns)
    if missing:
        raise ValueError(f'Use a Vertical watch (stack="Vertical"); missing columns: {sorted(missing)}')
    if set(metric_columns).intersection(watch.columns):
        raise ValueError('watch already contains metric columns; use the original Vertical watch.')
    if not watch['OptionType'].isin(['Call', 'Put']).all():
        raise ValueError('OptionType must contain only Call or Put, without missing values.')
    numeric = {name: _option_metric_numbers(watch[name]) for name in required - {'OptionType'}}
    bid, ask = numeric['BidPrice'], numeric['AskPrice']
    has_bid = (bid > 0) & (numeric['BidVolume'] > 0)
    has_ask = (ask > 0) & (numeric['AskVolume'] > 0)
    both = has_bid & has_ask
    crossed = both & (bid > ask)
    ordered = both & ~crossed
    incomplete = pd.concat([numeric[c].isna() for c in
                            ('BidPrice', 'BidVolume', 'AskPrice', 'AskVolume')], axis=1).any(axis=1)
    status = np.select(
        [incomplete, crossed, ordered & (bid == ask), ordered, has_bid, has_ask],
        ['Incomplete', 'Crossed', 'Locked', 'TwoSided', 'BidOnly', 'AskOnly'], default='NoQuote')
    # Halving before summation avoids overflow for large finite quote prices.
    midpoint = (ask / 2 + bid / 2).where(ordered)
    spread = (ask - bid).where(ordered)
    if price == 'Mid':
        premium = midpoint
    elif price in ('Ask', 'Bid'):
        premium = numeric[price + 'Price'].where((has_ask if price == 'Ask' else has_bid) & ~crossed)
    else:
        premium = numeric[price + 'Price'].where(numeric[price + 'Price'] > 0)
    spot = numeric[spot_column].where(numeric[spot_column] > 0)
    strike = numeric['StrikePrice'].where(numeric['StrikePrice'] > 0)
    call = watch['OptionType'].eq('Call')
    intrinsic = (spot - strike).where(call, strike - spot).clip(lower=0)
    breakeven = (strike + premium).where(call, strike - premium)
    size = numeric['ContractSize'].where(numeric['ContractSize'] > 0)
    oi = numeric['OpenPositions'].where(numeric['OpenPositions'] > 0)
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        metrics = [midpoint, spread, spread / midpoint * 100, premium, spot,
                   spot / strike, intrinsic, premium - intrinsic, breakeven.where(breakeven >= 0),
                   premium * size, numeric['TradeVolume'] / oi]
    result = watch.copy(deep=True)
    result['QuoteStatus'] = pd.array(status, dtype='string')
    for name, values in zip(metric_columns[1:], metrics):
        result[name] = values.where(np.isfinite(values)).to_numpy(dtype=float)
    return result


def calculate_expiration_payoff(
        underlying_prices: _Sequence[float], strike_price: float, premium: float,
        option_type: _Literal['Call', 'Put'], *, contract_size: int,
        contracts: int = 1, position: _Literal['Long', 'Short'] = 'Long') -> pd.DataFrame:
    """Calculate economic expiration payoff and gross profit without HTTP.

    Parameters
    ----------
    underlying_prices : Sequence[float]
        Required one-dimensional scenario prices, not forecasts. Nonnegative
        finite real numbers; NumPy arrays and pandas Series/Index also work.
        Order and duplicates are preserved; an empty sequence is valid.
    strike_price : float
        Required positive finite strike per underlying unit.
    premium : float
        Required nonnegative finite entry premium per underlying unit, paid for
        Long or received for Short. Supply the actual traded premium when known;
        a displayed ask/bid is only an indicative entry price, not a fill.
    option_type : {'Call', 'Put'}
        Required exact option side. Discover Ticker/OptionType/StrikePrice and
        ContractSize in download_market_watch(stack='Vertical'); inspect the
        underlying, expiration and strike before selecting an exact contract.
    contract_size : int
        Required positive whole underlying units per contract, from the chosen
        contract's ContractSize. There is no default 1000-unit assumption.
    contracts : int, default 1
        Positive whole number of contracts. Boolean values are not counts.
    position : {'Long', 'Short'}, default 'Long'
        Long owns the option; Short writes it. Buying to close an existing short
        is not a new Long position in this single-entry expiration calculation.

    Returns
    -------
    pandas.DataFrame
        Five float64 columns and a fresh RangeIndex: UnderlyingPrice,
        IntrinsicValue, ExpirationPayoff, PremiumCashFlow, GrossProfit.
        IntrinsicValue=max(S_T-K,0) for calls or max(K-S_T,0) for puts. With
        a=+1 for Long or -1 for Short and Q=contracts*contract_size:
        ExpirationPayoff=a*Q*IntrinsicValue; PremiumCashFlow=-a*Q*premium;
        GrossProfit=ExpirationPayoff+PremiumCashFlow. The first two columns
        are prices per underlying unit; the last three are total money amounts.
        All prices must share one currency/unit (rials for fima watch data).

    Notes
    -----
    Assumes economic exercise at expiration with the supplied fixed terms.
    Payoff excludes the entry premium; GrossProfit includes it. Neither models
    automatic exercise, request deadlines, physical delivery/strike funding,
    fees, tax, financing, margin, allocation or default. The cash-equivalent
    economic payoff is not a promised cash-settlement receipt. No annualization,
    discounting, future term adjustment or early closing transaction is implied.
    Input data is not mutated. See docs/options.md#expiration-scenarios.

    Raises
    ------
    ValueError
        Invalid side/position, nonnumeric or nonfinite input, invalid shape,
        negative prices/premium, nonpositive strike, noninteger/nonpositive
        contract_size/contracts, or amounts too large for finite float output.
    """
    if option_type not in ('Call', 'Put') or position not in ('Long', 'Short'):
        raise ValueError('option_type must be Call or Put; position must be Long or Short.')
    scalars = {}
    for name, value in [('strike_price', strike_price), ('premium', premium)]:
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, _Real):
            raise ValueError(f'{name} must be a finite real number.')
        try:
            scalars[name] = float(value)
        except (ValueError, OverflowError) as error:
            raise ValueError(f'{name} must be a finite real number.') from error
        if not np.isfinite(scalars[name]) or scalars[name] < 0 or (name == 'strike_price' and value == 0):
            raise ValueError(f'{name} must be finite and {"positive" if name == "strike_price" else "nonnegative"}.')
    for name, value in [('contract_size', contract_size), ('contracts', contracts)]:
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, _Integral) or value <= 0:
            raise ValueError(f'{name} must be a positive integer.')
    if not isinstance(underlying_prices, (_Sequence, np.ndarray, pd.Series, pd.Index)) or isinstance(underlying_prices, (str, bytes)):
        raise ValueError('underlying_prices must be a one-dimensional sequence of finite nonnegative real numbers.')
    try:
        raw = np.asarray(underlying_prices, dtype=object)
        if raw.ndim != 1 or any(isinstance(v, (bool, np.bool_)) or not isinstance(v, _Real) for v in raw):
            raise ValueError('invalid scenario values or shape')
        spots = raw.astype(float)
        quantity = float(int(contract_size) * int(contracts))
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError('underlying_prices and contract quantities must give finite real amounts.') from error
    if not np.isfinite(spots).all() or (spots < 0).any() or not np.isfinite(quantity):
        raise ValueError('underlying_prices and contract quantities must be finite and nonnegative.')
    sign = 1 if position == 'Long' else -1
    with np.errstate(over='ignore', invalid='ignore'):
        intrinsic = np.maximum(spots - scalars['strike_price'] if option_type == 'Call'
                               else scalars['strike_price'] - spots, 0)
        payoff = sign * quantity * intrinsic
        flow = -sign * quantity * scalars['premium']
        profit = payoff + flow
    if not np.isfinite(flow) or not np.isfinite(payoff).all() or not np.isfinite(profit).all():
        raise ValueError('Scenario cash flows must be finite; reduce prices or contract quantities.')
    return pd.DataFrame({'UnderlyingPrice': spots, 'IntrinsicValue': intrinsic,
                         'ExpirationPayoff': payoff, 'PremiumCashFlow': np.full(len(spots), flow),
                         'GrossProfit': profit}, dtype=float)
