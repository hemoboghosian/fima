"""Contracts for CODAL's public search and HTML retrieval, without network access."""

from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from fima import (
    fetch_codal_report, get_codal_data, get_codal_tables,
    list_codal_report_types, search_codal_filings,
)
from fima import codal
from fima.codal import CodalRequestError
from test.test_codal_financial_statements import _payload as statement_payload
from test.test_codal_monthly_activity import CURRENT, payload as monthly_payload


def _category(code, name, *types):
    return {"Code": code, "Name": name, "PublisherTypes": [
        {"Code": 1, "Name": "ناشران", "LetterTypes": [
            {"Id": identifier, "Name": label} for identifier, label in types
        ]}
    ]}


@pytest.fixture
def provider(monkeypatch):
    routes = {}
    calls = []
    categories = [
        _category(1, "اطلاعات و صورت مالی سالانه", (6, "اطلاعات و صورتهای مالی میاندوره ای")),
        _category(2, "افشااطلاعات با اهمیت و شفاف سازی", (11, "افشای اطلاعات با اهمیت")),
        _category(3, "گزارش عملکرد ماهانه", (8, "صورت وضعیت پورتفوی"), (58, "گزارش فعالیت ماهانه")),
        _category(6, "آگهی دعوت به مجامع و تصمیمات",
                  (16, "آگهی دعوت به مجمع عمومی عادی سالیانه"), (18, "آگهی دعوت به مجمع عمومی فوق العاده"),
                  (20, "تصمیمات مجمع عمومی عادی سالیانه"), (22, "تصمیمات مجمع عمومی فوق‌العاده")),
    ]

    def get(session, url, *, params, timeout, allow_redirects, headers):
        assert timeout == (10, 25)
        assert not allow_redirects
        assert headers["User-Agent"] == "fima"
        calls.append((url, params))
        path = urlsplit(url).path
        key = path
        if path == "/api/search/v2/q":
            key = (params["Category"], params["LetterType"], params["PageNumber"])
        elif path.startswith("/Reports/"):
            query = parse_qs(urlsplit(url).query)
            key = (query["LetterSerial"][0], query.get("sheetId", [None])[0])
        item = routes[key]
        if isinstance(item, Exception):
            raise item
        response = requests.Response()
        response.url = url
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        if isinstance(item, tuple):
            response.status_code, extra_headers, item = item
            response.headers.update(extra_headers)
        if isinstance(item, bytes):
            response._content = item
            response.headers["Content-Type"] = "text/html; charset=utf-8"
        else:
            response._content = json.dumps(item).encode()
        return response

    monkeypatch.setattr(requests.Session, "get", get)
    monkeypatch.setattr(codal, "_taxonomy_cache", None)
    routes["/api/search/v1/categories"] = categories
    return routes, calls


def _letter(tracing, serial, *, date=CURRENT, corrected=False, months=1, title=None,
            symbol="نمونه", type_id=58, published=None):
    if title is None:
        name = ("گزارش فعالیت ماهانه" if type_id == 58
                else "اطلاعات و صورت‌های مالی میاندوره‌ای")
        title = f"{name} دوره {months} ماهه منتهی به  {date}"
        if type_id == 6:
            title += " (حسابرسی نشده)"
        if corrected:
            title += "(اصلاحیه)"
    return {
        "TracingNo": tracing, "Title": title, "HasHtml": True, "Symbol": symbol,
        "CompanyName": "نمونه", "LetterCode": "ن-۳۰" if type_id == 58 else "ن-۱۰",
        "PublishDateTime": published or ("۱۴۰۴/۰۸/۰۹ ۱۲:۳۰:۰۰" if corrected else "۱۴۰۴/۰۸/۰۵ ۱۲:۳۰:۰۰"),
        "Url": f"/Reports/Decision.aspx?LetterSerial={serial}&let={type_id}",
    }


def _results(*letters, total=None, pages=1):
    return {"Letters": list(letters), "Total": len(letters) if total is None else total,
            "Page": pages, "IsAttacker": False}


def _html(payload, serial, *, extra="", symbol="نمونه"):
    return (
        f'<html><span id="ctl00_txbSymbol">{symbol}</span>'
        '<span id="ctl00_txbCompanyName">شرکت نمونه</span>'
        f'<span id="ctl00_lblPeriodEndToDate">{payload["periodEndToDate"]}</span>'
        f'<span id="ctl00_lblYearEndToDate">{payload["yearEndToDate"]}</span>'
        f'<span id="ctl00_lblIsAudited">({"حسابرسی شده" if payload.get("isAudited") else "حسابرسی نشده"})</span>'
        f'<span id="ctl00_pPriceNote">کلیه مبالغ درج شده به میلیون ریال می باشد</span>'
        f'<input id="ctl00_cphBody_ucDynamicFinancialStatement_hdfLetterRef" value="{serial}">'
        f'{extra}<script>\nvar datasource = {json.dumps(payload)};\n</script></html>'
    ).encode()


def _revision(which, serial, trace):
    return (
        f'<a id="ctl00_cphBody_ucNavigateToNextPrevLetter_hl{which}Version" '
        f'href="MonthlyActivity.aspx?LetterSerial={serial}">اطلاعیه شماره ( {trace} )</a>'
    )


@pytest.mark.parametrize("name", [
    "گزارش  عملكرد ماهانه", "گزارش فعاليت‌ ماهانه", "گزارش ماهانه",
])
def test_aliases_use_category_and_type_not_letter_code(provider, name):
    routes, calls = provider
    routes[3, 58, 1] = _results(_letter(12, "a"))
    data = search_codal_filings(" نمونه ", name, "مهر ١٤٠٤")
    assert data.iloc[0][["CategoryId", "LetterTypeId", "LetterCode", "ReportingPeriodEnd"]].tolist() == [
        3, 58, "ن-۳۰", CURRENT,
    ]
    assert calls[-1][1] == {"Category": 3, "LetterType": 58, "Symbol": "نمونه", "PageNumber": 1}
    assert list_codal_report_types().query("LetterTypeId == 58").iloc[0].CategoryName == "گزارش عملکرد ماهانه"


def test_unknown_and_conflicting_taxonomy(provider, monkeypatch):
    routes, calls = provider
    with pytest.raises(ValueError, match="صورت‌های مالی"):
        search_codal_filings("نمونه", "گزارش خیالی")
    assert len(calls) == 1
    routes["/api/search/v1/categories"].append(_category(9, "مقوله دیگر", (58, "گزارش فعالیت ماهانه")))
    monkeypatch.setattr(codal, "monotonic", lambda: float("inf"))
    with pytest.raises(CodalRequestError, match="conflicting categories"):
        search_codal_filings("نمونه", "گزارش ماهانه")


def test_taxonomy_cache_refreshes_conservatively(provider, monkeypatch):
    routes, calls = provider
    monkeypatch.setattr(codal, "monotonic", lambda: 1)
    first = list_codal_report_types()
    assert len(calls) == 1
    first.loc[0, "CategoryName"] = "changed"
    again = list_codal_report_types()
    assert len(calls) == 1
    assert again.iloc[0].CategoryName != "changed"
    monkeypatch.setattr(codal, "monotonic", lambda: 602)
    routes["/api/search/v1/categories"] = (429, {}, {})
    with pytest.raises(CodalRequestError, match="rate-limited"):
        list_codal_report_types()
    assert len(calls) == 2


def test_search_families_use_verified_type_or_period(provider):
    routes, _ = provider
    financial = _letter(1, "f", months=6, type_id=6)
    annual = _letter(2, "a", months=12, type_id=6)
    routes[1, 6, 1] = _results(financial, annual)
    assert set(search_codal_filings("نمونه", "صورت هاى مالى").TracingNo) == {1, 2}
    assert search_codal_filings("نمونه", "صورت‌های مالی سالانه").TracingNo.tolist() == [2]
    assert search_codal_filings("نمونه", "صورت مالی میان‌دوره‌ای").TracingNo.tolist() == [1]
    routes[6, 16, 1] = _results(_letter(16, "g", type_id=16))
    routes[6, 18, 1] = _results(_letter(18, "h", type_id=18))
    assert set(search_codal_filings("نمونه", "دعوت به مجمع").LetterTypeId) == {16, 18}
    with pytest.raises(ValueError, match="reporting-period"):
        search_codal_filings("نمونه", "اطلاعات با اهميت", "1404/07")


def test_pagination_keeps_corrections_filters_false_issuer_and_is_complete(provider):
    routes, _ = provider
    one, two = _letter(1, "a"), _letter(2, "b", corrected=True)
    wrong = _letter(3, "c", symbol="نمونه دیگر")
    routes[3, 58, 1] = _results(two, wrong, total=3, pages=2)
    routes[3, 58, 2] = _results(one, total=3, pages=2)
    results = search_codal_filings("نمونه", "گزارش ماهانه", CURRENT)
    assert results.TracingNo.tolist() == [2, 1]
    assert results.IsCorrected.tolist() == [True, False]
    with pytest.raises(CodalRequestError, match="incomplete"):
        search_codal_filings("نمونه", "گزارش ماهانه", max_pages=1)
    routes[3, 58, 2] = _results(two, total=3, pages=2)
    with pytest.raises(CodalRequestError, match="changed"):
        search_codal_filings("نمونه", "گزارش ماهانه")
    routes[3, 58, 2] = _results(one, total=4, pages=2)
    with pytest.raises(CodalRequestError, match="changed"):
        search_codal_filings("نمونه", "گزارش ماهانه")
    routes[3, 58, 1] = _results(pages=0)
    assert search_codal_filings("نمونه", "گزارش ماهانه").empty


def test_monthly_download_validates_revisions_and_normalizes_real_grid_contract(provider, monthly_payload):
    routes, _ = provider
    one, two = _letter(11, "a"), _letter(12, "b", corrected=True)
    routes[3, 58, 1] = _results(two, one)
    original = dict(monthly_payload, tracingNo=11, kind=0)
    corrected = dict(monthly_payload, tracingNo=12, kind=1)
    routes["a", None] = _html(original, "a", extra=_revision("New", "b", 12))
    routes["b", None] = _html(corrected, "b", extra=_revision("Prev", "a", 11))
    result = get_codal_data("نمونه", "گزارش عملکرد ماهانه", "۱۴۰۴/۰۷")
    assert len(result) == 230
    assert result.attrs["RevisionTracingNos"] == [11, 12]
    assert result.attrs["Filing"]["LetterCode"] == "ن-۳۰"
    assert set(result.TracingNo) == {12}
    assert set(result.ContentSha256) == {sha256(routes["b", None]).hexdigest()}
    ambiguous = _letter(13, "c")
    unrelated = dict(monthly_payload, tracingNo=13, kind=0)
    routes["c", None] = _html(unrelated, "c")
    routes[3, 58, 1] = _results(two, one, ambiguous)
    with pytest.raises(ValueError, match="incompatible"):
        get_codal_data("نمونه", "گزارش ماهانه", CURRENT)
    routes[3, 58, 1] = _results(two, one)
    sale = result.loc[result.Address.eq("Q4")].iloc[0]
    assert (sale.Value, sale.PeriodBasis, sale.Unit, sale.Scale) == (Decimal("75"), "CurrentMonth", "IRR", 10**6)
    assert result.loc[result.Address.eq("O4"), "Value"].item() == Decimal("0")
    assert result.loc[result.Address.eq("O5"), "Value"].item() is None
    routes["b", None] = _html(corrected, "b", extra=_revision("Prev", "conflicting", 11))
    with pytest.raises(ValueError, match="conflicting identity"):
        get_codal_data("نمونه", "گزارش ماهانه", CURRENT)


def test_financial_sheet_is_selected_from_form_and_validated(provider):
    routes, calls = provider
    report = statement_payload()
    report["sheets"][0]["title_Fa"] = "صورت سود و زیان"
    first = _letter(report["tracingNo"], "f", date=report["periodEndToDate"], months=6, type_id=6)
    routes[1, 6, 1] = _results(first)
    options = '<select id="ddlTable"><option value="19">نظر حسابرس</option>{}</select>'
    routes["f", None] = (
        "<html>" + options.format('<option value="1">صورت سود و زیان</option>'
                                 '<option value="71">صورت سود و زیان جامع</option>') + "</html>"
    ).encode()
    selected = options.format('<option value="1" selected="selected">صورت سود و زیان</option>')
    routes["f", "1"] = _html(report, "f", extra=selected)
    result = get_codal_data("نمونه", "صورت سود و زيان", report["periodEndToDate"])
    assert result.attrs["Coverage"]["RequestedSheetId"] == "1"
    assert set(result.StatementType) == {"IncomeStatement"}
    assert result.loc[result.Address.eq("B4"), "Value"].item() == Decimal("12.125")
    assert {check["Status"] for check in result.attrs["Reconciliations"]} == {"Passed"}
    assert calls[-1][0].endswith("sheetId=1")
    row = search_codal_filings("نمونه", "صورت مالی").iloc[0]
    assert fetch_codal_report(row, statement="سود و زیان")["Content"] == routes["f", "1"]
    with pytest.raises(ValueError, match="no unique sheet"):
        fetch_codal_report(row, statement="ترازنامه")
    routes["f", "1"] = _html(report, "f", extra=selected, symbol="نماد متفاوت")
    with pytest.raises(ValueError, match="symbol disagrees"):
        fetch_codal_report(row, statement="سود و زیان")


def test_unsupported_template_raw_mode_uses_menu_id_without_guessing(provider):
    routes, _ = provider
    report = statement_payload()
    report["title_En"] = "FinancialStatement-Listed-Product-V9"
    report["sheets"][0].update(code=47, title_Fa="صورت سود و زیان")
    first = _letter(report["tracingNo"], "f", date=report["periodEndToDate"], months=6, type_id=6)
    routes[1, 6, 1] = _results(first)
    routes["f", None] = b'<select id="ctl00_ddlTable"><option value="47">placeholder</option></select>'.replace(
        b"placeholder", "صورت سود و زیان".encode(),
    )
    routes["f", "47"] = _html(report, "f")
    with pytest.raises(ValueError, match="CODAL"):
        get_codal_data("نمونه", "صورت‌های مالی")
    result = get_codal_data("نمونه", "صورت‌های مالی", raw=True)
    assert set(result.SheetId) == {"47"}
    assert result.loc[result.Address.eq("B4"), "Value"].item() == "12.125"
    assert result.attrs["Tables"][0]["TitleFa"] is None
    assert get_codal_tables(fetch_codal_report(
        search_codal_filings("نمونه", "صورت‌های مالی").iloc[0], statement="صورت سود و زیان",
    ))[0]["Cells"].equals(result)


def test_no_arbitrary_choice_across_audit_statuses(provider):
    routes, _ = provider
    one = _letter(11, "a", months=6, type_id=6)
    two = _letter(12, "b", months=6, type_id=6)
    two["Title"] = two["Title"].replace("نشده", "شده")
    subsidiary = deepcopy(one)
    subsidiary.update(TracingNo=13, Title=one["Title"] + " (شرکت فرعی)")
    routes[1, 6, 1] = _results(one, two, subsidiary)
    assert search_codal_filings("نمونه", "صورت مالی").IsIssuerReport.tolist() == [False, True, True]
    with pytest.raises(ValueError, match="audit statuses"):
        get_codal_data("نمونه", "صورت مالی", CURRENT)


@pytest.mark.parametrize(("response", "message"), [
    (requests.Timeout("read timeout"), "request .* failed"),
    ((429, {"Retry-After": "60"}, {}), "rate-limited .*Retry-After: 60"),
    ((503, {}, {}), "HTTP 503"),
    ({"IsAttacker": True}, "human verification"),
    ((302, {"Location": "https://example.org/redirect"}, {}), "outside the expected HTTPS hosts"),
])
def test_provider_errors_are_not_empty_rows(provider, response, message):
    routes, _ = provider
    routes[3, 58, 1] = response
    with pytest.raises(CodalRequestError, match=message):
        search_codal_filings("نمونه", "گزارش ماهانه")


def test_captcha_and_wrong_letter_type_are_detected(provider):
    routes, _ = provider
    routes[3, 58, 1] = _results(_letter(12, "a"))
    routes["a", None] = b'<html><h1 id="captchaTitle">Verify</h1></html>'
    with pytest.raises(CodalRequestError, match="human verification"):
        get_codal_data("نمونه", "گزارش ماهانه", CURRENT)
    routes[3, 58, 1] = _results(_letter(12, "a", type_id=8))
    with pytest.raises(CodalRequestError, match="different letter type"):
        search_codal_filings("نمونه", "گزارش ماهانه")
