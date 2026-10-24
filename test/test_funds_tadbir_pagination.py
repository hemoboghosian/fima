"""Follow the published date window without changing the selected fund."""
from html import escape

import pytest

import fima.Funds as Funds
from .test_funds_coverage import public_fund
from .test_funds_parent_identity import allocation_html
from .test_funds_http import response


NEXT = "/Reports/FundDailyAssetDistribution?FromDate=1405%2F01%2F01&ToDate=1405%2F07%2F19&page=2"


def setup_site(monkeypatch, links=None, *, require_dates=False):
    public_fund(monkeypatch, "گروه رایانه تدبیر پرداز")
    links = {1: NEXT} if links is None else links
    calls = []

    def get(url, **kwargs):
        if url == "https://fund.example":
            return response(text='<select id="basketId"><option value="2">Fund A</option></select>', url=url)
        assert url == "https://fund.example/Reports/FundDailyAssetDistribution"
        params = dict(kwargs["params"])
        calls.append(params)
        assert params["basketId"] == 2
        if params["page"] > 1 and require_dates and "FromDate" not in params:
            return response(text="<h1>اشکال در عملیات</h1>", url=url)
        page = params["page"]
        html = allocation_html(page).replace("1405/07/19", f"1405/07/{20-page:02d}")
        if page in links:
            href = links[page]
            attr = "" if href is None else f' href="{escape(href, quote=True)}"'
            html = html.replace("</table>", f'<tfoot><tr><td><div class="pager"><a title="Next page"{attr}>Next</a></div></td></tr></tfoot></table>')
        return response(text=html, url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    return calls


def test_public_allocation_carries_next_link_dates_and_keeps_selected_basket(monkeypatch):
    calls = setup_site(monkeypatch, require_dates=True)
    result = Funds.get_daily_asset_allocation("Fund A")
    assert result.JalaliDate.tolist() == ["1405-07-19", "1405-07-18"]
    assert result.TopFiveStocks.tolist() == [1, 2]
    assert calls == [{"basketId": 2, "page": 1},
                     {"basketId": 2, "page": 2, "FromDate": "1405/01/01", "ToDate": "1405/07/19"}]


def test_date_window_is_retained_when_a_later_link_omits_it(monkeypatch):
    calls = setup_site(monkeypatch, {1: NEXT, 2: "?page=3"}, require_dates=True)
    assert len(Funds.get_daily_asset_allocation("Fund A")) == 3
    assert calls[-1] == {"basketId": 2, "page": 3, "FromDate": "1405/01/01", "ToDate": "1405/07/19"}


def test_published_parameter_casing_is_normalized_without_following_another_url(monkeypatch):
    calls = setup_site(monkeypatch, {1: NEXT.lower()}, require_dates=True)
    assert len(Funds.get_daily_asset_allocation("Fund A")) == 2
    assert calls[-1]["FromDate"] == "1405/01/01"


@pytest.mark.parametrize("href", [
    NEXT + "&basketId=3",
    NEXT + "&basketId=2&basketId=3",
    NEXT + "&FromDate=1404%2F01%2F01",
    NEXT + "&fromdate=1404%2F01%2F01",
    NEXT.replace("page=2", "page=5"),
    NEXT.replace("page=2", "page=0"),
    NEXT + "&page=2",
])
def test_ambiguous_or_changed_pagination_cannot_substitute_a_fund_or_skip_pages(monkeypatch, href):
    calls = setup_site(monkeypatch, {1: href})
    with pytest.raises(ValueError, match="Tadbir.*pagination"):
        Funds.get_daily_asset_allocation("Fund A")
    assert len(calls) == 1


@pytest.mark.parametrize("field", ["FromDate", "ToDate"])
def test_pagination_cannot_change_an_established_date_window(monkeypatch, field):
    changed = NEXT.replace("page=2", "page=3").replace(
        "1405%2F01%2F01" if field == "FromDate" else "1405%2F07%2F19", "1404%2F01%2F01")
    calls = setup_site(monkeypatch, {1: NEXT, 2: changed})
    with pytest.raises(ValueError, match="Tadbir.*pagination"):
        Funds.get_daily_asset_allocation("Fund A")
    assert len(calls) == 2


def test_legacy_next_control_without_href_still_advances_one_page(monkeypatch):
    calls = setup_site(monkeypatch, {1: None})
    assert len(Funds.get_daily_asset_allocation("Fund A")) == 2
    assert calls == [{"basketId": 2, "page": 1}, {"basketId": 2, "page": 2}]
