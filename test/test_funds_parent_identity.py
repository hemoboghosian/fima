"""A multi-compartment site's canonical fund is distinct from its ticker alias."""
import pandas as pd
import pytest

import fima.Funds as Funds
from .test_funds_coverage import normal_chart, chart, public_fund
from .test_funds_http import response


NAME = "بخشی صنایع آزمون"


def allocation_html(value):
    assets = ["پنج سهم برتر", "سایر سهام", "اوراق مشارکت", "اوراق سپرده",
              "نقد و بانک (جاری و سپرده)", "سایر دارایی‌ها", "صندوق سرمایه گذاری"]
    weights = ["پنج سهم برتر به کل دارایی", "سایر سهام به کل دارایی",
               "اوراق مشارکت به کل دارایی", "اوراق سپرده به کل دارایی",
               "وجه نقد به کل دارایی", "سایر دارایی‌ها به کل دارایی",
               "صندوق سرمایه گذاری به کل دارایی"]
    headers = ["ردیف", "تاریخ"] + assets + weights
    values = ["1", "1405/07/19"] + [str(value)] * len(assets) + ["1 %"] * len(weights)
    return ("<table><thead><tr>" + "".join(f"<th>{h}</th>" for h in headers)
            + "</tr></thead><tbody><tr>" + "".join(f"<td>{v}</td>" for v in values)
            + "</tr></tbody></table>")


def site(monkeypatch, options, *, title=NAME, defaults="var portfolioId = 8;"):
    public_fund(monkeypatch, "گروه رایانه تدبیر پرداز", name=NAME, kind="در سهام-بخشی")
    metadata = pd.DataFrame([{"FundName": NAME, "WebsiteAddress": "fund.example",
                              "FundTypeName": "در سهام-بخشی", "FundTypeID": "21",
                              "Ticker": "AAA", "GroupId": "4"}])
    monkeypatch.setattr(Funds, "get_all_funds", lambda **kwargs: metadata.copy())
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs.get("params")))
        if url == "https://fund.example":
            return response(text=f"<title>صندوق سرمایه گذاری {title}</title>"
                                 f"<script>{defaults}</script>"
                                 f'<select id="basketId">{options}</select>', url=url)
        if "FundDailyAssetDistribution" in url:
            return response(text=allocation_html(kwargs["params"]["basketId"]), url=url)
        value = int(url.rsplit("=", 1)[-1])
        return response([chart(value, "")] if "Combination" in url else normal_chart(value), url=url)

    monkeypatch.setattr(Funds.requests, "get", get)
    return calls


@pytest.mark.parametrize("allocation", [False, True])
@pytest.mark.parametrize("child", ["Unrelated child", "Child (AAA)", f"{NAME} (AAA)"])
def test_canonical_parent_uses_published_default_not_ticker_or_catalog_group(monkeypatch, allocation, child):
    calls = site(monkeypatch, f'<option value="2">{child}</option>')
    download = Funds.get_daily_asset_allocation if allocation else Funds.get_daily_navs
    result = download(NAME)
    assert result["TopFiveStocks" if allocation else "TotalNAV"].tolist() == [8]
    assert result.JalaliDate.tolist() == ["1405-07-19"]
    assert sum(url == "https://fund.example" for url, _ in calls) == 1


@pytest.mark.parametrize("allocation", [False, True])
def test_exact_selector_name_precedes_a_shared_ticker_alias(monkeypatch, allocation):
    site(monkeypatch, f'<option value="7">{NAME}</option>'
                     '<option value="2">Child (AAA)</option>')
    download = Funds.get_daily_asset_allocation if allocation else Funds.get_daily_navs
    result = download(NAME)
    assert result["TopFiveStocks" if allocation else "TotalNAV"].tolist() == [7]


@pytest.mark.parametrize("title,defaults", [
    ("Other fund", "var portfolioId = 8;"),
    (NAME, ""),
    (NAME, "var portfolioId = 8; var portfolioId = 9;"),
    (NAME, "var portfolioId = -1;"),
])
def test_parent_identity_requires_matching_title_and_unambiguous_published_default(monkeypatch, title, defaults):
    site(monkeypatch, '<option value="2">Other child</option>', title=title, defaults=defaults)
    with pytest.raises(ValueError, match="Tadbir.*identity"):
        Funds.get_daily_navs(NAME)


def test_canonical_default_does_not_hide_conflicting_named_selector_ids(monkeypatch):
    site(monkeypatch, f'<option value="7">{NAME}</option><option value="9">{NAME}</option>')
    with pytest.raises(ValueError, match="Tadbir.*identity"):
        Funds.get_daily_navs(NAME)


@pytest.mark.parametrize("defaults", ["", "var portfolioId = -1;", "var portfolioId = 8; var portfolioId = -1;"])
def test_invalid_parent_default_does_not_fall_back_to_a_child_ticker(monkeypatch, defaults):
    site(monkeypatch, '<option value="2">Child (AAA)</option>', defaults=defaults)
    with pytest.raises(ValueError, match="Tadbir.*identity"):
        Funds.get_daily_navs(NAME)
