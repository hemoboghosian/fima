"""Small source-shaped WebForms fixtures, without real reports or network I/O."""
from collections import deque
from html import escape
from types import SimpleNamespace
import inspect

import pandas as pd
import pytest
import requests

import fima
import fima.IFB as ifb


P = 'ctl00$ContentPlaceHolder1$'
HEADERS = ['ردیف','نوع گزارش','دوره گزارش','منتهی به','به تفکیک','تاریخ بارگزاری','توضیحات','فایل']
TYPES = [('0','همه'),('1','آمار معاملات'),('2','گزارش آماری توصیفی'),('5','رتبه‌بندی')]
PERIODS = [('0','همه'),('10','روزانه'),('20','هفتگی'),('30','ماهانه'),('40','سالانه')]
BREAKDOWNS = ['بازار','صنعت','نماد','حقیقی و حقوقی','خرید و فروش','برخط و ایستگاه','کارگزاری']


def page(ids=('0001',), *, current=1, pages=1, empty=False, state='state',
         report_type='0', period='0', title='', breakdown=None, upload='1405/08/17'):
    html=f'<input type="hidden" name="__VIEWSTATE" value="{state}"><input type="hidden" name="__VIEWSTATEGENERATOR" value="gen">'
    for name,value in [('FromDT','1405/08/01'),('ToDT','1405/08/17'),('txtTitle',title)]:
        html+=f'<input type="text" name="{P+name}" value="{escape(value)}">'
    for name,options,selected in [('comboReportType',TYPES,report_type),('comboReportPeriod',PERIODS,period)]:
        html+=f'<select name="{P+name}">'+''.join(f'<option value="{v}" '+('selected' if v==selected else '')+f'>{n}</option>' for v,n in options)+'</select>'
    for i,label in enumerate(BREAKDOWNS):
        html+=f'<input type="checkbox" id="b{i}" name="{P}TafkikCheckboxlist${i}" value="{2**i}" '+('checked' if breakdown==i else '')+f'><label for="b{i}">{label}</label>'
    html+='<span id="ContentPlaceHolder1_Label3"></span><table id="ContentPlaceHolder1_grdPRs">'
    if empty:
        return html+'<tr><td colspan="8">.داده ای یافت نشد</td></tr></table>'
    html+='<tr>'+''.join(f'<th>{h}</th>' for h in HEADERS)+'</tr>'
    for i,rid in enumerate(ids,1):
        html+=f'<tr><td>{(current-1)*50+i}</td><td>آمار معاملات</td><td>روزانه</td><td>1405/08/16</td><td>نماد، بازار</td><td>{upload}</td><td>Same title</td><td>'
        for fmt in ('PDF','Word','Excel'):
            html+=f'<a style="display: '+('none' if fmt=='Word' else '')+f'" href="/GetFiles/GetPeriodicalFile.aspx?id={rid}&amp;type={fmt}&amp;EnData=False">file</a>'
        html+='</td></tr>'
    html+='<tr class="pgr"><td colspan="8"><table><tr>'
    for n in range(1,pages+1):
        html+='<td>'+(f'<span>{n}</span>' if n==current else f'<a href="javascript:__doPostBack(\'{P}grdPRs\',\'Page${n}\')">{n}</a>')+'</td>'
    html+=f'</tr></table><div class="sizeselector"><select name="{P}grdPRs$ctl53$ctl{pages+2:02d}"><option value="10">10</option><option value="25">25</option><option selected value="50">50</option></select></div></td></tr></table>'
    return html


def response(html):
    return SimpleNamespace(content=html.encode(),headers={'Content-Type':'text/html; charset=utf-8'},raise_for_status=lambda:None)


@pytest.fixture
def provider(monkeypatch):
    import fima._ifb_reports as module
    class Session:
        def __init__(self):
            self.responses=deque([response(page()),response(page()),response(page())])
            self.calls=[];self.closed=False
        def __enter__(self): return self
        def __exit__(self,*args): self.closed=True
        def mount(self,*args): pass
        def get(self,url,**kwargs): self.calls.append(('GET',url,kwargs));return self.responses.popleft()
        def post(self,url,**kwargs): self.calls.append(('POST',url,kwargs));return self.responses.popleft()
    session=Session()
    monkeypatch.setattr(module.requests,'Session',lambda:session)
    monkeypatch.setattr(module.time,'sleep',lambda _:None)
    return session


def catalog(**kwargs):
    return ifb.get_ifb_periodical_reports('1405-08-01','1405-08-17',**kwargs)


def test_public_contract_and_existing_apis():
    assert fima.get_ifb_periodical_reports is ifb.get_ifb_periodical_reports
    assert list(inspect.signature(ifb.get_ifb_periodical_reports).parameters)==[
        'start_date','end_date','report_type','reporting_period','title','breakdown','jalali','max_pages']
    assert str(inspect.signature(ifb.get_risk_free_rate))=='() -> float'
    assert callable(fima.get_ifb_bond_yield_history) and callable(fima.get_ifb_yield_curve)


def test_identity_dates_typed_schema_urls_and_two_passes(provider):
    frame=catalog()
    assert frame.columns.tolist()==['ReportID','Title','ReportType','ReportingPeriod','PeriodEndJalaliDate',
        'PeriodEndGregorianDate','Breakdown','UploadJalaliDate','UploadGregorianDate','ExcelURL','PDFURL']
    row=frame.iloc[0]
    assert row.ReportID=='0001' and str(frame.ReportID.dtype)=='string'
    assert row.PeriodEndJalaliDate=='1405-08-16' and row.UploadJalaliDate=='1405-08-17'
    assert row.PeriodEndGregorianDate==pd.Timestamp('2026-11-07') and row.UploadGregorianDate==pd.Timestamp('2026-11-08')
    assert row.ExcelURL=='https://ifb.ir/GetFiles/GetPeriodicalFile.aspx?id=0001&type=Excel&EnData=False'
    assert row.Title=='Same title' and 'WordURL' not in frame and 'PeriodStartJalaliDate' not in frame
    assert frame.attrs['PageCount']==1 and frame.attrs['RecordCount']==1 and frame.attrs['ValidationPasses']==2
    assert provider.closed and len(provider.calls)==3
    assert all(c[2]['timeout']==(30,30) and 'verify' not in c[2] for c in provider.calls)


def test_complete_paging_filters_hidden_state_and_revisions(provider):
    ids=tuple(f'{i:04d}' for i in range(1,51))
    first=page(ids,current=1,pages=2,state='first')
    last=page(('0051',),current=2,pages=2,state='last')
    provider.responses=deque([response(page()),response(first),response(last),response(first),response(last)])
    frame=catalog()
    assert frame.ReportID.tolist()==list(ids)+['0051'] and frame.Title.nunique()==1
    assert frame.attrs['PageCount']==2 and frame.attrs['RecordCount']==51
    post=provider.calls[2][2]['data']
    assert post['__VIEWSTATE']=='first' and post['__EVENTTARGET']==P+'grdPRs' and post['__EVENTARGUMENT']=='Page$2'
    assert P+'BtnSearch' not in post and post[P+'FromDT']=='1405/08/01'
    assert provider.calls[3][2]['data']['__VIEWSTATE']=='last'


@pytest.mark.parametrize('kwargs,field,value,html',[
    ({'report_type':'trading'},'comboReportType','1',page(report_type='1')),
    ({'reporting_period':'daily'},'comboReportPeriod','10',page(period='10')),
    ({'title':'Same'},'txtTitle','Same',page(title='Same')),
    ({'breakdown':'market'},'TafkikCheckboxlist$0','1',page(breakdown=0)),
], ids=['trading','daily','title','market'])
def test_source_filters(provider,kwargs,field,value,html):
    provider.responses[1]=response(html);provider.responses[2]=response(html)
    assert len(catalog(**kwargs))==1
    assert provider.calls[1][2]['data'][P+field]==value


def test_gregorian_input(provider):
    assert len(ifb.get_ifb_periodical_reports('2026-10-23','2026-11-08',jalali=False))==1
    assert provider.calls[1][2]['data'][P+'FromDT']=='1405/08/01'


@pytest.mark.parametrize('kwargs',[{'report_type':'other'},{'reporting_period':'quarterly'}, {'breakdown':['market']},
    {'title':''},{'title':'x'*41},{'title':1},{'jalali':'yes'},{'max_pages':0},{'max_pages':101},{'max_pages':True}])
def test_invalid_selectors_before_network(provider,kwargs):
    with pytest.raises(ValueError): catalog(**kwargs)
    assert not provider.calls


@pytest.mark.parametrize('start,end',[(None,'1405-08-17'),('1405-08-01',None),('1405-13-01','1405-08-17'),('1405-08-18','1405-08-17')])
def test_required_valid_date_bounds(provider,start,end):
    with pytest.raises(ValueError): ifb.get_ifb_periodical_reports(start,end)
    assert not provider.calls


def test_valid_empty_search_requires_matching_second_pass(provider):
    provider.responses[1]=response(page(empty=True));provider.responses[2]=response(page(empty=True))
    frame=catalog()
    assert frame.empty and str(frame.ReportID.dtype)=='string'
    assert str(frame.PeriodEndGregorianDate.dtype)=='datetime64[ns]' and frame.attrs['RecordCount']==0
    assert provider.closed and len(provider.calls)==3


@pytest.mark.parametrize('html',[
    '<html>blocked</html>',page().replace('__VIEWSTATE','MISSING'),page().replace('تاریخ بارگزاری','changed'),
    page().replace('<span id="ContentPlaceHolder1_Label3"></span>','<span id="ContentPlaceHolder1_Label3">bad date</span>'),
    page().replace('1405/08/16','1405/13/16'),page().replace('1405/08/16','1405/07/16'),
    page().replace('1405/08/01','1405/07/01'),page().replace('id=0001&amp;type=Excel','id=9999&amp;type=Excel'),
    page().replace('/GetFiles/GetPeriodicalFile.aspx','https://example.com/GetFiles/GetPeriodicalFile.aspx'),
    page().replace('<span>1</span>','<span>2</span>'),page().replace('<td>1</td>','<td>2</td>',1),
    page().replace('type=Excel','type=Other'),
], ids=['blocked','state','header','filter-error','invalid-date','outside-window','lost-filter',
        'conflicting-id','foreign-url','wrong-page','wrong-row','unknown-format'])
def test_bad_page_is_not_empty_success(provider,html):
    provider.responses[1]=response(html)
    with pytest.raises(ValueError,match='IFB'): catalog()
    assert provider.closed


def test_duplicate_ids_not_silently_dropped(provider):
    provider.responses[1]=response(page(('0001','0001')))
    with pytest.raises(ValueError,match='IFB'): catalog()


@pytest.mark.parametrize('last',[
    page(tuple(f'{i:04d}' for i in range(1,51)),pages=2),
    page(('0051',),current=2,pages=3),
    page(('0001',),current=2,pages=2),
    page(empty=True),
], ids=['repeated','page-count-change','duplicate-id','missing-page'])
def test_repeated_changed_or_missing_page_fails(provider,last):
    first=page(tuple(f'{i:04d}' for i in range(1,51)),pages=2)
    provider.responses=deque([response(page()),response(first),response(last)])
    with pytest.raises(ValueError,match='IFB'): catalog()


def test_page_limit_raises_instead_of_returning_partial(provider):
    provider.responses[1]=response(page(tuple(f'{i:04d}' for i in range(1,51)),pages=2))
    with pytest.raises(ValueError,match='IFB.*limit'): catalog(max_pages=1)


def test_catalog_change_between_passes_is_an_error(provider):
    provider.responses[2]=response(page(('0002',)))
    with pytest.raises(ValueError,match='IFB.*chang'): catalog()


def test_upload_can_precede_period_end_and_missing_urls_stay_missing(provider):
    html=page(upload='1405/08/15').replace('style="display: " href="/GetFiles/GetPeriodicalFile.aspx?id=0001&amp;type=Excel','style="display: none" href="/GetFiles/GetPeriodicalFile.aspx?id=0001&amp;type=Excel')
    provider.responses[1]=response(html);provider.responses[2]=response(html)
    row=catalog().iloc[0]
    assert row.UploadJalaliDate=='1405-08-15' and pd.isna(row.ExcelURL)


@pytest.mark.parametrize('method,error',[('get',requests.Timeout('timeout')),('post',requests.HTTPError('403'))])
def test_transport_failures_propagate_and_close(provider,monkeypatch,method,error):
    def fail(*args,**kwargs): raise error
    monkeypatch.setattr(provider,method,fail)
    with pytest.raises(type(error)): catalog()
    assert provider.closed


def test_changed_format_availability_between_passes(provider):
    provider.responses[2]=response(page().replace('type=Excel','type=PDF'))
    with pytest.raises(ValueError,match='IFB'): catalog()


@pytest.mark.parametrize('change',[
    lambda s:s.replace('Same title',''),
    lambda s:s.replace('1405/08/17</td>','</td>'),
    lambda s:s.replace('>آمار معاملات</td>','>unknown</td>'),
    lambda s:s.replace('>نماد، بازار</td>','></td>'),
    lambda s:s.replace('>صنعت</label>','>other</label>'),
])
def test_required_source_metadata_changes_are_errors(provider,change):
    provider.responses[1]=response(change(page()))
    with pytest.raises(ValueError,match='IFB'): catalog()


def test_missing_format_change_is_reported_as_catalog_change(provider):
    provider.responses[2]=response(page().replace('type=Excel','type=Word').replace('style="display: " href="/GetFiles/GetPeriodicalFile.aspx?id=0001&amp;type=Word','style="display: none" href="/GetFiles/GetPeriodicalFile.aspx?id=0001&amp;type=Word'))
    with pytest.raises(ValueError,match='IFB.*chang'): catalog()


def test_no_import_time_network():
    import subprocess,sys
    script="from unittest.mock import patch; guard=patch('requests.sessions.Session.request',side_effect=AssertionError('HTTP at import')); guard.start(); import fima; assert callable(fima.get_ifb_periodical_reports)"
    subprocess.run([sys.executable,'-c',script],check=True,timeout=30)


def test_pagination_crosses_a_numbered_block_boundary(provider):
    import re
    pages=[]
    for n in range(1,12):
        ids=tuple(str(i) for i in range((n-1)*50+1,n*50+1)) if n<11 else ('501',)
        html=page(ids,current=n,pages=11)
        if n<11:
            html=html.replace("Page$11')\">11</a>","Page$11')\">...</a>")
        else:
            for previous in range(1,10):
                html=re.sub(r'<td><a[^>]+Page\$'+str(previous)+r"'\)[^>]*>"+str(previous)+r'</a></td>','',html)
            html=html.replace("Page$10')\">10</a>","Page$10')\">...</a>")
        pages.append(response(html))
    provider.responses=deque([response(page()),*pages,*pages])
    frame=catalog()
    assert len(frame)==501 and frame.attrs['PageCount']==11


def test_filter_replaced_by_an_input_is_a_schema_error(provider):
    import re
    provider.responses[0]=response(re.sub(r'<select name="'+re.escape(P)+r'comboReportType">.*?</select>',
        f'<input type="text" name="{P}comboReportType" value="0">',page()))
    with pytest.raises(ValueError,match='IFB.*selector'): catalog()
    assert provider.closed
