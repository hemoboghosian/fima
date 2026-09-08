import warnings
import requests
import pandas as pd
import jdatetime as jd
import datetime as dt
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import re
from functools import lru_cache
import warnings
from urllib3.exceptions import InsecureRequestWarning


warnings.simplefilter("ignore", InsecureRequestWarning)

PIKAD_URL_PREFIXES = {'servatfund.ir': 'servatsiteapi', 'goharnafis.ir': 'goharsiteapi',
                      'padashetemadfund.ir': 'farazsiteapi', 'edbifund.ir': 'andookhtehsiteapi',
                      'ganjinehzarinshahr.ir': 'ganjinehsiteapi', 'mellimesmfund.ir': 'multicoppersiteapi',
                      'tbtfund.ir': 'multitamadonsiteapi'}
NIKA_MANUAL_CONFIGS = \
    {
        # Only use this for websites whose HTML does not expose config.
        # Usually this should stay empty because Nika config is inside the page HTML.
        #
        # Example:
        # 'atiyehfund.com': {
        #     'apiPath': 'p.mofidfund.com',
        #     'hivePath': 'vhive/HivePortal',
        #     'basketId': '8',
        #     'fundId': '8'
        # }
    }


NO_PUBLIC_NAV_FUND_TYPES = {"جسورانه", "اختصاصی بازارگردانی", "زمین و ساختمان", "خصوصی", "پروژه‌ای"}


# GENERAL HELPER FUNCTIONS
def _safe_get_json(url: str, timeout: int = 30, params: dict = None):
    try:
        response = requests.get(url, params=params, timeout=timeout, verify=False, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            return None
        text = response.text.strip()
        if not text:
            return None
        return response.json()
    except Exception:
        return None


def _safe_get_text(url: str, timeout: int = 30):
    try:
        response = requests.get(url, timeout=timeout, verify=False, headers={"User-Agent": "Mozilla/5.0"},
                                allow_redirects=True)
        if response.status_code != 200:
            return None
        text = response.text.strip()
        if not text:
            return None
        return text
    except Exception:
        return None


def _safe_post_json(url: str, payload: dict, headers: dict = None, timeout: int = 12):
    try:
        if headers is None:
            headers = {}
        default_headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*",
                           "Content-Type": "application/json"}
        default_headers.update(headers)
        response = requests.post(url, json=payload, headers=default_headers, timeout=timeout, verify=False)
        if response.status_code != 200:
            return None
        text = response.text.strip()
        if not text:
            return None
        return response.json()
    except Exception:
        return None


def _today_jalali_str() -> str:
    today = jd.date.today()
    return f"{today.year:04d}/{today.month:02d}/{today.day:02d}"


def _normalize_website_host(website: str):
    if pd.isna(website) or website is None:
        return None
    website = str(website).strip()
    if website == "":
        return None
    if not website.startswith(("http://", "https://")):
        website_for_parse = "https://" + website
    else:
        website_for_parse = website
    parsed = urlparse(website_for_parse)
    host = parsed.netloc
    # Handles cases like "aghighfund.com/home/index"
    if host == "":
        host = parsed.path.split("/")[0]
    host = host.strip().strip("/").lower()
    if host == "":
        return None
    return host


def _build_base_urls(website: str) -> list:
    host = _normalize_website_host(website)
    if host is None:
        return []
    hosts = [host]
    # Try without www if the website has www.
    if host.startswith("www."):
        hosts.append(host[4:])
    # Do NOT automatically add www. for all websites.
    # Many Iranian fund APIs fail with www.
    hosts = list(dict.fromkeys(hosts))
    base_urls = []
    for h in hosts:
        base_urls.append(f"https://{h}")
        base_urls.append(f"http://{h}")
    return base_urls


def _jalali_str_to_date(date_str: str) -> jd.date:
    date_str = str(date_str).strip().replace("-", "/")
    if "/" in date_str:
        parts = date_str.split("/")
        return jd.date(year=int(parts[0]), month=int(parts[1]), day=int(parts[2]))
    date_str = re.sub(r"\D", "", date_str)
    if len(date_str) < 8:
        raise ValueError(f"Invalid Jalali date format: {date_str}")
    return jd.date(year=int(date_str[:4]), month=int(date_str[4:6]), day=int(date_str[6:8]))


def _gregorian_to_jalali(g_date) -> jd.date:
    return jd.date.fromgregorian(year=g_date.year, month=g_date.month, day=g_date.day)


def _require_columns(df: pd.DataFrame, required_columns: list, source_name: str):
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"{source_name} response is missing these columns: {missing_columns}")


# FIPIRAN FUNCTIONS
def _get_fund_types() -> pd.DataFrame:
    url = "https://www.fipiran.ir/services/fund/fundtype"
    fund_types = pd.DataFrame(requests.get(url, timeout=30, verify=False).json()['items'])
    fund_types.columns = ['FundTypeID', 'FundTypeName', 'IsActive']
    return fund_types


def _get_fund_website_address(fund_name: str, all_funds: pd.DataFrame = None) -> str:
    fund_row = _get_fund_row(fund_name, all_funds)
    return fund_row["WebsiteAddress"]


# DETECTOR VALIDATORS
def _is_valid_tadbirpardaz_nav_response(data) -> bool:
    if not isinstance(data, list) or len(data) == 0:
        return False
    names = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        names.add(str(item.get("name", "")).strip())
        item_list = item.get("List")
        if item_list is not None and not isinstance(item_list, list):
            return False
    # Tadbir NAV usually has these chart series.
    required_names = {"صدور", "ابطال", "آماری"}
    return len(required_names.intersection(names)) >= 2


def _is_valid_rayan_hamafza_nav_response(data) -> bool:
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        records = data["data"]
    elif isinstance(data, list):
        records = data
    else:
        return False
    if len(records) == 0:
        return False
    df = pd.DataFrame(records)
    columns = set(df.columns)
    # Newer Rayan format:
    # /api/v1/public/nav/1
    lower_format_required = {"jalaliDate", "purchaseNAVPerShare", "sellNAVPerShare", "statisticalNAVPerShare", "units",
                             "nav"}
    # Older Rayan format:
    # /api/data/NAV/1
    upper_format_required = {"JalaliDate", "PurchaseNAVPerShare", "SellNAVPerShare", "StatisticalNAVPerShare", "Units",
                             "NAV"}
    return (lower_format_required.issubset(columns) or upper_format_required.issubset(columns))


def _is_valid_mabna_nav_response(data) -> bool:
    if not isinstance(data, dict):
        return False
    records = data.get("data")
    if not isinstance(records, list) or len(records) == 0:
        return False
    first = records[0]
    if not isinstance(first, dict):
        return False
    # Your Mabna parser depends on data['data'] and date_time.
    if "date_time" not in first:
        return False
    # Keep this flexible because Mabna keys differ between normal and leveraged funds.
    return len(first.keys()) >= 5


def _is_valid_rahkar_nav_response(data) -> bool:
    if not isinstance(data, list) or len(data) == 0:
        return False
    first = data[0]
    if not isinstance(first, dict):
        return False
    keys = set(first.keys())
    if "date" not in keys:
        return False
    # Your Rahkar parser takes the first 5 columns and renames them.
    # So require date + at least 4 other fields.
    return len(keys) >= 5


def _is_valid_pikad_nav_response(data) -> bool:
    if not isinstance(data, dict):
        return False
    records = data.get("Result")
    if not isinstance(records, list) or len(records) == 0:
        return False
    first = records[0]
    if not isinstance(first, dict):
        return False
    expected_keys = {"Date", "SubscriptionNAV", "RedemptionNAV", "StaticalNAV", "NetAssetValue"}
    return expected_keys.issubset(set(first.keys()))


def _is_valid_nika_nav_response(data) -> bool:
    if not isinstance(data, dict):
        return False
    records = data.get("items")
    if not isinstance(records, list) or len(records) == 0:
        return False
    first = records[0]
    if not isinstance(first, dict):
        return False
    expected_keys = {"date", "issuanceNav", "redemptionNav", "nominalNAV", "totalUnit", "redemptionNetAssetValue"}
    return expected_keys.issubset(set(first.keys()))


def _is_valid_noavaran_nav_response(data) -> bool:
    if not isinstance(data, dict):
        return False
    records = data.get("content")
    if not isinstance(records, list) or len(records) == 0:
        return False
    first = records[0]
    if not isinstance(first, dict):
        return False
    expected_keys = {"Date", "SubscriptionValue", "RedemptionValue", "StatisticalValue", "TotalQuantity",
                     "NetAssetValue"}
    return expected_keys.issubset(set(first.keys()))


def _looks_like_noavaran_asset_allocation(data) -> bool:
    if not isinstance(data, dict):
        return False
    records = data.get("content")
    if not isinstance(records, list) or len(records) == 0:
        return False
    first = records[0]
    if not isinstance(first, dict):
        return False
    expected_keys = {"Date", "ShareAndWarrantValue", "BondValue", "UnitMutualFundValue", "CertificateOfDepositValue",
                     "BankDepositValue", "OtherValue", "FiveInstrumentValue"}
    return expected_keys.issubset(set(first.keys()))


# DETECTORS
def _detect_tadbirpardaz_by_nav_api(website: str) -> bool:
    for base_url in _build_base_urls(website):
        url = f"{base_url}/Chart/TotalNAV?type=getnavtotal&basketId=1"
        data = _safe_get_json(url)
        if _is_valid_tadbirpardaz_nav_response(data):
            return True
    return False


def _detect_rayan_hamafza_by_nav_api(website: str) -> bool:
    for base_url in _build_base_urls(website):
        candidate_urls = \
            [
                # Newer Rayan API
                f"{base_url}/api/v1/public/nav/1",

                # Older Rayan API, like emacofund.ir
                f"{base_url}/api/data/NAV/1",
            ]
        for url in candidate_urls:
            data = _safe_get_json(url, timeout=30)
            if _is_valid_rayan_hamafza_nav_response(data):
                return True
    return False


def _detect_mabna_by_nav_api(website: str) -> bool:
    for base_url in _build_base_urls(website):
        url = (f"{base_url}/api/v2/public/reports/navps?start_date=1997-11-10T08%3A13%3A36.377Z&"
               f"end_date=2026-01-11T08%3A13%3A36.377Z&page=1&size=5")
        data = _safe_get_json(url, timeout=30)
        if _is_valid_mabna_nav_response(data):
            return True
    return False


def _detect_rahkar_by_nav_api(website: str) -> bool:
    for base_url in _build_base_urls(website):
        url = f"{base_url}/api/app/nav/nav-list?MutualFundCompanyID=1"
        data = _safe_get_json(url, timeout=30)
        if _is_valid_rahkar_nav_response(data):
            return True
    return False


def _detect_pikad_by_nav_api(website: str) -> bool:
    host = _normalize_website_host(website)
    if host is None:
        return False
    if host not in PIKAD_URL_PREFIXES:
        return False
    url_prefix = PIKAD_URL_PREFIXES[host]
    url = f"https://{url_prefix}.exphoenixfund.com/api/nav/GetNavList"
    start_date = "2000-01-01"
    end_date = dt.date.today().isoformat()
    page_size = 5
    headers = {"Referer": f"https://{host}", "Origin": f"https://{host}"}
    payload = {"ReportFilter": {"DateFilter": {"StartDate": start_date, "EndDate": end_date}, "PageIndex": 1,
                                "PageSize": page_size},
               "OptionalFilter": {"take": page_size, "skip": 1, "page": 1, "sort": [{"field": "Date", "dir": "asc"}]},
               "BranchId": 0, "PartyId": 0}
    data = _safe_post_json(url, payload=payload, headers=headers)
    return _is_valid_pikad_nav_response(data)


def _detect_nika_by_nav_api(website: str) -> bool:
    start_date = "2000-01-01"
    end_date = dt.date.today().isoformat()
    url = _build_nika_nav_url(website=website, start_date=start_date, end_date=end_date, page_size=5)
    if url is None:
        return False
    data = _safe_get_json(url, timeout=30)
    return _is_valid_nika_nav_response(data)


def _detect_noavaran_by_nav_api(website: str) -> bool:
    for base_url in _build_base_urls(website):
        url = f"{base_url}/api/v1/site/nav-grid"
        params = {"FundId": 1, "PageNumber": 1, "PageSize": 5, "SortField": "Date", "SortOrder": "desc",
                  "FromDate": "1390/01/01", "ToDate": _today_jalali_str()}
        data = _safe_get_json(url, timeout=30, params=params)
        if _is_valid_noavaran_nav_response(data):
            return True
    return False


def _detect_website_developer(website: str) -> str:
    warnings.filterwarnings('ignore')
    host = _normalize_website_host(website)
    if host is None:
        return "No Address"
    # ---------------------------------------------------------
    # Strict NAV API detection.
    # Order matters only for performance, not logic.
    # ---------------------------------------------------------
    if _detect_tadbirpardaz_by_nav_api(host):
        return "گروه رایانه تدبیر پرداز"
    if _detect_rayan_hamafza_by_nav_api(host):
        return "شرکت رایان هم افزا"
    if _detect_rahkar_by_nav_api(host):
        return "راهکار حامی پرداز"
    if _detect_mabna_by_nav_api(host):
        return "پردازش اطلاعات مالی مبنا"
    if _detect_pikad_by_nav_api(host):
        return "پیکاد"
    if _detect_nika_by_nav_api(host):
        return "سامانه هوشمند نیکا سرمایه"
    if _detect_noavaran_by_nav_api(host):
        return "نوآوران"
    print(website, "Unknown")
    return "Unknown"


# Tadbirpardaz
def _get_daily_navs_per_share_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    fund_id = 1
    website = _get_fund_website_address(fund_name)
    url = f"https://{website}/Chart/TotalNAV?type=getnavtotal&basketId={fund_id}"
    response = requests.get(url, timeout=30, verify=False)
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
    navs['JDate'] = navs['GDate'].apply(_gregorian_to_jalali)
    navs.drop('GDate', axis=1, inplace=True)
    return navs


def _get_leveraged_daily_navs_per_share_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    fund_id = 1
    website = _get_fund_website_address(fund_name)
    url = f"https://{website}/Chart/TotalNAV?type=getnavtotal&basketId={fund_id}"
    response = requests.get(url, timeout=30, verify=False)
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
    navs['JDate'] = navs['GDate'].apply(_gregorian_to_jalali)
    navs.drop('GDate', axis=1, inplace=True)
    return navs


def _get_daily_total_nav_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    website = _get_fund_website_address(fund_name)
    url = f"https://{website}/Chart/CombinationOfFundAssets?type=getnavtotal&basketId=1"
    response = requests.get(url, timeout=30, verify=False)
    response.raise_for_status()
    data = response.json()
    df = pd.json_normalize(data, sep='_')
    total_nav = pd.DataFrame(df[df['name'] == ''].loc[0, 'List'])
    total_nav['x'] = pd.to_datetime(total_nav['x'], format='%m/%d/%Y').dt.date
    total_nav.sort_values('x', ascending=False, inplace=True, ignore_index=True)
    total_nav.columns = ['GDate', 'TotalNAV', 'Unknown']
    total_nav.drop('Unknown', axis=1, inplace=True)
    total_nav['JDate'] = total_nav['GDate'].apply(_gregorian_to_jalali)
    total_nav.drop('GDate', axis=1, inplace=True)
    return total_nav


def _get_daily_asset_allocation_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    fund_id = 1
    website = _get_fund_website_address(fund_name)
    base_url = f"https://{website}/Reports/FundDailyAssetDistribution"
    params = {"basketId": fund_id, "page": 1}
    all_rows = []
    headers = []
    while True:
        # Request the page
        response = requests.get(base_url, params=params, timeout=30, verify=False)
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
    daily_asset_allocation['Date'] = daily_asset_allocation['Date'].apply(_jalali_str_to_date)
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


def _get_daily_navs_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    navs_per_share = _get_daily_navs_per_share_tadbirpardaz(fund_name)
    total_navs = _get_daily_total_nav_tadbirpardaz(fund_name)
    navs = pd.merge(total_navs, navs_per_share, on='JDate', how='inner')
    navs = navs[['JDate', 'Subscription', 'Redemption', 'Statistical', 'TotalNAV']]
    return navs


# Rayan hamafza
def _get_daily_asset_allocation_rayan_hamafza(fund_name: str) -> pd.DataFrame:
    fund_id = 1
    fund_website = _get_fund_website_address(fund_name)
    url = f"https://{fund_website}/api/data/DailyAssetStructure/{fund_id}"
    response = requests.get(url, timeout=30, verify=False)
    response.raise_for_status()
    json_data = response.json()
    daily_asset_allocation = pd.DataFrame(json_data["data"])
    daily_asset_allocation.drop('FundId', inplace=True, axis=1)
    daily_asset_allocation.columns = \
        daily_asset_allocation.columns.map(lambda column: column.replace("Today", "")
                                           .replace("Percent", "s Weight").replace("Amount", "s"))
    daily_asset_allocation.columns = \
        daily_asset_allocation.columns.map(lambda column: column.replace("Cashs", "Cash").
                                           replace("TopFiveStocks", "Upper5%Stocks").replace("Ccds", "CCDs")
                                           .replace('Deposits', 'Bank'))
    daily_asset_allocation['Date'] = daily_asset_allocation['Date'].apply(_jalali_str_to_date)

    daily_asset_allocation = daily_asset_allocation[['Date', 'Stocks', 'Upper5%Stocks', 'Bonds', 'Cash', 'Bank',
                                                     'FundUnits', 'CCDs', 'OtherAssets', 'Stocks Weight',
                                                     'Upper5%Stocks Weight', 'Bonds Weight', 'Cash Weight',
                                                     'Bank Weight', 'FundUnits Weight', 'CCDs Weight',
                                                     'OtherAssets Weight']]
    return daily_asset_allocation


def _get_rayan_hamafza_nav_records(website: str):
    for base_url in _build_base_urls(website):
        candidate_urls = [f"{base_url}/api/v1/public/nav/1", f"{base_url}/api/data/NAV/1",]
        for url in candidate_urls:
            data = _safe_get_json(url, timeout=30)
            if not _is_valid_rayan_hamafza_nav_response(data):
                continue
            if isinstance(data, dict) and isinstance(data.get("data"), list):
                return data["data"]
            if isinstance(data, list):
                return data
    raise ValueError(f"Could not find valid Rayan Hamafza NAV API for website: {website}")


def _get_daily_navs_rayan_hamafza(fund_name: str) -> pd.DataFrame:
    website = _get_fund_website_address(fund_name)
    records = _get_rayan_hamafza_nav_records(website)
    navs = pd.DataFrame(records)
    # Normalize both Rayan formats to one column naming system.
    navs.rename({
            # Newer lower-case format
            "jalaliDate": "JDate", "purchaseNAVPerShare": "PurchaseNAVPerShare", "sellNAVPerShare": "SellNAVPerShare",
            "statisticalNAVPerShare": "StatisticalNAVPerShare", "units": "Units", "nav": "NAV",
            # Older upper-case format
            "JalaliDate": "JDate"}, inplace=True, axis=1)
    required_columns = ["JDate", "PurchaseNAVPerShare", "SellNAVPerShare", "StatisticalNAVPerShare", "Units", "NAV"]
    missing_columns = [column for column in required_columns if column not in navs.columns]
    if missing_columns:
        raise ValueError(f"Rayan Hamafza NAV response is missing these columns: {missing_columns}")
    navs["JDate"] = navs["JDate"].apply(_jalali_str_to_date)
    navs["PurchaseNAVPerShare"] = pd.to_numeric(navs["PurchaseNAVPerShare"], errors="coerce")
    navs["SellNAVPerShare"] = pd.to_numeric(navs["SellNAVPerShare"], errors="coerce")
    navs["StatisticalNAVPerShare"] = pd.to_numeric(navs["StatisticalNAVPerShare"], errors="coerce")
    navs["Units"] = pd.to_numeric(navs["Units"], errors="coerce")
    navs["NAV"] = pd.to_numeric(navs["NAV"], errors="coerce")
    # You want TOTAL NAVs, so multiply per-share NAVs by units.
    navs["Subscription"] = navs["PurchaseNAVPerShare"] * navs["Units"]
    navs["Redemption"] = navs["SellNAVPerShare"] * navs["Units"]
    navs["Statistical"] = navs["StatisticalNAVPerShare"] * navs["Units"]
    navs["TotalNAV"] = navs["NAV"]
    navs = navs[["JDate", "Subscription", "Redemption", "Statistical", "TotalNAV"]]
    return navs


# Mabna
def _get_daily_asset_allocation_mabna(fund_name: str) -> pd.DataFrame:
    fund_website = _get_fund_website_address(fund_name)
    url = f"https://{fund_website}/api/v1/overall/allassetsdaily.json"
    response = requests.get(url, timeout=30, verify=False)
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
    daily_asset_allocation.rename({'تاریخ': 'Date', 'سپرده بانکی': 'Bank', 'سپرده بانکی - نسبت': 'Bank Weight',
                                   'وجه نقد': 'Cash', 'وجه نقد - نسبت': 'Cash Weight',
                                   'سرمایه‌گذاری در اوراق بهادار با درآمد ثابت': 'Bonds',
                                   'سرمایه‌گذاری در اوراق بهادار با درآمد ثابت - نسبت': 'Bonds Weight',
                                   ' سرمایه گذاری در سهام ': 'Stocks', ' سرمایه گذاری در سهام  - نسبت': 'Stocks Weight',
                                   'سایر دارایی‌ها': 'OtherAssets', 'سایر دارایی‌ها - نسبت': 'OtherAssets Weight',
                                   ' پنج سهم با بیشترین وزن ': 'Upper5%Stocks',
                                   ' پنج سهم با بیشترین وزن  - نسبت': 'Upper5%Stocks Weight'}, inplace=True, axis=1)
    daily_asset_allocation['Date'] = daily_asset_allocation['Date'].apply(_jalali_str_to_date)
    daily_asset_allocation = daily_asset_allocation[['Date', 'Stocks', 'Upper5%Stocks', 'Bonds', 'Cash', 'Bank',
                                                     'OtherAssets', 'Stocks Weight', 'Upper5%Stocks Weight',
                                                     'Bonds Weight', 'Cash Weight', 'Bank Weight', 'OtherAssets Weight']]
    return daily_asset_allocation


def _get_daily_navs_mabna(fund_name: str) -> pd.DataFrame:
    website = _get_fund_website_address(fund_name)
    url = (f"https://{website}/api/v2/public/reports/navps?start_date=1997-11-10T08%3A13%3A36.377Z&"
           f"end_date=2026-01-11T08%3A13%3A36.377Z&page=1&size=1000000")
    response = requests.get(url, timeout=30, verify=False)
    navs = pd.DataFrame(response.json()['data'])
    navs['date_time'] = navs['date_time'].apply(lambda dt: pd.to_datetime(dt))
    navs['date_time'] = navs['date_time'].apply(_gregorian_to_jalali)
    navs = navs.iloc[:, [0, 2, 3, 12, 5]].copy()
    navs.columns = ['JDate', 'Subscription', 'Redemption', 'Statistical', 'TotalNAV']
    return navs


def _get_leveraged_daily_navs_mabna(fund_name: str) -> pd.DataFrame:
    portfolio_id = 1
    website = _get_fund_website_address(fund_name)
    url = f"https://{website}/api/v2/public/fund/chart?portfolio_id={portfolio_id}"
    response = requests.get(url, timeout=30, verify=False)
    navs = pd.DataFrame(response.json()['data'])
    navs['date_time'] = pd.to_datetime(navs['date_time']).dt.date
    navs['date_time'] = navs['date_time'].apply(_gregorian_to_jalali)
    navs.rename(columns={'date_time': 'JDate', 'total_unit_count': 'TotalUnits',
                         'purchase_price': 'SubscriptionPerUnit', 'redemption_price': 'RedemptionPerUnit',
                         'common_unit_purchase_price': 'CommonSubscriptionPerUnit',
                         'today_purchase_count': 'TodaySubscriptionsCount', 'today_redeemed_count': 'TodayRedeemsCount',
                         'total_purchase_count': 'TotalSubscriptionsCount', 'total_redeemed_count': 'TotalRedeemedCount',
                         'total_preferred_unit_count': 'TotalPrefferedUnits', 'total_common_unit_count': 'TotalCommonUnits',
                         'statistical_value': 'StatisticalPerUnit'}, inplace=True)
    return navs


# Pikad
def _get_daily_asset_allocation_pikad(fund_name: str) -> pd.DataFrame:
    fund_website = _get_fund_website_address(fund_name)
    url_prefix = PIKAD_URL_PREFIXES[fund_website]
    url = f"https://{url_prefix}.exphoenixfund.com/api/assetallocation/GetFlatDailyAssetAllocationByFilter"
    start_date = dt.datetime(2000, 1, 1).isoformat()
    end_date = dt.datetime.today().isoformat()
    take = 1000000
    page = 1
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*", "Content-Type": "application/json",
               "Referer": f"https://{fund_website}", "Origin": f"https://{fund_website}",}
    payload = {"ReportFilter": {"StartDate": start_date, "EndDate": end_date},
               "OptionalFilter": {"take": take, "page": page, "sort": [{"field": "Date", "dir": "desc"}]}}
    response = requests.post(url, headers=headers, json=payload, timeout=30, verify=False)
    response.raise_for_status()
    daily_asset_allocation = pd.DataFrame(response.json()['Result'])
    daily_asset_allocation.drop(['Id', 'Date', 'Created', 'Total'], inplace=True, axis=1)
    daily_asset_allocation.rename(
        {'JalaliDate': 'Date', 'BankAndCashValue': 'CashAndBank', 'BankAndCashPercent': 'CashAndBank Weight',
         'BondValue': 'Bonds', 'BondPercent': 'Bonds Weight', 'EquityValue': 'Stocks', 'FundValue': 'FundUnits',
         'FundPercent': 'FundUnits Weight', 'EquityPercent': 'Stocks Weight', 'OtherValue': 'OtherAssets',
         'BrokerValue': 'Broker', 'BrokerPercent': 'Broker Weight', 'OtherPercent': 'OtherAssets Weight',
         'TopEquityValue': 'Upper5%Stocks', 'TopEquityPercent': 'Upper5%Stocks Weight',
         'AccountReciveablesValue': 'ReceivableAccounts', 'AccountReciveablesPercent': 'ReceivableAccounts Weight',
         'FuturePeriodsValue': 'FuturePeriods', 'FuturePeriodsPercent': 'FuturePeriods Weight'}, inplace=True, axis=1)
    daily_asset_allocation['Date'] = daily_asset_allocation['Date'].apply(_jalali_str_to_date)
    daily_asset_allocation = daily_asset_allocation[['Date', 'Stocks', 'Upper5%Stocks', 'Bonds', 'CashAndBank', 'FundUnits',
                                                     'Broker', 'FuturePeriods', 'ReceivableAccounts',  'OtherAssets',
                                                     'Stocks Weight', 'Upper5%Stocks Weight', 'Bonds Weight',
                                                     'CashAndBank Weight', 'FundUnits Weight', 'Broker Weight',
                                                     'FuturePeriods Weight', 'ReceivableAccounts Weight',
                                                     'OtherAssets Weight']]
    return daily_asset_allocation


def _get_daily_navs_pikad(fund_name: str) -> pd.DataFrame:
    website = _get_fund_website_address(fund_name)
    url_prefix = PIKAD_URL_PREFIXES[website]
    url = f"https://{url_prefix}.exphoenixfund.com/api/nav/GetNavList"
    start_date = "2000-01-01"
    end_date = dt.date.today().isoformat()
    page_size = 1000000
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*",
               "Content-Type": "application/json", "Referer": f"https://{website}", "Origin": f"https://{website}"}

    payload = {"ReportFilter": {"DateFilter": {"StartDate": start_date, "EndDate": end_date}, "PageIndex": 1,
                                "PageSize": page_size},
               "OptionalFilter": {"take": page_size, "skip": 1, "page": 1, "sort": [{"field": "Date", "dir": "asc"}]},
               "BranchId": 0, "PartyId": 0}
    response = requests.post(url, headers=headers, json=payload, timeout=30, verify=False)
    navs = pd.DataFrame(response.json()['Result'])
    navs = navs.iloc[:, 1:6]
    navs['Date'] = pd.to_datetime(navs['Date']).dt.date
    navs['Date'] = navs['Date'].apply(_gregorian_to_jalali)
    navs.rename({'Date': 'JDate', 'SubscriptionNAV': 'Subscription', 'RedemptionNAV': 'Redemption',
                 'StaticalNAV': 'Statistical', 'NetAssetValue': 'TotalNAV'}, inplace=True, axis=1)
    navs = navs[['JDate', 'Subscription', 'Redemption', 'Statistical', 'TotalNAV']]
    return navs


# Rahkar
def _get_daily_asset_allocation_rahkar(fund_name: str) -> pd.DataFrame:
    mutual_fund_id = 1
    fund_website = _get_fund_website_address(fund_name)
    url = f"https://{fund_website}/api/app/asset/daily-asset-list?MutualFundCompanyID={mutual_fund_id}"
    response = requests.get(url, timeout=30, verify=False)
    daily_asset_allocation = pd.DataFrame(response.json())
    daily_asset_allocation.drop(['rowNum', 'totalRows'], inplace=True, axis=1)
    daily_asset_allocation.rename(
        {'date': 'Date', 'bankDepositKalaAsset': 'CCDs', 'bankDepositKalaAssetPersent': 'CCDs Weight',
         'jointShareAsset': 'Bonds', 'jointShareAssetPersent': 'Bonds Weight', 'shareAsset': 'Stocks',
         'unitMutualFundAsset': 'FundUnits', 'unitMutualFundAssetPersent': 'FundUnits Weight',
         'shareAssetPersent': 'Stocks Weight', 'otherAsset': 'OtherAssets', 'otherAssetPersent': 'OtherAssets Weight',
         'topFiveShareAsset': 'Upper5%Stocks', 'topFiveShareAssetPersent': 'Upper5%Stocks Weight',
         'bankDepositAsset': 'Bank', 'bankDepositAssetPersent': 'Bank Weight', 'bankAsset': 'Cash',
         'bankAssetPersent': 'Cash Weight'}, inplace=True, axis=1)
    daily_asset_allocation['Date'] = daily_asset_allocation['Date'].apply(_jalali_str_to_date)
    daily_asset_allocation = daily_asset_allocation[['Date', 'Stocks', 'Upper5%Stocks', 'Bonds', 'Bank', 'Cash',
                                                     'FundUnits', 'CCDs', 'OtherAssets', 'Stocks Weight',
                                                     'Upper5%Stocks Weight', 'Bonds Weight', 'Bank Weight', 'Cash Weight',
                                                     'FundUnits Weight', 'CCDs Weight', 'OtherAssets Weight']]
    return daily_asset_allocation


def _get_daily_navs_rahkar(fund_name: str) -> pd.DataFrame:
    mutual_fund_id = 1
    fund_website = _get_fund_website_address(fund_name)
    url = f"https://{fund_website}/api/app/nav/nav-list?MutualFundCompanyID={mutual_fund_id}"
    response = requests.get(url, timeout=30, verify=False)
    navs = pd.DataFrame(response.json())
    navs['date'] = navs['date'].apply(_jalali_str_to_date)
    navs = navs.iloc[:, :5].copy()
    navs.columns = ['JDate', 'Subscription', 'Redemption', 'Statistical', 'TotalNAV']
    return navs


# NoAvaran
def _get_noavaran_nav_records(website: str):
    for base_url in _build_base_urls(website):
        url = f"{base_url}/api/v1/site/nav-grid"
        params = {"FundId": 1, "PageNumber": 1, "PageSize": 100000, "SortField": "Date", "SortOrder": "desc",
                  "FromDate": "1390/01/01", "ToDate": _today_jalali_str()}
        data = _safe_get_json(url, timeout=30, params=params)
        if _is_valid_noavaran_nav_response(data):
            return data["content"]
    raise ValueError(f"Could not find valid Noavaran NAV API for website: {website}")


def _get_daily_navs_noavaran(fund_name: str) -> pd.DataFrame:
    fund_website = _get_fund_website_address(fund_name)
    records = _get_noavaran_nav_records(fund_website)
    navs = pd.DataFrame(records)
    required_columns = ["Date", "SubscriptionValue", "RedemptionValue", "StatisticalValue", "TotalQuantity",
                        "NetAssetValue"]
    missing_columns = [column for column in required_columns if column not in navs.columns]
    if missing_columns:
        raise ValueError(f"Noavaran NAV response is missing these columns: {missing_columns}")
    navs["JDate"] = navs["Date"].apply(_jalali_str_to_date)
    navs["SubscriptionValue"] = pd.to_numeric(navs["SubscriptionValue"], errors="coerce")
    navs["RedemptionValue"] = pd.to_numeric(navs["RedemptionValue"], errors="coerce")
    navs["StatisticalValue"] = pd.to_numeric(navs["StatisticalValue"], errors="coerce")
    navs["TotalQuantity"] = pd.to_numeric(navs["TotalQuantity"], errors="coerce")
    navs["NetAssetValue"] = pd.to_numeric(navs["NetAssetValue"], errors="coerce")
    # You want TOTAL NAVs.
    navs["Subscription"] = navs["SubscriptionValue"] * navs["TotalQuantity"]
    navs["Redemption"] = navs["RedemptionValue"] * navs["TotalQuantity"]
    navs["Statistical"] = navs["StatisticalValue"] * navs["TotalQuantity"]
    navs["TotalNAV"] = navs["NetAssetValue"]
    navs = navs[["JDate", "Subscription", "Redemption", "Statistical", "TotalNAV"]]
    return navs


def _get_daily_asset_allocation_noavaran(fund_name: str) -> pd.DataFrame:
    fund_website = _get_fund_website_address(fund_name)
    records = None
    for base_url in _build_base_urls(fund_website):
        url = f"{base_url}/api/v1/site/asset-structure-daily"
        params = {"FundId": 1, "PageNumber": 1, "PageSize": 100000, "SortField": "Date", "SortOrder": "desc",
                  "FromDate": "1390/01/01", "ToDate": _today_jalali_str()}
        data = _safe_get_json(url, timeout=30, params=params)
        if _looks_like_noavaran_asset_allocation(data):
            records = data["content"]
            break
    if records is None:
        raise ValueError(f"Could not find valid Noavaran asset allocation API for {fund_name} | {fund_website}")
    daily_asset_allocation = pd.DataFrame(records)
    daily_asset_allocation.rename({"Date": "Date", "ShareAndWarrantValue": "Stocks",
                                   "ShareAndWarrantPercent": "Stocks Weight", "FiveInstrumentValue": "Upper5%Stocks",
                                   "FiveInstrumentPercent": "Upper5%Stocks Weight", "BondValue": "Bonds",
                                   "BondPercent": "Bonds Weight", "CertificateOfDepositValue": "CDs",
                                   "CertificateOfDepositPercent": "CDs Weight",
                                   "PhysicalCertificateOfDepositValue": "PhysicalCDs",
                                   "PhysicalCertificateOfDepositPercent": "PhysicalCDs Weight",
                                   "BankDepositValue": "Bank", "BankDepositPercent": "Bank Weight",
                                   "UnitMutualFundValue": "FundUnits", "UnitMutualFundPercent": "FundUnits Weight",
                                   "OtherValue": "OtherAssets", "OtherPercent": "OtherAssets Weight"}, inplace=True, axis=1)
    daily_asset_allocation["Date"] = daily_asset_allocation["Date"].apply(_jalali_str_to_date)
    value_columns = ["Stocks", "Upper5%Stocks", "Bonds", "CDs", "PhysicalCDs", "Bank", "FundUnits", "OtherAssets"]
    weight_columns = ["Stocks Weight", "Upper5%Stocks Weight", "Bonds Weight", "CDs Weight", "PhysicalCDs Weight",
                      "Bank Weight", "FundUnits Weight", "OtherAssets Weight"]
    for column in value_columns:
        if column not in daily_asset_allocation.columns:
            daily_asset_allocation[column] = 0
        daily_asset_allocation[column] = pd.to_numeric(daily_asset_allocation[column], errors="coerce").fillna(0)
    for column in weight_columns:
        if column not in daily_asset_allocation.columns:
            daily_asset_allocation[column] = 0
        daily_asset_allocation[column] = pd.to_numeric(daily_asset_allocation[column], errors="coerce").fillna(0)

    daily_asset_allocation = daily_asset_allocation[["Date", "Stocks", "Upper5%Stocks", "Bonds", "CDs", "PhysicalCDs",
                                                     "Bank", "FundUnits", "OtherAssets", "Stocks Weight",
                                                     "Upper5%Stocks Weight", "Bonds Weight", "CDs Weight",
                                                     "PhysicalCDs Weight", "Bank Weight", "FundUnits Weight",
                                                     "OtherAssets Weight"]]
    return daily_asset_allocation


# Nika
def _get_daily_navs_nika(fund_name: str) -> pd.DataFrame:
    fund_website = _get_fund_website_address(fund_name)
    url = _build_nika_nav_url(website=fund_website, start_date="2000-01-01", end_date=dt.date.today().isoformat(),
                              page_size=1000000)
    if url is None:
        raise ValueError(f"Could not build Nika NAV URL for {fund_name} | {fund_website}")
    data = _safe_get_json(url, timeout=30)
    if not _is_valid_nika_nav_response(data):
        raise ValueError(f"Nika NAV response schema is invalid for {fund_name} | {fund_website}")
    navs = pd.DataFrame(data["items"])
    _require_columns(navs,["date", "issuanceNav", "redemptionNav", "nominalNAV", "totalUnit",
                           "redemptionNetAssetValue"],"Nika NAV")
    navs["GDate"] = pd.to_datetime(navs["date"]).dt.date
    navs["JDate"] = navs["GDate"].apply(_gregorian_to_jalali)
    navs["issuanceNav"] = pd.to_numeric(navs["issuanceNav"], errors="coerce")
    navs["redemptionNav"] = pd.to_numeric(navs["redemptionNav"], errors="coerce")
    navs["nominalNAV"] = pd.to_numeric(navs["nominalNAV"], errors="coerce")
    navs["totalUnit"] = pd.to_numeric(navs["totalUnit"], errors="coerce")
    navs["redemptionNetAssetValue"] = pd.to_numeric(navs["redemptionNetAssetValue"], errors="coerce")
    navs["Subscription"] = navs["issuanceNav"] * navs["totalUnit"]
    navs["Redemption"] = navs["redemptionNav"] * navs["totalUnit"]
    navs["Statistical"] = navs["nominalNAV"] * navs["totalUnit"]
    navs["TotalNAV"] = navs["redemptionNetAssetValue"]
    return navs[["JDate", "Subscription", "Redemption", "Statistical", "TotalNAV"]]


def _get_fund_row(fund_name: str, all_funds: pd.DataFrame = None) -> pd.Series:
    if all_funds is None:
        all_funds = get_all_funds(_set_website_developers=False)
    matches = all_funds[all_funds["Name"] == fund_name]
    if matches.empty:
        raise ValueError(f"Fund not found: {fund_name}")
    return matches.iloc[0]


def _autoset_website_developers(all_funds: pd.DataFrame, max_workers: int = 10) -> pd.DataFrame:
    results = {}
    def safe_detect(row):
        address = row.get("WebsiteAddress")
        fund_type = row.get("FundType")
        if pd.isna(address):
            return "No Address"
        if fund_type in NO_PUBLIC_NAV_FUND_TYPES:
            return "No Public NAV"
        return _detect_website_developer(address)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {executor.submit(safe_detect, row): index for index, row in all_funds.iterrows()}
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                result = future.result()
            except:
                result = "Error"
            results[index] = result
    all_funds["WebsiteDeveloper"] = all_funds.index.map(results)
    return all_funds


def _extract_nika_config_from_html(html: str):
    if html is None:
        return None
    # Next.js data often has escaped quotes.
    html = html.replace('\\"', '"')
    def find_value(key: str):
        pattern = rf'"{key}"\s*:\s*"([^"]+)"'
        match = re.search(pattern, html)
        if match:
            return match.group(1)
        return None
    api_path = find_value("apiPath")
    hive_path = find_value("hivePath")
    basket_id = find_value("basketId")
    fund_id = find_value("fundId")
    pam_code = find_value("pamCode")
    if api_path and hive_path and basket_id and fund_id:
        return {"apiPath": api_path.strip("/"), "hivePath": hive_path.strip("/"), "basketId": str(basket_id),
                "fundId": str(fund_id), "pamCode": pam_code}
    return None


@lru_cache(maxsize=1000)
def _get_nika_config_by_host(host: str):
    host = _normalize_website_host(host)
    if host is None:
        return None
    if host in NIKA_MANUAL_CONFIGS:
        return NIKA_MANUAL_CONFIGS[host]
    for base_url in _build_base_urls(host):
        html = _safe_get_text(base_url)
        config = _extract_nika_config_from_html(html)
        if config is not None:
            return config
    return None


def _build_nika_nav_url(website: str, start_date: str, end_date: str, page_size: int = 5):
    host = _normalize_website_host(website)
    if host is None:
        return None
    config = _get_nika_config_by_host(host)
    if config is None:
        return None
    api_path = config["apiPath"].replace("https://", "").replace("http://", "").strip("/")
    hive_path = config["hivePath"].strip("/")
    basket_id = config["basketId"]
    fund_id = config["fundId"]
    return (f"https://{api_path}/{hive_path}/{basket_id}/{fund_id}/Nav?"
            f"FromDate={start_date}&ToDate={end_date}&PageNumber=0&PageSize={page_size}")


# PUBLIC FUNCTIONS
def get_daily_navs(fund_name: str) -> pd.DataFrame:
    """Return daily NAV data for a fund.

    Parameters
    ----------
    fund_name : str
        Exact fund name as returned by get_all_funds().

    Returns
    -------
    pandas.DataFrame
        Daily NAV data for the requested fund.

    Raises
    ------
    ValueError
        If the fund name is invalid or daily NAV data is not available.
    NotImplementedError
        If the fund website provider is not supported.
    """
    all_funds = get_all_funds(_set_website_developers=False)
    fund_row = _get_fund_row(fund_name, all_funds)
    fund_type = fund_row['FundType']
    daily_navs = pd.DataFrame()
    if fund_type in NO_PUBLIC_NAV_FUND_TYPES:
        raise ValueError(f"Fund type does not have daily NAVs: {fund_type}")
    elif fund_name == 'صندوق تثبیت بازار سرمایه':
        raise ValueError(f"Fund does not have daily NAVs: {fund_name}")
    else:
        website_address = fund_row['WebsiteAddress']
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
                daily_navs = _get_leveraged_daily_navs_mabna(fund_name)
            else:
                daily_navs = _get_daily_navs_mabna(fund_name)
        elif website_developer == 'پیکاد':
            daily_navs = _get_daily_navs_pikad(fund_name)
        elif website_developer == 'راهکار حامی پرداز':
            daily_navs = _get_daily_navs_rahkar(fund_name)
        elif website_developer == 'سامانه هوشمند نیکا سرمایه':
            daily_navs = _get_daily_navs_nika(fund_name)
        elif website_developer == 'نوآوران':
            daily_navs = _get_daily_navs_noavaran(fund_name)
        else:
            raise NotImplementedError(f"Website developer is unknown for fund: {fund_name} | website: {website_address}")
    return daily_navs


def get_daily_asset_allocation(fund_name: str) -> pd.DataFrame:
    """Return daily asset-allocation data for a fund.

    Parameters
    ----------
    fund_name : str
        Exact fund name as returned by get_all_funds().

    Returns
    -------
    pandas.DataFrame
        Daily asset-allocation data for the requested fund.

    Raises
    ------
    ValueError
        If the fund name is invalid or asset-allocation data is not available.
    NotImplementedError
        If the fund website provider is not supported.
    """
    all_funds = get_all_funds(_set_website_developers=False)
    fund_row = _get_fund_row(fund_name, all_funds)
    fund_type = fund_row['FundType']
    daily_asset_allocation = pd.DataFrame()
    if fund_type in NO_PUBLIC_NAV_FUND_TYPES:
        raise ValueError(f"Fund type does not have daily asset allocations: {fund_type}")
    elif fund_name == 'صندوق تثبیت بازار سرمایه':
        raise ValueError(f"Fund does not have daily asset allocations: {fund_name}")
    else:
        website_address = fund_row['WebsiteAddress']
        website_developer = _detect_website_developer(website=website_address)
        if website_developer == 'گروه رایانه تدبیر پرداز':
            daily_asset_allocation = _get_daily_asset_allocation_tadbirpardaz(fund_name)
        elif website_developer == 'شرکت رایان هم افزا':
            daily_asset_allocation = _get_daily_asset_allocation_rayan_hamafza(fund_name)
        elif website_developer == 'پردازش اطلاعات مالی مبنا':
            daily_asset_allocation = _get_daily_asset_allocation_mabna(fund_name)
        elif website_developer == 'پیکاد':
            daily_asset_allocation = _get_daily_asset_allocation_pikad(fund_name)
        elif website_developer == 'راهکار حامی پرداز':
            daily_asset_allocation = _get_daily_asset_allocation_rahkar(fund_name)
        elif website_developer == 'نوآوران':
            daily_asset_allocation = _get_daily_asset_allocation_noavaran(fund_name)
        else:
            raise NotImplementedError(f"Website developer is unknown for fund: {fund_name} | website: {website_address}")
    return daily_asset_allocation


def get_all_funds(_set_website_developers: bool = False) -> pd.DataFrame:
    """Return available investment-fund information from Fipiran.

    Returns
    -------
    pandas.DataFrame
        Fund metadata and current fund information.

    Notes
    -----
    This function uses a live external data source, so network or provider
    availability can affect the result.
    """
    url = "https://www.fipiran.ir/services/fund/fundcompare"
    all_funds = pd.DataFrame(requests.get(url, timeout=30, verify=False).json()['items'])
    # all_funds.drop(['rankOf12Month', 'rankOf24Month', 'rankOf36Month', 'rankOf48Month', 'rankOf60Month',
    #                'rankLastUpdate', 'guaranteedEarningRate', 'articlesOfAssociationLink', 'prosoectusLink',
    #                'fundPublisher', 'fundWatch'], inplace=True, axis=1)
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
        lambda g: jd.date.fromgregorian(date=g) if isinstance(g, dt.date) and not pd.isna(g) else None)
    all_funds['UpdateDate'] = pd.to_datetime(all_funds['UpdateDate'], errors="coerce").dt.date
    all_funds['UpdateDate'] = all_funds['UpdateDate'].apply(
        lambda g: jd.date.fromgregorian(date=g) if isinstance(g, dt.date) and not pd.isna(g) else None)
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
    if _set_website_developers:
        all_funds = _autoset_website_developers(all_funds.copy())
    return all_funds
