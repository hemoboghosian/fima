"""Published fitted nodes are comparison snapshots, not invented daily history."""
from copy import deepcopy
from types import SimpleNamespace

import pandas as pd
import pytest
import requests

import fima
import fima.IFB as ifb
import fima._ifb_yields as source


PAYLOAD = [[{'Date': label, 'EnDate': english, 'DayNum': days, 'Value': value}
            for days,value in [(30,39.93909524597416),(60,None)]]
           for label,english in [('زمان فعلی','Corrent Date'),('یک ماه قبل','Last Month Date'),
                                 ('شش ماه قبلی','Last Six months Date')]]


@pytest.fixture
def provider(monkeypatch):
    state = {'data':deepcopy(PAYLOAD),'calls':[],'closed':False}

    class Session:
        def __enter__(self): return self
        def __exit__(self,*args): state['closed']=True
        def mount(self,*args): pass
        def post(self,url,**kwargs):
            state['calls'].append((url,kwargs))
            return SimpleNamespace(raise_for_status=lambda: None,json=lambda:{'d':state['data']})

    monkeypatch.setattr(source.requests,'Session',Session)
    return state


@pytest.mark.parametrize('category,method',[('treasury','GetITBtNelsonIndex'),('government','GetGovermentNelsonIndex'),
                                           ('nongovernment','GetNonGovermentNelsonIndex')])
def test_exact_source_nodes_units_labels_and_endpoint(provider,category,method):
    frame = ifb.get_ifb_yield_curve(category)
    assert fima.get_ifb_yield_curve is ifb.get_ifb_yield_curve
    assert frame.columns.tolist() == ['CurveCategory','ComparisonLabel','ComparisonEnglishLabel','TenorDays','YTM']
    assert len(frame)==6 and frame.iloc[0].YTM==39.93909524597416
    assert pd.isna(frame.iloc[1].YTM) and frame.iloc[0].TenorDays==30
    assert frame.iloc[0].ComparisonLabel=='زمان فعلی'
    assert frame.iloc[0].ComparisonEnglishLabel=='Corrent Date'
    assert frame.attrs['Snapshot'] is True and frame.attrs['TenorUnit']=='Days'
    assert 'GregorianDate' not in frame and 'SettlePrice' not in frame
    assert provider['calls']==[('https://ifb.ir/HistoricalInstrumentData.asmx/'+method,
                              {'headers':{'Content-Type':'application/json; charset=utf-8'},'timeout':(10,30)})]
    assert provider['closed']


@pytest.mark.parametrize('category',['all',None,1])
def test_invalid_category_before_network(provider,category):
    with pytest.raises(ValueError): ifb.get_ifb_yield_curve(category)
    assert not provider['calls']


def test_valid_empty_envelope_has_typed_schema(provider):
    provider['data']=[]
    frame=ifb.get_ifb_yield_curve()
    assert frame.empty and str(frame.TenorDays.dtype)=='Int64'
    assert pd.api.types.is_numeric_dtype(frame.YTM)


@pytest.mark.parametrize('change',[
    lambda p:p.pop(), lambda p:p.__setitem__(0,[]), lambda p:p[0][0].pop('Value'),
    lambda p:p[0][0].__setitem__('DayNum',0), lambda p:p[0][0].__setitem__('DayNum',30.5),
    lambda p:p[0][0].__setitem__('Value',float('inf')), lambda p:p[0].append(p[0][0]),
    lambda p:p[0][1].__setitem__('Date','different'), lambda p:p.__setitem__(1,p[0]),
    lambda p:p[0][0].__setitem__('Value','bad'),
])
def test_changed_or_incomplete_curve_is_an_error(provider,change):
    change(provider['data'])
    with pytest.raises(ValueError,match='IFB'): ifb.get_ifb_yield_curve()
    assert provider['closed']


def test_negative_published_yield_is_not_clamped(provider):
    provider['data'][0][0]['Value']=-2.5
    assert ifb.get_ifb_yield_curve().iloc[0].YTM==-2.5


@pytest.mark.parametrize('error',[requests.Timeout('timeout'),requests.HTTPError('403'),ValueError('bad JSON')])
def test_transport_and_json_failures(provider,monkeypatch,error):
    def fail(*args,**kwargs): raise error
    monkeypatch.setattr(source.requests.Session,'post',fail)
    with pytest.raises(type(error)): ifb.get_ifb_yield_curve()


@pytest.mark.parametrize('payload',[None,{}, {'d':None}, {'d':'invalid'}])
def test_invalid_envelope_is_not_an_empty_success(provider,monkeypatch,payload):
    monkeypatch.setattr(source.requests.Session,'post',lambda *a,**k:
                        SimpleNamespace(raise_for_status=lambda:None,json=lambda:payload))
    with pytest.raises(ValueError,match='IFB'): ifb.get_ifb_yield_curve()


def test_invalid_json_has_provider_context(provider,monkeypatch):
    def invalid(): raise ValueError('unexpected token')
    monkeypatch.setattr(source.requests.Session,'post',lambda *a,**k:
                        SimpleNamespace(raise_for_status=lambda:None,json=invalid))
    with pytest.raises(ValueError,match='IFB.*JSON'): ifb.get_ifb_yield_curve()
    assert provider['closed']
