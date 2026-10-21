"""Public Nika Oak allocation schema established from source-linked JS and JSON."""
import copy
import datetime as dt
import json
import pandas as pd
import pytest
import requests
import fima.Funds as Funds
from .test_funds_http import response
from .test_funds_coverage import public_fund

CONFIG = {"apiPath": "api.example", "hivePath": "vhive/HivePortal", "oakPath": "voak/oak/v1/api/public",
          "basketId": "8", "fundId": "8", "pamCode": "80166446"}
FIELDS = {"top5Stock": "TopFiveStocks", "otherStock": "OtherStocks", "bond": "Bonds", "cd": "CDs",
          "cashAndBank": "CashAndBank", "mutualFund": "FundUnits", "goldAndBar": "GoldAndBar", "otherAssets": "OtherAssets"}


def record(date="2026-10-19"):
    row = {"onDate": date, "reportDate": "2026-10-20"}
    for i, field in enumerate(FIELDS):
        row[field] = i * 1000000001
        row[field + "Percent"] = i + .25
    return row


def setup_site(monkeypatch, inception="1405-04-29", config=None):
    class Clock(dt.date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 20)
    monkeypatch.setattr(Funds.dt, "date", Clock)
    public_fund(monkeypatch, "سامانه هوشمند نیکا سرمایه")
    frame = pd.DataFrame([{"FundName": "Fund A", "FundTypeName": "در سهام", "FundTypeID": "6",
                           "WebsiteAddress": "fund.example", "InceptionJalaliDate": inception}])
    monkeypatch.setattr(Funds, "get_all_funds", lambda **kwargs: frame.copy())
    monkeypatch.setattr(Funds, "_get_nika_config_by_host", lambda _: CONFIG.copy() if config is None else config)


def test_nika_config_retains_published_oak_path():
    assert Funds._extract_nika_config_from_html(json.dumps(CONFIG))["oakPath"] == CONFIG["oakPath"]


def test_public_nika_historical_allocation_keeps_amounts_weights_and_effective_date(monkeypatch):
    setup_site(monkeypatch)
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        assert url == "https://api.example/voak/oak/v1/api/public/portfolio-composition/daily-asset-percentage"
        params = kwargs["params"]
        assert set(params) == {"pamCode", "fromDate", "toDate"}
        assert params["pamCode"] == "80166446"
        rows = [record()] if params["toDate"] == "2026-10-20" else [record("2026-07-20")]
        return response(rows, url=url)
    monkeypatch.setattr(Funds.requests, "get", get)
    result = Funds.get_daily_asset_allocation("Fund A")
    assert result.JalaliDate.tolist() == ["1405-07-27", "1405-04-29"]
    assert len(calls) == 2
    spans = sorted((dt.date.fromisoformat(k["params"]["fromDate"]), dt.date.fromisoformat(k["params"]["toDate"])) for _, k in calls)
    assert spans[0][0].isoformat() == "2026-07-20"
    assert spans[-1][1].isoformat() == "2026-10-20"
    assert spans[0][1] + dt.timedelta(days=1) == spans[1][0]
    assert all((end - start).days < 90 for start, end in spans)
    for i, target in enumerate(FIELDS.values()):
        assert result[target].tolist() == [i * 1000000001] * 2
        assert result[target + "Weight"].tolist() == [i + .25] * 2
    assert all(k["verify"] is True and k["timeout"] <= 30 for _, k in calls)


def test_nika_explicit_null_amount_is_missing_and_zero_is_zero(monkeypatch):
    setup_site(monkeypatch, inception="1405-07-27")
    row = record();row.update(bond=None, bondPercent=None, otherStock="۰", otherStockPercent="۰")
    monkeypatch.setattr(Funds.requests, "get", lambda url, **kwargs: response([row], url=url))
    result = Funds.get_daily_asset_allocation("Fund A")
    assert pd.isna(result.Bonds.iloc[0]) and pd.isna(result.BondsWeight.iloc[0])
    assert result.OtherStocks.tolist() == [0]


@pytest.mark.parametrize("change", ["missing", "bad_numeric", "bad_date", "outside_window", "duplicate", "wrong_shape"])
def test_nika_rejects_malformed_or_conflicting_reports(monkeypatch, change):
    setup_site(monkeypatch, inception="1405-07-27")
    row = record();rows = [row]
    if change == "missing": del row["bondPercent"]
    if change == "bad_numeric": row["bond"] = "not-a-number"
    if change == "bad_date": row["onDate"] = "20-19-2026"
    if change == "outside_window": row["onDate"] = "2000-01-01"
    if change == "duplicate": rows.append({**row, "bond": 42})
    if change == "wrong_shape": rows = {"unknown": []}
    monkeypatch.setattr(Funds.requests, "get", lambda url, **kwargs: response(rows, url=url))
    with pytest.raises(ValueError, match="Nika|provider"):
        Funds.get_daily_asset_allocation("Fund A")


@pytest.mark.parametrize("error", [requests.exceptions.SSLError("certificate"), requests.ReadTimeout("timeout")])
def test_nika_preserves_transport_errors_without_other_endpoints(monkeypatch, error):
    setup_site(monkeypatch, inception="1405-07-27")
    calls = []
    def get(url, **kwargs):
        calls.append(url);raise error
    monkeypatch.setattr(Funds.requests, "get", get)
    with pytest.raises(type(error)):
        Funds.get_daily_asset_allocation("Fund A")
    assert len(calls) == 1


def test_nika_waf_response_is_explicit_access_rejection(monkeypatch):
    setup_site(monkeypatch, inception="1405-07-27")
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        return response(text='<html><head><title>WAF</title></head><body>The URL requested was rejected.</body></html>', url=url)
    monkeypatch.setattr(Funds.requests, "get", get)
    with pytest.raises(requests.RequestException, match="access.*rejected|WAF"):
        Funds.get_daily_asset_allocation("Fund A")
    assert len(calls) == 1


def test_json_containing_a_waf_title_is_not_an_access_rejection(monkeypatch):
    data = {"description": "<title>WAF</title>"}
    monkeypatch.setattr(Funds.requests, "get", lambda url, **kwargs: response(data, url=url))
    assert Funds._safe_get_json("https://fund.example/public") == data


def test_nika_empty_windows_do_not_truncate_older_history(monkeypatch):
    setup_site(monkeypatch)
    calls = []

    def get(url, **kwargs):
        calls.append(kwargs["params"])
        rows = [] if kwargs["params"]["toDate"] == "2026-10-20" else [record("2026-07-20")]
        return response(rows, url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    assert Funds.get_daily_asset_allocation("Fund A").JalaliDate.tolist() == ["1405-04-29"]
    assert len(calls) == 2


def test_nika_entirely_empty_history_is_a_public_error(monkeypatch):
    setup_site(monkeypatch, inception="1405-07-27")
    monkeypatch.setattr(Funds.requests, "get", lambda url, **kwargs: response([], url=url))
    with pytest.raises(ValueError, match="No Nika historical"):
        Funds.get_daily_asset_allocation("Fund A")


@pytest.mark.parametrize("status,message", [
    (400, "There is no fiscal year in date"),
    (404, "Symbol prices are not found"),
])
def test_nika_missing_provider_history_is_not_silently_skipped(monkeypatch, status, message):
    setup_site(monkeypatch, inception="1405-07-27")
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return response({"message": message}, status=status, url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    with pytest.raises(requests.HTTPError):
        Funds.get_daily_asset_allocation("Fund A")
    assert len(calls) == 1


def test_legacy_nika_nav_configuration_does_not_invent_an_oak_endpoint(monkeypatch):
    config = {key: value for key, value in CONFIG.items() if key != "oakPath"}
    assert "oakPath" not in Funds._extract_nika_config_from_html(json.dumps(config))
    setup_site(monkeypatch, config=config)
    monkeypatch.setattr(Funds.requests, "get", lambda *a, **k: pytest.fail("No published Oak endpoint"))
    with pytest.raises(NotImplementedError, match="Nika allocation configuration"):
        Funds.get_daily_asset_allocation("Fund A")


@pytest.mark.parametrize("inception", [None, "bad-date", "1406-01-01"])
def test_nika_does_not_invent_fiscal_year_bounds(monkeypatch, inception):
    setup_site(monkeypatch, inception=inception)
    monkeypatch.setattr(Funds.requests, "get", lambda *a, **k: pytest.fail("No valid inception bound"))
    with pytest.raises(ValueError, match="inception|Inception|Nika"):
        Funds.get_daily_asset_allocation("Fund A")
