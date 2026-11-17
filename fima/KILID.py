"""KILID's public housing-market tables; listing prices are not transactions.

See docs/kilid.md for the source audit, data licenses, coverage and schemas.
No authentication, undocumented endpoint, derived FX conversion or crawling.
"""
import datetime as _dt
from decimal import Decimal as _Decimal
import json as _json
import math as _math
import re as _re
from urllib.parse import parse_qsl as _parse_qsl, urlsplit as _urlsplit, urlencode as _urlencode
from zoneinfo import ZoneInfo as _ZoneInfo

import jdatetime as _jd
import pandas as _pd
import requests as _requests
from bs4 import BeautifulSoup as _BeautifulSoup

__all__ = ["get_kilid_areas", "get_kilid_house_price_history",
           "get_kilid_house_price_snapshot", "get_kilid_area_comparison"]

_BASE = "https://kilid.com/house-prices"
_TIMEOUT = (10, 30)
_PERIODS = {"6m": 6, "1y": 12, "3y": 36}
_UNITS = {"toman": "TomanPerSquareMeter", "usd": "USDPerSquareMeter",
          "gold": "Gram18KGoldPerSquareMeter"}
_SUFFIXES = {"toman": "تومان", "usd": "دلار", "gold": "گرم"}
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
           "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
_IDENTITY = ["Area", "AreaName", "AreaLevel", "SourceParentArea"]
_SALE_METRICS = {
    "میانه قیمت هر متر مربع در آگهی‌ها": ("MedianListingPricePerSquareMeter", "TomanPerSquareMeter", "تومان"),
    "میانه قیمت کل در آگهی‌ها": ("MedianTotalListingPrice", "Toman", "تومان"),
    "تغییر ماهانه قیمت آگهی‌ها": ("MonthlyListingPriceChange", "Percent", "%"),
}
_RENT_METRICS = {
    "میانه اجاره مؤثر هر متر مربع": ("MedianEffectiveRentalListingPricePerSquareMeter", "TomanPerSquareMeterPerMonth", "تومان"),
    "برآورد اجاره مؤثر ماهانه واحد متوسط": ("EstimatedTypicalDwellingEffectiveMonthlyRent", "TomanPerMonth", "تومان"),
    "تعداد آگهی‌های اجاره": ("RentalListingCount", "Listings", ""),
}


def _now():
    return _dt.datetime.now(_dt.timezone.utc)


def _fail(message):
    raise RuntimeError("KILID: " + message)


def _plain(text):
    return _re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", text).translate(_DIGITS).replace("ي", "ی").replace("ك", "ک")


def _norm(text):
    return _re.sub(r"[\s\u200b-\u200d]", "", _plain(text))


def _area(area):
    # The public city list includes sowme'eh_sara; retain that source spelling.
    if not isinstance(area, str) or not _re.fullmatch(r"[a-z0-9]+(?:[-_'][a-z0-9]+)*", area):
        raise ValueError("area must be a KILID source slug, e.g. 'tehran-region5'; use get_kilid_areas")
    return area


def _slug(url):
    if not isinstance(url, str):
        _fail("missing geographic link")
    path = _urlsplit(url)
    if path.scheme not in ("", "https") or path.netloc not in ("", "kilid.com") or path.query or path.fragment:
        _fail("invalid geographic link")
    prefix = "/house-prices/"
    if not path.path.startswith(prefix):
        _fail("invalid geographic link")
    try:
        return _area(path.path[len(prefix):])
    except ValueError as exc:
        raise RuntimeError("KILID: malformed geographic identifier") from exc


def _one(node, selector):
    matches = node.select(selector)
    if len(matches) != 1:
        _fail("missing or ambiguous " + selector)
    return matches[0]


def _number(text, suffix, *, nonnegative=True):
    value = _plain(text).strip().replace("٪", "%").replace("−", "-")
    if value in ("—", "–", "-", "بدون داده"):
        return _pd.NA
    if suffix:
        if not value.endswith(suffix):
            _fail("incorrect financial unit: " + text)
        value = value[:-len(suffix)].strip()
    match = _re.fullmatch(r"([+-]?(?:[0-9]{1,3}(?:[,٬][0-9]{3})+|[0-9]+)(?:[.٫][0-9]+)?)\s*(هزار|میلیون|میلیارد)?", value)
    if not match:
        _fail("malformed financial value: " + text)
    scale = {None: 1, "هزار": 1000, "میلیون": 1000000, "میلیارد": 1000000000}[match[2]]
    number = float(_Decimal(match[1].replace(",", "").replace("٬", "").replace("٫", ".")) * scale)
    if not _math.isfinite(number) or (nonnegative and number < 0):
        _fail("invalid financial value: " + text)
    return number


def _month(text):
    value = _plain(text).replace("-", " ")
    match = _re.fullmatch(r"\s*(" + "|".join(_MONTHS) + r")\s+([0-9]{4})\s*", value)
    if not match or not 1200 <= int(match[2]) <= 1600:
        _fail("invalid Jalali month: " + text)
    return f"{match[2]}-{_MONTHS.index(match[1]) + 1:02d}"


def _month_number(month):
    year, number = map(int, month.split("-"))
    return year * 12 + number - 1


def _period_label(text, prefix):
    if not _norm(text).startswith(_norm(prefix)):
        _fail("missing reporting-month label")
    # The verified label has exactly one Persian month and one four-digit year.
    match = _re.search(r"(" + "|".join(_MONTHS) + r")\s+([0-9]{4})\s*$", _plain(text))
    if not match:
        _fail("invalid reporting month")
    return _month(match[0])


def _signature(url):
    parts = _urlsplit(url)
    return parts.scheme, parts.netloc, parts.path, sorted(_parse_qsl(parts.query)), parts.fragment


def _fetch(area, period="1y", denomination="toman"):
    canonical = _BASE + ("/" + area if area is not None else "")
    params = {}
    if period != "1y":
        params["months"] = _PERIODS[period]
    if denomination != "toman":
        params["denom"] = denomination
    url = canonical + ("?" + _urlencode(params) if params else "")
    try:
        response = _requests.get(url, timeout=_TIMEOUT, allow_redirects=False,
                                 headers={"User-Agent": "fima public market-data reader (https://github.com/hemoboghosian/fima)"})
        response.raise_for_status()
    except _requests.RequestException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        retry = getattr(getattr(exc, "response", None), "headers", {}).get("Retry-After")
        detail = f"HTTP {status}" if status else type(exc).__name__
        if retry:
            detail += f"; Retry-After={retry}; no automatic retry"
        raise RuntimeError(f"KILID retrieval failed ({detail}) for {url}") from exc
    if response.status_code != 200 or _signature(response.url) != _signature(url):
        _fail("redirect or wrong response location/selection; access may be restricted")
    if "text/html" not in response.headers.get("Content-Type", "").lower():
        _fail("expected a public HTML page")
    if not response.content.rstrip().lower().endswith(b"</html>"):
        _fail("incomplete HTML response")
    soup = _BeautifulSoup(response.content, "html.parser")
    if _one(soup, 'link[rel="canonical"]').get("href") != canonical:
        _fail("wrong geographic identity in canonical URL")
    records = {}
    try:
        for script in soup.select('script[type="application/ld+json"]'):
            record = _json.loads(script.get_text())
            if not isinstance(record, dict):
                _fail("malformed structured metadata")
            kind = record.get("@type")
            if kind in ("BreadcrumbList", "WebPage", "Dataset"):
                if kind in records:
                    _fail("duplicate structured metadata")
                records[kind] = record
    except (ValueError, TypeError) as exc:
        raise RuntimeError("KILID: malformed structured metadata") from exc
    for kind in ("WebPage", "Dataset"):
        if records.get(kind, {}).get("url") != canonical:
            _fail("wrong geographic identity in " + kind)
    crumbs = records.get("BreadcrumbList", {}).get("itemListElement")
    if not isinstance(crumbs, list) or len(crumbs) < 2:
        _fail("missing geographic breadcrumb identity")
    for position, item in enumerate(crumbs, 1):
        if not isinstance(item, dict) or item.get("position") != position or not isinstance(item.get("name"), str) or not isinstance(item.get("item"), str):
            _fail("malformed geographic breadcrumb identity")
    if crumbs[1].get("item") != _BASE or crumbs[-1].get("item") != canonical:
        _fail("wrong geographic breadcrumb identity")
    locations = crumbs[2:]
    slugs = [_slug(c.get("item")) for c in locations]
    if len(slugs) != len(set(slugs)):
        _fail("duplicate geographic breadcrumb identity")
    identity = {"Area": area, "AreaName": crumbs[-1]["name"], "AreaLevel": "Country",
                "SourceParentArea": slugs[-2] if len(slugs) > 1 else None}
    if locations:
        name = locations[-1]["name"]
        if _norm(name) not in _norm(_one(soup, "h1").get_text(" ", strip=True)):
            _fail("visible heading disagrees with geographic identity")
        identity["AreaLevel"] = ("City" if len(locations) == 1 else
                                 "Region" if _is_region(name) else
                                 "Neighborhood" if _is_region(locations[-2]["name"]) else "Area")
    retrieved = _now()
    modified = records["Dataset"].get("dateModified")
    warnings = []
    if modified:
        try:
            timestamp = _dt.datetime.fromisoformat(modified.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                warnings.append("UnverifiedSourceDateModified")
            elif timestamp > retrieved:
                warnings.append("FutureSourceDateModified")
        except (ValueError, TypeError, AttributeError):
            warnings.append("UnverifiedSourceDateModified")
    if records["WebPage"].get("dateModified") != modified:
        warnings.append("ConflictingSourceDateModified")
    attrs = {"SourceURL": url, "RetrievedAt": retrieved.isoformat(),
             "SourceDateModified": modified,
             "SourceTemporalCoverage": records["Dataset"].get("temporalCoverage"),
             "MetadataWarnings": warnings,
             "SourceBreadcrumb": [{"AreaName": c["name"], "SourceURL": c["item"]} for c in crumbs]}
    return soup, identity, attrs


def _is_region(name):
    return bool(_re.fullmatch(r"منطقه\s*[0-9]+", _plain(name)))


def _trust(node):
    badges = node.select('[data-testid="trust-badge"]')
    if not badges:
        return "PublishedListings"
    codes = {b.get("data-trust") for b in badges}
    if len(codes) != 1 or not codes <= {"MODELED", "IMPUTED"}:
        _fail("unknown or conflicting data-quality classification")
    return {"MODELED": "Modeled", "IMPUTED": "Imputed"}[codes.pop()]


def _methodology(soup, denomination):
    indicators = _one(soup, '[data-testid="market-indicators"]')
    basis = _one(indicators, '[data-testid="market-indicators-basis"]').get_text()
    if _norm(basis) != _norm("همه شاخص‌ها برای هر متر مربع است."):
        _fail("unverified per-square-meter basis")
    text = _norm(indicators.get_text(" ", strip=True))
    if denomination in ("usd", "gold") and (
            _norm("نرخ دلار بازار آزاد") not in text or
            _norm("قیمت گرم طلای ۱۸ عیار در همان ماه محاسبه می‌شود") not in text):
        _fail("unverified native monthly USD/18-karat gold methodology")


def _frame(rows, columns, numeric, attrs):
    result = _pd.DataFrame(rows, columns=columns)
    for col in columns:
        result[col] = result[col].astype("Float64" if col in numeric else "string")
    result.attrs = attrs
    return result


def _snapshot_rows(soup, identity):
    node = _one(soup, '[data-testid="market-stats"]')
    rows, unavailable, seen = [], [], set()
    for section in node.find_all("section", recursive=False):
        heading = _norm(_one(section, "h2").get_text(" ", strip=True))
        if heading == _norm("قیمت فروش بر اساس آگهی‌ها"):
            metrics, category = _SALE_METRICS, "SaleListings"
        elif heading == _norm("قیمت اجاره بر اساس آگهی‌ها"):
            metrics, category = _RENT_METRICS, "RentalListings"
        else:
            _fail("unknown market-statistic section")
        if category in seen:
            _fail("duplicate market-statistic section")
        seen.add(category)
        empty = section.select('[data-testid="market-stats-empty"]')
        if empty:
            if section.select('[data-testid="market-stat"]') or len(empty) != 1 or _norm(empty[0].get_text()) != _norm("در حال حاضر داده‌ای برای نمایش وجود ندارد"):
                _fail("inconsistent empty statistic section")
            unavailable.append(category)
            continue
        month = _period_label(_one(section, '[data-testid="market-stats-period"]').get_text(), "به‌روز تا")
        if category == "RentalListings":
            methodology = _one(soup, '[data-testid="market-indicators"]').get_text(" ", strip=True)
            if _norm("میانه اجاره ماهانه مؤثر آگهی‌های همان محدوده") not in _norm(methodology):
                _fail("unverified monthly effective rental-listing methodology")
        found = set()
        for stat in section.select('[data-testid="market-stat"]'):
            label = _norm(_one(stat, "dt").get_text(" ", strip=True))
            matches = [value for key, value in metrics.items() if _norm(key) == label]
            if not matches:
                continue  # Deliberately omit less-established/unsupported indicators.
            metric, unit, suffix = matches[0]
            if metric in found:
                _fail("duplicate market statistic")
            found.add(metric)
            # Later dd elements contain trust badges, not financial observations.
            values = stat.find_all("dd", recursive=False)
            if not values:
                _fail("missing statistic value")
            value = _number(values[0].get_text(" ", strip=True), suffix, nonnegative=unit != "Percent")
            if unit == "Listings" and not _pd.isna(value) and not value.is_integer():
                _fail("noninteger rental listing count")
            basis = _trust(stat)
            if metric.startswith("Estimated") and basis == "PublishedListings":
                basis = "SourceEstimate"
            rows.append({**identity, "JalaliMonth": month, "Metric": metric,
                         "Value": value, "Unit": unit, "DataBasis": basis})
        if category == "SaleListings" and found != {m[0] for m in _SALE_METRICS.values()}:
            _fail("missing required listing statistics")
    if seen != {"SaleListings", "RentalListings"} or "SaleListings" in unavailable:
        _fail("no verified sale-statistic contract")
    return rows, unavailable


def get_kilid_house_price_history(area, period="1y", denomination="toman") -> _pd.DataFrame:
    """Return KILID's complete published monthly listing-price table per m².

    area is a source slug from get_kilid_areas; period is '6m', '1y' or '3y';
    denomination is 'toman', 'usd' or 'gold' (grams of 18-karat gold).
    JalaliMonth contains YYYY-MM labels, never invented daily observations.
    Native monthly FX/gold values are used directly. Requested months need not
    equal row count. Raises ValueError for invalid inputs and RuntimeError for
    HTTP/access errors or unverifiable identity, units, selection/completeness.
    See docs/kilid.md for columns, metadata, revisions and usage restrictions.
    """
    area = _area(area)
    if not isinstance(period, str) or period not in _PERIODS:
        raise ValueError("period must be '6m', '1y' or '3y'")
    if not isinstance(denomination, str) or denomination not in _UNITS:
        raise ValueError("denomination must be 'toman', 'usd' or 'gold'")
    soup, identity, attrs = _fetch(area, period, denomination)
    controls = _one(soup, '[data-testid="trend-controls"]')
    selected = controls.select('a[aria-current="page"]')
    label = {"6m": "6ماه", "1y": "1سال", "3y": "3سال"}[period]
    canonical_path = _urlsplit(_BASE + "/" + area).path
    expected_query = dict(_parse_qsl(_urlsplit(attrs["SourceURL"]).query))
    if len(selected) != 2 or {_norm(x.get_text()) for x in selected} != {label, "قیمت"}:
        _fail("unverified period/price selection")
    tile = _one(soup, f'[data-testid="indicator-tile-{denomination}"][aria-current="page"]')
    if len(soup.select('[data-testid^="indicator-tile-"][aria-current="page"]')) != 1:
        _fail("ambiguous denomination selection")
    for link in selected + [tile]:
        parts = _urlsplit(link.get("href", ""))
        if parts.path != canonical_path or parts.netloc or parts.scheme or parts.fragment or dict(_parse_qsl(parts.query)) != expected_query:
            _fail("unverified source selection")
    _methodology(soup, denomination)
    stats, _ = _snapshot_rows(soup, identity)
    price_stat = next(r for r in stats if r["Metric"] == "MedianListingPricePerSquareMeter")
    if price_stat["DataBasis"] != "PublishedListings":
        _fail("modeled/imputed area is not a verified observed listing history")
    table = _one(soup, '[data-testid="trend-table"] table')
    headers = [_norm(x.get_text()) for x in table.select("thead th")]
    second = {"toman": "مقدار", "usd": "قیمت هر متر مربع به دلار",
              "gold": "قیمت هر متر مربع به گرم طلای ۱۸ عیار"}[denomination]
    if headers != [_norm("دوره"), _norm(second)]:
        _fail("incorrect history denomination/header")
    caption = _one(table, "caption").get_text(" ", strip=True)
    match = _re.fullmatch(r"روند قیمت از (.+) تا (.+)", caption)
    if not match:
        _fail("missing history bounds")
    first, last = _month(match[1]), _month(match[2])
    if _one(soup, '[data-testid="trend-chart"] > figcaption').get_text(" ", strip=True) != caption:
        _fail("conflicting chart/table history bounds")
    rows = []
    for row in table.select("tbody tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) != 2:
            _fail("malformed history row")
        month = _month(cells[0].get_text(" ", strip=True))
        value = _number(cells[1].get_text(" ", strip=True), _SUFFIXES[denomination])
        rows.append({"JalaliMonth": month, **identity, "MedianListingPricePerSquareMeter": value,
                     "Denomination": denomination, "Unit": _UNITS[denomination], "SourceURL": attrs["SourceURL"]})
    months = [r["JalaliMonth"] for r in rows]
    expected_count = _month_number(last) - _month_number(first) + 1
    if not rows or len(rows) > _PERIODS[period] or len(rows) != expected_count or months != sorted(set(months)) or months[0] != first or months[-1] != last:
        _fail("unverifiable history completeness: missing/duplicate months or inconsistent bounds")
    if any(_month_number(b) - _month_number(a) != 1 for a, b in zip(months, months[1:])):
        _fail("unverifiable history completeness: interior missing months")
    if all(_pd.isna(r["MedianListingPricePerSquareMeter"]) for r in rows):
        _fail("history contains no numerical observations")
    iran_date = _dt.datetime.fromisoformat(attrs["RetrievedAt"]).astimezone(_ZoneInfo("Asia/Tehran")).date()
    current = _jd.date.fromgregorian(date=iran_date)
    current_month = f"{current.year:04d}-{current.month:02d}"
    if last > current_month:
        _fail("future reporting month is not a historical observation")
    coverage = attrs["SourceTemporalCoverage"]
    if coverage:
        try:
            converted = [_jd.date.fromgregorian(date=_dt.date.fromisoformat(d)) for d in coverage.split("/")]
            if [f"{d.year:04d}-{d.month:02d}" for d in converted] != [first, last]:
                attrs["MetadataWarnings"].append("SourceCoverageDiffersFromTable")
        except (ValueError, TypeError, AttributeError):
            attrs["MetadataWarnings"].append("UnverifiedSourceTemporalCoverage")
    attrs.update({"RequestedMonths": _PERIODS[period], "SourceRowCount": len(rows),
                  "FirstJalaliMonth": first, "LastJalaliMonth": last,
                  "CurrentMonthIncluded": last == current_month,
                  "PriceBasis": "MedianApartmentListings", "Completeness": "PublishedTableAndMonthBounds"})
    return _frame(rows, ["JalaliMonth"] + _IDENTITY + ["MedianListingPricePerSquareMeter", "Denomination", "Unit", "SourceURL"],
                  {"MedianListingPricePerSquareMeter"}, attrs)


def get_kilid_house_price_snapshot(area) -> _pd.DataFrame:
    """Return latest published sale/rental listing statistics in long format.

    area is a source slug. Each Metric/Value has its own JalaliMonth, Unit and
    DataBasis, retaining modeled/imputed values as explicitly classified data.
    Chart values, undefined liquidity and forecasts are excluded. ValueError
    signals invalid input; RuntimeError signals failed/unverifiable retrieval.
    See docs/kilid.md for the supported metrics and missing-section behavior.
    """
    soup, identity, attrs = _fetch(_area(area))
    rows, unavailable = _snapshot_rows(soup, identity)
    for row in rows:
        row["SourceURL"] = attrs["SourceURL"]
    attrs.update({"SourceSection": "MarketStatistics", "UnavailableSections": unavailable})
    return _frame(rows, _IDENTITY + ["JalaliMonth", "Metric", "Value", "Unit", "DataBasis", "SourceURL"], {"Value"}, attrs)


def _comparisons(area):
    soup, identity, attrs = _fetch(area)
    node = _one(soup, '[data-testid="area-comparison"]')
    tables = node.select("table")
    if not tables:
        _fail("missing geographic comparison tables")
    root = area is None
    if not root:
        _methodology(soup, "gold")
    headers = ["محدوده", "قیمت هر متر مربع"] + ([] if root else ["به دلار", "به طلا (گرم)", "اجاره متری"]) + ["ماهانه", "سالانه"] + ([] if root else ["روند یک‌ساله"])
    months, rows = [], []
    numeric = ["PublishedPricePerSquareMeterToman", "PublishedPricePerSquareMeterUSD",
               "PublishedPricePerSquareMeterGold18KGrams", "PublishedMonthlyPriceChange", "PublishedYearlyPriceChange"]
    for table in tables:
        if [_norm(t.get_text()) for t in table.select("thead th")] != [_norm(t) for t in headers]:
            _fail("changed geographic comparison headers")
        months.append(_period_label(_one(table, "caption").get_text(" ", strip=True), "قیمت‌ها بر اساس آگهی‌های"))
        for row in table.select("tbody tr"):
            if row.get("data-testid") == "comparison-parent-row":
                continue  # This aggregate has a different identity/basis from children.
            if row.get("data-testid") != "comparison-row":
                _fail("unknown geographic comparison row")
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) != len(headers):
                _fail("malformed geographic comparison row")
            link = _one(cells[0], 'a[data-testid="comparison-link"]')
            slug, name = _slug(link.get("href")), link.get_text(" ", strip=True)
            level = ("City" if root else "Region" if _is_region(name) else
                     "Neighborhood" if identity["AreaLevel"] in ("Region", "Neighborhood") else "Area")
            values = [_number(cells[1].get_text(" ", strip=True), "تومان")]
            values += ([_pd.NA, _pd.NA] if root else
                       [_number(cells[2].get_text(" ", strip=True), "دلار"), _number(cells[3].get_text(" ", strip=True), "گرم")])
            offset = 2 if root else 5
            values += [_number(cells[i].get_text(" ", strip=True), "%", nonnegative=False) for i in (offset, offset + 1)]
            rows.append({"Area": slug, "AreaName": name, "AreaLevel": level,
                         "ListedUnderArea": area, "JalaliMonth": months[-1],
                         **dict(zip(numeric, values)), "DataBasis": _trust(cells[0]), "SourceURL": _BASE + "/" + slug})
    if len(set(months)) != 1 or not rows or len({r["Area"] for r in rows}) != len(rows):
        _fail("incomplete/duplicate comparisons or inconsistent reporting months")
    if root:
        counts = [h for h in soup.select("h3") if _norm(h.get_text()) == _norm("شهرهای زیر پوشش")]
        if len(counts) != 1:
            _fail("missing source city count")
        count = _number(_one(counts[0].parent, "p").get_text(" ", strip=True), "شهر")
        if _pd.isna(count) or count != len(rows):
            _fail("incomplete city list disagrees with source count")
    # Chips independently enumerate the same areas, including folded table rows.
    chips = soup.select('[data-testid="area-chip"]')
    if chips:
        chip_slugs = [_slug(c.get("href")) for c in chips]
        if len(chip_slugs) != len(set(chip_slugs)) or set(chip_slugs) | ({area} if identity["AreaLevel"] == "Neighborhood" else set()) != {r["Area"] for r in rows}:
            _fail("incomplete comparison tables disagree with geographic links")
    attrs.update({"SourceSection": "AreaComparison", "SourceRowCount": len(rows),
                  "Scope": "PublishedRelatedAreas", "PercentageUnit": "Percent",
                  "PriceUnits": ["TomanPerSquareMeter", "USDPerSquareMeter", "Gram18KGoldPerSquareMeter"]})
    return _frame(rows, ["Area", "AreaName", "AreaLevel", "ListedUnderArea", "JalaliMonth"] + numeric + ["DataBasis", "SourceURL"], set(numeric), attrs)


def get_kilid_areas(area=None) -> _pd.DataFrame:
    """Discover one page's published areas, without recursively crawling.

    None lists the source's cities. A source slug lists its related areas,
    including folded rows. ListedUnderArea is display context, not a verified
    geographic parent. Unknown geographic levels remain 'Area'. Raises
    ValueError for invalid slugs and RuntimeError for unverifiable retrieval.
    """
    frame = _comparisons(None if area is None else _area(area))
    return frame[["Area", "AreaName", "AreaLevel", "ListedUnderArea", "DataBasis", "SourceURL"]].copy()


def get_kilid_area_comparison(area) -> _pd.DataFrame:
    """Return all published related-area comparison rows for a source slug.

    Includes folded rows, source model classifications and reporting month.
    Numeric native toman/USD/18K-gold per-m² values and percentage-point growth
    preserve missing values without derived conversions. Related areas may be
    siblings; ListedUnderArea is not an assertion of parentage. ValueError
    signals invalid input; RuntimeError signals failed/unverifiable retrieval.
    """
    return _comparisons(_area(area))
