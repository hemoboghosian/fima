"""IFB's public market-value tables and whole-file historical CSV exports."""
import csv
from datetime import date
from io import StringIO
import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup
import jdatetime as jd
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


_INDUSTRY_URL = "https://ifb.ir/SepratedByIndustry.aspx"
_MARKET_URL = "https://ifb.ir/DataReporter/GroupByMarket.aspx"
_TIMEOUT = (10, 30)
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_BASE_HEADER = ["Date", "Total Market Value", "First Market", "Second Market",
                "Modern Financial Instruments Market"]
_BASE_COLUMNS = ["TotalMarketValue", "FirstMarketValue", "SecondMarketValue",
                 "ModernFinancialInstrumentsMarketValue"]
# The colored export has stale A/B/J labels. Verify the actual HTML grid labels
# before assigning its distinct yellow/orange/red columns.
_EXPORTS = [
    ("ColoredBase", "grdMarketValuesAfterPayeColored", "btnExportExcelAfterPayecolored",
     ["Paye A", "Paye B", "Paye J", "SME"],
     ["بازار پایه زرد", "بازار پایه نارنجی", "بازار پایه قرمز", "بازار نوآفرین"],
     ["YellowBaseMarketValue", "OrangeBaseMarketValue", "RedBaseMarketValue", "SMEMarketValue"]),
    ("LetterBase", "grdMarketValuesAfterPaye", "Button1",
     ["Paye A", "Paye B", "Paye J", "SME"],
     ["بازار پایه الف", "بازار پایه ب", "بازار پایه ج", "بازار نوآفرین"],
     ["ABaseMarketValue", "BBaseMarketValue", "JBaseMarketValue", "SMEMarketValue"]),
    ("LegacyBase", "grdMarketValues", "btnExportExcel",
     ["Base Market(Auction)", "Cross Traded (Negotiation)"],
     ["بازار پایه", "بازار پایه توافقی"],
     ["AuctionBaseMarketValue", "NegotiatedBaseMarketValue"]),
]
_VALUE_COLUMNS = list(dict.fromkeys(_BASE_COLUMNS + [c for item in _EXPORTS for c in item[5]]))


def _text(value):
    return re.sub(r"\s+", " ", str(value)).strip()


def _integer(value):
    text = _text(value).translate(_DIGITS).replace(",", "").replace("٬", "")
    if text in ("", "-", "—"):
        return pd.NA
    if not re.fullmatch(r"\d+", text) or int(text) > 2**63 - 1:
        raise ValueError(f"IFB invalid nonnegative integer market value/count: {value!r}")
    return int(text)


def _percentage(value):
    text = _text(value).translate(_DIGITS).replace("/", ".").replace("٫", ".")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*[%٪]", text)
    if not match or not 0 <= float(match[1]) <= 100:
        raise ValueError(f"IFB invalid market share: {value!r}")
    return float(match[1])


def _session():
    session = requests.Session()
    # Only read-only operations, at most one retry; do not retry access denial or
    # rate limits. Do not let a Retry-After header cause an unbounded sleep.
    retry = Retry(total=1, connect=1, read=0, status=1, backoff_factor=.25,
                  status_forcelist=(502, 503, 504), allowed_methods=("GET", "POST"),
                  respect_retry_after_header=False, raise_on_status=False)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _page(session, url):
    response = session.get(url, timeout=_TIMEOUT)
    response.raise_for_status()
    return BeautifulSoup(response.content, "html.parser")


def _attrs(soup, url):
    label = soup.select_one("#lbldt")
    return {"SourceURL": url, "Snapshot": True,
            "ProviderUpdateLabel": _text(label.get_text(" ")) if label else pd.NA,
            "Unit": "IRR"}


def _container(soup):
    table = soup.select_one("#ContentPlaceHolder1_tblContainer table.tblGrp")
    if table is None:
        raise ValueError("IFB market-value table missing; response is not a valid empty dataset.")
    return table


def _industry_frames(soup):
    table = _container(soup)
    code = "\n".join(t.get_text() for t in soup.select("script:not([src])"))
    pattern = r"indArray\.push\(\[\s*'([^'\r\n]+)'\s*,\s*(\d+)\s*,\s*(\d+)\s*\]\)\s*;"
    groups = re.findall(pattern, code)
    if not groups or len(groups) != len(re.findall(r"indArray\.push\s*\(", code)):
        raise ValueError("IFB industry array missing or malformed.")
    summary = pd.DataFrame([[_text(n), _integer(v), _integer(c)] for n, v, c in groups],
                           columns=["Industry", "MarketValue", "SymbolCount"])
    heads = table.select("tr.grpHead")
    if len(heads) != len(summary) or summary.Industry.duplicated().any():
        raise ValueError("IFB industry groups are missing or duplicated.")
    shares = []
    for head, name in zip(heads, summary.Industry):
        cells = head.find_all("td", recursive=False)
        if len(cells) != 3 or _text(cells[1].get_text()) != name:
            raise ValueError("IFB industry heading schema/order changed.")
        share = re.search(r"\(([^()]+[%٪])\)", cells[2].get_text())
        if not share:
            raise ValueError("IFB industry percentage missing.")
        shares.append(_percentage(share[1]))
    summary["PercentageShare"] = shares
    records = []
    for row in table.select("tr.grpData"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 6 or not cells[0].find("a", href=True) or not cells[2].has_attr("title"):
            raise ValueError("IFB constituent schema/exact value missing.")
        link = cells[0].find("a", href=True)
        url = urljoin(_INDUSTRY_URL, link["href"])
        parsed = urlparse(url)
        ids = parse_qs(parsed.query).get("id", [])
        if parsed.netloc != "ifb.ir" or parsed.path != "/Instruments.aspx" or len(ids) != 1 or not ids[0].isdigit():
            raise ValueError("IFB constituent instrument identity/link changed.")
        records.append([ids[0], _text(link.get_text()), _text(cells[1].get_text()),
                        _integer(cells[2]["title"]), *[_text(c.get_text()) for c in cells[3:]], url])
    symbols = pd.DataFrame(records, columns=["InstrumentID", "Ticker", "InstrumentName", "MarketValue",
                                             "Market", "Industry", "SubIndustry", "DetailURL"])
    counts = symbols.groupby("Industry").size().to_dict()
    expected = dict(zip(summary.Industry, summary.SymbolCount))
    if counts != expected or symbols.InstrumentID.duplicated().any():
        raise ValueError("IFB incomplete/duplicate constituents or inconsistent industry classification/counts.")
    for frame in (summary, symbols):
        frame["MarketValue"] = pd.array(frame.MarketValue, dtype="Int64")
        frame.attrs = _attrs(soup, _INDUSTRY_URL)
    summary["SymbolCount"] = pd.array(summary.SymbolCount, dtype="Int64")
    symbols["InstrumentID"] = symbols.InstrumentID.astype("string")
    return summary, symbols


def get_ifb_market_values(group_by="industry") -> pd.DataFrame:
    """Return IFB's aggregate market-value snapshot by ``industry`` or ``market``.

    Columns: Industry/Market, MarketValue (nullable integer rials), SymbolCount
    (nullable integer), PercentageShare (percentage points). Provider totals and
    incomplete update labels are preserved in attrs; this is not dated history.
    HTTP/request errors propagate; changed/incomplete source schemas raise
    ValueError. Includes debt/funds, not just equity capitalization. See
    docs/ifb.md for source universes and each field's meaning.
    """
    if group_by not in ("industry", "market"):
        raise ValueError("group_by must be 'industry' or 'market'.")
    with _session() as session:
        soup = _page(session, _INDUSTRY_URL if group_by == "industry" else _MARKET_URL)
    if group_by == "industry":
        return _industry_frames(soup)[0]
    table = _container(soup)
    rows = table.find_all("tr", recursive=False)
    if not rows:  # Some HTML serializers add tbody.
        rows = table.select("tbody > tr")
    expected = ["بازار", "تعداد نمادها", "ارزش (ریال)", "سهم از ارزش بازار"]
    if not rows or [_text(c.get_text()) for c in rows[0].find_all(["td", "th"])] != expected:
        raise ValueError("IFB market snapshot header changed.")
    records, total = [], None
    for row in rows[1:]:
        cells = row.find_all("td", recursive=False)
        if len(cells) != 4 or any(not cells[i].has_attr("title") for i in (1, 2)):
            raise ValueError("IFB market snapshot row/exact value missing.")
        name = _text(cells[0].get_text())
        count, value = _integer(cells[1]["title"]), _integer(cells[2]["title"])
        if name == "مجموع بازارها":
            if total is not None or row is not rows[-1]:
                raise ValueError("IFB duplicate/misplaced market total.")
            total = (count, value)
        else:
            records.append([name, value, count, _percentage(cells[3].get("title", cells[3].get_text()))])
    frame = pd.DataFrame(records, columns=["Market", "MarketValue", "SymbolCount", "PercentageShare"])
    if (total is None or frame.Market.duplicated().any() or frame.SymbolCount.isna().any()
            or pd.isna(total[0]) or sum(frame.SymbolCount) != total[0]):
        raise ValueError("IFB market snapshot count/total incomplete or duplicated.")
    for col in ("MarketValue", "SymbolCount"):
        frame[col] = pd.array(frame[col], dtype="Int64")
    frame.attrs = {**_attrs(soup, _MARKET_URL), "TotalSymbolCount": total[0], "TotalMarketValue": total[1]}
    return frame


def get_ifb_symbol_market_values(ticker=None, market=None, industry=None) -> pd.DataFrame:
    """Return all industry-page constituents, optionally exact-filtered locally.

    Filters are exact source strings, combined with AND; no match is a typed
    empty table. Columns: InstrumentID (IFB ID string, not TSETMC insCode),
    Ticker, InstrumentName, MarketValue (integer rials), Market, Industry,
    SubIndustry, DetailURL. The snapshot includes financial instruments beyond
    companies. HTTP errors propagate; source/count/identity changes raise
    ValueError. No historical observation date is invented. See docs/ifb.md.
    """
    for value in (ticker, market, industry):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError("IFB filters must be nonempty strings or None.")
    with _session() as session:
        soup = _page(session, _INDUSTRY_URL)
    frame = _industry_frames(soup)[1]
    for column, value in (("Ticker", ticker), ("Market", market), ("Industry", industry)):
        if value is not None:
            frame = frame.loc[frame[column].eq(_text(value))]
    return frame.reset_index(drop=True)


def _jdate(value):
    text = _text(value).translate(_DIGITS).replace("/", "-")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError(f"IFB invalid Jalali date: {value!r}")
    try:
        return jd.date(*map(int, text.split("-")))
    except ValueError as error:
        raise ValueError(f"IFB invalid Jalali date: {value!r}") from error


def _bounds(start, end, jalali):
    if not isinstance(jalali, bool):
        raise ValueError("jalali must be True or False.")
    result = []
    for value in (start, end):
        if value is None:
            result.append(None)
        elif not isinstance(value, str):
            raise ValueError("IFB date bounds must be YYYY-MM-DD strings or None.")
        elif jalali:
            result.append(_jdate(value).isoformat())
        else:
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError("Expected YYYY-MM-DD")
                result.append(jd.date.fromgregorian(date=date.fromisoformat(value)).isoformat())
            except ValueError as error:
                raise ValueError(f"IFB invalid Gregorian date bound: {value!r}") from error
    if all(result) and result[0] > result[1]:
        raise ValueError("IFB start_date must not exceed end_date.")
    return result


def _history_export(response, spec, soup):
    regime, grid, _, suffix, labels, columns = spec
    table = soup.find("table", id="ContentPlaceHolder1_" + grid)
    heading = table.find("tr") if table is not None else None
    expected = ["تاریخ", "جمع ارزش بازار", "بازار اول", "بازار دوم", "ابزارهای نوین مالی"] + labels
    if heading is None or [_text(c.get_text()) for c in heading.find_all(["td", "th"])] != expected:
        raise ValueError(f"IFB {regime} history grid/classification header changed.")
    if "text/csv" not in response.headers.get("Content-Type", "").lower():
        raise ValueError(f"IFB {regime} export is not CSV.")
    try:
        rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig")), strict=True))
    except (UnicodeError, csv.Error) as error:
        raise ValueError(f"IFB {regime} malformed CSV export.") from error
    header = _BASE_HEADER + suffix
    if not rows or rows[0] != header:
        raise ValueError(f"IFB {regime} CSV header changed.")
    records = []
    for row in rows[1:]:
        if len(row) == len(header) + 1 and row[-1] == "":
            row = row[:-1]
        if len(row) != len(header):
            raise ValueError(f"IFB {regime} CSV row length changed/truncated.")
        jdate = _jdate(row[0]).isoformat()
        if ((regime == "ColoredBase" and jdate < "1398-06-25") or
            (regime == "LetterBase" and not "1395-12-23" <= jdate <= "1398-06-24") or
            (regime == "LegacyBase" and jdate > "1395-12-22")):
            raise ValueError(f"IFB {regime} export repeats another market regime or changes coverage.")
        records.append([jdate, *[_integer(v) for v in row[1:]]])
    # Compare every date on the displayed first page, not just a nonempty file.
    visible = set()
    for row in table.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) == len(header) and not row.find("table"):
            visible.add(_jdate(cells[0].get_text()).isoformat())
    if not visible or not visible.issubset({row[0] for row in records}):
        raise ValueError(f"IFB {regime} export omits visible observations or is empty.")
    # Construct integer extension arrays before pandas can coerce missing large
    # integers to float64 (which would lose individual rials above 2**53).
    frame = pd.DataFrame({"JalaliDate": [r[0] for r in records]})
    for i, column in enumerate(_BASE_COLUMNS + columns, 1):
        frame[column] = pd.array([r[i] for r in records], dtype="Int64")
    frame["MarketRegime"] = regime
    return frame


def get_ifb_market_value_history(start_date=None, end_date=None, *, jalali=True) -> pd.DataFrame:
    """Return all three official market-value CSV histories, filtered inclusively.

    Bounds are YYYY-MM-DD Jalali strings by default, Gregorian with jalali=False.
    Both calendars are always returned, plus MarketRegime and regime-specific
    nullable integer rial columns. Missing source totals are never reconstructed.
    Identical duplicate rows are normalized with DuplicateRowCount in attrs;
    conflicting dates fail. Uses full exports, not first-page grid scraping.
    HTTP errors propagate; malformed/incomplete exports raise ValueError. No
    guarantee is made about dates absent from IFB's archives. See docs/ifb.md
    for the complete schema, regime transitions, units and source limitations.
    """
    start, end = _bounds(start_date, end_date, jalali)
    frames, counts = [], {}
    with _session() as session:
        soup = _page(session, _MARKET_URL)
        hidden = {t["name"]: t.get("value", "") for t in soup.select("input[type=hidden][name]")}
        if not hidden.get("__VIEWSTATE"):
            raise ValueError("IFB history WebForms state missing.")
        for spec in _EXPORTS:
            data = {**hidden, "ctl00$ContentPlaceHolder1$" + spec[2]: ""}
            response = session.post(_MARKET_URL, data=data, timeout=_TIMEOUT)
            response.raise_for_status()
            frame = _history_export(response, spec, soup)
            counts[spec[0]] = len(frame)
            frames.append(frame)
    frame = pd.concat(frames, ignore_index=True)
    original_count = len(frame)
    frame = frame.drop_duplicates()
    duplicate_count = original_count - len(frame)
    if frame.JalaliDate.duplicated().any():
        raise ValueError("IFB conflicting duplicate history dates; cannot select an authoritative record.")
    for column in _VALUE_COLUMNS:
        frame[column] = frame[column].astype("Int64")
    frame.insert(1, "GregorianDate", pd.to_datetime(frame.JalaliDate.map(lambda d: _jdate(d).togregorian())))
    frame = frame[["JalaliDate", "GregorianDate", "MarketRegime"] + _VALUE_COLUMNS]
    if start is not None:
        frame = frame.loc[frame.JalaliDate.ge(start)]
    if end is not None:
        frame = frame.loc[frame.JalaliDate.le(end)]
    frame = frame.sort_values("JalaliDate").reset_index(drop=True)
    frame.attrs = {"SourceURL": _MARKET_URL, "Snapshot": False, "Unit": "IRR",
                   "ExportRowCounts": counts, "DuplicateRowCount": duplicate_count}
    return frame
