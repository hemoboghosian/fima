"""Published valuation inputs from Aswath Damodaran, NYU Stern."""

from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from io import BytesIO
import json
import math
import re
from threading import Lock
from time import monotonic, sleep
from typing import Literal
from unicodedata import normalize
from urllib.parse import urljoin, urlsplit
import warnings
from zipfile import ZipFile

from bs4 import BeautifulSoup
import pandas as pd
import requests

__all__ = ["get_damodaran_datasets", "get_damodaran_data"]

_SOURCE = "Aswath Damodaran, NYU Stern"
_HOME = "https://pages.stern.nyu.edu/~adamodar/"
_PAGES = _HOME + "New_Home_Page/"
_CURRENT = _PAGES + "datacurrent.html"
_ARCHIVE = _PAGES + "dataarchived.html"
_DEFINITIONS = _PAGES + "datafile/variable.htm"
_USAGE = _PAGES + "datahistory.html#rules"
_COUNTRY = "country_risk_premiums"
_BETAS = "industry_betas"
_WACC = "industry_cost_of_capital"
_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")
_DATE_PATTERN = rf"({'|'.join(_MONTHS)}) ([0-9]{{1,2}}), ([0-9]{{4}})"
_MAX_BYTES = 8 * 1024 * 1024
_CATALOG_TTL = 6 * 3600
_ARTIFACT_TTL = 24 * 3600


@dataclass(frozen=True)
class _Family:
    name: str
    aliases: tuple[str, ...]
    current_title: str
    archive_title: str
    description: str
    frequency: str
    editions: tuple[str, ...]
    regions: tuple[str | None, ...]
    file_format: str


_FAMILIES = {
    _COUNTRY: _Family(
        "Country Risk Premiums", ("country risk premiums", "country risk premium"),
        "Risk Premiums for Other Markets", "Risk Premiums for Other Markets",
        "Sovereign default spreads and rating, CDS and frontier equity risk estimates.",
        "Periodic", ("2025-01", "2026-01", "2026-04", "2026-07"), (None,), "xlsx",
    ),
    _BETAS: _Family(
        "Industry Betas", ("industry betas", "industry beta", "betas", "بتای صنعت"),
        "Levered and Unlevered Betas by Industry", "Levered and Unlevered Betas by Industry",
        "Levered, unlevered and cash-adjusted industry betas with other risk measures.",
        "Annual", ("2025-01", "2026-01"), ("Global", "US"), "xls",
    ),
    _WACC: _Family(
        "Industry Cost of Capital", ("industry cost of capital", "cost of capital", "wacc"),
        "Costs of Capital by Industry Sector", "Costs of Capital by Industry",
        "Published USD cost of equity, debt and capital by industry.",
        "Annual", ("2025-01", "2026-01"), ("Global", "US"), "xls",
    ),
}
_REGIONS = {"global": "Global", "world": "Global", "us": "US", "u.s.": "US",
            "united states": "US"}


def _norm(text):
    return " ".join(normalize("NFKC", text).casefold().split()) if isinstance(text, str) else ""


def _aliases():
    aliases = {}
    for dataset, family in _FAMILIES.items():
        for alias in (dataset, *family.aliases):
            key = _norm(alias)
            if key in aliases:
                raise RuntimeError(f"Duplicate Damodaran dataset alias: {alias}")
            aliases[key] = dataset
    return aliases


_ALIASES = _aliases()


def _dataset(value):
    try:
        return _ALIASES[_norm(value)]
    except KeyError:
        raise ValueError(f"Unknown Damodaran dataset {value!r}. Choose from {', '.join(_FAMILIES)}.") from None


def _flag(value, name):
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be True or False.")


class _SourceError(ValueError):
    """An invalid provider response or unsupported layout."""


class _Session(requests.Session):
    def get_redirect_target(self, response):
        # Requests otherwise reads the body to prepare a redirect even with
        # allow_redirects=False. The downloader checks Location before each hop.
        return None


@dataclass(frozen=True)
class _Download:
    url: str
    retrieved_at: datetime
    etag: str | None
    last_modified: str | None
    body: bytes


@dataclass(frozen=True)
class _Edition:
    dataset: str
    region: str | None
    edition: str
    url: str
    catalog_url: str


@dataclass(frozen=True)
class _Cached:
    download: _Download
    value: dict | pd.DataFrame
    checked: float
    revalidated_at: datetime | None = None


_catalogs = OrderedDict()
_artifacts = OrderedDict()
_cache_lock = Lock()


def _cached(cache, key):
    with _cache_lock:
        entry = cache.get(key)
        if entry is not None:
            cache.move_to_end(key)
        return entry


def _remember(cache, key, entry, capacity):
    with _cache_lock:
        previous = cache.get(key)
        if previous is not None and previous.download.retrieved_at > entry.download.retrieved_at:
            return
        cache[key] = entry
        cache.move_to_end(key)
        if len(cache) > capacity:
            cache.popitem(last=False)


def _official_url(url, file_format=None):
    parts = urlsplit(url)
    if (not url.startswith(_HOME) or parts.netloc != "pages.stern.nyu.edu"
            or parts.query or parts.fragment):
        raise _SourceError("Unsafe source URL outside the official NYU Stern HTTPS origin")
    if file_format is None:
        if url not in (_CURRENT, _ARCHIVE):
            raise _SourceError(f"Unexpected catalog URL {url!r}")
    elif not re.fullmatch(r"/~adamodar/pc/(?:datasets|archives)/[A-Za-z0-9_.-]+\."
                          + file_format, parts.path, re.IGNORECASE):
        raise _SourceError(f"Unexpected {file_format.upper()} artifact URL {url!r}")
    return url


_MIME_TYPES = {
    None: {"text/html"},
    "xls": {"application/vnd.ms-excel", "application/octet-stream"},
    "xlsx": {"application/vnd.openxmlformats", "application/octet-stream",
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
}


def _retry_delay(response):
    retry_after = response.headers.get("Retry-After", "").strip()
    if not retry_after:
        return 0.25
    if retry_after.isascii() and retry_after.isdecimal() and len(retry_after) < 10:
        delay = int(retry_after)
    else:
        try:
            delay = max(0, (parsedate_to_datetime(retry_after) -
                            datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError) as exc:
            raise _SourceError(f"HTTP {response.status_code} with invalid Retry-After") from exc
    if delay > 5:
        raise _SourceError(f"HTTP {response.status_code} with a longer retry delay than supported")
    return delay


def _read_body(response, file_format, deadline):
    mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if mime not in _MIME_TYPES[file_format]:
        raise _SourceError(f"HTTP 200 with unexpected Content-Type {mime!r}")
    length = response.headers.get("Content-Length")
    if length is not None:
        if not re.fullmatch(r"[0-9]{1,12}", length) or int(length) > _MAX_BYTES:
            raise _SourceError(f"Invalid or oversized Content-Length: {length!r}")
        length = int(length)
    body = bytearray()
    for chunk in response.iter_content(chunk_size=16384):
        body.extend(chunk)
        if len(body) > _MAX_BYTES:
            raise _SourceError("Response exceeds the byte limit")
        if monotonic() >= deadline:
            raise _SourceError("Download exceeded its time budget")
    encoding = response.headers.get("Content-Encoding", "identity").lower()
    if not body or (encoding == "identity" and length is not None and length != len(body)):
        raise _SourceError("Empty or truncated response")
    return bytes(body)


def _download(session, requested, file_format=None, previous=None):
    deadline = monotonic() + 60
    for attempt in range(2):
        url = requested
        try:
            for hop in range(4):
                _official_url(url, file_format)
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise _SourceError(f"Download exceeded its time budget at {url}")
                headers = {"Accept-Encoding": "identity"}
                if previous is not None and url == previous.url:
                    if previous.etag:
                        headers["If-None-Match"] = previous.etag
                    if previous.last_modified:
                        headers["If-Modified-Since"] = previous.last_modified
                with session.get(url, stream=True, allow_redirects=False, headers=headers,
                                 timeout=(min(5, remaining), min(20, remaining))) as response:
                    status = response.status_code
                    if status in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        if not location or hop == 3:
                            raise _SourceError(f"HTTP {status} with missing or excessive redirects at {url}")
                        url = urljoin(url, location)
                        continue
                    if status == 304 and len(headers) > 1:
                        return None
                    if status in (429, 500, 502, 503, 504) and attempt == 0:
                        delay = _retry_delay(response)
                        break
                    if status != 200:
                        raise _SourceError(f"HTTP {status} at {url}")
                    try:
                        body = _read_body(response, file_format, deadline)
                    except _SourceError as exc:
                        raise _SourceError(f"{url}: {exc}") from exc
                    return _Download(url, datetime.now(timezone.utc), response.headers.get("ETag"),
                                     response.headers.get("Last-Modified"), body)
        except (requests.exceptions.SSLError, requests.exceptions.ProxyError):
            raise
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt:
                raise
            delay = 0.25
        if monotonic() + delay >= deadline:
            raise _SourceError(f"Retry would exceed the time budget at {url}")
        sleep(delay)


def _source_date(match):
    month, day, year = match.groups()
    return date(int(year), _MONTHS.index(month) + 1, int(day))


def _catalog_tables(body, url):
    """Read only the publisher's data table and its edition labels."""
    soup = BeautifulSoup(body, "lxml")
    current = url == _CURRENT
    headings = (("Topic", "Current data set as html (just US)", "Regional datasets (downloadable Excel)")
                if current else ("Topic", "Data Item", "US", "Europe", "Japan", "Emerging Markets", "Global"))
    tables = []
    for row in soup.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if [_norm(cell.get_text(" ")) for cell in cells[:len(headings)]] == list(map(_norm, headings)):
            tables.append(row.find_parent("table"))
    if len(tables) != 1:
        raise _SourceError("Expected one official data catalog table")
    industry_edition = None
    if current:
        banners = [match for heading in soup.find_all("h4") if
                   (match := re.match(r"Data of last full update: " + _DATE_PATTERN,
                                      " ".join(heading.get_text(" ").split())))]
        if len(banners) != 1:
            raise _SourceError("Expected one full-update date in the current catalog")
        industry_edition = _source_date(banners[0]).isoformat()[:7]
    rows = {}
    titles = {_norm(family.current_title if current else family.archive_title): key
              for key, family in _FAMILIES.items()}
    for row in tables[0].find_all("tr"):
        if row.find_parent("table") is not tables[0]:
            continue
        cells = row.find_all(["td", "th"], recursive=False)
        for index, cell in enumerate(cells):
            matches = {titles[label] for link in cell.find_all("a")
                       if (label := _norm(link.get_text(" "))) in titles}
            if not matches:
                continue
            if len(matches) != 1:
                raise _SourceError("Ambiguous dataset title cell in the official catalog")
            dataset = matches.pop()
            if dataset in rows:
                raise _SourceError(f"Duplicate catalog row for {dataset}")
            rows[dataset] = cells[index + 1:]
    entries = {}
    for dataset, family in _FAMILIES.items():
        cells = rows.get(dataset)
        if cells is None:
            raise _SourceError(f"Missing catalog row for {dataset}")
        if current:
            entries[dataset] = _current_entries(dataset, cells, industry_edition, url)
        else:
            entries[dataset] = _archive_entries(dataset, family, cells, url)
    return entries


def _links(cell):
    return [(label, link["href"]) for link in cell.find_all("a", href=True)
            if (label := " ".join(link.get_text(" ").split()))]


def _add_entry(entries, dataset, region, edition, url, href):
    target = urljoin(url, href)
    parts = urlsplit(target)
    if parts.scheme == "file" and url == _ARCHIVE:
        return
    file_format = _FAMILIES[dataset].file_format
    if edition in _FAMILIES[dataset].editions:
        _official_url(target, file_format)
    elif not target.startswith(_HOME) or parts.netloc != "pages.stern.nyu.edu" or parts.query or parts.fragment:
        raise _SourceError("Unsafe source URL in an unverified catalog edition")
    entry = _Edition(dataset, region, edition, target, url)
    key = region, edition
    if key in entries and entries[key] != entry:
        raise _SourceError(f"Conflicting catalog links for {dataset}, {region}, {edition}")
    if any(existing.url == target and existing != entry for existing in entries.values()):
        raise _SourceError(f"Shared catalog link for multiple {dataset} selections: {target}")
    entries[key] = entry


def _current_entries(dataset, cells, industry_edition, url):
    if not cells:
        raise _SourceError(f"Missing download cell for {dataset}")
    entries = {}
    for label, href in _links(cells[0]):
        if dataset == _COUNTRY:
            match = re.fullmatch(_DATE_PATTERN + r" update", label)
            if not match:
                raise _SourceError(f"Unrecognized country edition label {label!r}")
            edition = _source_date(match).isoformat()[:7]
            _add_entry(entries, dataset, None, edition, url, href)
        elif (region := _REGIONS.get(_norm(label))) is not None:
            _add_entry(entries, dataset, region, industry_edition, url, href)
    if {region for region, _ in entries} != set(_FAMILIES[dataset].regions):
        raise _SourceError(f"Missing current regional or edition links for {dataset}")
    return entries


def _archive_entries(dataset, family, cells, url):
    if dataset == _COUNTRY and len(cells) == 1 and cells[0].get("colspan") == "5":
        region_cells = [(None, cells[0])]
    elif dataset != _COUNTRY and len(cells) == 5 and all(
            cell.get("colspan", "1") == cell.get("rowspan", "1") == "1" for cell in cells):
        region_cells = [("Global", cells[4]), ("US", cells[0])]
    else:
        raise _SourceError(f"Unexpected archive region columns for {dataset}")
    entries = {}
    for region, cell in region_cells:
        for label, href in _links(cell):
            match = re.fullmatch(r"(1[0-2]|[1-9])/([0-9]{2})", label)
            if match:
                month, year = match.groups()
                edition = f"20{year}-{int(month):02d}"
                if edition in family.editions:
                    _add_entry(entries, dataset, region, edition, url, href)
    return entries


def _catalog(session, url, refresh):
    cache = _cached(_catalogs, url)
    if cache is not None and not refresh and monotonic() - cache.checked < _CATALOG_TTL:
        return cache.value
    try:
        download = _download(session, url, previous=cache.download if cache else None)
        if download is None:
            entry = replace(cache, checked=monotonic())
        else:
            data = _catalog_tables(download.body, download.url)
            entry = _Cached(replace(download, body=b""), data, monotonic())
    except (ValueError, requests.RequestException) as exc:
        raise RuntimeError(f"Damodaran catalog {url}: {exc}") from exc
    _remember(_catalogs, url, entry, 2)
    return entry.value


def _latest(entries, dataset, region):
    edition = max(month for key_region, month in entries if key_region == region)
    entry = entries[region, edition]
    choices = ", ".join(_FAMILIES[dataset].editions)
    if edition not in _FAMILIES[dataset].editions:
        raise RuntimeError(
            f"Damodaran {dataset}, {region or 'country'}, {edition}: newer current edition "
            f"has an unverified layout ({entry.url}). Verified explicit editions: {choices}."
        )
    return entry


_CATALOG_COLUMNS = (
    "Dataset", "DatasetName", "Category", "Description", "Region", "Edition", "IsLatest",
    "UpdateFrequency", "Source", "SourceURL", "CatalogURL", "FileFormat", "DefinitionsURL",
)


def get_damodaran_datasets(
    dataset: str | None = None, *, include_history: bool = False, refresh: bool = False,
) -> pd.DataFrame:
    """List supported Damodaran datasets, regions and workbook editions.

    dataset filters to a dataset ID or documented alias. With include_history,
    include verified older editions still linked by the publisher. Set refresh
    to revalidate the catalogs immediately. Returns a DataFrame of selections.

    Raises ValueError for invalid arguments and RuntimeError when an official
    catalog cannot be reached or its advertised current edition is unverified.
    """
    datasets = (_dataset(dataset),) if dataset is not None else _FAMILIES
    _flag(include_history, "include_history")
    _flag(refresh, "refresh")
    with _Session() as session:
        current = _catalog(session, _CURRENT, refresh)
        archived = _catalog(session, _ARCHIVE, refresh) if include_history else {}
    rows = []
    for key in datasets:
        family = _FAMILIES[key]
        for region in family.regions:
            latest = _latest(current[key], key, region)
            entries = {**current[key], **archived.get(key, {})}
            entries[region, latest.edition] = latest
            editions = sorted(family.editions, reverse=True) if include_history else [latest.edition]
            for edition in editions:
                if (entry := entries.get((region, edition))) is not None:
                    rows.append((key, family.name, "Risk and Discount Rates", family.description,
                                 region, edition, entry == latest, family.frequency, _SOURCE,
                                 entry.url, entry.catalog_url, family.file_format, _DEFINITIONS))
    frame = pd.DataFrame(rows, columns=_CATALOG_COLUMNS)
    return frame.astype({col: "bool" if col == "IsLatest" else "string" for col in frame})


@dataclass(frozen=True)
class _Cell:
    value: object
    number_format: str = "General"


@dataclass(frozen=True)
class _Field:
    label: str
    name: str
    unit: str = "PercentagePoint"
    missing: tuple[str, ...] = ()


_PCT = "PercentagePoint"
_RATIO = "Ratio"
_COUNT = "Count"
_FIRM_COUNT = _Field("Number of Firms", "NumberOfFirms", _COUNT)
_BETA_FIELDS = (
    _FIRM_COUNT,
    _Field("Beta", "LeveredBeta", _RATIO),
    _Field("D/E Ratio", "DebtToEquityPercent"),
    _Field("Effective Tax rate", "EffectiveTaxRatePercent"),
    _Field("Unlevered beta", "UnleveredBeta", _RATIO),
    _Field("Cash/Firm value", "CashToFirmValuePercent"),
    _Field("Unlevered beta corrected for cash", "CashAdjustedUnleveredBeta", _RATIO),
    _Field("HiLo Risk", "HiLoRisk", _RATIO),
    _Field("Standard deviation of equity", "EquityVolatilityPercent"),
    _Field("Standard deviation in operating income (last 10 years)",
           "OperatingIncomeVariation10YearPercent", missing=("NA",)),
)
_WACC_FIELDS = (
    _FIRM_COUNT,
    _Field("Beta", "Beta", _RATIO),
    _Field("Cost of Equity", "CostOfEquityPercent"),
    _Field("E/(D+E)", "EquityWeightPercent"),
    _Field("Std Dev in Stock", "EquityVolatilityPercent"),
    _Field("Cost of Debt", "PretaxCostOfDebtPercent"),
    _Field("Tax Rate", "ReportedTaxRatePercent"),
    _Field("After-tax Cost of Debt", "AfterTaxCostOfDebtPercent"),
    _Field("D/(D+E)", "DebtWeightPercent"),
    _Field("Cost of Capital", "CostOfCapitalPercent"),
)
_RATED_FIELDS = (
    _Field("Rating-based Default Spread", "DefaultSpreadPercent"),
    _Field("Total Equity Risk Premium", "EquityRiskPremiumPercent"),
    _Field("Country Risk Premium", "CountryRiskPremiumPercent"),
)
_CDS_MISSING = ("NA", "#N/A")
_CDS_PREMIUM_FIELDS = (
    _Field("Total Equity Risk Premium2", "CdsBasedEquityRiskPremiumPercent", missing=_CDS_MISSING),
    _Field("Country Risk Premium3", "CdsBasedCountryRiskPremiumPercent", missing=_CDS_MISSING),
)
_FRONTIER_FIELDS = (
    _Field("ERP", "EquityRiskPremiumPercent"),
    _Field("CRP", "CountryRiskPremiumPercent"),
    _Field("Default Spread", "DefaultSpreadPercent"),
)
_INDUSTRY_COLUMNS = ("IndustryName", "IndustryClassification", "RowType", "NumberOfFirms")
_COUNTRY_COLUMNS = (
    "Country", "CountryRegion", "RiskMethod", "MoodysRating", "DefaultSpreadPercent",
    "CountryRiskPremiumPercent", "EquityRiskPremiumPercent", "SovereignCdsNetSpreadPercent",
    "CdsBenchmark", "CdsBasedCountryRiskPremiumPercent", "CdsBasedEquityRiskPremiumPercent",
)
_DATE_COLUMNS = ("DataAsOf", "SourceUpdateDate")


def _grid_size(rows, columns):
    if not (1 <= rows <= 512 and 1 <= columns <= 48):
        raise _SourceError(f"Unexpected worksheet dimensions ({rows} rows, {columns} columns)")


def _xls_grid(body, name):
    import xlrd

    if not body.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        raise _SourceError("Expected the BIFF XLS compound-file signature")
    workbook = xlrd.open_workbook(file_contents=body, formatting_info=True, on_demand=True)
    try:
        if name not in workbook.sheet_names():
            raise _SourceError(f"Missing XLS worksheet {name!r}")
        sheet = workbook.sheet_by_name(name)
        _grid_size(sheet.nrows, sheet.ncols)
        rows = []
        for row in range(sheet.nrows):
            cells = []
            for cell in sheet.row(row):
                value = cell.value
                if cell.ctype == xlrd.XL_CELL_DATE:
                    value = xlrd.xldate_as_datetime(value, workbook.datemode)
                elif cell.ctype == xlrd.XL_CELL_ERROR:
                    value = xlrd.error_text_from_code[cell.value]
                elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                    value = bool(value)
                number_format = workbook.format_map[workbook.xf_list[cell.xf_index].format_key].format_str
                cells.append(_Cell(value, number_format))
            rows.append(cells)
        return rows
    finally:
        workbook.release_resources()


def _xlsx_grid(body, name):
    import openpyxl

    if not body.startswith(b"PK\x03\x04"):
        raise _SourceError("Expected the ZIP signature of an XLSX workbook")
    with ZipFile(BytesIO(body)) as archive:
        members = archive.infolist()
        names = {member.filename for member in members}
        if len(members) > 512 or sum(member.file_size for member in members) > 64 * 1024 * 1024:
            raise _SourceError("XLSX expands beyond its workbook limits")
        if (len(names) != len(members)
                or not {"[Content_Types].xml", "xl/workbook.xml"} <= names
                or "xl/vbaProject.bin" in names):
            raise _SourceError("Unexpected XLSX container members")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r"(Data Validation extension|Unknown extension) is not supported.*",
                                category=UserWarning, module=r"openpyxl\..*")
        workbook = openpyxl.load_workbook(BytesIO(body), read_only=True, data_only=True, keep_links=False)
        try:
            if name not in workbook.sheetnames:
                raise _SourceError(f"Missing XLSX worksheet {name!r}")
            sheet = workbook[name]
            _grid_size(sheet.max_row, sheet.max_column)
            return [[_Cell(cell.value, cell.number_format or "General") for cell in row]
                    for row in sheet.iter_rows()]
        finally:
            workbook.close()


def _header(row, expected):
    if len(row) < len(expected) or [_norm(cell.value) for cell in row[:len(expected)]] != list(map(_norm, expected)):
        raise _SourceError(f"Expected worksheet heading {', '.join(expected)}")


def _find_label(grid, label):
    matches = [index for index, row in enumerate(grid) if _norm(row[0].value) == _norm(label)]
    if len(matches) != 1:
        raise _SourceError(f"Expected one worksheet row headed {label!r}")
    return matches[0]


def _value(grid, label, column):
    row = _find_label(grid, label)
    if len(grid[row]) <= column:
        raise _SourceError(f"Missing value for {label!r}")
    return grid[row][column]


def _identity(cell, field):
    if not _norm(cell.value) or cell.value.lstrip().startswith(("#", "=")):
        raise _SourceError(f"Missing or invalid {field}: {cell.value!r}")
    return cell.value


def _number(cell, field):
    value = cell.value
    if isinstance(value, str) and value in field.missing:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise _SourceError(f"{field.name}: invalid number or missing cached value {value!r}")
    if field.unit == _PCT:
        if not re.fullmatch(r"0(?:\.0+)?%", cell.number_format):
            raise _SourceError(f"{field.name}: unexpected percentage format {cell.number_format!r}")
        percentage = value * 100.0
        if not math.isfinite(percentage):
            raise _SourceError(f"{field.name}: percentage exceeds numeric range")
        return percentage
    if not re.fullmatch(r"General|0(?:\.0+)?", cell.number_format):
        raise _SourceError(f"{field.name}: unexpected numeric format {cell.number_format!r}")
    if field.unit == _COUNT:
        if not 0 <= value < 2**63 or int(value) != value:
            raise _SourceError(f"{field.name}: invalid firm count {value!r}")
        return int(value)
    return value


def _fields(cells, fields):
    return {field.name: _number(cell, field) for cell, field in zip(cells, fields, strict=True)}


def _assumptions(grid, specifications):
    return {name: _number(_value(grid, label, column), _Field(label, name, unit))
            for label, column, name, unit in specifications}


def _parse_record(parser, row, row_number):
    try:
        return parser(row)
    except _SourceError as exc:
        raise _SourceError(f"Excel row {row_number}: {exc}") from exc


def _source_update(cell, edition):
    value = cell.value
    if not isinstance(value, datetime) or value.strftime("%Y-%m") != edition:
        raise _SourceError(f"Workbook update date {value!r} does not match edition {edition}")
    return value.date()


_MEANINGS = {
    "NumberOfFirms": "Published count of firms in the industry or market aggregate",
    "LeveredBeta": "Average equity regression beta with financial leverage",
    "DebtToEquityPercent": "Aggregate debt divided by market equity",
    "EffectiveTaxRatePercent": "Published trailing effective tax rate",
    "UnleveredBeta": "Beta after removing estimated financial leverage",
    "CashToFirmValuePercent": "Cash and equivalents divided by equity plus debt",
    "CashAdjustedUnleveredBeta": "Unlevered operating-asset beta after the cash adjustment",
    "HiLoRisk": "Average annual high-low range divided by the sum of the high and low",
    "EquityVolatilityPercent": "Published stock return volatility measure",
    "OperatingIncomeVariation10YearPercent": "Average coefficient of variation of ten years of operating income",
    "Beta": "Published average equity regression beta",
    "CostOfEquityPercent": "Required equity return under the source's CAPM estimate",
    "EquityWeightPercent": "Market equity weight in equity plus debt",
    "PretaxCostOfDebtPercent": "Estimated borrowing cost before the tax shield",
    "ReportedTaxRatePercent": "Displayed tax rate, with the debt tax assumption recorded separately",
    "AfterTaxCostOfDebtPercent": "Published borrowing cost after the tax shield",
    "DebtWeightPercent": "Debt weight in equity plus debt",
    "CostOfCapitalPercent": "Published weighted average of equity and after-tax debt costs",
    "DefaultSpreadPercent": "Sovereign credit spread based on rating or implied by the frontier method",
    "EquityRiskPremiumPercent": "Total equity premium under the rating or frontier method",
    "CountryRiskPremiumPercent": "Incremental equity premium under the rating or frontier method",
    "SovereignCdsNetSpreadPercent": "Sovereign CDS spread net of the reference in CdsBenchmark",
    "CdsBasedEquityRiskPremiumPercent": "Total equity premium estimated using the CDS method",
    "CdsBasedCountryRiskPremiumPercent": "Incremental equity premium estimated using the CDS method",
}


def _column_metadata(fields):
    return {field.name: {"SourceLabel": field.label, "NativeUnit": field.unit,
                         "Definition": _MEANINGS[field.name], "SourceEncoding": "Excel fraction" if field.unit == _PCT else "Excel number"}
            for field in fields}


def _industry(grid, entry):
    beta = entry.dataset == _BETAS
    fields = _BETA_FIELDS if beta else _WACC_FIELDS
    header_at = _find_label(grid, "Industry Name")
    _header(grid[header_at], ("Industry Name", *(field.label for field in fields)))
    preamble = grid[:header_at]
    identity = _find_label(preamble, "What is this data?")
    expected_region = "Global" if entry.region == "Global" else "US companies"
    expected_title = ("Beta, Unlevered beta and other risk measures" if beta else
                      "Cost of equity and capital in US dollars (updateable)" if entry.region == "Global"
                      else "Cost of equity and capital (updateable)")
    if (_norm(preamble[identity][1].value) != _norm(expected_title)
            or _norm(preamble[identity][5].value) != _norm(expected_region)):
        raise _SourceError(f"Unexpected industry workbook identity for {entry.region}")
    updated = _source_update(_value(preamble, "Date updated:", 1), entry.edition)
    warnings_list = []
    if beta:
        basis = _value(preamble, "Do you want to use marginal or effective tax rates in unlevering betas?", 5).value
        if basis not in ("Marginal", "Effective"):
            raise _SourceError(f"Unexpected unlevering tax basis {basis!r}")
        assumptions = _assumptions(preamble, (
            ("If marginal tax rate, enter the marginal tax rate to use", 5, "MarginalTaxRatePercent", _PCT),
        ))
        extra = {"UnleveringTaxBasis": basis}
    else:
        use_marginal = _value(preamble, "Do you want to use the marginal tax rate for cost of debt?", 5).value
        if use_marginal not in ("Yes", "No"):
            raise _SourceError(f"Unexpected WACC marginal tax setting {use_marginal!r}")
        assumptions = _assumptions(preamble, (
            ("Long Term Treasury bond rate =", 3, "TreasuryBondRatePercent", _PCT),
            ("Risk Premium to Use for Equity =", 3, "EquityRiskPremiumPercent", _PCT),
            ("Global Default Spread to add to cost of debt =", 3, "DefaultSpreadPercent", _PCT),
            ("If yes, enter the marginal tax rate to use", 5, "MarginalTaxRatePercent", _PCT),
        ))
        assumptions["UseMarginalTaxRate"] = use_marginal == "Yes"
        extra = {"Currency": "USD"}

    market_name = ("Tiotal Market" if entry.region == "Global" and entry.edition == "2025-01"
                   else "Total Market")
    market_names = (market_name, "Total Market (without financials)")

    def record(row):
        label = _identity(row[0], "IndustryName")
        row_type = "MarketAggregate" if label in market_names else "Industry"
        values = _fields(row[1:len(fields) + 1], fields)
        if not beta and not math.isclose(values["EquityWeightPercent"] + values["DebtWeightPercent"],
                                        100, rel_tol=0, abs_tol=0.02):
            warnings_list.append(f"Published equity and debt weights do not sum to 100 for {label}.")
        return {"IndustryName": label, "RowType": row_type, **values, **extra}

    rows = [_parse_record(record, row, index + 1)
            for index, row in enumerate(grid[header_at + 1:], header_at + 1)]
    labels = [row["IndustryName"] for row in rows]
    if (len(labels) < 3 or tuple(labels[-2:]) != market_names or
            any(_norm(label).startswith(("total market", "tiotal market")) for label in labels[:-2])):
        raise _SourceError("Expected industry rows followed by both published market aggregates")
    if len(set(map(_norm, labels))) != len(labels):
        raise _SourceError("Duplicate industry identity")
    signature = sha256(json.dumps(labels, ensure_ascii=False).encode("utf-8")).hexdigest()
    classification = f"{entry.dataset}/{entry.region}/{entry.edition}/{signature}"
    for row in rows:
        row["IndustryClassification"] = classification
    columns = (*_INDUSTRY_COLUMNS, *(field.name for field in fields[1:]), *extra)
    metadata = {
        "SourceAssumptions": assumptions,
        "SourceHeader": tuple(cell.value for cell in grid[header_at][:len(fields) + 1]),
        "ColumnMetadata": _column_metadata(fields),
        "MetadataWarnings": tuple(warnings_list),
        "Completeness": "All rows in the published main industry table, including both market aggregates.",
    }
    return rows, columns, updated, metadata


def _country_revision(preamble, published):
    row = preamble[_find_label(preamble, "Date of update:")]
    note = row[2].value
    if published.day != 1 or (note is not None and not isinstance(note, str)):
        raise _SourceError("Unexpected country-risk edition date or revision note")
    corrected = re.fullmatch(r"Default spreads corrected on " + _DATE_PATTERN, note or "")
    if published == date(2026, 7, 1):
        if not corrected or _source_date(corrected) != date(2026, 7, 9):
            raise _SourceError("Expected the July 9, 2026 default spread correction note")
        return _source_date(corrected), note, ()
    if published == date(2026, 1, 1) and note == "(Updated Feb 16 for sovereign ratings":
        return date(2026, 2, 16), note, ()
    if published == date(2026, 4, 1) and note == "(Updated Feb 16 for sovereign ratings":
        return published, note, ("April carries a February ratings note from the January workbook.",)
    if note:
        raise _SourceError(f"Unverified country-risk revision note {note!r}")
    return published, None, ()


def _country(grid, entry):
    _header(grid[0], ("Country and Equity Risk Premiums",))
    frontier_at = _find_label(grid, "Frontier Markets (no sovereign ratings)")
    header_at = _find_label(grid[:frontier_at], "Country")
    rated_header = grid[header_at]
    preamble = grid[:header_at]
    published = _source_update(_value(preamble, "Date of update:", 1), entry.edition)
    updated, revision, warnings_list = _country_revision(preamble, published)
    cds_label, benchmark = ("Sovereign CDS, net of US", "US") if entry.edition == "2025-01" else (
        "Sovereign CDS, net of Swiss CDS", "Switzerland")
    cds_fields = (_Field(cds_label, "SovereignCdsNetSpreadPercent", missing=_CDS_MISSING), *_CDS_PREMIUM_FIELDS)
    _header(rated_header, ("Country", "Africa", "Moody's rating",
                           *(field.label for field in (*_RATED_FIELDS, *cds_fields))))

    def rated(row):
        rating = _identity(row[2], "MoodysRating")
        if not re.fullmatch(r"Aaa|(?:Aa|A|Baa|Ba|B|Caa)[123]|Ca|C", rating):
            raise _SourceError(f"Unexpected Moody's rating {rating!r}")
        cds = _fields(row[6:9], cds_fields)
        if not (all(value is None for value in cds.values()) or all(value is not None for value in cds.values())):
            raise _SourceError("Inconsistent missing values in the CDS estimate block")
        return {"Country": _identity(row[0], "Country"), "CountryRegion": _identity(row[1], "CountryRegion"),
                "RiskMethod": "RatingBased", "MoodysRating": rating, "CdsBenchmark": benchmark,
                **_fields(row[3:6], _RATED_FIELDS), **cds}

    def frontier(row):
        _number(row[1], _Field("PRS Composite Risk Score", "PRS Composite Risk Score", _RATIO))
        return {"Country": _identity(row[0], "Country"), "RiskMethod": "FrontierPrs",
                **_fields(row[2:5], _FRONTIER_FIELDS)}

    start = frontier_at + 2
    if start >= len(grid):
        raise _SourceError("Missing frontier data")
    _header(grid[frontier_at + 1], ("Country", "PRS Composite Risk Score",
                                  *(field.label for field in _FRONTIER_FIELDS)))
    end = next((index for index in range(start, len(grid)) if not grid[index][0].value), len(grid))
    if (frontier_at <= header_at + 1 or end <= start or end + 1 >= len(grid)
            or any(cell.value for cell in grid[end][:9])
            or any(row[0].value for row in grid[end:])
            or [_norm(cell.value) for cell in grid[end + 1][1:3]] != ["rating", "default spread in basis points"]):
        raise _SourceError("Expected both country sections and the separate trailing spread lookup")
    rows = [_parse_record(rated, grid[index], index + 1) for index in range(header_at + 1, frontier_at)]
    rows.extend(_parse_record(frontier, grid[index], index + 1) for index in range(start, end))
    if len({(_norm(row["Country"]), row["RiskMethod"]) for row in rows}) != len(rows):
        raise _SourceError("Duplicate country identity within the published risk method")
    specifications = [
        ("Enter the current risk premium for a mature equity market", 4, "MatureMarketErpPercent", _PCT),
        ("If yes, enter the multiplier to use on the default spread (See worksheet for volatility numbers for selected emerging markets)",
         4, "RelativeEquityVolatility", _RATIO),
    ]
    if entry.edition != "2025-01":
        specifications.append(("Enter the current risk premium for the US =", 4, "UsErpPercent", _PCT))
    assumptions = _assumptions(preamble, specifications)
    adjustment = _value(preamble, "Do you want to adjust the country default spread for the additional volatility of the equity market to get to a country premium?", 4).value
    if adjustment not in ("Yes", "No"):
        raise _SourceError(f"Unexpected equity volatility adjustment setting {adjustment!r}")
    assumptions["AdjustForEquityVolatility"] = adjustment == "Yes"
    metadata = {
        "SourceAssumptions": assumptions,
        "SourceHeader": {
            "RatingBased": tuple(cell.value for cell in rated_header[:9]),
            "FrontierPrs": tuple(cell.value for cell in grid[frontier_at + 1][:5]),
        },
        "SourceEditionDate": published.isoformat(),
        "SourceRevisionNote": revision,
        "MetadataWarnings": warnings_list,
        "Completeness": "All rows in the published rating-based and frontier tables.",
        "ColumnMetadata": _column_metadata((*_RATED_FIELDS, *cds_fields)),
    }
    metadata["ColumnMetadata"].update({
        "Country": {"SourceLabel": "Country"},
        "CountryRegion": {"SourceLabel": "Africa"},
        "MoodysRating": {"SourceLabel": "Moody's rating", "NativeUnit": "Rating"},
    })
    for field in _FRONTIER_FIELDS:
        metadata["ColumnMetadata"][field.name]["FrontierSourceLabel"] = field.label
    return rows, _COUNTRY_COLUMNS, updated, metadata


def _frame(download, entry):
    if entry.dataset == _COUNTRY:
        name = "ERPs by country"
        grid = _xlsx_grid(download.body, name)
        rows, columns, updated, metadata = _country(grid, entry)
    else:
        name = "Industry Averages"
        grid = _xls_grid(download.body, name)
        rows, columns, updated, metadata = _industry(grid, entry)

    frame = pd.DataFrame(rows, columns=columns)
    frame = frame.assign(Dataset=entry.dataset, Region=entry.region, Edition=entry.edition,
                         DataAsOf=pd.NaT, DataAsOfPeriod=None, Source=_SOURCE, SourceURL=download.url,
                         SourceUpdateDate=pd.Timestamp(updated), RetrievedAt=pd.Timestamp(download.retrieved_at))
    units = {field: details.get("NativeUnit") for field, details in metadata["ColumnMetadata"].items()}
    types = {_COUNT: "Int64", _PCT: "Float64", _RATIO: "Float64"}
    frame = frame.astype({column: types.get(units.get(column), "string")
                          for column in frame if column not in (*_DATE_COLUMNS, "RetrievedAt")})
    frame = frame.astype({column: "datetime64[ns]" for column in _DATE_COLUMNS}
                         | {"RetrievedAt": "datetime64[ns, UTC]"})
    frame.attrs.update(metadata, CatalogURL=entry.catalog_url, DefinitionsURL=_DEFINITIONS, UsageURL=_USAGE,
                       SourceSheet=name, OriginalFile=urlsplit(download.url).path.rsplit("/", 1)[-1],
                       SourceHttpLastModified=download.last_modified, SourceETag=download.etag,
                       SourceRowCount=len(frame))
    return frame


def _artifact(session, entry, refresh):
    cached = _cached(_artifacts, entry)
    if cached is not None and not refresh and monotonic() - cached.checked < _ARTIFACT_TTL:
        result = cached
    else:
        try:
            download = _download(session, entry.url, _FAMILIES[entry.dataset].file_format,
                                 previous=cached.download if cached else None)
            if download is None:
                result = replace(cached, checked=monotonic(), revalidated_at=datetime.now(timezone.utc))
            else:
                frame = _frame(download, entry)
                result = _Cached(replace(download, body=b""), frame, monotonic())
        except Exception as exc:
            # Workbook readers expose several format-specific error types.
            raise RuntimeError(
                f"Damodaran {entry.dataset}, {entry.region or 'country'}, {entry.edition} "
                f"at {entry.url}: {exc}"
            ) from exc
        _remember(_artifacts, entry, result, 16)
    frame = result.value.copy(deep=True)
    if result.revalidated_at is not None:
        frame.attrs["RevalidatedAt"] = result.revalidated_at
    return frame


def get_damodaran_data(
    dataset: str, *, region: Literal["Global", "US"] | None = None,
    edition: str | None = None, refresh: bool = False,
) -> pd.DataFrame:
    """Download a published Damodaran valuation table as a pandas DataFrame.

    dataset accepts an ID or documented alias. For industry data, region
    defaults to Global and also accepts US. Omit region for country risk.
    edition defaults to the latest published selection or takes YYYY-MM.
    Set refresh to revalidate the relevant catalog and workbook immediately.

    Returns published values with edition and source provenance. Percent fields
    use percentage points. Raises ValueError for invalid or unavailable
    selections and RuntimeError when a source or workbook cannot be validated.
    """
    key = _dataset(dataset)
    family = _FAMILIES[key]
    _flag(refresh, "refresh")
    if key == _COUNTRY and region is not None:
        raise ValueError("Omit region for country risk premiums.")
    canonical_region = None
    if key != _COUNTRY:
        canonical_region = "Global" if region is None else _REGIONS.get(_norm(region))
        if canonical_region is None:
            raise ValueError(f"Unknown Damodaran region {region!r}. Choose Global or US.")
    if edition is not None:
        if not isinstance(edition, str) or not re.fullmatch(r"[0-9]{4}-(?:0[1-9]|1[0-2])", edition):
            raise ValueError("edition must use YYYY-MM, such as 2025-01.")
        if edition not in family.editions:
            raise ValueError(f"Unverified edition {edition} for {key}. Choose from {', '.join(family.editions)}.")

    with _Session() as session:
        if edition == "2025-01":
            archive = _catalog(session, _ARCHIVE, refresh)
            entry = archive[key].get((canonical_region, edition))
            if entry is None:
                entry = _catalog(session, _CURRENT, refresh)[key].get((canonical_region, edition))
        else:
            current = _catalog(session, _CURRENT, refresh)
            if edition is None:
                entry = _latest(current[key], key, canonical_region)
            else:
                entry = current[key].get((canonical_region, edition))
                if entry is None:
                    archive = _catalog(session, _ARCHIVE, refresh)
                    entry = archive[key].get((canonical_region, edition))
        if entry is None:
            raise ValueError(
                f"Damodaran currently lists no {edition} link for {key}, {canonical_region or 'country'}. "
                "See get_damodaran_datasets for available editions."
            )
        return _artifact(session, entry, refresh)
