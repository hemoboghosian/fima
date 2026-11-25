"""Discover World Development Indicators and retrieve validated annual observations."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
from numbers import Integral
import re
from time import monotonic, sleep
from typing import Literal
from urllib.parse import urlencode, urljoin, urlsplit

import pandas as pd
import requests


__all__ = [
    "get_world_bank_sources", "get_world_bank_countries",
    "get_world_bank_indicators", "get_world_bank_series",
]

_BASE = "https://api.worldbank.org/v2/"
_SOURCE_ID = "2"
_SOURCE_NAME = "World Development Indicators"
_DATASET = "https://datacatalog.worldbank.org/infrastructure-data/search/dataset/0037712/world-development-indicators"
_TERMS = "https://www.worldbank.org/ext/en/legal/terms-conditions/datasets"
_PAGE_SIZE = 500
_MAX_PAGES = 20
_MAX_BYTES = 2 * 1024 * 1024
_DEADLINE = 120
_RETRY_STATUS = {429, 500, 502, 503, 504}
_REDIRECT_STATUS = {301, 302, 303, 307, 308}
_COUNTRY_CODE = re.compile(r"[A-Z0-9]{3}")
_INDICATOR_CODE = re.compile(r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*")

_SOURCES = ("SourceId", "SourceCode", "Source", "SourceUpdateDate", "DataAvailable",
            "MetadataAvailable", "SourceURL")
_COUNTRIES = ("Country", "CountryName", "CountryCode2", "GeographyType", "Region",
              "IncomeLevel", "LendingType", "SourceId")
_INDICATORS = ("Indicator", "IndicatorName", "Description", "SourceId", "Source",
               "SourceOrganization", "Unit", "TopicIds", "Topics")
_SERIES = ("Country", "CountryName", "GeographyType", "Indicator", "IndicatorName", "SourceId",
           "Source", "Period", "Frequency", "Value", "Unit", "ObservationStatus", "Footnote",
           "Decimals")
_DTYPES = {"DataAvailable": "boolean", "MetadataAvailable": "boolean", "TopicIds": "object",
           "Topics": "object", "Value": "float64", "Decimals": "Int64"}


class _ContractError(ValueError):
    """An invalid provider payload, distinct from caller input errors."""


class _ProviderError(RuntimeError):
    def __init__(self, url, messages):
        self.codes = {code for code, _ in messages}
        details = " | ".join(f"{code} {message}" for code, message in messages)
        super().__init__(f"World Bank {url}: HTTP 200 provider error {details[:400]}")


class _Session(requests.Session):
    def get_redirect_target(self, response):
        # Requests otherwise reads redirect bodies even with allow_redirects=False.
        # Check each Location in the streaming downloader instead.
        return None


def _require(condition, message):
    if not condition:
        raise _ContractError(message)


def _mapping(value, label):
    _require(isinstance(value, dict), f"expected {label} object")
    return value


def _list(value, label):
    _require(isinstance(value, list), f"expected {label} list")
    return value


def _text(value, label, *, required=False):
    if value is None and not required:
        return None
    _require(isinstance(value, str) and (not required or bool(value.strip())),
             f"invalid {label} text")
    return value if value.strip() else None


def _count(value, label):
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,19}", value):
        value = int(value)
    _require(type(value) is int and 0 <= value <= 2**63 - 1, f"invalid {label} counter")
    return value


def _source_id(value):
    _require(value == _SOURCE_ID or type(value) is int and value == int(_SOURCE_ID),
             "unexpected source ID. Expected WDI source 2")
    return _SOURCE_ID


def _update_date(value):
    if value is None or value == "":
        return None
    _require(isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value),
             "invalid lastupdated date")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise _ContractError("invalid lastupdated date") from exc
    return value


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _finite_float(token):
    number = float(token)
    _require(math.isfinite(number), "nonfinite JSON number")
    return number


def _messages(payload):
    envelope = payload[0] if isinstance(payload, list) and payload else payload
    if not isinstance(envelope, dict) or "message" not in envelope:
        return ()
    messages = []
    for item in _list(envelope["message"], "provider message"):
        item = _mapping(item, "provider message")
        code = _count(item.get("id"), "provider error ID")
        message = _text(item.get("value"), "provider error") or _text(item.get("key"), "provider error")
        messages.append((code, (message or "unspecified error")[:200]))
    _require(messages, "empty provider error envelope")
    return messages


def _check_url(url):
    parts = urlsplit(url)
    _require(parts.scheme == "https" and parts.netloc == "api.worldbank.org"
             and parts.path.startswith("/v2/") and not parts.fragment,
             "unsafe URL outside the official Indicators v2 HTTPS endpoint")
    _require(len(url) <= 4000 and all(len(part) <= 1500 for part in parts.path.split("/")),
             "URL exceeds the provider's request limits")
    return parts


def _read_json(response, deadline):
    mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    _require(mime == "application/json", f"HTTP 200 with unexpected Content-Type {mime!r}")
    body = bytearray()
    for chunk in response.iter_content(chunk_size=16384):
        _require(monotonic() < deadline, "call exceeded its time budget")
        _require(len(body) + len(chunk) <= _MAX_BYTES, "response exceeds the decoded byte limit")
        body.extend(chunk)
    return json.loads(body.decode("utf-8-sig"), object_pairs_hook=_unique_pairs,
                      parse_float=_finite_float, parse_constant=_finite_float)


def _retry_delay(retry_after, attempt, url, reason):
    delay = 0.25 * 2**attempt
    if retry_after:
        try:
            if re.fullmatch(r"[0-9]+", retry_after):
                delay = int(retry_after)
            else:
                until = parsedate_to_datetime(retry_after)
                if until.tzinfo is None:
                    until = until.replace(tzinfo=timezone.utc)
                delay = max(0, (until - datetime.now(timezone.utc)).total_seconds())
        except (OverflowError, TypeError, ValueError) as exc:
            raise RuntimeError(f"World Bank {url}: {reason}. Invalid Retry-After. Retry later") from exc
    if delay > 5:
        raise RuntimeError(f"World Bank {url}: {reason}. Retry-After exceeds 5 seconds. Retry later")
    return delay


class _Client:
    def __init__(self, session):
        self.session = session
        self.deadline = monotonic() + _DEADLINE
        self.urls = []

    def get(self, path, page, params):
        query = urlencode({"format": "json", "page": page, "per_page": _PAGE_SIZE, **params})
        requested = f"{_BASE}{path}?{query}"
        for attempt in range(3):
            url = requested
            retry_after = ""
            cause = None
            try:
                original = _check_url(requested)
                for hop in range(4):
                    remaining = self.deadline - monotonic()
                    _require(remaining > 0, "call exceeded its time budget")
                    with self.session.get(url, stream=True, allow_redirects=False,
                                          timeout=(min(10, remaining), min(30, remaining))) as response:
                        status = response.status_code
                        if status in _REDIRECT_STATUS:
                            location = response.headers.get("Location")
                            _require(location and hop < 3, f"HTTP {status} with missing or excessive redirects")
                            target = urljoin(url, location)
                            parts = _check_url(target)
                            _require(parts.path.rstrip("/") == original.path.rstrip("/")
                                     and parts.query == original.query, "redirect changed the request scope")
                            url = target
                            continue
                        retry_after = response.headers.get("Retry-After", "").strip()
                        if status in _RETRY_STATUS:
                            reason = f"HTTP {status}"
                            break
                        _require(status == 200, f"unexpected HTTP {status}")
                        payload = _read_json(response, self.deadline)
                        _require(monotonic() < self.deadline, "call exceeded its time budget")
                        messages = _messages(payload)
                        if not messages:
                            self.urls.append(url)
                            return payload, url
                        error = _ProviderError(url, messages)
                        if error.codes != {105} or attempt == 2:
                            raise error
                        reason = "HTTP 200 provider error 105"
                        break
            except (requests.exceptions.SSLError, requests.exceptions.ProxyError) as exc:
                raise RuntimeError(f"World Bank {url}: {type(exc).__name__}") from exc
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                    requests.exceptions.ChunkedEncodingError) as exc:
                reason, cause = type(exc).__name__, exc
            except (requests.RequestException, ValueError, RecursionError) as exc:
                raise RuntimeError(f"World Bank {url}: {exc}") from exc
            if attempt == 2:
                raise RuntimeError(f"World Bank {url}: {reason}, retries exhausted") from cause
            delay = _retry_delay(retry_after, attempt, url, reason)
            if monotonic() + delay >= self.deadline:
                raise RuntimeError(f"World Bank {url}: {reason}. Retry exceeds time budget. Retry later") from cause
            sleep(delay)

    def frame(self, rows, columns, url, updated):
        frame = pd.DataFrame({column: pd.Series([row.get(column) for row in rows],
                                               dtype=_DTYPES.get(column, "string")) for column in columns})
        frame.attrs.update(Provider="World Bank", SourceId=_SOURCE_ID, SourceCode="WDI", Source=_SOURCE_NAME,
                           SourceURL=url, RequestURLs=tuple(self.urls),
                           RetrievedAt=datetime.now(timezone.utc).isoformat(), DatasetURL=_DATASET,
                           License="CC BY 4.0", TermsURL=_TERMS, SourceUpdateDate=updated)
        return frame


@dataclass(frozen=True)
class _Page:
    number: int
    pages: int
    size: int
    total: int
    source_id: str | None
    updated: str | None


def _variables(header, concept):
    sources = _list(header.get("source"), "source")
    _require(len(sources) == 1, "expected one WDI source")
    source = _mapping(sources[0], "source")
    _check_source(source, "name")
    concepts = _list(source.get("concept"), "concept")
    _require(len(concepts) == 1, f"expected one {concept} concept")
    item = _mapping(concepts[0], "concept")
    _require(isinstance(item.get("id"), str) and item["id"].casefold() == concept,
             f"unexpected concept, expected {concept}")
    return _list(item.get("variable"), f"{concept} variable")


def _country_variables(header):
    return _variables(header, "country")


def _page(payload, number, extract, *, series=False, max_records=None):
    if extract is None:
        _require(isinstance(payload, list) and len(payload) == 2, "expected two-element JSON envelope")
        header = _mapping(payload[0], "header")
    else:
        header = _mapping(payload, "header")
    current, pages, size, total = (_count(header.get(key), key)
                                   for key in ("page", "pages", "per_page", "total"))
    source = header.get("sourceid")
    source_id = None if source is None else _source_id(source)
    updated = _update_date(header.get("lastupdated"))
    metadata = _Page(current, pages, size, total, source_id, updated)
    if extract is None and payload[1] is None and (current, pages, size, total) == (0, 0, 0, 0):
        _require(number == 1 and (not series or header.get("sourceid", False) is None
                                  and header.get("lastupdated", False) is None),
                 "unexpected empty page sentinel")
        return metadata, []
    _require(number == current and 0 < size <= _PAGE_SIZE and 1 <= number <= pages <= _MAX_PAGES,
             f"invalid pagination for page {number} (limit {_MAX_PAGES} pages)")
    _require(total > 0 and pages == (total + size - 1) // size, "page count does not reconcile with total")
    if max_records is not None:
        _require(total <= max_records, f"advertised total exceeds the requested scope of {max_records} records")
    if series:
        _require(source_id == _SOURCE_ID, "missing WDI source ID on a populated series page")
    records = _list(payload[1] if extract is None else extract(header), "page records")
    _require(len(records) == min(size, total - (number - 1) * size), "page record count does not reconcile")
    return metadata, records


def _paged(client, path, parse, *, extract=None, params=None, series=False, max_records=None):
    first = None
    records = {}
    for number in range(1, _MAX_PAGES + 1):
        payload, url = client.get(path, number, params or {})
        try:
            page, rows = _page(payload, number, extract, series=series, max_records=max_records)
            if first is None:
                first, first_url = page, url
            else:
                _require(page == _Page(number, first.pages, first.size, first.total,
                                       first.source_id, first.updated), "pagination or source metadata changed across pages")
            for row in rows:
                key, record = parse(_mapping(row, "record"))
                _require(key not in records, f"duplicate record {key!r}")
                records[key] = record
            if number >= first.pages:
                return records, first, first_url
        except (ValueError, OverflowError) as exc:
            raise RuntimeError(f"World Bank {url}: {exc}") from exc


def _check_source(record, label):
    _source_id(record.get("id"))
    _require(record.get(label) == _SOURCE_NAME, "expected World Development Indicators source name")


def _source(client):
    def parse(record):
        _check_source(record, "name")
        _require(record.get("code") == "WDI", "unexpected source code, expected WDI")
        flags = [record.get(key) for key in ("dataavailability", "metadataavailability")]
        _require(all(flag in ("Y", "N") for flag in flags), "invalid WDI availability flag")
        return _SOURCE_ID, dict(SourceId=_SOURCE_ID, SourceCode="WDI", Source=_SOURCE_NAME,
                                SourceUpdateDate=_update_date(record.get("lastupdated")),
                                DataAvailable=flags[0] == "Y", MetadataAvailable=flags[1] == "Y")

    records, page, url = _paged(client, "source/2", parse, max_records=1)
    if not records:
        raise RuntimeError(f"World Bank {url}: missing WDI source record")
    row = records[_SOURCE_ID]
    if row["SourceUpdateDate"] and page.updated and row["SourceUpdateDate"] != page.updated:
        raise RuntimeError(f"World Bank {url}: conflicting source update dates")
    row["SourceUpdateDate"] = row["SourceUpdateDate"] or page.updated
    row["SourceURL"] = url
    return row


def _provider_code(value, pattern, label):
    _require(isinstance(value, str) and len(value) <= 1500 and pattern.fullmatch(value),
             f"invalid {label} {repr(value)[:100]} in provider response")
    return value


def _membership(row):
    return (_provider_code(row.get("id"), _COUNTRY_CODE, "WDI geography code"),
            _text(row.get("value"), "WDI geography name", required=True))


def _geography(row):
    code = _provider_code(row.get("id"), _COUNTRY_CODE, "general geography code")
    iso2 = _text(row.get("iso2Code"), "two-character geography code")
    if iso2 is not None:
        _provider_code(iso2, re.compile(r"[A-Z0-9]{2}"), "two-character geography code")
    labels = {}
    for wire, name in (("region", "Region"), ("incomeLevel", "IncomeLevel"), ("lendingType", "LendingType")):
        field = _mapping(row.get(wire), wire)
        labels[name] = _text(field.get("value"), wire)
    region = _mapping(row.get("region"), "region")
    admin = _mapping(row.get("adminregion"), "adminregion")
    region_ids = (_text(region.get("id"), "region ID"), _text(admin.get("id"), "adminregion ID"))
    _require(labels["Region"] is not None, "missing general geography region label")
    return code, (iso2, labels["Region"].strip() == "Aggregates", labels, region_ids)


def _classification(code_key, name_key):
    def parse(row):
        return (_provider_code(row.get(code_key), _COUNTRY_CODE, "group code"),
                _text(row.get(name_key), "group name", required=True))
    return parse


# Regional subdivisions verified in the official region catalog. Other regional
# codes are obtained from the region and administrative-region IDs of economies.
_REGIONAL_SUBDIVISIONS = {"AFE", "AFW", "CEB"}


def _countries(client):
    members, page, url = _paged(client, "sources/2/country/data", _membership, extract=_country_variables)
    general, _, _ = _paged(client, "country", _geography)
    regions, _, _ = _paged(client, "region", _classification("code", "name"))
    incomes, _, _ = _paged(client, "incomelevel", _classification("id", "value"))
    lending, _, _ = _paged(client, "lendingtype", _classification("id", "value"))
    regional_ids = _REGIONAL_SUBDIVISIONS | {code for _, aggregate, _, ids in general.values()
                                            if not aggregate for code in ids if code is not None}
    groups = {code: "Region" for code in regions.keys() & regional_ids}
    groups.update(dict.fromkeys(incomes, "IncomeGroup"))
    groups.update(dict.fromkeys(lending, "LendingGroup"))
    groups["WLD"] = "World"
    for catalog, catalog_url in ((members, url), (general, "country"), (regions, "region"),
                                 (incomes, "incomelevel"), (lending, "lendingtype")):
        if not catalog:
            raise RuntimeError(f"World Bank {catalog_url}: unexpectedly empty geography catalog")
    result = {}
    for code, name in sorted(members.items()):
        iso2, aggregate, labels, _ = general.get(code, (None, False, {}, ()))
        kind = "Unknown" if code not in general else "Economy"
        if aggregate:
            kind = groups.get(code, "OtherAggregate")
            labels = {}
        result[code] = dict(Country=code, CountryName=name, CountryCode2=iso2, GeographyType=kind,
                            SourceId=_SOURCE_ID, **labels)
    return result, page, url


def _indicator(row):
    code = _provider_code(row.get("id"), _INDICATOR_CODE, "WDI indicator code")
    _check_source(_mapping(row.get("source"), "indicator source"), "value")
    topics = {}
    raw_topics = row.get("topics")
    # IC.MNG.IND represents absent topics as a one-element placeholder.
    for topic in _list([] if raw_topics is None or raw_topics == [{}] else raw_topics, "topics"):
        topic = _mapping(topic, "topic")
        key = str(_count(topic.get("id"), "topic ID"))
        _require(key not in topics, f"duplicate topic ID {key}")
        topics[key] = _text(topic.get("value"), "topic name", required=True)
    return code.upper(), dict(
        Indicator=code, IndicatorName=_text(row.get("name"), "indicator name", required=True),
        Description=_text(row.get("sourceNote"), "definition"), SourceId=_SOURCE_ID, Source=_SOURCE_NAME,
        SourceOrganization=_text(row.get("sourceOrganization"), "source organization"),
        Unit=_text(row.get("unit"), "catalog unit"), TopicIds=tuple(topics), Topics=tuple(topics.values()),
    )


def _selected_indicator(client, code):
    exact_error = None
    try:
        rows, _, url = _paged(client, f"source/2/indicator/{code}", _indicator, max_records=1)
    except _ProviderError as exc:
        if exc.codes != {120}:
            raise
        exact_error, rows = exc, {}
    if rows:
        if code not in rows:
            raise RuntimeError(f"World Bank {url}: unexpected indicator identity, expected {code}")
        return rows[code]

    # The exact route's generic "Invalid value" also covers provider errors.
    # Only a reconciled source catalog can establish that this code is unknown.
    catalog, _, catalog_url = _paged(client, "source/2/indicator", _indicator)
    if not catalog:
        raise RuntimeError(f"World Bank {catalog_url}: unexpectedly empty WDI indicator catalog") from exact_error
    if code not in catalog:
        raise ValueError(f"Unknown WDI indicator {code!r}. See get_world_bank_indicators()")
    if exact_error is not None:
        raise exact_error
    raise RuntimeError(f"World Bank {url}: indicator {code} missing from its exact endpoint")


def _rich_metadata(client, code):
    def extract(header):
        variables = _variables(header, "series")
        _require(len(variables) == 1, "expected one metadata indicator")
        series = _mapping(variables[0], "metadata indicator")
        _require(series.get("id") == code, f"unexpected metadata indicator, expected {code}")
        return series.get("metatype")

    def parse(row):
        return (_text(row.get("id"), "metadata field", required=True),
                _text(row.get("value"), "metadata value"))

    fields, _, url = _paged(client, f"sources/2/series/{code}/metadata", parse, extract=extract)
    if fields.get("Dataset") not in (None, "WB_WDI"):
        raise RuntimeError(f"World Bank {url}: unexpected metadata dataset identity")
    return fields, url


def _observation_parser(indicator, geographies, start_year, end_year):
    code = indicator["Indicator"]

    def parse(row):
        reported = _mapping(row.get("indicator"), "observation indicator")
        _require(reported.get("id") == code, f"unexpected observation indicator, expected {code}")
        _text(reported.get("value"), "observation indicator name", required=True)
        country = _provider_code(row.get("countrycode"), _COUNTRY_CODE, "observation geography code")
        _require(country in geographies, f"unexpected observation geography {country}")
        iso3 = _text(row.get("countryiso3code"), "observation ISO3 code")
        _require(iso3 in (None, country), f"conflicting ISO3 code for {country}")
        geography = geographies[country]
        details = _mapping(row.get("country"), "observation country")
        code2 = _text(details.get("id"), "observation two-character code")
        if code2 is not None and geography["CountryCode2"] is not None:
            _require(code2 == geography["CountryCode2"], f"conflicting two-character code for {country}")
        period = row.get("date")
        _require(isinstance(period, str) and re.fullmatch(r"[0-9]{4}", period),
                 f"expected annual YYYY period, received {period!r}")
        _require(start_year <= int(period) <= end_year,
                 f"period {period} outside requested {start_year}:{end_year}. The provider may have ignored the date filter")
        _require("value" in row, "missing observation value field")
        value = row["value"]
        if value is not None:
            _require(type(value) in (int, float) and math.isfinite(value), "invalid numeric observation value")
            value = float(value)
        decimals = row.get("decimal")
        return (country, period), dict(
            Country=country, CountryName=_text(details.get("value"), "observation country name", required=True),
            GeographyType=geography["GeographyType"], Indicator=code, IndicatorName=indicator["IndicatorName"],
            SourceId=_SOURCE_ID, Source=_SOURCE_NAME, Period=period, Frequency="A", Value=value,
            Unit=_text(row.get("unit"), "observation unit"), ObservationStatus=_text(row.get("obs_status"), "status"),
            Footnote=_text(row.get("footnote"), "footnote"),
            Decimals=None if decimals is None else _count(decimals, "decimal"),
        )

    return parse


def _unit_key(unit):
    key = re.sub(r"\s*=\s*", "=", " ".join(unit.casefold().split()))
    index = re.fullmatch(r"index \(([0-9]{4}=100)\)", key)
    return index[1] if index else key


def _title_unit(name):
    """Recognize explicit title units used to corroborate structured metadata."""
    if re.search(r"\((?:annual )?%(?: growth| change| of [^)]+)?\)$", name, re.IGNORECASE):
        return "%"
    match = re.search(r"\((?:[^()]*, )?(current US\$|constant [0-9]{4} US\$|current LCU|"
                      r"constant LCU|LCU per US\$|[0-9]{4}\s*=\s*100)(?:, period average)?\)$",
                      name, re.IGNORECASE)
    return match[1] if match else None


# Reviewed definitions for indicators with a missing structured unit. Require
# the explicit title unit and the definition's denominator or index base.
_REVIEWED_UNITS = {
    "BX.KLT.DINV.WD.GD.ZS": ("%", r"(?:percent(?:age)? of|% of|divided by) (?:gdp|gross domestic product)\b"),
    "CM.MKT.TRNR": ("%", r"shares traded divided by their market capitalization"),
    "DT.TDS.DECT.EX.ZS": ("%", r"debt service to exports of goods, services and primary income"),
    "TT.PRI.MRCH.XD.WD": ("2015 = 100", r"\b(?:base|reference) year\s+2015\b"),
}
_MARKET_CAP_UNIT = ("End-of-year total market capitalization of listed domestic companies, "
                    "divided by gross domestic product, expressed as a percentage.")


def _series_unit(indicator, fields, observation_units):
    title_unit = _title_unit(indicator["IndicatorName"])
    metadata_unit = fields.get("Unitofmeasure")
    catalog_unit = indicator["Unit"]
    explicit = observation_units + ((catalog_unit,) if catalog_unit else ())
    if explicit:
        # Any published explicit unit is eligible, as long as the explicit
        # sources agree and a recognized title unit does not contradict it.
        compared = explicit + ((title_unit,) if title_unit else ())
        if len({_unit_key(unit) for unit in compared}) == 1:
            return explicit[0], "Observation" if observation_units else "Catalog"
        return None, None
    if title_unit is None:
        return None, None
    rich_title_unit = _title_unit(fields.get("IndicatorName") or "")
    if rich_title_unit is not None and _unit_key(rich_title_unit) != _unit_key(title_unit):
        return None, None
    code = indicator["Indicator"]
    if metadata_unit:
        if _unit_key(metadata_unit) == _unit_key(title_unit):
            return metadata_unit, "Metadata"
        if code == "CM.MKT.LCAP.GD.ZS" and title_unit == "%" and metadata_unit == _MARKET_CAP_UNIT:
            return "%", "Metadata"
    elif code in _REVIEWED_UNITS:
        reviewed, evidence = _REVIEWED_UNITS[code]
        definition = fields.get("Longdefinition") or indicator["Description"] or ""
        if _unit_key(reviewed) != _unit_key(title_unit):
            return None, None
        if re.search(evidence, definition, re.IGNORECASE):
            return reviewed, "Definition"
    return None, None


def _indicator_metadata(indicator, fields, units, unit_source, url):
    metadata = {key: indicator[key] for key in ("Indicator", "IndicatorName", "Description", "SourceOrganization")}
    metadata.update(CatalogUnit=indicator["Unit"], ObservationUnits=units, UnitSource=unit_source, MetadataURL=url)
    for output, wire in {
        "MetadataIndicatorName": "IndicatorName", "LongDefinition": "Longdefinition",
        "Periodicity": "Periodicity", "ReferencePeriod": "Referenceperiod", "MetadataUnit": "Unitofmeasure",
        "Limitations": "Limitationsandexceptions", "License": "License_Type", "LicenseURL": "License_URL",
        "MetadataSourceOrganization": "Source", "AggregationMethod": "Aggregationmethod",
        "DevelopmentRelevance": "Developmentrelevance", "OtherNotes": "Othernotes",
        "StatisticalConceptAndMethodology": "Statisticalconceptandmethodology", "MetadataTopic": "Topic",
    }.items():
        metadata[output] = fields.get(wire)
    return metadata


def _validate_source(source):
    if not isinstance(source, str) or source != "WDI":
        raise ValueError(f"Unsupported World Bank source {source!r}. Use 'WDI' from get_world_bank_sources()")


def _search_term(search):
    if search is None:
        return None
    if not isinstance(search, str) or not search.strip():
        raise ValueError(f"search must be a nonblank string or None, got {search!r}")
    return search.strip().casefold()


def _matches(term, *fields):
    return term is None or any(field is not None and term in field.casefold() for field in fields)


def _argument_code(value, pattern, name, discovery):
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed.isascii() and len(trimmed) <= 1500 and pattern.fullmatch(trimmed.upper()):
            return trimmed.upper()
    raise ValueError(f"Invalid {name} {value!r}. Use an exact code from {discovery}()")


def _series_arguments(indicator, countries, start_year, end_year):
    code = _argument_code(indicator, _INDICATOR_CODE, "indicator", "get_world_bank_indicators")
    if isinstance(countries, str):
        countries = (countries,)
    if not isinstance(countries, (list, tuple)) or not 1 <= len(countries) <= 20:
        raise ValueError("countries must contain one to 20 geography codes from get_world_bank_countries()")
    codes = tuple(_argument_code(country, _COUNTRY_CODE, "geography", "get_world_bank_countries")
                  for country in countries)
    if "ALL" in codes:
        raise ValueError("ALL is a provider wildcard. Use exact codes from get_world_bank_countries()")
    if len(codes) != len(set(codes)):
        raise ValueError(f"countries must contain distinct WDI geography codes, got {codes!r}")
    current_year = date.today().year
    if (any(not isinstance(year, Integral) or isinstance(year, bool) for year in (start_year, end_year))
            or not 1960 <= start_year <= end_year <= current_year):
        raise ValueError(f"start_year and end_year must be ascending inclusive integers from 1960 to {current_year}, "
                         f"got {start_year!r}, {end_year!r}")
    return code, codes, int(start_year), int(end_year)


def get_world_bank_sources() -> pd.DataFrame:
    """Return the supported WDI source, its update date and availability flags.

    The one-row DataFrame includes the official source URL and retrieval
    provenance in attrs.

    Raises RuntimeError if the World Bank request or source validation fails.
    """
    with _Session() as session:
        client = _Client(session)
        row = _source(client)
        return client.frame([row], _SOURCES, row["SourceURL"], row["SourceUpdateDate"])


def get_world_bank_countries(
    include_aggregates: bool = False,
    *,
    search: str | None = None,
    source: Literal["WDI"] = "WDI",
) -> pd.DataFrame:
    """Return the WDI geography catalog, sorted by World Bank code.

    Set include_aggregates=True to include groups and unclassified WDI IDs.
    The search parameter matches a literal case-insensitive substring of either code or the name.
    The source parameter accepts "WDI".
    Invalid arguments raise ValueError. Failed requests or validation raise RuntimeError.
    """
    _validate_source(source)
    if type(include_aggregates) is not bool:
        raise ValueError(f"include_aggregates must be a bool, got {include_aggregates!r}")
    term = _search_term(search)
    with _Session() as session:
        client = _Client(session)
        countries, page, url = _countries(client)
        rows = [row for row in countries.values() if (include_aggregates or row["GeographyType"] == "Economy")
                and _matches(term, row["Country"], row["CountryCode2"], row["CountryName"])]
        return client.frame(rows, _COUNTRIES, url, page.updated)


def get_world_bank_indicators(
    search: str | None = None,
    *,
    source: Literal["WDI"] = "WDI",
) -> pd.DataFrame:
    """Return WDI indicators and their definitions, sorted by indicator code.

    The search parameter matches a literal case-insensitive substring of code, name, definition,
    catalog unit or topic. The source parameter accepts "WDI".
    Invalid arguments raise ValueError. Failed requests or validation raise RuntimeError.
    """
    _validate_source(source)
    term = _search_term(search)
    with _Session() as session:
        client = _Client(session)
        indicators, page, url = _paged(client, "source/2/indicator", _indicator)
        if not indicators:
            raise RuntimeError(f"World Bank {url}: unexpectedly empty WDI indicator catalog")
        rows = [row for row in sorted(indicators.values(), key=lambda item: item["Indicator"])
                if _matches(term, row["Indicator"], row["IndicatorName"], row["Description"],
                            row["Unit"], *row["Topics"])]
        return client.frame(rows, _INDICATORS, url, page.updated)


def get_world_bank_series(
    indicator: str,
    countries: str | list[str] | tuple[str, ...],
    start_year: int,
    end_year: int,
    *,
    source: Literal["WDI"] = "WDI",
) -> pd.DataFrame:
    """Return one annual WDI indicator for one to 20 distinct World Bank geographies.

    Use exact indicator and countries codes from discovery. The start_year and
    end_year are inclusive and range from 1960 through the current year. The
    source parameter accepts "WDI". Rows follow the requested geography order
    and ascending years.
    Inspect attrs for definitions, unit evidence, provenance and missing coverage.
    Invalid arguments, unknown codes and declared nonannual indicators raise
    ValueError. Provider, transport and incomplete-response errors raise RuntimeError.
    """
    _validate_source(source)
    code, codes, start_year, end_year = _series_arguments(indicator, countries, start_year, end_year)
    periods = tuple(str(year) for year in range(start_year, end_year + 1))
    with _Session() as session:
        client = _Client(session)
        selected = _selected_indicator(client, code)
        code = selected["Indicator"]
        countries, _, _ = _countries(client)
        unknown = [geo for geo in codes if geo not in countries]
        if unknown:
            raise ValueError(f"Unknown WDI geographies {unknown!r}. See get_world_bank_countries(include_aggregates=True)")
        geographies = {geo: countries[geo] for geo in codes}
        fields, metadata_url = _rich_metadata(client, code)
        periodicity = fields.get("Periodicity")
        if periodicity is not None and periodicity.strip().casefold() != "annual":
            raise ValueError(f"WDI indicator {code} has unsupported periodicity {periodicity!r}. Select an annual indicator")
        path = f"country/{';'.join(codes)}/indicator/{code}"
        params = dict(source=_SOURCE_ID, date=f"{start_year}:{end_year}", ctrycode="y", footnote="y", scale="n")
        parse = _observation_parser(selected, geographies, start_year, end_year)
        records, page, url = _paged(client, path, parse, params=params, series=True,
                                   max_records=len(codes) * len(periods))
        if not records:
            if periodicity is None:
                raise RuntimeError(f"World Bank {url}: annual frequency cannot be verified for an empty result without periodicity metadata")
            _source(client)
        units = tuple(sorted({row["Unit"] for row in records.values() if row["Unit"] is not None}))
        unit, unit_source = _series_unit(selected, fields, units)
        rows, coverage = [], []
        for geo in codes:
            returned, null, omitted = [], [], []
            for period in periods:
                row = records.get((geo, period))
                if row is None:
                    omitted.append(period)
                    continue
                returned.append(period)
                if row["Value"] is None:
                    null.append(period)
                row["Unit"] = unit
                rows.append(row)
            coverage.append(dict(Country=geo, ReturnedPeriods=tuple(returned), NullPeriods=tuple(null),
                                 OmittedPeriods=tuple(omitted)))
        frame = client.frame(rows, _SERIES, url, page.updated)
        frame.attrs.update(
            IndicatorMetadata=_indicator_metadata(selected, fields, units, unit_source, metadata_url),
            Coverage=tuple(coverage), Pagination=dict(AdvertisedRecords=page.total, ReturnedRecords=len(rows),
                                                    Pages=page.pages, PageSize=page.size),
            Completeness="ProviderCountsReconciled", RequestedCountries=codes, StartYear=start_year, EndYear=end_year,
        )
        return frame
