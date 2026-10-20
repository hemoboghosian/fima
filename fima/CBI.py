"""Official Central Bank of Iran policy, inflation and currency-rate data."""
import datetime as _dt
import re as _re
import xml.etree.ElementTree as _ET
from urllib.parse import urljoin as _urljoin, urlsplit as _urlsplit

import jdatetime as _jd
import pandas as _pd
import requests as _requests
from bs4 import BeautifulSoup as _BeautifulSoup

from ._data import jalali_date as _jalali_date, number_series as _number_series

__all__ = ["get_cbi_policy_rates", "get_cbi_inflation_rates",
           "get_cbi_exchange_rates", "get_cbi_ets_rates"]

_URL = "https://cbi.ir/PolicyRates/policyrates_fa.aspx"
_TIMEOUT = (10, 30)
_ACCESS_ERROR = ("CBI rejected ordinary programmatic access from this environment "
                 "(Request Rejected page); provider access is unavailable")
# The public page rejects requests' default headers. No browser state is used.
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _header(text):
    text = text.replace("ي", "ی").replace("ك", "ک")
    return _re.sub(r"[\s\u200b-\u200f\u202a-\u202e\u2066-\u2069]", "", text)


# Verified against CBI's official policyrates_en.aspx, including Repo Cut-off Rate.
_FIELDS = {
    _header("تاریخ"): "JalaliDate",
    _header("نرخ بازار بین‌بانکی(%)"): "InterbankRate",
    _header("حداقل نرخ توافق بازخرید(%)"): "RepoCutoffRate",
    _header("نرخ اعتبارگیری قاعده‌مند(%)"): "StandingLendingRate",
    _header("نرخ سپرده‌گذاری قاعده‌مند(%)"): "StandingDepositRate",
}
_COLUMNS = ["JalaliDate", "GregorianDate", "InterbankRate", "RepoCutoffRate",
            "StandingLendingRate", "StandingDepositRate"]


def _page(response):
    response.raise_for_status()
    soup = _BeautifulSoup(response.content, "html.parser")
    title = soup.title.get_text(" ", strip=True).casefold() if soup.title else ""
    body = soup.get_text(" ", strip=True).casefold()
    if title in ("request rejected", "درخواست رد شد") or (
            "the requested url was rejected" in body and "support id" in body
            and not soup.find("select")):
        raise ValueError(_ACCESS_ERROR)
    return soup


def _form_state(soup):
    selectors = [s for s in soup.select("select[name]")
                 if s["name"].split("$")[-1] == "ddlYear"]
    if len(selectors) != 1:
        raise ValueError("CBI year selector is missing or ambiguous")
    selector = selectors[0]
    form = selector.find_parent("form")
    if form is None or form.get("method", "").lower() != "post":
        raise ValueError("CBI year selector has no ASP.NET POST form")
    years = {}
    options = selector.find_all("option")
    for option in options:
        value = option.get("value", option.get_text(strip=True))
        if not value.strip() or option.has_attr("disabled"):
            continue
        year = value.strip().translate(_DIGITS)
        label = option.get_text(strip=True).translate(_DIGITS)
        if not _re.fullmatch(r"[0-9]{4}", year) or label != year or year in years:
            raise ValueError("CBI advertised years are malformed or ambiguous")
        years[year] = value
    if not years:
        raise ValueError("CBI year selector advertises no available years")
    selected = selector.find("option", selected=True) or (options[0] if options else None)
    current = (selected.get("value", selected.get_text(strip=True)).strip().translate(_DIGITS)
               if selected is not None else None)
    hidden = {i["name"]: i.get("value", "")
              for i in form.select('input[type="hidden"][name]')}
    if not hidden.get("__VIEWSTATE"):
        raise ValueError("CBI ASP.NET __VIEWSTATE is missing or empty")
    return form, selector["name"], years, current, hidden


def _parse_year(soup, year):
    matches = []
    for table in soup.find_all("table"):
        headings = table.find_all("th")
        labels = [_header(h.get_text(" ", strip=True)) for h in headings]
        if len(labels) == len(_FIELDS) and set(labels) == set(_FIELDS):
            matches.append((table, headings, labels))
    if len(matches) != 1:
        raise ValueError("CBI policy-rate table is missing, ambiguous or has unexpected headers")
    table, headings, labels = matches[0]
    if any(h.get("colspan", "1") != "1" or h.get("rowspan", "1") != "1" for h in headings):
        raise ValueError("CBI policy-rate table has unsupported grouped headers")
    header_row = headings[0].parent
    if any(h.parent is not header_row for h in headings) or header_row.find("td"):
        raise ValueError("CBI policy-rate table has an unexpected header structure")
    rows = []
    for row in table.find_all("tr"):
        if row is header_row:
            continue
        cells = row.find_all("td", recursive=False)
        if row.find("th") or len(cells) != len(labels) or any(
                c.get("colspan", "1") != "1" or c.get("rowspan", "1") != "1" for c in cells):
            raise ValueError("CBI policy-rate table has an unexpected row structure")
        rows.append([c.get_text(" ", strip=True) for c in cells])
    # No empty-year state has been observed at CBI. Treat it as incomplete retrieval.
    if not rows:
        raise ValueError("CBI policy-rate table is empty; complete history cannot be verified")
    result = _pd.DataFrame(rows, columns=[_FIELDS[label] for label in labels])
    dates = result["JalaliDate"].str.translate(_DIGITS)
    if not dates.str.fullmatch(r"[0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}").all():
        raise ValueError("CBI contains a missing or malformed Jalali date")
    result["JalaliDate"] = dates.map(_jalali_date).astype("string")
    if not result["JalaliDate"].str.startswith(year + "-").all():
        raise ValueError("CBI returned dates outside the requested year")
    result["GregorianDate"] = _pd.to_datetime(result["JalaliDate"].map(
        lambda d: _jd.date(*map(int, d.split("-"))).togregorian())).astype("datetime64[ns]")
    for column in _COLUMNS[2:]:
        result[column] = _number_series(result[column]).astype("float64")
        if result[column].isin([float("inf"), float("-inf")]).any():
            raise ValueError(f"CBI contains a nonfinite {column}")
    return result[_COLUMNS]


def get_cbi_policy_rates():
    """Return complete policy-rate history advertised by the CBI year selector.

    No parameters are required. All available Jalali years are discovered from
    https://cbi.ir/PolicyRates/policyrates_fa.aspx and fetched sequentially using
    the page's ordinary ASP.NET postbacks in a single HTTP session.

    Returns
    -------
    pandas.DataFrame
        Chronologically ascending, exact-deduplicated records with a RangeIndex.
        JalaliDate is an ASCII YYYY-MM-DD pandas string; GregorianDate is
        datetime64[ns]. InterbankRate, RepoCutoffRate, StandingLendingRate and
        StandingDepositRate are float64 percentages in percentage points
        (24.0 means 24%), with NaN for missing provider values. No filling occurs.
        RepoCutoffRate is CBI's minimum accepted repo rate, not the interbank rate.

    Raises
    ------
    RuntimeError
        If access fails (including CBI's HTTP-200 Request Rejected page), the
        page/schema changes, or any advertised year cannot
        be retrieved and validated (including an empty table). Annual failures
        identify the year; no partial history is returned. The original network
        or parsing exception is available as the exception cause.
    """
    with _requests.Session() as session:
        session.headers.update(_HEADERS)
        try:
            response = session.get(_URL, timeout=_TIMEOUT)
            soup = _page(response)
            form, field, years, selected, hidden = _form_state(soup)
        except (_requests.RequestException, ValueError) as exc:
            raise RuntimeError(f"Unable to retrieve CBI policy-rate history: {exc}") from exc
        frames = []
        for year in years:
            try:
                if selected != year:
                    action = _urljoin(response.url, form.get("action") or response.url)
                    target = _urlsplit(action)
                    if target.scheme != "https" or target.netloc != _urlsplit(response.url).netloc:
                        raise ValueError("CBI postback action is not on the same HTTPS origin")
                    payload = dict(hidden)
                    payload.update({"__EVENTTARGET": field, "__EVENTARGUMENT": "", field: years[year]})
                    response = session.post(action, data=payload, timeout=_TIMEOUT)
                    soup = _page(response)
                    form, field, advertised, selected, hidden = _form_state(soup)
                    if advertised != years:
                        raise ValueError("CBI advertised years changed during retrieval; retry the call")
                if selected != year:
                    raise ValueError("CBI postback did not select the requested year")
                frames.append(_parse_year(soup, year))
            except (_requests.RequestException, ValueError, OverflowError) as exc:
                raise RuntimeError(f"CBI policy rates: failed advertised year {year}: {exc}") from exc
    return (_pd.concat(frames, ignore_index=True).drop_duplicates()
            .sort_values("JalaliDate", kind="stable").reset_index(drop=True))


_INFLATION_URL = "https://cbi.ir/Inflation/Inflation_FA.aspx"
_EXCHANGE_URL = "https://cbi.ir/exratesadv/exratesadv_fa.aspx"
_ETS_URL = "https://cbi.ir/etsratesadv/etsratesadv_fa.aspx"
_MONTHS = {_header(name): f"{i:02d}" for i, name in enumerate(
    ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
     "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"], 1)}
_FX_COLUMNS = ["JalaliDate", "GregorianDate", "CurrencyCode", "CurrencyName", "CurrencyUnit"]
_TRANSACTIONS = {"cash": "اسکناس", "transfer": "حواله"}


def _form(soup):
    form = soup.find("form")
    if form is None or form.get("method", "").lower() != "post":
        raise ValueError("CBI ASP.NET POST form is missing")
    hidden = {i["name"]: i.get("value", "") for i in form.select('input[type="hidden"][name]')}
    if not hidden.get("__VIEWSTATE"):
        raise ValueError("CBI ASP.NET __VIEWSTATE is missing or empty")
    return form, hidden


def _field(soup, suffix):
    fields = [x for x in soup.select("[name]") if x["name"].endswith("$" + suffix)]
    if len(fields) != 1:
        raise ValueError(f"CBI form field {suffix} is missing or ambiguous")
    return fields[0]


def _submit(session, response, soup, values):
    form, hidden = _form(soup)
    action = _urljoin(response.url, form.get("action") or response.url)
    if _urlsplit(action).scheme != "https" or _urlsplit(action).netloc != _urlsplit(response.url).netloc:
        raise ValueError("CBI postback action is not on the same HTTPS origin")
    hidden.update(values)
    return session.post(action, data=hidden, timeout=_TIMEOUT)


def _rates(values):
    # CBI's earliest annual inflation observation uses this explicit missing marker.
    result = _number_series(values.replace("-.-", None)).astype("float64")
    if result.isin([float("inf"), float("-inf")]).any():
        raise ValueError("CBI contains a nonfinite rate")
    return result


def _inflation_table(soup, frequency, year=None):
    expected = ["ماه" if frequency == "monthly" else "سال", "نرخ تورم"]
    matches = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if rows and [_header(c.get_text(" ", strip=True)) for c in rows[0].find_all(["td", "th"])] == list(map(_header, expected)):
            matches.append(rows)
    if len(matches) != 1:
        raise ValueError("CBI inflation table is missing, ambiguous or has unexpected headers")
    records = []
    for row in matches[0][1:]:
        cells = row.find_all("td", recursive=False)
        if len(cells) != 2 or any(c.has_attr("colspan") or c.has_attr("rowspan") for c in cells):
            raise ValueError("CBI inflation table has an unexpected row structure")
        period, rate = [c.get_text(" ", strip=True) for c in cells]
        if frequency == "monthly":
            month = _MONTHS.get(_header(period))
            if month is None:
                raise ValueError(f"CBI has an unknown Persian month: {period!r}")
            records.append([f"{year}-{month}", rate])
        else:
            match = _re.fullmatch(r"([0-9]{4})\s*(?:\((.+)\))?", period.translate(_DIGITS))
            if not match:
                raise ValueError(f"CBI has a malformed annual year: {period!r}")
            records.append([match[1], rate, match[2] or _pd.NA])
    if not records:
        raise ValueError("CBI inflation table is empty; completeness cannot be verified")
    columns = ["JalaliMonth", "InflationRate"] if frequency == "monthly" else ["JalaliYear", "InflationRate", "Note"]
    result = _pd.DataFrame(records, columns=columns)
    result[columns[0]] = result[columns[0]].astype("string")
    result["InflationRate"] = _rates(result["InflationRate"])
    if "Note" in result:
        result["Note"] = result["Note"].astype("string")
    return result


def get_cbi_inflation_rates(frequency="monthly"):
    """Return CBI's complete monthly or annual inflation table.

    Parameters
    ----------
    frequency : {"monthly", "annual"}, default "monthly"
        Monthly means CBI's rate 'ending in the month', not a monthly CPI
        change or point-to-point rate. Available years are discovered dynamically.

    Returns
    -------
    pandas.DataFrame
        Monthly: JalaliMonth (string YYYY-MM), InflationRate (float64 percentage
        points). Annual: JalaliYear (string), InflationRate (float64), Note
        (nullable string, including base-year annotations). No daily dates are
        invented. Exact duplicates are removed and periods sorted ascending.

    Raises
    ------
    ValueError
        For an invalid frequency.
    RuntimeError
        For provider rejection, transport/schema errors, or any failed advertised
        year. No partial monthly history is returned.
    """
    if frequency not in ("monthly", "annual"):
        raise ValueError("frequency must be 'monthly' or 'annual'")
    with _requests.Session() as session:
        session.headers.update(_HEADERS)
        try:
            response = session.get(_INFLATION_URL, timeout=_TIMEOUT)
            soup = _page(response)
            if frequency == "annual":
                frames = [_inflation_table(soup, frequency)]
            else:
                _, field, years, selected, _ = _form_state(soup)
                frames = []
                ordered = ([selected] if selected in years else []) + [y for y in years if y != selected]
                for year in ordered:
                    try:
                        if selected != year:
                            response = _submit(session, response, soup, {
                                "__EVENTTARGET": field, "__EVENTARGUMENT": "", field: years[year]})
                            soup = _page(response)
                            _, field, advertised, selected, _ = _form_state(soup)
                            if advertised != years:
                                raise ValueError("CBI advertised inflation years changed during retrieval")
                        if selected != year:
                            raise ValueError("CBI postback did not select the requested year")
                        frames.append(_inflation_table(soup, frequency, year))
                    except (_requests.RequestException, ValueError) as exc:
                        raise RuntimeError(f"CBI inflation: failed advertised year {year}: {exc}") from exc
        except (_requests.RequestException, ValueError) as exc:
            raise RuntimeError(f"Unable to retrieve CBI inflation: {exc}") from exc
    result = _pd.concat(frames, ignore_index=True).drop_duplicates()
    return result.sort_values(result.columns[0], kind="stable").reset_index(drop=True)


def _date_range(start_date, end_date, jalali):
    if not isinstance(jalali, bool):
        raise ValueError("jalali must be a boolean")
    if (start_date is None) != (end_date is None):
        raise ValueError("Supply both start_date and end_date for bounded history, or neither for latest rates")
    if start_date is None:
        return None, None

    def parse(value):
        if isinstance(value, _dt.datetime):
            value = value.date()
        if isinstance(value, _dt.date) and not jalali:
            return value
        if isinstance(value, _jd.date) and jalali:
            return value.togregorian()
        text = str(value).strip().translate(_DIGITS)
        if not _re.fullmatch(r"[0-9]{4}[-/][0-9]{2}[-/][0-9]{2}", text):
            raise ValueError(f"Invalid date: {value!r}; use YYYY-MM-DD")
        date = (_jd.date if jalali else _dt.date)(*map(int, text.replace("/", "-").split("-")))
        return date.togregorian() if jalali else date

    start, end = parse(start_date), parse(end_date)
    if start > end or (end - start).days >= 366:
        raise ValueError("Date range must be ascending and include at most 366 calendar days")
    return start, end


def _currency_queries(currency):
    if currency is None:
        return None
    queries = [currency] if isinstance(currency, str) else currency
    if not isinstance(queries, (list, tuple)) or not queries or any(
            not isinstance(q, str) or not q.strip() for q in queries):
        raise ValueError("currency must be a code, exact Persian name, nonempty list/tuple, or None")
    return queries


def _denomination(name, required=False):
    name = " ".join(name.replace("ي", "ی").replace("ك", "ک").split())
    for prefix, unit in [("یک هزار ", 1000), ("یکصد ", 100), ("صد ", 100), ("ده ", 10), ("یک ", 1)]:
        if name.startswith(prefix):
            return unit, name[len(prefix):]
    if required:
        raise ValueError(f"CBI has an unsupported currency denomination: {name!r}")
    return 1, name


def _currency_code(code):
    match = _re.fullmatch(r"([A-Z]{3})([1-9][0-9]*)?", code.strip().upper())
    if not match:
        raise ValueError(f"CBI has a malformed currency code: {code!r}")
    return match[1], int(match[2] or 1)


def _catalog(soup, ets):
    tables = [t for t in soup.find_all("table") if t.find("tr") and
              _header(t.find("tr").get_text(" ", strip=True)) == _header("کد ارز عنوان ارز")]
    if len(tables) != 1:
        raise ValueError("CBI currency catalog table is missing or has unexpected headers")
    result = []
    for row in tables[0].find_all("tr")[1:]:
        cells = row.find_all("td", recursive=False)
        checkbox = row.find("input", attrs={"type": "checkbox"})
        if len(cells) != 3 or checkbox is None or not checkbox.get("name"):
            raise ValueError("CBI currency catalog has an unexpected row structure")
        code = cells[1].get_text(strip=True).upper()
        base, _ = _currency_code(code)
        label = cells[2].get_text(" ", strip=True)
        unit, name = _denomination(label, required=ets)
        result.append(dict(code=code, base=base, name=name, unit=unit,
                           checkbox=checkbox["name"], value=checkbox.get("value", "on")))
    if not result or len({r["base"] for r in result}) != len(result):
        raise ValueError("CBI currency catalog is empty or ambiguous")
    return result


def _select_currencies(catalog, queries):
    if queries is None:
        return catalog
    selected = []
    for query in queries:
        matches = [r for r in catalog if query.strip().upper() in (r["code"], r["base"]) or
                   _header(_denomination(query)[1]) == _header(r["name"])]
        if len(matches) != 1:
            raise ValueError(f"Unknown or ambiguous CBI currency: {query!r}")
        if matches[0] not in selected:
            selected.append(matches[0])
    return selected


def _export_payload(soup, selected, start, end, transaction=None, side=None):
    data = {}
    for control in soup.find_all("select"):
        option = control.find("option", selected=True) or control.find("option")
        if option is None:
            raise ValueError("CBI form has an empty selector")
        data[control["name"]] = option["value"]
    outputs = [x for x in soup.select('input[type="radio"][name]')
               if x["name"].endswith("$Output") and x.get("value") == "rdbXML"]
    if len(outputs) != 1:
        raise ValueError("CBI XML export radio control is missing or ambiguous")
    data[outputs[0]["name"]] = outputs[0]["value"]
    for row in selected:
        data[row["checkbox"]] = row["value"]
    if start is None:
        data[_field(soup, "ddlWeeks")["name"]] = "0"
        button = _field(soup, "btnShowRateByWeek")
    else:
        for prefix, date in [("Start", start), ("End", end)]:
            jdate = _jd.date.fromgregorian(date=date)
            for part, value in [("Year", jdate.year), ("Month", jdate.month), ("Day", jdate.day)]:
                field = _field(soup, "ddl" + prefix + part)
                if str(value) not in [o.get("value") for o in field.find_all("option")]:
                    raise ValueError("Requested date is outside CBI's advertised date selectors")
                data[field["name"]] = str(value)
        button = _field(soup, "btnShowRateByDate")
    data[button["name"]] = button.get("value", "")
    if transaction is not None:
        for suffix, value in [("payTypeDropDown", _TRANSACTIONS[transaction]), ("payPriceDropDown", side)]:
            field = _field(soup, suffix)
            if value not in [o.get("value") for o in field.find_all("option")]:
                raise ValueError(f"CBI {suffix} no longer advertises the expected mode")
            data[field["name"]] = value
    return data


def _export_rows(response, selected, start, end, ets):
    response.raise_for_status()
    if not response.content.lstrip(b"\xef\xbb\xbf \r\n").startswith((b"<?xml", b"<exchangerates")):
        _page(response)  # Preserve the exact known rejection cause for live tests.
        raise ValueError("CBI did not return an XML history export")
    try:
        root = _ET.fromstring(response.content.decode("utf-8-sig"))
    except (_ET.ParseError, UnicodeError) as exc:
        raise ValueError("CBI returned malformed history XML") from exc
    if root.tag != "exchangerates" or any(c.tag != "currency" for c in root):
        raise ValueError("CBI history XML has an unexpected root or structure")
    catalog = {r["base"]: r for r in selected}
    records = []
    for currency in root:
        code = currency.get("id", "").strip().upper()
        base, unit = _currency_code(code)
        if base not in catalog:
            raise ValueError("CBI returned an unrequested currency")
        source = catalog[base]
        if ets:
            unit = source["unit"]
        for rate in currency:
            if rate.tag == "summary":
                continue
            if rate.tag != "rate" or [x.tag for x in rate] != ["date", "value"]:
                raise ValueError("CBI history XML has a malformed rate observation")
            raw_date = (rate.findtext("date") or "").translate(_DIGITS)
            if not _re.fullmatch(r"[0-9]{4}/[0-9]{1,2}/[0-9]{1,2}", raw_date):
                raise ValueError("CBI history contains a malformed observation date")
            jdate = _jalali_date(raw_date)
            gdate = _jd.date(*map(int, jdate.split("-"))).togregorian()
            if start is not None and not start <= gdate <= end:
                raise ValueError("CBI returned observations outside the requested date range")
            records.append([jdate, gdate, code, source["name"], unit, rate.findtext("value")])
    result = _pd.DataFrame(records, columns=_FX_COLUMNS + ["Rate"])
    for column in ["JalaliDate", "CurrencyCode", "CurrencyName"]:
        result[column] = result[column].astype("string")
    result["GregorianDate"] = _pd.to_datetime(result["GregorianDate"]).astype("datetime64[ns]")
    result["CurrencyUnit"] = result["CurrencyUnit"].astype("int64")
    result["Rate"] = _rates(result["Rate"])
    return result.drop_duplicates().reset_index(drop=True)


def _exchange_history(currency, start, end, transactions=None):
    queries = _currency_queries(currency)
    ets = transactions is not None
    url = _ETS_URL if ets else _EXCHANGE_URL
    frames = []
    expected_catalog = None
    with _requests.Session() as session:
        session.headers.update(_HEADERS)
        for transaction in transactions if ets else [None]:
            sides = []
            for side in ["Buy", "Sell"] if ets else [None]:
                try:
                    response = session.get(url, timeout=_TIMEOUT)
                    soup = _page(response)
                    catalog = _catalog(soup, ets)
                except (_requests.RequestException, ValueError) as exc:
                    raise RuntimeError(f"Unable to discover CBI {'ETS' if ets else 'exchange'} rates: {exc}") from exc
                selected = _select_currencies(catalog, queries)
                try:
                    identity = [(r["code"], r["name"], r["unit"]) for r in selected]
                    if expected_catalog is not None and identity != expected_catalog:
                        raise ValueError("CBI selected currency catalog changed during retrieval")
                    expected_catalog = identity
                    payload = _export_payload(soup, selected, start, end, transaction, side)
                    response = _submit(session, response, soup, payload)
                    result = _export_rows(response, selected, start, end, ets)
                    if ets:
                        if result.duplicated(_FX_COLUMNS).any():
                            raise ValueError("CBI has conflicting duplicate side observations")
                        sides.append(result.rename(columns={"Rate": side + "Rate"}))
                    else:
                        frames.append(result.rename(columns={"Rate": "ExchangeRate"}))
                except (_requests.RequestException, ValueError, OverflowError) as exc:
                    raise RuntimeError(f"CBI {'ETS ' + transaction + ' ' + side if ets else 'exchange'} retrieval failed: {exc}") from exc
            if ets:
                result = sides[0].merge(sides[1], on=_FX_COLUMNS, how="outer", validate="one_to_one")
                result["TransactionType"] = _pd.Series(transaction, index=result.index, dtype="string")
                frames.append(result[_FX_COLUMNS + ["TransactionType", "BuyRate", "SellRate"]])
    result = _pd.concat(frames, ignore_index=True).drop_duplicates()
    order = ["JalaliDate", "CurrencyCode"] + (["TransactionType"] if ets else [])
    return result.sort_values(order, kind="stable").reset_index(drop=True)


def get_cbi_exchange_rates(currency=None, start_date=None, end_date=None, *, jalali=False):
    """Return the normal CBI exchange dataset, separately from ETS buy/sell quotes.

    currency accepts a code, exact normalized Persian name, list/tuple, or None
    for all advertised currencies. With no dates, retrieve the provider's latest
    report. For history supply both inclusive dates (YYYY-MM-DD, Gregorian by
    default; jalali=True for Jalali), at most 366 calendar days per call. Requests
    use the official advanced-search XML export, never one request per day.

    Returns a sorted DataFrame with JalaliDate (string), GregorianDate
    (datetime64[ns]), CurrencyCode/CurrencyName (string), CurrencyUnit (int64),
    ExchangeRate (float64, NaN for missing rates). Values are Iranian rial per
    CurrencyUnit foreign units. Provider codes such as JPY100 are preserved.
    The current source defines its rate using prior-business-day remittance
    transactions at Iran's currency/gold exchange center; older regimes differ.
    Only source rate records are returned; no holiday/calendar filling occurs.

    Invalid inputs or unknown/ambiguous currencies raise ValueError. Access,
    HTTP, transport, malformed export or schema failures raise RuntimeError
    (with original cause). A valid empty XML report returns a typed empty table.
    """
    _currency_queries(currency)
    start, end = _date_range(start_date, end_date, jalali)
    return _exchange_history(currency, start, end)


def get_cbi_ets_rates(currency=None, transaction_type="all", start_date=None, end_date=None, *, jalali=False):
    """Return ETS cash/transfer buy and sell quotes in one wide DataFrame.

    transaction_type is cash (اسکناس), transfer (حواله), or all; the two exact
    Persian aliases are also accepted. Currency/date arguments and the latest
    default/366-day historical bound follow get_cbi_exchange_rates. Each mode
    uses the official advanced-search XML exports for Buy and Sell, merged on
    source date/currency/unit. There is no daily crawl or inferred mid-price.

    Columns: JalaliDate (string), GregorianDate (datetime64[ns]), CurrencyCode,
    CurrencyName (string), CurrencyUnit (int64), TransactionType (string),
    BuyRate/SellRate (float64, percentage scaling does not apply). Rates are
    Iranian rial for the published foreign denomination, parsed from CBI's
    Persian description, including 10/100/1000 units. No conversion or holiday
    filling is performed; repeated source-dated records remain source records.
    Buy/Sell faithfully retain CBI's labels; no customer perspective is assumed.

    ValueError signals invalid inputs/currency; RuntimeError signals provider,
    network or schema failure. No failed request is replaced with partial data.
    Valid empty XML reports produce a typed empty table.
    """
    aliases = {"اسکناس": "cash", "حواله": "transfer"}
    if not isinstance(transaction_type, str):
        raise ValueError("transaction_type must be cash, transfer or all")
    transaction_type = aliases.get(transaction_type, transaction_type)
    if transaction_type not in ("cash", "transfer", "all"):
        raise ValueError("transaction_type must be cash, transfer or all")
    _currency_queries(currency)
    start, end = _date_range(start_date, end_date, jalali)
    transactions = ["cash", "transfer"] if transaction_type == "all" else [transaction_type]
    return _exchange_history(currency, start, end, transactions)
