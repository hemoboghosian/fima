import requests
import json
import pandas as pd
import jdatetime as jd


def get_all_ime_physical_trades(start_date: str = None, end_date: str = None, _chunk_size: int = 180) -> pd.DataFrame:

    if start_date is None:
        start_date = '1380-01-01'
    if end_date is None:
        end_date = str(jd.date.today())

    main_category = 0
    category = 0
    sub_category = 0
    producer = 0


    url = "https://www.ime.co.ir/subsystems/ime/services/home/imedata.asmx/GetAmareMoamelatList"

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/plain, */*; q=0.01",
               "Content-Type": "application/json; charset=utf-8", "X-Requested-With": "XMLHttpRequest",
               "Origin": "https://www.ime.co.ir", "Referer": "https://www.ime.co.ir/offer-stat.html",
               "Connection": "keep-alive"}

    temp_start_date = jd.date(year=int(start_date[:4]), month=int(start_date[5:7]), day=int(start_date[8:]))
    end_date = temp_end_date = jd.date(year=int(end_date[:4]), month=int(end_date[5:7]), day=int(end_date[8:]))
    chunked_dates = []
    while temp_end_date <= end_date:
        temp_end_date = temp_start_date + jd.timedelta(days=_chunk_size)
        chunked_dates.append([str(temp_start_date).replace('-', '/'), str(temp_end_date).replace('-', '/')])
        temp_start_date = temp_end_date + jd.timedelta(days=1)
        temp_end_date = temp_end_date + jd.timedelta(days=_chunk_size)
    chunked_dates.append([str(temp_start_date + jd.timedelta(days=1)).replace('-', '/'), str(end_date).replace('-', '/')])

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

    if only_active:
        start_date = str(jd.date.today() - jd.timedelta(days=10))
        end_date = str(jd.date.today())
    else:
        if start_date is None:
            start_date = '1385-01-01'
        if end_date is None:
            end_date = str(jd.date.today())

    temp_start_date = jd.date(year=int(start_date[:4]), month=int(start_date[5:7]), day=int(start_date[8:]))
    end_date = temp_end_date = jd.date(year=int(end_date[:4]), month=int(end_date[5:7]), day=int(end_date[8:]))
    chunked_dates = []
    while temp_end_date <= end_date:
        temp_end_date = temp_start_date + jd.timedelta(days=_chunk_size)
        chunked_dates.append([str(temp_start_date).replace('-', '/'), str(temp_end_date).replace('-', '/')])
        temp_start_date = temp_end_date + jd.timedelta(days=1)
        temp_end_date = temp_end_date + jd.timedelta(days=_chunk_size)
    chunked_dates.append([str(temp_start_date + jd.timedelta(days=1)).replace('-', '/'), str(end_date).replace('-', '/')])

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

        return all_data
    return pd.DataFrame(all_rows)



