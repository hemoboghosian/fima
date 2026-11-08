"""Small source-shaped fixtures; deterministic tests never contact IFB."""
from types import SimpleNamespace

import pandas as pd
import pytest
import requests

import fima
import fima.IFB as ifb


INDUSTRY = """<label id="lbldt">یکشنبه 17 آبان ماه ساعت 05:09:05</label>
<script>var indArray=[];
indArray.push(['اوراق تامين مالي ',9007199254740993,2]);
indArray.push(['فلزات اساسي ',100,1]);</script>
<div id="ContentPlaceHolder1_tblContainer"><table class="tblGrp">
<tr style="display:none"><td>نماد</td><td>نام شرکت</td><td>ارزش</td><td>بازار</td><td>صنعت</td><td>زیر صنعت</td></tr>
<tr class="grpHead"><td></td><td>اوراق تامين مالي</td><td>9 B (99/99%)</td></tr>
<tr class="grpData"><td><a href="/Instruments.aspx?id=00123">اخزا1</a></td><td>اسناد خزانه</td><td title="9,007,199,254,740,992">9 B</td><td>اوراق با درآمد ثابت</td><td>اوراق تامين مالي</td><td>اسناد خزانه اسلامي</td></tr>
<tr class="grpData"><td><a href="/Instruments.aspx?id=00456">اراد1</a></td><td>مرابحه</td><td title="1">1</td><td>اوراق با درآمد ثابت</td><td>اوراق تامين مالي</td><td>مرابحه</td></tr>
<tr class="grpHead"><td></td><td>فلزات اساسي</td><td>100 (0/01%)</td></tr>
<tr class="grpData"><td><a href="/Instruments.aspx?id=00789">فلز1</a></td><td>شرکت فلز</td><td title="100">100</td><td>بازار اول</td><td>فلزات اساسي</td><td>فولاد</td></tr>
</table></div>"""

MARKET = """<label id="lbldt">یکشنبه 17 آبان ماه ساعت 05:09:08</label>
<input type="hidden" name="__VIEWSTATE" value="state"/>
<input type="hidden" name="__EVENTVALIDATION" value="event"/>
<div id="ContentPlaceHolder1_tblContainer"><table class="tblGrp">
<tr class="grpHead"><td>بازار</td><td>تعداد نمادها</td><td>ارزش (ریال)</td><td>سهم از ارزش بازار</td></tr>
<tr><td>بازار اول</td><td title="۲">۲</td><td title="9,007,199,254,740,993">9 B</td><td title="99/99%">99/99%</td></tr>
<tr><td>بازار دوم</td><td title="1">1</td><td title="100">100</td><td title="0/01%">0/01%</td></tr>
<tr><td>مجموع بازارها</td><td title="3">3</td><td title="9,007,199,254,741,099">9 B</td><td></td></tr>
</table></div>"""

CSV_HEADER = "Date,Total Market Value,First Market,Second Market,Modern Financial Instruments Market,Paye A,Paye B,Paye J,SME\r\n"
OLD_HEADER = "Date,Total Market Value,First Market,Second Market,Modern Financial Instruments Market,Base Market(Auction),Cross Traded (Negotiation)\r\n"
EXPORTS = [
    CSV_HEADER + "1405/08/17,9007199254740993,1,2,3,4,5,6,7,\r\n1398/06/25,28,1,2,3,4,5,6,7,\r\n",
    CSV_HEADER + "1398/06/24,28,1,2,3,4,5,6,7,\r\n1396/08/15,,1,2,3,4,5,,7,\r\n1396/08/15,,1,2,3,4,5,,7,\r\n1395/12/23,,1,2,3,4,5,,7,\r\n",
    OLD_HEADER + "1395/12/22,15,1,2,3,4,5,\r\n1393/07/14,15,1,2,3,4,5,\r\n",
]


def history_page():
    headers = [
        ("grdMarketValuesAfterPayeColored", ["بازار پایه زرد", "بازار پایه نارنجی", "بازار پایه قرمز", "بازار نوآفرین"], "1405/08/17"),
        ("grdMarketValuesAfterPaye", ["بازار پایه الف", "بازار پایه ب", "بازار پایه ج", "بازار نوآفرین"], "1398/06/24"),
        ("grdMarketValues", ["بازار پایه", "بازار پایه توافقی"], "1395/12/22"),
    ]
    result = MARKET
    for grid, fields, date in headers:
        columns = ["تاریخ", "جمع ارزش بازار", "بازار اول", "بازار دوم", "ابزارهای نوین مالی"] + fields
        result += f'<table id="ContentPlaceHolder1_{grid}"><tr>' + ''.join(f'<th>{c}</th>' for c in columns) + '</tr>'
        result += f'<tr><td>{date}</td>' + '<td><span title="1">1</span></td>' * (len(columns) - 1) + '</tr></table>'
    return result


class Session:
    def __init__(self, page=INDUSTRY, exports=None):
        self.page, self.exports = page, list(exports or EXPORTS)
        self.calls, self.closed = [], False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def mount(self, *args):
        pass

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return response(self.page, "text/html; charset=utf-8")

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return response(self.exports.pop(0), "text/csv; charset=utf-8")


def response(text, content_type):
    return SimpleNamespace(text=text, content=text.encode(), headers={"Content-Type": content_type},
                           raise_for_status=lambda: None)


@pytest.fixture
def provider(monkeypatch):
    # Import here so the pre-implementation failures identify missing public API.
    import fima._ifb_market_values as module
    session = Session()
    monkeypatch.setattr(module.requests, "Session", lambda: session)
    return session


def test_public_imports():
    for name in ["get_ifb_market_values", "get_ifb_symbol_market_values", "get_ifb_market_value_history"]:
        assert callable(getattr(ifb, name))
        assert getattr(fima, name) is getattr(ifb, name)


def test_industry_counts_shares_precision_and_no_invented_date(provider):
    result = ifb.get_ifb_market_values()
    assert result.columns.tolist() == ["Industry", "MarketValue", "SymbolCount", "PercentageShare"]
    assert result.iloc[0].MarketValue == 9007199254740993
    assert result.SymbolCount.tolist() == [2, 1]
    assert result.PercentageShare.tolist() == [99.99, .01]
    assert str(result.MarketValue.dtype) == "Int64"
    assert result.attrs["Snapshot"] is True
    assert "17 آبان" in result.attrs["ProviderUpdateLabel"]
    assert "GregorianDate" not in result
    assert provider.closed


def test_market_source_totals_are_preserved(provider):
    provider.page = MARKET
    result = ifb.get_ifb_market_values("market")
    assert result.columns.tolist() == ["Market", "MarketValue", "SymbolCount", "PercentageShare"]
    assert result.MarketValue.tolist() == [9007199254740993, 100]
    assert result.attrs["TotalMarketValue"] == 9007199254741099
    assert result.attrs["TotalSymbolCount"] == 3


def test_full_constituents_identity_classification_and_filters(provider):
    full = ifb.get_ifb_symbol_market_values()
    assert full.InstrumentID.tolist() == ["00123", "00456", "00789"]
    assert str(full.InstrumentID.dtype) == "string"
    assert full.iloc[0].MarketValue == 9007199254740992
    result = ifb.get_ifb_symbol_market_values(ticker="اخزا1", market="اوراق با درآمد ثابت", industry="اوراق تامين مالي")
    assert len(result) == 1
    assert result.iloc[0].SubIndustry == "اسناد خزانه اسلامي"
    assert result.iloc[0].DetailURL == "https://ifb.ir/Instruments.aspx?id=00123"
    empty = ifb.get_ifb_symbol_market_values(ticker="missing")
    assert empty.empty and empty.columns.tolist() == full.columns.tolist()
    assert str(empty.MarketValue.dtype) == "Int64"


@pytest.mark.parametrize("change", [
    lambda x: x.replace(',2]);', ',3]);'),  # Missing constituent, never truncate.
    lambda x: x.replace('title="100"', 'title="bad"'),
    lambda x: x.replace('id=00789', 'id=00123'),
    lambda x: x.replace('فولاد</td>', 'فولاد</td><td>new field</td>'),
    lambda x: x.replace('<td>فلزات اساسي</td><td>فولاد', '<td>unknown</td><td>فولاد'),
    lambda x: x.replace("indArray.push(['فلزات اساسي ',100,1]);", "indArray.push(['bad']);"),
    lambda x: x.replace('title="100"', ''),
])
def test_industry_schema_completeness_and_identity_failures(provider, change):
    provider.page = change(INDUSTRY)
    with pytest.raises(ValueError, match="IFB"):
        ifb.get_ifb_symbol_market_values()
    assert provider.closed


def test_unrecognized_empty_page_is_failure(provider):
    provider.page = '<html>Service temporarily unavailable</html>'
    with pytest.raises(ValueError, match="IFB"):
        ifb.get_ifb_market_values()


@pytest.mark.parametrize("kwargs", [{"group_by": "sector"}, {"group_by": None}])
def test_invalid_group_before_network(provider, kwargs):
    with pytest.raises(ValueError):
        ifb.get_ifb_market_values(**kwargs)
    assert not provider.calls


def test_all_export_regimes_exact_values_missing_and_duplicates(provider):
    provider.page = history_page()
    result = ifb.get_ifb_market_value_history()
    assert len(result) == 7  # Eight provider rows; one identical duplicate normalized.
    assert result.JalaliDate.iloc[0] == "1393-07-14"
    assert result.JalaliDate.iloc[-1] == "1405-08-17"
    assert result.iloc[-1].TotalMarketValue == 9007199254740993
    assert str(result.TotalMarketValue.dtype) == "Int64"
    assert str(result.GregorianDate.dtype) == "datetime64[ns]"
    assert pd.isna(result.loc[result.JalaliDate.eq("1396-08-15"), "TotalMarketValue"]).all()
    assert pd.isna(result.iloc[-1].ABaseMarketValue)
    assert result.iloc[-1].YellowBaseMarketValue == 4
    assert result.iloc[2].ABaseMarketValue == 4
    assert result.iloc[0].AuctionBaseMarketValue == 4
    assert result.attrs["DuplicateRowCount"] == 1
    assert result.attrs["ExportRowCounts"] == {"ColoredBase": 2, "LetterBase": 4, "LegacyBase": 2}
    assert [call[0] for call in provider.calls] == ["GET", "POST", "POST", "POST"]
    for _, url, kwargs in provider.calls:
        assert url == "https://ifb.ir/DataReporter/GroupByMarket.aspx"
        assert kwargs["timeout"] == (10, 30)
        assert "verify" not in kwargs
    assert provider.calls[1][2]["data"]["__VIEWSTATE"] == "state"
    assert provider.calls[2][2]["data"]["__EVENTVALIDATION"] == "event"
    assert provider.closed


@pytest.mark.parametrize("jalali,start,end", [(True, "1405-08-17", "1405-08-17"), (False, "2026-11-08", "2026-11-08")])
def test_inclusive_date_filter_after_complete_export(provider, jalali, start, end):
    provider.page = history_page()
    result = ifb.get_ifb_market_value_history(start, end, jalali=jalali)
    assert len(result) == 1
    assert result.JalaliDate.tolist() == ["1405-08-17"]
    assert len(provider.calls) == 4


@pytest.mark.parametrize("start,end,jalali", [("1405-13-01", None, True), ("1405-01-02", "1405-01-01", True),
                                             ("bad", None, False), (None, None, "yes")])
def test_invalid_bounds_before_network(provider, start, end, jalali):
    with pytest.raises(ValueError):
        ifb.get_ifb_market_value_history(start, end, jalali=jalali)
    assert not provider.calls


@pytest.mark.parametrize("bad", [
    "<html>error</html>",
    CSV_HEADER.replace("SME", "NewUnknownColumn") + EXPORTS[0].split('\r\n', 1)[1],
    CSV_HEADER + "1405/08/17,1,2\r\n",
    EXPORTS[0].replace("9007199254740993", "nan"),
    EXPORTS[0].replace("1405/08/17", "1405/13/17"),
    EXPORTS[0] + "1405/08/17,10,1,2,3,4,5,6,7,\r\n",  # Conflicting date.
    EXPORTS[0].split('\r\n', 1)[0] + '\r\n',  # Empty export contradicts visible rows.
    EXPORTS[0].replace("1405/08/17", "1405/08/16"),  # Missing latest visible date.
    EXPORTS[0].replace(',7,\r\n', ',7,unexpected\r\n'),
])
def test_history_rejects_bad_or_incomplete_exports(provider, bad):
    provider.page = history_page()
    provider.exports[0] = bad
    with pytest.raises(ValueError, match="IFB"):
        ifb.get_ifb_market_value_history()
    assert provider.closed


def test_repeated_export_or_wrong_regime_fails(provider):
    provider.page = history_page()
    provider.exports[1] = EXPORTS[0]
    with pytest.raises(ValueError, match="IFB"):
        ifb.get_ifb_market_value_history()


def test_http_failure_propagates_and_closes(provider, monkeypatch):
    def fail(*args, **kwargs):
        raise requests.HTTPError("503 from IFB")
    monkeypatch.setattr(provider, "get", fail)
    with pytest.raises(requests.HTTPError):
        ifb.get_ifb_market_values()
    assert provider.closed


def test_empty_date_window_keeps_typed_schema(provider):
    provider.page = history_page()
    result = ifb.get_ifb_market_value_history("1406-01-01")
    assert result.empty
    assert str(result.TotalMarketValue.dtype) == "Int64"
    assert str(result.GregorianDate.dtype) == "datetime64[ns]"


def test_constituent_missing_value_preserves_other_large_integers(provider):
    provider.page = INDUSTRY.replace('title="100"', 'title="-"')
    result = ifb.get_ifb_symbol_market_values()
    assert result.iloc[0].MarketValue == 9007199254740992
    assert pd.isna(result.iloc[-1].MarketValue)


@pytest.mark.parametrize("change", [
    lambda x: x.replace('title="3"', 'title="4"'),
    lambda x: x.replace('سهم از ارزش بازار', 'new header'),
    lambda x: x.replace('<tr><td>بازار دوم', '<tr><td>بازار اول'),
    lambda x: x.replace('<td title="1">1</td>', '<td title="-">-</td>'),
    lambda x: x.replace('title="0/01%"', 'title="101%"'),
])
def test_market_missing_rows_counts_and_schema_fail(provider, change):
    provider.page = change(MARKET)
    with pytest.raises(ValueError, match="IFB"):
        ifb.get_ifb_market_values("market")


@pytest.mark.parametrize("kwargs", [{"ticker": ""}, {"market": 12}, {"industry": []}])
def test_invalid_symbol_filters_before_network(provider, kwargs):
    with pytest.raises(ValueError):
        ifb.get_ifb_symbol_market_values(**kwargs)
    assert not provider.calls


@pytest.mark.parametrize("page", [
    history_page().replace('name="__VIEWSTATE"', 'name="unknown"'),
    history_page().replace('بازار پایه زرد', 'بازار پایه الف'),
    history_page().replace('<table id="ContentPlaceHolder1_grdMarketValuesAfterPayeColored">', '<table id="unknown">'),
    history_page().replace('<table id="ContentPlaceHolder1_grdMarketValuesAfterPayeColored"><tr>', '<table id="ContentPlaceHolder1_grdMarketValuesAfterPayeColored"></table><table><tr>'),
])
def test_history_state_and_classification_failures(provider, page):
    provider.page = page
    with pytest.raises(ValueError, match="IFB"):
        ifb.get_ifb_market_value_history()
    assert provider.closed


def test_export_http_failure_after_successful_first_export(provider, monkeypatch):
    provider.page = history_page()
    post = provider.post

    def fail_second(*args, **kwargs):
        if len(provider.calls) == 2:
            raise requests.HTTPError("IFB export unavailable")
        return post(*args, **kwargs)

    monkeypatch.setattr(provider, "post", fail_second)
    with pytest.raises(requests.HTTPError):
        ifb.get_ifb_market_value_history()
    assert provider.closed
