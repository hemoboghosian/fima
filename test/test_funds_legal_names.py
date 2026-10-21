"""Observed fixed-income legal spellings identify the same provider fund."""
import pytest
import fima.Funds as Funds
from .test_funds_coverage import public_fund, mabna_nav, current_assets
from .test_funds_http import response
from .test_funds_rayan import allocation


@pytest.mark.parametrize("catalog_name,provider_name,provider", [
    ("در اوراق بهادار با در آمد ثابت کاریزما", "در اوراق بهادار با درآمد ثابت کاریزما", "شرکت رایان هم افزا"),
    ("در اوراق بهادار با درآمد ثابت برلیان شهر", "صندوق درآمد ثابت برلیان شهر", "پردازش اطلاعات مالی مبنا"),
])
@pytest.mark.parametrize("assets", [False, True])
def test_verified_fixed_income_spelling_matches_public_identity(monkeypatch, catalog_name, provider_name, provider, allocation, assets):
    public_fund(monkeypatch, provider, name=catalog_name, kind="در اوراق بهادار با درآمد ثابت")
    def get(url, **kwargs):
        if url.endswith("/fundItems"):
            return response([{"fundId": 8, "fundName": provider_name}], url=url)
        if url.endswith("/portfolios"):
            return response({"data": [{"id": "8", "name": provider_name}]}, url=url)
        if provider == "پردازش اطلاعات مالی مبنا":
            assert kwargs["params"]["portfolio_id"] == 8
            return response({"data": [current_assets() if assets else mabna_nav()]}, url=url)
        if assets:
            assert url.endswith("/dailyAssetStructure/8")
            return response([{**allocation, "fundId": 8}], url=url)
        assert url.endswith("/nav/8")
        return response([{"jalaliDate": "1405/07/19", "purchaseNAVPerShare": 3,
                          "sellNAVPerShare": 2, "statisticalNAVPerShare": 2,
                          "units": 10, "nav": 20}], url=url)
    monkeypatch.setattr(Funds.requests, "get", get)
    result = (Funds.get_daily_asset_allocation if assets else Funds.get_daily_navs)(catalog_name)
    assert result.JalaliDate.tolist() == ["1405-07-19"]
    assert result["Stocks" if assets else "SubscriptionNAV"].tolist() == [
        (4 if provider == "پردازش اطلاعات مالی مبنا" else 1) if assets else 3]


def test_fixed_income_spelling_does_not_match_a_different_brand(monkeypatch):
    public_fund(monkeypatch, "شرکت رایان هم افزا", name="در اوراق بهادار با در آمد ثابت آریا")
    monkeypatch.setattr(Funds.requests, "get", lambda url, **kwargs: response([{"fundId": 8, "fundName": "درآمد ثابت دیگر"}], url=url))
    with pytest.raises(NotImplementedError, match="identity"):
        Funds.get_daily_navs("در اوراق بهادار با در آمد ثابت آریا")
