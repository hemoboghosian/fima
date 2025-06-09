import jdatetime as jd
import pandas as pd
import requests
from persian import convert_ar_characters
import time
from concurrent.futures import ThreadPoolExecutor


def get_supervision_lists() -> pd.DataFrame:
    supervision_lists = []
    for index in range(1, 4):
        url = f"https://cdn.tsetmc.com/api/Supervision/GetSupervisionListBySourceID/1/{index}"
        supervision_lists.append(pd.DataFrame(requests.get(url).json()['supervision']))
    supervision_lists = pd.concat(supervision_lists, ignore_index=True)

    supervision_lists['Ticker'] = None
    supervision_lists['Name'] = None
    for index, supervision_list_record in supervision_lists.iterrows():
        supervision_lists.at[index, 'Ticker'] = supervision_list_record['instrument']['lVal18AFC']
        supervision_lists.at[index, 'Name'] = supervision_list_record['instrument']['lVal30']

    supervision_lists = supervision_lists[['insCode', 'reasons', 'Ticker', 'Name']]
    supervision_lists.rename(columns={'insCode': 'InstrumentCode', 'reasons': 'Reasons'}, inplace=True)

    supervision_lists['Reasons'] = supervision_lists['Reasons'].str.split('<br>')
    supervision_lists = supervision_lists.explode('Reasons').reset_index(drop=True)
    supervision_lists = supervision_lists[supervision_lists['Reasons'] != '']
    return supervision_lists


def _fetch_shareholders_for_date(args):
    jdate, instrument_code = args
    try:
        gdate = jd.date.togregorian(jdate).isoformat().replace('-', '')
        url = f"https://cdn.tsetmc.com/api/Shareholder/{instrument_code}/{gdate}"
        data = pd.DataFrame(requests.get(url, timeout=10).json().get('shareShareholder'))
        return data
    except:
        return None


def get_ticker_historical_share_holders(ticker: str, _max_workers: int = 10) -> pd.DataFrame:
    instrument_code = _find_instrument_code(ticker)
    jdates = get_ticker_historical_data(ticker_instrument_code=instrument_code).index.tolist()
    args = [(jdate, instrument_code) for jdate in jdates]

    with ThreadPoolExecutor(max_workers=_max_workers) as executor: results = list(executor.map(_fetch_shareholders_for_date, args))

    ticker_historical_share_holders_list = [df for df in results if df is not None]

    if not ticker_historical_share_holders_list:
        return pd.DataFrame()

    ticker_historical_share_holders = pd.concat(ticker_historical_share_holders_list, ignore_index=True)

    ticker_historical_share_holders.drop(columns=['shareHolderID', 'cIsin', 'change', 'changeAmount'], inplace=True, errors='ignore')
    ticker_historical_share_holders.rename(columns={'shareHolderName': 'Name', 'dEven': 'GDate', 'numberOfShares': 'SharesNo',
                                                    'perOfShares': 'SharePercentage', 'shareHolderShareID': 'ShareHolderShareID'}, inplace=True)

    ticker_historical_share_holders['Name'] = ticker_historical_share_holders['Name'].apply(convert_ar_characters)

    ticker_historical_share_holders['GDate'] = pd.to_datetime(ticker_historical_share_holders['GDate'].astype(str)).dt.date
    ticker_historical_share_holders['JDate'] = ticker_historical_share_holders['GDate'].apply(lambda g: jd.date.fromgregorian(year=g.year, month=g.month, day=g.day))

    ticker_historical_share_holders.drop('GDate', axis=1, inplace=True)

    return ticker_historical_share_holders


def _fetch_client_types_for_date(args):
    jdate, instrument_code = args
    try:
        gdate = jd.date.togregorian(jdate).isoformat().replace('-', '')
        url = f"https://cdn.tsetmc.com/api/ClientType/GetClientTypeHistory/{instrument_code}/{gdate}"
        response = requests.get(url, timeout=10).json()
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
        columns={'recDate': 'GDate', 'insCode': 'InstrumentCode', 'buy_I_Volume': 'InstitutionalBuyVolume',
                 'buy_N_Volume': 'RetailBuyVolume', 'buy_I_Value': 'InstitutionalBuyValue', 'buy_N_Value': 'RetailBuyValue',
                 'buy_N_Count': 'RetailBuyCount', 'sell_I_Volume': 'InstitutionalSellVolume',
                 'buy_I_Count': 'InstitutionalBuyCount', 'sell_N_Volume': 'RetailSellVolume',
                 'sell_I_Value': 'InstitutionalSellValue', 'sell_N_Value': 'RetailSellValue',
                 'sell_N_Count': 'RetailSellCount', 'sell_I_Count': 'InstitutionalSellCount'}, inplace=True)

    ticker_historical_trades_client_type['GDate'] = pd.to_datetime(ticker_historical_trades_client_type['GDate'].astype(str)).dt.date
    ticker_historical_trades_client_type['JDate'] = \
        ticker_historical_trades_client_type['GDate'].apply(lambda g: jd.date.fromgregorian(year=g.year, month=g.month, day=g.day))

    ticker_historical_trades_client_type.drop(['GDate', 'InstrumentCode'], axis=1, inplace=True)
    ticker_historical_trades_client_type.set_index('JDate', inplace=True)
    return ticker_historical_trades_client_type


def _fetch_shares_no_for_date(args):
    jdate, instrument_code = args
    try:
        gdate = jd.date.togregorian(jdate).isoformat().replace('-', '')
        url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentHistory/{instrument_code}/{gdate}"
        data = requests.get(url, timeout=10).json()
        return jdate, int(data['instrumentHistory']['zTitad'])
    except:
        return jdate, None


def get_ticker_historical_market_caps(ticker: str, _max_workers: int = 10) -> pd.DataFrame:
    ticker_instrument_code = _find_instrument_code(ticker)
    df = get_ticker_historical_data(ticker_instrument_code=ticker_instrument_code)[['ClosePrice']]
    date_args = [(jdate, ticker_instrument_code) for jdate in df.index]

    with ThreadPoolExecutor(max_workers=_max_workers) as executor:
        results = list(executor.map(_fetch_shares_no_for_date, date_args))

    shares_no_dict = dict(results)
    df['SharesNo'] = df.index.map(shares_no_dict.get)

    df['MarketCap'] = df['SharesNo'] * df['ClosePrice']
    return df


def _get_ticker_info_with_instrument_code(instrument_id: int):
    try:
        url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/{instrument_id}"
        data = requests.get(url, timeout=10).json()['instrumentInfo']
        return instrument_id, data.get('lVal18AFC', ''), data.get('lVal30', '')
    except:
        return instrument_id, None, None


def _update_ticker_info_parallel(df: pd.DataFrame, _max_workers: int = 10) -> pd.DataFrame:
    instrument_codes = df['InstrumentID'].tolist()

    with ThreadPoolExecutor(max_workers=_max_workers) as executor:
        results = list(executor.map(_get_ticker_info_with_instrument_code, instrument_codes))

    info_df = pd.DataFrame(results, columns=['InstrumentID', 'Ticker', 'Name']).set_index('InstrumentID')

    df = df.set_index('InstrumentID')
    df[['Ticker', 'Name']] = info_df
    return df.reset_index()


def _get_static_data() -> (pd.DataFrame, pd.DataFrame):
    url = "https://cdn.tsetmc.com/api/StaticData/GetStaticData"
    static_data_combined = requests.get(url).json()['staticData']
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


def get_ticker_historical_data(ticker: str=None, ticker_instrument_code: str=None) -> pd.DataFrame:
    if ticker_instrument_code is None:
        ticker_instrument_code  = _find_instrument_code(ticker)
    if ticker_instrument_code != '':
        url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/{ticker_instrument_code}/0"
        ticker_historical_data = pd.DataFrame(requests.get(url).json()['closingPriceDaily'])
        ticker_historical_data.drop(['iClose', 'id', 'hEven', 'insCode', 'yClose', 'last'], axis=1, inplace=True)
        ticker_historical_data.rename(columns={'priceChange': 'PriceChange', 'priceMin': 'MinPrice', 'priceMax': 'MaxPrice',
                                               'priceYesterday': 'YesterdayPrice', 'priceFirst': 'FirstPrice',
                                               'dEven': 'GDate', 'pClosing': 'ClosePrice',
                                               'pDrCotVal': 'LastPrice', 'zTotTran': 'TransactionNo', 'qTotTran5J': 'Volume',
                                               'qTotCap': 'Value'}, inplace=True)
        ticker_historical_data['GDate'] = pd.to_datetime(ticker_historical_data['GDate'], format='%Y%m%d').dt.date
        ticker_historical_data['JDate'] = ticker_historical_data['GDate'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
        ticker_historical_data.drop('GDate', axis=1, inplace=True)
        ticker_historical_data.set_index('JDate', inplace=True)
        return ticker_historical_data
    else:
        print('Could not find ticker instrument code to download the historical data.')
        return None


def _find_instrument_code(ticker: str) -> str:
    url = "https://old.tsetmc.com/tsev2/data/MarketWatchInit.aspx?h=0&r=0"
    response = requests.get(url, timeout=10)
    time.sleep(5)
    raw_text = response.text

    percent_index = raw_text.find('%')
    if percent_index == -1:
        raise ValueError("No '%' found in the response.")
    trimmed_text = raw_text[percent_index + 1:]
    if '@' not in trimmed_text:
        raise ValueError("The trimmed response does not contain '@'. Unexpected format.")

    _, main_data = trimmed_text.split('@', 1)
    records = [row for row in main_data.split(';') if row.strip()]
    parsed_data = [row.split(',') for row in records]

    market_watch = pd.DataFrame(parsed_data)
    market_watch = market_watch.iloc[:, [0, 2, 3]]
    market_watch.rename(columns={0: 'InstrumentID', 2: 'Ticker', 3: 'Name'}, inplace=True)

    unknown_instrument_codes = market_watch[market_watch['Ticker'].astype(str).str.fullmatch(r'\d+(\.\d+)?')].copy()
    known_instrument_codes = market_watch[~market_watch['Ticker'].astype(str).str.fullmatch(r'\d+(\.\d+)?')].copy()
    known_instrument_codes['Ticker'] = known_instrument_codes['Ticker'].apply(lambda ar_ticker: convert_ar_characters(ar_ticker))

    if ticker in known_instrument_codes['Ticker'].values:
        found_item = known_instrument_codes[known_instrument_codes['Ticker'] == ticker]
        return found_item['InstrumentID'].values[0]
    else:
        tree_map_instrument_codes = _get_instrument_codes_tree_map()
        if ticker in tree_map_instrument_codes['Ticker'].values:
            found_item = tree_map_instrument_codes[tree_map_instrument_codes['Ticker'] == ticker]
            return found_item['InstrumentID'].values[0]
        else:
            unknown_instrument_codes = _update_ticker_info_parallel(unknown_instrument_codes)
            unknown_instrument_codes['Ticker'] = unknown_instrument_codes['Ticker'].apply(lambda ar_ticker: convert_ar_characters(ar_ticker))
            # still_unknown_instrument_codes = unknown_instrument_codes[unknown_instrument_codes['Ticker'].astype(str).str.fullmatch(r'\d+(\.\d+)?')].copy()
            if ticker in unknown_instrument_codes['Ticker'].values:
                found_item = unknown_instrument_codes[unknown_instrument_codes['Ticker'] == ticker]
                return found_item['InstrumentID'].values[0]
    return ''


def get_ticker_intraday_trades(ticker: str) -> pd.DataFrame:
    ticker_instrument_code  = _find_instrument_code(ticker)
    url = f"https://cdn.tsetmc.com/api/Trade/GetTrade/{ticker_instrument_code}"
    ticker_intraday_trades = pd.DataFrame(requests.get(url).json()['trade'])
    ticker_intraday_trades.drop(['insCode', 'dEven', 'qTitNgJ', 'iSensVarP', 'pPhSeaCotJ', 'pPbSeaCotJ',
                                 'iAnuTran', 'xqVarPJDrPRf'], axis=1, inplace=True)
    ticker_intraday_trades.rename(columns={'nTran': 'TransitionsNo', 'hEven': 'Time', 'qTitTran': 'Volume', 'pTran':
        'Price', 'canceled': 'Canceled'}, inplace=True)
    ticker_intraday_trades['Time'] = pd.to_datetime(ticker_intraday_trades['Time'], format="%H%M%S").dt.time
    return ticker_intraday_trades


def _get_instrument_codes_tree_map() -> pd.DataFrame:
    sector = 0
    size = 20000
    based_on: str = 1

    url = ("https://cdn.tsetmc.com/api/ClosingPrice/GetMarketMap?"
           "market=AllAll-TseAll-OtcAll-TseDebt-TseEtf-TseDerivative-TseStock-OtcDebt-OtcEtf-OtcBase-OtcDerivative-OtcStock-&"
           f"size={size}&sector={sector}&typeSelected={based_on}&hEven=0")
    tree_map_data = pd.DataFrame(requests.get(url, timeout=10).json())
    time.sleep(5)
    instrument_codes = tree_map_data.loc[:, ['insCode', 'lVal18AFC', 'lVal30']]
    instrument_codes.columns = ['InstrumentCode', 'Ticker', 'Name']
    instrument_codes['Ticker'] = instrument_codes['Ticker'].apply(lambda ticker_code: convert_ar_characters(ticker_code))
    return instrument_codes


def get_indexes_status() -> pd.DataFrame:
    tse_url = "https://cdn.tsetmc.com/api/Index/GetIndexB1LastAll/SelectedIndexes/1"
    tse_idnexes_status = requests.get(tse_url).json()['indexB1']

    ifb_url = "https://cdn.tsetmc.com/api/Index/GetIndexB1LastAll/SelectedIndexes/2"
    ifb_indexes_status = requests.get(ifb_url).json()['indexB1']

    indexes_status = tse_idnexes_status + ifb_indexes_status
    indexes_status = pd.DataFrame(indexes_status)
    indexes_status.rename(columns={'insCode': 'InstrumentCode', 'hEven': 'HourMinute', 'xDrNivJIdx004': 'Value',
                                 'xPhNivJIdx004': 'MinValue', 'xPbNivJIdx004': 'MaxValue', 'xVarIdxJRfV': 'PercentageChange',
                                 'indexChange': 'Change', 'lVal30': 'Index'}, inplace=True)
    indexes_status.drop(['dEven', 'c1', 'c2', 'c3', 'c4', 'last'], inplace=True, axis=1)
    indexes_status['Index'] = indexes_status['Index'].apply(lambda index: convert_ar_characters(index))
    indexes_status['Index'] = indexes_status['Index'].str.replace('شاخص قیمت(وزنی-ارزشی)', 'شاخص قیمت (وزنی-ارزشی)')
    indexes_status.set_index('Index', inplace=True, drop=True)
    return indexes_status


def get_index_historical_data(index: str) -> pd.DataFrame:
    indexes_status = get_indexes_status()
    index_instrument_code = indexes_status.loc[index, 'InstrumentCode']
    url = f"https://cdn.tsetmc.com/api/Index/GetIndexB2History/{index_instrument_code}"
    index_historical_data = pd.DataFrame(requests.get(url).json()['indexB2'])
    index_historical_data.rename(columns={'insCode': 'InstrumentCode', 'dEven': 'GDate', 'xNivInuClMresIbs': 'Value', 'xNivInuPbMresIbs': 'MinValue',
                                          'xNivInuPhMresIbs': 'MaxValue'}, inplace=True)
    index_historical_data['GDate'] = pd.to_datetime(index_historical_data['GDate'], format='%Y%m%d').dt.date
    index_historical_data['JDate'] = index_historical_data['GDate'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
    index_historical_data.drop(['InstrumentCode', 'GDate'], inplace=True, axis=1)
    index_historical_data.set_index('JDate', inplace=True, drop=True)
    return index_historical_data


def get_index_last_intraday_data(index: str) -> pd.DataFrame:
    indexes_status = get_indexes_status()
    index_instrument_code = indexes_status.loc[index, 'InstrumentCode']
    url = f"https://cdn.tsetmc.com/api/Index/GetIndexB1LastDay/{index_instrument_code}"
    index_intradyay_data = pd.DataFrame(requests.get(url).json()['indexB1'])
    index_intradyay_data.rename(columns={'insCode': 'InstrumentCode', 'dEven': 'GDate', 'xDrNivJIdx004': 'Value', 'xPhNivJIdx004': 'MinValue',
                                          'xPbNivJIdx004': 'MaxValue', 'hEven': 'Time', 'xVarIdxJRfV': 'PercentageChange'}, inplace=True)
    index_intradyay_data['GDate'] = pd.to_datetime(index_intradyay_data['GDate'], format='%Y%m%d').dt.date
    index_intradyay_data['JDate'] = index_intradyay_data['GDate'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
    index_intradyay_data['Time'] = pd.to_datetime(index_intradyay_data['Time'], format='%H%M%S').dt.time
    index_intradyay_data.drop(['InstrumentCode', 'GDate', 'last', 'indexChange', 'lVal30', 'c1', 'c2', 'c3', 'c4'], inplace=True, axis=1)
    index_intradyay_data = index_intradyay_data[['JDate', 'Time', 'Value', 'MinValue', 'MaxValue', 'PercentageChange']]
    return index_intradyay_data


def get_index_companies(index: str, thirty_days_history: bool=False) -> (pd.DataFrame, pd.DataFrame):
    indexes_status = get_indexes_status()
    index_instrument_code = indexes_status.loc[index, 'InstrumentCode']
    url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetIndexCompany/{index_instrument_code}"
    index_companies_data = requests.get(url).json()
    index_companies = pd.DataFrame(index_companies_data['indexCompany'])
    index_companies.rename(columns={'instrument': 'Instrument', 'priceChange': 'PriceChange', 'priceMin': 'MinPrice',
                                    'priceMax': 'MaxPrice', 'priceYesterday': 'YesterdayPrice', 'priceFirst': 'FirstPrice',
                                    'insCode': 'InstrumentCode', 'pClosing': 'ClosePrice', 'pDrCotVal': 'LastPrice',
                                    'zTotTran': 'TransactionsNo', 'qTotTran5J': 'Value', 'qTotCap': 'Value'}, inplace=True)
    index_companies['Ticker'] = index_companies['Instrument'].apply(lambda instrument: convert_ar_characters(instrument['lVal18AFC']))
    index_companies['Name'] = index_companies['Instrument'].apply(lambda instrument: convert_ar_characters(instrument['lVal30']))
    index_companies.drop(['instrumentState', 'lastHEven', 'finalLastDate', 'nvt', 'mop', 'pRedTran',
                          'thirtyDayClosingHistory', 'last', 'id', 'dEven', 'hEven', 'iClose', 'yClose', 'Instrument'],
                         inplace=True, axis=1)
    index_companies = index_companies[['Ticker', 'Name', 'InstrumentCode', 'YesterdayPrice', 'FirstPrice', 'MinPrice',
                                       'MaxPrice', 'ClosePrice', 'PriceChange', 'LastPrice', 'TransactionsNo', 'Value', 'Value']]
    index_companies.set_index('Ticker', inplace=True, drop=True)

    tickers_instrument_code = index_companies.loc[:, 'InstrumentCode'].to_frame('InstrumentCode').reset_index().set_index('InstrumentCode')

    if thirty_days_history:
        index_companies_past_30_days = pd.DataFrame(index_companies_data['relatedCompanyThirtyDayHistory'])
        index_companies_past_30_days = index_companies_past_30_days[['insCode', 'dEven', 'pClosing']]
        index_companies_past_30_days.rename(columns={'insCode': 'InstrumentCode', 'dEven': 'GDate', 'pClosing': 'ClosePrice'}, inplace=True)
        index_companies_past_30_days['Ticker'] = \
            index_companies_past_30_days['InstrumentCode'].apply(lambda instrument_code: tickers_instrument_code.loc[instrument_code, 'Ticker'])
        index_companies_past_30_days['GDate'] = pd.to_datetime(index_companies_past_30_days['GDate'], format='%Y%m%d').dt.date
        index_companies_past_30_days['JDate'] = index_companies_past_30_days['GDate'].apply(
            lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
        index_companies_past_30_days.drop(['InstrumentCode', 'GDate'], axis=1, inplace=True)
        index_companies_past_30_days = index_companies_past_30_days[['Ticker', 'JDate', 'ClosePrice']]
    else:
        index_companies_past_30_days = pd.DataFrame()
    return index_companies, index_companies_past_30_days
