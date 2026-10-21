import requests
import pandas as pd
import jdatetime as jd
import datetime as dt
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import re
from email.utils import parsedate_to_datetime
from contextvars import ContextVar
from numbers import Integral, Real
from copy import deepcopy
from ._data import boolean_series, identifier_series, jalali_date, number_series, gregorian_series, text_or_na

__all__ = ["get_all_funds", "get_daily_navs", "get_daily_asset_allocation",
           "get_tsetmc_funds", "get_tsetmc_fund_details", "get_tsetmc_fund_types"]


def _column_name(name):
    name = name.replace("Upper5%Stocks", "TopFiveStocks").replace("Upper5%Bonds", "TopFiveBonds")
    return "".join(part[0].upper() + part[1:] for part in re.split(r"[ _]+", name) if part)


def _nav_frame(frame):
    names = {"JDate": "JalaliDate", "Subscription": "SubscriptionNAV",
             "Redemption": "RedemptionNAV", "Statistical": "StatisticalNAV",
             "SubscriptionPerUnit": "SubscriptionNAV", "RedemptionPerUnit": "RedemptionNAV",
             "StatisticalPerUnit": "StatisticalNAV", "CommonSubscriptionPerUnit": "OrdinarySubscriptionNAV",
             "SpecialSubscription": "PreferredSubscriptionNAV", "SpecialRedemption": "PreferredRedemptionNAV",
             "SpecialStatistical": "PreferredStatisticalNAV", "TotalPrefferedUnits": "TotalPreferredUnits",
             "total_net_asset_value_with_buy_commission_and_discount": "TotalSubscriptionNAV",
             "total_net_asset_value_with_sell_commission_and_discount": "TotalRedemptionNAV"}
    result = frame.rename(columns={c: names.get(c, _column_name(c)) for c in frame}).copy()
    result["JalaliDate"] = result["JalaliDate"].map(jalali_date)
    for column in result:
        if column != "JalaliDate" and (column.endswith(("NAV", "Units", "Count", "Amount", "Ratio", "Factor"))
                                        or column == "Common"):
            result[column] = number_series(result[column])
    return result


def _allocation_frame(frame):
    result = frame.copy()
    # Unrecognized provider labels remain opaque metadata instead of guessed
    # translations or non-English public column names.
    unknown = [c for c in result if not c.isascii() and not c.endswith(" Weight")]
    if unknown:
        result["ProviderAssets"] = [{name: {"Value": row[name], "Weight": row.get(name + " Weight")}
                                     for name in unknown if pd.notna(row[name])}
                                    for _, row in result.iterrows()]
        result.drop(columns=[c for c in result if not c.isascii()], inplace=True)
    result.rename(columns={c: "JalaliDate" if c == "Date" else _column_name(c) for c in result}, inplace=True)
    result["JalaliDate"] = result["JalaliDate"].map(jalali_date)
    for column in result:
        if column not in ("JalaliDate", "ProviderAssets"):
            result[column] = number_series(result[column])
    return result


def _catalog_frame(frame):
    names = {"RegNo": "RegistrationNumber", "InceptionDate": "InceptionJalaliDate",
             "UpdateDate": "UpdateJalaliDate", "DividendFrequency (Month)": "DividendFrequencyMonths",
             "Others Weight": "OtherAssetsWeight", "Bank CDs Weight": "DepositWeight",
             "StatisticalNav": "StatisticalNAV"}
    result = frame.rename(columns={c: names.get(c, _column_name(c)) for c in frame}).copy()
    for column in result:
        if column == "IsCompleted":
            result[column] = boolean_series(result[column])
        elif column in ("RegistrationNumber", "InstrumentCode", "GroupId", "FundTypeID") or column.endswith(("SeoRegisterNo", "SeoRegisterNumber")):
            result[column] = identifier_series(result[column])
        elif column.endswith("JalaliDate"):
            result[column] = result[column].map(jalali_date)
        elif column == "RankLastUpdate":
            result[column] = result[column].map(lambda value: pd.to_datetime(value, errors="coerce"))
        elif (column.endswith(("Weight", "Return", "NAV")) or column in
              {"Units", "DividendFrequencyMonths", "ReturnFromInception", "EstimatedReturn", "GuaranteedEarningRate"}):
            result[column] = number_series(result[column])
        elif column in ("LiquidityGuarantor", "FundName", "WebsiteAddress"):
            result[column] = result[column].map(text_or_na)
    return result


_TSETMC_FUND_NAMES = {
    "regNo": "RegistrationNumber", "mfName": "FundName", "mfNameEng": "FundEnglishName",
    "name": "ProviderName", "nameEN": "ProviderNameEN", "fixIncome": "FundTypeID",
    "fundType": "ProviderFundTypeCode", "fundSize": "ProviderFundSize",
    "recordDate": "UpdateGregorianDate", "initiationDate": "InceptionGregorianDate",
    "navSub": "SubscriptionNAV", "navRed": "RedemptionNAV", "navStat": "StatisticalNAV",
    "netAsset": "TotalNAV", "portfolioFiveBest": "TopFiveStocksWeight",
    "portfolioStock": "StocksWeight", "portfolioBond": "BondsWeight",
    "portfolioDeposit": "DepositWeight", "portfolioOther": "OtherAssetsWeight",
    "portfolioCash": "CashWeight", "dividentIntervalPeriod": "DividendFrequencyMonths",
    "day1Return": "DailyReturn", "day7Return": "WeeklyReturn", "day30Return": "MonthlyReturn",
    "day90Return": "QuarterlyReturn", "day180Return": "SemiAnnualReturn",
    "day365Return": "AnnualReturn", "dayFirstReturn": "ReturnFromInception",
    "units": "Units", "custodian": "Custodian", "custodianEN": "CustodianEN",
    "guarantor": "Guarantor", "guarantorEN": "GuarantorEN",
    "manager": "Manager", "managerEN": "ManagerEN",
    "investmentManager": "InvestmentManager", "investmentManagerEN": "InvestmentManagerEN",
    "marketMaker": "MarketMaker", "marketMakerEN": "MarketMakerEN",
    "auditor": "Auditor", "auditorEN": "AuditorEN",
    "webSite": "WebSite", "webSiteEN": "WebSiteEN",
    "guaranteedEarningRate": "GuaranteedEarningRate",
    "estimatedEarningRate": "EstimatedEarningRate",
}

# The official NAV chart uses these five fields. Other nested record types do
# not inherit this mapping merely because their source keys look similar.
_TSETMC_NAV_NAMES = {key: _TSETMC_FUND_NAMES[key] for key in
                    ("recordDate", "navSub", "navRed", "navStat", "netAsset")}


def _tsetmc_named_fields(record, names):
    result, metadata = {}, {}
    for key, value in record.items():
        if key in names and not isinstance(value, (dict, list)):
            result[names[key]] = deepcopy(value)
        else:
            metadata[key] = deepcopy(value)
    if metadata:
        result["ProviderMetadata"] = metadata
    return result


def _tsetmc_fund_object(record):
    result = _tsetmc_named_fields({k: v for k, v in record.items() if k != "stats"},
                                 _TSETMC_FUND_NAMES)
    if "stats" in record:
        history = record["stats"]
        if history is not None and (not isinstance(history, list)
                                    or any(not isinstance(row, dict) for row in history)):
            raise ValueError("Invalid TSETMC fund stats: expected a list of NAV records or null")
        result["Stats"] = (None if history is None else
                           [_tsetmc_named_fields(row, _TSETMC_NAV_NAMES) for row in history])
    return result


def _tsetmc_fund_frame(records):
    result = pd.DataFrame([_tsetmc_fund_object(record) for record in records])
    for column in result:
        if column in ("RegistrationNumber", "FundTypeID", "ProviderFundTypeCode"):
            result[column] = identifier_series(result[column])
        elif column.endswith("GregorianDate"):
            result[column] = gregorian_series(result[column])
        elif (column.endswith(("NAV", "Weight", "Return", "Percent", "No")) or column in
              {"Units", "UnitsSub", "UnitsRed", "DividendFrequencyMonths", "ReturnFromInception",
               "EstimatedEarningRate", "GuaranteedEarningRate", "ProviderFundSize"}):
            result[column] = number_series(result[column])
    return result


def __dir__():
    """Present the public Funds API to runtime module discovery."""
    return sorted(__all__)


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


NO_PUBLIC_NAV_FUND_TYPES = {"جسورانه", "زمین و ساختمان", "خصوصی", "پروژه‌ای"}
_fund_request_context = ContextVar("fund_request_context", default=None)

# Official migrations independently verified against public SEO registrations.
# Vista's manager links the replacement at vistaamc.ir/products/behinkhodro;
# Agah's replacement publishes registration 12093 and its original instrument.
_OFFICIAL_FUND_WEBSITES = {
    ("12093", "petroagahfund.ir"): "agahsectorfund.ir",
    ("12168", "vistakhodro.ir"): "vistasectorfund.ir",
}

# Labels/selectors verified against TSETMC's public fund menu.
_TSETMC_FUND_TYPES = (
    (6, "سهامی", "equity"), (7, "مختلط", "mixed"),
    (4, "درآمد ثابت", "fixed_income"), (11, "بازارگردانی", "market_maker"),
    (12, "جسورانه", "venture_capital"), (14, "زمین و ساختمان", "real_estate"),
    (13, "پروژه", "project"), (5, "کالایی", "commodity"),
    (16, "خصوصی", "private"), (17, "صندوق", "fund"),
)


def _fund_label(name):
    name = str(name).translate(str.maketrans({"ي": "ی", "ك": "ک"})).strip()
    name = re.sub(r"^صندوق\s+(?:سرمایه[\s\u200c]*گذاری\s+|س\.?\s+)", "", name)
    name = re.sub(r"^صندوق\s+", "", name)
    # Aghigh's verified provider name changed from مشترک to قابل معامله.
    name = re.sub(r"^(?:مشترک|قابل\s+معامله)\s+", "", name)
    name = re.sub(r"^(?:در\s+اوراق\s+بهادار\s+)?(?:با\s*)?در\s*آمد\s+ثابت\s+", "", name)
    name = re.sub(r"^اختصاصی\s+(?=بازار\s*گردانی)", "", name)
    return re.sub(r"\s|\u200c", "", name)


def _select_fund_id(items, id_key, name_key, provider):
    context = _fund_request_context.get()
    row = context["row"]
    name = _fund_label(row["FundName"])
    ticker = row.get("Ticker")
    matches, aliases, ticker_matches = set(), set(), set()
    for item in items:
        if not isinstance(item, dict) or name_key not in item or id_key not in item:
            raise ValueError(f"Invalid {provider} fund identity response")
        label = str(item[name_key])
        base_name = re.sub(r"\([^()]*\)\s*$", "", label)
        tickers = re.findall(r"\(([^()]*)\)", label)
        if _fund_label(label) == name:
            matches.add(str(item[id_key]))
        elif _fund_label(base_name) == name:
            aliases.add(str(item[id_key]))
        elif (isinstance(ticker, str) and ticker.strip()
                and (_fund_label(ticker) == _fund_label(label)
                     or any(_fund_label(ticker) == _fund_label(t) for t in tickers))):
            ticker_matches.add(str(item[id_key]))
    matches = matches or aliases or ticker_matches
    if len(matches) != 1:
        raise NotImplementedError(f"Cannot resolve {provider} identity for fund {row['FundName']}; "
                                  "the website may expose only underlying baskets")
    value = next(iter(matches))
    if not re.fullmatch(r"[1-9]\d*", value):
        raise ValueError(f"Invalid {provider} fund identity: {value!r}")
    return int(value)


def _unique_catalog_identity(website, column=None):
    context = _fund_request_context.get()
    catalog = context.get("catalog")
    identity = ["FundName", "RegistrationNumber", "GroupId"]
    if catalog is None or any(key not in catalog for key in identity + ["WebsiteAddress"]):
        return False
    matches = catalog[catalog["WebsiteAddress"].map(_normalize_website_host).eq(_normalize_website_host(website))]
    if column is not None:
        value = context["row"].get(column)
        if column not in matches or pd.isna(value):
            return False
        matches = matches[matches[column].eq(value).fillna(False)]
    return len(matches[identity].drop_duplicates()) == 1


def _rayan_instrument_id(items, website):
    row = _fund_request_context.get()["row"]
    code = row.get("InstrumentCode")
    if not isinstance(code, str) or not re.fullmatch(r"[1-9]\d*", code):
        return None
    matches, has_instruments = set(), False
    for item in items:
        url = item.get("tsetmcUrl")
        if url is not None and not isinstance(url, str):
            raise ValueError("Invalid Rayan fund instrument reference")
        reference = urlparse(url or "")
        if (reference.scheme in ("http", "https") and reference.username is None
                and reference.hostname in ("tsetmc.ir", "www.tsetmc.ir", "tsetmc.com", "www.tsetmc.com")
                and re.fullmatch(r"/InstInfo/[1-9]\d*/?", reference.path)
                and not reference.query and not reference.fragment):
            has_instruments = True
            if reference.path.rstrip("/") == f"/InstInfo/{code}":
                matches.add(str(item["fundId"]))
    if not matches:
        if has_instruments:
            raise NotImplementedError(f"Cannot resolve Rayan identity for fund {row['FundName']}; "
                                      "the published instruments disagree with the catalog")
        return None
    if len(matches) != 1 or not _unique_catalog_identity(website, "InstrumentCode"):
        named = [item for item in items if _fund_label(item["fundName"]) == _fund_label(row["FundName"])]
        if named:
            return _select_fund_id(named, "fundId", "fundName", "Rayan")
        raise NotImplementedError(f"Cannot resolve Rayan identity for fund {row['FundName']}; "
                                  "the instrument identifies multiple funds or unit classes")
    return next(iter(matches))


def _rayan_fund_id(website):
    context = _fund_request_context.get()
    if context is None:
        return 1
    if "rayan_id" not in context:
        data = _safe_get_json(f"https://{website}/api/v1/public/fundItems")
        if data is None and context["row"]["FundTypeName"] != "اختصاصی بازارگردانی":
            context["rayan_id"] = 1  # Legacy single-fund sites have no fundItems API.
        else:
            if not isinstance(data, list) or not data:
                raise NotImplementedError(f"No Rayan identity for fund {context['row']['FundName']}")
            if any(not isinstance(item, dict) or "fundId" not in item or "fundName" not in item for item in data):
                raise ValueError("Invalid Rayan fund identity response")
            row = context["row"]
            non_market_maker = str(row.get("FundTypeID")) != "11" and row["FundTypeName"] != "اختصاصی بازارگردانی"
            value = _rayan_instrument_id(data, website) if non_market_maker else None
            if value is None:
                try:
                    value = _select_fund_id(data, "fundId", "fundName", "Rayan")
                except NotImplementedError:
                    # dsCode is the SEO registration; submitCode is a different
                    # company-registration number. A multi-fund default is not
                    # sufficient evidence for a parent or another unit class.
                    if not non_market_maker or len(data) != 1 or not _unique_catalog_identity(website):
                        raise
                    info = _safe_get_json(f"https://{website}/api/v1/public/siteInfo")
                    registration = row.get("RegistrationNumber")
                    if (pd.isna(registration) or not isinstance(info, dict)
                            or str(info.get("dsCode")) != str(registration)
                            or str(info.get("defaultFundId")) != str(data[0]["fundId"])):
                        raise
                    value = data[0]["fundId"]
            if not re.fullmatch(r"[1-9]\d*", str(value)):
                raise ValueError(f"Invalid Rayan fund identity: {value!r}")
            context["rayan_id"] = int(value)
    return context["rayan_id"]


def _tadbir_basket_id(website):
    context = _fund_request_context.get()
    if context is None:
        return 1
    if "tadbir_id" not in context:
        soup = BeautifulSoup(_request("GET", f"https://{website}").text, "html.parser")
        selectors = soup.select("select#basketId")
        if not selectors:
            context["tadbir_id"] = 1
        else:
            # Some pages repeat selectors, with the parent only in the report selector.
            options = {(option.get("value"), option.get_text(strip=True))
                       for selector in selectors for option in selector.select("option")}
            items = [{"id": value, "name": name} for value, name in options]
            row = context["row"]
            name = _fund_label(row["FundName"])
            # The canonical parent can be omitted from every selector, while
            # a child shares its ticker or its name followed by that ticker.
            # Only a matching page title and one explicit positive default
            # identify that parent; neither GroupId nor an arbitrary ID does.
            if (str(row.get("FundTypeID")) != "11" and row["FundTypeName"] != "اختصاصی بازارگردانی"
                    and not any(_fund_label(item["name"]) == name for item in items)
                    and soup.title is not None and _fund_label(soup.title.get_text(" ", strip=True)) == name):
                defaults = {value.strip() for script in soup.select("script:not([src])")
                            for value in re.findall(r"\bvar\s+portfolioId\s*=\s*([^;]+);", script.get_text())}
                if len(defaults) != 1 or not re.fullmatch(r"[1-9]\d*", next(iter(defaults))):
                    raise ValueError(f"Tadbir canonical fund identity is missing or ambiguous for {row['FundName']}")
                items.append({"id": next(iter(defaults)), "name": row["FundName"]})
            try:
                context["tadbir_id"] = _select_fund_id(items, "id", "name", "Tadbir")
            except NotImplementedError as exc:
                raise ValueError(f"Tadbir fund identity is missing or ambiguous for {context['row']['FundName']}") from exc
    return context["tadbir_id"]


def _mabna_registered_page(website):
    soup = BeautifulSoup(_request("GET", f"https://{website}").text, "html.parser")
    text = text_or_na(soup.get_text(" ", strip=True))
    registrations = set(re.findall(r"(?<![0-9])([0-9]{4,6})\s+نزد\s+سازمان\s+بورس\b", str(text)))
    registrations.update(re.findall(
        r"شماره\s+ثبت\s+نزد\s+سازمان\s+بورس(?:\s+و\s+اوراق\s+بهادار)?\s+([0-9]{4,6})\b", str(text)))
    registration = _fund_request_context.get()["row"].get("RegistrationNumber")
    return soup, pd.notna(registration) and registrations == {str(registration)}


def _mabna_portfolio_id(website):
    context = _fund_request_context.get()
    if context is None:
        return 1
    if "mabna_id" not in context:
        data = _safe_get_json(f"https://{website}/api/v2/public/fund/portfolios")
        if data is None and context["row"]["FundTypeName"] != "اختصاصی بازارگردانی":
            context["mabna_id"] = 1
        else:
            items = data.get("data") if isinstance(data, dict) else None
            if not isinstance(items, list) or not items:
                raise ValueError("Invalid Mabna portfolio identity response")
            if any(not isinstance(item, dict) or "id" not in item or "name" not in item for item in items):
                raise ValueError("Invalid Mabna portfolio identity response")
            row = context["row"]
            non_market_maker = str(row.get("FundTypeID")) != "11" and row["FundTypeName"] != "اختصاصی بازارگردانی"
            if len(items) > 1 and non_market_maker:
                soup, registered = _mabna_registered_page(website)
                if soup.title is not None and _fund_label(soup.title.get_text(" ", strip=True)) == _fund_label(row["FundName"]):
                    if not registered or not _unique_catalog_identity(website, "FundName"):
                        raise ValueError(f"Invalid Mabna canonical fund identity for {row['FundName']}")
                    # The public report initializes its symbol as undefined:
                    # omitting portfolio_id selects the legal fund aggregate.
                    context["mabna_id"] = None
                    return None
            try:
                value = _select_fund_id(items, "id", "name", "Mabna")
            except NotImplementedError:
                if not non_market_maker or len(items) != 1 or not _unique_catalog_identity(website):
                    raise
                _, registered = _mabna_registered_page(website)
                if not registered:
                    raise
                value = items[0]["id"]
            if not re.fullmatch(r"[1-9]\d*", str(value)):
                raise ValueError(f"Invalid Mabna fund identity: {value!r}")
            context["mabna_id"] = int(value)
    return context["mabna_id"]


# GENERAL HELPER FUNCTIONS
def _retry_delay(response):
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(0, float(retry_after))
        except ValueError:
            try:
                when = parsedate_to_datetime(retry_after)
                return max(0, (when - dt.datetime.now(dt.timezone.utc)).total_seconds())
            except (ValueError, TypeError, OverflowError):
                pass
    return 0.5


def _request(method: str, url: str, timeout=30, **kwargs):
    """Verified, finite requests; retry a transient GET status at most once."""
    context = _fund_request_context.get()
    client = context.get("session", requests) if context is not None else requests
    for attempt in range(2):
        try:
            response = getattr(client, method.lower())(
                url, timeout=timeout, verify=True, allow_redirects=True, **kwargs)
        except requests.RequestException as exc:
            raise type(exc)(f"Funds {method} {url}: {exc}",
                            request=exc.request, response=exc.response) from exc
        if method == "GET" and attempt == 0 and response.status_code in (429, 500, 502, 503, 504):
            delay = _retry_delay(response)
            # Surface a long Retry-After instead of ignoring it or sleeping indefinitely.
            if delay <= 2:
                response.close()
                time.sleep(delay)
                continue
        response.raise_for_status()
        return response


def _decode_json(response):
    try:
        return response.json()
    except requests.exceptions.JSONDecodeError as exc:
        raise ValueError(f"Funds provider returned empty or invalid JSON: {response.url}") from exc


def _tsetmc_fund_identifier(value, parameter, minimum=1):
    """Accept URL identifiers, including integer-valued JSON registration numbers."""
    if isinstance(value, bool):
        number = None
    elif isinstance(value, Integral):
        number = int(value)
    elif isinstance(value, Real):
        try:
            number = int(value)
        except (ValueError, OverflowError):
            number = None
        if number != value:
            number = None
    elif isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        number = int(value)
    else:
        number = None
    if number is None or number < minimum:
        raise ValueError(f"{parameter} must be a whole-number identifier >= {minimum}")
    return number


def _tsetmc_fund_record(record, url):
    if not isinstance(record, dict) or not {"regNo", "mfName"}.issubset(record):
        raise ValueError(f"Invalid TSETMC fund record: {url}")
    _tsetmc_fund_identifier(record["regNo"], f"TSETMC regNo at {url}")
    return record


def _tsetmc_name(value):
    value = value.translate(str.maketrans({"ي": "ی", "ك": "ک"})).casefold()
    return re.sub(r"[\s\u200c]+", "", value)


def get_tsetmc_fund_types() -> pd.DataFrame:
    """List supported Persian/English group names and TSETMC numeric selectors.

    Return a fresh table with FundTypeID, FundTypeName and EnglishName.
    The mapping comes from the verified public menu; this performs no HTTP.
    It describes supported names, not current service availability or counts.
    Advanced numeric selector 0 is not listed: its all-groups API can fail.
    """
    frame = pd.DataFrame(_TSETMC_FUND_TYPES, columns=["FundTypeID", "FundTypeName", "EnglishName"])
    frame["FundTypeID"] = identifier_series(frame["FundTypeID"])
    return frame


def _tsetmc_fund_type(value):
    if isinstance(value, str):
        aliases = {label: code for code, persian, english in _TSETMC_FUND_TYPES
                   for label in (persian, english)}
        aliases.update({"در سهام": 6, "سهام": 6, "stock": 6,
                        "پروژه‌ای": 13, "بر پایه گواهی سپرده کالایی": 5})
        normalize = lambda label: _tsetmc_name(label).replace("_", "")
        names = {normalize(label): code for label, code in aliases.items()}
        if normalize(value) in names:
            return names[normalize(value)]
    try:
        return _tsetmc_fund_identifier(value, "fund_type", minimum=0)
    except ValueError as exc:
        raise ValueError("Invalid fund_type; choose a name from get_tsetmc_fund_types() "
                         "or supply a nonnegative numeric selector") from exc


def get_tsetmc_funds(fund_type: int | str) -> pd.DataFrame:
    """Return a normalized TSETMC fund-group snapshot.

    ``fund_type`` accepts a Persian/English group name (e.g. "سهامی",
    "مختلط", "equity", "mixed"); see get_tsetmc_fund_types() for options.
    Arabic/Persian letter variants, spacing and English case are normalized.
    Existing nonnegative integer, integer-valued number and ASCII digit-string
    selectors remain supported. These are not Fipiran type IDs or the returned
    ``fundType`` field. Provider availability is not guaranteed.

    Return a DataFrame in provider order with canonical English columns,
    numeric NAV/amount/percentage values, string identifiers and pandas
    Gregorian dates. Nested Stats records use semantic public keys. Unverified
    fields/payloads are preserved only inside explicit ProviderMetadata dicts.
    An explicit empty ``funds`` array returns an empty DataFrame without columns.

    Raises ValueError for invalid identifiers, JSON or record/envelope schema;
    requests.RequestException subclasses for transport and HTTP failures.
    HTTPS certificates are verified; requests have a finite timeout and at
    most one retry for a short transient GET status, as in other Funds APIs.
    """
    fund_type = _tsetmc_fund_type(fund_type)
    url = f"https://cdn.tsetmc.com/api/Fund/GetFunds/{fund_type}"
    try:
        data = _decode_json(_request("GET", url))
    except ValueError as exc:
        raise ValueError(f"TSETMC fund response: {exc}") from exc
    records = data.get("funds") if isinstance(data, dict) else None
    if not isinstance(records, list):
        raise ValueError(f"Invalid TSETMC funds response: {url}")
    return _tsetmc_fund_frame([_tsetmc_fund_record(record, url) for record in records])


def _resolve_tsetmc_fund_name(fund_name, fund_type):
    codes = [_tsetmc_fund_type(fund_type)] if fund_type is not None else [
        code for code, _, _ in _TSETMC_FUND_TYPES]
    matches = set()
    wanted = _tsetmc_name(fund_name)
    for code in codes:
        for record in get_tsetmc_funds(code).to_dict("records"):
            name = record["FundName"]
            if isinstance(name, str) and _tsetmc_name(name) == wanted:
                matches.add(_tsetmc_fund_identifier(record["RegistrationNumber"], "TSETMC regNo"))
    if not matches:
        raise ValueError(f"No TSETMC fund matches {fund_name!r}; "
                         "choose its full name from get_tsetmc_funds(fund_type)")
    if len(matches) != 1:
        raise ValueError(f"Multiple TSETMC funds match {fund_name!r}; specify fund_type "
                         "or use reg_no from get_tsetmc_funds(fund_type)")
    return matches.pop()


def get_tsetmc_fund_details(fund_name=None, *, fund_type=None, reg_no=None) -> dict:
    """Return a normalized TSETMC fund dict selected by name or registration.

    Supply a full ``fund_name`` positionally or by keyword. Resolve it against
    official catalogs using exact equality after Arabic/Persian letter, English
    case and whitespace normalization; no substring or fuzzy matching. Optional
    ``fund_type`` restricts lookup to one named/numeric group. Otherwise all ten
    known individual groups are checked, without relying on selector 0; a failed
    group is propagated rather than silently assuming uniqueness. Repeated
    matches for one registration are accepted; multiple registrations fail.

    Legacy positional numbers/digit strings and ``reg_no=`` remain supported
    and bypass catalog lookup. Registration numbers are positive whole numbers
    from TSETMC, not instrument codes. Do not combine registration selection
    with a fund name or type; conflicting selectors fail before HTTP.

    Ordinary keys share snapshot meanings: FundName, RegistrationNumber,
    SubscriptionNAV, RedemptionNAV, StatisticalNAV, TotalNAV, etc. Stats holds
    NAV records with the same verified field names. Unknown/ambiguous fields
    (including the unverified fundProfits payload) remain explicitly raw inside
    ProviderMetadata. No duplicate provider-key aliases or raw option is added.
    JSON scalar values and history order are preserved: histories are not sorted,
    filled or date-converted. Detail and list dates/coverage can differ.

    Raises ValueError for invalid/conflicting selectors, missing/ambiguous names,
    invalid JSON, malformed records or mismatched registration; requests.RequestException subclasses
    for transport and HTTP failures, including provider not-found HTTP errors.
    Uses the same verified, finite, bounded-retry transport as other Funds APIs.
    """
    if reg_no is not None:
        if fund_name is not None or fund_type is not None:
            raise ValueError("Supply either fund_name (with optional fund_type) or reg_no")
        reg_no = _tsetmc_fund_identifier(reg_no, "reg_no")
    elif isinstance(fund_name, str) and any(character.isalpha() for character in fund_name):
        reg_no = _resolve_tsetmc_fund_name(fund_name, fund_type)
    else:
        if fund_type is not None:
            raise ValueError("fund_type requires a fund_name; do not combine it with reg_no")
        reg_no = _tsetmc_fund_identifier(fund_name, "reg_no or fund_name")
    url = f"https://cdn.tsetmc.com/api/Fund/GetFundInDetail/{reg_no}"
    try:
        data = _decode_json(_request("GET", url))
    except ValueError as exc:
        raise ValueError(f"TSETMC fund response: {exc}") from exc
    record = _tsetmc_fund_record(data.get("fund") if isinstance(data, dict) else None, url)
    if _tsetmc_fund_identifier(record["regNo"], f"TSETMC regNo at {url}") != reg_no:
        raise ValueError(f"TSETMC fund registration does not match reg_no: {url}")
    return _tsetmc_fund_object(record)


def _records(response, key=None):
    data = _decode_json(response)
    if key is not None:
        if not isinstance(data, dict) or data.get("status", 200) != 200:
            raise ValueError(f"Invalid Funds provider response: {response.url}")
        data = data.get(key)
    if not isinstance(data, list) or not data or not all(isinstance(row, dict) for row in data):
        raise ValueError(f"Missing or empty Funds provider records ({key}): {response.url}")
    return data


def _safe_get_json(url: str, timeout: int = 30, params: dict = None):
    """Probe optional endpoints without hiding transport or service failures."""
    try:
        response = _request("GET", url, params=params, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    except requests.HTTPError as exc:
        if exc.response.status_code not in (404, 405):
            raise
        return None
    try:
        return _decode_json(response)
    except ValueError:
        return None


def _safe_get_text(url: str, timeout: int = 30):
    try:
        response = _request("GET", url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    except requests.HTTPError as exc:
        if exc.response.status_code not in (404, 405):
            raise
        return None
    return response.text.strip() or None


def _safe_post_json(url: str, payload: dict, headers: dict = None, timeout: int = 12):
    default_headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*",
                       "Content-Type": "application/json"}
    default_headers.update(headers or {})
    try:
        response = _request("POST", url, json=payload, headers=default_headers, timeout=timeout)
    except requests.HTTPError as exc:
        if exc.response.status_code not in (404, 405):
            raise
        return None
    try:
        return _decode_json(response)
    except ValueError:
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


def _catalog_website(address):
    if isinstance(address, list):
        address = next((value for value in address if isinstance(value, str) and value.strip()), None)
    if address is None or isinstance(address, str) or pd.isna(address):
        return _normalize_website_host(address)
    raise ValueError("Fipiran websiteAddress must be a string, list, or null")


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
    fund_types = pd.DataFrame(_records(_request("GET", url), "items"))
    _require_columns(fund_types, ["fundType", "name", "isActive"], "Fipiran fund types")
    return fund_types[["fundType", "name", "isActive"]].rename(
        columns={"fundType": "FundTypeID", "name": "FundTypeName", "isActive": "IsActive"})


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


def _mabna_nav_params(size: int):
    return {"start_date": "1997-11-10T08:13:36.377Z",
            "end_date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "page": 1, "size": size}


def _detect_mabna_by_nav_api(website: str) -> bool:
    for base_url in _build_base_urls(website):
        url = f"{base_url}/api/v2/public/reports/navps"
        data = _safe_get_json(url, timeout=30, params=_mabna_nav_params(5))
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
    return "Unknown"


# Tadbirpardaz
def _tadbir_chart(data, series):
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("Invalid Tadbir chart response")
    result = None
    for name, column in series.items():
        matches = [item for item in data if item.get("name") == name]
        if len(matches) != 1:
            raise ValueError(f"Tadbir chart requires exactly one series: {name!r}")
        points = matches[0].get("List")
        if not isinstance(points, list) or not points or not all(
                isinstance(point, dict) and point.get("x") is not None and point.get("y") is not None
                for point in points):
            raise ValueError(f"Tadbir chart has empty or invalid points: {name!r}")
        frame = pd.DataFrame(points)[["x", "y"]].rename(columns={"x": "GDate", "y": column})
        frame["GDate"] = pd.to_datetime(frame["GDate"], format="%m/%d/%Y").dt.date
        frame[column] = pd.to_numeric(frame[column])
        # Current Jahesh and Bidar charts repeat identical date/value points.
        # Removing exact repeats is lossless; conflicting prices still fail.
        frame = frame.drop_duplicates(subset=["GDate", column])
        if frame["GDate"].duplicated().any():
            raise ValueError(f"Tadbir chart has duplicate dates: {name!r}")
        result = frame if result is None else result.merge(frame, on="GDate", how="inner", validate="one_to_one")
    if result.empty:
        raise ValueError("Tadbir chart series have no shared reporting dates")
    result = result.sort_values("GDate", ascending=False, ignore_index=True)
    result["JDate"] = result["GDate"].apply(_gregorian_to_jalali)
    return result.drop(columns="GDate")


def _get_daily_navs_per_share_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    website = _get_fund_website_address(fund_name)
    url = f"https://{website}/Chart/TotalNAV?type=getnavtotal&basketId={_tadbir_basket_id(website)}"
    return _tadbir_chart(_decode_json(_request("GET", url)), {
        "صدور": "Subscription", "آماری": "Statistical", "ابطال": "Redemption"})


def _get_leveraged_daily_navs_per_share_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    website = _get_fund_website_address(fund_name)
    url = f"https://{website}/Chart/TotalNAV?type=getnavtotal&basketId={_tadbir_basket_id(website)}"
    data = _decode_json(_request("GET", url))
    legacy = isinstance(data, list) and any(isinstance(item, dict) and item.get("name") == "عادی" for item in data)
    mapping = {"صدور": "Subscription", "آماری": "Statistical", "ابطال": "Redemption"}
    if legacy:
        mapping["عادی"] = "Common"
    mapping.update({"صدور ممتاز": "SpecialSubscription", "ابطال ممتاز": "SpecialRedemption"})
    if not legacy:
        mapping["آماری ممتاز"] = "SpecialStatistical"
    return _tadbir_chart(data, mapping)


def _get_daily_total_nav_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    website = _get_fund_website_address(fund_name)
    url = f"https://{website}/Chart/CombinationOfFundAssets?type=getnavtotal&basketId={_tadbir_basket_id(website)}"
    return _tadbir_chart(_decode_json(_request("GET", url)), {"": "TotalNAV"})


def _get_daily_asset_allocation_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    website = _get_fund_website_address(fund_name)
    fund_id = _tadbir_basket_id(website)
    base_url = f"https://{website}/Reports/FundDailyAssetDistribution"
    params = {"basketId": fund_id, "page": 1}
    all_rows = []
    headers = []
    seen_pages = set()
    while params["page"] <= 10000:
        # Request the page
        response = _request("GET", base_url, params=params)
        soup = BeautifulSoup(response.text, "html.parser")
        # Extract headers (only once)
        if not headers:
            headers = [th.get_text(strip=True) for th in soup.select("thead th")]
        # Extract data rows
        rows = [tuple(td.get_text(strip=True).replace("\u200c", "") for td in tr.find_all("td"))
                for tr in soup.select("tbody tr")]
        if not headers or not rows or any(len(row) != len(headers) for row in rows):
            raise ValueError(f"Tadbir asset report is empty or malformed: {base_url}")
        page_rows = tuple(rows)
        if page_rows in seen_pages:
            raise ValueError(f"Tadbir asset report repeats a page: {base_url}")
        seen_pages.add(page_rows)
        all_rows.extend(rows)
        # Check if there is a next page
        next_page_link = soup.select_one("tfoot .pager a[title='Next page']")
        if next_page_link:
            # Update page number in query params
            params["page"] += 1
            time.sleep(0.3)  # be polite
        else:
            break
    else:
        raise ValueError(f"Tadbir asset report exceeded the page limit: {base_url}")

    daily_asset_allocation = pd.DataFrame(all_rows, columns=headers)

    daily_asset_allocation.drop('ردیف', inplace=True, axis=1)
    daily_asset_allocation.rename({'تاریخ': 'Date', 'پنج سهم برتر': 'Upper5%Stocks', 'پنج سهم برتر به کل دارایی': 'Upper5%Stocks Weight',
               'سایر سهام': 'OtherStocks', 'سایر سهام به کل دارایی': 'OtherStocks Weight', 'اوراق مشارکت': 'Bonds',
               'اوراق مشارکت به کل دارایی': 'Bonds Weight', 'اوراق سپرده': 'CDs',
               'اوراق سپرده به کل دارایی': 'CDs Weight', 'نقد و بانک (جاری و سپرده)': 'CashAndBank',
               'وجه نقد به کل دارایی': 'CashAndBank Weight', 'سایر دارایی‌ها': 'OtherAssets',
               'سایر دارایی‌ها به کل دارایی': 'OtherAssets Weight', 'صندوق سرمایه گذاری': 'FundUnits',
               'صندوق سرمایه گذاری به کل دارایی': 'FundUnits Weight'}, inplace=True, axis=1)

    optional_assets = {"گواهی سپرده کالایی": "CCDs", "اختیار معامله": "Options",
                       "پروژه در جریان ساخت": "ConstructionProjects", "دارایی‌های ثابت": "FixedAssets"}
    extra_values = []
    for source, target in optional_assets.items():
        if source in daily_asset_allocation:
            _require_columns(daily_asset_allocation, [f"{source} به کل دارایی"], "Tadbir asset report")
            daily_asset_allocation.rename(columns={source: target, f"{source} به کل دارایی": f"{target} Weight"}, inplace=True)
            extra_values.append(target)

    daily_asset_allocation['Date'] = daily_asset_allocation['Date'].apply(lambda date_str: str(int(date_str.replace('/', ''))))
    daily_asset_allocation['Date'] = daily_asset_allocation['Date'].apply(_jalali_str_to_date)
    for ValueColumn in ['Upper5%Stocks', 'OtherStocks', 'Bonds', 'CDs', 'CashAndBank', 'OtherAssets', 'FundUnits'] + extra_values:
        daily_asset_allocation.loc[:, ValueColumn] = daily_asset_allocation[ValueColumn].str.replace(',', '').astype(int)
    for PercentageColumn in ['Upper5%Stocks Weight', 'OtherStocks Weight', 'Bonds Weight', 'CDs Weight',
                              'CashAndBank Weight', 'OtherAssets Weight', 'FundUnits Weight'] + [f"{name} Weight" for name in extra_values]:
        daily_asset_allocation.loc[:, PercentageColumn] = daily_asset_allocation[PercentageColumn].str.replace(' %', '').astype(float)

    daily_asset_allocation = daily_asset_allocation[['Date', 'OtherStocks', 'Upper5%Stocks', 'Bonds', 'CDs', 'CashAndBank',
                                                     'FundUnits', 'OtherAssets', 'OtherStocks Weight', 'Upper5%Stocks Weight',
                                                     'Bonds Weight', 'CDs Weight', 'CashAndBank Weight', 'FundUnits Weight',
                                                      'OtherAssets Weight'] + extra_values + [f"{name} Weight" for name in extra_values]]

    return daily_asset_allocation


def _get_daily_navs_tadbirpardaz(fund_name: str) -> pd.DataFrame:
    navs_per_share = _get_daily_navs_per_share_tadbirpardaz(fund_name)
    total_navs = _get_daily_total_nav_tadbirpardaz(fund_name)
    navs = pd.merge(total_navs, navs_per_share, on='JDate', how='inner')
    navs = navs[['JDate', 'Subscription', 'Redemption', 'Statistical', 'TotalNAV']]
    return navs


# Rayan hamafza
def _get_daily_asset_allocation_rayan_hamafza(fund_name: str) -> pd.DataFrame:
    website = _get_fund_website_address(fund_name)
    fund_id = _rayan_fund_id(website)
    assets = [("Stock", "Stocks"), ("TopFiveStock", "Upper5%Stocks"), ("Bond", "Bonds"),
              ("Cash", "Cash"), ("Deposit", "Bank"), ("FundUnit", "FundUnits"),
              ("Ccd", "CCDs"), ("OtherAsset", "OtherAssets")]
    mapping = {"Date": "Date"}
    mapping.update({f"{source}TodayAmount": target for source, target in assets})
    mapping.update({f"{source}TodayPercent": f"{target} Weight" for source, target in assets})
    for base_url in _build_base_urls(website):
        for path in (f"/api/v1/public/dailyAssetStructure/{fund_id}", f"/api/data/DailyAssetStructure/{fund_id}"):
            data = _safe_get_json(base_url + path)
            records = data.get("data") if isinstance(data, dict) else data
            if not isinstance(records, list) or not records or not all(isinstance(row, dict) for row in records):
                continue
            # The new API uses lower camel case; the legacy API uses upper camel case.
            records = [{key[0].upper() + key[1:]: value for key, value in row.items() if key}
                       for row in records]
            if not all(set(mapping).issubset(row) for row in records):
                continue
            result = pd.DataFrame(records).rename(columns=mapping)[list(mapping.values())].copy()
            result["Date"] = result["Date"].apply(_jalali_str_to_date)
            return result
    raise ValueError(f"Could not find valid Rayan Hamafza asset allocation API for {fund_name} | {website}")


def _get_rayan_hamafza_nav_records(website: str, fund_id=1):
    for base_url in _build_base_urls(website):
        candidate_urls = [f"{base_url}/api/v1/public/nav/{fund_id}", f"{base_url}/api/data/NAV/{fund_id}",]
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
    context = _fund_request_context.get()
    if context is not None and context["row"]["FundTypeName"] == "اختصاصی بازارگردانی":
        data = _safe_get_json(f"https://{website}/api/v1/public/navMulti?size=-1")
        if data is not None:
            if not isinstance(data, list) or not data or not all(isinstance(row, dict) for row in data):
                raise ValueError("Invalid Rayan aggregate NAV records")
            navs = pd.DataFrame(data)
            required = ["jalaliDate", "purchaseNAVPerShare", "sellNAVPerShare",
                        "statisticNav", "fundCapital", "totalAssetsValue"]
            _require_columns(navs, required, "Rayan aggregate NAV")
            if navs[required].isna().any().any():
                raise ValueError("Missing Rayan aggregate NAV values")
            result = pd.DataFrame({"JDate": navs["jalaliDate"].map(_jalali_str_to_date)})
            for source, target in [("purchaseNAVPerShare", "Subscription"),
                                   ("sellNAVPerShare", "Redemption"), ("statisticNav", "Statistical")]:
                result[target] = number_series(navs[source])
            result["TotalNAV"] = pd.to_numeric(navs["totalAssetsValue"])
            return result
    records = _get_rayan_hamafza_nav_records(website, _rayan_fund_id(website))
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
    navs["PurchaseNAVPerShare"] = number_series(navs["PurchaseNAVPerShare"])
    navs["SellNAVPerShare"] = number_series(navs["SellNAVPerShare"])
    navs["StatisticalNAVPerShare"] = number_series(navs["StatisticalNAVPerShare"])
    navs["Units"] = number_series(navs["Units"])
    navs["NAV"] = number_series(navs["NAV"])
    # Keep per-unit NAV distinct from the aggregate NAV supplied separately.
    navs["Subscription"] = navs["PurchaseNAVPerShare"]
    navs["Redemption"] = navs["SellNAVPerShare"]
    navs["Statistical"] = navs["StatisticalNAVPerShare"]
    navs["TotalNAV"] = navs["NAV"]
    navs = navs[["JDate", "Subscription", "Redemption", "Statistical", "TotalNAV"]]
    return navs


# Mabna
def _mabna_report_records(url, params):
    rows = []
    seen = set()
    total = None
    for page in range(1, 10001):
        data = _safe_get_json(url, params={**params, "page": page})
        if data is None and page == 1:
            return None
        records = data.get("data") if isinstance(data, dict) else None
        if not isinstance(records, list) or not records or not all(isinstance(row, dict) for row in records):
            raise ValueError(f"Missing or empty Mabna report records: {url}")
        dates = tuple(row.get("date_time", row.get("date")) for row in records)
        if any(not isinstance(date, str) for date in dates):
            raise ValueError(f"Invalid Mabna report dates: {url}")
        if len(set(dates)) != len(dates) or seen.intersection(dates):
            raise ValueError(f"Mabna report repeats dates or a page: {url}")
        seen.update(dates)
        rows.extend(records)
        count = data.get("total_count")
        if count is None:
            return rows  # Legacy reports have no pagination metadata.
        if not isinstance(count, int) or isinstance(count, bool) or count < len(rows):
            raise ValueError(f"Invalid Mabna report total_count: {url}")
        if total is not None and count != total:
            raise ValueError(f"Mabna report total_count changed during pagination: {url}")
        total = count
        if len(rows) == total:
            return rows
    raise ValueError(f"Mabna report exceeded the page limit: {url}")


def _mabna_asset_frame(records, current):
    names = {
        "سپرده بانکی": "Bank", "وجه نقد": "Cash", "اوراق بهادار": "Bonds",
        "سرمایه‌گذاری در اوراق بهادار با درآمد ثابت": "Bonds", "سهام": "Stocks",
        "سرمایه گذاری در سهام": "Stocks", "گواهی سپرده کالایی": "CCDs",
        "صندوق های سرمایه گذاری": "FundUnits", "سایر دارایی‌ها": "OtherAssets",
        "پنج سهم با بیشترین وزن": "Upper5%Stocks", "پنج ورقه بهادار با بیشترین وزن": "Upper5%Bonds",
    }
    mapping = {_fund_label(name): column for name, column in names.items()}
    rows = []
    for item in records:
        if not isinstance(item, dict) or "date" not in item:
            raise ValueError("Invalid Mabna asset report date")
        assets = item.get("items", {}).get("assets") if current and isinstance(item.get("items"), dict) else item.get("assets")
        if not isinstance(assets, list) or not assets:
            raise ValueError("Invalid Mabna asset report assets")
        date = _gregorian_to_jalali(pd.to_datetime(item["date"]).date()) if current else _jalali_str_to_date(item["date"])
        row = {"Date": date}
        for asset in assets:
            if not isinstance(asset, dict) or not {"asset_name", "value", "percentage"}.issubset(asset):
                raise ValueError("Invalid Mabna asset report fields")
            name = asset["asset_name"]
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Invalid Mabna asset name")
            column = mapping.get(_fund_label(name), name.strip())
            if column in row:
                raise ValueError(f"Duplicate Mabna asset name: {name}")
            row[column] = number_series(pd.Series([asset["value"]])).iloc[0]
            row[f"{column} Weight"] = number_series(pd.Series([asset["percentage"]])).iloc[0]
            if pd.isna(row[column]) or pd.isna(row[f"{column} Weight"]):
                raise ValueError(f"Missing Mabna asset values: {name}")
        rows.append(row)
    result = pd.DataFrame(rows)
    columns = ["Date", "Stocks", "Upper5%Stocks", "Bonds", "Cash", "Bank", "OtherAssets",
               "Stocks Weight", "Upper5%Stocks Weight", "Bonds Weight", "Cash Weight", "Bank Weight", "OtherAssets Weight"]
    _require_columns(result, columns, "Mabna asset report")
    if result[columns].isna().any().any():
        raise ValueError("Missing Mabna asset report values")
    extras = [column for column in result if column not in columns]
    return result[columns + extras]


def _get_daily_asset_allocation_mabna(fund_name: str) -> pd.DataFrame:
    fund_website = _get_fund_website_address(fund_name)
    url = f"https://{fund_website}/api/v2/public/reports/daily-assets"
    portfolio_id = _mabna_portfolio_id(fund_website)
    params = {"size": 1000000}
    if portfolio_id is not None:
        params["portfolio_id"] = portfolio_id
    data = _mabna_report_records(url, params)
    if data is not None:
        return _mabna_asset_frame(data, current=True)
    if portfolio_id is None:
        raise ValueError(f"No Mabna canonical asset report: {url}")
    url = f"https://{fund_website}/api/v1/overall/allassetsdaily.json"
    response = _request("GET", url)
    data = _records(response)[0]
    if not isinstance(data.get("values"), list) or not data["values"]:
        raise ValueError("Invalid legacy Mabna asset records")
    return _mabna_asset_frame(data["values"], current=False)


def _get_daily_navs_mabna(fund_name: str) -> pd.DataFrame:
    website = _get_fund_website_address(fund_name)
    url = f"https://{website}/api/v2/public/reports/navps"
    params = _mabna_nav_params(1000000)
    portfolio_id = _mabna_portfolio_id(website)
    if portfolio_id is not None:
        params["portfolio_id"] = portfolio_id
    records = _mabna_report_records(url, params)
    if records is None:
        raise ValueError(f"No Mabna NAV report: {url}")
    mapping = {"date_time": "JDate", "purchase_price": "Subscription", "redemption_price": "Redemption",
               "statistical_value": "Statistical", "total_net_asset_value_with_buy_commission_and_discount": "TotalSubscriptionNAV"}
    navs = pd.DataFrame(records)
    _require_columns(navs, list(mapping), "Mabna NAV")
    if navs[list(mapping)].isna().any().any():
        raise ValueError("Missing Mabna NAV values")
    navs = navs[list(mapping)].rename(columns=mapping).copy()
    navs["JDate"] = pd.to_datetime(navs["JDate"]).map(lambda date: _gregorian_to_jalali(date.date()))
    for column in ["Subscription", "Redemption", "Statistical", "TotalSubscriptionNAV"]:
        navs[column] = number_series(navs[column])
    return navs


def _get_leveraged_daily_navs_mabna(fund_name: str) -> pd.DataFrame:
    website = _get_fund_website_address(fund_name)
    portfolio_id = _mabna_portfolio_id(website)
    query = "" if portfolio_id is None else f"?portfolio_id={portfolio_id}"
    url = f"https://{website}/api/v2/public/fund/chart{query}"
    response = _request("GET", url)
    navs = pd.DataFrame(_records(response, "data"))
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
    response = _request("POST", url, headers=headers, json=payload)
    response.raise_for_status()
    daily_asset_allocation = pd.DataFrame(_records(response, "Result"))
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
    response = _request("POST", url, headers=headers, json=payload)
    navs = pd.DataFrame(_records(response, "Result"))
    _require_columns(navs, ["Date", "SubscriptionNAV", "RedemptionNAV", "StaticalNAV", "NetAssetValue"], "Pikad NAV")
    navs = navs[["Date", "SubscriptionNAV", "RedemptionNAV", "StaticalNAV", "NetAssetValue"]].copy()
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
    response = _request("GET", url)
    daily_asset_allocation = pd.DataFrame(_records(response))
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
    response = _request("GET", url)
    navs = pd.DataFrame(_records(response))
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
    navs["SubscriptionValue"] = number_series(navs["SubscriptionValue"])
    navs["RedemptionValue"] = number_series(navs["RedemptionValue"])
    navs["StatisticalValue"] = number_series(navs["StatisticalValue"])
    navs["TotalQuantity"] = number_series(navs["TotalQuantity"])
    navs["NetAssetValue"] = number_series(navs["NetAssetValue"])
    # Per-unit NAV; total assets are supplied separately.
    navs["Subscription"] = navs["SubscriptionValue"]
    navs["Redemption"] = navs["RedemptionValue"]
    navs["Statistical"] = navs["StatisticalValue"]
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
            daily_asset_allocation[column] = float("nan")
        daily_asset_allocation[column] = number_series(daily_asset_allocation[column])
    for column in weight_columns:
        if column not in daily_asset_allocation.columns:
            daily_asset_allocation[column] = float("nan")
        daily_asset_allocation[column] = number_series(daily_asset_allocation[column])

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
    data = _decode_json(_request("GET", url))
    if not _is_valid_nika_nav_response(data):
        raise ValueError(f"Nika NAV response schema is invalid for {fund_name} | {fund_website}")
    navs = pd.DataFrame(data["items"])
    _require_columns(navs,["date", "issuanceNav", "redemptionNav", "nominalNAV", "totalUnit",
                           "redemptionNetAssetValue"],"Nika NAV")
    navs["GDate"] = pd.to_datetime(navs["date"]).dt.date
    navs["JDate"] = navs["GDate"].apply(_gregorian_to_jalali)
    navs["issuanceNav"] = number_series(navs["issuanceNav"])
    navs["redemptionNav"] = number_series(navs["redemptionNav"])
    navs["nominalNAV"] = number_series(navs["nominalNAV"])
    navs["totalUnit"] = number_series(navs["totalUnit"])
    navs["redemptionNetAssetValue"] = number_series(navs["redemptionNetAssetValue"])
    navs["Subscription"] = navs["issuanceNav"]
    navs["Redemption"] = navs["redemptionNav"]
    navs["Statistical"] = navs["nominalNAV"]
    navs["TotalNAV"] = navs["redemptionNetAssetValue"]
    return navs[["JDate", "Subscription", "Redemption", "Statistical", "TotalNAV"]]


def _get_fund_row(fund_name: str, all_funds: pd.DataFrame = None) -> pd.Series:
    if all_funds is None:
        context = _fund_request_context.get()
        if context is not None and context["row"]["FundName"] == fund_name:
            return context["row"]
        all_funds = get_all_funds(_set_website_developers=False)
    matches = all_funds[all_funds["FundName"] == fund_name]
    if matches.empty:
        raise ValueError(f"Fund not found: {fund_name}")
    return matches.iloc[0]


def _autoset_website_developers(all_funds: pd.DataFrame, max_workers: int = 10) -> pd.DataFrame:
    results = {}
    def safe_detect(row):
        address = row.get("WebsiteAddress")
        fund_type = row.get("FundTypeName")
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
            except (requests.RequestException, ValueError):
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
def _history_website(website, catalog):
    context = _fund_request_context.get()
    row = context["row"]
    host = _normalize_website_host(website)
    target = _OFFICIAL_FUND_WEBSITES.get((str(row.get("RegistrationNumber")), host))
    if (target is None or str(row.get("FundTypeID")) == "11"
            or row["FundTypeName"] == "اختصاصی بازارگردانی"):
        return website
    info = _safe_get_json(f"https://{target}/api/v1/public/siteInfo")
    if not isinstance(info, dict) or str(info.get("dsCode")) != str(row["RegistrationNumber"]):
        raise ValueError(f"Invalid fund-domain migration identity for {row['FundName']} | {target}")
    # Keep the raw public catalog intact. Provider resolution uses the verified
    # replacement consistently for this call, including catalog uniqueness.
    resolved = catalog.copy()
    resolved.loc[resolved["WebsiteAddress"].map(_normalize_website_host).eq(host), "WebsiteAddress"] = target
    context["catalog"] = resolved
    context["row"] = row.copy()
    context["row"]["WebsiteAddress"] = target
    return target


def _get_fund_history(fund_name, allocation):
    all_funds = get_all_funds(_set_website_developers=False)
    row = _get_fund_row(fund_name, all_funds)
    kind = "daily asset allocations" if allocation else "daily NAVs"
    if row["FundTypeName"] in NO_PUBLIC_NAV_FUND_TYPES:
        raise ValueError(f"Fund type does not have {kind}: {row['FundTypeName']}")
    if fund_name == "صندوق تثبیت بازار سرمایه":
        raise ValueError(f"Fund does not have {kind}: {fund_name}")
    website = row["WebsiteAddress"]
    session = requests.Session()
    token = _fund_request_context.set({"row": row, "catalog": all_funds, "session": session})
    try:
        website = _history_website(website, all_funds)
        developer = _detect_website_developer(website=website)
        if allocation:
            parsers = {
                "گروه رایانه تدبیر پرداز": _get_daily_asset_allocation_tadbirpardaz,
                "شرکت رایان هم افزا": _get_daily_asset_allocation_rayan_hamafza,
                "پردازش اطلاعات مالی مبنا": _get_daily_asset_allocation_mabna,
                "پیکاد": _get_daily_asset_allocation_pikad,
                "راهکار حامی پرداز": _get_daily_asset_allocation_rahkar,
                "نوآوران": _get_daily_asset_allocation_noavaran,
            }
        else:
            leveraged = row["FundTypeName"] == "در سهام-سهامی اهرمی"
            parsers = {
                "گروه رایانه تدبیر پرداز": (_get_leveraged_daily_navs_per_share_tadbirpardaz
                                             if leveraged else _get_daily_navs_tadbirpardaz),
                "شرکت رایان هم افزا": _get_daily_navs_rayan_hamafza,
                "پردازش اطلاعات مالی مبنا": (_get_leveraged_daily_navs_mabna
                                             if leveraged else _get_daily_navs_mabna),
                "پیکاد": _get_daily_navs_pikad,
                "راهکار حامی پرداز": _get_daily_navs_rahkar,
                "سامانه هوشمند نیکا سرمایه": _get_daily_navs_nika,
                "نوآوران": _get_daily_navs_noavaran,
            }
        parser = parsers.get(developer)
        if parser is None:
            raise NotImplementedError(f"Provider {developer} does not support {kind} for fund: {fund_name} | website: {website}")
        return _provider_result(parser, fund_name, website)
    finally:
        try:
            session.close()
        finally:
            _fund_request_context.reset(token)


def _provider_result(parser, fund_name, website):
    try:
        result = parser(fund_name)
    except requests.RequestException:
        raise
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError(f"Invalid provider response for fund {fund_name} | website: {website}; "
                         f"missing or unexpected fields: {exc}") from exc
    if result.empty:
        raise ValueError(f"No provider data for fund {fund_name} | website: {website}")
    return result


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
        Leveraged Tadbir charts contain ordinary and preferred per-unit NAV
        columns; preferred-unit columns use PreferredSubscriptionNAV,
        PreferredRedemptionNAV and PreferredStatisticalNAV; legacy charts
        retain Common without inferring a NAV subtype. NAVs are per unit;
        aggregate valuations remain separate. See docs/data-migration.md.

    Raises
    ------
    ValueError
        If the fund name is invalid, data is unavailable, or the provider
        response is empty or malformed.
    NotImplementedError
        If the provider is unsupported or its published identity list cannot
        resolve the requested fund. Market-maker Rayan NAV uses aggregate
        history rather than an underlying basket.
    requests.RequestException
        For connection, timeout, certificate, or HTTP errors from a provider.
    """
    return _nav_frame(_get_fund_history(fund_name, allocation=False))


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
        Existing provider units are preserved. Current Mabna reports also
        retain additional known asset amounts and Weight columns. Unknown
        source-language asset labels remain in ProviderAssets metadata.

    Raises
    ------
    ValueError
        If the fund name is invalid, data is unavailable, or the provider
        response is empty or malformed.
    NotImplementedError
        If the provider or requested fund identity is unsupported. A site
        exposing only market-maker baskets does not supply aggregate daily
        allocation for the parent fund.
    requests.RequestException
        For connection, timeout, certificate, or HTTP errors from a provider.
    """
    return _allocation_frame(_get_fund_history(fund_name, allocation=True))


def get_all_funds(_set_website_developers: bool = False) -> pd.DataFrame:
    """Return available investment-fund information from Fipiran.

    Parameters
    ----------
    _set_website_developers : bool, default False
        Probe fund websites to add WebsiteDeveloper. Failed requests are
        marked Error in this optional metadata column.

    Returns
    -------
    pandas.DataFrame
        Fund metadata and current information, including market-maker funds
        and non-market-maker fund compartments, but not the individual
        instruments covered by market makers.
        FundName/FundTypeName identify the fund and type; RegistrationNumber
        and FundTypeID are strings. WebsiteAddress is the first host or pd.NA.
        Missing allocation weights remain missing; valid zero remains zero.

    Raises
    ------
    requests.RequestException
        For connection, timeout, certificate, or HTTP errors from Fipiran.
    ValueError
        If the catalog or fund-type response is empty or malformed.

    Notes
    -----
    This function uses a live external data source, so network or provider
    availability can affect the result.
    HTTPS certificates are verified. A migrated fund website or invalid
    certificate may prevent retrieval even when other funds remain reachable.
    """
    url = "https://www.fipiran.ir/services/fund/fundcompare"
    response = _request("POST", url, json={"regNos": [], "showMarketMakers": True})
    try:
        all_funds = pd.DataFrame(_records(response, "items"))
    except ValueError as exc:
        raise ValueError(f"Fipiran fund catalog: {exc}") from exc
    _require_columns(all_funds, ["name", "fundType", "typeOfInvest", "fundSize",
                                "initiationDate", "date"], "Fipiran fund catalog")
    market_makers = all_funds["fundType"].eq(11)
    if market_makers.any():
        _require_columns(all_funds, ["groupId"], "Fipiran fund catalog")
        groups = all_funds.loc[market_makers, "groupId"]
        valid_groups = groups.map(
            lambda value: isinstance(value, (int, float)) and not isinstance(value, bool)
            and value >= 0 and value % 1 == 0)
        if not valid_groups.all():
            raise ValueError("Fipiran market-maker groupId must be a non-negative integer")
        # Fipiran's market-maker listing keeps parent groups 0 and 1.
        # Other market-maker groups are instruments, not investment funds.
        # Non-market-maker groups can be genuine fund compartments.
        all_funds = all_funds.loc[
            ~market_makers | all_funds["groupId"].isin([0, 1])].reset_index(drop=True)
        if all_funds.empty:
            raise ValueError("Fipiran fund catalog contains no fund-level records")
    for column, default in {"websiteAddress": None, "guarantor": None,
                            "dividendIntervalPeriod": float("nan")}.items():
        if column not in all_funds:
            all_funds[column] = default
    # all_funds.drop(['rankOf12Month', 'rankOf24Month', 'rankOf36Month', 'rankOf48Month', 'rankOf60Month',
    #                'rankLastUpdate', 'guaranteedEarningRate', 'articlesOfAssociationLink', 'prosoectusLink',
    #                'fundPublisher', 'fundWatch'], inplace=True, axis=1)
    all_funds.columns = all_funds.columns.map(lambda column: column[0].upper() + column[1:])
    all_funds.rename({'Name': 'FundName', 'RegNo': 'RegistrationNumber', 'TypeOfInvest': 'InvestmentType', 'FundSize': 'TotalNAV',
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
    all_funds['FundTypeID'] = identifier_series(all_funds['FundType'])
    all_funds['FundTypeName'] = all_funds.pop('FundType').map(fund_type_map)
    all_funds['InvestmentType'] = all_funds['InvestmentType'].map(
        lambda value: {'Negotiable': 'ETF', 'IssuanceAndCancellation': 'Open-Ended'}.get(value, value))
    all_funds['InceptionDate'] = pd.to_datetime(all_funds['InceptionDate'], errors="coerce").dt.date
    all_funds['InceptionDate'] = all_funds['InceptionDate'].apply(
        lambda g: jd.date.fromgregorian(date=g) if isinstance(g, dt.date) and not pd.isna(g) else None)
    all_funds['UpdateDate'] = pd.to_datetime(all_funds['UpdateDate'], errors="coerce").dt.date
    all_funds['UpdateDate'] = all_funds['UpdateDate'].apply(
        lambda g: jd.date.fromgregorian(date=g) if isinstance(g, dt.date) and not pd.isna(g) else None)
    weight_columns = ['Upper5%Stocks Weight', 'Stocks Weight', 'Bonds Weight', 'Others Weight', 'Cash Weight',
                     'Bank CDs Weight', 'FundUnits Weight', 'Commodities Weight']
    for column in weight_columns:
        if column not in all_funds:
            all_funds[column] = float('nan')
        all_funds[column] = number_series(all_funds[column])
    all_funds['LiquidityGuarantor'] = all_funds['LiquidityGuarantor'].replace('----', '-')
    all_funds['DividendFrequency (Month)'] = number_series(all_funds['DividendFrequency (Month)'])
    all_funds['WebsiteAddress'] = all_funds['WebsiteAddress'].apply(_catalog_website)
    all_funds.loc[all_funds['FundName'] == 'صندوق تثبیت بازار سرمایه', 'WebsiteAddress'] = 'cmsfund.ir/'
    if _set_website_developers:
        all_funds = _autoset_website_developers(all_funds.copy())
    return _catalog_frame(all_funds)
