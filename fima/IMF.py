"""Official IMF DataMapper v2, selected annual World Economic Outlook data.

See docs/imf.md for native units, coverage, projection uncertainty and data terms.
No HTTP occurs at import time. The source currently ignores geographic/year
filters; each series call retrieves just one indicator and filters it locally.
"""
from typing import Literal as _Literal
import datetime as _dt
from email.utils import parsedate_to_datetime as _parsedate
import json as _json
import math as _math
from numbers import Integral as _Integral
import re as _re
import time as _time
from urllib.parse import urlsplit as _urlsplit
import warnings as _warnings

import pandas as _pd
import requests as _requests

__all__ = ["get_imf_datasets", "get_imf_indicators", "get_imf_countries", "get_imf_series"]

_BASE = "https://www.imf.org/external/datamapper/api/v2/"
_WEO = "https://www.imf.org/external/datamapper/datasets/WEO"
_TERMS = "https://www.imf.org/en/about/copyright-and-terms"
_TIMEOUT = (10, 30)
_MAX_BYTES = 2 * 1024 * 1024
_INDICATORS = ["Indicator", "IndicatorName", "Description", "Dataset", "Unit", "Frequency",
               "Source", "SourceProjectionYear", "SourceLastModified", "SourceURL"]
_GEOGRAPHIES = ["Country", "CountryName", "GeographyType", "SourceURL"]
_SERIES = ["Country", "CountryName", "GeographyType", "Indicator", "Period", "Frequency", "Value", "Unit"]


def _fail(message):
    raise RuntimeError("IMF: " + message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate JSON identity: " + key)
        result[key] = value
    return result


def _constant(value):
    _fail("nonfinite JSON number: " + value)


def _retry_delay(response, attempt):
    value = response.headers.get("Retry-After")
    if value is None:
        return 2 ** attempt
    try:
        if _re.fullmatch(r"[0-9]+", value):
            delay = int(value)
        else:
            when = _parsedate(value)
            if when.tzinfo is None:
                raise ValueError("timezone missing")
            delay = max(0, (when - _dt.datetime.now(_dt.timezone.utc)).total_seconds())
        if delay > 30:
            _fail("Retry-After exceeds 30 seconds; retry the call later")
        return delay
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError("IMF: invalid Retry-After; retry the call later") from exc


def _get(path, params=None):
    url = _BASE + path
    try:
        for attempt in range(3):
            response = _requests.get(url, params=params, timeout=_TIMEOUT, stream=True,
                                     headers={"Accept": "application/json"})
            try:
                final = _urlsplit(response.url)
                if final.scheme != "https" or final.netloc != "www.imf.org":
                    _fail("response redirected outside the official HTTPS origin")
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    delay = _retry_delay(response, attempt)
                else:
                    response.raise_for_status()
                    if response.status_code != 200:
                        _fail(f"unexpected HTTP status {response.status_code}")
                    if response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                        _fail("expected application/json, received another MIME type")
                    chunks, size = [], 0
                    for chunk in response.iter_content(chunk_size=65536):
                        size += len(chunk)
                        if size > _MAX_BYTES:
                            _fail("response exceeds the 2 MiB limit; no partial result returned")
                        chunks.append(chunk)
                    payload = _json.loads(b"".join(chunks).decode("utf-8-sig"),
                                          object_pairs_hook=_pairs, parse_constant=_constant)
                    if not isinstance(payload, dict) or payload.get("api") != {"version": "2", "output-method": "json"}:
                        _fail("unexpected DataMapper v2 response schema/version")
                    if payload.get("error") or payload.get("errors"):
                        _fail("provider returned an error response")
                    return payload, response.url
            finally:
                response.close()
            _time.sleep(delay)
    except (_requests.RequestException, ValueError, UnicodeError) as exc:
        raise RuntimeError(f"IMF: request failed for {url}: {exc}") from exc


def _identifier(value, label):
    if not isinstance(value, str) or not _re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value):
        raise ValueError(f"{label} must be an exact IMF identifier from the discovery functions")
    return value


def _frame(rows, columns):
    result = _pd.DataFrame(rows, columns=columns)
    for col in columns:
        result[col] = result[col].astype("Int64" if col == "SourceProjectionYear" else
                                         "float64" if col == "Value" else "string")
    result.attrs.update(Source="International Monetary Fund", TermsURL=_TERMS)
    return result


def _metadata(code, item):
    if not isinstance(item, dict) or item.get("dataset") != "WEO":
        _fail("unexpected WEO indicator metadata")
    for key in ("label", "description", "source", "unit", "last-modified"):
        if not isinstance(item.get(key), str) or not item[key].strip():
            _fail("missing WEO indicator metadata: " + key)
    if item.get("frequency", "A") != "A" or any(k in item for k in ("scale", "unit-mult", "UNIT_MULT")):
        _fail("unsupported frequency or separate scale metadata")
    projection = item.get("projection-year")
    if projection is not None and (type(projection) is not int or not 1000 <= projection <= 9999):
        _fail("invalid source projection-year metadata")
    return dict(zip(_INDICATORS, [code, item["label"], item["description"], "WEO", item["unit"], "A",
                                 item["source"], projection, item["last-modified"], _WEO]))


def _catalog():
    payload, url = _get("indicators")
    catalog = payload.get("indicators")
    if not isinstance(catalog, dict) or not catalog:
        _fail("missing indicator catalog")
    rows = []
    for code, item in catalog.items():
        if not isinstance(item, dict) or not isinstance(item.get("dataset"), str):
            _fail("malformed indicator catalog entry")
        if item["dataset"] == "WEO":
            try:
                _identifier(code, "indicator")
            except ValueError as exc:
                raise RuntimeError("IMF: malformed indicator identity") from exc
            rows.append(_metadata(code, item))
    if not rows:
        _fail("catalog no longer advertises WEO indicators")
    result = _frame(rows, _INDICATORS).sort_values("Indicator", ignore_index=True)
    result.attrs["SourceURL"] = url
    return result


def get_imf_datasets() -> _pd.DataFrame:
    """Discover the supported DataMapper subset (currently annual WEO only).

    Returns a DataFrame with Dataset, DatasetName, Frequency, IndicatorCount,
    SourceURL. Count comes from the current indicator catalog, not all IMF data.
    Raises RuntimeError on HTTP, provider or schema failure. No authentication.
    """
    indicators = _catalog()
    result = _frame([["WEO", "World Economic Outlook", "A", _WEO]],
                    ["Dataset", "DatasetName", "Frequency", "SourceURL"])
    result.insert(3, "IndicatorCount", _pd.Series([len(indicators)], dtype="Int64"))
    return result


def get_imf_indicators(dataset: _Literal["WEO"] | None=None, search: str | None=None) -> _pd.DataFrame:
    """Discover supported annual WEO indicators, definitions and native units.

    dataset: None or 'WEO'. search: optional literal case-insensitive substring
    in identifier/name/description/unit; filtering follows one catalog GET.
    Returns Indicator, IndicatorName, Description, Dataset, Unit, Frequency,
    Source (edition), SourceProjectionYear (nullable Int64), SourceLastModified
    (unlocalized source timestamp), SourceURL. Other columns use pandas string.
    Raises ValueError for invalid inputs; RuntimeError for source failures.
    """
    if dataset is not None and (not isinstance(dataset, str) or dataset != "WEO"):
        raise ValueError("dataset must be None or 'WEO'; only DataMapper WEO is supported")
    if search is not None and (not isinstance(search, str) or not search.strip()):
        raise ValueError("search must be a nonempty string or None")
    result = _catalog()
    if search is not None:
        mask = _pd.Series(False, index=result.index)
        for column in ("Indicator", "IndicatorName", "Description", "Unit"):
            mask |= result[column].str.contains(search, case=False, regex=False, na=False)
        result = result.loc[mask].reset_index(drop=True)
    return result


def get_imf_countries(include_aggregates: bool=False) -> _pd.DataFrame:
    """Discover exact source geographic IDs; they are not all ISO country codes.

    include_aggregates: bool, also fetch regions and analytical groups if True.
    Returns Country, CountryName, GeographyType ('Country'/'Region'/'Group'),
    SourceURL, all pandas string; source-null names stay pd.NA. This source-wide catalog does not promise WEO
    coverage for every geography/indicator. No country-code conversion occurs.
    Raises ValueError for invalid input; RuntimeError for source/schema errors.
    """
    if type(include_aggregates) is not bool:
        raise ValueError("include_aggregates must be a bool")
    rows, seen = [], set()
    for path, kind in [("countries", "Country")] + ([("regions", "Region"), ("groups", "Group")] if include_aggregates else []):
        payload, url = _get(path)
        catalog = payload.get(path)
        if not isinstance(catalog, dict) or not catalog:
            _fail("missing geographic catalog: " + path)
        for code, item in catalog.items():
            try:
                _identifier(code, "country")
            except ValueError as exc:
                raise RuntimeError("IMF: malformed geographic identity") from exc
            if (code in seen or not isinstance(item, dict) or "label" not in item or
                    (item["label"] is not None and
                     (not isinstance(item["label"], str) or not item["label"].strip()))):
                _fail("duplicate or malformed geographic catalog entry")
            seen.add(code)
            rows.append([code, item["label"], kind, url])
    return _frame(rows, _GEOGRAPHIES).sort_values(["GeographyType", "Country"], ignore_index=True)


def get_imf_series(indicator: str, countries: str | list[str] | tuple[str, ...], start_year: _Integral, end_year: _Integral) -> _pd.DataFrame:
    """Retrieve one WEO annual indicator for explicit geographies and years.

    indicator: exact supported ID from get_imf_indicators. countries: one exact
    source ID or list/tuple of 1..20 distinct IDs (countries, regions or groups).
    start_year, end_year: inclusive integer annual labels, 1000..9999; at most
    200 years. No default global download. The API currently ignores filters:
    one selected indicator history is fetched (2 MiB cap), then filtered locally.

    Returns tidy Country, CountryName, GeographyType, Indicator, Period (YYYY),
    Frequency ('A'), Value (float64/NaN), Unit (native source scale). Other
    columns use pandas string; order is requested geography then ascending year.
    Source nulls remain NaN and omitted periods are not manufactured. Empty
    intervals retain the schema. attrs include IndicatorMetadata, SourceURL,
    TermsURL, Coverage (per geography, missing years), Filtering='ClientSide',
    ObservationStatus='Unknown', and Completeness. SourceProjectionYear is
    preserved as metadata, never used as a country-specific actual/forecast
    boundary. Historical estimates and projections may coexist in every result.

    Raises ValueError for invalid IDs/years; RuntimeError for transport, schema,
    numeric or metadata inconsistency. Warns RuntimeWarning when a requested
    geography has no source series, with explicit Coverage rather than zeroes.
    No pagination/count contract exists: omissions cannot independently be
    distinguished from unavailable coverage. See docs/imf.md and IMF data terms.
    """
    _identifier(indicator, "indicator")
    selected = [countries] if isinstance(countries, str) else countries
    if not isinstance(selected, (list, tuple)) or not 1 <= len(selected) <= 20:
        raise ValueError("countries must be one ID or a list/tuple of 1..20 distinct IDs")
    selected = [_identifier(c, "country") for c in selected]
    if len(set(selected)) != len(selected):
        raise ValueError("countries must contain distinct IDs")
    for year in (start_year, end_year):
        if isinstance(year, bool) or not isinstance(year, _Integral) or not 1000 <= year <= 9999:
            raise ValueError("years must be integers in 1000..9999")
    if start_year > end_year or end_year - start_year >= 200:
        raise ValueError("year interval must be ordered and contain at most 200 years")
    catalog = _catalog().set_index("Indicator")
    if indicator not in catalog.index:
        raise ValueError("unsupported indicator; use get_imf_indicators (annual WEO only)")
    # Country-only calls avoid fetching aggregate catalogs. Unknown IDs are then
    # checked against the official region/group catalogs before any series GET.
    geographies = get_imf_countries().set_index("Country")
    if any(c not in geographies.index for c in selected):
        geographies = get_imf_countries(include_aggregates=True).set_index("Country")
    unknown = [c for c in selected if c not in geographies.index]
    if unknown:
        raise ValueError("unknown IMF geographic identifiers: " + ", ".join(unknown))
    years = [str(y) for y in range(start_year, end_year + 1)]
    payload, url = _get(indicator + "/" + "/".join(selected), {"periods": ",".join(years)})
    source_meta = payload.get("indicators")
    if not isinstance(source_meta, dict) or set(source_meta) != {indicator}:
        _fail("series indicator metadata is missing or mismatched")
    metadata = _metadata(indicator, source_meta[indicator])
    expected = catalog.loc[indicator].to_dict()
    expected["Indicator"] = indicator
    # Compare nullable projection metadata without pandas' ambiguous NA equality.
    for key, value in metadata.items():
        wanted = expected[key]
        if not ((value is None and _pd.isna(wanted)) or
                (value is not None and not _pd.isna(wanted) and value == wanted)):
            _fail("indicator metadata changed during retrieval; retry the call")
    values = payload.get("values")
    if not isinstance(values, dict) or not isinstance(values.get(indicator), dict):
        _fail("missing or malformed series values")
    # Observed v2 artifact: exactly an empty indicator key with null value.
    if any(key != indicator and (key != "" or value is not None) for key, value in values.items()):
        _fail("unexpected indicator in series response")
    series = values[indicator]
    # Validate all supplied observations before applying client filters. A bad
    # period/value outside the selection must not conceal a partial response.
    for country, observations in series.items():
        if not isinstance(country, str) or not _re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", country) or not isinstance(observations, dict):
            _fail("malformed geographic series")
        for period, value in observations.items():
            if not _re.fullmatch(r"[1-9][0-9]{3}", period):
                _fail("expected annual YYYY period")
            if value is not None:
                try:
                    valid = type(value) in (int, float) and _math.isfinite(value)
                except OverflowError:
                    valid = False
                if not valid:
                    _fail("nonnumeric or nonfinite observation")
    rows, coverage, unavailable = [], [], []
    for country in selected:
        geo = geographies.loc[country]
        observations = series.get(country, {})
        present = sorted(set(years).intersection(observations))
        coverage.append(dict(Country=country, SourceSeriesPresent=country in series,
                             ReturnedPeriods=present, MissingPeriods=sorted(set(years) - set(present))))
        if country not in series:
            unavailable.append(country)
        for period in present:
            rows.append([country, geo.CountryName, geo.GeographyType, indicator, period, "A",
                         observations[period], metadata["Unit"]])
    if unavailable:
        _warnings.warn("IMF supplied no series for " + ", ".join(unavailable) +
                       "; availability/completeness is unverified. Inspect result.attrs['Coverage'].",
                       RuntimeWarning, stacklevel=2)
    result = _frame(rows, _SERIES)
    result.attrs.update(IndicatorMetadata=metadata, SourceURL=url, Coverage=coverage,
                        Filtering="ClientSide", ObservationStatus="Unknown",
                        Completeness="SourceProvidesNoObservationCounts")
    return result
