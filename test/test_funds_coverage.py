import copy

import jdatetime as jd
import pandas as pd
import pytest
import requests

import fima.Funds as Funds
from .test_funds_http import response


def public_fund(monkeypatch, provider, *, name="Fund A", kind="در سهام", group=0):
    calls = []
    row = {"FundName": name, "FundTypeName": kind, "WebsiteAddress": "fund.example",
           "GroupId": group, "Ticker": "AAA"}

    def catalog(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame([row])

    monkeypatch.setattr(Funds, "get_all_funds", catalog)
    monkeypatch.setattr(Funds, "_detect_website_developer", lambda website: provider)
    # Keep transport mocks shared by module-level and scoped-session requests.
    monkeypatch.setattr(Funds.requests.Session, "get", lambda self, url, **kwargs: Funds.requests.get(url, **kwargs))
    return calls


def chart(value, name="صدور"):
    return {"name": name, "List": [{"x": "10/11/2026", "y": value}]}


def normal_chart(value):
    return [chart(value), chart(value + 1, "آماری"), chart(value + 2, "ابطال")]


def test_public_rayan_marketmaker_uses_aggregate_nav(monkeypatch):
    catalog_calls = public_fund(monkeypatch, "شرکت رایان هم افزا", kind="اختصاصی بازارگردانی")
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if "navMulti" in url:
            return response([{"jalaliDate": "1405/07/19", "purchaseNAVPerShare": 11,
                              "sellNAVPerShare": 10, "statisticNav": 9,
                              "fundCapital": 5, "totalAssetsValue": 50}], url=url)
        pytest.fail("Aggregate fund request must not read an underlying basket")

    monkeypatch.setattr(Funds.requests, "get", get)
    assert Funds.get_daily_navs("Fund A").to_dict("records") == [{
        "JalaliDate": "1405-07-19", "SubscriptionNAV": 11, "RedemptionNAV": 10,
        "StatisticalNAV": 9, "TotalNAV": 50}]
    assert len(catalog_calls) == 1
    assert calls == ["https://fund.example/api/v1/public/navMulti?size=-1"]


def test_rayan_marketmaker_allocation_does_not_return_a_basket(monkeypatch):
    public_fund(monkeypatch, "شرکت رایان هم افزا", kind="اختصاصی بازارگردانی")
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return response([{"fundId": 1, "fundName": "Unrelated basket"}], url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    with pytest.raises(NotImplementedError, match="fund.*Fund A"):
        Funds.get_daily_asset_allocation("Fund A")
    assert len(calls) == 1 and calls[0].endswith("/fundItems")


def test_public_rayan_resolves_identity_and_catalog_only_once(monkeypatch):
    catalog_calls = public_fund(monkeypatch, "شرکت رایان هم افزا")
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if url.endswith("/fundItems"):
            return response([{"fundId": 1, "fundName": "Other"},
                             {"fundId": 8, "fundName": "Fund A"}], url=url)
        assert url.endswith("/nav/8")
        return response([{"jalaliDate": "1405/07/19", "purchaseNAVPerShare": 3,
                          "sellNAVPerShare": 2, "statisticalNAVPerShare": 2,
                          "units": 10, "nav": 20}], url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    assert Funds.get_daily_navs("Fund A")["TotalNAV"].tolist() == [20]
    assert len(catalog_calls) == 1
    assert len(calls) == 2


@pytest.mark.parametrize("kind", ["در سهام-بخشی", "اختصاصی بازارگردانی"])
def test_tadbir_identity_comes_from_website_not_catalog_group(monkeypatch, kind):
    catalog_calls = public_fund(monkeypatch, "گروه رایانه تدبیر پرداز", kind=kind, group=4)
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs.get("params")))
        if url == "https://fund.example":
            return response(text='<select id="basketId"><option value="2">Other</option>'
                                 '<option value="8">Fund A</option></select>', url=url)
        assert "basketId=8" in url
        data = [chart(80, "")] if "CombinationOfFundAssets" in url else normal_chart(8)
        return response(data, url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    assert Funds.get_daily_navs("Fund A")["TotalNAV"].tolist() == [80]
    assert len(catalog_calls) == 1
    assert sum(url == "https://fund.example" for url, _ in calls) == 1


@pytest.mark.parametrize("options", [
    '<option value="2">Other</option>',
    '<option value="2">Fund A</option><option value="3">Fund A</option>',
    '<option value="bad">Fund A</option>',
])
def test_tadbir_missing_ambiguous_or_invalid_identity_is_not_defaulted(monkeypatch, options):
    public_fund(monkeypatch, "گروه رایانه تدبیر پرداز", kind="در سهام-بخشی", group=4)

    def get(url, **kwargs):
        if url == "https://fund.example":
            return response(text='<select id="basketId">' + options + '</select>', url=url)
        return response([chart(80, "")] if "Combination" in url else normal_chart(8), url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    with pytest.raises(ValueError, match="Tadbir.*identity"):
        Funds.get_daily_navs("Fund A")


def test_current_tadbir_leveraged_schema_without_legacy_common_series(monkeypatch):
    names = ["صدور", "آماری", "ابطال", "صدور ممتاز", "ابطال ممتاز", "آماری ممتاز"]
    data = [chart(value, name) for value, name in enumerate(names, 1)]
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "fund.example")
    monkeypatch.setattr(Funds.requests, "get", lambda url, **kwargs: response(data[::-1], url=url))
    result = Funds._get_leveraged_daily_navs_per_share_tadbirpardaz("A")
    assert result.to_dict("records") == [{
        "Subscription": 1, "Statistical": 2, "Redemption": 3,
        "SpecialSubscription": 4, "SpecialRedemption": 5,
        "SpecialStatistical": 6, "JDate": jd.date(1405, 7, 19)}]


def mabna_nav():
    return {"date_time": "2026-10-11T23:59:59+03:30", "purchase_price": 3,
            "redemption_price": 2, "statistical_value": 2,
            "total_net_asset_value_with_buy_commission_and_discount": 30}


def test_mabna_nav_fields_are_named_not_positional(monkeypatch):
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "fund.example")
    data = dict(reversed(list(mabna_nav().items())))
    monkeypatch.setattr(Funds.requests, "get", lambda url, **kwargs: response({"data": [data]}, url=url))
    assert Funds._get_daily_navs_mabna("A").to_dict("records") == [{
        "JDate": jd.date(1405, 7, 19), "Subscription": 3, "Redemption": 2,
        "Statistical": 2, "TotalSubscriptionNAV": 30}]


def current_assets(date="2026-10-11"):
    return {"date": date, "items": {"assets": [
        {"asset_name": name, "value": value, "percentage": value / 10}
        for name, value in [("سپرده بانکی", 1), ("وجه نقد", 2), ("اوراق بهادار", 3),
                            ("سهام", 4), ("گواهی سپرده کالایی", 5),
                            ("صندوق های سرمایه گذاری", 6), ("سایر دارایی‌ها", 7),
                            ("پنج سهم با بیشترین وزن", 8)]]}}


def test_current_mabna_allocation_and_complete_pagination(monkeypatch):
    public_fund(monkeypatch, "پردازش اطلاعات مالی مبنا")
    pages = []

    def get(url, **kwargs):
        if url.endswith("/portfolios"):
            return response({"data": [{"id": "3", "name": "Fund A"}]}, url=url)
        assert url.endswith("/api/v2/public/reports/daily-assets")
        assert kwargs["params"]["portfolio_id"] == 3
        page = kwargs["params"]["page"]
        pages.append(page)
        return response({"data": [current_assets(f"2026-10-{12-page:02d}")],
                         "total_count": 2}, url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    result = Funds.get_daily_asset_allocation("Fund A")
    assert result["JalaliDate"].tolist() == ["1405-07-19", "1405-07-18"]
    assert result["Stocks"].tolist() == [4, 4]
    assert result["StocksWeight"].tolist() == [.4, .4]
    assert result["CCDs"].tolist() == [5, 5]
    assert pages == [1, 2]


def test_mabna_legacy_allocation_is_retained(monkeypatch):
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "fund.example")
    assets = [dict(a) for a in current_assets()["items"]["assets"]]
    names = ["سپرده بانکی", "وجه نقد", "سرمایه‌گذاری در اوراق بهادار با درآمد ثابت",
             "سرمایه‌گذاری در سهام", "گواهی سپرده کالایی", "صندوق های سرمایه گذاری",
             "سایر دارایی‌ها", " پنج سهم با بیشترین وزن "]
    for item, name in zip(assets, names):
        item["asset_name"] = name
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        if "/api/v2/" in url:
            return response(status=404, text="", url=url)
        return response([{"values": [{"date": "1405/07/19", "assets": assets}]}], url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    assert Funds._get_daily_asset_allocation_mabna("A")["Stocks"].tolist() == [4]
    assert calls[-1].endswith("/api/v1/overall/allassetsdaily.json")


@pytest.mark.parametrize("error", [requests.ReadTimeout, requests.exceptions.SSLError])
def test_new_mabna_endpoint_transport_errors_do_not_fall_back(monkeypatch, error):
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "fund.example")
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        raise error("unavailable")

    monkeypatch.setattr(Funds.requests, "get", get)
    with pytest.raises(error):
        Funds._get_daily_asset_allocation_mabna("A")
    assert calls == ["https://fund.example/api/v2/public/reports/daily-assets"]


def test_mabna_repeated_page_is_an_error(monkeypatch):
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "fund.example")
    monkeypatch.setattr(Funds.requests, "get", lambda url, **kwargs: response(
        {"data": [current_assets()], "total_count": 3}, url=url))
    with pytest.raises(ValueError, match="Mabna.*repeat"):
        Funds._get_daily_asset_allocation_mabna("A")


def test_mabna_malformed_current_assets_are_not_silently_empty(monkeypatch):
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "fund.example")
    data = copy.deepcopy(current_assets())
    del data["items"]["assets"][0]["percentage"]
    monkeypatch.setattr(Funds.requests, "get", lambda url, **kwargs: response({"data": [data]}, url=url))
    with pytest.raises(ValueError, match="Mabna"):
        Funds._get_daily_asset_allocation_mabna("A")


@pytest.mark.parametrize("provider,path,items", [
    ("شرکت رایان هم افزا", "/fundItems", [{"fundId": 1, "fundName": "Other"}]),
    ("پردازش اطلاعات مالی مبنا", "/portfolios", {"data": [{"id": "1", "name": "Other"}]}),
])
def test_single_unrelated_provider_identity_is_never_used(monkeypatch, provider, path, items):
    public_fund(monkeypatch, provider)

    def get(url, **kwargs):
        assert url.endswith(path)
        return response(items, url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    with pytest.raises(NotImplementedError, match="identity.*Fund A"):
        Funds.get_daily_asset_allocation("Fund A")


@pytest.mark.parametrize("error", [requests.ReadTimeout, requests.exceptions.SSLError])
def test_public_request_context_is_reset_after_transport_error(monkeypatch, error):
    public_fund(monkeypatch, "شرکت رایان هم افزا")
    monkeypatch.setattr(Funds.requests, "get", lambda *args, **kwargs: (_ for _ in ()).throw(error("unavailable")))
    with pytest.raises(error):
        Funds.get_daily_navs("Fund A")
    assert Funds._fund_request_context.get() is None


def test_rayan_aggregate_checks_each_record(monkeypatch):
    public_fund(monkeypatch, "شرکت رایان هم افزا", kind="اختصاصی بازارگردانی")
    complete = {"jalaliDate": "1405/07/19", "purchaseNAVPerShare": 11,
                "sellNAVPerShare": 10, "statisticNav": 9, "fundCapital": 5, "totalAssetsValue": 50}
    incomplete = dict(complete, jalaliDate="1405/07/18")
    del incomplete["fundCapital"]
    monkeypatch.setattr(Funds.requests, "get", lambda url, **kwargs: response([complete, incomplete], url=url))
    with pytest.raises(ValueError, match="Rayan aggregate"):
        Funds.get_daily_navs("Fund A")


def test_rayan_converted_fund_name_remains_compatible(monkeypatch):
    public_fund(monkeypatch, "شرکت رایان هم افزا", name="مشترک عقیق")

    def get(url, **kwargs):
        if url.endswith("/fundItems"):
            return response([{"fundId": 1, "fundName": " قابل معامله عقیق"}], url=url)
        return response([{"jalaliDate": "1405/07/19", "purchaseNAVPerShare": 3,
                          "sellNAVPerShare": 2, "statisticalNAVPerShare": 2,
                          "units": 10, "nav": 20}], url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    assert Funds.get_daily_navs("مشترک عقیق")["TotalNAV"].tolist() == [20]


def test_connections_reused_within_download_and_closed_between_funds(monkeypatch):
    public_fund(monkeypatch, "شرکت رایان هم افزا")
    sessions = []

    class Session:
        def __init__(self):
            self.calls = []
            self.closed = False
            sessions.append(self)

        def get(self, url, **kwargs):
            assert kwargs["verify"] is True and kwargs["timeout"] == 30
            self.calls.append(url)
            if url.endswith("/fundItems"):
                return response([{"fundId": 1, "fundName": "Fund A"}], url=url)
            return response([{"jalaliDate": "1405/07/19", "purchaseNAVPerShare": 3,
                              "sellNAVPerShare": 2, "statisticalNAVPerShare": 2,
                              "units": 10, "nav": 20}], url=url)

        def close(self):
            self.closed = True

    monkeypatch.setattr(Funds.requests, "Session", Session)
    for _ in range(2):
        assert Funds.get_daily_navs("Fund A")["TotalNAV"].tolist() == [20]
    assert len(sessions) == 2
    assert all(len(session.calls) == 2 and session.closed for session in sessions)
    assert Funds._fund_request_context.get() is None


def test_tadbir_identical_chart_repeats_are_lossless(monkeypatch):
    data = normal_chart(8)
    for item in data:
        item["List"].append(copy.deepcopy(item["List"][0]))
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "fund.example")
    monkeypatch.setattr(Funds.requests, "get", lambda url, **kwargs: response(data, url=url))
    assert Funds._get_daily_navs_per_share_tadbirpardaz("A").to_dict("records") == [{
        "Subscription": 8, "Statistical": 9, "Redemption": 10, "JDate": jd.date(1405, 7, 19)}]


def test_tadbir_parent_identity_can_be_in_a_second_selector(monkeypatch):
    public_fund(monkeypatch, "گروه رایانه تدبیر پرداز")

    def get(url, **kwargs):
        if url == "https://fund.example":
            return response(text='<select id="basketId"><option value="2">Other</option></select>'
                                 '<select id="basketId"><option value="1">Fund A</option>'
                                 '<option value="2">Other</option></select>', url=url)
        assert "basketId=1" in url
        return response([chart(80, "")] if "Combination" in url else normal_chart(8), url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    assert Funds.get_daily_navs("Fund A")["TotalNAV"].tolist() == [80]


@pytest.mark.parametrize("display", ["آذرین", "صندوق س.بخشی فلزات کیمیا-ب (آذرین)"])
def test_tadbir_sector_alias_resolves_by_exact_catalog_ticker(monkeypatch, display):
    public_fund(monkeypatch, "گروه رایانه تدبیر پرداز", name="بخشی فلزات کیمیا", kind="در سهام-بخشی")
    metadata = pd.DataFrame([{"FundName": "بخشی فلزات کیمیا", "FundTypeName": "در سهام-بخشی",
                              "WebsiteAddress": "fund.example", "Ticker": "آذرین"}])
    monkeypatch.setattr(Funds, "get_all_funds", lambda **kwargs: metadata.copy())

    def get(url, **kwargs):
        if url == "https://fund.example":
            return response(text=f'<select id="basketId"><option value="2">{display}</option></select>', url=url)
        assert "basketId=2" in url
        return response([chart(80, "")] if "Combination" in url else normal_chart(8), url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    assert Funds.get_daily_navs("بخشی فلزات کیمیا")["TotalNAV"].tolist() == [80]


def test_rayan_fixed_income_display_name_remains_compatible(monkeypatch):
    public_fund(monkeypatch, "شرکت رایان هم افزا", name="در اوراق بهادار با درآمد ثابت آریا")

    def get(url, **kwargs):
        if url.endswith("/fundItems"):
            return response([{"fundId": 1, "fundName": "بادرآمد ثابت آریا"}], url=url)
        return response([{"jalaliDate": "1405/07/19", "purchaseNAVPerShare": 3,
                          "sellNAVPerShare": 2, "statisticalNAVPerShare": 2,
                          "units": 10, "nav": 20}], url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    assert Funds.get_daily_navs("در اوراق بهادار با درآمد ثابت آریا")["TotalNAV"].tolist() == [20]


def test_tadbir_allocation_selects_basket_and_preserves_option_holdings(monkeypatch):
    public_fund(monkeypatch, "گروه رایانه تدبیر پرداز", kind="در سهام-بخشی")
    names = ["پنج سهم برتر", "سایر سهام", "اوراق مشارکت", "اوراق سپرده",
             "نقد و بانک (جاری و سپرده)", "سایر دارایی‌ها", "صندوق سرمایه گذاری", "اختیار معامله"]
    weights = ["پنج سهم برتر به کل دارایی", "سایر سهام به کل دارایی", "اوراق مشارکت به کل دارایی",
               "اوراق سپرده به کل دارایی", "وجه نقد به کل دارایی", "سایر دارایی‌ها به کل دارایی",
               "صندوق سرمایه گذاری به کل دارایی", "اختیار معامله به کل دارایی"]
    headers = ["ردیف", "تاریخ"] + names + weights
    values = ["1", "1405/07/19"] + ["1,000"] * len(names) + ["2 %"] * len(weights)
    html = '<table><thead><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr></thead>'
    html += '<tbody><tr>' + ''.join(f'<td>{v}</td>' for v in values) + '</tr></tbody></table>'

    def get(url, **kwargs):
        if url == "https://fund.example":
            return response(text='<select id="basketId"><option value="8">Fund A</option></select>', url=url)
        assert kwargs["params"] == {"basketId": 8, "page": 1}
        return response(text=html, url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    result = Funds.get_daily_asset_allocation("Fund A")
    assert result["Options"].tolist() == [1000]
    assert result["OptionsWeight"].tolist() == [2.0]
    assert result["TopFiveStocks"].tolist() == [1000]


def test_mabna_nav_checks_each_record(monkeypatch):
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "fund.example")
    complete = mabna_nav()
    incomplete = dict(complete, date_time="2026-10-10T23:59:59+03:30")
    del incomplete["purchase_price"]
    monkeypatch.setattr(Funds.requests, "get", lambda url, **kwargs: response({"data": [complete, incomplete]}, url=url))
    with pytest.raises(ValueError, match="Missing Mabna NAV"):
        Funds._get_daily_navs_mabna("A")


def test_mabna_missing_core_asset_on_a_date_is_not_returned_as_nan(monkeypatch):
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "fund.example")
    complete = current_assets()
    incomplete = current_assets("2026-10-10")
    incomplete["items"]["assets"] = [a for a in incomplete["items"]["assets"] if a["asset_name"] != "سهام"]
    monkeypatch.setattr(Funds.requests, "get", lambda url, **kwargs: response({"data": [complete, incomplete]}, url=url))
    with pytest.raises(ValueError, match="Missing Mabna asset"):
        Funds._get_daily_asset_allocation_mabna("A")
