"""Contract metadata regressions from verified TSE/IFB and historical APIs."""
from types import SimpleNamespace

import jdatetime as jd
import pandas as pd
import pytest
import requests

import fima.Options as options


@pytest.fixture
def metadata(monkeypatch):
    source = {"name": "اختيارخ BASE-100000-14050817", "calls": []}
    monkeypatch.setattr(options, "_find_instrument_code",
                        lambda search_key, **kwargs: "000UA" if search_key == "BASE" else "000OPT")
    def get(url, **kwargs):
        assert kwargs["timeout"] == 30
        source["calls"].append(url)
        if "GetInstrumentInfo" in url:
            payload = {"instrumentInfo": {"lVal30": source["name"]}}
        else:
            payload = {"closingPriceInfo": {"pDrCotVal": 177900 if url.endswith("000UA") else 84427}}
        return SimpleNamespace(json=lambda: payload, raise_for_status=lambda: None)
    monkeypatch.setattr(options.requests, "get", get)
    return source


@pytest.mark.parametrize("expiry", ["14050817", "1405/08/17"])
@pytest.mark.parametrize("kind,expected", [("خ", "Call"), ("ف", "Put")])
def test_option_metadata_parses_official_expiry_formats(metadata, expiry, kind, expected):
    metadata["name"] = f"اختيار{kind} BASE-100000-{expiry}"
    row = options.ticker_info("TEST").iloc[0]
    assert row.UnderlyingTicker == "BASE"
    assert row.StrikePrice == 100000
    assert row.MaturityJalaliDate == "1405-08-17"
    assert row.DaysToMaturity == (jd.date(1405, 8, 17) - jd.date.today()).days
    assert row.OptionType == expected
    assert row.LastPrice == 84427
    assert row.UnderlyingLastPrice == 177900
    assert metadata["calls"][-1].endswith("000UA")


@pytest.mark.parametrize("j_date", [True, False])
@pytest.mark.parametrize("positional", [True, False])
def test_legacy_date_selector_on_current_metadata_contract(metadata, j_date, positional):
    result = (options.ticker_info("TEST", j_date) if positional
              else options.ticker_info("TEST", j_date=j_date))
    date = "MaturityJalaliDate" if j_date else "MaturityGregorianDate"
    assert list(result) == ["UnderlyingTicker", "StrikePrice", date, "DaysToMaturity",
                            "OptionType", "LastPrice", "UnderlyingLastPrice"]
    if j_date:
        assert result.iloc[0][date] == "1405-08-17"
    else:
        assert str(result[date].dtype) == "datetime64[ns]"
        assert result.iloc[0][date] == pd.Timestamp("2026-11-08")


@pytest.mark.parametrize("name", ["ordinary equity", "اختيارx BASE-100000-1405/08/17",
                                 "اختيارخ BASE-bad-14050817", "اختيارخ BASE-100000-14051301"])
def test_invalid_option_metadata_is_not_reinterpreted(metadata, name):
    metadata["name"] = name
    with pytest.raises(ValueError, match="Invalid TSETMC option instrument name"):
        options.ticker_info("TEST")


@pytest.mark.parametrize("failed_request", [0, 1, 2])
def test_metadata_checks_status_before_reading_json(metadata, monkeypatch, failed_request):
    metadata["name"] = "اختيارخ BASE-100000-1405/08/17"
    original = options.requests.get
    calls = []
    def get(*args, **kwargs):
        response = original(*args, **kwargs)
        position = len(calls)
        calls.append(args)
        if position == failed_request:
            def failed_status():
                raise requests.HTTPError("503 metadata unavailable")
            return SimpleNamespace(raise_for_status=failed_status)
        return response
    monkeypatch.setattr(options.requests, "get", get)
    with pytest.raises(requests.HTTPError, match="503"):
        options.ticker_info("TEST")
