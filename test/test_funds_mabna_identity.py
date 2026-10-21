"""Canonical Mabna histories must not be replaced with a shared-ticker child."""
import pandas as pd
import pytest
import requests

import fima.Funds as Funds
from .test_funds_coverage import public_fund, mabna_nav, current_assets
from .test_funds_http import response


PARENT = "قابل معامله بخشی کیان"
PAGE = "<title>صندوق سرمایه‌گذاری قابل معامله بخشی کیان</title><p>شماره ثبت ۵۶۸۴۸ نزد مرجع ثبت شرکت‌ها</p><p>شماره ثبت ۱۲۲۳۴ نزد سازمان بورس و اوراق بهادار</p>"
ITEMS = [{"id": "1", "name": "فارما کیان"}, {"id": "11", "name": "یوتیلیتی"}]


def setup_site(monkeypatch, *, name=PARENT, items=None, page=PAGE, siblings=(), registration="12234"):
    public_fund(monkeypatch, "پردازش اطلاعات مالی مبنا", name=name)
    row = {"FundName": name, "FundTypeName": "در سهام-بخشی", "FundTypeID": "21",
           "WebsiteAddress": "fund.example", "RegistrationNumber": registration,
           "GroupId": "0", "Ticker": "فارما کیان"}
    catalog = pd.DataFrame([row, *siblings])
    monkeypatch.setattr(Funds, "get_all_funds", lambda **kwargs: catalog.copy())
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        assert kwargs["verify"] is True and kwargs["timeout"] <= 30
        if url.endswith("/portfolios"):
            return response({"data": ITEMS if items is None else items}, url=url)
        if url == "https://fund.example":
            if isinstance(page, Exception):
                raise page
            return response(text=page, url=url)
        params = kwargs["params"]
        selected = params.get("portfolio_id")
        if url.endswith("/navps"):
            row = {**mabna_nav(), "purchase_price": 3 if selected is None else int(selected) + 10}
        else:
            assert url.endswith("/daily-assets")
            row = current_assets()
            row["items"]["assets"][3]["value"] = 4 if selected is None else int(selected) + 10
        return response({"data": [row], "total_count": 1}, url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    return calls


@pytest.mark.parametrize("assets", [False, True])
def test_canonical_legal_fund_omits_child_portfolio_parameter(monkeypatch, assets):
    calls = setup_site(monkeypatch)
    result = (Funds.get_daily_asset_allocation if assets else Funds.get_daily_navs)(PARENT)
    assert result.JalaliDate.tolist() == ["1405-07-19"]
    assert result["Stocks" if assets else "SubscriptionNAV"].tolist() == [4 if assets else 3]
    assert "portfolio_id" not in calls[-1][1]["params"]


@pytest.mark.parametrize("assets", [False, True])
def test_explicit_child_keeps_its_named_portfolio(monkeypatch, assets):
    calls = setup_site(monkeypatch, name="یوتیلیتی")
    result = (Funds.get_daily_asset_allocation if assets else Funds.get_daily_navs)("یوتیلیتی")
    assert result["Stocks" if assets else "SubscriptionNAV"].tolist() == [21]
    assert calls[-1][1]["params"]["portfolio_id"] == 11


@pytest.mark.parametrize("assets", [False, True])
def test_single_renamed_fund_requires_its_published_seo_registration(monkeypatch, assets):
    calls = setup_site(monkeypatch, items=[{"id": "8", "name": "Renamed legal fund"}])
    result = (Funds.get_daily_asset_allocation if assets else Funds.get_daily_navs)(PARENT)
    assert result["Stocks" if assets else "SubscriptionNAV"].tolist() == [18]
    assert calls[-1][1]["params"]["portfolio_id"] == 8


def test_seo_registration_can_follow_its_explicit_authority_label(monkeypatch):
    page = "<title>Other display name</title><p>شماره ثبت نزد سازمان بورس و اوراق بهادار ۱۲۲۳۴</p><p>شماره ثبت نزد مرجع ثبت شرکت‌ها ۵۶۸۴۸</p>"
    calls = setup_site(monkeypatch, items=[{"id": "8", "name": "Other"}], page=page)
    assert Funds.get_daily_navs(PARENT).SubscriptionNAV.tolist() == [18]
    assert calls[-1][1]["params"]["portfolio_id"] == 8


@pytest.mark.parametrize("page", [
    PAGE.replace("۱۲۲۳۴", "۹۹۹۹۹"),
    PAGE.replace("نزد سازمان بورس", "نزد مرجع ثبت"),
    PAGE + "<p>شماره ثبت 99999 نزد سازمان بورس</p>",
])
def test_canonical_title_cannot_fall_back_to_shared_ticker_without_registration(monkeypatch, page):
    calls = setup_site(monkeypatch, page=page)
    with pytest.raises(ValueError, match="Mabna.*identity"):
        Funds.get_daily_navs(PARENT)
    assert not any(url.endswith("/navps") for url, _ in calls)


@pytest.mark.parametrize("page", ["<title>Other</title>", PAGE.replace("۱۲۲۳۴", "۹۹۹۹۹")])
def test_single_unrelated_fund_cannot_use_company_registration(monkeypatch, page):
    setup_site(monkeypatch, items=[{"id": "8", "name": "Other"}], page=page)
    with pytest.raises(NotImplementedError, match="identity"):
        Funds.get_daily_navs(PARENT)


def test_shared_site_cannot_identify_a_single_renamed_fund(monkeypatch):
    sibling = {"FundName": "Sibling", "FundTypeName": "در سهام", "WebsiteAddress": "fund.example",
               "RegistrationNumber": "12234", "GroupId": "1"}
    calls = setup_site(monkeypatch, items=[{"id": "8", "name": "Other"}], siblings=[sibling])
    with pytest.raises(NotImplementedError, match="identity"):
        Funds.get_daily_navs(PARENT)
    assert not any(url == "https://fund.example" for url, _ in calls)


def test_ambiguous_catalog_parent_cannot_fall_back_to_shared_ticker(monkeypatch):
    sibling = {"FundName": PARENT, "FundTypeName": "در سهام-بخشی", "WebsiteAddress": "fund.example",
               "RegistrationNumber": "12234", "GroupId": "1"}
    calls = setup_site(monkeypatch, siblings=[sibling])
    with pytest.raises(ValueError, match="Mabna.*identity"):
        Funds.get_daily_navs(PARENT)
    assert not any(url.endswith("/navps") for url, _ in calls)


def test_canonical_allocation_does_not_use_an_unverified_legacy_fallback(monkeypatch):
    setup_site(monkeypatch)
    get = Funds.requests.get
    calls = []

    def missing_report(url, **kwargs):
        calls.append(url)
        if url.endswith("/daily-assets"):
            return response(status=404, text="", url=url)
        return get(url, **kwargs)

    monkeypatch.setattr(Funds.requests, "get", missing_report)
    with pytest.raises(ValueError, match="Mabna canonical asset"):
        Funds.get_daily_asset_allocation(PARENT)
    assert not any("/api/v1/" in url for url in calls)


@pytest.mark.parametrize("error", [requests.exceptions.SSLError, requests.ReadTimeout])
def test_identity_page_transport_failure_is_preserved(monkeypatch, error):
    setup_site(monkeypatch, page=error("unavailable"))
    with pytest.raises(error):
        Funds.get_daily_navs(PARENT)


@pytest.mark.parametrize("value", [0, -1, "bad"])
def test_renamed_sole_portfolio_still_requires_a_positive_id(monkeypatch, value):
    setup_site(monkeypatch, items=[{"id": value, "name": "Other"}])
    with pytest.raises(ValueError, match="Mabna.*identity"):
        Funds.get_daily_navs(PARENT)
