"""Stable public Rayan identifiers must not substitute another unit class."""
import copy
import pandas as pd
import pytest
import requests
import fima.Funds as Funds
from .test_funds_http import response
from .test_funds_coverage import public_fund
from .test_funds_rayan import allocation


def setup_site(monkeypatch, items, *, instrument="123456789", registration="10782", info=None, siblings=(), allocation_row=None):
    public_fund(monkeypatch, "شرکت رایان هم افزا")
    row = {"FundName": "Fund A", "FundTypeName": "در سهام", "FundTypeID": "6",
           "WebsiteAddress": "fund.example", "RegistrationNumber": registration,
           "InstrumentCode": instrument, "GroupId": "0", "Ticker": None}
    frame = pd.DataFrame([row, *siblings])
    monkeypatch.setattr(Funds, "get_all_funds", lambda **k: frame.copy())
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        if url.endswith("/fundItems"):
            return response(items, url=url)
        if url.endswith("/siteInfo"):
            if isinstance(info, Exception):
                raise info
            return response(info, url=url)
        if "/dailyAssetStructure/" in url:
            return response([copy.deepcopy(allocation_row)], url=url)
        if "/nav/" in url:
            selected = int(url.rsplit("/", 1)[-1])
            return response([{"jalaliDate": "1405/07/19", "purchaseNAVPerShare": selected,
                              "sellNAVPerShare": selected, "statisticalNAVPerShare": selected,
                              "units": 10, "nav": selected * 10}], url=url)
        pytest.fail("Unexpected request: " + url)
    monkeypatch.setattr(Funds.requests, "get", get)
    return calls


@pytest.mark.parametrize("assets", [False, True])
def test_renamed_rayan_fund_uses_exact_official_instrument_not_first_class(monkeypatch, allocation, assets):
    items = [{"fundId": 1, "fundName": "Ordinary class", "tsetmcUrl": None},
             {"fundId": 8, "fundName": "Renamed preferred class", "tsetmcUrl": "https://tsetmc.ir/InstInfo/123456789"}]
    calls = setup_site(monkeypatch, items, allocation_row={**allocation, "fundId": 8})
    result = (Funds.get_daily_asset_allocation if assets else Funds.get_daily_navs)("Fund A")
    assert result.JalaliDate.tolist() == ["1405-07-19"]
    assert any(url.endswith("/dailyAssetStructure/8" if assets else "/nav/8") for url in calls)
    if not assets:
        assert result.SubscriptionNAV.tolist() == [8]


@pytest.mark.parametrize("assets", [False, True])
def test_single_renamed_rayan_fund_requires_published_registration_and_default(monkeypatch, allocation, assets):
    info = {"dsCode": "10782", "submitCode": "99999", "defaultFundId": 8,
            "fundName": "Renamed fund", "tsetmcUrl": None}
    calls = setup_site(monkeypatch, [{"fundId": 8, "fundName": "Renamed fund", "tsetmcUrl": None}],
                       instrument=None, info=info, allocation_row={**allocation, "fundId": 8})
    result = (Funds.get_daily_asset_allocation if assets else Funds.get_daily_navs)("Fund A")
    assert result.JalaliDate.tolist() == ["1405-07-19"]
    assert calls.count("https://fund.example/api/v1/public/siteInfo") == 1
    assert any(url.endswith("/dailyAssetStructure/8" if assets else "/nav/8") for url in calls)


@pytest.mark.parametrize("info", [
    {"dsCode": "99999", "submitCode": "10782", "defaultFundId": 8},
    {"dsCode": "10782", "defaultFundId": 1},
    {"dsCode": "10782"},
    None,
])
def test_unrelated_registration_or_default_is_not_a_renamed_fund(monkeypatch, info):
    calls = setup_site(monkeypatch, [{"fundId": 8, "fundName": "Other"}], instrument=None, info=info)
    with pytest.raises(NotImplementedError, match="identity"):
        Funds.get_daily_navs("Fund A")
    assert not any("/nav/" in url for url in calls)


@pytest.mark.parametrize("url", ["https://unrelated.example/InstInfo/123456789",
                                  "https://tsetmc.ir/InstInfo/999999999",
                                  "https://tsetmc.ir/InstInfo/123456789/extra"])
def test_instrument_matching_requires_exact_official_identifier_url(monkeypatch, url):
    calls = setup_site(monkeypatch, [{"fundId": 8, "fundName": "Other", "tsetmcUrl": url}])
    with pytest.raises(NotImplementedError, match="identity"):
        Funds.get_daily_navs("Fund A")
    assert not any("/nav/" in x for x in calls)


def test_shared_catalog_instrument_does_not_identify_a_parent_as_its_child(monkeypatch):
    sibling = {"FundName": "Child", "FundTypeName": "در سهام", "FundTypeID": "6",
               "WebsiteAddress": "fund.example", "RegistrationNumber": "10782",
               "GroupId": "1", "InstrumentCode": "123456789", "Ticker": None}
    calls = setup_site(monkeypatch, [{"fundId": 8, "fundName": "Child", "tsetmcUrl": "https://tsetmc.ir/InstInfo/123456789"}], siblings=[sibling])
    with pytest.raises(NotImplementedError, match="identity"):
        Funds.get_daily_navs("Fund A")
    assert not any("/nav/" in x for x in calls)


def test_ambiguous_provider_instrument_ids_are_not_arbitrarily_selected(monkeypatch):
    items = [{"fundId": v, "fundName": "Other", "tsetmcUrl": "https://tsetmc.ir/InstInfo/123456789"} for v in [2, 8]]
    calls = setup_site(monkeypatch, items)
    with pytest.raises(NotImplementedError, match="identity"):
        Funds.get_daily_navs("Fund A")
    assert not any("/nav/" in x for x in calls)


def test_shared_instrument_does_not_discard_a_distinct_exact_provider_name(monkeypatch):
    sibling = {"FundName": "Child", "FundTypeName": "در سهام", "FundTypeID": "6",
               "WebsiteAddress": "fund.example", "RegistrationNumber": "10782",
               "GroupId": "1", "InstrumentCode": "123456789", "Ticker": None}
    items = [{"fundId": 8, "fundName": "Fund A", "tsetmcUrl": "https://tsetmc.ir/InstInfo/123456789"},
             {"fundId": 2, "fundName": "Child", "tsetmcUrl": "https://tsetmc.ir/InstInfo/123456789"}]
    setup_site(monkeypatch, items, siblings=[sibling])
    assert Funds.get_daily_navs("Fund A").SubscriptionNAV.tolist() == [8]


def test_registration_discovery_preserves_tls_failure(monkeypatch):
    calls = setup_site(monkeypatch, [{"fundId": 8, "fundName": "Other"}], instrument=None,
                       info=requests.exceptions.SSLError("certificate mismatch"))
    with pytest.raises(requests.exceptions.SSLError):
        Funds.get_daily_navs("Fund A")
    assert not any("/nav/" in x for x in calls)


def test_instrument_precedes_another_unit_class_with_a_matching_name(monkeypatch):
    items = [{"fundId": 1, "fundName": "Fund A", "tsetmcUrl": None},
             {"fundId": 8, "fundName": "Preferred", "tsetmcUrl": "https://tsetmc.ir/InstInfo/123456789"}]
    setup_site(monkeypatch, items)
    assert Funds.get_daily_navs("Fund A").SubscriptionNAV.tolist() == [8]


def test_name_does_not_hide_a_conflicting_published_instrument(monkeypatch):
    calls = setup_site(monkeypatch, [{"fundId": 1, "fundName": "Fund A", "tsetmcUrl": "https://tsetmc.ir/InstInfo/999"}])
    with pytest.raises(NotImplementedError, match="instruments disagree"):
        Funds.get_daily_navs("Fund A")
    assert not any("/nav/" in x for x in calls)


@pytest.mark.parametrize("value", [0, -1, "bad"])
def test_stable_instrument_still_requires_a_positive_provider_id(monkeypatch, value):
    setup_site(monkeypatch, [{"fundId": value, "fundName": "Renamed", "tsetmcUrl": "https://tsetmc.ir/InstInfo/123456789"}])
    with pytest.raises(ValueError, match="Rayan.*identity"):
        Funds.get_daily_navs("Fund A")


def test_malformed_provider_instrument_reference_is_explicit(monkeypatch):
    setup_site(monkeypatch, [{"fundId": 8, "fundName": "Renamed", "tsetmcUrl": 123}])
    with pytest.raises(ValueError, match="Rayan.*reference"):
        Funds.get_daily_navs("Fund A")
