"""Discover and retrieve public CODAL filings by Persian report name."""

from collections.abc import Mapping
from contextlib import ExitStack, contextmanager, suppress
from copy import deepcopy
from datetime import timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from threading import Lock
from time import monotonic, time
from unicodedata import normalize
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit

import jdatetime
import pandas as pd
import requests

from .codal_reports import (
    _decode_codal_html,
    _parse_codal_html,
    _sheet_options,
    get_codal_financial_statements,
    get_codal_monthly_activity,
    get_codal_tables,
)

__all__ = [
    "CodalRequestError", "list_codal_report_types", "search_codal_filings",
    "fetch_codal_report", "get_codal_data",
]

_SEARCH_HOST = "search.codal.ir"
_TAXONOMY = f"https://{_SEARCH_HOST}/api/search/v1/categories"
_SEARCH = f"https://{_SEARCH_HOST}/api/search/v2/q"
_REPORT_ROOT = "https://www.codal.ir"
_REPORT_HOSTS = {"www.codal.ir", "codal.ir"}
_CAPTCHA_CONTROLS = (
    "#captchaImage, .g-recaptcha, #challenge-form input:not([type=hidden]), #challenge-form button"
)
_CAPTCHA_MARKUP = re.compile(rb"captchaTitle|captchaImage|g-recaptcha|challenge-form", re.IGNORECASE)
_TAXONOMY_TTL = 600
_taxonomy_cache = None
_taxonomy_lock = Lock()
_rate_limit = None
_rate_limit_lock = Lock()
_TRANSLATION = str.maketrans("يكى۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "یکی01234567890123456789")
_PERSIAN_MONTHS = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)
_PERIOD_TITLE = re.compile(r"دوره\s+([0-9]{1,2})\s*ماهه\s+منتهی\s+به\s+([0-9]{4}/[0-9]{1,2}/[0-9]{1,2})")
_DATE = re.compile(r"([0-9]{4})/([0-9]{1,2})(?:/([0-9]{1,2}))?")
_PUBLISHED = re.compile(r"([0-9]{4}/[0-9]{2}/[0-9]{2})\s+([0-9]{2}:[0-9]{2}:[0-9]{2})")
_FINANCIAL_LABELS = (
    "اطلاعات و صورتهای مالی میاندوره ای",
    "اطلاعات و صورتهای مالی سالانه",
    "اطلاعات و صورتهای مالی پایان دوره",
)
_REPORT_ALIASES = {
    "گزارش فعالیت ماهانه": ("گزارش عملکرد ماهانه", "گزارش ماهانه"),
    "صورت‌های مالی": ("صورت مالی", "اطلاعات و صورت‌های مالی"),
    "صورت‌های مالی میان‌دوره‌ای": (
        "صورت مالی میان دوره‌ای", "اطلاعات و صورتهای مالی میاندوره ای",
        "اطلاعات و صورت مالی میان‌دوره‌ای",
    ),
    "صورت‌های مالی سالانه": (
        "صورت مالی سالانه", "اطلاعات و صورتهای مالی سالانه", "اطلاعات و صورت مالی سالانه",
        "اطلاعات و صورتهای مالی پایان دوره",
    ),
    "افشای اطلاعات بااهمیت": ("اطلاعات بااهمیت", "افشا اطلاعات با اهمیت"),
    "آگهی دعوت به مجمع": ("دعوت به مجمع",),
    "تصمیمات مجمع": (),
}
_STATEMENT_ALIASES = {
    "سود و زیان": ("صورت سود و زیان",),
    "صورت وضعیت مالی": ("ترازنامه",),
    "جریان وجوه نقد": (
        "صورت جریان وجوه نقد", "صورت جریان های نقدی", "جریان های نقدی", "صورت جریان وجوه نقدی",
    ),
}
_SEARCH_COLUMNS = (
    "TracingNo", "Symbol", "CompanyName", "Title", "LetterCode", "CategoryId",
    "CategoryName", "LetterTypeId", "LetterTypeName", "ReportingPeriodEnd",
    "DurationMonths", "PublishDateTime", "IsCorrected", "IsConsolidated",
    "IsAudited", "IsIssuerReport", "HasHtml", "Url", "ProviderMetadata",
)


class CodalRequestError(OSError):
    """CODAL could not provide a complete, usable HTTP response."""


class _HumanVerification(CodalRequestError):
    def __init__(self, message, *, url=None, search=False):
        super().__init__(message)
        self.url = url
        self.search = search


def _text(value):
    return " ".join(normalize("NFKC", value).translate(_TRANSLATION)
                    .replace("\u200c", " ").replace("\u200d", "")
                    .replace("\u200e", "").replace("\u200f", "").replace("\u0640", "").split())


def _key(value):
    return _text(value).replace(" ", "")


def _aliases(groups):
    return {_key(value): name for name, aliases in groups.items() for value in (name, *aliases)}


_REPORT_NAMES = _aliases(_REPORT_ALIASES)
_STATEMENT_NAMES = _aliases(_STATEMENT_ALIASES)


def _rate_limit_error(retry_after):
    wait = f" (Retry-After: {retry_after})" if retry_after else ""
    return CodalRequestError(
        f"CODAL temporarily rate-limited the request (HTTP 429){wait}. Avoid retrying immediately."
    )


def _retry_delay(retry_after):
    if re.fullmatch(r"[0-9]+", retry_after):
        return float(retry_after)
    try:
        date = parsedate_to_datetime(retry_after)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return max(0, date.timestamp() - time())
    except (ValueError, OverflowError, OSError):
        return 0


def _remember_rate_limit(retry_after):
    global _rate_limit
    delay = _retry_delay(retry_after) if retry_after else 0
    if delay > 0:
        with _rate_limit_lock:
            deadline = monotonic() + delay
            if _rate_limit is None or deadline > _rate_limit[0]:
                _rate_limit = (deadline, retry_after)


def _check_rate_limit():
    with _rate_limit_lock:
        if _rate_limit is not None and monotonic() < _rate_limit[0]:
            raise _rate_limit_error(_rate_limit[1])


def _codal_host(url, hosts):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.netloc.lower() not in hosts:
        raise CodalRequestError("CODAL returned a URL outside the expected HTTPS hosts")
    return parts.netloc


def _check_status(status, retry_after, host):
    if status == 429:
        _remember_rate_limit(retry_after)
        raise _rate_limit_error(retry_after)
    if status != 200:
        raise CodalRequestError(f"CODAL returned HTTP {status} from {host}")


def _checked_response(response, report, search):
    host = _codal_host(response.url, _REPORT_HOSTS if report else {_SEARCH_HOST})
    status = response.status_code
    retry_after = response.headers.get("Retry-After")
    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if (report and status in (200, 403) and content_type == "text/html"
            and _CAPTCHA_MARKUP.search(response.content)):
        try:
            page = _decode_codal_html(response.content)
        except ValueError:
            if status == 200:
                raise
        else:
            if page.select_one(_CAPTCHA_CONTROLS):
                raise _HumanVerification("CODAL report requires human verification", url=response.url)
            if status == 200 and page.select_one("#captchaTitle, #challenge-form"):
                raise _HumanVerification("CODAL report requires human verification")
    _check_status(status, retry_after, host)
    expected = "text/html" if report else "application/json"
    if content_type != expected:
        raise CodalRequestError(f"CODAL did not return {expected} from {host}")
    if report:
        return response
    try:
        data = response.json()
    except ValueError as exc:
        raise CodalRequestError("CODAL returned malformed JSON") from exc
    if search and isinstance(data, dict) and data.get("IsAttacker") is True:
        raise _HumanVerification("CODAL search requires human verification", url=response.url, search=True)
    return data


def _http_get(session, url, params, report):
    hosts = _REPORT_HOSTS if report else {_SEARCH_HOST}
    content_type = "text/html" if report else "application/json"
    search = url == _SEARCH
    for _ in range(5):
        host = _codal_host(url, hosts)
        _check_rate_limit()
        try:
            response = session.get(
                url, params=params, timeout=(10, 25), allow_redirects=False,
                headers={"Accept": content_type, "User-Agent": "fima"},
            )
        except requests.RequestException as exc:
            raise CodalRequestError(f"CODAL request to {host} failed: {exc}") from exc
        if response.is_redirect:
            url = urljoin(response.url, response.headers["Location"])
            params = None
            continue
        return _checked_response(response, report, search)
    raise CodalRequestError("CODAL exceeded the redirect limit")


class _InteractiveSession:
    def __init__(self, http, resources):
        self.http = http
        self.resources = resources
        self.browser = None

    def get(self, url, params, report):
        if self.browser is None:
            try:
                return _http_get(self.http, url, params, report)
            except _HumanVerification as challenge:
                if challenge.url is None:
                    raise
                _check_rate_limit()
                from ._codal_browser import open_browser

                self.browser = self.resources.enter_context(open_browser())
                self.browser.verify(challenge.url, search=challenge.search, params=params)
        _check_rate_limit()
        try:
            response = self.browser.get(url, params, report)
            return _checked_response(response, report, url == _SEARCH)
        except _HumanVerification as exc:
            raise CodalRequestError("CODAL still requires human verification in the browser session") from exc


@contextmanager
def _codal_session(interactive):
    if type(interactive) is not bool:
        raise ValueError("interactive must be True or False")
    with ExitStack() as resources:
        http = resources.enter_context(requests.Session())
        yield _InteractiveSession(http, resources) if interactive else http


def _get(session, url, *, params=None, report=False):
    if isinstance(session, _InteractiveSession):
        return session.get(url, params, report)
    return _http_get(session, url, params, report)


def _taxonomy(payload):
    """Read the exchange-issuer branch of CODAL's category → publisher → type hierarchy."""
    records = {}
    try:
        if not isinstance(payload, list):
            raise ValueError
        for category in payload:
            category_id = category["Code"]
            category_name = category["Name"]
            for publisher in category["PublisherTypes"]:
                if _key(publisher["Name"]) != _key("ناشران") or category_id == -1:
                    continue
                for letter_type in publisher["LetterTypes"]:
                    type_id = letter_type["Id"]
                    type_name = letter_type["Name"]
                    if (type(category_id) is not int or type(type_id) is not int
                            or not _key(category_name) or not _key(type_name)):
                        raise ValueError
                    pair = (category_id, type_id)
                    labels = (category_name, type_name)
                    if records.setdefault(pair, labels) != labels:
                        raise ValueError
    except (TypeError, KeyError, AttributeError, ValueError) as exc:
        raise CodalRequestError("Unexpected CODAL category and letter-type taxonomy") from exc
    if not records:
        raise CodalRequestError("CODAL taxonomy is missing exchange-issuer letter types")
    return [(category, category_name, kind, type_name)
            for (category, kind), (category_name, type_name) in records.items()]


def _taxonomy_path():
    return Path.home() / ".cache" / "fima" / "codal-taxonomy-v1.json"


def _read_taxonomy_snapshot(path):
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        # Older snapshots recorded the end of validation, so their fetch time is unknown.
        fetch_started_at = snapshot["fetch_started_at"]
        now_monotonic = monotonic()
        now = time()
        if (type(fetch_started_at) not in (int, float)
                or not now - _TAXONOMY_TTL < fetch_started_at <= now):
            return None
        deadline = now_monotonic + (_TAXONOMY_TTL - (now - fetch_started_at))
        return deadline, tuple(_taxonomy(snapshot["payload"]))
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return None


def _write_taxonomy_snapshot(path, fetch_started_at, payload):
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False,
        ) as file:
            temporary = Path(file.name)
            json.dump({"fetch_started_at": fetch_started_at, "payload": payload}, file)
        temporary.replace(path)
    except (OSError, RecursionError):
        pass  # Ignore disk and serialization failures for the optional snapshot.
    finally:
        if temporary is not None:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)


def _issuer_taxonomy(session):
    global _taxonomy_cache
    with _taxonomy_lock:
        if _taxonomy_cache and monotonic() < _taxonomy_cache[0]:
            return _taxonomy_cache[1]
        try:
            path = _taxonomy_path()
        except RuntimeError:  # A home directory may be unavailable.
            path = None
        snapshot = _read_taxonomy_snapshot(path) if path is not None else None
        if snapshot is not None and monotonic() < snapshot[0]:
            _taxonomy_cache = snapshot
            return snapshot[1]

        deadline = monotonic() + _TAXONOMY_TTL
        fetch_started_at = time()
        payload = _get(session, _TAXONOMY)
        records = tuple(_taxonomy(payload))
        _taxonomy_cache = (deadline, records)
        if path is not None:
            _write_taxonomy_snapshot(path, fetch_started_at, payload)
        return records


def list_codal_report_types() -> pd.DataFrame:
    """Return current category IDs, category names, letter-type IDs and Persian names for issuers.

    The DataFrame has one row per category and letter-type pair. A validated
    provider response can be reused for up to ten minutes across processes.
    The CODAL filing's textual LetterCode is a separate field in search results.
    Raises CodalRequestError if the public taxonomy is unavailable or malformed.
    """
    with requests.Session() as session:
        records = _issuer_taxonomy(session)
    return pd.DataFrame(records, columns=("CategoryId", "CategoryName", "LetterTypeId", "LetterTypeName"))


def _resolve(session, report_type):
    value = _key(report_type) if isinstance(report_type, str) else ""
    statement = _STATEMENT_NAMES.get(value)
    name = "صورت‌های مالی" if statement else _REPORT_NAMES.get(value)
    taxonomy = _issuer_taxonomy(session)
    if name in {"صورت‌های مالی", "صورت‌های مالی میان‌دوره‌ای", "صورت‌های مالی سالانه"}:
        family = "financial"
        labels = {_key(label) for label in _FINANCIAL_LABELS}
        choices = [row for row in taxonomy if _key(row[3]) in labels]
    elif name in {"آگهی دعوت به مجمع", "تصمیمات مجمع"}:
        family = "announcement"
        choices = [row for row in taxonomy if _key(row[3]).startswith(_key(name))]
    else:
        family = "monthly" if name == "گزارش فعالیت ماهانه" else "announcement"
        choices = [row for row in taxonomy if _key(row[3]) == (_key(name) if name else value)]
    if not choices and name:
        raise CodalRequestError(f"CODAL taxonomy no longer lists the requested report family {name!r}")
    if not choices:
        valid = "، ".join((*_REPORT_ALIASES, *_STATEMENT_ALIASES))
        raise ValueError(f"نام گزارش {report_type!r} شناخته نشد. نام‌های قابل استفاده: {valid}")
    if name and family in {"financial", "monthly"} and len({row[0] for row in choices}) != 1:
        raise CodalRequestError(f"CODAL taxonomy returned conflicting categories for {name!r}")
    if len(choices) > 1 and name is None:
        raise ValueError(f"نام گزارش {report_type!r} مبهم است. نام کامل گزارش را وارد کنید.")
    return name, family, statement, choices


def _period(value):
    if value is None:
        return None
    value = _text(value) if isinstance(value, str) else ""
    for month, label in enumerate(_PERSIAN_MONTHS, 1):
        natural = re.fullmatch(rf"{label} ([0-9]{{4}})", value)
        if natural:
            value = f"{natural[1]}/{month:02d}"
            break
    match = _DATE.fullmatch(value)
    if not match:
        raise ValueError("period must be a Jalali month or date (for example ۱۴۰۵/۰۶ or شهریور ۱۴۰۵)")
    year, month, day = (int(part) if part is not None else None for part in match.groups())
    jdatetime.date(year, month, day or 1)
    if day == 0:
        raise ValueError("Invalid Jalali day")
    return f"{year:04d}/{month:02d}" + (f"/{day:02d}" if day else "")


def _published(value):
    match = _PUBLISHED.fullmatch(_text(value))
    if not match:
        raise ValueError("invalid CODAL publication time")
    return f"{match[1]} {match[2]}"


def _query_value(url, key):
    values = [
        value for parameter, items in parse_qs(urlsplit(url).query).items()
        if parameter.lower() == key.lower() for value in items
    ]
    return values[0] if len(values) == 1 else None


def _filing_record(letter, choice, family):
    category_id, category_name, type_id, type_name = choice
    try:
        tracing = letter["TracingNo"]
        symbol, company, title, letter_code, url = (
            letter[key] for key in ("Symbol", "CompanyName", "Title", "LetterCode", "Url")
        )
        has_html = letter["HasHtml"]
        if (type(tracing) is not int or tracing < 1 or type(has_html) is not bool
                or not all(isinstance(field, str) for field in (symbol, company, title, letter_code, url))):
            raise ValueError
        url = urljoin(_REPORT_ROOT, url) if url else None
        linked_type = _query_value(url, "let") if url else None
        if linked_type is not None and linked_type != str(type_id):
            raise ValueError(f"filing {tracing} has a different letter type")
        published = _published(letter["PublishDateTime"])
        text = _text(title)
        corrected = bool(re.search(r"\(\s*اصلاحیه\s*\)|^اصلاحیه(?:\s|$)", text))
        match = _PERIOD_TITLE.search(text) if family in {"monthly", "financial"} else None
        duration = int(match[1]) if match else None
        date = _period(match[2]) if match else None
        consolidated = audited = issuer_report = None
        if match:
            consolidated = "تلفیقی" in _key(text[:match.start()])
            audited = {"حسابرسیشده": True, "حسابرسینشده": False}.get(
                next((word for word in ("حسابرسینشده", "حسابرسیشده")
                      if word in _key(text[match.end():])), None)
            )
            suffix = re.sub(r"\(\s*(?:حسابرسی\s*(?:ن?شده)|اصلاحیه)\s*\)", "", text[match.end():])
            issuer_report = not suffix.strip()
    except (TypeError, KeyError, AttributeError, ValueError) as exc:
        raise CodalRequestError(f"Unexpected CODAL filing metadata: {exc}") from exc
    return dict(zip(_SEARCH_COLUMNS, (
        tracing, symbol, company, title, letter_code, category_id, category_name, type_id,
        type_name, date, duration, published, corrected, consolidated, audited,
        issuer_report, has_html, url, letter,
    )))


def _pages(session, symbol, choice, max_pages):
    params = {"Symbol": symbol, "Category": choice[0], "LetterType": choice[2]}
    counts = None
    seen = set()
    for number in range(1, max_pages + 1):
        data = _get(session, _SEARCH, params={**params, "PageNumber": number})
        try:
            pages, total, letters = data["Page"], data["Total"], data["Letters"]
            if (type(pages) is not int or type(total) is not int or not isinstance(letters, list)
                    or data.get("IsAttacker") is not False or min(pages, total) < 0
                    or (total == 0 and (pages not in (0, 1) or letters))
                    or (total > 0 and (pages < number or not letters))):
                raise ValueError
            ids = {letter["TracingNo"] for letter in letters}
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise CodalRequestError("Unexpected CODAL search response or pagination fields") from exc
        if pages > max_pages:
            raise CodalRequestError(f"CODAL returned {pages} pages, above max_pages={max_pages}; search incomplete")
        if counts not in (None, (pages, total)) or seen & ids or len(ids) != len(letters):
            raise CodalRequestError("CODAL search changed during pagination; search incomplete")
        counts = (pages, total)
        seen.update(ids)
        yield from letters
        if number >= pages:
            if len(seen) != total:
                raise CodalRequestError("CODAL search row count disagrees with its total; search incomplete")
            return


def _search_symbol(symbol, max_pages):
    if not isinstance(symbol, str) or not _key(symbol):
        raise ValueError("symbol must be a non-empty stock symbol")
    if type(max_pages) is not int or max_pages < 1:
        raise ValueError("max_pages must be a positive integer")
    return _text(symbol)


def _search_rows(session, symbol, resolved, period, max_pages):
    name, family, _, choices = resolved
    if period and family == "announcement":
        raise ValueError("This report type has no supported reporting-period date. Search without period.")
    records = {}
    for choice in choices:
        for letter in _pages(session, symbol, choice, max_pages):
            row = _filing_record(letter, choice, family)
            if _text(row["Symbol"]) != symbol:
                continue
            if period and not (row["ReportingPeriodEnd"] or "").startswith(period):
                continue
            if name == "صورت‌های مالی سالانه" and row["DurationMonths"] != 12:
                continue
            if name == "صورت‌های مالی میان‌دوره‌ای" and row["DurationMonths"] not in range(1, 12):
                continue
            tracing = row["TracingNo"]
            if tracing in records:
                if records[tracing] != row:
                    raise CodalRequestError(f"CODAL returned conflicting search metadata for filing {tracing}")
            else:
                records[tracing] = row
                yield row


def search_codal_filings(
    symbol: str, report_type: str, period: str | None = None, *, max_pages: int = 100,
    interactive: bool = False,
) -> pd.DataFrame:
    """Find CODAL filings by stock symbol and Persian report_type.

    period accepts a Jalali reporting month or date for monthly and financial
    filings. Search keeps originals, corrections, subsidiaries, and both
    scopes under the exact publisher symbol. max_pages bounds each taxonomy
    query. An empty frame means the completed search found no matching rows.
    interactive=True allows human verification on CODAL in visible Chromium
    when the provider presents a supported challenge. Invalid inputs raise
    ValueError. Failed or incomplete requests raise CodalRequestError.
    """
    period = _period(period)
    symbol = _search_symbol(symbol, max_pages)
    with _codal_session(interactive) as session:
        rows = sorted(
            _search_rows(session, symbol, _resolve(session, report_type), period, max_pages),
            key=lambda row: (row["PublishDateTime"], row["TracingNo"]), reverse=True,
        )
    return pd.DataFrame(rows, columns=_SEARCH_COLUMNS, dtype=object)



def _statement_name(statement):
    if statement is None:
        return None
    name = _STATEMENT_NAMES.get(_key(statement)) if isinstance(statement, str) else None
    if name is None:
        raise ValueError(f"نام صورت مالی را از این گزینه‌ها انتخاب کنید: {'، '.join(_STATEMENT_ALIASES)}")
    return name


def _report_page(session, url):
    if not re.fullmatch(r"/Reports/[a-z]+\.aspx", urlsplit(url).path, re.IGNORECASE):
        raise ValueError("CODAL filing does not link to a supported public HTML report")
    response = _get(session, url, report=True)
    return response, _decode_codal_html(response.content)


def _sheet_matches(title, statement):
    return isinstance(title, str) and _STATEMENT_NAMES.get(_key(title)) == statement


def _sheet_url(url, sheet_id):
    parts = urlsplit(url)
    query = [item for item in parts.query.split("&")
             if item and item.partition("=")[0].lower() != "sheetid"]
    return urlunsplit(parts._replace(query="&".join([*query, f"sheetId={sheet_id}"])))


def _company_key(name):
    return _key(re.sub(r"^شرکت\s+", "", _text(name))) if isinstance(name, str) else ""


def _validate_report(report, filing):
    metadata, page, source = (report[key] for key in ("ProviderMetadata", "PageMetadata", "Source"))
    tracing = filing["TracingNo"]
    if metadata.get("tracingNo") != tracing or metadata.get("type") != filing["LetterTypeId"]:
        raise ValueError(f"Downloaded report identity disagrees with CODAL search for filing {tracing}")
    publisher_symbol = _text(filing["Symbol"])
    symbols = {_text(page[key]) for key in ("Symbol", "DisplaySymbol") if page.get(key)}
    if publisher_symbol not in symbols:
        raise ValueError(f"Downloaded report symbol disagrees with CODAL search for filing {tracing}")
    if filing["IsIssuerReport"] and (
        not _company_key(page.get("CompanyName"))
        or _company_key(page["CompanyName"]) != _company_key(filing["CompanyName"])
    ):
        raise ValueError(f"Downloaded report company disagrees with CODAL search for filing {tracing}")
    for field, source_field in (("DurationMonths", "period"), ("IsConsolidated", "isConsolidated"),
                                ("IsAudited", "isAudited")):
        if filing[field] is not None and filing[field] != metadata.get(source_field):
            raise ValueError(f"Downloaded report {field} disagrees with CODAL search for filing {tracing}")
    expected_date = filing["ReportingPeriodEnd"]
    if expected_date and (_period(metadata.get("periodEndToDate")) != expected_date
                          or _period(page.get("PeriodEndDate")) != expected_date):
        raise ValueError(f"Downloaded report period end disagrees with CODAL search for filing {tracing}")
    if expected_date and metadata.get("kind") != int(filing["IsCorrected"]):
        raise ValueError(f"Downloaded report correction status disagrees with CODAL search for filing {tracing}")
    if metadata.get("publishDateTime") and _published(metadata["publishDateTime"]) != filing["PublishDateTime"]:
        raise ValueError(f"Downloaded report publication time disagrees with CODAL search for filing {tracing}")
    serial = _query_value(source["Url"], "LetterSerial")
    if not serial or (source["LetterSerial"] and source["LetterSerial"] != serial):
        raise ValueError(f"Downloaded report letter serial disagrees with its source URL for filing {tracing}")


def _downloaded_report(response, page, filing, requested):
    source = {"Url": response.url, "SearchUrl": filing["Url"]}
    return _parse_codal_html(response.content, page, source, requested)


def _fetch_report(session, filing, statement, *, revision_only=False, source_url=None):
    if not filing["HasHtml"] or not filing["Url"]:
        raise ValueError(f"CODAL filing {filing['TracingNo']} has no public HTML report")
    response, page = _report_page(session, source_url or filing["Url"])
    requested = None
    report = None
    menu = _sheet_options(page) if statement else None
    if revision_only and menu:
        selected = [row for row in menu if row["IsSelected"]]
        if len(selected) == 1:
            name = _STATEMENT_NAMES.get(_key(selected[0]["Title"]))
            sheet_id = selected[0]["SheetId"]
            if name and name != statement and re.fullmatch(r"[0-9]+", sheet_id):
                try:
                    report = _downloaded_report(response, page, filing, sheet_id)
                except ValueError:
                    # The landing page may lack a usable structured statement.
                    pass
                else:
                    statement, requested = name, sheet_id
    if menu is not None and report is None:
        sheet_ids = [row["SheetId"] for row in menu if _sheet_matches(row["Title"], statement)]
        if len(sheet_ids) != 1 or not re.fullmatch(r"[0-9]+", sheet_ids[0]):
            raise ValueError(f"CODAL filing {filing['TracingNo']} has no unique sheet for {statement!r}")
        requested = sheet_ids[0]
        if not any(row["SheetId"] == requested and row["IsSelected"] for row in menu):
            response, page = _report_page(session, _sheet_url(response.url, requested))
    if report is None:
        report = _downloaded_report(response, page, filing, requested)
    _validate_report(report, filing)
    if statement:
        matching = [sheet["SheetId"] for sheet in report["Sheets"]
                    if _sheet_matches(sheet["ProviderMetadata"].get("title_Fa"), statement)]
        actual = report["Coverage"]["SelectedSheetId"]
        if (len(matching) != 1 or requested not in (None, matching[0])
                or actual not in (None, matching[0])):
            raise ValueError(f"Downloaded CODAL sheet does not match {statement!r}")
        report["Coverage"]["RequestedSheetId"] = matching[0]
    report["Filing"] = deepcopy(dict(filing))
    return report


def fetch_codal_report(
    filing: Mapping | pd.Series, *, statement: str | None = None, interactive: bool = False,
) -> dict:
    """Download a row from search_codal_filings, optionally selecting a Persian statement name.

    Returns a report compatible with get_codal_tables, with the original HTML
    bytes, SHA-256, filing metadata, and loaded sheet coverage. interactive=True
    allows a human to complete a supported CODAL challenge in visible Chromium.
    Raises ValueError for an unavailable sheet, unsupported HTML, or wrong filing
    identity, and CodalRequestError for access or transport failures.
    """
    if not isinstance(filing, (Mapping, pd.Series)) or any(key not in filing for key in _SEARCH_COLUMNS):
        raise TypeError("filing must be a row from search_codal_filings")
    statement = _statement_name(statement)
    with _codal_session(interactive) as session:
        return _fetch_report(session, filing, statement)


def _revision_reference(link):
    url = link.get("Href")
    serial = _query_value(url, "LetterSerial") if url else None
    trace = re.findall(r"\(\s*([0-9]+)\s*\)", _text(link["Text"]))
    return (int(trace[0]) if len(trace) == 1 else None), serial


def _revision_target(link, reports, source_url):
    trace, serial = _revision_reference(link)
    report = reports.get(trace)
    target = urlsplit(urljoin(source_url, link.get("Href") or ""))
    if target.scheme == "https" and target.netloc.lower() in _REPORT_HOSTS and serial and report and serial in {
        _query_value(report["Source"]["SearchUrl"], "LetterSerial"),
        _query_value(report["Source"]["Url"], "LetterSerial"),
    }:
        return trace
    raise ValueError("CODAL revision points outside the matching filings or has a conflicting identity")


def _select_revision(reports):
    by_id = {report["Filing"]["TracingNo"]: report for report in reports}
    previous = {}
    forward = []
    for tracing, report in by_id.items():
        links = report["PageMetadata"].get("RevisionLinks", [])
        source_url = report["Source"]["Url"]
        for link in links:
            element = link["ElementId"]
            if element.endswith("hlPrevVersion"):
                earlier = _revision_target(link, by_id, source_url)
                earlier_time = by_id[earlier]["Filing"]["PublishDateTime"]
                if tracing in previous or earlier_time >= report["Filing"]["PublishDateTime"]:
                    raise ValueError("CODAL provided conflicting previous filing revisions")
                previous[tracing] = earlier
            elif element.endswith("hlNewVersion"):
                forward.append((tracing, _revision_target(link, by_id, source_url)))
        if bool(tracing in previous) != report["Filing"]["IsCorrected"]:
            raise ValueError(f"CODAL filing {tracing} has no consistent correction link")
    latest = by_id.keys() - previous.values()
    if len(latest) == 1:
        current = latest.pop()
        chain = []
        while current is not None and current not in chain:
            chain.append(current)
            current = previous.get(current)
        if current is None and len(chain) == len(by_id):
            for older, newer in forward:
                if chain.index(older) <= chain.index(newer):
                    raise ValueError("CODAL provided conflicting newer filing revisions")
            return by_id[chain[0]], list(reversed(chain))
    raise ValueError("Multiple incompatible CODAL filings matched. Inspect search_codal_filings().")


def _monthly_predecessor_url(report, filing):
    """Use a filing's public previous-version link when it identifies the search row."""
    links = [link for link in report["PageMetadata"].get("RevisionLinks", [])
             if link["ElementId"].endswith("hlPrevVersion")]
    serial = _query_value(filing["Url"], "LetterSerial") if filing["Url"] else None
    if len(links) != 1 or not serial or _revision_reference(links[0]) != (filing["TracingNo"], serial):
        return None
    source = report["Source"]["Url"]
    url = urljoin(source, links[0]["Href"])
    origin = urlsplit(source)
    parts = urlsplit(url)
    if (parts.scheme == "https" and parts.netloc == origin.netloc
            and parts.path.lower() == origin.path.lower() == "/reports/monthlyactivity.aspx"
            and parts.query.lower().startswith("letterserial=") and "&" not in parts.query):
        return url
    return None


def _fetch_revisions(session, filings, statement, family):
    # A complete linear chain has one original and a strictly increasing publication time.
    if (sum(not row["IsCorrected"] for row in filings) != 1
            or len({row["PublishDateTime"] for row in filings}) != len(filings)):
        raise ValueError("Multiple incompatible CODAL filings matched. Inspect search_codal_filings().")
    ordered = sorted(filings, key=lambda row: row["PublishDateTime"], reverse=True)
    reports = []
    for row in ordered:
        url = _monthly_predecessor_url(reports[-1], row) if reports and family == "monthly" else None
        reports.append(_fetch_report(session, row, statement, revision_only=bool(reports), source_url=url))
    return _select_revision(reports)


def _period_identity(row):
    return row["ReportingPeriodEnd"], row["DurationMonths"], row["IsAudited"]


def _candidate_filings(rows, family, period, audited, duration_months):
    filings = []
    for row in rows:
        if (not row["IsIssuerReport"] or row["IsConsolidated"]
                or (family == "monthly" and row["DurationMonths"] != 1)
                or (audited is not None and row["IsAudited"] is not audited)
                or (duration_months is not None and row["DurationMonths"] != duration_months)):
            continue
        if period and filings and _period_identity(row) != _period_identity(filings[0]):
            # Later pages cannot remove an ambiguity within an explicitly requested period.
            _ambiguous_period()
        filings.append(row)
    if filings and period is None:
        newest = max(row["ReportingPeriodEnd"] for row in filings)
        filings = [row for row in filings if row["ReportingPeriodEnd"] == newest]
        if len({_period_identity(row) for row in filings}) > 1:
            _ambiguous_period()
    return filings


def _ambiguous_period():
    raise ValueError("Multiple CODAL periods, durations or audit statuses matched. "
                     "Specify an exact period, duration_months or audited.")


def _raw_cells(report):
    tables = get_codal_tables(report)
    frame = pd.concat([table["Cells"] for table in tables], ignore_index=True)
    for key in ("Source", "ProviderMetadata", "PageMetadata", "Coverage"):
        frame.attrs[key] = deepcopy(report[key])
    frame.attrs["Tables"] = [{key: value for key, value in table.items() if key != "Cells"} for table in tables]
    return frame


def get_codal_data(
    symbol: str, report_type: str, period: str | None = None, *,
    statement: str | None = None, audited: bool | None = None,
    duration_months: int | None = None, raw: bool = False, max_pages: int = 100,
    interactive: bool = False,
) -> pd.DataFrame:
    """Retrieve one CODAL report as a DataFrame using a symbol and Persian report name.

    Pass a stock symbol such as فولاد and a Persian report_type such as گزارش ماهانه.
    period accepts a Jalali month or date and defaults to the latest reporting
    date. Financial statements default to سود و زیان. A named statement can
    also be used as report_type. For financial ambiguity audited and
    duration_months can select a filing using its audit status and duration.
    raw=True returns source cells instead of normalized observations.
    max_pages bounds each taxonomy query. The automatic workflow selects the
    issuer's own separate report and follows verified correction links.
    interactive=True opens visible Chromium when CODAL requires supported
    human verification and continues in the same browser session.
    The returned frame carries source and filing metadata in its attrs.

    Raises ValueError for unknown names, missing or incompatible filings,
    unavailable sheets, or unsupported normalization. Raises CodalRequestError
    for network, access, and incomplete-search failures.
    """
    period = _period(period)
    symbol = _search_symbol(symbol, max_pages)
    statement = _statement_name(statement)
    if audited is not None and type(audited) is not bool:
        raise ValueError("audited must be True, False or None")
    if duration_months is not None and (type(duration_months) is not int or not 1 <= duration_months <= 12):
        raise ValueError("duration_months must be from 1 to 12")
    with _codal_session(interactive) as session:
        resolved = _resolve(session, report_type)
        _, family, implied, _ = resolved
        if implied and statement and implied != statement:
            raise ValueError("report_type and statement identify different financial sheets")
        if family == "financial":
            statement = statement or implied or "سود و زیان"
        elif statement or audited is not None or duration_months is not None:
            raise ValueError("statement, audited and duration_months apply to financial statements")
        if family == "announcement" and not raw:
            raise ValueError("This CODAL report type requires raw=True or search_codal_filings()")
        rows = _search_rows(session, symbol, resolved, period, max_pages)
        if family == "announcement":
            filing = next(rows, None)
            if filing is None or next(rows, None) is not None:
                raise ValueError("Use search_codal_filings() and fetch_codal_report() to choose one notice")
            report = _fetch_report(session, filing, None)
            revisions = [filing["TracingNo"]]
        else:
            filings = _candidate_filings(rows, family, period, audited, duration_months)
            if not filings:
                raise ValueError(f"No matching separate CODAL report for {symbol!r} and period {period!r}")
            report, revisions = _fetch_revisions(session, filings, statement, family)
    if raw:
        frame = _raw_cells(report)
    elif family == "monthly":
        frame = get_codal_monthly_activity(report)
    else:
        frame = get_codal_financial_statements(report)
    frame.attrs["Filing"] = report["Filing"]
    frame.attrs["RevisionTracingNos"] = revisions
    return frame
