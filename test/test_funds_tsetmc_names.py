import json

import pandas as pd
import pytest
import requests

import fima
import fima.Funds as Funds


GROUPS = {6, 7, 4, 11, 12, 14, 13, 5, 16, 17}


def mock_catalogs(monkeypatch, catalogs=None, failed_group=None):
    calls = []
    catalogs = catalogs if catalogs is not None else {
        7: [{"regNo": 11172.0, "mfName": "آرمان سپهر آتی", "fixIncome": 7}],
    }

    def get(url, **kwargs):
        calls.append(url)
        identifier = int(url.rsplit("/", 1)[1])
        response = requests.Response()
        response.url = url
        response.status_code = 500 if "GetFunds/" in url and identifier == failed_group else 200
        if "GetFundInDetail/" in url:
            data = {"fund": {"regNo": float(identifier), "mfName": "آرمان سپهر آتی",
                             "stats": [], "futureField": None}}
        else:
            data = {"funds": catalogs.get(identifier, [])}
        response._content = json.dumps(data).encode()
        response._content_consumed = True
        return response

    monkeypatch.setattr(Funds.requests, "get", get)
    monkeypatch.setattr(Funds.time, "sleep", lambda _: None)
    return calls


def test_type_discovery_is_offline_and_returns_an_independent_table(monkeypatch):
    calls = mock_catalogs(monkeypatch)
    table = Funds.get_tsetmc_fund_types()
    assert list(table.columns) == ["FundTypeID", "FundTypeName", "EnglishName"]
    assert set(table.FundTypeID) == GROUPS
    assert table.set_index("FundTypeName").loc["سهامی", "FundTypeID"] == 6
    assert table.set_index("FundTypeName").loc["مختلط", "EnglishName"] == "mixed"
    table.loc[0, "FundTypeName"] = "changed locally"
    assert "changed locally" not in Funds.get_tsetmc_fund_types().FundTypeName.tolist()
    assert fima.get_tsetmc_fund_types is Funds.get_tsetmc_fund_types
    assert calls == []


@pytest.mark.parametrize("label,code", [
    ("سهامی", 6), ("سهامي", 6), ("در سهام", 6), ("سهام", 6),
    (" equity ", 6), ("STOCK", 6), ("مختلط", 7), ("mixed", 7),
    ("درآمد\u200c ثابت", 4), ("Fixed Income", 4), ("fixed_income", 4),
    ("بازارگردانی", 11), ("جسورانه", 12), ("زمین و ساختمان", 14),
    ("پروژه‌ای", 13), ("کالایی", 5), ("بر پایه گواهی سپرده کالایی", 5),
    ("خصوصی", 16), ("صندوق", 17),
])
def test_named_type_uses_the_verified_selector(monkeypatch, label, code):
    calls = mock_catalogs(monkeypatch)
    assert isinstance(Funds.get_tsetmc_funds(label), pd.DataFrame)
    assert calls == [f"https://cdn.tsetmc.com/api/Fund/GetFunds/{code}"]


def test_unknown_type_explains_discovery_before_http(monkeypatch):
    calls = mock_catalogs(monkeypatch)
    with pytest.raises(ValueError, match="fund_type.*get_tsetmc_fund_types"):
        Funds.get_tsetmc_funds("stockish")
    assert calls == []


@pytest.mark.parametrize("name", ["آرمان سپهر آتی", "  آرمان\u200cسپهر   آتي  "])
def test_name_lookup_without_type_searches_all_individual_groups(monkeypatch, name):
    calls = mock_catalogs(monkeypatch)
    result = Funds.get_tsetmc_fund_details(name)
    assert result["regNo"] == 11172
    assert result["stats"] == [] and result["futureField"] is None
    assert {int(url.rsplit("/", 1)[1]) for url in calls[:-1]} == GROUPS
    assert len(calls) == len(GROUPS) + 1
    assert calls[-1].endswith("/GetFundInDetail/11172")
    assert not any(url.endswith("/GetFunds/0") for url in calls)


def test_keyword_name_and_type_limit_catalog_requests(monkeypatch):
    calls = mock_catalogs(monkeypatch)
    result = Funds.get_tsetmc_fund_details(fund_name="آرمان سپهر آتی", fund_type="مختلط")
    assert result["regNo"] == 11172
    assert [url.rsplit("/", 2)[1:] for url in calls] == [
        ["GetFunds", "7"], ["GetFundInDetail", "11172"],
    ]


def test_name_collision_requires_explicit_disambiguation(monkeypatch):
    catalogs = {
        6: [{"regNo": 12250.0, "mfName": "نام تکراری"}],
        7: [{"regNo": 11172.0, "mfName": "نام\u200cتکراري"}],
    }
    calls = mock_catalogs(monkeypatch, catalogs)
    with pytest.raises(ValueError, match="Multiple.*fund_type.*reg_no"):
        Funds.get_tsetmc_fund_details("نام تکراری")
    assert not any("GetFundInDetail" in url for url in calls)
    assert Funds.get_tsetmc_fund_details("نام تکراری", fund_type="مختلط")["regNo"] == 11172


def test_repeated_match_for_same_registration_is_one_fund(monkeypatch):
    row = {"regNo": 11172.0, "mfName": "آرمان سپهر آتی"}
    mock_catalogs(monkeypatch, {6: [row], 7: [row, dict(row)]})
    assert Funds.get_tsetmc_fund_details("آرمان سپهر آتی")["regNo"] == 11172


def test_partial_or_missing_name_is_not_guessed(monkeypatch):
    calls = mock_catalogs(monkeypatch)
    with pytest.raises(ValueError, match="No TSETMC fund.*get_tsetmc_funds"):
        Funds.get_tsetmc_fund_details("آرمان", fund_type="مختلط")
    assert len(calls) == 1


def test_failed_group_prevents_assuming_a_unique_match(monkeypatch):
    calls = mock_catalogs(monkeypatch, failed_group=4)
    with pytest.raises(requests.HTTPError):
        Funds.get_tsetmc_fund_details("آرمان سپهر آتی")
    assert any(url.endswith("/GetFunds/7") for url in calls)
    assert sum(url.endswith("/GetFunds/4") for url in calls) == 2
    assert not any("GetFundInDetail" in url for url in calls)


@pytest.mark.parametrize("kwargs", [
    {}, {"fund_name": "آرمان سپهر آتی", "reg_no": 11172},
    {"reg_no": 11172, "fund_type": "مختلط"},
    {"fund_name": 11172, "fund_type": "مختلط"},
    {"fund_name": "آرمان سپهر آتی", "fund_type": "wrong"},
])
def test_missing_or_conflicting_selectors_fail_before_http(monkeypatch, kwargs):
    calls = mock_catalogs(monkeypatch)
    with pytest.raises(ValueError):
        Funds.get_tsetmc_fund_details(**kwargs)
    assert calls == []


def test_previous_reg_no_keyword_bypasses_name_lookup(monkeypatch):
    calls = mock_catalogs(monkeypatch)
    assert Funds.get_tsetmc_fund_details(reg_no="11172")["regNo"] == 11172
    assert calls == ["https://cdn.tsetmc.com/api/Fund/GetFundInDetail/11172"]


@pytest.mark.integration
@pytest.mark.parametrize("label,code", [("سهامی", 6), ("مختلط", 7)])
def test_live_named_fund_type(label, code):
    result = Funds.get_tsetmc_funds(label)
    assert not result.empty and (result.fixIncome == code).all()


@pytest.mark.integration
@pytest.mark.parametrize("fund_type", ["مختلط", None])
def test_live_fund_by_name(fund_type):
    result = Funds.get_tsetmc_fund_details("آرمان سپهر آتی", fund_type=fund_type)
    assert result["regNo"] == 11172
    assert result["mfName"] == "آرمان سپهر آتی"
