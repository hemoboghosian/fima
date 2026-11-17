"""Deterministic tests against small, sanitized public aggregate tables."""
from copy import deepcopy
from datetime import datetime, timezone
import inspect
from pathlib import Path
import subprocess
import sys

from bs4 import BeautifulSoup
import pandas as pd
import pytest
import requests

import fima
import fima.KILID as kilid


FIXTURES = Path(__file__).parent / "fixtures" / "kilid"
BASE = "https://kilid.com/house-prices"


def page(name="region5-usd-36"):
    return (FIXTURES / (name + ".html")).read_text(encoding="utf-8")


class Response:
    def __init__(self, html, url, status=200, kind="text/html; charset=utf-8"):
        self.content = html.encode("utf-8")
        self.url, self.status_code = url, status
        self.headers = {"Content-Type": kind}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


@pytest.fixture
def install(monkeypatch):
    def factory(name="region5-usd-36", html=None, status=200, url=None, error=None,
                kind="text/html; charset=utf-8", headers=None):
        calls = []

        def get(request_url, **kwargs):
            calls.append((request_url, kwargs))
            if error:
                raise error
            response = Response(page(name) if html is None else html,
                                url or request_url, status, kind)
            response.headers.update(headers or {})
            return response

        monkeypatch.setattr(kilid._requests, "get", get)
        monkeypatch.setattr(kilid, "_now", lambda: datetime(2026, 11, 17, tzinfo=timezone.utc))
        return calls
    return factory


def changed(selector, action, name="region5-usd-36"):
    soup = BeautifulSoup(page(name), "html.parser")
    action(soup.select_one(selector))
    return str(soup)


def history():
    return kilid.get_kilid_house_price_history("tehran-region5", "3y", "usd")


def test_public_signatures_and_exports():
    expected = {
        "get_kilid_areas": "(area=None)",
        "get_kilid_house_price_history": "(area, period='1y', denomination='toman')",
        "get_kilid_house_price_snapshot": "(area)",
        "get_kilid_area_comparison": "(area)",
    }
    assert set(kilid.__all__) == set(expected)
    for name, signature in expected.items():
        fn = getattr(kilid, name)
        assert getattr(fima, name) is fn
        sig = inspect.signature(fn)
        assert str(sig.replace(return_annotation=inspect.Signature.empty)) == signature
        assert sig.return_annotation is pd.DataFrame


@pytest.mark.parametrize("name,period,denom,count,first,last,unit,start,end", [
    ("region5-toman-36", "3y", "toman", 36, 90000000, 290900000,
     "TomanPerSquareMeter", "1402-09", "1405-08"),
    ("region5-usd-36", "3y", "usd", 35, 1783, 1060,
     "USDPerSquareMeter", "1402-09", "1405-07"),
    ("region5-gold-36", "3y", "gold", 35, 36.6, 10.7,
     "Gram18KGoldPerSquareMeter", "1402-09", "1405-07"),
    ("region5-usd-6", "6m", "usd", 6, 1180, 1060,
     "USDPerSquareMeter", "1405-02", "1405-07"),
    ("region5-toman-12", "1y", "toman", 12, 126200000, 290900000,
     "TomanPerSquareMeter", "1404-09", "1405-08"),
])
def test_real_native_histories(install, name, period, denom, count, first, last,
                             unit, start, end):
    calls = install(name)
    frame = kilid.get_kilid_house_price_history("tehran-region5", period, denom)
    assert len(frame) == count
    assert frame.JalaliMonth.iloc[[0, -1]].tolist() == [start, end]
    assert frame.MedianListingPricePerSquareMeter.iloc[[0, -1]].tolist() == [first, last]
    assert str(frame.MedianListingPricePerSquareMeter.dtype) == "Float64"
    assert set(frame.Unit) == {unit}
    assert set(frame.Area) == {"tehran-region5"}
    assert set(frame.AreaName) == {"منطقه 5"}
    assert set(frame.AreaLevel) == {"Region"}
    assert set(frame.SourceParentArea) == {"tehran"}
    assert str(frame.JalaliMonth.dtype) == "string"
    assert not any("Date" in name for name in frame.columns)
    assert frame.attrs["SourceRowCount"] == count
    assert frame.attrs["RequestedMonths"] == {"6m": 6, "1y": 12, "3y": 36}[period]
    assert frame.attrs["Completeness"] == "PublishedTableAndMonthBounds"
    assert frame.attrs["CurrentMonthIncluded"] is (denom == "toman")
    assert len(calls) == 1
    assert calls[0][1]["timeout"] == (10, 30)
    assert calls[0][1]["allow_redirects"] is False
    assert "verify" not in calls[0][1] or calls[0][1]["verify"] is True


def test_metadata_is_not_freshness(install):
    install()
    frame = history()
    assert frame.attrs["SourceDateModified"] == "2026-11-22T00:00:00.000Z"
    assert "FutureSourceDateModified" in frame.attrs["MetadataWarnings"]
    assert frame.attrs["RetrievedAt"] == "2026-11-17T00:00:00+00:00"
    assert frame.attrs["SourceTemporalCoverage"] == "2023-11-22/2026-10-23"
    assert "SourceCoverageDiffersFromTable" in frame.attrs["MetadataWarnings"]


@pytest.mark.parametrize("name,area,last", [
    ("region1", "tehran-region1", 571300000),
    ("moradabad", "tehran-region5-moradabad", 367800000),
    ("tehran", "tehran", 237200000),
])
def test_other_geographies(install, name, area, last):
    install(name)
    frame = kilid.get_kilid_house_price_history(area)
    assert len(frame) == 12
    assert frame.MedianListingPricePerSquareMeter.iloc[-1] == last
    assert set(frame.Area) == {area}
    if name == "moradabad":
        assert set(frame.AreaLevel) == {"Neighborhood"}
        assert set(frame.SourceParentArea) == {"tehran-region5"}


def test_discovery_is_scoped_and_preserves_mixed_levels(install):
    calls = install("index")
    cities = kilid.get_kilid_areas()
    assert len(cities) == 36 and len(calls) == 1
    assert set(cities.AreaLevel) == {"City"}
    assert cities.loc[cities.Area == "shahriar", "DataBasis"].item() == "Modeled"
    assert cities.ListedUnderArea.isna().all()
    assert "sowme'eh_sara" in set(cities.Area)
    install("tehran")
    children = kilid.get_kilid_areas("tehran")
    assert len(children) == 40
    assert sum(children.AreaLevel == "Region") == 22
    assert sum(children.AreaLevel == "Area") == 18
    assert children.loc[children.Area == "tehran-mlkabad", "DataBasis"].item() == "PublishedListings"
    install()
    neighborhoods = kilid.get_kilid_areas("tehran-region5")
    assert len(neighborhoods) == 25
    assert set(neighborhoods.AreaLevel) == {"Neighborhood"}
    # A slug without a region component is still discovered from the source.
    assert "tehran-shhrk_nft_mntkh_5" in set(neighborhoods.Area)


def test_comparison_includes_folded_rows_and_native_missing_values(install):
    install()
    frame = kilid.get_kilid_area_comparison("tehran-region5")
    assert len(frame) == 25
    assert frame.Area.is_unique
    assert frame.PublishedPricePerSquareMeterUSD.isna().all()
    assert frame.PublishedPricePerSquareMeterGold18KGrams.isna().all()
    first = frame.iloc[0]
    assert first.Area == "tehran-region5-moradabad"
    assert first.PublishedPricePerSquareMeterToman == 371400000
    assert first.PublishedMonthlyPriceChange == 24.3
    assert first.PublishedYearlyPriceChange == 343.8
    assert set(frame.JalaliMonth) == {"1405-08"}
    assert set(frame.ListedUnderArea) == {"tehran-region5"}
    assert "Forecast" not in str(frame.columns)


def test_snapshot_uses_statistic_section_and_keeps_rental_dates(install):
    install("moradabad")
    frame = kilid.get_kilid_house_price_snapshot("tehran-region5-moradabad")
    rows = frame.set_index("Metric")
    assert rows.loc["MedianListingPricePerSquareMeter", "Value"] == 371400000
    assert rows.loc["MedianTotalListingPrice", "Value"] == 29000000000
    assert rows.loc["MonthlyListingPriceChange", "Value"] == 24.3
    assert rows.loc["MedianEffectiveRentalListingPricePerSquareMeter", "Value"] == 700000
    assert rows.loc["RentalListingCount", "Value"] == 76
    assert str(frame.Value.dtype) == "Float64"
    assert not any("Liquidity" in x or "Forecast" in x for x in frame.Metric)
    install("shahriar")
    frame = kilid.get_kilid_house_price_snapshot("shahriar")
    rows = frame.set_index("Metric")
    assert rows.loc["MedianListingPricePerSquareMeter", "DataBasis"] == "Modeled"
    assert rows.loc["MonthlyListingPriceChange", "DataBasis"] == "Imputed"
    assert rows.loc["RentalListingCount", "JalaliMonth"] == "1402-04"
    assert rows.loc["MedianTotalListingPrice", "JalaliMonth"] == "1405-08"


def test_valid_empty_rental_section_is_not_zero(install):
    install("region5-toman-12")
    frame = kilid.get_kilid_house_price_snapshot("tehran-region5")
    assert len(frame) == 3
    assert frame.attrs["UnavailableSections"] == ["RentalListings"]


def test_monthly_rental_unit_requires_source_methodology(install):
    install(html=page('moradabad').replace('اجاره ماهانه مؤثر', 'اجاره سالانه مؤثر'))
    with pytest.raises(RuntimeError, match='monthly effective rental'):
        kilid.get_kilid_house_price_snapshot('tehran-region5-moradabad')


@pytest.mark.parametrize("area", [None, "", "../tehran", "https://kilid.com/house-prices/tehran",
                                  "tehran?denom=usd", "تهران", 5, "-tehran", "tehran/"])
def test_invalid_area_before_network(install, area):
    calls = install()
    with pytest.raises(ValueError, match="area"):
        kilid.get_kilid_house_price_history(area)
    assert not calls


@pytest.mark.parametrize("period,denom", [("36", "usd"), (36, "usd"), ("2y", "usd"),
                                         (None, "usd"), ("3y", "rial"), ("3y", "USD"),
                                         ("3y", None), ([], "usd"), ("3y", [])])
def test_unsupported_choices_before_network(install, period, denom):
    calls = install()
    with pytest.raises(ValueError):
        kilid.get_kilid_house_price_history("tehran-region5", period, denom)
    assert not calls


@pytest.mark.parametrize("error", [requests.Timeout("timeout"), requests.exceptions.SSLError("TLS"),
                                  requests.ConnectionError("offline")])
def test_network_errors_are_chained(install, error):
    calls = install(error=error)
    with pytest.raises(RuntimeError, match="KILID") as caught:
        history()
    assert caught.value.__cause__ is error
    assert len(calls) == 1


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 503])
def test_http_failures_are_not_empty_or_retried(install, status):
    calls = install(status=status, headers={"Retry-After": "120"})
    with pytest.raises(RuntimeError, match=str(status)):
        history()
    assert len(calls) == 1


@pytest.mark.parametrize("status,url", [(302, BASE + "/tehran"), (200, BASE + "/tehran"),
                                       (200, BASE + "/tehran-region5?months=6&denom=usd")])
def test_wrong_response_location_or_selection(install, status, url):
    install(status=status, url=url)
    with pytest.raises(RuntimeError):
        history()


@pytest.mark.parametrize("html", ["<html><title>Access denied</title></html>",
                                 "<html><title>CAPTCHA</title></html>", "", page()[:-20]])
def test_challenge_empty_and_partial_html_rejected(install, html):
    install(html=html)
    with pytest.raises(RuntimeError):
        history()


@pytest.mark.parametrize("selector", ['link[rel="canonical"]', 'script[type="application/ld+json"]',
                                     '[data-testid="trend-table"]',
                                     '[data-testid="trend-controls"]',
                                     '[data-testid="indicator-tile-usd"]'])
def test_missing_contract_elements(install, selector):
    install(html=changed(selector, lambda x: x.decompose()))
    with pytest.raises(RuntimeError):
        history()


def test_wrong_canonical_identity(install):
    install(html=changed('link[rel="canonical"]', lambda x: x.__setitem__('href', BASE + '/tehran')))
    with pytest.raises(RuntimeError, match="identity"):
        history()


def test_visible_heading_identity_must_agree(install):
    install(html=changed('h1', lambda x: setattr(x, 'string', 'قیمت مسکن در منطقه 1 تهران')))
    with pytest.raises(RuntimeError, match='identity'):
        history()


def test_future_history_month_is_rejected(install):
    html = page('region1').replace('1405', '1406').replace('1404', '1405')
    install(html=html)
    with pytest.raises(RuntimeError, match='future reporting month'):
        kilid.get_kilid_house_price_history('tehran-region1')


def test_city_count_detects_interior_truncation(install):
    install('index', html=changed('[data-testid="comparison-row"]', lambda x: x.decompose(), name='index'))
    with pytest.raises(RuntimeError, match='source count'):
        kilid.get_kilid_areas()


@pytest.mark.parametrize('mutation', ['malformed', 'identity', 'breadcrumb', 'duplicate'])
def test_bad_structured_metadata(install, mutation):
    import json
    soup = BeautifulSoup(page(), 'html.parser')
    scripts = soup.select('script[type="application/ld+json"]')
    if mutation == 'malformed':
        scripts[1].string = '{'
    elif mutation == 'duplicate':
        scripts[1].insert_after(deepcopy(scripts[1]))
    else:
        data = json.loads(scripts[0 if mutation == 'breadcrumb' else 1].get_text())
        if mutation == 'breadcrumb':
            del data['itemListElement'][0]['item']
            scripts[0].string = json.dumps(data)
        else:
            data['url'] = BASE + '/tehran'
            scripts[1].string = json.dumps(data)
    install(html=str(soup))
    with pytest.raises(RuntimeError):
        history()


def test_inconsistent_metadata_is_exposed(install):
    import json
    soup = BeautifulSoup(page(), 'html.parser')
    script = soup.select('script[type="application/ld+json"]')[1]
    data = json.loads(script.get_text())
    data['dateModified'] = '2026-11-16T00:00:00.000Z'
    script.string = json.dumps(data)
    install(html=str(soup))
    assert 'ConflictingSourceDateModified' in history().attrs['MetadataWarnings']


def test_percent_sign_direction_and_valid_zero(install):
    soup = BeautifulSoup(page(), 'html.parser')
    row = soup.select_one('[data-testid="comparison-row"]')
    cells = row.find_all('td', recursive=False)
    cells[0].string = '۰ تومان'
    cells[4].string = '\u200e−۰٫۱٪'
    install(html=str(soup))
    first = kilid.get_kilid_area_comparison('tehran-region5').iloc[0]
    assert first.PublishedPricePerSquareMeterToman == 0
    assert first.PublishedMonthlyPriceChange == -0.1


@pytest.mark.parametrize('mutation', ['duplicate', 'missing', 'badunit', 'unknownbadge'])
def test_invalid_snapshot_statistics(install, mutation):
    soup = BeautifulSoup(page('moradabad'), 'html.parser')
    stat = soup.select_one('[data-testid="market-stat"]')
    if mutation == 'duplicate':
        stat.insert_after(deepcopy(stat))
    elif mutation == 'missing':
        stat.decompose()
    elif mutation == 'badunit':
        stat.dd.string = '۳۷۱ میلیون ریال'
    else:
        badge = soup.new_tag('span', attrs={'data-testid': 'trust-badge', 'data-trust': 'UNKNOWN'})
        stat.append(badge)
    install(html=str(soup))
    with pytest.raises(RuntimeError):
        kilid.get_kilid_house_price_snapshot('tehran-region5-moradabad')


@pytest.mark.parametrize("change", ["duplicate", "interior", "first", "last", "nonfinite",
                                  "wrongunit", "negative", "month", "percent", "empty"])
def test_incomplete_or_invalid_history(install, change):
    soup = BeautifulSoup(page(), "html.parser")
    rows = soup.select('[data-testid="trend-table"] tbody tr')
    if change == "duplicate":
        rows[1].insert_after(deepcopy(rows[1]))
    elif change in ("interior", "first", "last"):
        rows[{"interior": 5, "first": 0, "last": -1}[change]].decompose()
    elif change in ("nonfinite", "wrongunit", "negative", "percent"):
        rows[1].td.string = {"nonfinite": "NaN دلار", "wrongunit": "۱٬۷۸۳ تومان",
                             "negative": "−۱ دلار", "percent": "۲٪"}[change]
    elif change == "month":
        rows[1].th.string = "آذر - 1499"
    else:
        for row in rows:
            row.decompose()
    install(html=str(soup))
    with pytest.raises(RuntimeError):
        history()


def test_true_missing_value_is_preserved(install):
    install(html=changed('[data-testid="trend-table"] tbody tr td', lambda x: setattr(x, 'string', '—')))
    frame = history()
    assert pd.isna(frame.MedianListingPricePerSquareMeter.iloc[0])
    assert len(frame) == 35


def test_arabic_digits_and_ascii_separators(install):
    install(html=page().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "٠١٢٣٤٥٦٧٨٩")).replace("٬", ","))
    assert history().MedianListingPricePerSquareMeter.iloc[0] == 1783


def test_wrong_period_even_with_correct_table_bounds(install):
    html = page().replace('aria-current="page" href="/house-prices/tehran-region5?months=36&amp;denom=usd"',
                          'aria-current="page" href="/house-prices/tehran-region5?months=6&amp;denom=usd"')
    assert html != page()
    install(html=html)
    with pytest.raises(RuntimeError, match="selection"):
        history()


def test_gold_methodology_required(install):
    html = page("region5-gold-36").replace("۱۸ عیار", "۲۴ عیار")
    install(html=html)
    with pytest.raises(RuntimeError):
        kilid.get_kilid_house_price_history("tehran-region5", "3y", "gold")


@pytest.mark.parametrize('method', ['get_kilid_house_price_history', 'get_kilid_area_comparison'])
def test_per_square_meter_basis_is_required(install, method):
    html = changed('[data-testid="market-indicators-basis"]', lambda x: setattr(x, 'string', 'قیمت کل'))
    install(html=html)
    with pytest.raises(RuntimeError, match='per-square-meter'):
        if method == 'get_kilid_house_price_history':
            history()
        else:
            getattr(kilid, method)('tehran-region5')


def test_sparse_modeled_history_is_not_observed_history(install):
    install("shahriar")
    with pytest.raises(RuntimeError):
        kilid.get_kilid_house_price_history("shahriar")


@pytest.mark.parametrize("change", ["duplicate", "fold", "header", "unit", "period"])
def test_invalid_comparisons(install, change):
    soup = BeautifulSoup(page(), 'html.parser')
    if change == "duplicate":
        row = soup.select_one('[data-testid="comparison-row"]')
        row.insert_after(deepcopy(row))
    elif change == "fold":
        soup.select_one('[data-testid="comparison-fold"]').decompose()
    elif change == "header":
        soup.select_one('[data-testid="area-comparison"] thead th').string = "قیمت"
    elif change == "unit":
        soup.select_one('[data-testid="comparison-row"] td').string = "۳۷۱ میلیون ریال"
    else:
        soup.select('[data-testid="area-comparison"] caption')[-1].string = 'قیمت‌ها بر اساس آگهی‌های مهر ۱۴۰۵'
    install(html=str(soup))
    with pytest.raises(RuntimeError):
        kilid.get_kilid_area_comparison('tehran-region5')


def test_no_import_time_http():
    code = '''import requests
def fail(*args, **kwargs):
    raise AssertionError("network at import")
requests.sessions.Session.request = fail
import fima
import fima.KILID
assert callable(fima.get_kilid_house_price_history)
'''
    subprocess.run([sys.executable, '-c', code], check=True, capture_output=True, text=True)
