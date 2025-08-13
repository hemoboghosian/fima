import warnings
import requests
import pandas as pd
import jdatetime as jd
import datetime
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def _get_fund_types() -> pd.DataFrame:
    url = "https://fund.fipiran.ir/api/v1/fund/fundtype"
    response = requests.get(url)
    response.raise_for_status()  # raises error for bad responses
    data = response.json()
    fund_types = pd.DataFrame(data['items'])
    fund_types.columns = ['FundTypeID', 'FundTypeName', 'IsActive']
    return fund_types


def get_all_funds(set_website_developers: bool = False) ->pd.DataFrame:
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
                      'Other': 'Others Weight', 'Cash': 'Cash Weight', 'Deposit': 'Bank CDs Weight',
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
                     'Bank CDs Weight', 'FundUnits Weight', 'Commodities Weight']
    all_funds.loc[:, weight_columns] = all_funds.loc[:, weight_columns].fillna(0)

    all_funds['LiquidityGuarantor'] = all_funds['LiquidityGuarantor'].replace('----', '-')

    all_funds['DividendFrequency (Month)'] = all_funds['DividendFrequency (Month)'].fillna(0)
    all_funds['DividendFrequency (Month)'] = all_funds['DividendFrequency (Month)'].astype('int')
    all_funds['DividendFrequency (Month)'] = all_funds['DividendFrequency (Month)'].replace(0, '-')

    all_funds['WebsiteAddress'] = all_funds['WebsiteAddress'].apply(
        lambda website_address: website_address[0] if len(website_address) == 1 else None)
    all_funds.loc[all_funds['Name'] == 'صندوق تثبیت بازار سرمایه', 'WebsiteAddress'] = 'cmsfund.ir/'

    if set_website_developers:
        all_funds = _autoset_website_developers(all_funds.copy())

    return all_funds


def _get_daily_navs_per_share_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    fund_id = 1
    website = get_fund_website_address(fund_name)
    url = f"https://{website}/Chart/TotalNAV?type=getnavtotal&basketId={fund_id}"
    response = requests.get(url, timeout=10, verify=False)
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
    navs.drop('GDate', axis=1, inplace=True)
    return navs


def _get_leveraged_daily_navs_per_share_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    fund_id = 1
    website = get_fund_website_address(fund_name)
    url = f"https://{website}/Chart/TotalNAV?type=getnavtotal&basketId={fund_id}"
    response = requests.get(url, timeout=10, verify=False)
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

    preffered_subscription = pd.DataFrame(df[df['name'] == 'صدور ممتاز'].loc[3, 'List'])
    preffered_subscription['x'] = pd.to_datetime(preffered_subscription['x'], format='%m/%d/%Y').dt.date
    preffered_subscription.sort_values('x', ascending=False, inplace=True, ignore_index=True)

    preffered_redemption = pd.DataFrame(df[df['name'] == 'ابطال ممتاز'].loc[4, 'List'])
    preffered_redemption['x'] = pd.to_datetime(preffered_redemption['x'], format='%m/%d/%Y').dt.date
    preffered_redemption.sort_values('x', ascending=False, inplace=True, ignore_index=True)

    common = pd.DataFrame(df[df['name'] == 'عادی'].loc[5, 'List'])
    common['x'] = pd.to_datetime(common['x'], format='%m/%d/%Y').dt.date
    common.sort_values('x', ascending=False, inplace=True, ignore_index=True)

    navs = pd.DataFrame()
    navs['GDate'] = subscription['x']
    navs['Subscription'] = subscription['y']
    navs['Statistical'] = statistical['y']
    navs['Redemption'] = redemption['y']
    navs['Common'] = common['y']
    navs['SpecialSubscription'] = preffered_subscription['y']
    navs['SpecialRedemption'] = preffered_redemption['y']
    navs['JDate'] = navs['GDate'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
    navs.drop('GDate', axis=1, inplace=True)
    return navs


def _get_daily_total_nav_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    website = get_fund_website_address(fund_name)
    url = f"https://{website}/Chart/CombinationOfFundAssets?type=getnavtotal&basketId=1"
    response = requests.get(url, timeout=10, verify=False)
    response.raise_for_status()
    data = response.json()
    df = pd.json_normalize(data, sep='_')

    total_nav = pd.DataFrame(df[df['name'] == ''].loc[0, 'List'])
    total_nav['x'] = pd.to_datetime(total_nav['x'], format='%m/%d/%Y').dt.date
    total_nav.sort_values('x', ascending=False, inplace=True, ignore_index=True)
    total_nav.columns = ['GDate', 'TotalNAV', 'Unknown']
    total_nav.drop('Unknown', axis=1, inplace=True)
    total_nav['JDate'] = total_nav['GDate'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
    total_nav.drop('GDate', axis=1, inplace=True)
    return total_nav


def _autoset_website_developers(all_funds: pd.DataFrame, max_workers: int = 10) -> pd.DataFrame:
    results = {}
    def safe_detect(address):
        if pd.isna(address):
            return "No Address"
        return _detect_website_developer(address)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {executor.submit(safe_detect, row['WebsiteAddress']): index for index, row in all_funds.iterrows()}
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                result = future.result()
            except:
                result = "Error"
            results[index] = result
    all_funds['WebsiteDeveloper'] = all_funds.index.map(results)
    return all_funds


def _get_daily_asset_allocation_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    fund_id = 1
    website = get_fund_website_address(fund_name)
    base_url = f"https://{website}/Reports/FundDailyAssetDistribution"
    params = {"basketId": fund_id, "page": 1}

    all_rows = []
    headers = []

    while True:
        # Request the page
        response = requests.get(base_url, params=params, timeout=10, verify=False)
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

    daily_asset_allocation = pd.DataFrame(all_rows, columns=headers)

    daily_asset_allocation.drop('ردیف', inplace=True, axis=1)
    daily_asset_allocation.rename({'تاریخ': 'Date', 'پنج سهم برتر': 'Upper5%Stocks', 'پنج سهم برتر به کل دارایی': 'Upper5%Stocks Weight',
               'سایر سهام': 'OtherStocks', 'سایر سهام به کل دارایی': 'OtherStocks Weight', 'اوراق مشارکت': 'Bonds',
               'اوراق مشارکت به کل دارایی': 'Bonds Weight', 'اوراق سپرده': 'CDs',
               'اوراق سپرده به کل دارایی': 'CDs Weight', 'نقد و بانک (جاری و سپرده)': 'CashAndBank',
               'وجه نقد به کل دارایی': 'CashAndBank Weight', 'سایر دارایی‌ها': 'OtherAssets',
               'سایر دارایی‌ها به کل دارایی': 'OtherAssets Weight', 'صندوق سرمایه گذاری': 'FundUnits',
               'صندوق سرمایه گذاری به کل دارایی': 'FundUnits Weight'}, inplace=True, axis=1)

    daily_asset_allocation['Date'] = daily_asset_allocation['Date'].apply(lambda date_str: str(int(date_str.replace('/', ''))))
    daily_asset_allocation['Date'] = daily_asset_allocation['Date'].apply(
        lambda date_str: jd.date(year=int(date_str[:4]), month=int(date_str[4:6]), day=int(date_str[6:])))
    for ValueColumn in ['Upper5%Stocks', 'OtherStocks', 'Bonds', 'CDs', 'CashAndBank', 'OtherAssets', 'FundUnits']:
        daily_asset_allocation.loc[:, ValueColumn] = daily_asset_allocation[ValueColumn].str.replace(',', '').astype(int)
    for PercentageColumn in ['Upper5%Stocks Weight', 'OtherStocks Weight', 'Bonds Weight', 'CDs Weight',
                             'CashAndBank Weight', 'OtherAssets Weight', 'FundUnits Weight']:
        daily_asset_allocation.loc[:, PercentageColumn] = daily_asset_allocation[PercentageColumn].str.replace(' %', '').astype(float)

    daily_asset_allocation = daily_asset_allocation[['Date', 'OtherStocks', 'Upper5%Stocks', 'Bonds', 'CDs', 'CashAndBank',
                                                     'FundUnits', 'OtherAssets', 'OtherStocks Weight', 'Upper5%Stocks Weight',
                                                     'Bonds Weight', 'CDs Weight', 'CashAndBank Weight', 'FundUnits Weight',
                                                     'OtherAssets Weight']]

    return daily_asset_allocation


def _get_daily_asset_allocation_rayan_hamafza(fund_name: str) -> pd.DataFrame:
    fund_id = 1
    fund_website = get_fund_website_address(fund_name)
    url = f"https://{fund_website}/api/data/DailyAssetStructure/{fund_id}"

    response = requests.get(url, timeout=10, verify=False)
    response.raise_for_status()
    json_data = response.json()
    daily_asset_allocation = pd.DataFrame(json_data["data"])

    daily_asset_allocation.drop('FundId', inplace=True, axis=1)
    daily_asset_allocation.columns = \
        daily_asset_allocation.columns.map(lambda column: column.replace("Today", "").replace("Percent", "s Weight").replace("Amount", "s"))
    daily_asset_allocation.columns = \
        daily_asset_allocation.columns.map(lambda column: column.replace("Cashs", "Cash").
                                           replace("TopFiveStocks", "Upper5%Stocks").replace("Ccds", "CCDs").replace('Deposits', 'Bank'))

    daily_asset_allocation['Date'] = daily_asset_allocation['Date'].apply(lambda date_str: jd.date(year=int(date_str[:4]), month=int(date_str[5:7]), day=int(date_str[8:])))

    daily_asset_allocation = daily_asset_allocation[['Date', 'Stocks', 'Upper5%Stocks', 'Bonds', 'Cash', 'Bank', 'FundUnits', 'CCDs',
                                                     'OtherAssets', 'Stocks Weight', 'Upper5%Stocks Weight', 'Bonds Weight',
                                                     'Cash Weight', 'Bank Weight', 'FundUnits Weight', 'CCDs Weight', 'OtherAssets Weight']]

    return daily_asset_allocation


def _get_daily_asset_allocation_mabna(fund_name: str) -> pd.DataFrame:
    fund_website = get_fund_website_address(fund_name)
    url = f"https://{fund_website}/api/v1/overall/allassetsdaily.json"
    response = requests.get(url, timeout=10, verify=False)
    data = response.json()[0]
    records = []
    for item in data['values']:
        row = {'تاریخ': item['date']}
        for asset in item['assets']:
            name = asset['asset_name']
            row[name] = asset['value']
            row[f"{name} - نسبت"] = asset['percentage']
        records.append(row)
    daily_asset_allocation = pd.DataFrame(records)
    daily_asset_allocation.rename(
        {'تاریخ': 'Date', 'سپرده بانکی': 'Bank', 'سپرده بانکی - نسبت': 'Bank Weight',
         'وجه نقد': 'Cash', 'وجه نقد - نسبت': 'Cash Weight', 'سرمایه‌گذاری در اوراق بهادار با درآمد ثابت': 'Bonds',
         'سرمایه‌گذاری در اوراق بهادار با درآمد ثابت - نسبت': 'Bonds Weight', ' سرمایه گذاری در سهام ': 'Stocks',
         ' سرمایه گذاری در سهام  - نسبت': 'Stocks Weight', 'سایر دارایی‌ها': 'OtherAssets',
         'سایر دارایی‌ها - نسبت': 'OtherAssets Weight', ' پنج سهم با بیشترین وزن ': 'Upper5%Stocks',
         ' پنج سهم با بیشترین وزن  - نسبت': 'Upper5%Stocks Weight'}, inplace=True, axis=1)

    daily_asset_allocation['Date'] = daily_asset_allocation['Date'].apply(
        lambda date_str: jd.date(year=int(date_str[:4]), month=int(date_str[5:7]), day=int(date_str[8:])))

    daily_asset_allocation = daily_asset_allocation[['Date', 'Stocks', 'Upper5%Stocks', 'Bonds', 'Cash', 'Bank',
                                                     'OtherAssets', 'Stocks Weight', 'Upper5%Stocks Weight',
                                                     'Bonds Weight', 'Cash Weight', 'Bank Weight', 'OtherAssets Weight']]
    return daily_asset_allocation


def _get_daily_asset_allocation_pikad(fund_name: str) -> pd.DataFrame:
    fund_website = get_fund_website_address(fund_name)
    url_prefixes = {'servatfund.ir': 'servatsiteapi', 'goharnafis.ir': 'goharsiteapi',
                    'padashetemadfund.ir': 'farazsiteapi',
                    'edbifund.ir': 'andookhtehsiteapi', 'ganjinehzarinshahr.ir': 'ganjinehsiteapi',
                    'mellimesmfund.ir': 'multicoppersiteapi', 'tbtfund.ir': 'multitamadonsiteapi'}
    url_prefix = url_prefixes[fund_website]
    url = f"https://{url_prefix}.exphoenixfund.com/api/assetallocation/GetFlatDailyAssetAllocationByFilter"
    start_date = datetime.datetime(2000, 1, 1).isoformat()
    end_date = datetime.datetime.today().isoformat()
    take = 1000000
    page = 1
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*", "Content-Type": "application/json",
               "Referer": f"https://{fund_website}", "Origin": f"https://{fund_website}",}

    payload = {"ReportFilter": {"StartDate": start_date, "EndDate": end_date},
               "OptionalFilter": {"take": take, "page": page, "sort": [{"field": "Date", "dir": "desc"}]}}

    response = requests.post(url, headers=headers, json=payload, timeout=10, verify=False)
    response.raise_for_status()
    daily_asset_allocation = pd.DataFrame(response.json()['Result'])
    daily_asset_allocation.drop(['Id', 'Date', 'Created', 'Total'], inplace=True, axis=1)
    daily_asset_allocation.rename(
        {'JalaliDate': 'Date', 'BankAndCashValue': 'CashAndBank', 'BankAndCashPercent': 'CashAndBank Weight', 'BondValue': 'Bonds',
         'BondPercent': 'Bonds Weight', 'EquityValue': 'Stocks', 'FundValue': 'FundUnits', 'FundPercent': 'FundUnits Weight',
         'EquityPercent': 'Stocks Weight', 'OtherValue': 'OtherAssets', 'BrokerValue': 'Broker', 'BrokerPercent': 'Broker Weight',
         'OtherPercent': 'OtherAssets Weight', 'TopEquityValue': 'Upper5%Stocks', 'TopEquityPercent': 'Upper5%Stocks Weight',
         'AccountReciveablesValue': 'ReceivableAccounts', 'AccountReciveablesPercent': 'ReceivableAccounts Weight',
         'FuturePeriodsValue': 'FuturePeriods', 'FuturePeriodsPercent': 'FuturePeriods Weight'}, inplace=True, axis=1)

    daily_asset_allocation['Date'] = daily_asset_allocation['Date'].apply(
        lambda date_str: jd.date(year=int(date_str[:4]), month=int(date_str[5:7]), day=int(date_str[8:])))

    daily_asset_allocation = daily_asset_allocation[['Date', 'Stocks', 'Upper5%Stocks', 'Bonds', 'CashAndBank', 'FundUnits',
                                                     'Broker', 'FuturePeriods', 'ReceivableAccounts',  'OtherAssets',
                                                     'Stocks Weight', 'Upper5%Stocks Weight', 'Bonds Weight', 'CashAndBank Weight',
                                                     'FundUnits Weight', 'Broker Weight', 'FuturePeriods Weight',
                                                     'ReceivableAccounts Weight',  'OtherAssets Weight']]

    return daily_asset_allocation


def _get_daily_asset_allocation_rahkar(fund_name: str) -> pd.DataFrame:
    mutual_fund_id = 1
    fund_website = get_fund_website_address(fund_name)
    url = f"https://{fund_website}/api/app/asset/daily-asset-list?MutualFundCompanyID={mutual_fund_id}"
    response = requests.get(url, timeout=10, verify=False)
    daily_asset_allocation = pd.DataFrame(response.json())
    daily_asset_allocation.drop(['rowNum', 'totalRows'], inplace=True, axis=1)
    daily_asset_allocation.rename(
        {'date': 'Date', 'bankDepositKalaAsset': 'CCDs', 'bankDepositKalaAssetPersent': 'CCDs Weight',
         'jointShareAsset': 'Bonds', 'jointShareAssetPersent': 'Bonds Weight', 'shareAsset': 'Stocks',
         'unitMutualFundAsset': 'FundUnits', 'unitMutualFundAssetPersent': 'FundUnits Weight',
         'shareAssetPersent': 'Stocks Weight', 'otherAsset': 'OtherAssets', 'otherAssetPersent': 'OtherAssets Weight',
         'topFiveShareAsset': 'Upper5%Stocks', 'topFiveShareAssetPersent': 'Upper5%Stocks Weight',
         'bankDepositAsset': 'Bank', 'bankDepositAssetPersent': 'Bank Weight', 'bankAsset': 'Cash', 'bankAssetPersent': 'Cash Weight'}, inplace=True, axis=1)

    daily_asset_allocation['Date'] = daily_asset_allocation['Date'].apply(
        lambda date_str: jd.date(year=int(date_str[:4]), month=int(date_str[5:7]), day=int(date_str[8:])))

    daily_asset_allocation = daily_asset_allocation[['Date', 'Stocks', 'Upper5%Stocks', 'Bonds', 'Bank', 'Cash',
                                                     'FundUnits', 'CCDs', 'OtherAssets', 'Stocks Weight',
                                                     'Upper5%Stocks Weight', 'Bonds Weight', 'Bank Weight', 'Cash Weight',
                                                     'FundUnits Weight', 'CCDs Weight', 'OtherAssets Weight']]

    return daily_asset_allocation


def get_fund_website_address(fund_name: str) -> str:
    all_funds = get_all_funds(set_website_developers=False)
    return all_funds[all_funds['Name'] == fund_name]['WebsiteAddress'].values[0]


def _get_daily_navs_rayan_hamafza(fund_name: str) -> pd.DataFrame:
    website = get_fund_website_address(fund_name)
    url = f"https://{website}/api/data/NavMulti"
    response = requests.get(url, timeout=10, verify=False)
    response.raise_for_status()
    data = response.json()
    navs = pd.json_normalize(data)

    navs.rename({'JalaliDate': 'JDate', 'PurchaseNAVPerShare': 'Subscription', 'SellNAVPerShare': 'Redemption',
                 'StatisticNav': 'Statistical', 'TotalAssetsValue': 'TotalNAV'}, inplace=True, axis=1)

    navs['JDate'] = navs['JDate'].apply(lambda date_str: jd.date(year=int(date_str[:4]), month=int(date_str[5:7]), day=int(date_str[8:])))
    navs = navs[['JDate', 'Subscription', 'Redemption', 'Statistical', 'TotalNAV']]
    return navs


def _get_daily_navs_pikad(fund_name: str) -> pd.DataFrame:
    website = get_fund_website_address(fund_name)
    url_prefixes = {'servatfund.ir': 'servatsiteapi', 'goharnafis.ir': 'goharsiteapi',
                    'padashetemadfund.ir': 'farazsiteapi',
                    'edbifund.ir': 'andookhtehsiteapi', 'ganjinehzarinshahr.ir': 'ganjinehsiteapi',
                    'mellimesmfund.ir': 'multicoppersiteapi', 'tbtfund.ir': 'multitamadonsiteapi'}
    url_prefix = url_prefixes[website]
    url = f"https://{url_prefix}.exphoenixfund.com/api/nav/GetNavList"
    start_date = "2000-01-01"
    end_date = datetime.date.today().isoformat()
    page_size = 1000000
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*",
               "Content-Type": "application/json", "Referer": f"https://{website}", "Origin": f"https://{website}"}

    payload = {"ReportFilter": {"DateFilter": {"StartDate": start_date, "EndDate": end_date}, "PageIndex": 1,
                                "PageSize": page_size},
               "OptionalFilter": {"take": page_size, "skip": 1, "page": 1, "sort": [{"field": "Date", "dir": "asc"}]},
               "BranchId": 0, "PartyId": 0}

    response = requests.post(url, headers=headers, json=payload, timeout=10, verify=False)
    navs = pd.DataFrame(response.json()['Result'])
    navs = navs.iloc[:, 1:6]
    navs['Date'] = pd.to_datetime(navs['Date']).dt.date
    navs['Date'] = navs['Date'].apply(
        lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
    navs.rename({'Date': 'JDate', 'SubscriptionNAV': 'Subscription', 'RedemptionNAV': 'Redemption',
                 'StaticalNAV': 'Statistical', 'NetAssetValue': 'TotalNAV'}, inplace=True, axis=1)
    navs = navs[['JDate', 'Subscription', 'Redemption', 'Statistical', 'TotalNAV']]
    return navs


def _get_daily_navs_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    navs_per_share = _get_daily_navs_per_share_tadbirpardaz(fund_name)
    total_navs = _get_daily_total_nav_tadbirpardaz(fund_name)
    navs = pd.merge(total_navs, navs_per_share, on='JDate', how='inner')
    navs = navs[['JDate', 'Subscription', 'Redemption', 'Statistical', 'TotalNAV']]
    return navs


def _get_daily_navs_mabna(fund_name: str) -> pd.DataFrame:
    website = get_fund_website_address(fund_name)
    url = f"https://{website}/api/v1/overall/navps.json"
    response = requests.get(url, timeout=10, verify=False)
    navs = pd.DataFrame(response.json()[0]['values'])
    navs['date'] = navs['date'].apply(
        lambda date_str: jd.date(year=int(date_str[:4]), month=int(date_str[4:6]), day=int(date_str[6:8])))
    navs = navs.iloc[:, :5].copy()
    navs.columns = ['JDate', 'Subscription', 'Redemption', 'Statistical', 'TotalNAV']
    return navs


def _get_leveraged_daily_navs_mabna(fund_name: str) -> pd.DataFrame:
    portfolio_id = 1
    website = get_fund_website_address(fund_name)
    url = f"https://{website}/api/v2/public/fund/chart?portfolio_id={portfolio_id}"
    response = requests.get(url, timeout=10, verify=False)
    navs = pd.DataFrame(response.json()['data'])
    navs['date_time'] = pd.to_datetime(navs['date_time']).dt.date
    navs['date_time'] = navs['date_time'].apply(lambda g_date: jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day))
    navs.rename(columns={'date_time': 'JDate', 'total_unit_count': 'TotalUnits', 'purchase_price': 'SubscriptionPerUnit', 'redemption_price': 'RedemptionPerUnit',
       'common_unit_purchase_price': 'CommonSubscriptionPerUnit', 'today_purchase_count': 'TodaySubscriptionsCount',
       'today_redeemed_count': 'TodayRedeemsCount', 'total_purchase_count': 'TotalSubscriptionsCount', 'total_redeemed_count': 'TotalRedeemedCount',
       'total_preferred_unit_count': 'TotalPrefferedUnits', 'total_common_unit_count': 'TotalCommonUnits',
       'statistical_value': 'StatisticalPerUnit'}, inplace=True)
    return navs


def _get_daily_navs_rahkar(fund_name: str) -> pd.DataFrame:
    mutual_fund_id = 1
    fund_website = get_fund_website_address(fund_name)
    url = f"https://{fund_website}/api/app/nav/nav-list?MutualFundCompanyID={mutual_fund_id}"
    response = requests.get(url, timeout=10, verify=False)
    navs = pd.DataFrame(response.json())
    navs['date'] = navs['date'].apply(lambda date_str: jd.date(year=int(date_str[:4]), month=int(date_str[5:7]), day=int(date_str[8:])))
    navs = navs.iloc[:, :5].copy()
    navs.columns = ['JDate', 'Subscription', 'Redemption', 'Statistical', 'TotalNAV']


def get_daily_navs(fund_name: str) -> pd.DataFrame:
    all_funds = get_all_funds(set_website_developers=False)
    fund_type = all_funds[all_funds['Name'] == fund_name]['FundType'].values[0]
    if fund_type in ['پروژه‌ای', 'خصوصی']:
        print(f"Fund type is {fund_type} and it doesn't have daily NAVs.")
        return pd.DataFrame()
    elif fund_name == 'صندوق تثبیت بازار سرمایه':
        print(f"The {fund_name} doesn't have daily asset allocations.")
        return pd.DataFrame()
    else:
        website_address = all_funds[all_funds['Name'] == fund_name]['WebsiteAddress'].values[0]
        website_developer = _detect_website_developer(website=website_address)
        if website_developer == 'گروه رایانه تدبیر پرداز':
            if fund_type == 'در سهام-سهامی اهرمی':
                daily_navs = _get_leveraged_daily_navs_per_share_tadbirpardaz(fund_name)
            else:
                daily_navs = _get_daily_navs_tadbirpardaz(fund_name)
        elif website_developer == 'شرکت رایان هم افزا':
            daily_navs = _get_daily_navs_rayan_hamafza(fund_name)
        elif website_developer == 'پردازش اطلاعات مالی مبنا':
            if fund_type == 'در سهام-سهامی اهرمی':
                daily_navs = _get_daily_navs_tadbirpardaz(fund_type)
            else:
                daily_navs = _get_daily_navs_mabna(fund_name)
        elif website_developer == 'پیکاد':
            daily_navs = _get_daily_navs_pikad(fund_name)
        elif website_developer == 'راهکار حامی پرداز':
            daily_navs = _get_daily_navs_rahkar(fund_name)
        else:
            print('The website developer is unknown. Please contact me if you got this message.')
            daily_navs = None
        return daily_navs


def get_daily_asset_allocation(fund_name: str) -> pd.DataFrame:
    all_funds = get_all_funds(set_website_developers=False)
    fund_type = all_funds[all_funds['Name'] == fund_name]['FundType'].values[0]
    if fund_type in ['پروژه‌ای', 'خصوصی']:
        print(f"Fund type is {fund_type} and it doesn't have daily asset allocations.")
        return pd.DataFrame()
    elif fund_name == 'صندوق تثبیت بازار سرمایه':
        print(f"The {fund_name} doesn't have daily asset allocations.")
        return pd.DataFrame()
    else:
        website_address = all_funds[all_funds['Name'] == fund_name]['WebsiteAddress'].values[0]
        website_developer = _detect_website_developer(website=website_address)
        if website_developer == 'گروه رایانه تدبیر پرداز':
            daily_asset_allocation = _get_daily_asset_allocation_tadbirpardaz(fund_name)
        elif website_developer == 'شرکت رایان هم افزا':
            daily_asset_allocation = _get_daily_asset_allocation_rayan_hamafza(fund_name)
        elif website_developer == 'پردازش اطلاعات مالی مبنا':
            daily_asset_allocation = _get_daily_asset_allocation_mabna(fund_name)
        elif website_developer == 'پیکاد':
            daily_asset_allocation = _get_daily_asset_allocation_pikad(fund_name)
        else:
            print('The website developer is unknown. Please contact me if you see this message.')
            daily_asset_allocation = None
        return daily_asset_allocation


def _get_html_with_selenium(url: str, webdriver_type: str='Chrome', sleep_time: int=5):
    if webdriver_type == 'Firefox':
        options = FirefoxOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=options)
        driver.get(url)
        time.sleep(sleep_time)
        html = driver.page_source
        driver.quit()
    elif webdriver_type == 'Chrome':
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)
        time.sleep(sleep_time)
        html = driver.page_source
        driver.quit()
    else:
        html = ""
    return html


def _detect_website_developer(website: str) -> str:
    warnings.filterwarnings('ignore')
    urls = [f'https://{website}', f'http://{website}']
    for url in urls:
        try:
            response = requests.get(url, timeout=15, verify=False)
            html = response.text
            soup = BeautifulSoup(html, "html.parser")

            if soup.select_one(".tadbirLogo") or soup.select_one(".TadbirLogo") or "تدبیرپرداز" in html:
                return "گروه رایانه تدبیر پرداز"
            elif "rayanhamafza.com" in html:
                return "شرکت رایان هم افزا"
            elif "mabnadp.com" in html or "پردازش اطلاعات مالی مبنا" in html:
                return "پردازش اطلاعات مالی مبنا"
            elif "ره پویان پردازش گستر صحرا" in html:
                return "ره پویان پردازش گستر صحرا"
            elif "Webzi.ir" in html:
                return 'وبزی'
            elif "گروه طراحی کوثروب" in html or "kowsarweb.ir" in html:
                return 'گروه طراحی کوثر وب'
            elif "صندوق سرمایه‌گذاری جسورانه ارغوان" in html:
                return "صندوق سرمایه‌گذاری جسورانه ارغوان"
            elif "صندوق سرمایه‌گذاری جسورانه پارتیان" in html:
                return "صندوق سرمایه‌گذاری جسورانه پارتیان"
            else:
                html = _get_html_with_selenium(url)
                soup = BeautifulSoup(html, "html.parser")
                if "rahkarhamipardaz.com" in html or "Rahkar Hami Pardaz" in html:
                    return "راهکار حامی پرداز"
                elif "Pikad" in html or 'pikad.net' in html:
                    return "پیکاد"
                elif soup.select_one(".tadbirLogo") or soup.select_one(".TadbirLogo") or "تدبیرپرداز" in html:
                    return "گروه رایانه تدبیر پرداز"
                elif "rayanhamafza.com" in html:
                    return "شرکت رایان هم افزا"
                elif "mabnadp.com" in html or "پردازش اطلاعات مالی مبنا" in html:
                    return "پردازش اطلاعات مالی مبنا"
                elif "ره پویان پردازش گستر صحرا" in html:
                    return "ره پویان پردازش گستر صحرا"
                elif "Webzi.ir" in html:
                    return 'وبزی'
                elif "گروه طراحی کوثروب" in html or "kowsarweb.ir" in html:
                    return 'گروه طراحی کوثر وب'
                elif "صندوق سرمایه‌گذاری جسورانه ارغوان" in html:
                    return "صندوق سرمایه‌گذاری جسورانه ارغوان"
                elif "صندوق سرمایه‌گذاری جسورانه پارتیان" in html:
                    return "صندوق سرمایه‌گذاری جسورانه پارتیان"
                else:
                    print(f'The website developer for {url} is unknown. Please contact me if you got this message.')
                    return "Unknown"
        except requests.exceptions.ConnectionError:
            # print(f"[DNS/Connection Error] {url}")
            continue
        except requests.exceptions.RequestException:
            # print(f"[Request Error] {url}")
            continue
    return "-"


# AllFunds = get_all_funds(set_website_developers=True)
#
# UknownFunds = AllFunds[AllFunds['WebsiteDeveloper'] == 'Unknown']
# BarFunds = AllFunds[AllFunds['WebsiteDeveloper'] == '-']
#
# TestFunds = AllFunds[AllFunds['WebsiteDeveloper'] == 'گروه رایانه تدبیر پرداز']
# TestFund = TestFunds.iloc[1, :].to_frame().T
# TestFundName = TestFund['Name'].values[0]
# TestFundWebsiteAddress = TestFund['WebsiteAddress'].values[0]
# print(TestFundWebsiteAddress)