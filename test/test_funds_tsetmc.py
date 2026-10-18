"""TSETMC response contracts captured on 2026-10-14; no live calls by default."""

import copy
import json
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest
import requests

import fima
import fima.Funds as Funds


BASE_URL = "https://cdn.tsetmc.com/api/Fund"


@pytest.fixture
def fund():
    # Reduced real detail response: keep the source dates and nested shapes.
    return {
        "regNo": 11172.0, "fundType": 0, "fixIncome": 7,
        "mfName": "آرمان سپهر آتی", "name": None, "webSite": "",
        "recordDate": "2026-09-05T00:00:00", "navSub": 62105.0,
        "navRed": 61734.0, "navStat": 61734.0, "portfolioDeposit": 12.88,
        "fundProfits": [],
        "stats": [
            {"recordDate": "2013-10-31T00:00:00", "navSub": 11002.0,
             "netAsset": 276407000000.0, "navStat": 10933.0, "navRed": 10933.0},
            {"recordDate": "2013-10-30T00:00:00", "navSub": 11000.0,
             "netAsset": 276334000000.0, "navStat": 10930.0, "navRed": 10930.0},
            {"recordDate": "2026-09-05T00:00:00", "navSub": 62105.0,
             "netAsset": 3398029096688.0, "navStat": 61734.0, "navRed": 61734.0},
        ],
    }


def mock_get(monkeypatch, data=None, *, status=200, text=None):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        response = requests.Response()
        response.url = url
        response.status_code = status
        response._content = (json.dumps(data) if text is None else text).encode()
        response._content_consumed = True
        return response

    monkeypatch.setattr(Funds.requests, "get", get)
    return calls


@pytest.mark.parametrize("fund_type", [6, "6", np.int64(6), 6.0])
def test_list_normalizes_columns_and_preserves_order_and_nested_values(monkeypatch, fund, fund_type):
    row = dict(fund, recordDate="2026-10-12T00:00:00", stats=None,
               futureField={"source": "unchanged"})
    rows = [row, dict(row, regNo=12250.0, mfName="صندوق دوم")]
    calls = mock_get(monkeypatch, {"funds": rows})

    result = Funds.get_tsetmc_funds(fund_type)

    assert list(result.columns) == ["RegistrationNumber", "ProviderFundTypeCode", "FundTypeID", "FundName",
        "ProviderName", "WebSite", "UpdateGregorianDate", "SubscriptionNAV", "RedemptionNAV", "StatisticalNAV",
        "DepositWeight", "FundProfits", "Stats", "FutureField"]
    assert result.RegistrationNumber.tolist() == ["11172", "12250"]
    assert result.FundName.tolist() == [row["mfName"] for row in rows]
    assert result.loc[0, "ProviderFundTypeCode"] == "0"
    assert result.loc[0, "FundTypeID"] == "7"  # Do not derive this from the URL.
    assert result.SubscriptionNAV.tolist() == [62105, 62105]
    assert result.RedemptionNAV.tolist() == [61734, 61734]
    assert result.StatisticalNAV.tolist() == [61734, 61734]
    assert result.UpdateGregorianDate.tolist() == [pd.Timestamp("2026-10-12")] * 2
    assert result.loc[0, "FutureField"] == {"source": "unchanged"}
    assert result.loc[0, "Stats"] is None
    assert result.loc[0, "FundProfits"] == []
    assert calls == [(BASE_URL + "/GetFunds/6", {
        "timeout": 30, "verify": True, "allow_redirects": True,
    })]


@pytest.mark.parametrize("reg_no", [11172, "11172", 11172.0, np.float64(11172), np.int64(11172)])
def test_detail_preserves_full_object_and_unsorted_history(monkeypatch, fund, reg_no):
    fund["futureField"] = {"records": [1, None]}
    original = copy.deepcopy(fund)
    calls = mock_get(monkeypatch, {"fund": fund})

    assert Funds.get_tsetmc_fund_details(reg_no) == original
    assert fund == original
    assert calls[0][0] == BASE_URL + "/GetFundInDetail/11172"
    assert calls[0][1]["verify"] is True


def test_empty_group_is_valid_and_zero_is_an_explicit_selector(monkeypatch):
    calls = mock_get(monkeypatch, {"funds": []})
    assert Funds.get_tsetmc_funds(0).empty
    assert calls[0][0].endswith("/GetFunds/0")


@pytest.mark.parametrize("function,parameter,invalid", [
    ("get_tsetmc_funds", "fund_type", -1),
    ("get_tsetmc_fund_details", "reg_no", 0),
] + [(name, parameter, value)
     for name, parameter in [("get_tsetmc_funds", "fund_type"),
                             ("get_tsetmc_fund_details", "reg_no")]
     for value in [True, False, None, 6.5, Fraction(2**54 + 1, 2**54),
                   np.nan, np.inf, "../6", "6/7", "6.0", "", "۶"]])
def test_invalid_identifier_fails_before_http(monkeypatch, function, parameter, invalid):
    calls = mock_get(monkeypatch, {})
    with pytest.raises(ValueError, match=parameter):
        getattr(Funds, function)(invalid)
    assert calls == []


@pytest.mark.parametrize("data", [
    None, [], {}, {"funds": None}, {"funds": {}}, {"funds": [None]},
    {"funds": [{}]}, {"funds": [{"regNo": 0}]},
    {"funds": [{"regNo": "bad", "mfName": None}]},
    {"funds": [{"regNo": np.nan, "mfName": "A"}]},
])
def test_malformed_list_is_not_an_empty_group(monkeypatch, data):
    mock_get(monkeypatch, data)
    with pytest.raises(ValueError, match="TSETMC.*GetFunds/6"):
        Funds.get_tsetmc_funds(6)


@pytest.mark.parametrize("data", [
    None, [], {}, {"fund": None}, {"fund": []}, {"fund": {}},
    {"fund": {"regNo": 0}}, {"fund": {"regNo": "bad", "mfName": None}},
    {"fund": {"regNo": 12250.0, "mfName": "Different fund"}},
])
def test_missing_malformed_or_wrong_detail_identity_is_an_error(monkeypatch, data):
    mock_get(monkeypatch, data)
    with pytest.raises(ValueError, match="TSETMC.*GetFundInDetail/11172"):
        Funds.get_tsetmc_fund_details(11172)


@pytest.mark.parametrize("function,arg", [("get_tsetmc_funds", 6), ("get_tsetmc_fund_details", 11172)])
def test_public_errors_keep_provider_context(monkeypatch, function, arg):
    calls = mock_get(monkeypatch, status=500, text="")
    monkeypatch.setattr(Funds.time, "sleep", lambda _: None)
    with pytest.raises(requests.HTTPError) as error:
        getattr(Funds, function)(arg)
    assert error.value.response.url.startswith(BASE_URL)
    assert len(calls) == 2

    mock_get(monkeypatch, text="<html>provider error</html>")
    with pytest.raises(ValueError, match="invalid JSON.*cdn.tsetmc.com"):
        getattr(Funds, function)(arg)

    def unavailable(*args, **kwargs):
        raise requests.Timeout("provider unavailable")

    monkeypatch.setattr(Funds.requests, "get", unavailable)
    with pytest.raises(requests.Timeout, match="cdn.tsetmc.com"):
        getattr(Funds, function)(arg)


def test_both_entry_points_export_new_functions():
    for name in ["get_tsetmc_funds", "get_tsetmc_fund_details"]:
        assert getattr(fima, name) is getattr(Funds, name)


def test_optional_detail_fields_can_be_absent_or_null(monkeypatch):
    record = {"regNo": 11172.0, "mfName": None, "stats": None}
    mock_get(monkeypatch, {"fund": record})
    assert Funds.get_tsetmc_fund_details(11172) == record


@pytest.mark.integration
@pytest.mark.parametrize("fund_type", [6, 7])
def test_live_tsetmc_fund_group(fund_type):
    result = Funds.get_tsetmc_funds(fund_type)
    assert not result.empty
    assert {"RegistrationNumber", "FundName", "FundTypeID", "UpdateGregorianDate", "StatisticalNAV"}.issubset(result.columns)
    assert (result.FundTypeID == str(fund_type)).all()


@pytest.mark.integration
def test_live_tsetmc_fund_detail():
    result = Funds.get_tsetmc_fund_details(11172)
    assert result["regNo"] == 11172
    assert result["mfName"]
    assert isinstance(result["stats"], list) and result["stats"]
    assert {"recordDate", "navSub", "navRed", "navStat", "netAsset"}.issubset(result["stats"][0])
