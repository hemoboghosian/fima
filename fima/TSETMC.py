import jdatetime as jd
import pandas as pd
import requests
from persian import convert_ar_characters


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


def get_ticker_historical_data(ticker: str) -> pd.DataFrame:
    ticker_instrument_code = 778253364357513
    url = f"https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/{ticker_instrument_code}/0"
    ticker_historical_data = pd.DataFrame(requests.get(url).json()['closingPriceDaily'])
    return ticker_historical_data


def get_ticker_intraday_trades(ticker: str) -> pd.DataFrame:
    ticker_instrument_code = 778253364357513
    url = f"https://cdn.tsetmc.com/api/Trade/GetTrade/{ticker_instrument_code}"
    ticker_intraday_trades = pd.DataFrame(requests.get(url).json()['trade'])
    return ticker_intraday_trades


def get_tickers(market: str='All', instrument: str='All', sector: str='All', _based_on: str='Value') -> pd.DataFrame:
    # market = 'tse'
    # instrument = 'debt'
    # sector = 'All'
    market = market.lower()
    instrument = instrument.lower()
    sector = sector.lower()
    size = 20000

    based_on_dictionary = {'Value': 1, 'Volume': 2, 'MarketCap': 3}

    markets_dictionary = {'ifb': 'Otc', 'tse': 'Tse', 'all': 'All'}

    instruments_dictionary = {'stock': 'Stock', 'debt': 'Debt', 'etf': 'Etf', 'derivative': 'Derivative', 'base': 'Base'}

    _, sectors = _get_static_data()
    sectors_dictionary = sectors.loc[:, ['Code', 'IndustryGroup']].set_index('IndustryGroup')
    sectors_dictionary.loc['all', 'Code'] = 0
    sectors_dictionary['Code'] = sectors_dictionary['Code'].astype(int)

    if market == 'all':
        url = ("https://cdn.tsetmc.com/api/ClosingPrice/GetMarketMap?"
               "market=AllAll-TseAll-OtcAll-TseDebt-TseEtf-TseDerivative-TseStock-OtcDebt-OtcEtf-OtcBase-OtcDerivative-OtcStock-&"
               f"size={size}&sector={sectors_dictionary.loc[sector, 'Code']}&typeSelected={based_on_dictionary[_based_on]}&hEven=0")
    else:
        if instrument == 'all':
            url = ("https://cdn.tsetmc.com/api/ClosingPrice/GetMarketMap?"
                   f"market={markets_dictionary[market]}All-{markets_dictionary[market]}Stock-"
                   f"{markets_dictionary[market]}Debt-{markets_dictionary[market]}Etf-{markets_dictionary[market]}Derivative-&"
                   f"size={size}&sector={sectors_dictionary.loc[sector, 'Code']}&typeSelected={based_on_dictionary[_based_on]}&hEven=0")
        else:
            market_combination = f"{markets_dictionary[market]}{instruments_dictionary[instrument]}"
            url = ("https://cdn.tsetmc.com/api/ClosingPrice/GetMarketMap?"
                   f"market={market_combination}-&size={size}&sector={sectors_dictionary.loc[sector, 'Code']}&"
                   f"typeSelected={based_on_dictionary[_based_on]}&hEven=0")
    data = pd.DataFrame(requests.get(url, timeout=10).json())
    return data


def get_ticker_info(ticker: str) -> pd.DataFrame:
    ticker_instrument_code = 778253364357513
    url = f"https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/{ticker_instrument_code}"
    index_info = pd.DataFrame(requests.get(url).json()['instrumentInfo'])
    return index_info


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
                                    'zTotTran': 'Volume', 'qTotTran5J': 'Value', 'qTotCap': 'MarketCap'}, inplace=True)
    index_companies['Ticker'] = index_companies['Instrument'].apply(lambda instrument: convert_ar_characters(instrument['lVal18AFC']))
    index_companies['Name'] = index_companies['Instrument'].apply(lambda instrument: convert_ar_characters(instrument['lVal30']))
    index_companies.drop(['instrumentState', 'lastHEven', 'finalLastDate', 'nvt', 'mop', 'pRedTran',
                          'thirtyDayClosingHistory', 'last', 'id', 'dEven', 'hEven', 'iClose', 'yClose', 'Instrument'],
                         inplace=True, axis=1)
    index_companies = index_companies[['Ticker', 'Name', 'InstrumentCode', 'YesterdayPrice', 'FirstPrice', 'MinPrice',
                                       'MaxPrice', 'ClosePrice', 'PriceChange', 'LastPrice', 'Volume', 'Value', 'MarketCap']]
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

