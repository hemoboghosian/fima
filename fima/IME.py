import requests, json, time, threading
import pandas as pd
import jdatetime as jd
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


_IME_THREAD_LOCAL = threading.local()


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


def _date_key(date_value) -> int:
    return int(str(date_value).replace('-', '').replace('/', ''))


def _parse_ime_jdate(value):
    if pd.isna(value):
        return None
    value = str(value).strip().replace('/', '-')
    if not value:
        return None
    parts = value[:10].split('-')
    if len(parts) != 3:
        return None
    try:
        return jd.date(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        return None


def _make_ime_retry_session(pool_size: int = 10, max_retries: int = 1, backoff_factor: float = 0.4) -> requests.Session:
    session = requests.Session()
    retry_kwargs = dict(total=max_retries, connect=max_retries, read=max_retries, status=max_retries,
                        backoff_factor=backoff_factor, status_forcelist=(408, 429, 500, 502, 503, 504),
                        raise_on_status=False,)
    try:
        retry = Retry(allowed_methods=frozenset(['POST']), **retry_kwargs)
    except TypeError:  # older urllib3 compatibility
        retry = Retry(method_whitelist=frozenset(['POST']), **retry_kwargs)

    adapter = HTTPAdapter(max_retries=retry, pool_connections=pool_size, pool_maxsize=pool_size)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session


def _get_thread_ime_session(pool_size: int, max_retries: int) -> requests.Session:
    # requests.Session is not shared across threads. Each worker thread gets one session.
    session_key = f'ime_session_{pool_size}_{max_retries}'
    session = getattr(_IME_THREAD_LOCAL, session_key, None)
    if session is None:
        session = _make_ime_retry_session(pool_size=pool_size, max_retries=max_retries)
        setattr(_IME_THREAD_LOCAL, session_key, session)
    return session


def _clean_ime_physical_records(records) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()

    all_data = pd.DataFrame.from_records(records)
    if all_data.empty:
        return pd.DataFrame()

    ending_1_columns = [column for column in all_data.columns if str(column).endswith('1')]
    ime_physical_drop_columns = ['taghazavoroudi', 'xTalarReportPK', 'bArzehRadifTarSarresid', 'arzehPk', 'Category']
    all_data.drop(columns=ending_1_columns + ime_physical_drop_columns, errors='ignore', inplace=True)

    ime_physical_columns = ['GoodsName', 'Symbol', 'ProducerName', 'ContractType', 'MinPrice', 'ClosePrice', 'MaxPrice',
                            'SupplyVolume', 'SupplyBasePrice', 'SupplyMinPrice', 'Demand', 'DemandMaxPrice',
                            'ContractSize', 'TransactionValue', 'Date', 'DeliveryDate', 'Warehouse', 'Supplier',
                            'SettlementDate', 'Broker', 'SupplyType', 'BuyType', 'Currency', 'Unit', 'ExchangeHall',
                            'PacketType', 'Settlement']

    if len(all_data.columns) != len(ime_physical_columns):
        raise ValueError('IME physical trades schema changed. ' 
                         f'Expected {len(ime_physical_columns)} columns after cleanup, got {len(all_data.columns)}. '
                         f'Columns: {list(all_data.columns)}')

    all_data.columns = ime_physical_columns
    all_data['Date'] = all_data['Date'].map(_parse_ime_jdate)
    all_data['DeliveryDate'] = all_data['DeliveryDate'].map(_parse_ime_jdate)
    return all_data


def get_all_ime_physical_trades(start_date: str = None, end_date: str = None, _chunk_size: int = 30, _max_workers: int = 2,
                                _timeout=(20, 120), _max_retries: int = 3, _strict: bool = True, _verbose: bool = False,
                                _rescue_chunk_size: int = 7) -> pd.DataFrame:
    """
    Safer IME physical trades downloader.

    Main idea:
    - first downloads normal chunks;
    - if some chunks fail, retries only failed chunks sequentially in smaller chunks;
    - if _strict=True, it raises only if rescue also fails.
    """

    if start_date is None or (_date_key(start_date) < 13850101):
        start_date = '1385-01-01'
    else:
        start_date = str(start_date).replace('/', '-')

    if end_date is None:
        end_date = str(jd.date.today())
    else:
        end_date = str(end_date).replace('/', '-')

    today = str(jd.date.today())
    if _date_key(end_date) > _date_key(today):
        end_date = today

    if _date_key(start_date) > _date_key(end_date):
        return pd.DataFrame()

    url = 'https://www.ime.co.ir/subsystems/ime/services/home/imedata.asmx/GetAmareMoamelatList'

    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/plain, */*; q=0.01',
               'Content-Type': 'application/json; charset=utf-8', 'X-Requested-With': 'XMLHttpRequest',
               'Origin': 'https://www.ime.co.ir', 'Referer': 'https://www.ime.co.ir/offer-stat.html',
               'Connection': 'keep-alive'}

    chunks = _chunk_jalali_dates(start_date, end_date, _chunk_size)
    if not chunks:
        return pd.DataFrame()

    def fetch_one_chunk(index: int, from_date: str, to_date: str):
        payload = {'Language': 8, 'fari': False, 'GregorianFromDate': from_date, 'GregorianToDate': to_date,
                   'MainCat': 0, 'Cat': 0, 'SubCat': 0, 'Producer': 0}

        session = _get_thread_ime_session(pool_size=max(2, _max_workers), max_retries=_max_retries)

        try:
            response = session.post(url, headers=headers, json=payload, timeout=_timeout)
            response.raise_for_status()

            text = response.text.strip()
            if not text.startswith('{'):
                return index, [], f'Non-JSON response for {from_date} to {to_date}', from_date, to_date

            raw_json = response.json().get('d', '[]')
            records = json.loads(raw_json) if isinstance(raw_json, str) else raw_json

            if not isinstance(records, list):
                return index, [], f'Unexpected JSON shape for {from_date} to {to_date}', from_date, to_date

            return index, records, None, from_date, to_date

        except Exception as exc:
            return index, [], f'{from_date} to {to_date}: {exc}', from_date, to_date

    max_workers = max(1, min(int(_max_workers), len(chunks)))

    results_by_index = {}
    failed_chunks = []

    if max_workers == 1:
        for index, (from_date, to_date) in enumerate(chunks):
            chunk_index, records, error, f, t = fetch_one_chunk(index, from_date, to_date)
            results_by_index[chunk_index] = records

            if error:
                failed_chunks.append((chunk_index, f, t, error))
                if _verbose:
                    print(f'❌ {error}')
            elif _verbose:
                print(f'✅ {f} to {t}: {len(records)} rows')

            time.sleep(0.3)

    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_one_chunk, index, from_date, to_date): (index, from_date, to_date)
                       for index, (from_date, to_date) in enumerate(chunks)}

            for future in as_completed(futures):
                chunk_index, records, error, f, t = future.result()
                results_by_index[chunk_index] = records

                if error:
                    failed_chunks.append((chunk_index, f, t, error))
                    if _verbose:
                        print(f'❌ {error}')
                elif _verbose:
                    print(f'✅ {f} to {t}: {len(records)} rows')

    final_failures = []

    if failed_chunks:
        if _verbose:
            print(f'⚠️ Retrying {len(failed_chunks)} failed chunks with smaller {_rescue_chunk_size}-day chunks...')

        for original_index, failed_from, failed_to, first_error in failed_chunks:
            rescued_records = []
            rescue_subchunks = _chunk_jalali_dates(failed_from, failed_to, _rescue_chunk_size)

            for sub_index, (sub_from, sub_to) in enumerate(rescue_subchunks):
                _, records, error, _, _ = fetch_one_chunk(original_index, sub_from, sub_to)

                if error:
                    final_failures.append(error)
                    if _verbose:
                        print(f'❌ Rescue failed: {error}')
                else:
                    rescued_records.extend(records)
                    if _verbose:
                        print(f'✅ Rescue succeeded: {sub_from} to {sub_to}: {len(records)} rows')

                time.sleep(0.7)

            results_by_index[original_index] = rescued_records

    if final_failures and _strict:
        raise RuntimeError('Some IME physical-trade chunks failed even after rescue retry:\n'
                           + '\n'.join(final_failures[:30]))

    all_records = []
    for index in range(len(chunks)):
        all_records.extend(results_by_index.get(index, []))

    return _clean_ime_physical_records(all_records)


def get_all_ime_futures_trades(only_active: bool = False, start_date: str = None, end_date: str = None,
                               _chunk_size: int = 100, _offset: int = 0, _timeout=(10, 45)) -> pd.DataFrame:

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
            response = requests.get(url, headers=headers, params=params, timeout=_timeout)
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
                               end_date: str = None, _chunk_size: int = 100, _offset: int = 0,
                              _timeout=(10, 45)) -> pd.DataFrame:

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
            response = requests.get(url, headers=headers, params=params, timeout=_timeout)
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


def get_all_physical_producer_products(start_date: str = None, end_date: str = None,
                                       all_ime_physical_trades: pd.DataFrame = None) -> pd.DataFrame:
    if all_ime_physical_trades is None:
        all_ime_physical_trades = get_all_ime_physical_trades(start_date=start_date, end_date=end_date)
    if all_ime_physical_trades is None or all_ime_physical_trades.empty:
        return pd.DataFrame(columns=['Producer', 'Products'])
    producer_products = (all_ime_physical_trades.groupby('ProducerName')['GoodsName']
                         .agg(lambda x: list(sorted(set(x.dropna())))).reset_index()
                         .rename(columns={'GoodsName': 'Products', 'ProducerName': 'Producer'}))
    return producer_products


def get_producer_physical_trades(producer: str, start_date: str = None, end_date: str = None,
                                 all_ime_physical_trades: pd.DataFrame = None,) -> pd.DataFrame:
    if all_ime_physical_trades is None:
        all_ime_physical_trades = get_all_ime_physical_trades(start_date=start_date, end_date=end_date)
    if all_ime_physical_trades is None or all_ime_physical_trades.empty:
        return pd.DataFrame()
    if producer not in all_ime_physical_trades['ProducerName'].unique():
        print(f'Producer name you entered ({producer}) is not in the list of producers.')
        return pd.DataFrame()
    producer_physical_trades = all_ime_physical_trades[all_ime_physical_trades['ProducerName'] == producer].copy()
    if start_date is not None:
        start_jd = jd.date(year=int(str(start_date)[:4]), month=int(str(start_date)[5:7]), day=int(str(start_date)[8:10]))
        producer_physical_trades = producer_physical_trades[producer_physical_trades['Date'] >= start_jd]
    if end_date is not None:
        end_jd = jd.date(year=int(str(end_date)[:4]), month=int(str(end_date)[5:7]), day=int(str(end_date)[8:10]))
        producer_physical_trades = producer_physical_trades[producer_physical_trades['Date'] <= end_jd]
    producer_physical_trades.reset_index(inplace=True, drop=True)
    return producer_physical_trades


def get_all_ime_export_trades(start_date: str = None, end_date: str = None, _chunk_size: int = 100, _offset: int = 40,
                               _timeout=(10, 45)) -> pd.DataFrame:

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
            response = requests.get(url, headers=headers, params=params, timeout=_timeout)
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


def get_all_ime_cd_trades(start_date: str = None, end_date: str = None, _chunk_size: int = 100, _offset: int = 30,
                               _timeout=(10, 45)) -> pd.DataFrame:

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
            response = requests.get(url, headers=headers, params=params, timeout=_timeout)
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


def get_all_ime_salaf_trades(start_date: str = None, end_date: str = None, _chunk_size: int = 100, _offset: int = 30,
                               _timeout=(10, 45)) -> pd.DataFrame:

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
            response = requests.get(url, headers=headers, params=params, timeout=_timeout)
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


def get_gold_and_silver_cd_trades(contract_type: str, start_date: str = None, end_date: str = None,
                                  _timeout=(10, 45)) -> pd.DataFrame:

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

        response = requests.post(url, json=payload, headers=headers, timeout=_timeout)
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


Test = get_all_physical_producer_products()

