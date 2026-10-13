import datetime as dt
from urllib.parse import parse_qs, urlparse

import jdatetime as jd
import pytest

import fima.Funds as Funds
from .test_funds_http import response


@pytest.fixture
def current_mabna(monkeypatch):
    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 12, 12, 30, 45, 123000, tzinfo=tz)
    monkeypatch.setattr(Funds.dt, "datetime", Clock)
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "fund.example")
    calls = []

    def get(url, **kwargs):
        params = kwargs.get("params") or {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        calls.append((url, params))
        # Current provider fields are verified; query-bound assertions remain exact.
        record = {"date_time": "2026-10-11T00:00:00", "purchase_price": 20,
                  "redemption_price": 30, "statistical_value": 120,
                  "total_net_asset_value_with_buy_commission_and_discount": 50}
        rows = [record] if params["end_date"] >= "2026-10-11" else []
        return response({"data": rows}, url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    return calls


def assert_query(call, size, portfolio=False):
    url, params = call
    assert url == "https://fund.example/api/v2/public/reports/navps"
    expected = {
        "start_date": "1997-11-10T08:13:36.377Z",
        "end_date": "2026-10-12T12:30:45.123Z",
        "page": 1, "size": size,
    }
    if portfolio:
        expected["portfolio_id"] = 1
    assert params == expected


def test_mabna_discovery_includes_recent_history(current_mabna):
    assert Funds._detect_mabna_by_nav_api("fund.example")
    assert_query(current_mabna[0], 5)


def test_mabna_history_includes_recent_dates(current_mabna):
    result = Funds._get_daily_navs_mabna("A")
    assert result["JDate"].tolist() == [jd.date(1405, 7, 19)]
    assert_query(current_mabna[0], 1000000, portfolio=True)
