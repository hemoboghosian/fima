import requests
import json
import pandas as pd
import jdatetime as jd
import time


def _chunk_jalali_dates(start_s: str, end_s: str, chunk_size_days: int):
    start = jd.date(int(start_s[:4]), int(start_s[5:7]), int(start_s[8:]))
    end   = jd.date(int(end_s[:4]),   int(end_s[5:7]),   int(end_s[8:]))

    chunks = []
    cur = start
    delta = jd.timedelta(days=chunk_size_days)
    while cur <= end:
        nxt = cur + delta
        chunk_end = end if nxt > end else nxt
        chunks.append((cur.strftime('%Y/%m/%d'), chunk_end.strftime('%Y/%m/%d')))
        cur = chunk_end + jd.timedelta(days=1)
    return chunks


def get_all_ime_physical_trades(start_date: str = None, end_date: str = None, _chunk_size: int = 180) -> pd.DataFrame:

    if start_date is None or (int(start_date.replace('-', '')) < 13850101):
        start_date = '1385-01-01'
    if end_date is None:
        end_date = str(jd.date.today())

    if int(start_date.replace('-', '')) > int(end_date.replace('-', '')):
        return None

    main_category = 0
    category = 0
    sub_category = 0
    producer = 0


    url = "https://www.ime.co.ir/subsystems/ime/services/home/imedata.asmx/GetAmareMoamelatList"

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/plain, */*; q=0.01",
               "Content-Type": "application/json; charset=utf-8", "X-Requested-With": "XMLHttpRequest",
               "Origin": "https://www.ime.co.ir", "Referer": "https://www.ime.co.ir/offer-stat.html",
               "Connection": "keep-alive"}

    chunked_dates = _chunk_jalali_dates(start_date, end_date, _chunk_size)

    all_data = []
    for from_date, to_date in chunked_dates:
        payload = {"Language": 8, "fari": False, "GregorianFromDate": from_date, "GregorianToDate": to_date,
                   "MainCat": main_category, "Cat": category, "SubCat": sub_category, "Producer": producer}

        try:
            res = requests.post(url, headers=headers, json=payload)
        except requests.exceptions.RequestException as e:
            continue

        if not res.ok or not res.text.strip().startswith("{"):
            continue

        try:
            raw_json = res.json()["d"]
            records = json.loads(raw_json)
        except Exception as e:
            continue

        if not records:
            continue

        all_data.extend(records)

    if all_data:
        all_data = pd.DataFrame(all_data)

        all_data.drop([column for column in all_data.columns if column.endswith('1')], inplace=True, axis=1)
        all_data.drop(['taghazavoroudi', 'xTalarReportPK', 'bArzehRadifTarSarresid', 'arzehPk', 'Category'], axis=1,
                      inplace=True)

        all_data.columns = ['GoodsName', 'Symbol', 'ProducerName', 'ContractType', 'MinPrice', 'ClosePrice', 'MaxPrice',
                            'SupplyVolume', 'SupplyBasePrice', 'SupplyMinPrice', 'Demand', 'DemandMaxPrice',
                            'ContractSize', 'TransactionValue', 'Date', 'DeliveryDate', 'Warehouse', 'Supplier',
                            'SettlementDate', 'Broker', 'SupplyType', 'BuyType', 'Currency', 'Unit', 'ExchangeHall',
                            'PacketType', 'Settlement']

        all_data['Date'] = all_data['Date'].apply(
            lambda str_j_date: jd.date(year=int(str_j_date[:4]), month=int(str_j_date[5:7]), day=int(str_j_date[8:]))
            if pd.notna(str_j_date) else None)
        all_data['DeliveryDate'] = all_data['DeliveryDate'].apply(
            lambda str_j_date: jd.date(year=int(str_j_date[:4]), month=int(str_j_date[5:7]), day=int(str_j_date[8:]))
            if pd.notna(str_j_date) else None)
    else:
        all_data = pd.DataFrame()
    return all_data


def get_all_ime_futures_trades(only_active: bool = False, start_date: str = None, end_date: str = None,
                               _chunk_size: int = 100, _offset: int = 0) -> pd.DataFrame:

    if only_active and start_date == str(jd.date.today()):
        start_date = str(jd.date.today() - jd.timedelta(days=1))

    if start_date is None or (int(start_date.replace('-', '')) < 13870101):
        start_date = '1387-01-01'
    if end_date is None:
        end_date = str(jd.date.today())

    if int(start_date.replace('-', '')) > int(end_date.replace('-', '')):
        return None

    chunked_dates = _chunk_jalali_dates(start_date, end_date, _chunk_size)

    url = "https://www.ime.co.ir/subsystems/ime/futurereports/FutureAmareMoamelatHnadler.ashx"
    contract_filter = -1 if only_active else 0

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/javascript, */*; q=0.01",
               "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.ime.co.ir/fut-report.html"}

    all_rows = []
    for f, t in chunked_dates:
        params = {"f": f, "t": t, "c": contract_filter, "lang": 8, "order": "asc"}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            rows = data.get("rows", [])
            if rows:
                all_rows.extend(rows)
        except Exception as e:
            print(f"❌ Failed for chunk {f} to {t}: {e}")
            continue
    if all_rows:
        all_data = pd.DataFrame(all_rows)
        all_data.rename({'DT': 'Date', 'Vol_Haghighi_Buy': 'RetailBuyVolume', 'Val_Haghighi_Buy': 'RetailBuyValue',
                         'Vol_Haghighi_Sell': 'RetailSellVolume', 'Val_Haghighi_Sell': 'RetailSellValue',
                         'Vol_Hoghooghi_Buy': 'InstitutionalBuyVolume', 'Val_Hoghooghi_Buy': 'InstitutionalBuyValue',
                         'Vol_Hoghooghi_Sell': 'InstitutionalSellVolume', 'Val_Hoghooghi_Sell': 'InstitutionalSellValue',
                         'C_Buy': 'CBuy', 'C_Sell': 'CSell'},
                        inplace=True, axis=1)

        all_data['Date'] = all_data['Date'].apply(
            lambda str_j_date: jd.date(year=int(str_j_date[:4]), month=int(str_j_date[5:7]), day=int(str_j_date[8:]))
            if pd.notna(str_j_date) else None)
        all_data['DeliveryDate'] = all_data['DeliveryDate'].apply(
            lambda str_j_date: jd.date(year=int(str_j_date[:4]), month=int(str_j_date[5:7]), day=int(str_j_date[8:]))
            if pd.notna(str_j_date) else None)
        all_data.sort_values(by='Date', inplace=True, ignore_index=True)
        return all_data
    return pd.DataFrame(all_rows)


def get_all_ime_option_trades(option_type: str = 'All', only_active: bool = False, start_date: str = None,
                               end_date: str = None, _chunk_size: int = 100, _offset: int = 0) -> pd.DataFrame:

    if only_active and start_date == str(jd.date.today()):
        start_date = str(jd.date.today() - jd.timedelta(days=1))

    if start_date is None or (int(start_date.replace('-', '')) < 13950101):
        start_date = '1395-01-01'
    if end_date is None:
        end_date = str(jd.date.today() - jd.timedelta(days=1))

    if int(start_date.replace('-', '')) > int(end_date.replace('-', '')):
        return None

    chunked_dates = _chunk_jalali_dates(start_date, end_date, _chunk_size)

    url = "https://www.ime.co.ir/subsystems/ime/option/optionboarddata.ashx"
    contract_filter = -1 if only_active else 0

    if option_type == 'Call':
        option_type_filter = 1
    elif option_type == 'Put':
        option_type_filter = 2
    else:
        option_type_filter = 0

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/javascript, */*; q=0.01",
               "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.ime.co.ir/fut-report.html"}

    all_rows = []
    for f, t in chunked_dates:
        params = {"f": f, "t": t, "c": contract_filter, "ot": option_type_filter, "lang": 8, "order": "asc"}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            rows = data.get("rows", [])
            if rows:
                all_rows.extend(rows)
        except Exception as e:
            print(f"❌ Failed for chunk {f} to {t}: {e}")
            continue
    if all_rows:
        all_data = pd.DataFrame(all_rows)
        all_data.rename({'DT': 'Date', 'Vol_Haghighi_Buy': 'RetailBuyVolume', 'Val_Haghighi_Buy': 'RetailBuyValue',
                         'Vol_Haghighi_Sell': 'RetailSellVolume', 'Val_Haghighi_Sell': 'RetailSellValue',
                         'Vol_Hoghooghi_Buy': 'InstitutionalBuyVolume', 'Val_Hoghooghi_Buy': 'InstitutionalBuyValue',
                         'Vol_Hoghooghi_Sell': 'InstitutionalSellVolume', 'Val_Hoghooghi_Sell': 'InstitutionalSellValue',
                         'C_Buy': 'CBuy', 'C_Sell': 'CSell', 'id': 'ID', 'DT_en': 'GDate'},
                        inplace=True, axis=1)

        all_data['Date'] = all_data['Date'].apply(
            lambda str_j_date: jd.date(year=int(str_j_date[:4]), month=int(str_j_date[5:7]), day=int(str_j_date[8:]))
            if pd.notna(str_j_date) else None)
        all_data['DeliveryDate'] = all_data['DeliveryDate'].apply(
            lambda str_j_date: jd.date(year=int(str_j_date[:4]), month=int(str_j_date[5:7]), day=int(str_j_date[8:]))
            if pd.notna(str_j_date) else None)
        all_data['GDate'] = pd.to_datetime(all_data['GDate'])
        all_data['GDate'] = all_data['GDate'].dt.date
        all_data['CreateDateTime'] = pd.to_datetime(all_data['CreateDateTime'], format='mixed')
        all_data['CreateDateTime'] = all_data['CreateDateTime'].dt.date
        all_data.sort_values(by='Date', inplace=True, ignore_index=True)
        return all_data
    return pd.DataFrame(all_rows)


def get_all_physical_producer_products() -> pd.DataFrame:
    all_ime_physical_trades = get_all_ime_physical_trades()
    producer_products = (all_ime_physical_trades.groupby('ProducerName')
                         ['GoodsName'].agg(lambda x: list(sorted(set(x)))).reset_index()
                         .rename(columns={'GoodsName': 'Products', 'ProducerName': 'Producer'}))
    return producer_products


def get_producer_physical_trades(producer: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    if int(start_date.replace('-', '')) > int(end_date.replace('-', '')):
        return None
    all_ime_physical_trades = get_all_ime_physical_trades()
    if producer in all_ime_physical_trades['ProducerName'].unique():
        producer_physical_trades = all_ime_physical_trades[all_ime_physical_trades['ProducerName'] == producer].copy()
        if start_date is not None:
            start_date = jd.date(year=int(start_date[:4]), month=int(start_date[5:7]), day=int(start_date[8:]))
            producer_physical_trades = producer_physical_trades[producer_physical_trades['Date'] >= start_date]
        if end_date is not None:
            end_date = jd.date(year=int(end_date[:4]), month=int(end_date[5:7]), day=int(end_date[8:]))
            producer_physical_trades = producer_physical_trades[producer_physical_trades['Date'] <= end_date]
        producer_physical_trades.reset_index(inplace=True, drop=True)
        return producer_physical_trades
    else:
        print(f'Producer name you entered ({producer}) is not in the list of producers.')
        return pd.DataFrame()


def get_all_ime_export_trades(start_date: str = None, end_date: str = None, _chunk_size: int = 100, _offset: int = 40) -> pd.DataFrame:

    if start_date is None or (int(start_date.replace('-', '')) < 13871201):
        start_date = '1387-12-01'
    if end_date is None:
        end_date = str(jd.date.today())

    if int(start_date.replace('-', '')) > int(end_date.replace('-', '')):
        return None

    chunked_dates = _chunk_jalali_dates(start_date, end_date, _chunk_size)

    url = "https://www.ime.co.ir/subsystems/ime/fiziki/export.ashx"

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/javascript, */*; q=0.01",
               "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.ime.co.ir/export-stat.html"}

    all_rows = []
    for f, t in chunked_dates:
        params = {"f": f, "t": t, "m": 0, "c": 0, "s": 0, "p": 0, "lang": 8, "order": "asc"}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            rows = data.get("rows", [])
            if rows:
                all_rows.extend(rows)
        except Exception as e:
            print(f"❌ Failed for chunk {f} to {t}: {e}")
            continue
    if all_rows:
        all_data = pd.DataFrame(all_rows)
        all_data.drop(['TaghazaVoroudi', 'bArzehRadifTarSarresid', 'xKala_xGrouhAsliKalaPK', 'xKala_xGrouhKalaPK',
                       'xKala_xZirGrouhKalaPK', 'xNamad_xTolidKonandehPK', 'xRingPK', 'arzehPk'], axis=1, inplace=True)
        all_data.rename({'cBrokerSpcName': 'BrokerName', 'arze': 'Supply', 'arzeMinPrice': 'SupplyMinPrice',
                         'taghaza': 'Demand', 'taghazaMaxPrice': 'DemandMaxPrice', 'date': 'Date',
                         'typeName': 'MainGroupName', 'Talar': 'ExchangeHall', 'ArzeBasePrice': 'SupplyBasePrice',
                         'ArzehKonandeh': 'Supplier', 'xRingName': 'RingName', 'ModeDescription': 'SupplyType',
                         'MethodDescription': 'BuyType', 'NerkhArz': 'FXRate'}, inplace=True, axis=1)

        all_data['Date'] = all_data['Date'].apply(
            lambda str_j_date: jd.date(year=int(str_j_date[:4]), month=int(str_j_date[5:7]), day=int(str_j_date[8:]))
            if pd.notna(str_j_date) else None)
        all_data['DeliveryDate'] = all_data['DeliveryDate'].apply(
            lambda str_j_date: jd.date(year=int(str_j_date[:4]), month=int(str_j_date[5:7]), day=int(str_j_date[8:]))
            if pd.notna(str_j_date) else None)

        all_data['GoodsName'] = all_data['GoodsName'].apply(lambda goods_name: goods_name.replace(' - صادراتی', ''))

        all_data.sort_values(by='Date', inplace=True, ignore_index=True)

        return all_data
    return pd.DataFrame(all_rows)


def get_all_ime_cd_trades(start_date: str = None, end_date: str = None, _chunk_size: int = 100, _offset: int = 30) -> pd.DataFrame:

    if start_date is None or (int(start_date.replace('-', '')) < 13940301):
        start_date = '1394-03-01'
    if end_date is None:
        end_date = str(jd.date.today())

    if int(start_date.replace('-', '')) > int(end_date.replace('-', '')):
        return None

    chunked_dates = _chunk_jalali_dates(start_date, end_date, _chunk_size)

    url = "https://www.ime.co.ir/subsystems/ime/bazaremali/bazaremalidata.ashx"

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/javascript, */*; q=0.01",
               "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.ime.co.ir/standard-transactions.html"}

    all_rows = []
    for f, t in chunked_dates:
        params = {"f": f, "t": t, "c": 1, "ot": 0, "lang": 8, "order": "asc"}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            rows = data.get("rows", [])
            if rows:
                all_rows.extend(rows)
        except Exception as e:
            print(f"❌ Failed for chunk {f} to {t}: {e}")
            continue
    if all_rows:
        all_data = pd.DataFrame(all_rows)
        all_data.rename({'id': 'ID', 'Namad': 'Code', 'LVal18AFC': 'Symbol',
                         'DT': 'Date', 'NamadDescription': 'Description', 'PClosing': 'ClosePrice',
                         'PDrCotVal': 'LastPrice', 'ZTotTran': 'TotalTransitions', 'QTotTran5J': 'Volume',
                         'QTotCap': 'Value', 'PriceMin': 'MinPrice', 'PriceMax': 'MaxPrice',
                         'PriceYesterday': 'YesterdayPrice', 'LastTradeChangePrice': 'LastPriceChange',
                         'LastTradeChangePricePercent': 'LastPricePercentageChange',
                         'LastPriceChangePrice': 'ClosePriceChangePrice',
                         'LastPriceChangePricePercent': 'ClosePricePercentageChange', 'DT_En': 'GDate'}, inplace=True, axis=1)

        all_data['Date'] = all_data['Date'].apply(
            lambda str_j_date: jd.date(year=int(str_j_date[:4]), month=int(str_j_date[5:7]), day=int(str_j_date[8:]))
            if pd.notna(str_j_date) else None)
        all_data['GDate'] = pd.to_datetime(all_data['GDate'])
        all_data['GDate'] = all_data['GDate'].dt.date
        all_data.sort_values(by='Date', inplace=True, ignore_index=True)
        return all_data
    return pd.DataFrame(all_rows)


def get_all_export_producer_products() -> pd.DataFrame:
    all_ime_export_trades = get_all_ime_export_trades()
    producer_products = (all_ime_export_trades.groupby('ProducerName')
                         ['GoodsName'].agg(lambda x: list(sorted(set(x)))).reset_index()
                         .rename(columns={'GoodsName': 'Products', 'ProducerName': 'Producer'}))
    return producer_products


def get_producer_export_trades(producer: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    if int(start_date.replace('-', '')) > int(end_date.replace('-', '')):
        return None
    all_ime_export_trades = get_all_ime_export_trades()
    if producer in all_ime_export_trades['ProducerName'].unique():
        producer_export_trades = all_ime_export_trades[all_ime_export_trades['ProducerName'] == producer].copy()
        if start_date is not None:
            start_date = jd.date(year=int(start_date[:4]), month=int(start_date[5:7]), day=int(start_date[8:]))
            producer_export_trades = producer_export_trades[producer_export_trades['Date'] >= start_date]
        if end_date is not None:
            end_date = jd.date(year=int(end_date[:4]), month=int(end_date[5:7]), day=int(end_date[8:]))
            producer_export_trades = producer_export_trades[producer_export_trades['Date'] <= end_date]
        producer_export_trades.reset_index(inplace=True, drop=True)
        return producer_export_trades
    else:
        print(f'Producer name you entered ({producer}) is not in the list of producers.')
        return pd.DataFrame()


def get_all_ime_salaf_trades(start_date: str = None, end_date: str = None, _chunk_size: int = 100, _offset: int = 30) -> pd.DataFrame:

    if start_date is None or (int(start_date.replace('-', '')) < 13930501):
        start_date = '1393-05-01'
    if end_date is None:
        end_date = str(jd.date.today())

    if int(start_date.replace('-', '')) > int(end_date.replace('-', '')):
        return None

    chunked_dates = _chunk_jalali_dates(start_date, end_date, _chunk_size)

    url = "https://www.ime.co.ir/subsystems/ime/bazaremali/bazaremalidata.ashx"

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/javascript, */*; q=0.01",
               "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.ime.co.ir/standard-transactions.html"}

    all_rows = []
    for f, t in chunked_dates:
        params = {"f": f, "t": t, "c": 0, "ot": 0, "lang": 8, "order": "asc"}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            rows = data.get("rows", [])
            if rows:
                all_rows.extend(rows)
        except Exception as e:
            print(f"❌ Failed for chunk {f} to {t}: {e}")
            continue
    if all_rows:
        all_data = pd.DataFrame(all_rows)
        all_data.rename({'id': 'ID', 'Namad': 'Code', 'LVal18AFC': 'Symbol',
                         'DT': 'Date', 'NamadDescription': 'Description', 'PClosing': 'ClosePrice',
                         'PDrCotVal': 'LastPrice', 'ZTotTran': 'TotalTransitions', 'QTotTran5J': 'Volume',
                         'QTotCap': 'Value', 'PriceMin': 'MinPrice', 'PriceMax': 'MaxPrice',
                         'PriceYesterday': 'YesterdayPrice', 'LastTradeChangePrice': 'LastPriceChange',
                         'LastTradeChangePricePercent': 'LastPricePercentageChange',
                         'LastPriceChangePrice': 'ClosePriceChangePrice',
                         'LastPriceChangePricePercent': 'ClosePricePercentageChange', 'DT_En': 'GDate'}, inplace=True, axis=1)

        all_data['Date'] = all_data['Date'].apply(
            lambda str_j_date: jd.date(year=int(str_j_date[:4]), month=int(str_j_date[5:7]), day=int(str_j_date[8:]))
            if pd.notna(str_j_date) else None)
        all_data['GDate'] = pd.to_datetime(all_data['GDate'])
        all_data['GDate'] = all_data['GDate'].dt.date
        all_data.sort_values(by='Date', inplace=True, ignore_index=True)
        return all_data
    return pd.DataFrame(all_rows)


def get_gold_and_silver_cd_trades(contract_type: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:

    if start_date is None or (int(start_date.replace('-', '')) < 14011201):
        start_date = '1401-12-01'
    if end_date is None:
        end_date = str(jd.date.today())

    if int(start_date.replace('-', '')) > int(end_date.replace('-', '')):
        return None

    market_id = 22
    page_size = 100
    contract_codes = {'gold_coin_cd': 'CD1GOC0001',  # گواهی سپرده پیوسته تمام سکه بهار آزادی طرح جدید
                      'gold_bar_cd': 'CD1GOB0001',   # گواهی سپرده پیوسته شمش طلای +995
                      'silver_bar_cd': 'CD1SIB0001'  # گواهی سپرده پیوسته شمش نقره 999.9
                      }
    contract_code = contract_codes[contract_type]

    from_date = str(jd.date.togregorian(jd.date(int(start_date[:4]), int(start_date[5:7]), int(start_date[8:]))))
    to_date = str(jd.date.togregorian(jd.date(int(end_date[:4]), int(end_date[5:7]), int(end_date[8:]))))

    if 'gold' in contract_type:
        url = "https://dataapi.ime.co.ir/api/CDC/CDCTrades"
        headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json; charset=utf-8",
                   "Origin": "https://gold.ime.co.ir", "Referer": "https://gold.ime.co.ir/"}
    elif 'silver' in contract_type:
        url = "https://dataapi.ime.co.ir/api/CDC/CDCTrades"
        headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json; charset=utf-8",
                   "Origin": "https://silver.ime.co.ir", "Referer": "https://silver.ime.co.ir/"}
    else:
        return None

    all_data = []
    page = 1
    while True:
        payload = {"fromDate": from_date, "toDate": to_date, "pageNumber": page, "pageSize": page_size,
                   "marketId": market_id, "customFilter": contract_code}

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            raise Exception(f"Request failed on page {page}: {response.status_code}")

        data = response.json()
        all_data.extend(data['Data'])

        if not data.get("HasNextPage", False):
            break
        page += 1
        time.sleep(0.3)

    all_data = pd.DataFrame(all_data)

    all_data['PersianDate'] = all_data['PersianDate'].apply(
        lambda j_date_str: jd.date(year=int(j_date_str[:4]), month=int(j_date_str[5:7]), day=int(j_date_str[8:])))
    all_data.sort_values('PersianDate', inplace=True, ascending=False, ignore_index=True)
    all_data['DT'] = pd.to_datetime(all_data['DT']).dt.date
    all_data['DeliveryDate'] = pd.to_datetime(all_data['DeliveryDate']).dt.date
    all_data.drop('ROW', inplace=True, axis=1)
    all_data.rename({'ChangeOpenInterest': 'OpenInterestChange', 'C_Buy': 'CBuy', 'C_Sell': 'CSell',
               'Vol_Hoghooghi_Buy': 'InstitutionalBuyVolume', 'Vol_Hoghooghi_Sell': 'InstitutionalSellVolume',
               'Vol_Haghighi_Buy': 'RetailBuyVolume', 'Vol_Haghighi_Sell': 'RetailSellVolume',
               'Val_Hoghooghi_Buy': 'InstitutionalBuyValue', 'Val_Hoghooghi_Sell': 'InstitutionalSellValue',
               'Val_Haghighi_Buy': 'RetailBuyValue', 'Val_Haghighi_Sell': 'RetailSellValue', 'DT': 'GDate',
               'PersianDate': 'JDate', 'DeliveryDate': 'DeliveryGDate'}, inplace=True, axis=1)
    all_data['DeliveryJDate'] = all_data['DeliveryGDate'].apply(lambda delivery_g_date: jd.date.fromgregorian(date=delivery_g_date))
    all_data.sort_values(by='JDate', inplace=True, ignore_index=True)
    return all_data
