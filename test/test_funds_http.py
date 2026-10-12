import json
import subprocess
import sys
import datetime as dt

import jdatetime as jd
import pytest
import requests

import fima
import fima.Funds as Funds


def response(data=None, *, status=200, text=None, headers=None, url="https://fund.example/api"):
    result = requests.Response()
    result.status_code = status
    result.url = url
    result._content = (json.dumps(data) if text is None else text).encode()
    result._content_consumed = True
    result.headers.update(headers or {})
    return result


@pytest.fixture
def catalog():
    return {"items": [{
        "name": "Fund A", "fundType": 1, "typeOfInvest": "Negotiable",
        "fundSize": 100, "initiationDate": "2020-01-01", "date": "2026-10-11",
        "websiteAddress": ["https://fund.example/home"], "guarantor": "----",
        "dividendIntervalPeriod": None,
    }]}


def mock_catalog(monkeypatch, catalog, types=None):
    calls = []
    types = types or {"items": [{"name": "Equity", "isActive": True, "fundType": 1}]}

    def get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        return response(types if url.endswith("fundtype") else catalog)

    def post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        return response(catalog)

    monkeypatch.setattr(Funds.requests, "get", get)
    monkeypatch.setattr(Funds.requests, "post", post)
    return calls


def test_catalog_uses_provider_post_contract_and_optional_weights(monkeypatch, catalog):
    calls = mock_catalog(monkeypatch, catalog)
    result = Funds.get_all_funds()
    assert calls[0][0] == "POST"
    assert calls[0][1] == "https://www.fipiran.ir/services/fund/fundcompare"
    assert calls[0][2]["json"] == {"regNos": [], "showMarketMakers": True}
    assert result.loc[0, "FundType"] == "Equity"
    assert result.loc[0, "WebsiteAddress"] == "fund.example"
    assert result.loc[0, "FundUnits Weight"] == 0
    assert result.loc[0, "UpdateDate"] == jd.date.fromgregorian(date=dt.date(2026, 10, 11))


@pytest.mark.parametrize("website,expected", [
    (None, None), ([], None), (["fund.example", "other.example"], "fund.example"),
    ("https://fund.example/home", "fund.example"), ([None], None),
])
def test_catalog_website_shapes(monkeypatch, catalog, website, expected):
    catalog["items"][0]["websiteAddress"] = website
    mock_catalog(monkeypatch, catalog)
    assert Funds.get_all_funds().loc[0, "WebsiteAddress"] == expected


@pytest.mark.parametrize("data", [None, [], {}, {"items": []}, {"items": [None]}, {"items": [{"name": "A"}]}])
def test_catalog_rejects_missing_or_empty_schema(monkeypatch, data):
    mock_catalog(monkeypatch, data)
    with pytest.raises(ValueError, match="Fipiran"):
        Funds.get_all_funds()


def test_fund_types_are_keyed_independently_of_json_order(monkeypatch):
    monkeypatch.setattr(Funds.requests, "get", lambda *a, **k: response(
        {"items": [{"name": "Equity", "isActive": True, "fundType": 1}]}
    ))
    assert Funds._get_fund_types().iloc[0].to_dict() == {
        "FundTypeID": 1, "FundTypeName": "Equity", "IsActive": True,
    }


@pytest.mark.parametrize("error", [requests.ConnectTimeout, requests.ReadTimeout, requests.ConnectionError, requests.exceptions.SSLError])
def test_probe_preserves_transport_failures(monkeypatch, error):
    def get(*args, **kwargs):
        raise error("provider unavailable")
    monkeypatch.setattr(Funds.requests, "get", get)
    with pytest.raises(error, match="fund.example"):
        Funds._safe_get_json("https://fund.example/api")


@pytest.mark.parametrize("status", [401, 403, 429, 500, 502, 503, 504])
def test_probe_preserves_terminal_http_errors(monkeypatch, status):
    calls = []
    def get(*args, **kwargs):
        calls.append(1)
        return response(status=status, text="", headers={"Retry-After": "120"})
    monkeypatch.setattr(Funds.requests, "get", get)
    monkeypatch.setattr(Funds.time, "sleep", lambda _: None)
    with pytest.raises(requests.HTTPError) as exc:
        Funds._safe_get_json("https://fund.example/api")
    assert exc.value.response.status_code == status
    assert len(calls) <= 2
    if status == 429:
        assert len(calls) == 1  # Do not retry before a provider's long Retry-After.


@pytest.mark.parametrize("status", [404, 405])
def test_probe_can_reject_missing_endpoints(monkeypatch, status):
    monkeypatch.setattr(Funds.requests, "get", lambda *a, **k: response(status=status, text=""))
    assert Funds._safe_get_json("https://fund.example/api") is None


def test_get_retries_one_transient_status_and_verifies_tls(monkeypatch):
    replies = iter([response(status=503, text=""), response({"data": [1]})])
    calls = []
    def get(url, **kwargs):
        calls.append(kwargs)
        return next(replies)
    monkeypatch.setattr(Funds.requests, "get", get)
    monkeypatch.setattr(Funds.time, "sleep", lambda _: None)
    assert Funds._safe_get_json("https://fund.example/api") == {"data": [1]}
    assert len(calls) == 2
    assert all(call["verify"] is True and call["allow_redirects"] is True and call["timeout"] for call in calls)


def test_post_does_not_retry_or_hide_rate_limit(monkeypatch):
    calls = []
    def post(*args, **kwargs):
        calls.append(kwargs)
        return response(status=429, text="")
    monkeypatch.setattr(Funds.requests, "post", post)
    with pytest.raises(requests.HTTPError):
        Funds._safe_post_json("https://fund.example/api", {})
    assert len(calls) == 1
    assert calls[0]["verify"] is True


def test_get_retry_is_bounded(monkeypatch):
    calls, delays = [], []
    def get(url, **kwargs):
        calls.append(url)
        return response(status=503, text="", url=url)
    monkeypatch.setattr(Funds.requests, "get", get)
    monkeypatch.setattr(Funds.time, "sleep", delays.append)
    with pytest.raises(requests.HTTPError):
        Funds._safe_get_json("https://fund.example/api")
    assert len(calls) == 2
    assert delays == [0.5]


def test_catalog_checks_status_before_json(monkeypatch):
    monkeypatch.setattr(Funds.requests, "post", lambda url, **k: response(status=405, text="", url=url))
    with pytest.raises(requests.HTTPError):
        Funds.get_all_funds()


def test_public_provider_schema_error_has_fund_and_website(monkeypatch):
    import pandas as pd
    monkeypatch.setattr(Funds, "get_all_funds", lambda **k: pd.DataFrame([
        {"Name": "Fund A", "WebsiteAddress": "servatfund.ir", "FundType": "Equity"}]))
    monkeypatch.setattr(Funds, "_detect_website_developer", lambda **k: "پیکاد")
    monkeypatch.setattr(Funds.requests, "post", lambda url, **k: response({"Result": [{"unexpected": 1}]}, url=url))
    with pytest.raises(ValueError, match="Fund A.*servatfund.ir"):
        Funds.get_daily_navs("Fund A")


@pytest.mark.parametrize("text", ["", "<html>error</html>"])
def test_known_provider_rejects_invalid_json_with_source(monkeypatch, text):
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "servatfund.ir")
    monkeypatch.setattr(Funds.requests, "post", lambda url, **k: response(text=text, url=url))
    with pytest.raises(ValueError, match="exphoenixfund"):
        Funds._get_daily_navs_pikad("Fund A")


def test_provider_checks_http_status_before_parsing(monkeypatch):
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "servatfund.ir")
    monkeypatch.setattr(Funds.requests, "post", lambda *a, **k: response(status=405, text=""))
    with pytest.raises(requests.HTTPError) as exc:
        Funds._get_daily_navs_pikad("Fund A")
    assert exc.value.response.status_code == 405


def test_detection_does_not_call_timeout_an_unknown_provider(monkeypatch):
    def get(*args, **kwargs):
        raise requests.Timeout("unreachable")
    monkeypatch.setattr(Funds.requests, "get", get)
    with pytest.raises(requests.Timeout):
        Funds._detect_website_developer("fund.example")


def test_nika_does_not_cache_failed_discovery(monkeypatch):
    text = '{"apiPath":"api.example","hivePath":"vhive","basketId":"8","fundId":"8"}'
    replies = iter([None, None, text])
    monkeypatch.setattr(Funds, "_safe_get_text", lambda _: next(replies))
    assert Funds._get_nika_config_by_host("retry-config.example") is None
    assert Funds._get_nika_config_by_host("retry-config.example")["fundId"] == "8"


def test_funds_reload_does_not_request_or_change_warning_filters():
    public_functions = {name: getattr(Funds, name) for name in Funds.__all__}
    # Reload in a child process so later tests retain the package's public aliases.
    subprocess.run([sys.executable, "-c", """
import importlib
import warnings
import fima.Funds as Funds

def unexpected(*args, **kwargs):
    raise AssertionError("HTTP during import")

Funds.requests.get = unexpected
Funds.requests.post = unexpected
with warnings.catch_warnings():
    warnings.resetwarnings()
    before = warnings.filters[:]
    importlib.reload(Funds)
    assert warnings.filters == before
"""], check=True, timeout=30)
    for name, function in public_functions.items():
        assert getattr(Funds, name) is function
        assert getattr(fima, name) is function
