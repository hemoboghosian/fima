"""Official Central Bank of Iran data, starting with policy-rate history."""
import re as _re
from urllib.parse import urljoin as _urljoin, urlsplit as _urlsplit

import jdatetime as _jd
import pandas as _pd
import requests as _requests
from bs4 import BeautifulSoup as _BeautifulSoup

from ._data import jalali_date as _jalali_date, number_series as _number_series

__all__ = ["get_cbi_policy_rates"]

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
    if title == "request rejected" or (
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
