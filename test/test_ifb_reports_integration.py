"""Opt-in exact comparisons with every page in an official filtered catalog."""
import re

from bs4 import BeautifulSoup
import pandas as pd
import pytest

import fima.IFB as ifb
import fima._ifb_reports as source


pytestmark = pytest.mark.integration


@pytest.mark.parametrize('start,end,kwargs',[
    ('1405-07-01','1405-08-17',{}),
    ('1300-01-01','1405-08-17',{'reporting_period':'annual'}),
    ('1405-08-17','1405-08-17',{}),
])
def test_live_every_report_id_date_and_visible_format(monkeypatch,start,end,kwargs):
    factory=source._session
    responses=[]

    def capture():
        session=factory()
        request=session.request

        def record(method,url,**kw):
            response=request(method,url,**kw)
            if method.upper()=='POST': responses.append(response.content)
            return response

        monkeypatch.setattr(session,'request',record)
        return session

    monkeypatch.setattr(source,'_session',capture)
    frame=ifb.get_ifb_periodical_reports(start,end,**kwargs)
    assert len(responses)%2==0
    expected=[]
    for body in responses[:len(responses)//2]:
        soup=BeautifulSoup(body,'html.parser')
        for row in soup.select('#ContentPlaceHolder1_grdPRs > tr'):
            cells=row.find_all('td',recursive=False)
            if len(cells)!=8: continue
            visible=[a['href'] for a in cells[-1].select('a[href]') if not re.search(r'display\s*:\s*none',a.get('style',''))]
            ids={re.search(r'id=([0-9]+)',url)[1] for url in visible}
            assert len(ids)==1
            expected.append((ids.pop(),cells[3].get_text(strip=True).replace('/','-'),
                             cells[5].get_text(strip=True).replace('/','-'),
                             any('type=Excel&' in url for url in visible),any('type=PDF&' in url for url in visible)))
    actual=[(r.ReportID,r.PeriodEndJalaliDate,r.UploadJalaliDate,pd.notna(r.ExcelURL),pd.notna(r.PDFURL))
            for r in frame.itertuples(index=False)]
    assert actual==expected
    assert len(frame)==frame.ReportID.nunique()==frame.attrs['RecordCount']
    assert len(responses)==2*max(1,frame.attrs['PageCount'])
