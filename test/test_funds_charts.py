import copy

import jdatetime as jd
import pytest
import requests

import fima.Funds as Funds
from .test_funds_http import response


@pytest.fixture
def chart():
    return [
        {"name": "صدور", "List": [{"x": "10/11/2026", "y": 10}, {"x": "10/10/2026", "y": 9}]},
        {"name": "آماری", "List": [{"x": "10/09/2026", "y": 19}, {"x": "10/10/2026", "y": 20}]},
        {"name": "ابطال", "List": [{"x": "10/10/2026", "y": 29}, {"x": "10/11/2026", "y": 30}]},
    ]


def mock_chart(monkeypatch, data):
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "fund.example")
    monkeypatch.setattr(Funds.requests, "get", lambda url, **k: response(data, url=url))


@pytest.mark.parametrize("reordered", [False, True])
def test_tadbir_series_are_named_and_joined_by_date(monkeypatch, chart, reordered):
    if reordered:
        chart.reverse()
    mock_chart(monkeypatch, chart)
    result = Funds._get_daily_navs_per_share_tadbirpardaz("Fund A")
    assert result.to_dict("records") == [{
        "Subscription": 9, "Statistical": 20, "Redemption": 29,
        "JDate": jd.date(1405, 7, 18),
    }]


def test_tadbir_leveraged_named_series(monkeypatch):
    names = ["صدور", "آماری", "ابطال", "صدور ممتاز", "ابطال ممتاز", "عادی"]
    data = [{"name": name, "List": [{"x": "10/11/2026", "y": value}]} for value, name in enumerate(names, 1)]
    mock_chart(monkeypatch, data[::-1])
    assert Funds._get_leveraged_daily_navs_per_share_tadbirpardaz("A").to_dict("records") == [{
        "Subscription": 1, "Statistical": 2, "Redemption": 3, "Common": 6,
        "SpecialSubscription": 4, "SpecialRedemption": 5, "JDate": jd.date(1405, 7, 19),
    }]


@pytest.mark.parametrize("bad", ["missing_series", "empty_series", "missing_point", "duplicate_date", "duplicate_series"])
def test_tadbir_rejects_incomplete_or_ambiguous_chart(monkeypatch, chart, bad):
    if bad == "missing_series":
        chart.pop()
    elif bad == "empty_series":
        chart[0]["List"] = []
    elif bad == "missing_point":
        del chart[0]["List"][0]["y"]
    elif bad == "duplicate_date":
        chart[0]["List"].append(copy.deepcopy(chart[0]["List"][0]))
    else:
        chart.append(copy.deepcopy(chart[0]))
    mock_chart(monkeypatch, chart)
    with pytest.raises(ValueError, match="Tadbir"):
        Funds._get_daily_navs_per_share_tadbirpardaz("A")


def test_tadbir_total_nav_ignores_extra_point_fields(monkeypatch):
    mock_chart(monkeypatch, [{"name": "", "List": [{"extra": 8, "y": 100, "x": "10/11/2026", "tooltip": "text"}]}])
    assert Funds._get_daily_total_nav_tadbirpardaz("A").to_dict("records") == [
        {"TotalNAV": 100, "JDate": jd.date(1405, 7, 19)}]


def test_pikad_nav_uses_named_fields(monkeypatch):
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "servatfund.ir")
    data = {"Result": [{"NetAssetValue": 100, "StaticalNAV": 3, "RedemptionNAV": 2,
                        "SubscriptionNAV": 1, "Date": "2026-10-11", "Id": 999}]}
    monkeypatch.setattr(Funds.requests, "post", lambda url, **k: response(data, url=url))
    assert Funds._get_daily_navs_pikad("A").to_dict("records") == [{
        "JDate": jd.date(1405, 7, 19), "Subscription": 1, "Redemption": 2,
        "Statistical": 3, "TotalNAV": 100,
    }]


def test_tadbir_asset_pages_do_not_loop_on_repeated_rows(monkeypatch):
    html = """<table><thead><tr><th>ردیف</th><th>تاریخ</th></tr></thead>
    <tbody><tr><td>1</td><td>1405/07/19</td></tr></tbody>
    <tfoot><tr><td class="pager"><a title="Next page">Next</a></td></tr></tfoot></table>"""
    calls = []
    def get(url, **kwargs):
        calls.append(kwargs["params"]["page"])
        if len(calls) > 2:
            pytest.fail("Repeated provider page was requested indefinitely")
        return response(text=html, url=url)
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "fund.example")
    monkeypatch.setattr(Funds.requests, "get", get)
    monkeypatch.setattr(Funds.time, "sleep", lambda _: None)
    with pytest.raises(ValueError, match="Tadbir.*repeat"):
        Funds._get_daily_asset_allocation_tadbirpardaz("A")
    assert calls == [1, 2]


def test_tadbir_asset_html_without_report_is_a_schema_error(monkeypatch):
    mock_chart(monkeypatch, [])
    monkeypatch.setattr(Funds.requests, "get", lambda url, **k: response(text="<html>Moved</html>", url=url))
    with pytest.raises(ValueError, match="Tadbir"):
        Funds._get_daily_asset_allocation_tadbirpardaz("A")


def test_public_schema_context_preserves_request_exceptions():
    def invalid_url(_):
        raise requests.exceptions.InvalidURL("invalid provider URL")
    with pytest.raises(requests.exceptions.InvalidURL):
        Funds._provider_result(invalid_url, "A", "fund.example")
