"""Official replacements are conditional on the fund's legal registration."""
import pandas as pd
import pytest
import requests

import fima.Funds as Funds
from .test_funds_coverage import public_fund
from .test_funds_http import response
from .test_funds_rayan import allocation


MIGRATIONS = [
    ("petroagahfund.ir", "12093", "agahsectorfund.ir", "بخشی صنایع آگاه", "پتروآگاه", "پترو آگاه"),
    ("vistakhodro.ir", "12168", "vistasectorfund.ir", "بخشی صنایع ویستا", "بهین رو", "قابل معامله بخشی صنایع ویستا"),
    ("etebarsaham.com", "11706", "www.etebarsahamfund.com", "اعتبار سهام ایرانیان", "اعتبارسهام", "صندوق سرمایه گذاری اعتبار سهام ایرانیان"),
]


def setup_site(monkeypatch, migration, allocation, *, registration=None, info=None, error=None,
               nav_data=None, nav_error=None):
    old, expected, current, name, ticker, display = migration
    kind, type_id = ("در سهام", "6") if expected == "11706" else ("در سهام-بخشی", "21")
    public_fund(monkeypatch, "شرکت رایان هم افزا", name=name, kind=kind)
    instrument = {"12093": "37828981835497620", "12168": "42799209630949274",
                  "11706": "55761294311886451"}[expected]
    catalog = pd.DataFrame([{"FundName": name, "FundTypeName": kind, "FundTypeID": type_id,
                             "WebsiteAddress": old, "RegistrationNumber": registration or expected,
                             "GroupId": "0", "Ticker": ticker, "InstrumentCode": instrument}])
    monkeypatch.setattr(Funds, "get_all_funds", lambda **kwargs: catalog.copy())
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        assert kwargs["verify"] is True and kwargs["timeout"] <= 30
        if url.startswith("https://" + old):
            raise requests.exceptions.SSLError("old hostname certificate mismatch")
        assert url.startswith("https://" + current)
        if url.endswith("/siteInfo"):
            if error is not None:
                raise error
            return response({"dsCode": expected} if info is None else info, url=url)
        if url.endswith("/fundItems"):
            return response([{"fundId": 1, "fundName": display,
                              "tsetmcUrl": f"https://tsetmc.ir/InstInfo/{instrument}"}], url=url)
        if url.endswith("/dailyAssetStructure/1"):
            return response([allocation], url=url)
        assert url.endswith("/nav/1")
        if nav_error is not None:
            raise nav_error
        return response([{"jalaliDate": "1405/07/19", "purchaseNAVPerShare": 3,
                          "sellNAVPerShare": 2, "statisticalNAVPerShare": 2,
                          "units": 10, "nav": 20}] if nav_data is None else nav_data, url=url)
    monkeypatch.setattr(Funds.requests, "get", get)
    return catalog, calls


@pytest.mark.parametrize("migration", MIGRATIONS)
@pytest.mark.parametrize("assets", [False, True])
def test_public_history_uses_verified_replacement_without_changing_catalog(monkeypatch, allocation, migration, assets):
    original, calls = setup_site(monkeypatch, migration, allocation)
    result = (Funds.get_daily_asset_allocation if assets else Funds.get_daily_navs)(migration[3])
    assert result.JalaliDate.tolist() == ["1405-07-19"]
    assert all(url.startswith("https://" + migration[2]) for url, _ in calls)
    assert sum(url.endswith("/siteInfo") for url, _ in calls) == 1
    pd.testing.assert_frame_equal(Funds.get_all_funds(), original)


@pytest.mark.parametrize("migration", MIGRATIONS)
def test_another_catalog_registration_cannot_inherit_a_domain_override(monkeypatch, allocation, migration):
    _, calls = setup_site(monkeypatch, migration, allocation, registration="99999")
    with pytest.raises(requests.exceptions.SSLError, match="old hostname"):
        Funds.get_daily_navs(migration[3])
    assert all(url.startswith("https://" + migration[0]) for url, _ in calls)


@pytest.mark.parametrize("info", [{}, {"dsCode": "99999"}, []])
def test_replacement_must_still_publish_the_expected_registration(monkeypatch, allocation, info):
    _, calls = setup_site(monkeypatch, MIGRATIONS[0], allocation, info=info)
    with pytest.raises(ValueError, match="migration.*identity|identity.*migration"):
        Funds.get_daily_navs(MIGRATIONS[0][3])
    assert len(calls) == 1 and calls[0][0].endswith("/siteInfo")


def test_replacement_tls_error_is_not_downgraded_or_hidden(monkeypatch, allocation):
    _, calls = setup_site(monkeypatch, MIGRATIONS[0], allocation,
                          error=requests.exceptions.SSLError("target certificate mismatch"))
    with pytest.raises(requests.exceptions.SSLError, match="target certificate"):
        Funds.get_daily_navs(MIGRATIONS[0][3])
    assert len(calls) == 1 and calls[0][0].startswith("https://agahsectorfund.ir")


@pytest.mark.parametrize("assets", [False, True])
def test_verified_native_migration_avoids_unrelated_legacy_discovery(monkeypatch, allocation, assets):
    setup_site(monkeypatch, MIGRATIONS[2], allocation)

    def legacy_probe(**kwargs):
        raise requests.ConnectionError("unrelated legacy hostname closed the connection")

    monkeypatch.setattr(Funds, "_detect_website_developer", legacy_probe)
    result = (Funds.get_daily_asset_allocation if assets else Funds.get_daily_navs)(MIGRATIONS[2][3])
    assert result.JalaliDate.tolist() == ["1405-07-19"]


def test_registration_alone_cannot_accept_a_non_rayan_migration_response(monkeypatch, allocation):
    setup_site(monkeypatch, MIGRATIONS[2], allocation, nav_data={"unrelated": []})
    with pytest.raises(ValueError, match="migration.*NAV"):
        Funds.get_daily_navs(MIGRATIONS[2][3])


def test_migration_preserves_native_nav_transport_errors(monkeypatch, allocation):
    setup_site(monkeypatch, MIGRATIONS[2], allocation,
               nav_error=requests.ReadTimeout("canonical NAV unavailable"))
    with pytest.raises(requests.ReadTimeout, match="canonical NAV unavailable"):
        Funds.get_daily_asset_allocation(MIGRATIONS[2][3])
