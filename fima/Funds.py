import requests
import pandas as pd
import jdatetime as jd
import datetime
from bs4 import BeautifulSoup
import time


# from selenium import webdriver
# from selenium.webdriver.firefox.service import Service
# from selenium.webdriver.firefox.options import Options
# from webdriver_manager.firefox import GeckoDriverManager
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as ec
# from bs4 import BeautifulSoup


# def get_all_funds_by_date(j_date: str) -> pd.DataFrame:
#     options = Options()
#     options.add_argument("--headless")
#     options.add_argument("--disable-gpu")
#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-dev-shm-usage")
#
#     driver = webdriver.Chrome(service=Service(GeckoDriverManager().install()), options=options)
#
#     g_date = str(jd.date(int(j_date[:4]), int(j_date[5:7]), int(j_date[8:])).togregorian())
#     url = f"https://fund.fipiran.ir/mf/list?date={g_date}"
#     driver.get(url)
#     wait = WebDriverWait(driver, 15)
#
#     # --- Step 1: Open pagination dropdown ---
#     dropdown_btn = wait.until(ec.element_to_be_clickable(
#         (By.CSS_SELECTOR, "div.MuiSelect-root[role='button']")))
#     dropdown_btn.click()
#
#     # --- Step 2: Click 'همه' (value = 523) ---
#     all_option = wait.until(ec.element_to_be_clickable((By.XPATH, "//li[@data-value='523']")))
#     all_option.click()
#
#     wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "tbody tr")) > 100)
#
#     soup = BeautifulSoup(driver.page_source, "html.parser")
#     driver.quit()
#
#     headers = [th.get_text(strip=True) for th in soup.select("thead th div span") if th.get_text(strip=True)]
#
#     rows = []
#     for tr in soup.select("tbody tr"):
#         tds = tr.find_all("td")
#         row = [td.get_text(strip=True).replace('\u200c', '') for td in tds][3:]
#         rows.append(row)
#
#     df = pd.DataFrame(rows, columns=headers)
#     return df


def _get_fund_types() -> pd.DataFrame:
    url = "https://fund.fipiran.ir/api/v1/fund/fundtype"
    response = requests.get(url)
    response.raise_for_status()  # raises error for bad responses
    data = response.json()
    fund_types = pd.DataFrame(data['items'])
    fund_types.columns = ['FundTypeID', 'FundTypeName', 'IsActive']
    return fund_types


def get_all_funds() ->pd.DataFrame:
    url = "https://fund.fipiran.ir/api/v1/fund/fundcompare"
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    data = response.json()
    all_funds = pd.DataFrame(data['items'])

    all_funds.drop(['rankOf12Month', 'rankOf24Month', 'rankOf36Month', 'rankOf48Month', 'rankOf60Month',
                   'rankLastUpdate', 'guaranteedEarningRate', 'articlesOfAssociationLink', 'prosoectusLink',
                   'fundPublisher', 'fundWatch'], inplace=True, axis=1)
    all_funds.columns = all_funds.columns.map(lambda column: column[0].upper() + column[1:])
    all_funds.rename({'RegNo': 'RegNo', 'TypeOfInvest': 'InvestmentType', 'FundSize': 'TotalNAV',
                      'InitiationDate': 'InceptionDate', 'DailyEfficiency': 'DailyReturn',
                      'WeeklyEfficiency': 'WeeklyReturn', 'MonthlyEfficiency': 'MonthlyReturn',
                      'QuarterlyEfficiency': 'QuarterlyReturn', 'SixMonthEfficiency': 'SemiAnnualReturn',
                      'AnnualEfficiency': 'AnnualReturn', 'Efficiency': 'ReturnFromInception',
                      'CancelNav': 'RedemptionNAV', 'IssueNav': 'SubscriptionNAV',
                      'DividendIntervalPeriod': 'DividendFrequency (Month)', 'Date': 'UpdateDate',
                      'EstimatedEarningRate': 'EstimatedReturn', 'InvestedUnits': 'Units',
                      'Guarantor': 'LiquidityGuarantor', 'GuarantorSeoRegisterNo': 'LiquidityGuarantorSeoRegisterNumber',
                      'FiveBest': 'Upper5%Stocks Weight', 'Stock': 'Stocks Weight', 'Bond': 'Bonds Weight',
                      'Other': 'Others Weight', 'Cash': 'Cash Weight', 'Deposit': 'Deposits Weight',
                      'FundUnit': 'FundUnits Weight', 'Commodity': 'Commodities Weight', 'SmallSymbolName': 'Ticker',
                      'InsCode': 'InstrumentCode'}, axis=1, inplace=True)

    fund_types = _get_fund_types()
    fund_type_map = fund_types.set_index('FundTypeID')['FundTypeName']
    all_funds['FundType'] = all_funds['FundType'].map(fund_type_map)

    all_funds['InvestmentType'] = all_funds['InvestmentType'].map(
        lambda investment_type: 'ETF' if investment_type == 'Negotiable' else 'Open-Ended')

    all_funds['InceptionDate'] = pd.to_datetime(all_funds['InceptionDate'], errors="coerce").dt.date
    all_funds['InceptionDate'] = all_funds['InceptionDate'].apply(
        lambda g: jd.date.fromgregorian(date=g) if isinstance(g, datetime.date) and not pd.isna(g) else None)

    all_funds['UpdateDate'] = pd.to_datetime(all_funds['UpdateDate'], errors="coerce").dt.date
    all_funds['UpdateDate'] = all_funds['UpdateDate'].apply(
        lambda g: jd.date.fromgregorian(date=g) if isinstance(g, datetime.date) and not pd.isna(g) else None)

    weight_columns = ['Upper5%Stocks Weight', 'Stocks Weight', 'Bonds Weight', 'Others Weight', 'Cash Weight',
                     'Deposits Weight', 'FundUnits Weight', 'Commodities Weight']
    all_funds.loc[:, weight_columns] = all_funds.loc[:, weight_columns].fillna(0)

    all_funds['LiquidityGuarantor'] = all_funds['LiquidityGuarantor'].replace('----', '-')

    all_funds['DividendFrequency (Month)'] = all_funds['DividendFrequency (Month)'].fillna(0)
    all_funds['DividendFrequency (Month)'] = all_funds['DividendFrequency (Month)'].astype('int')
    all_funds['DividendFrequency (Month)'] = all_funds['DividendFrequency (Month)'].replace(0, '-')

    all_funds['WebsiteAddress'] = all_funds['WebsiteAddress'].apply(
        lambda website_address: website_address[0] if len(website_address) == 1 else None)

    return all_funds


def get_daily_navs_tadbirpardaz(website: str) -> pd.DataFrame:
    url = f"https://{website}/Chart/TotalNAV?type=getnavtotal&basketId=1"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    df = pd.json_normalize(data, sep='_')

    subscription = pd.DataFrame(df[df['name'] == 'صدور'].loc[0, 'List'])
    subscription['x'] = pd.to_datetime(subscription['x'], format='%m/%d/%Y').dt.date
    subscription.sort_values('x', ascending=False, inplace=True, ignore_index=True)

    statistical = pd.DataFrame(df[df['name'] == 'آماری'].loc[1, 'List'])
    statistical['x'] = pd.to_datetime(statistical['x'], format='%m/%d/%Y').dt.date
    statistical.sort_values('x', ascending=False, inplace=True, ignore_index=True)

    redemption = pd.DataFrame(df[df['name'] == 'ابطال'].loc[2, 'List'])
    redemption['x'] = pd.to_datetime(redemption['x'], format='%m/%d/%Y').dt.date
    redemption.sort_values('x', ascending=False, inplace=True, ignore_index=True)

    navs = pd.DataFrame()
    navs['GDate'] = subscription['x']
    navs['Subscription'] = subscription['y']
    navs['Statistical'] = statistical['y']
    navs['Redemption'] = redemption['y']
    navs['JDate'] = navs['GDate'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
    return navs


def get_daily_total_nav_tadbirpardaz(website: str) -> pd.DataFrame:
    url = f"https://{website}/Chart/CombinationOfFundAssets?type=getnavtotal&basketId=1"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    df = pd.json_normalize(data, sep='_')

    total_nav = pd.DataFrame(df[df['name'] == ''].loc[0, 'List'])
    total_nav['x'] = pd.to_datetime(total_nav['x'], format='%m/%d/%Y').dt.date
    total_nav.sort_values('x', ascending=False, inplace=True, ignore_index=True)
    total_nav.columns = ['GDate', 'TotalNAV', 'Unknown']
    total_nav.drop('Unknown', axis=1, inplace=True)
    total_nav['JDate'] = total_nav['GDate'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
    return total_nav


def initialize_website_developers(all_funds: pd.DataFrame) -> pd.DataFrame:
    all_funds['WebsiteDeveloper'] = None
    for index, row in all_funds.iterrows():
        website = row['websiteAddress'] if row['websiteAddress'] is not None else None
        try:
            _ = get_daily_total_nav_tadbirpardaz(website)
            all_funds.loc[index, 'WebsiteDeveloper'] = 'گروه رایانه تدبیرپرداز'
        except:
            print('Found new website developer. Please contact me if you get this message.')
    return all_funds


def get_daily_asset_allocation_tadbirpardaz(website: str) -> pd.DataFrame:
    basket_id = 1
    base_url = f"https://{website}/Reports/FundDailyAssetDistribution"
    params = {"basketId": basket_id, "page": 1}

    all_rows = []
    headers = []

    while True:
        # Request the page
        response = requests.get(base_url, params=params)
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract headers (only once)
        if not headers:
            headers = [th.get_text(strip=True) for th in soup.select("thead th")]

        # Extract data rows
        for tr in soup.select("tbody tr"):
            row = [td.get_text(strip=True).replace("\u200c", "") for td in tr.find_all("td")]
            all_rows.append(row)

        # Check if there is a next page
        next_page_link = soup.select_one("tfoot .pager a[title='Next page']")
        if next_page_link:
            # Update page number in query params
            params["page"] += 1
            time.sleep(0.3)  # be polite
        else:
            break

    df = pd.DataFrame(all_rows, columns=headers)

    df.drop('ردیف', inplace=True, axis=1)
    df.rename({'تاریخ': 'Date', 'پنج سهم برتر': 'Upper5%Stocks', 'پنج سهم برتر به کل دارایی': 'Upper5%Stocks Weight',
               'سایر سهام': 'OtherStocks', 'سایر سهام به کل دارایی': 'OtherStocks Weight', 'اوراق مشارکت': 'Bonds',
               'اوراق مشارکت به کل دارایی': 'Bonds Weight', 'اوراق سپرده': 'Deposits',
               'اوراق سپرده به کل دارایی': 'Deposits Weight', 'نقد و بانک (جاری و سپرده)': 'Cash',
               'وجه نقد به کل دارایی': 'Cash Weight', 'سایر دارایی‌ها': 'OtherAssets',
               'سایر دارایی‌ها به کل دارایی': 'OtherAssets Weight', 'صندوق سرمایه گذاری': 'Funds',
               'صندوق سرمایه گذاری به کل دارایی': 'Funds Weight'}, inplace=True, axis=1)

    df['Date'] = df['Date'].apply(lambda date_str: str(int(date_str.replace('/', ''))))
    df['Date'] = df['Date'].apply(
        lambda date_str: jd.date(year=int(date_str[:4]), month=int(date_str[4:6]), day=int(date_str[6:])))
    for ValueColumn in ['Upper5%Stocks', 'OtherStocks', 'Bonds', 'Deposits', 'Cash', 'OtherAssets', 'Funds']:
        df.loc[:, ValueColumn] = df[ValueColumn].str.replace(',', '').astype(int)
    for PercentageColumn in ['Upper5%Stocks Weight', 'OtherStocks Weight', 'Bonds Weight', 'Deposits Weight',
                             'Cash Weight', 'OtherAssets Weight', 'Funds Weight']:
        df.loc[:, PercentageColumn] = df[PercentageColumn].str.replace(' %', '').astype(float)

    return df

