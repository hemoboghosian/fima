import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from io import StringIO
import jdatetime as jd
import re, json, html, time, requests, threading
from urllib.parse import urljoin, urlparse
from typing import Tuple
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter


_THREAD_LOCAL = threading.local()


def _ifb_clean_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u200c", "")
                  .translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))).strip()


def _ifb_hidden_fields(soup):
    def get(name):
        tag = soup.select_one(f"input[name='{name}']")
        return tag.get("value", "") if tag else ""

    data = {"__VIEWSTATE": get("__VIEWSTATE"), "__VIEWSTATEGENERATOR": get("__VIEWSTATEGENERATOR")}
    event_validation = get("__EVENTVALIDATION")
    if event_validation:
        data["__EVENTVALIDATION"] = event_validation
    return data


def _ifb_mount_adapter(session, pool_size=20):
    adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size, max_retries=0)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _ifb_find_page_size_control(soup, grid_name_part):
    select = soup.select_one(f"div.sizeselector select[name*='{grid_name_part}']")
    return select.get("name") if select else None


def _ifb_best_page_size(soup, grid_name_part, requested=100):
    """Use the largest allowed page size up to requested. Falls back to requested."""
    select = soup.select_one(f"div.sizeselector select[name*='{grid_name_part}']")
    if not select:
        return str(requested)

    values = []
    for option in select.find_all("option"):
        value = _ifb_clean_text(option.get("value") or option.get_text(strip=True))
        if value.isdigit():
            values.append(int(value))

    if not values:
        return str(requested)

    allowed = [v for v in values if v <= requested]
    return str(max(allowed) if allowed else max(values))


def _ifb_set_page_size(session, url, headers, soup, grid_name_part, requested=100,
                       fallback_control_name=None, timeout=30):
    control_name = _ifb_find_page_size_control(soup, grid_name_part) or fallback_control_name
    if not control_name:
        return soup

    page_size = _ifb_best_page_size(soup, grid_name_part, requested=requested)
    payload = {"__EVENTTARGET": control_name, "__EVENTARGUMENT": "", **_ifb_hidden_fields(soup), control_name: page_size,}
    response = session.post(url, headers=headers, data=payload, timeout=timeout)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _ifb_get_grid_page(session, url, headers, soup, grid_unique_id, page, timeout=30):
    payload = {"__EVENTTARGET": grid_unique_id, "__EVENTARGUMENT": f"Page${page}", **_ifb_hidden_fields(soup),}
    response = session.post(url, headers=headers, data=payload, timeout=timeout)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _ifb_collect_grid_rows(url, headers, grid_unique_id, parse_rows_func, page_size_grid_name_part,
                           requested_page_size=100, fallback_page_size_control=None, timeout=30,
                           max_pages=10_000):
    """Sequential pagination is kept because ASP.NET ViewState is stateful.
    The speed gain comes from no artificial sleep and larger page size.
    """
    session = _ifb_mount_adapter(requests.Session(), pool_size=10)

    response = session.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    soup = _ifb_set_page_size(session=session, url=url, headers=headers, soup=soup,
                              grid_name_part=page_size_grid_name_part, requested=requested_page_size,
                              fallback_control_name=fallback_page_size_control, timeout=timeout,)

    all_rows = []
    seen_pages = set()
    page = 1

    while page <= max_pages:
        rows = parse_rows_func(soup)
        if not rows:
            break

        page_signature = tuple(map(tuple, rows))
        if page_signature in seen_pages:
            break
        seen_pages.add(page_signature)
        all_rows.extend(rows)

        page += 1
        soup = _ifb_get_grid_page(session, url, headers, soup, grid_unique_id, page, timeout=timeout)

    return all_rows


def _ifb_parse_jdate(value):
    text = _ifb_clean_text(value)
    parts = re.findall(r"\d+", text)
    if len(parts) < 3:
        return np.nan
    return jd.date(int(parts[0]), int(parts[1]), int(parts[2]))


def _ifb_clean_amount_columns(df, columns):
    for column in columns:
        df[column] = \
            (df[column].astype(str).str.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
             .str.replace("B", "", regex=False).str.replace(",", "", regex=False)
             .str.replace("/", ".", regex=False).str.strip())
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def get_sukuk_daily_trades_based_on_bs() -> pd.DataFrame:
    url = "https://ifb.ir/datareporter/DailySukukTrades.aspx"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": url,
        "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    def parse_rows(soup):
        table = soup.select_one("table[id$='grdDSTs']")
        if not table:
            return []

        output = []
        for tr in table.find_all("tr"):
            if tr.find("th") or "pgr" in (tr.get("class") or []) or tr.find("table"):
                continue
            tds = tr.find_all("td", recursive=False)
            if len(tds) == 12:
                row = [_ifb_clean_text(td.get_text(strip=True)) for td in tds]
                if row[0].replace(",", "").isdigit():
                    output.append(row)
        return output

    rows = _ifb_collect_grid_rows(
        url=url,
        headers=headers,
        grid_unique_id="ctl00$ContentPlaceHolder1$grdDSTs",
        parse_rows_func=parse_rows,
        page_size_grid_name_part="grdDSTs",
        requested_page_size=100,
        fallback_page_size_control="ctl00$ContentPlaceHolder1$grdDSTs$ctl14$ctl13",
        timeout=30,
    )

    raw_columns = [
        "RowIndex", "Date",
        "Buyer: Government", "Buyer: CentralBank", "Buyer: Funds", "Buyer: Banks", "Buyer: Others",
        "Seller: Government", "Seller: CentralBank", "Seller: Funds", "Seller: Banks", "Seller: Others",
    ]
    raw = pd.DataFrame(rows, columns=raw_columns)
    if raw.empty:
        return pd.DataFrame(columns=["Date", "Buyer/Seller", "Government", "CentralBank", "Funds", "Banks", "Others"])

    raw["RowIndex"] = pd.to_numeric(raw["RowIndex"], errors="coerce")
    raw = raw.dropna(subset=["RowIndex"])

    buyer_cols = [col for col in raw.columns if col.startswith("Buyer")]
    seller_cols = [col for col in raw.columns if col.startswith("Seller")]

    buyer = raw[["Date"] + buyer_cols].copy()
    buyer.columns = ["Date"] + [col.split(":", 1)[1].strip() for col in buyer_cols]
    buyer["Buyer/Seller"] = "Buyer"

    seller = raw[["Date"] + seller_cols].copy()
    seller.columns = ["Date"] + [col.split(":", 1)[1].strip() for col in seller_cols]
    seller["Buyer/Seller"] = "Seller"

    result = pd.concat([buyer, seller], ignore_index=True)
    result = result[["Date", "Buyer/Seller", "Government", "CentralBank", "Funds", "Banks", "Others"]]
    result.sort_values("Date", inplace=True, ignore_index=True, ascending=False)
    result["Date"] = result["Date"].apply(_ifb_parse_jdate)
    result = result[result["Date"] != jd.date(1278, 10, 10)].reset_index(drop=True)
    result = _ifb_clean_amount_columns(result, ["Government", "CentralBank", "Funds", "Banks", "Others"])
    return result


def get_sukuk_daily_trades_based_on_ct() -> pd.DataFrame:
    url = "https://ifb.ir/datareporter/DailySukukTrades.aspx"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": url,
        "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    def parse_rows(soup):
        table = soup.select_one("table[id$='grdDSTTypes']")
        if not table:
            return []

        output = []
        for tr in table.find_all("tr"):
            if tr.find("th") or "pgr" in (tr.get("class") or []) or tr.find("table"):
                continue
            tds = tr.find_all("td", recursive=False)
            if len(tds) == 5:
                row = [_ifb_clean_text(td.get_text(strip=True)) for td in tds]
                if row[0].replace(",", "").isdigit():
                    output.append(row)
        return output

    rows = _ifb_collect_grid_rows(
        url=url,
        headers=headers,
        grid_unique_id="ctl00$ContentPlaceHolder1$grdDSTTypes",
        parse_rows_func=parse_rows,
        page_size_grid_name_part="grdDSTs",  # this page-size dropdown controls the DailySukukTrades page
        requested_page_size=100,
        fallback_page_size_control="ctl00$ContentPlaceHolder1$grdDSTs$ctl14$ctl13",
        timeout=30,
    )

    result = pd.DataFrame(rows, columns=["RowIndex", "Date", "OpenMarketOperations", "GovernmentSubscription", "Others"])
    if result.empty:
        return pd.DataFrame(columns=["Date", "OpenMarketOperations", "GovernmentSubscription", "Others"])

    result["RowIndex"] = pd.to_numeric(result["RowIndex"], errors="coerce")
    result = result.dropna(subset=["RowIndex"]).drop(columns="RowIndex")
    result.sort_values("Date", inplace=True, ignore_index=True, ascending=False)
    result["Date"] = result["Date"].apply(_ifb_parse_jdate)
    result = result[result["Date"] != jd.date(1278, 10, 10)].reset_index(drop=True)
    result = _ifb_clean_amount_columns(result, ["OpenMarketOperations", "GovernmentSubscription", "Others"])
    return result


def get_all_crowdfunding_plans(include_descriptions=True, max_workers=8) -> pd.DataFrame:
    url = "https://ifb.ir/Finstars/AllCrowdFundingProject.aspx"
    show_desc = "https://ifb.ir/Finstars/AllCrowdFundingProject.aspx/showDesc"
    grid_unique_id = "ctl00$ContentPlaceHolder1$grdCrowdFundingData"
    table_css = "table[id$='grdCrowdFundingData']"

    base_headers = {"User-Agent": "Mozilla/5.0", "Referer": url}
    post_headers = {**base_headers, "Content-Type": "application/x-www-form-urlencoded"}
    ajax_headers = {
        **base_headers,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://ifb.ir",
    }

    request_session = _ifb_mount_adapter(requests.Session(), pool_size=max_workers + 2)

    def parse_rows(soup):
        table = soup.select_one(table_css)
        if not table:
            return []

        output = []
        for tr in table.find_all("tr"):
            if tr.find("th") or "pgr" in (tr.get("class") or []) or tr.find("table"):
                continue
            tds = tr.find_all("td", recursive=False)
            if len(tds) != 10:
                continue

            row_no = _ifb_clean_text(tds[0].get_text(strip=True))
            if not row_no.replace(",", "").isdigit():
                continue

            a_dom = tds[4].find("a")
            a_desc = tds[8].find("a")
            match = re.search(r"showDesc\('([^']+)'\)", a_desc.get("onclick", "")) if a_desc else None

            output.append({
                "Row": row_no,
                "PlanName": _ifb_clean_text(tds[1].get_text(strip=True)),
                "Company": _ifb_clean_text(tds[2].get_text(strip=True)),
                "NationalID": _ifb_clean_text(tds[3].get_text(strip=True)),
                "Domain": (_clean_domain(a_dom["href"]) if a_dom and a_dom.has_attr("href") else None),
                "Status": _ifb_clean_text(tds[5].get_text(strip=True)),
                "StartDate": _ifb_clean_text(tds[6].get_text(strip=True)),
                "EndDate": _ifb_clean_text(tds[7].get_text(strip=True)),
                "DescriptionID": match.group(1) if match else None,
            })
        return output

    response = request_session.get(url, headers=base_headers, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    soup = _ifb_set_page_size(
        session=request_session,
        url=url,
        headers=post_headers,
        soup=soup,
        grid_name_part="grdCrowdFundingData",
        requested=100,
        timeout=30,
    )

    rows = []
    seen_pages = set()
    page = 1
    while True:
        batch = parse_rows(soup)
        if not batch:
            break

        page_signature = tuple(tuple(item.values()) for item in batch)
        if page_signature in seen_pages:
            break
        seen_pages.add(page_signature)
        rows.extend(batch)

        page += 1
        soup = _ifb_get_grid_page(request_session, url, post_headers, soup, grid_unique_id, page, timeout=30)

    all_crowdfunding_plans = pd.DataFrame(rows)
    if all_crowdfunding_plans.empty:
        return pd.DataFrame()

    # Fetch descriptions AFTER collecting all pages, and do it concurrently.
    if include_descriptions:
        desc_ids = [x for x in all_crowdfunding_plans["DescriptionID"].dropna().astype(str).unique() if x]
        base_cookies = request_session.cookies.copy()

        def html_to_text(value):
            if not value:
                return None
            return BeautifulSoup(value, "html.parser").get_text(" ").strip()

        def get_thread_session():
            session = getattr(_THREAD_LOCAL, "ifb_desc_session", None)
            if session is None:
                session = _ifb_mount_adapter(requests.Session(), pool_size=2)
                session.cookies.update(base_cookies)
                _THREAD_LOCAL.ifb_desc_session = session
            return session

        def fetch_desc(desc_id):
            if not desc_id:
                return desc_id, None

            session = get_thread_session()
            # Keep your original fallback logic, but run it in parallel.
            payloads = ({"id": str(desc_id)}, {"ID": str(desc_id)}, {"ID": int(desc_id)} if str(desc_id).isdigit() else None)
            for payload in payloads:
                if payload is None:
                    continue
                try:
                    response = session.post(show_desc, headers=ajax_headers, data=json.dumps(payload), timeout=30)
                    if response.status_code != 200:
                        continue
                    try:
                        data = response.json()
                        raw = data.get("d", "") if isinstance(data, dict) else data
                    except Exception:
                        raw = response.text
                    raw = (raw or "").strip()
                    if raw:
                        return desc_id, html_to_text(html.unescape(raw))
                except requests.RequestException:
                    continue
            return desc_id, None

        descriptions = {}
        if desc_ids:
            workers = max(1, min(int(max_workers), len(desc_ids)))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                for desc_id, text in executor.map(fetch_desc, desc_ids):
                    descriptions[desc_id] = text
        all_crowdfunding_plans["Description"] = all_crowdfunding_plans["DescriptionID"].astype(str).map(descriptions)
    else:
        all_crowdfunding_plans["Description"] = None

    all_crowdfunding_plans["Row"] = pd.to_numeric(all_crowdfunding_plans["Row"], errors="coerce")
    all_crowdfunding_plans.sort_values("Row", inplace=True, ignore_index=True)
    all_crowdfunding_plans["StartDate"] = all_crowdfunding_plans["StartDate"].apply(_ifb_parse_jdate)
    all_crowdfunding_plans["EndDate"] = all_crowdfunding_plans["EndDate"].apply(_ifb_parse_jdate)
    all_crowdfunding_plans.drop(columns=["Row", "DescriptionID"], inplace=True)

    all_crowdfunding_platforms = get_all_crowdfunding_platforms()
    all_crowdfunding_plans = pd.merge(all_crowdfunding_plans, all_crowdfunding_platforms, on="Domain", how="left")
    all_crowdfunding_plans = all_crowdfunding_plans.iloc[:, :-4]
    all_crowdfunding_plans.rename(columns={"Status_x": "Status"}, inplace=True)
    return all_crowdfunding_plans


def _clean_domain(url: str) -> str:
    parsed = urlparse(url.strip().lower())
    return parsed.netloc.replace("www.", "")


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


def get_all_crowdfunding_platforms():
    base = "https://ifb.ir"
    url = "https://ifb.ir/Finstars/AllCrowdFundingAgents.aspx"
    page_size = 100
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}

    r1 = session.get(url, headers=headers, timeout=30)
    r1.encoding = "utf-8"
    soup = BeautifulSoup(r1.text, "html.parser")

    def hidden_values(name):
        el = soup.find("input", attrs={"name": name})
        return el["value"] if el and el.has_attr("value") else ""

    hidden = {"__VIEWSTATE": hidden_values("__VIEWSTATE"), "__VIEWSTATEGENERATOR": hidden_values("__VIEWSTATEGENERATOR"),
              "__EVENTVALIDATION": hidden_values("__EVENTVALIDATION")}

    # Find the dropdown "page size" control name
    size_select = soup.select_one("select[name*='grdCrowdFundingData'][name$='ctl03']")
    if not size_select:
        raise RuntimeError("Could not find page size dropdown in the HTML.")
    size_name = size_select["name"]

    payload = {"__EVENTTARGET": size_name, "__EVENTARGUMENT": "", **hidden, str(size_name): str(page_size)}

    r2 = session.post(url, data=payload, headers=headers, timeout=30)
    r2.encoding = "utf-8"
    soup = BeautifulSoup(r2.text, "html.parser")

    table = soup.find("table", id=lambda x: x and x.endswith("grdCrowdFundingData"))
    if not table:
        raise RuntimeError("Crowdfunding table not found after POST.")

    rows = table.find_all("tr")
    all_crowdfunding_platforms = []

    for i, tr in enumerate(rows, start=1):
        tds = tr.find_all("td")
        if len(tds) < 9:
            continue
        platform = tds[1].get_text(strip=True)
        operator = tds[2].get_text(strip=True)
        inst = tds[3].get_text(strip=True)
        start_date = tds[4].get_text(strip=True)
        exp_date = tds[5].get_text(strip=True)
        status = tds[6].get_text(strip=True)
        phone = tds[7].get_text(strip=True)
        a_dom = tds[8].find("a")
        domain_url = (urljoin(base, a_dom["href"]) if a_dom and a_dom.has_attr("href") else "").lower()
        # a_file = tds[8].find("a")
        # file_url = urljoin(base, a_file["href"]) if a_file and a_file.has_attr("href") else ""

        all_crowdfunding_platforms.append({"Platform": platform, "Operator": operator, "Institute": inst,
                                           "ActivityStartDate": start_date, "LicenseExpiryDate": exp_date,
                                           "Status": status, "PhoneNumber": phone, "Domain": domain_url})

    all_crowdfunding_platforms = pd.DataFrame(all_crowdfunding_platforms)

    all_crowdfunding_platforms['ActivityStartDate'] = \
        all_crowdfunding_platforms['ActivityStartDate'].apply(lambda date_str:
                                                              jd.date(year=int(date_str.split('-')[0]),
                                                                      month=int(date_str.split('-')[1]),
                                                                      day=int(date_str.split('-')[2])))
    all_crowdfunding_platforms['LicenseExpiryDate'] = \
        all_crowdfunding_platforms['LicenseExpiryDate'].apply(lambda date_str:
                                                              jd.date(year=int(date_str.split('-')[0]),
                                                                      month=int(date_str.split('-')[1]),
                                                                      day=int(date_str.split('-')[2])))

    all_crowdfunding_platforms["Domain"] = (all_crowdfunding_platforms["Domain"].apply(lambda domain: _clean_domain(domain)))

    return all_crowdfunding_platforms


def get_all_standard_financing_instruments() -> pd.DataFrame:
    url = "https://ifb.ir/MFI/FinancialInstrument.aspx"
    grid_unique_id = "ctl00$ContentPlaceHolder1$grdFinancialData"
    table_css = "table[id$='grdFinancialData']"

    page_size_value = "50"
    base_headers = {"User-Agent": "Mozilla/5.0", "Referer": url}
    post_headers = {**base_headers, "Content-Type": "application/x-www-form-urlencoded"}

    request_session = requests.Session()


    def p2l(s: str) -> str:
        if s is None:
            return s
        return re.sub(r"\s+", " ", str(s)).strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))


    def to_int(x):
        if x is None:
            return None
        x = p2l(x).replace(",", "")
        return int(x) if re.fullmatch(r"\d+", x) else None


    def to_pct(x):
        if x is None:
            return None
        x = p2l(x).replace("%", "").strip()
        try:
            return float(x)
        except:
            return None


    def extract_hidden_fields(hf_soup):
        def v(name):
            el = hf_soup.select_one(f"input[name='{name}']")
            return el["value"] if el and el.has_attr("value") else None
        data = {"__VIEWSTATE": v("__VIEWSTATE"), "__VIEWSTATEGENERATOR": v("__VIEWSTATEGENERATOR")}
        ev = v("__EVENTVALIDATION")
        if ev:
            data["__EVENTVALIDATION"] = ev
        return data


    def find_pagesize_control_name(fpscn_soup):
        sel = fpscn_soup.select_one("div.sizeselector select[name*='grdFinancialData']")
        return sel.get("name") if sel else None


    def set_page_size(sps_soup, size_value):
        name = find_pagesize_control_name(sps_soup)
        if not name:
            return sps_soup
        sps_payload = {"__EVENTTARGET": name, "__EVENTARGUMENT": "", **extract_hidden_fields(sps_soup), name: str(size_value)}
        r = request_session.post(url, headers=post_headers, data=sps_payload, timeout=30)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")


    def parse_rows(pr_soup):
        table = pr_soup.select_one(table_css)
        if not table:
            return []

        tbody = table.find("tbody")
        tr_list = (tbody.find_all("tr", recursive=False) if tbody else table.find_all("tr", recursive=False))

        out = []
        for tr in tr_list:
            # skip header rows, pager container row, and any row that contains a nested table (pager inner table)
            if tr.find("th") or "pgr" in (tr.get("class") or []) or tr.find("table"):
                continue

            tds = tr.find_all("td", recursive=False)
            if len(tds) < 11:
                continue

            # first cell must be a digit row index
            first_text = p2l(tds[0].get_text(strip=True))
            if not re.fullmatch(r"\d+", first_text):
                continue

            # نماد + detail link
            a = tds[1].find("a")
            symbol = p2l(a.get_text(strip=True) if a else tds[1].get_text(strip=True))
            href = (a.get("href") if a else "") or ""
            detail_url = None if href.lower().startswith("javascript:") else (urljoin(url, href) if href else None)
            ticker_id = detail_url[-5:]
            issue_date_list = p2l(tds[6].get_text()).split('-')
            issue_date = jd.date(year=int(issue_date_list[0]), month=int(issue_date_list[1]), day=int(issue_date_list[2]))

            out.append({"Row": to_int(first_text), "Ticker": symbol, "TickerID": ticker_id, "DetailURL": detail_url,
                        "IssueVolume": to_int(tds[2].get_text()), "AcceptVolume": to_int(tds[3].get_text()),
                        "ParValue": to_int(tds[4].get_text()), "CouponPercent": to_pct(tds[5].get_text()),
                        "IssueDate": issue_date, "MarketMaker": p2l(tds[7].get_text()),
                        "MarketMakingMethod": p2l(tds[8].get_text()), "VolatilityRange": p2l(tds[9].get_text())})
        return out

    request_session.get(url, headers=base_headers, timeout=30)
    r0 = request_session.get(url, headers=base_headers, timeout=30)
    r0.raise_for_status()
    soup = BeautifulSoup(r0.text, "html.parser")
    soup = set_page_size(soup, page_size_value)

    rows, seen = [], set()
    page = 1
    while True:
        if page > 1:
            payload = {"__EVENTTARGET": grid_unique_id, "__EVENTARGUMENT": f"Page${page}", **extract_hidden_fields(soup)}
            rp = request_session.post(url, headers=post_headers, data=payload, timeout=30)
            soup = BeautifulSoup(rp.text, "html.parser")
            time.sleep(0.15)

        batch = parse_rows(soup)
        if not batch:
            break  # nothing parsed on this page; end

        # guard against accidental repeats
        sig = tuple(tuple(x.values()) for x in batch)
        if sig in seen:
            break
        seen.add(sig)

        rows.extend(batch)
        page += 1

    all_standard_financing_instruments = pd.DataFrame(rows)
    if not all_standard_financing_instruments.empty:
        all_standard_financing_instruments["Row"] = \
            pd.to_numeric(all_standard_financing_instruments["Row"], errors="coerce").astype("Int64")
        all_standard_financing_instruments = \
            all_standard_financing_instruments.sort_values("Row").reset_index(drop=True)
        all_standard_financing_instruments.drop(columns='Row', inplace=True)
    return all_standard_financing_instruments


def get_ticker_info(ticker: str) -> Tuple[pd.DataFrame, pd.DataFrame]:

    all_standard_financing_instruments = get_all_standard_financing_instruments()
    all_special_financing_instruments = get_all_special_financing_instruments()
    all_financing_instruments = pd.concat([all_standard_financing_instruments, all_special_financing_instruments], ignore_index=True)
    all_financing_instruments.drop_duplicates(subset=["TickerID"], inplace=True, ignore_index=True)

    if ticker in all_financing_instruments['Ticker'].values:
        ticker_details_urls = all_financing_instruments[all_financing_instruments['Ticker'] == ticker]
        if len(ticker_details_urls) > 1:
            print('There are more of one record for the ticker you entered. Check the website and try again.')
            return None, None
        else:
            ticker_details_url = all_financing_instruments[all_financing_instruments['Ticker'] == ticker].iloc[0]['DetailURL']
    else:
        print('You entered a wrong ticker. Try again with a correct one.')
        return None, None

    # grids / selectors on this page
    pb_grid_unique_id = "ctl00$ContentPlaceHolder1$grdPBs"
    pb_table_css = "table[id$='grdPBs']"
    # Page-size control observed on your screenshot: ctl00$ContentPlaceHolder1$grdPBs$ctl13$ctl04
    # We'll auto-detect it in case it shifts.
    page_size_value = "50"

    base_headers = {"User-Agent": "Mozilla/5.0", "Referer": ticker_details_url}
    post_headers = {**base_headers, "Content-Type": "application/x-www-form-urlencoded"}
    session = requests.Session()


    def p2l(s: str) -> str:
        if s is None: return s
        return re.sub(r"\s+", " ", str(s)).strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))


    def to_amount(s: str):
        """'58,602/74' or '1,000,000' -> float"""
        if not s: return None
        s = p2l(s).replace(",", "").replace("/", ".")
        try: return float(s)
        except ValueError: return None


    def extract_hidden_fields(hf_soup):
        def val(name):
            el = hf_soup.select_one(f"input[name='{name}']")
            return el["value"] if el and el.has_attr("value") else None
        data = {"__VIEWSTATE": val("__VIEWSTATE"),
                "__VIEWSTATEGENERATOR": val("__VIEWSTATEGENERATOR")}
        ev = val("__EVENTVALIDATION")
        if ev: data["__EVENTVALIDATION"] = ev
        return data


    def find_pagesize_control_name(pscn_soup, grid_suffix="grdPBs"):
        sel = pscn_soup.select_one(f"div.sizeselector select[name*='{grid_suffix}']")
        return sel.get("name") if sel else None


    def set_page_size(ps_soup, size_value):
        name = find_pagesize_control_name(ps_soup, "grdPBs")
        if not name:
            return ps_soup
        ps_payload = {"__EVENTTARGET": name, "__EVENTARGUMENT": "",
                   **extract_hidden_fields(ps_soup), name: str(size_value)}
        r = session.post(ticker_details_url, headers=post_headers, data=ps_payload, timeout=30)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")


    def parse_info_tables(it_soup):
        """All key/value pairs from all .insTable blocks, with section titles."""
        out = []
        for panel in it_soup.select("div.subpanel"):
            section = p2l((panel.select_one(".panelheader label") or {}).get_text(strip=True) if panel.select_one(".panelheader label") else "")
            if section in ["", "اطلاعات ارکان"]:
                continue  # exclude this section
            for tbl in panel.select("table.insTable"):
                for tr in tbl.select("tr"):
                    tds = tr.find_all("td")
                    if len(tds) < 2: continue
                    label = p2l(tds[0].get_text())
                    value = p2l(tds[1].get_text())
                    if label or value:
                        out.append({"Section": section, "Label": label, "Value": value})
        return out


    def parse_payments_page(pp_soup):
        """One page of grdPBs -> list of dicts."""
        table = pp_soup.select_one(pb_table_css)
        if not table: return []
        tbody = table.find("tbody") or table
        rows = []
        for tr in tbody.find_all("tr", recursive=False):
            if tr.find("th") or "pgr" in (tr.get("class") or []) or tr.find("table"):
                continue
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 2:
                continue
            payment_date_list = p2l(tds[0].get_text()).split('/')
            payment_date = jd.date(year=int(payment_date_list[0]), month=int(payment_date_list[1]), day=int(payment_date_list[2]))
            payment_amount_per_unit = to_amount(tds[1].get_text())
            rows.append({"PaymentDate": payment_date, "PaymentAmountPerUnit": payment_amount_per_unit})
        return rows


    session.get(ticker_details_url, headers=base_headers, timeout=30)
    r0 = session.get(ticker_details_url, headers=base_headers, timeout=30)
    r0.raise_for_status()
    soup = BeautifulSoup(r0.text, "html.parser")

    # 1) Info tables
    info_rows = parse_info_tables(soup)

    # 2) Payments grid: set page size to 50 (if selector exists) and iterate pages
    soup = set_page_size(soup, page_size_value)

    # pager: read last page number (might be only 1)
    def get_last_page(s):
        pager_tr = s.select_one("table[id$='grdPBs'] tr.pgr")
        if not pager_tr: return 1
        nums = []
        for td in pager_tr.find_all("td"):
            t = p2l(td.get_text(strip=True)).replace("...", "")
            if t.isdigit():
                nums.append(int(t))
        return max(nums) if nums else 1

    total_pages = get_last_page(soup)
    payments_rows, page = [], 1
    seen = set()

    while page <= total_pages:
        if page > 1:
            payload = {"__EVENTTARGET": pb_grid_unique_id,
                       "__EVENTARGUMENT": f"Page${page}",
                       **extract_hidden_fields(soup)}
            rp = session.post(ticker_details_url, headers=post_headers, data=payload, timeout=30)
            soup = BeautifulSoup(rp.text, "html.parser")
            time.sleep(0.12)

        batch = parse_payments_page(soup)
        if not batch:
            break
        sig = tuple(tuple(x.values()) for x in batch)
        if sig in seen:
            break
        seen.add(sig)

        payments_rows.extend(batch)
        page += 1

    ticker_info = pd.DataFrame(info_rows)
    ticker_info['Label'] = ticker_info['Label'].apply(lambda label: label.replace(":", ""))
    ticker_info.sort_values('Section', inplace=True, ignore_index=True)

    ticker_payments = pd.DataFrame(payments_rows)
    if not ticker_payments.empty:
        ticker_payments.sort_values(["PaymentDate", 'PaymentAmountPerUnit'], inplace=True, ignore_index=True)

    return ticker_info, ticker_payments


def get_all_special_financing_instruments() -> pd.DataFrame:

    url = "https://ifb.ir/MFI/QualifiedMFI.aspx"
    grid_unique_id = "ctl00$ContentPlaceHolder1$grdFinancialData"
    table_css = "table[id$='grdFinancialData']"

    page_size_value = "50"
    base_headers = {"User-Agent": "Mozilla/5.0", "Referer": url}
    post_headers = {**base_headers, "Content-Type": "application/x-www-form-urlencoded"}

    session = requests.Session()


    def p2l(s: str) -> str:
        if s is None:
            return s
        return re.sub(r"\s+", " ", str(s)).strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))


    def to_int(x):
        if x is None:
            return None
        x = p2l(x).replace(",", "")
        return int(x) if re.fullmatch(r"\d+", x) else None


    def extract_hidden_fields(hf_soup):
        def val(name):
            el = hf_soup.select_one(f"input[name='{name}']")
            return el["value"] if el and el.has_attr("value") else None
        data = {"__VIEWSTATE": val("__VIEWSTATE"), "__VIEWSTATEGENERATOR": val("__VIEWSTATEGENERATOR")}
        ev = val("__EVENTVALIDATION")
        if ev:
            data["__EVENTVALIDATION"] = ev
        return data


    def find_pagesize_control_name(fpscn_soup):
        sel = fpscn_soup.select_one("div.sizeselector select[name*='grdFinancialData']")
        return sel.get("name") if sel else None


    def set_page_size(sps_soup, size_value):
        name = find_pagesize_control_name(sps_soup)
        if not name:
            return sps_soup
        sps_payload = {"__EVENTTARGET": name, "__EVENTARGUMENT": "", **extract_hidden_fields(sps_soup), name: str(size_value)}
        r = session.post(url, headers=post_headers, data=sps_payload, timeout=30)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")


    def parse_rows(pr_soup):
        table = pr_soup.select_one(table_css)
        if not table:
            return []
        tbody = table.find("tbody") or table
        rows_out = []
        for tr in tbody.find_all("tr", recursive=False):
            # skip header / pager rows and any row with nested table (pager inner table)
            if tr.find("th") or "pgr" in (tr.get("class") or []) or tr.find("table"):
                continue
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 10:
                continue

            # guard: first cell should be a number
            row_txt = p2l(tds[0].get_text())
            if not re.fullmatch(r"\d+", row_txt):
                continue

            # Symbol + link
            a = tds[1].find("a")
            ticker = p2l(a.get_text(strip=True) if a else tds[1].get_text(strip=True))
            href = (a.get("href") if a else "") or ""
            detail_url = urljoin(url, href) if href and not href.lower().startswith("javascript:") else None
            ticker_id = detail_url[-5:]
            coupon_type = p2l(tds[5].get_text())
            market_maker = p2l(tds[7].get_text())
            description = p2l(tds[8].get_text()) or None
            issue_date_list = p2l(tds[6].get_text()).split('-')
            issue_date = jd.date(year=int(issue_date_list[0]), month=int(issue_date_list[1]),
                                 day=int(issue_date_list[2]))

            rows_out.append({"Row": to_int(row_txt), "Ticker": ticker, "TickerID": ticker_id, "DetailURL": detail_url,
                             "IssueVolume": to_int(tds[2].get_text()), "AcceptVolume": to_int(tds[3].get_text()),
                             "ParValue": to_int(tds[4].get_text()), "NominalCouponType": coupon_type,
                             "IssueDate": issue_date, "MarketMaker": market_maker, "Description": description})

        return rows_out


    session.get(url, headers=base_headers, timeout=30)
    r0 = session.get(url, headers=base_headers, timeout=30)
    r0.raise_for_status()
    soup = BeautifulSoup(r0.text, "html.parser")
    soup = set_page_size(soup, page_size_value)


    def get_last_page(s):
        pager_tr = s.select_one("table[id$='grdFinancialData'] tr.pgr")
        if not pager_tr:
            return 1
        nums = []
        for td in pager_tr.find_all("td"):
            t = p2l(td.get_text(strip=True)).replace("...", "")
            if t.isdigit():
                nums.append(int(t))
        return max(nums) if nums else 1

    total_pages = get_last_page(soup)

    rows, page, seen = [], 1, set()
    while page <= total_pages:
        if page > 1:
            payload = {"__EVENTTARGET": grid_unique_id, "__EVENTARGUMENT": f"Page${page}", **extract_hidden_fields(soup)}
            rp = session.post(url, headers=post_headers, data=payload, timeout=30)
            rp.raise_for_status()
            soup = BeautifulSoup(rp.text, "html.parser")
            time.sleep(0.12)

        batch = parse_rows(soup)
        if not batch:
            break
        sig = tuple(tuple(x.values()) for x in batch)
        if sig in seen:
            break
        seen.add(sig)

        rows.extend(batch)
        page += 1

    all_special_financing_instruments = pd.DataFrame(rows)
    if not all_special_financing_instruments.empty:
        all_special_financing_instruments["Row"] = \
            pd.to_numeric(all_special_financing_instruments["Row"], errors="coerce").astype("Int64")
        all_special_financing_instruments = \
            all_special_financing_instruments.sort_values("Row").reset_index(drop=True)
        all_special_financing_instruments.drop(columns='Row', inplace=True)
    return all_special_financing_instruments