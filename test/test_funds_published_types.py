"""Actual provider reports determine availability, not broad fund categories."""
import pandas as pd
import pytest

import fima.Funds as Funds
from .test_funds_coverage import public_fund, normal_chart, chart
from .test_funds_parent_identity import allocation_html
from .test_funds_http import response


KINDS = ["جسورانه", "خصوصی", "پروژه‌ای", "زمین و ساختمان"]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("assets", [False, True])
def test_published_histories_are_not_rejected_by_fund_category(monkeypatch, kind, assets):
    public_fund(monkeypatch, "گروه رایانه تدبیر پرداز", kind=kind)
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if url == "https://fund.example":
            return response(text="<title>Fund A</title>", url=url)
        if "FundDailyAssetDistribution" in url:
            return response(text=allocation_html(7), url=url)
        return response([chart(70, "")] if "Combination" in url else normal_chart(3), url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    result = (Funds.get_daily_asset_allocation if assets else Funds.get_daily_navs)("Fund A")
    assert result.JalaliDate.tolist() == ["1405-07-19"]
    assert result["TopFiveStocks" if assets else "SubscriptionNAV"].tolist() == [7 if assets else 3]
    assert calls


@pytest.mark.parametrize("kind", KINDS)
def test_optional_developer_discovery_checks_the_actual_provider(monkeypatch, kind):
    calls = []
    monkeypatch.setattr(Funds, "_detect_website_developer", lambda host: calls.append(host) or "Known provider")
    catalog = pd.DataFrame([{"WebsiteAddress": "fund.example", "FundTypeName": kind}])
    assert Funds._autoset_website_developers(catalog, max_workers=1).WebsiteDeveloper.tolist() == ["Known provider"]
    assert calls == ["fund.example"]


@pytest.mark.parametrize("assets", [False, True])
def test_absent_provider_remains_an_explicit_unsupported_error(monkeypatch, assets):
    public_fund(monkeypatch, "Unknown", kind="جسورانه")
    with pytest.raises(NotImplementedError, match="Unknown.*Fund A"):
        (Funds.get_daily_asset_allocation if assets else Funds.get_daily_navs)("Fund A")


def test_published_category_does_not_hide_malformed_reports(monkeypatch):
    public_fund(monkeypatch, "گروه رایانه تدبیر پرداز", kind="پروژه‌ای")
    monkeypatch.setattr(Funds.requests, "get", lambda url, **kwargs: response(text="<html>No report</html>", url=url))
    with pytest.raises(ValueError, match="Tadbir asset report.*malformed"):
        Funds.get_daily_asset_allocation("Fund A")
