"""A renamed ticker cannot change an exact numbered legal compartment."""
import pytest

import fima.Funds as Funds
from .test_funds_coverage import public_fund, normal_chart, chart
from .test_funds_http import response
from .test_funds_parent_identity import allocation_html


NAME = "جام- صندوق کالای آزمایش 2-بخشی"
PUBLISHED = "جام طلا - صندوق کالای آزمایش 2-بخشی"


def site(monkeypatch, options, name=NAME):
    public_fund(monkeypatch, "گروه رایانه تدبیر پرداز", name=name, group=99)
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs.get("params")))
        if url == "https://fund.example":
            return response(text='<title>صندوق کالای آزمایش</title>'
                                 '<script>var portfolioId=1;</script>'
                                 f'<select id="basketId">{options}</select>', url=url)
        if "FundDailyAssetDistribution" in url:
            return response(text=allocation_html(kwargs["params"]["basketId"]), url=url)
        value = int(url.rsplit("=", 1)[-1])
        return response([chart(value, "")] if "Combination" in url else normal_chart(value), url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    return calls


@pytest.mark.parametrize("allocation", [False, True])
def test_renamed_ticker_preserves_exact_numbered_legal_compartment(monkeypatch, allocation):
    site(monkeypatch, '<option value="2">Other child (AAA)</option>'
                     f'<option value="3">{PUBLISHED}</option>')
    download = Funds.get_daily_asset_allocation if allocation else Funds.get_daily_navs
    result = download(NAME)
    assert result["TopFiveStocks" if allocation else "TotalNAV"].tolist() == [3]


def test_numbered_legal_name_cannot_choose_between_conflicting_selector_ids(monkeypatch):
    site(monkeypatch, f'<option value="3">{PUBLISHED}</option>'
                     f'<option value="4">{PUBLISHED}</option>')
    with pytest.raises(ValueError, match="Tadbir.*identity"):
        Funds.get_daily_navs(NAME)


@pytest.mark.parametrize("label", [
    PUBLISHED.replace(" 2-", " 1-"),
    PUBLISHED.replace("آزمایش", "دیگر"),
    "جام طلا - صندوق کالای آزمایش 2",
    "Other child (AAA)",
])
def test_different_or_incomplete_legal_compartment_is_not_a_match(monkeypatch, label):
    site(monkeypatch, f'<option value="3">{label}</option>')
    with pytest.raises(ValueError, match="Tadbir.*identity"):
        Funds.get_daily_navs(NAME)


def test_parent_is_not_matched_to_a_numbered_child(monkeypatch):
    site(monkeypatch, f'<option value="3">{PUBLISHED}</option>', name="صندوق کالای دیگر")
    with pytest.raises(ValueError, match="Tadbir.*identity"):
        Funds.get_daily_navs("صندوق کالای دیگر")


def test_exact_selector_name_has_precedence_over_a_renamed_prefix(monkeypatch):
    site(monkeypatch, f'<option value="3">{PUBLISHED}</option>'
                     f'<option value="4">{NAME}</option>')
    assert Funds.get_daily_navs(NAME).TotalNAV.tolist() == [4]
