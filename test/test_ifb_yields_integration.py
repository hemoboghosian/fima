"""Opt-in official export comparisons and financial reference cases."""
from collections import Counter

from bs4 import BeautifulSoup
import pandas as pd
import pytest

import fima.IFB as ifb
import fima._ifb_yields as source


pytestmark = pytest.mark.integration


@pytest.mark.parametrize('instrument_id,start', [('33029','1402-01-01'), ('40578','1300-01-01')])
def test_live_selected_complete_export(monkeypatch, instrument_id, start):
    factory = source._session
    responses = []

    def capture():
        session = factory()
        request = session.request

        def record(method, url, **kwargs):
            response = request(method,url,**kwargs)
            responses.append(response)
            return response

        monkeypatch.setattr(session,'request',record)
        return session

    monkeypatch.setattr(source,'_session',capture)
    result = ifb.get_ifb_bond_yield_history(start,'1405-08-17',instrument_id=instrument_id,on_conflict='preserve')
    assert not result.empty and len(responses) == 3
    rows = [[c.get_text(strip=True) for c in tr.find_all('td',recursive=False)]
            for tr in BeautifulSoup(responses[-1].content,'html.parser').select('tr')][1:]
    assert result.attrs['ExportRowCount'] == len(rows)
    assert len(result) == len({tuple(row) for row in rows})
    expected = Counter((r[1], float(r[4].replace(',','')), int(r[5].replace(',','')), float(r[6].replace('%','').replace(',',''))) for r in rows)
    parsed = Counter((r.LastTradeJalaliDate,r.ClosingPrice,r.TradeVolume,r.YTM) for r in result.itertuples(index=False))
    assert set(parsed) == set(expected)
    assert result.InstrumentID.eq(instrument_id).all()
    assert result.LastTradeGregorianDate.is_monotonic_increasing


def test_live_valid_empty_history():
    frame = ifb.get_ifb_bond_yield_history('1403-01-01','1403-01-02',instrument_id='33029')
    assert frame.empty
    assert str(frame.TradeVolume.dtype) == 'Int64'
    assert frame.attrs['ExportRowCount'] == 0


def test_live_default_conflict_error():
    with pytest.raises(ValueError,match='conflicting'):
        ifb.get_ifb_bond_yield_history('1403-11-23','1403-11-23',instrument_id='33029')


@pytest.mark.parametrize('category',['treasury','government','nongovernment'])
def test_live_fitted_curve_exact_official_nodes(monkeypatch,category):
    factory=source._session
    payloads=[]

    def capture():
        session=factory()
        post=session.post

        def record(*args,**kwargs):
            response=post(*args,**kwargs)
            payloads.append(response.json()['d'])
            return response

        monkeypatch.setattr(session,'post',record)
        return session

    monkeypatch.setattr(source,'_session',capture)
    frame=ifb.get_ifb_yield_curve(category)
    rows=[row for series in payloads[0] for row in series]
    assert len(frame)==len(rows)>0
    for parsed,raw in zip(frame.itertuples(index=False),rows):
        assert (parsed.ComparisonLabel,parsed.ComparisonEnglishLabel,parsed.TenorDays,parsed.YTM)==(
            raw['Date'],raw['EnDate'],raw['DayNum'],raw['Value'])
