import copy

import jdatetime as jd
import pytest
import requests

import fima.Funds as Funds
from .test_funds_http import response


@pytest.fixture
def allocation():
    return {"fundId": 1, "date": "1405/07/19",
            "stockTodayAmount": 1, "stockTodayPercent": 10,
            "bondTodayAmount": 2, "bondTodayPercent": 20,
            "fundUnitTodayAmount": 3, "fundUnitTodayPercent": 30,
            "ccdTodayAmount": 4, "ccdTodayPercent": 40,
            "depositTodayAmount": 5, "depositTodayPercent": 50,
            "cashTodayAmount": 6, "cashTodayPercent": 60,
            "otherAssetTodayAmount": 7, "otherAssetTodayPercent": 70,
            "topFiveStockTodayAmount": 8, "topFiveStockTodayPercent": 80}


def assert_allocation(result):
    assert result.to_dict("records") == [{
        "Date": jd.date(1405, 7, 19), "Stocks": 1, "Upper5%Stocks": 8,
        "Bonds": 2, "Cash": 6, "Bank": 5, "FundUnits": 3, "CCDs": 4,
        "OtherAssets": 7, "Stocks Weight": 10, "Upper5%Stocks Weight": 80,
        "Bonds Weight": 20, "Cash Weight": 60, "Bank Weight": 50,
        "FundUnits Weight": 30, "CCDs Weight": 40, "OtherAssets Weight": 70,
    }]


def mock_resolver(monkeypatch):
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "aghighfund.com")


def test_current_rayan_asset_endpoint_and_schema(monkeypatch, allocation):
    mock_resolver(monkeypatch)
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        if "/api/v1/public/dailyAssetStructure/" in url:
            return response([dict(reversed(list(allocation.items())))], url=url)
        return response(status=404, text="", url=url)
    monkeypatch.setattr(Funds.requests, "get", get)
    assert_allocation(Funds._get_daily_asset_allocation_rayan_hamafza("A"))
    assert calls == ["https://aghighfund.com/api/v1/public/dailyAssetStructure/1"]


@pytest.mark.parametrize("current_reply", ["404", "405", "html", "empty", "changed_schema"])
def test_rayan_legacy_endpoint_is_preserved(monkeypatch, allocation, current_reply):
    mock_resolver(monkeypatch)
    legacy = {key[0].upper() + key[1:]: value for key, value in allocation.items()}
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        if "/api/data/DailyAssetStructure/" in url:
            return response({"data": [legacy]}, url=url)
        if current_reply.isdigit():
            return response(status=int(current_reply), text="", url=url)
        if current_reply == "html":
            return response(text="<html>Legacy site</html>", url=url)
        return response([] if current_reply == "empty" else [{"changed": 1}], url=url)
    monkeypatch.setattr(Funds.requests, "get", get)
    assert_allocation(Funds._get_daily_asset_allocation_rayan_hamafza("A"))
    assert calls[-1] == "https://aghighfund.com/api/data/DailyAssetStructure/1"


@pytest.mark.parametrize("error", [requests.ReadTimeout, requests.exceptions.SSLError])
def test_rayan_transport_error_does_not_downgrade_or_fall_back(monkeypatch, error):
    mock_resolver(monkeypatch)
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        raise error("unreachable")
    monkeypatch.setattr(Funds.requests, "get", get)
    with pytest.raises(error):
        Funds._get_daily_asset_allocation_rayan_hamafza("A")
    assert len(calls) == 1


def test_rayan_rate_limit_does_not_fall_back(monkeypatch):
    mock_resolver(monkeypatch)
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        return response(status=429, text="", url=url, headers={"Retry-After": "120"})
    monkeypatch.setattr(Funds.requests, "get", get)
    with pytest.raises(requests.HTTPError):
        Funds._get_daily_asset_allocation_rayan_hamafza("A")
    assert len(calls) == 1


def test_rayan_validates_every_record(monkeypatch, allocation):
    mock_resolver(monkeypatch)
    rows = [{key[0].upper() + key[1:]: value for key, value in allocation.items()}]
    rows.append(copy.deepcopy(rows[0]))
    del rows[1]["StockTodayAmount"]
    monkeypatch.setattr(Funds.requests, "get", lambda url, **k: response({"data": rows}, url=url))
    with pytest.raises(ValueError, match="Rayan.*aghighfund.com"):
        Funds._get_daily_asset_allocation_rayan_hamafza("A")
