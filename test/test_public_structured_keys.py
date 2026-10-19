"""Ordinary public keys are semantic; opaque source evidence is explicit."""
import copy
import re

import pandas as pd
import pytest

import fima.Funds as funds
import fima.Options as options
from .test_funds_tsetmc import mock_get
from .test_tgju import provider, USD
import fima.TGJU as tgju


def assert_public_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            assert re.fullmatch(r"[A-Z][A-Za-z0-9]*", key), key
            if key not in {"ProviderMetadata", "ProviderInstrument", "ProviderAssets"}:
                assert_public_keys(child)
    elif isinstance(value, list):
        for child in value:
            assert_public_keys(child)


@pytest.mark.parametrize("snapshot", [False, True])
def test_fund_semantic_keys_and_nested_history_without_source_mutation(monkeypatch, snapshot):
    record = dict(regNo=11172.0, mfName="Fund", name=None, fixIncome=7, fundType=0,
                  navSub=101, navRed=99, navStat=100, netAsset=10000,
                  recordDate="2026-10-01T00:00:00", portfolioFiveBest=25,
                  stats=[dict(recordDate="2026-10-02T00:00:00", navSub=102,
                              navRed=100, navStat=101, netAsset=10100,
                              unverifiedBasis={"sourceLabel": "opaque"})],
                  fundProfits=[{"navSub": 12, "recordDate": "opaque-date"}],
                  futureField={"mfName": "not a fund name in this context"})
    original = copy.deepcopy(record)
    mock_get(monkeypatch, {"funds": [record]} if snapshot else {"fund": record})
    result = (funds.get_tsetmc_funds(7).iloc[0].to_dict() if snapshot
              else funds.get_tsetmc_fund_details(11172))
    assert result["FundName"] == "Fund" and result["ProviderName"] is None
    assert str(result["RegistrationNumber"]).removesuffix(".0") == "11172"
    assert str(result["FundTypeID"]) == "7" and str(result["ProviderFundTypeCode"]) == "0"
    assert [result[k] for k in ("SubscriptionNAV", "RedemptionNAV", "StatisticalNAV", "TotalNAV")] == [101, 99, 100, 10000]
    assert result["TopFiveStocksWeight"] == 25
    history = result["Stats"][0]
    assert history["UpdateGregorianDate"] == original["stats"][0]["recordDate"]
    assert history["SubscriptionNAV"] == 102 and history["TotalNAV"] == 10100
    assert history["ProviderMetadata"] == {"unverifiedBasis": {"sourceLabel": "opaque"}}
    assert result["ProviderMetadata"] == {
        "fundProfits": original["fundProfits"], "futureField": original["futureField"]}
    assert_public_keys(result)
    assert record == original
    history["ProviderMetadata"]["unverifiedBasis"]["sourceLabel"] = "changed"
    assert record == original


def test_detail_keeps_history_order_values_and_missing_fields(monkeypatch):
    record = dict(regNo=11172, mfName=None, stats=[
        dict(recordDate="2026-10-02", navStat=None),
        dict(recordDate="2026-10-01", navStat=0)])
    mock_get(monkeypatch, {"fund": record})
    result = funds.get_tsetmc_fund_details(11172)
    assert result["FundName"] is None
    assert [r["UpdateGregorianDate"] for r in result["Stats"]] == ["2026-10-02", "2026-10-01"]
    assert [r["StatisticalNAV"] for r in result["Stats"]] == [None, 0]
    assert "SubscriptionNAV" not in result and "ProviderMetadata" not in result


@pytest.mark.parametrize("history", [{}, [None], "not a NAV history"])
def test_malformed_nav_records_do_not_leak_raw_objects(monkeypatch, history):
    mock_get(monkeypatch, {"fund": dict(regNo=11172, mfName="Fund", stats=history)})
    with pytest.raises(ValueError, match="TSETMC.*stats"):
        funds.get_tsetmc_fund_details(11172)


@pytest.mark.parametrize("function", [tgju.get_tgju_instruments, tgju.get_tgju_market])
def test_pagination_attrs_have_public_names(provider, function):
    result = function("currency", page=2)
    assert result.attrs["Page"] == 2 and result.attrs["HasMore"] is False
    assert_public_keys(result.attrs)


def test_tgju_detail_normal_keys_and_explicit_source_metadata(provider):
    result = tgju.get_tgju_instrument_details("USD", "currency")
    assert result["InstrumentName"] == USD["title"]
    assert result["ProviderInstrument"] == USD
    assert result["ProviderMetadata"]
    assert "title" not in result and "s3" not in result and "Name" not in result
    assert_public_keys(result)


def test_options_series_labels_are_canonical():
    # The short-history branch is deterministic and returns the same Greek labels.
    result = options.get_greeks("TEST", _ticker_info_df=pd.DataFrame({"UnderlyingTicker": ["TEST"]}),
                                _ua_historical_data=pd.DataFrame(), r_f=.05)
    assert result.index.tolist() == ["Delta", "Gamma", "Theta", "Vega", "Rho"]
