import requests
import pandas as pd
import jdatetime as jd
# from selenium import webdriver
# from selenium.webdriver.firefox.service import Service
# from selenium.webdriver.firefox.options import Options
# from webdriver_manager.firefox import GeckoDriverManager
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as ec
# from bs4 import BeautifulSoup


def get_all_funds() ->pd.DataFrame:
    url = "https://fund.fipiran.ir/api/v1/fund/fundcompare"
    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    data = response.json()
    all_funds = pd.DataFrame(data['items'])

    all_funds['websiteAddress'] = all_funds['websiteAddress'].apply(
        lambda website_address: website_address[0] if len(website_address) == 1 else None)

    return all_funds


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


def get_daily_navs(website: str) -> pd.DataFrame:
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


def get_daily_total_nav(website: str) -> pd.DataFrame:
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
    for index, row in AllFunds.iterrows():
        website = row['websiteAddress'] if row['websiteAddress'] is not None else None
        try:
            _ = get_daily_total_nav(website)
            all_funds.loc[index, 'WebsiteDeveloper'] = 'گروه رایانه تدبیرپرداز'
        except:
            print('Found new website developer. Please contact me if you get this message.')
    return all_funds


AllFunds = get_all_funds()