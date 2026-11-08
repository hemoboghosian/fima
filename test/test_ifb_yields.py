"""Source-shaped historical yield fixtures; no external requests."""
from collections import deque
from types import SimpleNamespace

import pandas as pd
import pytest
import requests

import fima
import fima.IFB as ifb


P = 'ctl00$ContentPlaceHolder1$'
GRID_HEADER = ['ردیف', 'نماد', 'تاریخ آخرین روز معاملاتی', 'تاریخ انتشار', 'تاریخ سررسید', 'قبمت پایانی', 'حجم', 'YTM']
EXPORT_HEADER = ['نام نماد', 'تاریخ آخرین معامله', 'تاریخ انتشار', 'تاریخ سررسید', 'قیمت پایانی', 'حجم', 'YTM']
ROW = ['اخزا204', '1405-08-16', '1402-08-15', '1405-10-21', '937,500', '1', '43.68%']
OLD = ['اخزا204', '1405-08-12', '1402-08-15', '1405-10-21', '940,460', '400,031', '38.37%']


def page(rows=None, *, empty=False, error='', state='initial', more=False):
    result = f'<input type="hidden" name="__VIEWSTATE" value="{state}"><input type="hidden" name="__VIEWSTATEGENERATOR" value="gen">'
    result += f'<input type="text" name="{P}TxtDateFrom" value="1405/08/01"><input type="text" name="{P}TxtDateTo" value="1405/08/17">'
    result += f'<select name="{P}SymbolComboboxYTMHistory" id="ContentPlaceHolder1_SymbolComboboxYTMHistory">'
    result += '<option value="-1">همه</option><option selected value="0033029">اخزا204</option><option value="33136">اراد157</option><option value="33302">اراد157</option></select>'
    result += f'<span id="ContentPlaceHolder1_lblerror">{error}</span><table id="ContentPlaceHolder1_ytmHistoryGride">'
    if empty:
        return result + '<tr><td colspan="8">.داده ای یافت نشد</td></tr></table>'
    result += '<tr>' + ''.join(f'<th>{h}</th>' for h in GRID_HEADER) + '</tr>'
    for i, row in enumerate(rows if rows is not None else [ROW], 1):
        result += f'<tr><td>{i}</td><td><a href="InstrumentsMFI.aspx?id=0033029" symbolid_fk="0033029">{row[0]}</a></td>'
        result += ''.join(f'<td>{v}</td>' for v in row[1:]) + '</tr>'
    if more:
        result += f'<tr class="pgr"><td colspan="8"><a href="javascript:__doPostBack(\'{P}ytmHistoryGride\',\'Page$2\')">2</a></td></tr>'
    return result + '</table>'


def export(rows=None):
    rows = rows if rows is not None else [ROW, OLD]
    return '<table><tr>' + ''.join(f'<td>{h}</td>' for h in EXPORT_HEADER) + '</tr>' + ''.join(
        '<tr>' + ''.join(f'<td>{v}</td>' for v in row) + '</tr>' for row in rows) + '</table>'


class Session:
    def __init__(self):
        self.responses = deque([response(page()), response(page(state='filtered', more=True)), response(export(), True)])
        self.calls, self.closed = [], False

    def __enter__(self): return self
    def __exit__(self, *args): self.closed = True
    def mount(self, *args): pass
    def get(self, url, **kwargs):
        self.calls.append(('GET', url, kwargs)); return self.responses.popleft()
    def post(self, url, **kwargs):
        self.calls.append(('POST', url, kwargs)); return self.responses.popleft()


def response(text, download=False):
    return SimpleNamespace(content=text.encode(), headers={'Content-Type': 'application/vnd.ms-excel; charset=utf-8' if download else 'text/html'},
                           raise_for_status=lambda: None)


@pytest.fixture
def provider(monkeypatch):
    import fima._ifb_yields as module
    session = Session()
    monkeypatch.setattr(module.requests, 'Session', lambda: session)
    return session


def history(**kwargs):
    return ifb.get_ifb_bond_yield_history('1405-08-01', '1405-08-17', ticker='اخزا204', **kwargs)


def test_public_export_and_existing_signatures():
    import inspect
    assert fima.get_ifb_bond_yield_history is ifb.get_ifb_bond_yield_history
    assert str(inspect.signature(ifb.get_risk_free_rate)) == '() -> float'
    for fn in [ifb.get_all_bonds_without_coupons, ifb.get_all_bonds_with_coupons]:
        assert list(inspect.signature(fn).parameters) == ['deprecated']


def test_complete_export_identity_financial_mapping_and_dates(provider):
    frame = history()
    assert len(frame) == 2 and frame.iloc[-1].InstrumentID == '0033029'
    assert str(frame.InstrumentID.dtype) == 'string'
    assert frame.LastTradeJalaliDate.tolist() == ['1405-08-12', '1405-08-16']
    assert frame.iloc[-1].LastTradeGregorianDate == pd.Timestamp('2026-11-07')
    assert frame.iloc[-1].ClosingPrice == 937500
    assert frame.iloc[-1].TradeVolume == 1
    assert frame.iloc[-1].YTM == 43.68
    assert frame.iloc[-1].IssueJalaliDate == '1402-08-15'
    assert frame.iloc[-1].MaturityJalaliDate == '1405-10-21'
    assert not frame.HasConflictingObservation.any()
    assert frame.attrs['ExportRowCount'] == 2
    assert provider.closed
    assert [x[0] for x in provider.calls] == ['GET', 'POST', 'POST']
    assert provider.calls[1][2]['data'][P+'SymbolComboboxYTMHistory'] == '0033029'
    assert provider.calls[2][2]['data']['__VIEWSTATE'] == 'filtered'
    assert P+'Button1' not in provider.calls[2][2]['data']
    for _, url, kwargs in provider.calls:
        assert url == 'https://ifb.ir/YTM.aspx'
        assert kwargs['timeout'] == (10, 30) and 'verify' not in kwargs


def test_id_selection_and_gregorian_bounds(provider):
    frame = ifb.get_ifb_bond_yield_history('2026-10-23', '2026-11-08', instrument_id='0033029', jalali=False)
    assert len(frame) == 2
    assert provider.calls[1][2]['data'][P+'TxtDateFrom'] == '1405/08/01'


@pytest.mark.parametrize('kwargs', [dict(ticker='missing'), dict(ticker='اراد157'), dict(instrument_id='33029'),
                                  dict(ticker='wrong', instrument_id='0033029')])
def test_unknown_or_ambiguous_identity_does_not_export(provider, kwargs):
    with pytest.raises(ValueError, match='IFB'):
        ifb.get_ifb_bond_yield_history('1405-08-01', '1405-08-17', **kwargs)
    assert len(provider.calls) == 1


@pytest.mark.parametrize('start,end,kwargs', [
    ('1405-13-01','1405-08-17',dict(ticker='x')), ('1405-08-18','1405-08-17',dict(ticker='x')),
    (None,'1405-08-17',dict(ticker='x')), ('1405-08-01','1405-08-17',{}),
    ('1405-08-01','1405-08-17',dict(ticker='x',on_conflict='first')),
    ('1405-08-01','1405-08-17',dict(ticker='x',jalali='yes')),
])
def test_bad_inputs_before_network(provider, start, end, kwargs):
    with pytest.raises(ValueError): ifb.get_ifb_bond_yield_history(start,end,**kwargs)
    assert not provider.calls


def test_valid_empty_filters_close_without_export(provider):
    provider.responses[1] = response(page(empty=True, state='filtered'))
    result = history()
    assert result.empty and len(provider.calls) == 2
    assert str(result.LastTradeGregorianDate.dtype) == 'datetime64[ns]'
    assert str(result.TradeVolume.dtype) == 'Int64'
    assert pd.api.types.is_numeric_dtype(result.YTM)


@pytest.mark.parametrize('html', [page(error='فرمت تاریخ درست نیست'), '<html>server error</html>',
    page().replace('symbolid_fk="0033029"','symbolid_fk="999"'),
    page().replace('1405-08-16','1405-07-30'),
    page().replace('قبمت پایانی','unknown field')])
def test_bad_filtered_page_is_not_empty(provider, html):
    provider.responses[1] = response(html)
    with pytest.raises(ValueError, match='IFB'): history()
    assert provider.closed


@pytest.mark.parametrize('html', [export().replace('</table>',''), export().replace('<td>YTM</td>','<td>other</td>'),
    export().replace('<td>43.68%</td>',''), export().replace('اخزا204','OTHER'),
    export([OLD]), export([ROW]), export().replace('937,500','bad'),
    export().replace('937,500','inf'), export().replace('<td>1</td>','<td>1.5</td>'),
    export().replace('1405-08-12','1405-13-12'), '<html>error</html>'])
def test_export_schema_truncation_filter_and_completeness(provider, html):
    provider.responses[2] = response(html, True)
    with pytest.raises(ValueError, match='IFB'): history()
    assert provider.closed


def test_duplicates_and_conflicting_observations(provider):
    conflict = ROW.copy(); conflict[4], conflict[6] = '938,000', '43.50%'
    provider.responses[2] = response(export([ROW, ROW, conflict, OLD]), True)
    with pytest.raises(ValueError, match='conflicting'): history()


def test_explicit_preserve_mode_flags_conflicts_and_reports_repeats(provider):
    conflict = ROW.copy(); conflict[6] = '43.50%'
    provider.responses[2] = response(export([ROW, ROW, conflict, OLD]), True)
    frame = history(on_conflict='preserve')
    assert len(frame) == 3 and frame.HasConflictingObservation.tolist() == [False,True,True]
    assert frame.attrs['DuplicateRowCount'] == 1
    assert frame.attrs['ConflictingDates'] == ['1405-08-16']


def test_missing_financials_negative_published_yield_and_zero_volume(provider):
    missing = OLD.copy(); missing[4:] = ['-', '0', '-3,446.12%']
    provider.responses[2] = response(export([ROW,missing]), True)
    frame = history()
    assert pd.isna(frame.iloc[0].ClosingPrice)
    assert frame.iloc[0].TradeVolume == 0 and frame.iloc[0].YTM == -3446.12


@pytest.mark.parametrize('stage,error', [('get',requests.Timeout('IFB timeout')), ('post',requests.HTTPError('503 IFB'))])
def test_transport_errors_propagate(provider, monkeypatch, stage, error):
    def fail(*args,**kwargs): raise error
    monkeypatch.setattr(provider,stage,fail)
    with pytest.raises(type(error)): history()
    assert provider.closed


def test_documented_financial_reference_cases():
    # Independently verified IFB face values, dates and cash flows. This checks
    # the meaning/scale, not a fima pricing implementation (there is none here).
    import jdatetime as jd
    from scipy.optimize import brentq
    days = (jd.date(1405,10,21)-jd.date(1405,8,16)).days
    assert round(((1_000_000/937_500)**(365/days)-1)*100,2) == 43.68
    flows = [(547,58602.74),(547,1_000_000),(454,56082.19),(365,56712.33),
             (275,58602.74),(182,58602.74),(89,56082.19)]
    rate = brentq(lambda r: sum(a/(1+r)**(t/365) for t,a in flows)-864000,0,1)
    assert round(rate*100,2) == 39.93 and round(rate*100,2) != 23


def test_no_import_time_requests():
    import subprocess
    import sys
    code = "import requests; requests.sessions.Session.request=lambda *a,**k: (_ for _ in ()).throw(AssertionError('HTTP at import')); import fima; assert callable(fima.get_ifb_bond_yield_history)"
    subprocess.run([sys.executable,'-c',code],check=True,timeout=30)
