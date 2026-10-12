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
        # Keep the existing parser's positions; this test characterizes query bounds,
        # not an unverified upstream record-key contract.
        record = {"date_time": "2026-10-11T00:00:00"}
        record.update({f"field_{i}": i * 10 for i in range(1, 13)})
        rows = [record] if params["end_date"] >= "2026-10-11" else []
        return response({"data": rows}, url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    return calls


def assert_query(call, size):
    url, params = call
    assert url == "https://fund.example/api/v2/public/reports/navps"
    assert params == {
        "start_date": "1997-11-10T08:13:36.377Z",
        "end_date": "2026-10-12T12:30:45.123Z",
        "page": 1, "size": size,
    }


def test_mabna_discovery_includes_recent_history(current_mabna):
    assert Funds._detect_mabna_by_nav_api("fund.example")
    assert_query(current_mabna[0], 5)


def test_mabna_history_includes_recent_dates(current_mabna):
    result = Funds._get_daily_navs_mabna("A")
    assert result["JDate"].tolist() == [jd.date(1405, 7, 19)]
    assert_query(current_mabna[0], 1000000)
