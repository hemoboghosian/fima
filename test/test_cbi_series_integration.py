"""Opt-in source comparisons; only the specifically recognized rejection skips."""
import json
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import pandas as pd
import pytest
import requests

import fima.CBI as CBI

pytestmark = pytest.mark.integration
DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789')


def live(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except RuntimeError as exc:
        if isinstance(exc.__cause__, ValueError) and str(exc.__cause__) == CBI._ACCESS_ERROR:
            pytest.skip(str(exc))
        raise


def source_page(response):
    try:
        return CBI._page(response)
    except ValueError as exc:
        if str(exc) == CBI._ACCESS_ERROR:
            pytest.skip(str(exc))
        raise


def test_live_inflation_monthly_complete_years_and_values(monkeypatch):
    captured = {}
    original = CBI._inflation_table

    def capture(soup, frequency, year=None):
        captured[year] = soup
        return original(soup, frequency, year)

    monkeypatch.setattr(CBI, '_inflation_table', capture)
    result = live(CBI.get_cbi_inflation_rates)
    first = next(iter(captured.values()))
    advertised = {o['value'].translate(DIGITS) for o in first.find('select').find_all('option')}
    assert set(captured) == advertised
    assert list(result.columns) == ['JalaliMonth','InflationRate']
    assert [str(d) for d in result.dtypes] == ['string','float64']
    assert result.JalaliMonth.is_monotonic_increasing and not result.duplicated().any()
    months = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند']
    raw_count = 0
    for year,soup in captured.items():
        table = next(t for t in soup.find_all('table') if t.find('tr').get_text(' ',strip=True) == 'ماه نرخ تورم')
        rows = table.find_all('tr')[1:]
        raw_count += len(rows)
        for row in rows:
            month,rate = [c.get_text(strip=True) for c in row.find_all('td')]
            period = f'{year}-{months.index(month)+1:02d}'
            actual = result.loc[result.JalaliMonth == period,'InflationRate']
            assert len(actual) == 1 and actual.iloc[0] == float(rate.translate(DIGITS))
    assert len(result) <= raw_count
    print(json.dumps({'InflationYears':sorted(advertised),'MonthlyRows':len(result),
                      'EarliestMonth':result.JalaliMonth.min(),'LatestMonth':result.JalaliMonth.max()}))


def test_live_annual_inflation_notes_and_values(monkeypatch):
    captured = []
    original = CBI._inflation_table

    def capture(soup,*args,**kwargs):
        captured.append(soup)
        return original(soup,*args,**kwargs)

    monkeypatch.setattr(CBI,'_inflation_table',capture)
    result = live(CBI.get_cbi_inflation_rates,'annual')
    assert result.JalaliYear.is_monotonic_increasing
    assert [str(d) for d in result.dtypes] == ['string','float64','string']
    table = next(t for t in captured[0].find_all('table') if t.find('tr').get_text(' ',strip=True) == 'سال نرخ تورم')
    for row in table.find_all('tr')[1:]:
        raw_year,rate = [c.get_text(strip=True).translate(DIGITS) for c in row.find_all('td')]
        year = raw_year[:4]
        actual = result[result.JalaliYear == year].iloc[0]
        if rate == '-.-':
            assert pd.isna(actual.InflationRate)
        else:
            assert actual.InflationRate == float(rate)
        if '(' in raw_year:
            assert actual.Note == raw_year.split('(',1)[1].removesuffix(')')
    print(json.dumps({'AnnualRows':len(result),'EarliestYear':result.JalaliYear.min(),
                      'LatestYear':result.JalaliYear.max(),'Notes':result[result.Note.notna()].to_dict('records')},ensure_ascii=True))


@pytest.mark.parametrize('ets',[False,True])
def test_live_bulk_history_matches_exports_and_daily_pages(monkeypatch,ets):
    exports = []
    original = CBI._export_rows

    def capture(response,selected,start,end,is_ets):
        exports.append(response.content)
        return original(response,selected,start,end,is_ets)

    monkeypatch.setattr(CBI,'_export_rows',capture)
    function = CBI.get_cbi_ets_rates if ets else CBI.get_cbi_exchange_rates
    result = live(function,currency=['USD','JPY','IQD'],start_date='2026-10-15',end_date='2026-10-19')
    assert not result.empty and result.JalaliDate.is_monotonic_increasing
    assert result.GregorianDate.between('2026-10-15','2026-10-19').all()
    assert not result.duplicated().any()
    # Compare raw XML rate observations independently, excluding summary values.
    raw_dates = set()
    for index,content in enumerate(exports):
        root = ET.fromstring(content.decode('utf-8-sig'))
        for currency in root.findall('currency'):
            code = currency.attrib['id'].strip()
            for row in currency.findall('rate'):
                date = row.findtext('date').replace('/','-')
                raw_dates.add(date)
                actual = result[(result.CurrencyCode == code)&(result.JalaliDate == date)]
                if ets:
                    actual = actual[actual.TransactionType == ('cash' if index < 2 else 'transfer')]
                column = ('BuyRate' if index % 2 == 0 else 'SellRate') if ets else 'ExchangeRate'
                assert actual[column].iloc[0] == float(row.findtext('value'))
    assert set(result.JalaliDate) == raw_dates  # No calendar filling.
    assert result[result.CurrencyCode.str.startswith(('JPY','IQD'))].CurrencyUnit.eq(100).all()
    with requests.Session() as session:
        session.headers.update(CBI._HEADERS)
        path = 'etsrates/etsrates_fa.aspx' if ets else 'ExRates/rates_fa.aspx'
        for transaction in ['cash','transfer'] if ets else [None]:
            response = session.get('https://cbi.ir/'+path,params={'date':'2026/10/19'},timeout=(10,30))
            soup = source_page(response)
            if ets and transaction == 'transfer':
                form = soup.find('form')
                data = {x['name']:x.get('value','') for x in form.select('input[type=hidden][name]')}
                for select in form.find_all('select'):
                    data[select['name']] = (select.find('option',selected=True) or select.find('option'))['value']
                    if select['name'].endswith('$payTypeDropDown'):
                        data[select['name']] = 'tt'
                button = form.find('input',attrs={'type':'submit'})
                data[button['name']] = button.get('value','')
                response = session.post(urljoin(response.url,form.get('action')),data=data,timeout=(10,30))
                soup = source_page(response)
            table = soup.find(id=lambda value:value and value.endswith('_pnlRatesList')).find('table')
            compared = 0
            for row in table.find_all('tr')[1:]:
                cells = [c.get_text(strip=True).translate(DIGITS) for c in row.find_all('td',recursive=False)]
                if not cells or cells[0] not in set(result.CurrencyCode):
                    continue
                actual = result[(result.CurrencyCode == cells[0])&(result.JalaliDate == '1405-07-27')]
                if ets:
                    actual = actual[actual.TransactionType == transaction]
                    assert actual.SellRate.iloc[0] == float(cells[2].replace(',',''))
                    assert actual.BuyRate.iloc[0] == float(cells[5].replace(',',''))
                else:
                    assert actual.ExchangeRate.iloc[0] == float(cells[2].replace(',',''))
                compared += 1
            assert compared == 3
    print(json.dumps({'Dataset':'ETS' if ets else 'Exchange','Rows':len(result),
                      'RowsByType':result.groupby('TransactionType').size().to_dict() if ets else {},
                      'CurrencyCount':result.CurrencyCode.nunique(),'Earliest':result.JalaliDate.min(),
                      'Latest':result.JalaliDate.max(),'Dtypes':{c:str(d) for c,d in result.dtypes.items()},
                      'Mechanism':'official advanced-search XML; no daily retrieval loop'}))


@pytest.mark.parametrize('ets',[False,True])
def test_live_latest_all_currencies_is_bounded(ets):
    result = live(CBI.get_cbi_ets_rates if ets else CBI.get_cbi_exchange_rates)
    assert not result.empty
    assert result.CurrencyCode.nunique() > 3
    assert not result.duplicated().any()
    if ets:
        assert set(result.TransactionType) == {'cash','transfer'}
    print(json.dumps({'LatestDataset':'ETS' if ets else 'Exchange','Currencies':result.CurrencyCode.nunique(),
                      'Rows':len(result),'Earliest':result.JalaliDate.min(),'Latest':result.JalaliDate.max()}))
