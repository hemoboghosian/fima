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
            if (path, *key) in routes:
                key = (path, *key)
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
    monkeypatch.setattr(codal, "_rate_limit", None)
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


def test_monthly_request_budget_includes_redirects_and_all_history(provider, monthly_payload, monkeypatch):
    routes, calls = provider
    newest = _letter(12, "b", corrected=True)
    oldest = _letter(11, "a")
    routes[3, 58, 1] = _results(newest, total=9, pages=9)
    for page_number in range(2, 9):
        unrelated = _letter(100 + page_number, "unused", date="1404/06/31")
        routes[3, 58, page_number] = _results(unrelated, total=9, pages=9)
    routes[3, 58, 9] = _results(oldest, total=9, pages=9)
    for serial in ("a", "b"):
        routes["/Reports/Decision.aspx", serial, None] = (
            302, {"Location": f"/Reports/MonthlyActivity.aspx?LetterSerial={serial}"}, {},
        )
    routes["/Reports/MonthlyActivity.aspx", "a", None] = _html(
        dict(monthly_payload, tracingNo=11, kind=0), "a", extra=_revision("New", "b", 12),
    )
    routes["/Reports/MonthlyActivity.aspx", "b", None] = _html(
        dict(monthly_payload, tracingNo=12), "b", extra=_revision("Prev", "a", 11),
    )

    def check(searches):
        assert [params["PageNumber"] for _, params in searches] == list(range(1, 10))
        assert all(set(params) == {"PageNumber", "Symbol", "Category", "LetterType"}
                   for _, params in searches)

    for first_search in (1, 0):
        calls.clear()
        result = get_codal_data("نمونه", "گزارش عملکرد ماهانه", "1404/07")
        assert result.attrs["RevisionTracingNos"] == [11, 12]
        assert result.attrs["Filing"]["TracingNo"] == 12
        assert len(calls) == first_search + 12
        check(calls[first_search:-3])
        assert [urlsplit(url).path for url, _ in calls[-3:]] == [
            "/Reports/Decision.aspx", "/Reports/MonthlyActivity.aspx", "/Reports/MonthlyActivity.aspx",
        ]
        assert "LetterSerial=a" in calls[-1][0]

    calls.clear()
    rows = search_codal_filings("نمونه", "گزارش ماهانه", CURRENT)
    check(calls)
    assert rows.TracingNo.tolist() == [12, 11]

    calls.clear()
    blocked = routes["/Reports/MonthlyActivity.aspx", "a", None]
    routes["/Reports/MonthlyActivity.aspx", "a", None] = b'<html><h1 id="captchaTitle">Verify</h1></html>'
    with pytest.raises(CodalRequestError, match="human verification"):
        get_codal_data("نمونه", "گزارش ماهانه", CURRENT)
    assert len(calls) == 12
    routes["/Reports/MonthlyActivity.aspx", "a", None] = blocked

    calls.clear()
    monkeypatch.setattr(codal, "_monthly_predecessor_url", lambda *args: None)
    baseline = get_codal_data("نمونه", "گزارش ماهانه", CURRENT)
    assert len(calls) == 13
    assert baseline.equals(result)
    assert baseline.attrs == result.attrs


@pytest.mark.parametrize("usable_predecessor", [True, False])
def test_only_returned_revision_needs_requested_statement(provider, usable_predecessor):
    routes, calls = provider
    corrected = statement_payload()
    corrected.update(tracingNo=12, kind=1)
    corrected["sheets"][0]["title_Fa"] = "صورت سود و زیان"
    date = corrected["periodEndToDate"]
    original = statement_payload(sheets=("0",))
    original.update(tracingNo=11, kind=0)
    original["sheets"][0]["title_Fa"] = "صورت وضعیت مالی"
    older_income = dict(corrected, kind=0, tracingNo=11)
    rows = (_letter(12, "b", date=date, corrected=True, months=6, type_id=6),
            _letter(11, "a", date=date, months=6, type_id=6))
    routes[1, 6, 1] = _results(*rows)
    menu = ('<select id="ddlTable"><option value="0" selected="selected">صورت وضعیت مالی</option>'
            '<option value="1">صورت سود و زیان</option></select>')
    selected = '<select id="ddlTable"><option value="1" selected="selected">صورت سود و زیان</option></select>'
    routes["b", None] = menu.encode()
    routes["b", "1"] = _html(corrected, "b", extra=selected + _revision("Prev", "a", 11))
    routes["a", None] = (
        _html(original, "a", extra=menu + _revision("New", "b", 12))
        if usable_predecessor else menu.encode()
    )
    if not usable_predecessor:
        routes["a", "1"] = _html(older_income, "a", extra=selected + _revision("New", "b", 12))

    result = get_codal_data("نمونه", "صورت سود و زیان", date)
    assert result.attrs["RevisionTracingNos"] == [11, 12]
    assert result.attrs["Coverage"]["RequestedSheetId"] == "1"
    assert result.loc[result.Address.eq("B4"), "Value"].item() == Decimal("12.125")
    assert len(calls) == (5 if usable_predecessor else 6)
    if usable_predecessor:
        routes["a", None] = _html(original, "a", extra=menu + _revision("New", "b", 12),
                                  symbol="ناشر دیگر")
        with pytest.raises(ValueError, match="symbol disagrees"):
            get_codal_data("نمونه", "صورت سود و زیان", date)


def test_definitive_ambiguity_uses_only_first_page_but_search_stays_complete(provider):
    routes, calls = provider
    one = _letter(11, "a", months=6, type_id=6)
    two = _letter(12, "b", months=6, type_id=6)
    two["Title"] = two["Title"].replace("نشده", "شده")
    late = _letter(13, "c", months=6, type_id=6, corrected=True)
    routes[1, 6, 1] = _results(one, two, total=3, pages=35)
    with pytest.raises(ValueError, match="audit statuses"):
        get_codal_data("نمونه", "صورت‌های مالی", CURRENT)
    assert len(calls) == 2

    routes[1, 6, 1] = _results(one, two, total=3, pages=2)
    routes[1, 6, 2] = _results(late, total=3, pages=2)
    assert search_codal_filings("نمونه", "صورت‌های مالی", CURRENT).TracingNo.tolist() == [13, 12, 11]


@pytest.mark.parametrize("func", [get_codal_data, search_codal_filings])
def test_invalid_search_inputs_use_no_requests(provider, func):
    _, calls = provider
    with pytest.raises(ValueError, match="symbol"):
        func(" ", "گزارش ماهانه")
    with pytest.raises(ValueError, match="max_pages"):
        func("نمونه", "گزارش ماهانه", max_pages=0)
    assert not calls


@pytest.mark.parametrize("retry_after", ["60", "Tue, 14 Nov 2023 22:14:20 GMT"])
def test_retry_after_is_respected_across_calls_without_sleeping(provider, monkeypatch, retry_after):
    routes, calls = provider
    tick = [10]
    monkeypatch.setattr(codal, "monotonic", lambda: tick[0])
    monkeypatch.setattr(codal, "time", lambda: 1_700_000_000)
    routes[3, 58, 1] = _results(_letter(11, "a"))
    row = search_codal_filings("نمونه", "گزارش ماهانه").iloc[0]
    routes[3, 58, 1] = _results(_letter(11, "a"), total=3, pages=3)
    routes[3, 58, 2] = (429, {"Retry-After": retry_after}, {})
    routes["a", None] = b'<html><h1 id="captchaTitle">Verify</h1></html>'
    calls.clear()
    with pytest.raises(CodalRequestError) as error:
        get_codal_data("نمونه", "گزارش ماهانه")
    assert retry_after in str(error.value)
    assert [params["PageNumber"] for _, params in calls] == [1, 2]

    tick[0] = 69
    with pytest.raises(CodalRequestError, match="429"):
        fetch_codal_report(row)
    with pytest.raises(CodalRequestError, match="429"):
        search_codal_filings("نمونه", "گزارش ماهانه")
    assert len(calls) == 2

    tick[0] = 70
    with pytest.raises(CodalRequestError, match="human verification"):
        fetch_codal_report(row)
    assert len(calls) == 3


@pytest.mark.parametrize("headers", [{}, {"Retry-After": "invalid"}])
def test_rate_limit_without_usable_retry_after_stops_the_operation(provider, headers):
    routes, calls = provider
    routes[3, 58, 1] = (429, headers, {})
    with pytest.raises(CodalRequestError, match="rate-limited"):
        get_codal_data("نمونه", "گزارش ماهانه")
    assert len(calls) == 2
