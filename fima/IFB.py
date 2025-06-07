import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from io import StringIO
import jdatetime as jd


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