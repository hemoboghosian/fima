import jdatetime as jd
import pandas as pd
import numpy as np
import requests
from persian import convert_ar_characters
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple, List, Literal
import time
from ._data import boolean_series, identifier_series, jalali_date, number_series, time_string


def _public_frame(frame):
    for column in frame:
        if column == "Canceled":
            frame[column] = boolean_series(frame[column])
        elif column == "InstrumentCode":
            frame[column] = identifier_series(frame[column])
        elif column == "JalaliDate":
            frame[column] = frame[column].map(jalali_date)
        elif column == "Time":
            frame[column] = frame[column].map(time_string)
        elif (column in {"PriceChange", "YesterdayPrice", "OpeningPrice", "LowPrice", "HighPrice",
                         "ClosingPrice", "LastPrice", "TransactionCount", "TradeVolume", "TradeValue",
                         "TradeNumber", "Price", "NumberOfShares", "OldNumberOfShares", "NewNumberOfShares",
                         "MarketCap", "SharePercentage", "IndexValue", "LowIndexValue", "HighIndexValue",
                         "PercentageChange", "Change", "UnadjustedClosingPrice", "Capital"}
              or column.startswith(("Retail", "Institutional"))):
            frame[column] = number_series(frame[column])
    if frame.index.name == "JalaliDate":
        frame.index = pd.Index([jalali_date(x) for x in frame.index], name="JalaliDate")
    return frame


def get_share_changes() -> pd.DataFrame:
    tse_url = "https://cdn.tsetmc.com/api/Instrument/GetInstrumentShareChangeByFlow/1/7"
    tse_share_changes = pd.DataFrame(requests.get(tse_url, timeout=15).json()['instrumentShareChange'])
    tse_share_changes.rename(columns={'lVal30': 'InstrumentName', 'lVal18AFC': 'Ticker', 'insCode': 'InstrumentCode'}, inplace=True)
    tse_share_changes.drop(['idn', 'InstrumentCode'], axis=1, inplace=True)
    tse_share_changes.rename(columns={'dEven': 'GregorianDate', 'numberOfShareOld': 'OldNumberOfShares',
                                          'numberOfShareNew': 'NewNumberOfShares'}, inplace=True)

    ifb_url = "https://cdn.tsetmc.com/api/Instrument/GetInstrumentShareChangeByFlow/2/7"
    ifb_share_changes = pd.DataFrame(requests.get(ifb_url, timeout=15).json()['instrumentShareChange'])
    ifb_share_changes.rename(columns={'lVal30': 'InstrumentName', 'lVal18AFC': 'Ticker', 'insCode': 'InstrumentCode'}, inplace=True)
    ifb_share_changes.drop(['idn', 'InstrumentCode'], axis=1, inplace=True)
    ifb_share_changes.rename(columns={'dEven': 'GregorianDate', 'numberOfShareOld': 'OldNumberOfShares',
                                          'numberOfShareNew': 'NewNumberOfShares'}, inplace=True)

    share_changes = pd.concat([tse_share_changes, ifb_share_changes], axis=0, ignore_index=True)
    share_changes['GregorianDate'] = pd.to_datetime(share_changes['GregorianDate'].astype(str)).dt.date
    share_changes['JalaliDate'] = share_changes['GregorianDate'].apply(lambda g: jd.date.fromgregorian(year=g.year, month=g.month, day=g.day))
    share_changes.drop('GregorianDate', axis=1, inplace=True)
    share_changes['InstrumentName'] = share_changes['InstrumentName'].apply(lambda name: convert_ar_characters(name))
    share_changes['Ticker'] = share_changes['Ticker'].apply(lambda name: convert_ar_characters(name))
    return _public_frame(share_changes)


def get_price_adjustments() -> pd.DataFrame:
    tse_url = "https://cdn.tsetmc.com/api/ClosingPrice/GetPriceAdjustByFlow/1/100000"
    tse_price_adjustments = pd.DataFrame(requests.get(tse_url, timeout=15).json()['priceAdjust'])
    tse_price_adjustments['Ticker'] = None
    tse_price_adjustments['InstrumentName'] = None
    tse_price_adjustments['InstrumentCode'] = None
    for index, tse_price_adjustments_record in tse_price_adjustments.iterrows():
        tse_price_adjustments.at[index, 'Ticker'] = tse_price_adjustments_record['instrument']['lVal18AFC']
        tse_price_adjustments.at[index, 'InstrumentName'] = tse_price_adjustments_record['instrument']['lVal30']
        tse_price_adjustments.at[index, 'InstrumentCode'] = tse_price_adjustments_record['instrument']['insCode']
    tse_price_adjustments.drop(['instrument', 'insCode', 'corporateTypeCode'], axis=1, inplace=True)
    tse_price_adjustments.rename(columns={'dEven': 'GregorianDate', 'pClosing': 'ClosingPrice',
                                          'pClosingNotAdjusted': 'UnadjustedClosingPrice'}, inplace=True)

    ifb_url = "https://cdn.tsetmc.com/api/ClosingPrice/GetPriceAdjustByFlow/2/100000"
    ifb_price_adjustments = pd.DataFrame(requests.get(ifb_url, timeout=15).json()['priceAdjust'])
    ifb_price_adjustments['Ticker'] = None
    ifb_price_adjustments['InstrumentName'] = None
    ifb_price_adjustments['InstrumentCode'] = None
    for index, ifb_price_adjustments_record in ifb_price_adjustments.iterrows():
        ifb_price_adjustments.at[index, 'Ticker'] = ifb_price_adjustments_record['instrument']['lVal18AFC']
        ifb_price_adjustments.at[index, 'InstrumentName'] = ifb_price_adjustments_record['instrument']['lVal30']
        ifb_price_adjustments.at[index, 'InstrumentCode'] = ifb_price_adjustments_record['instrument']['insCode']
    ifb_price_adjustments.drop(['instrument', 'insCode', 'corporateTypeCode'], axis=1, inplace=True)
    ifb_price_adjustments.rename(columns={'dEven': 'GregorianDate', 'pClosing': 'ClosingPrice',
                                          'pClosingNotAdjusted': 'UnadjustedClosingPrice'}, inplace=True)

    price_adjustments = pd.concat([tse_price_adjustments, ifb_price_adjustments], axis=0, ignore_index=True)
    price_adjustments['GregorianDate'] = pd.to_datetime(price_adjustments['GregorianDate'].astype(str)).dt.date
    price_adjustments['JalaliDate'] = price_adjustments['GregorianDate'].apply(lambda g: jd.date.fromgregorian(year=g.year, month=g.month, day=g.day))
    price_adjustments.drop('GregorianDate', axis=1, inplace=True)
    price_adjustments['InstrumentName'] = price_adjustments['InstrumentName'].apply(lambda name: convert_ar_characters(name))
    price_adjustments['Ticker'] = price_adjustments['Ticker'].apply(lambda name: convert_ar_characters(name))
    return _public_frame(price_adjustments)


def get_supervision_lists() -> pd.DataFrame:
    supervision_lists = []
    for index in range(1, 4):
        url = f"https://cdn.tsetmc.com/api/Supervision/GetSupervisionListBySourceID/1/{index}"
        supervision_lists.append(pd.DataFrame(requests.get(url, timeout=15).json()['supervision']))
    supervision_lists = pd.concat(supervision_lists, ignore_index=True)

    supervision_lists['Ticker'] = None
    supervision_lists['InstrumentName'] = None
    for index, supervision_list_record in supervision_lists.iterrows():
        supervision_lists.at[index, 'Ticker'] = supervision_list_record['instrument']['lVal18AFC']
        supervision_lists.at[index, 'InstrumentName'] = supervision_list_record['instrument']['lVal30']

    supervision_lists = supervision_lists[['insCode', 'reasons', 'Ticker', 'InstrumentName']]
    supervision_lists.rename(columns={'insCode': 'InstrumentCode', 'reasons': 'Reasons'}, inplace=True)

    supervision_lists['Reasons'] = supervision_lists['Reasons'].str.split('<br>')
    supervision_lists = supervision_lists.explode('Reasons').reset_index(drop=True)
    supervision_lists = supervision_lists[supervision_lists['Reasons'] != '']
    return _public_frame(supervision_lists)


def _fetch_shareholders_for_date(args):
    jdate, instrument_code = args
    try:
        gdate = jd.date(*map(int, str(jdate).split('-'))).togregorian().isoformat().replace('-', '')
        url = f"https://cdn.tsetmc.com/api/Shareholder/{instrument_code}/{gdate}"
        data = pd.DataFrame(requests.get(url, timeout=15).json().get('shareShareholder'))
        return data
    except:
        return None


def get_ticker_historical_shareholders(ticker: str, _max_workers: int = 10) -> pd.DataFrame:
    instrument_code = _find_instrument_code(ticker)
    jdates = get_ticker_historical_data(ticker_instrument_code=instrument_code).index.tolist()
    args = [(jdate, instrument_code) for jdate in jdates]

    with ThreadPoolExecutor(max_workers=_max_workers) as executor: results = list(executor.map(_fetch_shareholders_for_date, args))

    ticker_historical_shareholders_list = [df for df in results if df is not None]

    if not ticker_historical_shareholders_list:
        return pd.DataFrame()

    ticker_historical_shareholders = pd.concat(ticker_historical_shareholders_list, ignore_index=True)

    ticker_historical_shareholders.drop(columns=['shareHolderID', 'cIsin', 'change', 'changeAmount'], inplace=True, errors='ignore')
    ticker_historical_shareholders.rename(columns={'shareHolderName': 'ShareholderName', 'dEven': 'GregorianDate', 'numberOfShares': 'NumberOfShares',
                                                    'perOfShares': 'SharePercentage', 'shareHolderShareID': 'ShareHolderShareID'}, inplace=True)

    ticker_historical_shareholders.drop(columns=['ShareHolderShareID'], inplace=True)

    ticker_historical_shareholders['ShareholderName'] = ticker_historical_shareholders['ShareholderName'].apply(convert_ar_characters)

    ticker_historical_shareholders['GregorianDate'] = pd.to_datetime(ticker_historical_shareholders['GregorianDate'].astype(str)).dt.date
    ticker_historical_shareholders['JalaliDate'] = ticker_historical_shareholders['GregorianDate'].apply(lambda g: jd.date.fromgregorian(year=g.year, month=g.month, day=g.day))

    ticker_historical_shareholders.drop('GregorianDate', axis=1, inplace=True)

    return _public_frame(ticker_historical_shareholders)


def _fetch_client_types_for_date(args):
    jdate, instrument_code = args
    try:
        gdate = jd.date(*map(int, str(jdate).split('-'))).togregorian().isoformat().replace('-', '')
        url = f"https://cdn.tsetmc.com/api/ClientType/GetClientTypeHistory/{instrument_code}/{gdate}"
        response = requests.get(url, timeout=15).json()
        df = pd.DataFrame([response['clientType']])
        return df
    except:
        return None


def get_ticker_historical_trades_client_type(ticker: str, _max_workers: int = 10) -> pd.DataFrame:
    instrument_code = _find_instrument_code(ticker)
    jdates = get_ticker_historical_data(ticker_instrument_code=instrument_code).index.tolist()
    args = [(jdate, instrument_code) for jdate in jdates]

    with ThreadPoolExecutor(max_workers=_max_workers) as executor:
        results = list(executor.map(_fetch_client_types_for_date, args))

    ticker_historical_trades_client_type_list = [df for df in results if df is not None]
    if not ticker_historical_trades_client_type_list:
        return pd.DataFrame()

    ticker_historical_trades_client_type = pd.concat(ticker_historical_trades_client_type_list, ignore_index=True)

    ticker_historical_trades_client_type.rename(
        columns={'recDate': 'GregorianDate', 'insCode': 'InstrumentCode', 'buy_I_Volume': 'RetailBuyVolume',
                 'buy_N_Volume': 'InstitutionalBuyVolume', 'buy_I_Value': 'RetailBuyValue', 'buy_N_Value': 'InstitutionalBuyValue',
                 'buy_N_Count': 'InstitutionalBuyCount', 'sell_I_Volume': 'RetailSellVolume',
                 'buy_I_Count': 'RetailBuyCount', 'sell_N_Volume': 'InstitutionalSellVolume',
                 'sell_I_Value': 'RetailSellValue', 'sell_N_Value': 'InstitutionalSellValue',
                 'sell_N_Count': 'InstitutionalSellCount', 'sell_I_Count': 'RetailSellCount'}, inplace=True)

    ticker_historical_trades_client_type['GregorianDate'] = pd.to_datetime(ticker_historical_trades_client_type['GregorianDate'].astype(str)).dt.date
    ticker_historical_trades_client_type['JalaliDate'] = \
        ticker_historical_trades_client_type['GregorianDate'].apply(lambda g: jd.date.fromgregorian(year=g.year, month=g.month, day=g.day))

    ticker_historical_trades_client_type.drop(['GregorianDate', 'InstrumentCode'], axis=1, inplace=True)
    ticker_historical_trades_client_type.set_index('JalaliDate', inplace=True)
    return _public_frame(ticker_historical_trades_client_type)


def _fetch_shares_no_for_date(args):
    jdate, instrument_code = args
    try:
        gdate = jd.date(*map(int, str(jdate).split('-'))).togregorian().isoformat().replace('-', '')
        url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentHistory/{instrument_code}/{gdate}"
        data = requests.get(url, timeout=15).json()
        return jdate, int(data['instrumentHistory']['zTitad'])
    except:
        return jdate, None


def get_ticker_historical_market_caps(ticker: str, _max_workers: int = 10) -> pd.DataFrame:
    ticker_instrument_code = _find_instrument_code(ticker)
    df = get_ticker_historical_data(ticker_instrument_code=ticker_instrument_code)[['ClosingPrice']]
    date_args = [(jdate, ticker_instrument_code) for jdate in df.index]

    with ThreadPoolExecutor(max_workers=_max_workers) as executor:
        results = list(executor.map(_fetch_shares_no_for_date, date_args))

    shares_no_dict = dict(results)
    df['NumberOfShares'] = df.index.map(shares_no_dict.get)

    df['MarketCap'] = df['NumberOfShares'] * df['ClosingPrice']
    return _public_frame(df)


def _get_ticker_info_with_instrument_code(instrument_id: int):
    try:
        url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/{instrument_id}"
        data = requests.get(url, timeout=15).json()['instrumentInfo']
        return instrument_id, data.get('lVal18AFC', ''), data.get('lVal30', '')
    except:
        return instrument_id, None, None


def _update_ticker_info_parallel(df: pd.DataFrame, _max_workers: int = 10) -> pd.DataFrame:
    instrument_codes = df['InstrumentID'].tolist()

    with ThreadPoolExecutor(max_workers=_max_workers) as executor:
        results = list(executor.map(_get_ticker_info_with_instrument_code, instrument_codes))

    info_df = pd.DataFrame(results, columns=['InstrumentID', 'Ticker', 'InstrumentName']).set_index('InstrumentID')

    df = df.set_index('InstrumentID')
    df[['Ticker', 'InstrumentName']] = info_df
    return df.reset_index()


def _get_static_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    url = "https://cdn.tsetmc.com/api/StaticData/GetStaticData"
    static_data_combined = requests.get(url, timeout=15).json()['staticData']
    paper_types = []
    industrial_groups = []
    for static_data in static_data_combined:
        if static_data['type'] == 'IndustrialGroup':
            industrial_groups.append(static_data)
        elif static_data['type'] == 'PaperType':
            paper_types.append(static_data)

    paper_types = pd.DataFrame(paper_types)
    paper_types['name'] = paper_types['name'].apply(lambda name: convert_ar_characters(name.strip()))
    # paper_types['description'] = paper_types['description'].apply(lambda description: description.strip())
    paper_types.drop(['description', 'type'], axis=1, inplace=True)
    paper_types.rename(columns={'code': 'Code', 'name': 'Instrument', 'id': 'ID'}, inplace=True)

    industrial_groups = pd.DataFrame(industrial_groups)
    industrial_groups['name'] = industrial_groups['name'].apply(lambda name: convert_ar_characters(name.strip()))
    # industrial_groups['description'] = industrial_groups['description'].apply(lambda description: description.strip())
    industrial_groups.drop(['description', 'type'], axis=1, inplace=True)
    industrial_groups.rename(columns={'code': 'Code', 'name': 'IndustryGroup', 'id': 'ID'}, inplace=True)
    industrial_groups = industrial_groups[['ID', 'Code', 'IndustryGroup']]

    return paper_types, industrial_groups


def adjust_historical_prices(data: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with TSETMC reference-price-based backward-adjusted prices.

    Supply one instrument's raw history, including ClosingPrice, YesterdayPrice,
    LastPrice, OpeningPrice, LowPrice and HighPrice. Dates must be in GregorianDate
    (Gregorian), JalaliDate (Jalali), a DatetimeIndex, or the JalaliDate index returned by
    get_ticker_historical_data. Identifier columns, when present, must describe
    one known instrument; histories from different instruments must be processed
    separately, even when their tickers match.

    Calculation uses ascending actual dates and every supplied observation,
    including zero-trade rows. Each ratio is the current YesterdayPrice divided
    by the preceding ClosingPrice. A row's AdjustmentFactor is the product of all
    subsequent ratios. The latest supplied date has factor 1; filtering BEFORE
    calling this function changes that endpoint. Later actions can revise older
    adjusted levels. The oldest reference is unused, since no preceding close
    is available. Gaps are linked as observed, not certified as complete sessions
    or classified as corporate actions.

    Append AdjustmentFactor and AdjustedClosingPrice, AdjustedLastPrice,
    AdjustedOpeningPrice, AdjustedLowPrice and AdjustedHighPrice as float64 values
    without rounding. Preserve the index, row order and all raw columns. Empty
    histories return empty added columns; a single row has factor 1.

    Raise ValueError for missing columns/dates, duplicate dates, instrument
    mixing, invalid prices/references or nonfinite arithmetic. Prices must be
    positive and finite, except OpeningPrice may be zero even on traded rows:
    TSETMC can supply a zero opening field while reporting positive trade
    prices. Preserve that zero in AdjustedOpeningPrice without imputing a price.
    Other zero non-closing prices require TransactionCount == 0. Positive
    reference prices of 1000 are valid.
    No network requests are made. This is not a validated total-return series.
    """
    prices = ['ClosingPrice', 'LastPrice', 'OpeningPrice', 'LowPrice', 'HighPrice']
    if not data.columns.is_unique:
        raise ValueError('Historical data must have unique column names.')
    missing = [column for column in prices + ['YesterdayPrice'] if column not in data]
    if missing:
        raise ValueError(f'Missing historical price columns: {missing}')
    result = data.copy()
    if data.empty:
        for column in ['AdjustmentFactor'] + ['Adjusted' + price for price in prices]:
            result[column] = np.array([], dtype=float)
        return result

    identifiers = [column for column in ['InstrumentCode', 'insCode'] if column in data]
    if not identifiers and 'Ticker' in data:
        identifiers = ['Ticker']
    for column in identifiers:
        values = data[column]
        if values.isna().any() or values.astype(str).str.strip().eq('').any() or values.nunique() != 1:
            raise ValueError(f'Historical data must contain one known instrument ({column}).')

    try:
        if 'GregorianDate' in data:
            dates = pd.to_datetime(data['GregorianDate'].astype(str), errors='raise', format='mixed')
        elif 'JalaliDate' in data or data.index.name == 'JalaliDate':
            source = data['JalaliDate'] if 'JalaliDate' in data else data.index
            dates = pd.to_datetime([
                (value if isinstance(value, jd.date) else jd.date(*map(int, str(value).split('-')))).togregorian()
                for value in source
            ])
        elif isinstance(data.index, pd.DatetimeIndex):
            dates = data.index
        else:
            raise ValueError('Supply GregorianDate, JalaliDate, a DatetimeIndex or a JalaliDate index.')
        dates = pd.DatetimeIndex(dates).normalize()
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'Invalid historical dates: {exc}') from exc
    if dates.isna().any() or dates.has_duplicates:
        raise ValueError('Historical dates must be present and unique per instrument.')
    order = np.argsort(dates.asi8, kind='stable')

    numeric = {}
    zero_trade = (data['TransactionCount'].eq(0).fillna(False).to_numpy(dtype=bool)
                  if 'TransactionCount' in data else np.zeros(len(data), dtype=bool))
    for column in prices + ['YesterdayPrice']:
        values = pd.to_numeric(data[column], errors='coerce').to_numpy(dtype=float, na_value=np.nan)
        checked = values[order][1:] if column == 'YesterdayPrice' else values
        valid = np.isfinite(checked) & (checked > 0)
        if column == 'OpeningPrice':
            valid |= values == 0
        elif column in prices and column != 'ClosingPrice':
            valid |= zero_trade & (values == 0)
        if not valid.all():
            requirement = 'nonnegative' if column == 'OpeningPrice' else 'positive'
            raise ValueError(f'{column} must contain finite {requirement} prices; '
                             'zero LastPrice/LowPrice/HighPrice require TransactionCount == 0.')
        numeric[column] = values

    with np.errstate(over='ignore', under='ignore', invalid='ignore', divide='ignore'):
        subsequent = np.ones(len(data), dtype=float)
        subsequent[:-1] = numeric['YesterdayPrice'][order][1:] / numeric['ClosingPrice'][order][:-1]
        chronological_factors = np.cumprod(subsequent[::-1])[::-1]
        factors = np.empty(len(data), dtype=float)
        factors[order] = chronological_factors
        if not (np.isfinite(factors) & (factors > 0)).all():
            raise ValueError('Adjustment factors must remain finite and positive.')
        result['AdjustmentFactor'] = factors
        for column in prices:
            adjusted = numeric[column] * factors
            if not np.isfinite(adjusted).all() or ((numeric[column] > 0) & (adjusted == 0)).any():
                raise ValueError(f'Adjusted{column} must remain finite and positive for positive prices.')
            result['Adjusted' + column] = adjusted
    return result


def get_ticker_historical_data(ticker: str=None, ticker_instrument_code: str=None, *,
                               adjust_prices: bool=False) -> pd.DataFrame:
    """Download official TSETMC daily history with a Jalali date index.

    ticker is resolved only when ticker_instrument_code is None. ClosingPrice is
    pClosing (official close); LastPrice is pDrCotVal (last trade), and
    YesterdayPrice is priceYesterday (exchange reference). With adjust_prices
    False, return raw columns. True appends floating-point adjusted prices via
    adjust_historical_prices, anchored at the latest returned observation.
    All raw observations and non-price fields remain unchanged. No date filter
    is applied. Provider/network errors propagate; invalid adjustment inputs
    raise ValueError. An unresolved ticker retains the legacy None result.
    """
    if ticker_instrument_code is None:
        ticker_instrument_code  = _find_instrument_code(ticker)
    if ticker_instrument_code != '':
        url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/{ticker_instrument_code}/0"
        ticker_historical_data = pd.DataFrame(requests.get(url, timeout=15).json()['closingPriceDaily'])
        if ticker_historical_data.empty:
            ticker_historical_data = pd.DataFrame(columns=[
                'PriceChange', 'LowPrice', 'HighPrice', 'YesterdayPrice', 'OpeningPrice',
                'ClosingPrice', 'LastPrice', 'TransactionCount', 'TradeVolume', 'TradeValue',
            ], index=pd.Index([], name='JalaliDate'))
            return _public_frame(adjust_historical_prices(ticker_historical_data) if adjust_prices else ticker_historical_data)
        ticker_historical_data.drop(['iClose', 'id', 'hEven', 'yClose', 'last'], axis=1, inplace=True)
        ticker_historical_data.rename(columns={'priceChange': 'PriceChange', 'priceMin': 'LowPrice', 'priceMax': 'HighPrice',
                                               'priceYesterday': 'YesterdayPrice', 'priceFirst': 'OpeningPrice',
                                               'dEven': 'GregorianDate', 'pClosing': 'ClosingPrice',
                                               'pDrCotVal': 'LastPrice', 'zTotTran': 'TransactionCount', 'qTotTran5J': 'TradeVolume',
                                               'qTotCap': 'TradeValue'}, inplace=True)
        ticker_historical_data['GregorianDate'] = pd.to_datetime(ticker_historical_data['GregorianDate'], format='%Y%m%d').dt.date
        ticker_historical_data['JalaliDate'] = ticker_historical_data['GregorianDate'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
        ticker_historical_data.drop('GregorianDate', axis=1, inplace=True)
        ticker_historical_data.set_index('JalaliDate', inplace=True)
        ticker_historical_data = _public_frame(ticker_historical_data)
        if adjust_prices:
            ticker_historical_data = adjust_historical_prices(ticker_historical_data)
        ticker_historical_data.drop('insCode', axis=1, inplace=True)
        return _public_frame(ticker_historical_data)
    else:
        print('Could not find ticker instrument code to download the historical data.')
        return None


def _find_instrument_code(search_key: str, trade_type: List[Literal['Ordinary', 'Block', 'Jobrani', 'Omde']] = 'Ordinary') -> str:
    search_key = convert_ar_characters(search_key)
    search_result = pd.DataFrame(requests.get(f'https://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/{search_key}', timeout=15).json()['instrumentSearch'])
    search_result['lVal18AFC'] = search_result['lVal18AFC'].apply(convert_ar_characters)
    found_record = search_result[search_result['lVal18AFC'] == search_key].reset_index(drop=True)
    if len(found_record) == 0:
        print('The search key you entered is not present.')
        return ''
    else:
        if trade_type == 'Ordinary':
            return found_record.loc[0, 'insCode']
        elif trade_type == 'Block':
            return found_record.loc[0, 'insCode2']
        elif trade_type == 'Jobrani':
            return found_record.loc[0, 'insCode3']
        elif trade_type == 'Omde':
            return found_record.loc[0, 'insCode4']
        else:
            return found_record.loc[0, 'insCode']


    # url = "https://old.tsetmc.com/tsev2/data/MarketWatchInit.aspx?h=0&r=0"
    # response = requests.get(url, timeout=15, timeout=10)
    # time.sleep(5)
    # raw_text = response.text
    #
    # percent_index = raw_text.find('%')
    # if percent_index == -1:
    #     raise ValueError("No '%' found in the response.")
    # trimmed_text = raw_text[percent_index + 1:]
    # if '@' not in trimmed_text:
    #     raise ValueError("The trimmed response does not contain '@'. Unexpected format.")
    #
    # _, main_data = trimmed_text.split('@', 1)
    # records = [row for row in main_data.split(';') if row.strip()]
    # parsed_data = [row.split(',') for row in records]
    #
    # market_watch = pd.DataFrame(parsed_data)
    # market_watch = market_watch.iloc[:, [0, 2, 3]]
    # market_watch.rename(columns={0: 'InstrumentID', 2: 'Ticker', 3: 'InstrumentName'}, inplace=True)
    #
    # unknown_instrument_codes = market_watch[market_watch['Ticker'].astype(str).str.fullmatch(r'\d+(\.\d+)?')].copy()
    # known_instrument_codes = market_watch[~market_watch['Ticker'].astype(str).str.fullmatch(r'\d+(\.\d+)?')].copy()
    # known_instrument_codes['Ticker'] = known_instrument_codes['Ticker'].apply(lambda ar_ticker: convert_ar_characters(ar_ticker))
    #
    # if ticker in known_instrument_codes['Ticker'].values:
    #     found_item = known_instrument_codes[known_instrument_codes['Ticker'] == ticker]
    #     return found_item['InstrumentID'].values[0]
    # else:
    #     tree_map_instrument_codes = _get_instrument_codes_tree_map()
    #     if ticker in tree_map_instrument_codes['Ticker'].values:
    #         found_item = tree_map_instrument_codes[tree_map_instrument_codes['Ticker'] == ticker]
    #         return found_item['InstrumentID'].values[0]
    #     else:
    #         unknown_instrument_codes = _update_ticker_info_parallel(unknown_instrument_codes)
    #         unknown_instrument_codes['Ticker'] = unknown_instrument_codes['Ticker'].apply(lambda ar_ticker: convert_ar_characters(ar_ticker))
    #         # still_unknown_instrument_codes = unknown_instrument_codes[unknown_instrument_codes['Ticker'].astype(str).str.fullmatch(r'\d+(\.\d+)?')].copy()
    #         if ticker in unknown_instrument_codes['Ticker'].values:
    #             found_item = unknown_instrument_codes[unknown_instrument_codes['Ticker'] == ticker]
    #             return found_item['InstrumentID'].values[0]
    # return ''


def get_ticker_intraday_trades(ticker: str) -> pd.DataFrame:
    ticker_instrument_code  = _find_instrument_code(ticker)
    url = f"https://cdn.tsetmc.com/api/Trade/GetTrade/{ticker_instrument_code}"
    ticker_intraday_trades = pd.DataFrame(requests.get(url, timeout=15).json()['trade'])
    ticker_intraday_trades.drop(['insCode', 'dEven', 'qTitNgJ', 'iSensVarP', 'pPhSeaCotJ', 'pPbSeaCotJ',
                                 'iAnuTran', 'xqVarPJDrPRf'], axis=1, inplace=True)
    ticker_intraday_trades.rename(columns={'nTran': 'TradeNumber', 'hEven': 'Time', 'qTitTran': 'TradeVolume', 'pTran':
        'Price', 'canceled': 'Canceled'}, inplace=True)
    ticker_intraday_trades['Time'] = pd.to_datetime(ticker_intraday_trades['Time'], format="%H%M%S").dt.time
    return _public_frame(ticker_intraday_trades)


def _get_instrument_codes_tree_map() -> pd.DataFrame:
    sector = 0
    size = 20000
    based_on: str = 1

    url = ("https://cdn.tsetmc.com/api/ClosingPrice/GetMarketMap?"
           "market=AllAll-TseAll-OtcAll-TseDebt-TseEtf-TseDerivative-TseStock-OtcDebt-OtcEtf-OtcBase-OtcDerivative-OtcStock-&"
           f"size={size}&sector={sector}&typeSelected={based_on}&hEven=0")
    tree_map_data = pd.DataFrame(requests.get(url, timeout=15).json())
    time.sleep(5)
    instrument_codes = tree_map_data.loc[:, ['insCode', 'lVal18AFC', 'lVal30']]
    instrument_codes.columns = ['InstrumentCode', 'Ticker', 'InstrumentName']
    instrument_codes['Ticker'] = instrument_codes['Ticker'].apply(lambda ticker_code: convert_ar_characters(ticker_code))
    return instrument_codes


def get_indexes_status() -> pd.DataFrame:
    tse_url = "https://cdn.tsetmc.com/api/Index/GetIndexB1LastAll/SelectedIndexes/1"
    tse_idnexes_status = requests.get(tse_url, timeout=15).json()['indexB1']

    ifb_url = "https://cdn.tsetmc.com/api/Index/GetIndexB1LastAll/SelectedIndexes/2"
    ifb_indexes_status = requests.get(ifb_url, timeout=15).json()['indexB1']

    indexes_status = tse_idnexes_status + ifb_indexes_status
    indexes_status = pd.DataFrame(indexes_status)
    indexes_status.rename(columns={'insCode': 'InstrumentCode', 'hEven': 'Time', 'xDrNivJIdx004': 'IndexValue',
                                 'xPhNivJIdx004': 'HighIndexValue', 'xPbNivJIdx004': 'LowIndexValue', 'xVarIdxJRfV': 'PercentageChange',
                                 'indexChange': 'Change', 'lVal30': 'Index'}, inplace=True)
    indexes_status.drop(['dEven', 'c1', 'c2', 'c3', 'c4', 'last'], inplace=True, axis=1)
    indexes_status['Index'] = indexes_status['Index'].apply(lambda index: convert_ar_characters(index))
    indexes_status['Index'] = indexes_status['Index'].str.replace('شاخص قیمت(وزنی-ارزشی)', 'شاخص قیمت (وزنی-ارزشی)')
    indexes_status.set_index('Index', inplace=True, drop=True)
    return _public_frame(indexes_status)


def get_index_historical_data(index: str) -> pd.DataFrame:
    indexes_status = get_indexes_status()
    index_instrument_code = indexes_status.loc[index, 'InstrumentCode']
    url = f"https://cdn.tsetmc.com/api/Index/GetIndexB2History/{index_instrument_code}"
    index_historical_data = pd.DataFrame(requests.get(url, timeout=15).json()['indexB2'])
    index_historical_data.rename(columns={'insCode': 'InstrumentCode', 'dEven': 'GregorianDate', 'xNivInuClMresIbs': 'IndexValue', 'xNivInuPbMresIbs': 'LowIndexValue',
                                          'xNivInuPhMresIbs': 'HighIndexValue'}, inplace=True)
    index_historical_data['GregorianDate'] = pd.to_datetime(index_historical_data['GregorianDate'], format='%Y%m%d').dt.date
    index_historical_data['JalaliDate'] = index_historical_data['GregorianDate'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
    index_historical_data.drop(['InstrumentCode', 'GregorianDate'], inplace=True, axis=1)
    index_historical_data.set_index('JalaliDate', inplace=True, drop=True)
    index_historical_data.drop(columns=['LowIndexValue', 'HighIndexValue'], inplace=True)
    return _public_frame(index_historical_data)


def get_index_last_intraday_data(index: str) -> pd.DataFrame:
    indexes_status = get_indexes_status()
    index_instrument_code = indexes_status.loc[index, 'InstrumentCode']
    url = f"https://cdn.tsetmc.com/api/Index/GetIndexB1LastDay/{index_instrument_code}"
    index_intradyay_data = pd.DataFrame(requests.get(url, timeout=15).json()['indexB1'])
    index_intradyay_data.rename(columns={'insCode': 'InstrumentCode', 'dEven': 'GregorianDate', 'xDrNivJIdx004': 'IndexValue', 'xPhNivJIdx004': 'HighIndexValue',
                                          'xPbNivJIdx004': 'LowIndexValue', 'hEven': 'Time', 'xVarIdxJRfV': 'PercentageChange'}, inplace=True)
    index_intradyay_data['GregorianDate'] = pd.to_datetime(index_intradyay_data['GregorianDate'], format='%Y%m%d').dt.date
    index_intradyay_data['JalaliDate'] = index_intradyay_data['GregorianDate'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
    index_intradyay_data['Time'] = pd.to_datetime(index_intradyay_data['Time'], format='%H%M%S').dt.time
    index_intradyay_data.drop(['InstrumentCode', 'GregorianDate', 'last', 'indexChange', 'lVal30', 'c1', 'c2', 'c3', 'c4'], inplace=True, axis=1)
    index_intradyay_data = index_intradyay_data[['JalaliDate', 'Time', 'IndexValue', 'LowIndexValue', 'HighIndexValue', 'PercentageChange']]
    return _public_frame(index_intradyay_data)


def get_index_companies(index: str, thirty_days_history: bool=False) -> Tuple[pd.DataFrame, pd.DataFrame]:
    indexes_status = get_indexes_status()
    index_instrument_code = indexes_status.loc[index, 'InstrumentCode']
    url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetIndexCompany/{index_instrument_code}"
    index_companies_data = requests.get(url, timeout=15).json()
    index_companies = pd.DataFrame(index_companies_data['indexCompany'])
    index_companies.rename(columns={'instrument': 'Instrument', 'priceChange': 'PriceChange', 'priceMin': 'LowPrice',
                                    'priceMax': 'HighPrice', 'priceYesterday': 'YesterdayPrice', 'priceFirst': 'OpeningPrice',
                                    'insCode': 'InstrumentCode', 'pClosing': 'ClosingPrice', 'pDrCotVal': 'LastPrice',
                                    'zTotTran': 'TransactionCount', 'qTotTran5J': 'TradeVolume', 'qTotCap': 'TradeValue'}, inplace=True)
    index_companies['Ticker'] = index_companies['Instrument'].apply(lambda instrument: convert_ar_characters(instrument['lVal18AFC']))
    index_companies['InstrumentName'] = index_companies['Instrument'].apply(lambda instrument: convert_ar_characters(instrument['lVal30']))
    index_companies.drop(['instrumentState', 'lastHEven', 'finalLastDate', 'nvt', 'mop', 'pRedTran',
                          'thirtyDayClosingHistory', 'last', 'id', 'dEven', 'hEven', 'iClose', 'yClose', 'Instrument'],
                         inplace=True, axis=1)
    index_companies = index_companies[['Ticker', 'InstrumentName', 'InstrumentCode', 'YesterdayPrice', 'OpeningPrice', 'LowPrice',
                                       'HighPrice', 'ClosingPrice', 'PriceChange', 'LastPrice', 'TransactionCount', 'TradeVolume', 'TradeValue']]
    index_companies.set_index('Ticker', inplace=True, drop=True)
    tickers_instrument_code = index_companies[['InstrumentCode']].reset_index().set_index('InstrumentCode')

    if thirty_days_history:
        index_companies_past_30_days = pd.DataFrame(index_companies_data['relatedCompanyThirtyDayHistory'])
        index_companies_past_30_days = index_companies_past_30_days[['insCode', 'dEven', 'pClosing']]
        index_companies_past_30_days.rename(columns={'insCode': 'InstrumentCode', 'dEven': 'GregorianDate', 'pClosing': 'ClosingPrice'}, inplace=True)
        index_companies_past_30_days['Ticker'] = \
            index_companies_past_30_days['InstrumentCode'].apply(lambda instrument_code: tickers_instrument_code.loc[instrument_code, 'Ticker'])
        index_companies_past_30_days['GregorianDate'] = pd.to_datetime(index_companies_past_30_days['GregorianDate'], format='%Y%m%d').dt.date
        index_companies_past_30_days['JalaliDate'] = index_companies_past_30_days['GregorianDate'].apply(
            lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
        index_companies_past_30_days.drop(['InstrumentCode', 'GregorianDate'], axis=1, inplace=True)
        index_companies_past_30_days = index_companies_past_30_days[['Ticker', 'JalaliDate', 'ClosingPrice']]
    else:
        index_companies_past_30_days = pd.DataFrame()
    return _public_frame(index_companies), _public_frame(index_companies_past_30_days)


def get_tickers(tse: bool, ifb: bool, details: bool = False) -> pd.DataFrame:
    if not tse and not ifb:
        print("At least one of ifb and tse must be True")
        return pd.DataFrame()
    tickers = pd.DataFrame(columns=['InstrumentCode', 'Ticker', 'InstrumentName', 'Market'])
    if tse:
        url = "https://cdn.tsetmc.com/api/ClosingPrice/GetIndexCompany/32097828799138957"
        tse_tickers = pd.DataFrame(requests.get(url, timeout=15).json()['indexCompany'])
        tse_tickers.rename(columns={'insCode': 'InstrumentCode'}, inplace=True)
        tse_tickers['Ticker'] = tse_tickers['instrument'].apply(lambda instrument: instrument['lVal18AFC'])
        tse_tickers['InstrumentName'] = tse_tickers['instrument'].apply(lambda instrument: instrument['lVal30'])
        tse_tickers = tse_tickers[['InstrumentCode', 'Ticker', 'InstrumentName']]
        tse_tickers['Market'] = 'TSE'
        tickers = pd.concat([tickers, tse_tickers], axis=0)
    if ifb:
        url = "https://cdn.tsetmc.com/api/ClosingPrice/GetIndexCompany/43685683301327984"
        ifb_tickers = pd.DataFrame(requests.get(url, timeout=15).json()['indexCompany'])
        ifb_tickers.rename(columns={'insCode': 'InstrumentCode'}, inplace=True)
        ifb_tickers['Ticker'] = ifb_tickers['instrument'].apply(lambda instrument: instrument['lVal18AFC'])
        ifb_tickers['InstrumentName'] = ifb_tickers['instrument'].apply(lambda instrument: instrument['lVal30'])
        ifb_tickers = ifb_tickers[['InstrumentCode', 'Ticker', 'InstrumentName']]
        ifb_tickers['Market'] = 'IFB'
        tickers = pd.concat([tickers, ifb_tickers], axis=0)

    if details:
        tickers.set_index('Ticker', inplace=True)
        tickers.loc[:, ['FiscalYear', 'Auditor', 'Website', 'Capital', 'ActivitySubject']] = None
        for ticker in tickers.index:
            try:
                ticker_info = requests.get(f"https://cdn.tsetmc.com/api/Codal/GetCodalPublisherBySymbol/{ticker}", timeout=15).json()['codalPublisher']
                tickers.loc[ticker, 'FiscalYear'] = ticker_info['financialYear']
                tickers.loc[ticker, 'Auditor'] = ticker_info['auditorName']
                tickers.loc[ticker, 'Website'] = ticker_info['website']
                tickers.loc[ticker, 'Capital'] = ticker_info['listedCapital']
                tickers.loc[ticker, 'ActivitySubject'] = ticker_info['activitySubject']
            except:
                print(f'There is no info related to {ticker}.')
                continue
    return _public_frame(tickers)
