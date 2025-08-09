import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from io import StringIO
import jdatetime as jd
import time


def get_risk_free_rate() -> float:
    all_bonds_without_coupons = get_all_bonds_without_coupons(deprecated=False)
    all_t_notes = all_bonds_without_coupons[all_bonds_without_coupons['Ticker'].str.contains('سخاب|اخزا')].copy()
    today_date = jd.date.today()
    all_t_notes['DaysTillMaturity'] = (all_t_notes['MaturityDate'] - today_date).apply(lambda delta: delta.days)
    last_traded_t_notes = all_t_notes[all_t_notes['LastTradedDate'] == all_t_notes['LastTradedDate'].max()]
    rf = last_traded_t_notes['YTM'].mean()
    return rf


def get_all_bonds_without_coupons(deprecated: bool = True) -> pd.DataFrame:
    url = "https://ifb.ir/YTM.aspx"

    session = requests.Session()
    response = session.get(url)

    if response.status_code != 200:
        print(f"Failed to access page. Status code: {response.status_code}")
        return None

    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table", {"id": "ContentPlaceHolder1_grdytmforkhazaneh", "class": "KhazanehGrid"})

    if table is None:
        print("Table not found.")
        return None

    df_list = pd.read_html(StringIO(str(table)))
    bonds_without_coupons = df_list[0]

    if ~deprecated:
        bonds_without_coupons = bonds_without_coupons[bonds_without_coupons['YTM'] != 'سررسید شده'].copy()

    bonds_without_coupons.columns = ['Index', 'Ticker', 'LastTradedPrice', 'LastTradedDate', 'MaturityDate', 'YTM', 'SimpleReturn']

    bonds_without_coupons['LastTradedDate'] = \
        bonds_without_coupons['LastTradedDate'].apply(lambda str_date: jd.date(year=int(str_date[:4]),
                                                                               month=int(str_date[5:7]),
                                                                               day=int(str_date[8:])))

    bonds_without_coupons['MaturityDate'] = \
        bonds_without_coupons['MaturityDate'].apply(lambda str_date: jd.date(year=int(str_date[:4]),
                                                                               month=int(str_date[5:7]),
                                                                               day=int(str_date[8:])))

    bonds_without_coupons['YTM'] = \
        bonds_without_coupons['YTM'].apply(lambda str_ytm: float(str_ytm.replace('/', '.').replace('%', '')) / 100)
    bonds_without_coupons['SimpleReturn'] = \
        bonds_without_coupons['SimpleReturn'].apply(lambda str_ytm: float(str_ytm.replace('/', '.').replace('%', '')) / 100)

    bonds_without_coupons.drop('Index', inplace=True, axis=1)
    bonds_without_coupons.reset_index(inplace=True, drop=True)

    return bonds_without_coupons


def get_all_bonds_with_coupons(deprecated: bool = True) -> pd.DataFrame:
    url = "https://ifb.ir/YTM.aspx"

    session = requests.Session()
    response = session.get(url)

    if response.status_code != 200:
        print(f"Failed to access page. Status code: {response.status_code}")
        return None

    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table", {"id": "ContentPlaceHolder1_grdytm", "class": "mGrid"})

    if table is None:
        print("Table not found.")
        return None

    df_list = pd.read_html(StringIO(str(table)))
    bonds_with_coupons = df_list[0]

    if ~deprecated:
        bonds_with_coupons = bonds_with_coupons[bonds_with_coupons['YTM'] != 'سررسید شده'].copy()

    bonds_with_coupons.columns = ['Index', 'Ticker', 'LastTradedPrice', 'LastTradedDate', 'MaturityDate', 'YTM']

    bonds_with_coupons['LastTradedDate'] = bonds_with_coupons['LastTradedDate'].apply(
        lambda str_date: jd.date(year=int(str_date[:4]), month=int(str_date[5:7]), day=int(str_date[8:])) if pd.notna(str_date) else np.nan)

    bonds_with_coupons['MaturityDate'] = bonds_with_coupons['MaturityDate'].apply(
        lambda str_date: jd.date(year=int(str_date[:4]), month=int(str_date[5:7]), day=int(str_date[8:])) if str_date != '0' else np.nan)

    bonds_with_coupons['YTM'] = bonds_with_coupons['YTM'].apply(
        lambda str_ytm: float(str_ytm.replace('/', '.').replace('%', '')) / 100 if (pd.notna(str_ytm) and str_ytm != 'سررسید شده') else np.nan)

    bonds_with_coupons.drop('Index', inplace=True, axis=1)
    bonds_with_coupons.reset_index(inplace=True, drop=True)

    return bonds_with_coupons


def get_ifb_equally_weighted_total_index_historical_data() -> pd.DataFrame:
    url = "https://ifb.ir/HistoricalInstrumentData.asmx/getTotalSameWeightIndexHistory"

    headers = {"Content-Type": "application/json; charset=utf-8",
               "Accept": "application/json, text/javascript, */*; q=0.01", "User-Agent": "Mozilla/5.0",
               "Origin": "https://ifb.ir", "Referer": "https://ifb.ir/IFBIndex.aspx"}

    try:
        response = requests.post(url, headers=headers)
        result = pd.DataFrame(response.json()["d"], columns=["timestamp", "WeightedIndex"])
        result["GDate"] = pd.to_datetime(result["timestamp"], unit="ms").dt.date
        result['JDate'] = result['GDate'].apply(lambda gdate: jd.date.fromgregorian(year=gdate.year, month=gdate.month, day=gdate.day))
        result.drop('timestamp', inplace=True, axis=1)
        result.rename(columns={'WeightedIndex': 'EquallyWeightedTotalIndex'}, inplace=True)
        return result

    except (requests.RequestException, KeyError, IndexError, ValueError):
        return pd.DataFrame()


def get_ifb_equally_weighted_price_index_historical_data() -> pd.DataFrame:
    url = "https://ifb.ir/HistoricalInstrumentData.asmx/getSameWeightPriceIndexHistory"

    headers = {"Content-Type": "application/json; charset=utf-8",
               "Accept": "application/json, text/javascript, */*; q=0.01", "User-Agent": "Mozilla/5.0",
               "Origin": "https://ifb.ir", "Referer": "https://ifb.ir/IFBIndex.aspx"}

    try:
        response = requests.post(url, headers=headers)
        result = pd.DataFrame(response.json()["d"], columns=["timestamp", "WeightedIndex"])
        result["GDate"] = pd.to_datetime(result["timestamp"], unit="ms").dt.date
        result['JDate'] = result['GDate'].apply(lambda gdate: jd.date.fromgregorian(year=gdate.year, month=gdate.month, day=gdate.day))
        result.drop('timestamp', inplace=True, axis=1)
        result.rename(columns={'WeightedIndex': 'EquallyWeightedPriceIndex'}, inplace=True)
        return result

    except (requests.RequestException, KeyError, IndexError, ValueError):
        return pd.DataFrame()


def get_ifb_price_index_historical_data() -> pd.DataFrame:
    url = "https://ifb.ir/HistoricalInstrumentData.asmx/getPriceIndexHistory"

    headers = {"Content-Type": "application/json; charset=utf-8",
               "Accept": "application/json, text/javascript, */*; q=0.01", "User-Agent": "Mozilla/5.0",
               "Origin": "https://ifb.ir", "Referer": "https://ifb.ir/IFBIndex.aspx"}

    try:
        response = requests.post(url, headers=headers)
        result = pd.DataFrame(response.json()["d"], columns=["timestamp", "WeightedIndex"])
        result["GDate"] = pd.to_datetime(result["timestamp"], unit="ms").dt.date
        result['JDate'] = result['GDate'].apply(lambda gdate: jd.date.fromgregorian(year=gdate.year, month=gdate.month, day=gdate.day))
        result.drop('timestamp', inplace=True, axis=1)
        result.rename(columns={'WeightedIndex': 'PriceIndex'}, inplace=True)
        return result

    except (requests.RequestException, KeyError, IndexError, ValueError):
        return pd.DataFrame()


def get_ifb_total_index_historical_data() -> pd.DataFrame:
    url = "https://ifb.ir/HistoricalInstrumentData.asmx/getIndexHistory"

    headers = {"Content-Type": "application/json; charset=utf-8",
               "Accept": "application/json, text/javascript, */*; q=0.01", "User-Agent": "Mozilla/5.0",
               "Origin": "https://ifb.ir", "Referer": "https://ifb.ir/IFBIndex.aspx"}

    try:
        response = requests.post(url, headers=headers)
        result = pd.DataFrame(response.json()["d"], columns=["timestamp", "WeightedIndex"])
        result["GDate"] = pd.to_datetime(result["timestamp"], unit="ms").dt.date
        result['JDate'] = result['GDate'].apply(lambda gdate: jd.date.fromgregorian(year=gdate.year, month=gdate.month, day=gdate.day))
        result.drop('timestamp', inplace=True, axis=1)
        result.rename(columns={'WeightedIndex': 'TotalIndex'}, inplace=True)
        return result

    except (requests.RequestException, KeyError, IndexError, ValueError):
        return pd.DataFrame()


def get_ifb_total_sukuk_index_historical_data() -> pd.DataFrame:
    url = "https://ifb.ir/HistoricalInstrumentData.asmx/GetWeightedIndexHistory"

    headers = {"Content-Type": "application/json; charset=utf-8",
               "Accept": "application/json, text/javascript, */*; q=0.01", "User-Agent": "Mozilla/5.0",
               "Origin": "https://ifb.ir", "Referer": "https://ifb.ir/IFBIndex.aspx"}

    try:
        response = requests.post(url, headers=headers)
        result = pd.DataFrame(np.array(response.json()["d"])[0], columns=["timestamp", "WeightedIndex"])
        result["GDate"] = pd.to_datetime(result["timestamp"], unit="ms").dt.date
        result['JDate'] = result['GDate'].apply(lambda gdate: jd.date.fromgregorian(year=gdate.year, month=gdate.month, day=gdate.day))
        result.drop('timestamp', inplace=True, axis=1)
        result.rename(columns={'WeightedIndex': 'TotalSukukIndex'}, inplace=True)
        return result

    except (requests.RequestException, KeyError, IndexError, ValueError):
        return pd.DataFrame()


def get_sukuk_daily_trades_based_on_bs() -> pd.DataFrame:

    def extract_hidden_fields(soup):
        def get(name):
            tag = soup.select_one(f"input[name='{name}']")
            return tag["value"] if tag else None
        return {"__VIEWSTATE": get("__VIEWSTATE"),"__VIEWSTATEGENERATOR": get("__VIEWSTATEGENERATOR")}
    
    def parse_table(soup):
        table = soup.select_one("table[id$='grdDSTs']")
        table_rows = table.select("tr")[2:-1]
        table_data = []
        for row in table_rows:
            cols = row.find_all("td")
            if len(cols) == 12:
                values = [td.get_text(strip=True).replace("\u200c", "") for td in cols]
                table_data.append(values)
        return table_data
    
    def set_rows_per_page(page_session, hidden_fields, per_page="50"):
        dropdown_field = "ctl00$ContentPlaceHolder1$grdDSTs$ctl14$ctl13"
        page_data = {"__EVENTTARGET": dropdown_field, "__EVENTARGUMENT": "", "__VIEWSTATE": hidden_fields["__VIEWSTATE"],
                     "__VIEWSTATEGENERATOR": hidden_fields["__VIEWSTATEGENERATOR"], dropdown_field: per_page}
        page_result = page_session.post(url, headers=headers, data=page_data)
        return BeautifulSoup(page_result.text, "html.parser")

    url = "https://ifb.ir/datareporter/DailySukukTrades.aspx"

    headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded", "Referer": url,
               "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7"}

    session = requests.Session()
    result = session.get(url, headers=headers)
    beautiful_soup = BeautifulSoup(result.text, "html.parser")
    hidden = extract_hidden_fields(beautiful_soup)

    beautiful_soup = set_rows_per_page(session, hidden)
    hidden = extract_hidden_fields(beautiful_soup)

    all_rows = []
    seen_rows = set()
    page = 1

    while True:
        if page > 1:
            data = {"__EVENTTARGET": "ctl00$ContentPlaceHolder1$grdDSTs", "__EVENTARGUMENT": f"Page${page}",
                    "__VIEWSTATE": hidden["__VIEWSTATE"], "__VIEWSTATEGENERATOR": hidden["__VIEWSTATEGENERATOR"]}
            res = session.post(url, headers=headers, data=data)
            beautiful_soup = BeautifulSoup(res.text, "html.parser")
            hidden = extract_hidden_fields(beautiful_soup)
            time.sleep(0.5)

        rows = parse_table(beautiful_soup)
        if not rows:
            break

        key = tuple(map(tuple, rows))
        if key in seen_rows:
            break
        seen_rows.add(key)

        all_rows.extend(rows)
        page += 1

    sukuk_daily_trades = pd.DataFrame(all_rows, columns=["RowIndex", "Date", "Buyer: Government",
                                                         "Buyer: CentralBank", "Buyer: Funds", "Buyer: Banks",
                                                         "Buyer: Others", "Seller: Government",
                                                         "Seller: CentralBank", "Seller: Funds", "Seller: Banks",
                                                         "Seller: Others"])

    sukuk_daily_trades["RowIndex"] = pd.to_numeric(sukuk_daily_trades["RowIndex"], errors="coerce")
    sukuk_daily_trades = sukuk_daily_trades.dropna(subset=["RowIndex"])

    buyer_cols = [col for col in sukuk_daily_trades.columns if col.startswith("Buyer")]
    seller_cols = [col for col in sukuk_daily_trades.columns if col.startswith("Seller")]

    buyer_sukuk_daily_trades = sukuk_daily_trades[["Date"] + buyer_cols].copy()
    buyer_sukuk_daily_trades.columns = ["Date"] + [col.split(":")[1].strip() for col in buyer_cols]
    buyer_sukuk_daily_trades["Buyer/Seller"] = "Buyer"

    seller_sukuk_daily_trades = sukuk_daily_trades[["Date"] + seller_cols].copy()
    seller_sukuk_daily_trades.columns = ["Date"] + [col.split(":")[1].strip() for col in seller_cols]
    seller_sukuk_daily_trades["Buyer/Seller"] = "Seller"

    sukuk_daily_trades = pd.concat([buyer_sukuk_daily_trades, seller_sukuk_daily_trades], ignore_index=True)

    columns = ["Date", "Buyer/Seller"] + [col for col in sukuk_daily_trades.columns if col not in ["Date",
                                                                                                   "Buyer/Seller"]]
    sukuk_daily_trades = sukuk_daily_trades[columns]
    sukuk_daily_trades.sort_values('Date', inplace=True, ignore_index=True, ascending=False)

    sukuk_daily_trades['Date'] = sukuk_daily_trades['Date'].apply(lambda jdate: jd.date(year=int(jdate[:4]),
                                                                                        month=int(jdate[5:7]),
                                                                                        day=int(jdate[8:])))
    sukuk_daily_trades = sukuk_daily_trades[sukuk_daily_trades['Date'] != jd.date(1278, 10, 10)]
    sukuk_daily_trades.reset_index(inplace=True, drop=True)

    for amount_column in ['Government', 'CentralBank', 'Funds', 'Banks', 'Others']:
        sukuk_daily_trades[amount_column] = (sukuk_daily_trades[amount_column].astype(str)
                                             .str.replace("B|,", "", regex=True)
                                             .str.replace("/", ".", regex=False).str.strip())
        sukuk_daily_trades[amount_column] = pd.to_numeric(sukuk_daily_trades[amount_column], errors="coerce")

    return sukuk_daily_trades


def get_sukuk_daily_trades_based_on_ct() -> pd.DataFrame:
    def extract_hidden_fields(hidden_soup):
        def get(name):
            tag = hidden_soup.select_one(f"input[name='{name}']")
            return tag["value"] if tag else None

        return {"__VIEWSTATE": get("__VIEWSTATE"), "__VIEWSTATEGENERATOR": get("__VIEWSTATEGENERATOR")}

    def parse_table(table_soup):
        table = table_soup.select_one("table[id$='grdDSTTypes']")
        table_rows = table.select("tr")[1:-1]
        table_data = []
        for row in table_rows:
            cols = row.find_all("td")
            if len(cols) == 5:
                values = [td.get_text(strip=True).replace("\u200c", "") for td in cols]
                table_data.append(values)
        return table_data

    def set_rows_per_page(page_session, hidden_fields, per_page="50"):
        dropdown_field = "ctl00$ContentPlaceHolder1$grdDSTs$ctl14$ctl13"
        page_data = {"__EVENTTARGET": dropdown_field, "__EVENTARGUMENT": "", "__VIEWSTATE": hidden_fields["__VIEWSTATE"],
                "__VIEWSTATEGENERATOR": hidden_fields["__VIEWSTATEGENERATOR"], dropdown_field: per_page}
        page_result = page_session.post(url, headers=headers, data=page_data)
        return BeautifulSoup(page_result.text, "html.parser")

    url = "https://ifb.ir/datareporter/DailySukukTrades.aspx"

    headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded", "Referer": url,
               "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7"}

    session = requests.Session()
    res = session.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    hidden = extract_hidden_fields(soup)

    soup = set_rows_per_page(session, hidden)
    hidden = extract_hidden_fields(soup)

    all_rows = []
    seen_rows = set()
    page = 1

    while True:
        if page > 1:
            data = {"__EVENTTARGET": "ctl00$ContentPlaceHolder1$grdDSTTypes", "__EVENTARGUMENT": f"Page${page}",
                    "__VIEWSTATE": hidden["__VIEWSTATE"], "__VIEWSTATEGENERATOR": hidden["__VIEWSTATEGENERATOR"]}
            res = session.post(url, headers=headers, data=data)
            soup = BeautifulSoup(res.text, "html.parser")
            hidden = extract_hidden_fields(soup)
            time.sleep(0.25)

        rows = parse_table(soup)
        if not rows:
            break

        key = tuple(map(tuple, rows))
        if key in seen_rows:
            break
        seen_rows.add(key)

        all_rows.extend(rows)
        page += 1

    sukuk_daily_trades = pd.DataFrame(all_rows, columns=["RowIndex", "Date", "OpenMarketOperations",
                                                         "GovernmentSubscription", "Others"])

    sukuk_daily_trades["RowIndex"] = pd.to_numeric(sukuk_daily_trades["RowIndex"], errors="coerce")
    sukuk_daily_trades = sukuk_daily_trades.dropna(subset=["RowIndex"])
    sukuk_daily_trades.drop('RowIndex', inplace=True, axis=1)

    sukuk_daily_trades.sort_values('Date', inplace=True, ignore_index=True, ascending=False)
    sukuk_daily_trades['Date'] = sukuk_daily_trades['Date'].apply(lambda jdate: jd.date(year=int(jdate[:4]),
                                                                                        month=int(jdate[5:7]),
                                                                                        day=int(jdate[8:])))
    sukuk_daily_trades = sukuk_daily_trades[sukuk_daily_trades['Date'] != jd.date(1278, 10, 10)]
    sukuk_daily_trades.reset_index(inplace=True, drop=True)

    for amount_column in ["OpenMarketOperations", "GovernmentSubscription", "Others"]:
        sukuk_daily_trades[amount_column] = (sukuk_daily_trades[amount_column].astype(str)
                                             .str.replace("B|,", "", regex=True)
                                             .str.replace("/", ".", regex=False).str.strip())
        sukuk_daily_trades[amount_column] = pd.to_numeric(sukuk_daily_trades[amount_column], errors="coerce")

    return sukuk_daily_trades

