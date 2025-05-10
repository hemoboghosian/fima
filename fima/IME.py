import requests
import json
import pandas as pd
import jdatetime as jd


def get_all_ime_physical_trades(start_date: str = None, end_date: str = None) -> pd.DataFrame:

    if start_date is None and end_date is None:
        start_date = '1380-01-01'
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
        temp_end_date = temp_start_date + jd.timedelta(days=180)
        chunked_dates.append([str(temp_start_date).replace('-', '/'), str(temp_end_date).replace('-', '/')])
        temp_start_date = temp_end_date + jd.timedelta(days=1)
        temp_end_date = temp_end_date + jd.timedelta(days=180)
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

        all_data['Date'] = all_data['Date'].apply(lambda str_j_date: jd.date(year=int(str_j_date[:4]), month=int(str_j_date[5:7]), day=int(str_j_date[8:])))
        all_data['DeliveryDate'] = all_data['DeliveryDate'].apply(lambda str_j_date: jd.date(year=int(str_j_date[:4]), month=int(str_j_date[5:7]), day=int(str_j_date[8:])))
    else:
        all_data = pd.DataFrame()
    return all_data
