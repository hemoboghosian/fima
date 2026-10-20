"""Small fixtures modeled on the observed CBI Web Forms DOM, without tokens."""
import inspect
import subprocess
import sys

import pandas as pd
import pytest
import requests

import fima
import fima.CBI as CBI


FIELD = "ctl00$ucBody$ucContent$ctl00$ddlYear"
HEADERS = ["تاریخ", "نرخ بازار بین‌بانکی(%)", "حداقل نرخ توافق بازخرید(%)",
           "نرخ اعتبارگیری قاعده\u200b‌مند(%)", "نرخ سپرده‌گذاری قاعده‌\u200bمند(%)"]
COLUMNS = ["JalaliDate", "GregorianDate", "InterbankRate", "RepoCutoffRate",
           "StandingLendingRate", "StandingDepositRate"]


def page(years=("1407", "1403", "1399"), selected="1407", rows=None,
         state="initial", headers=HEADERS, order=None):
    if rows is None:
        rows = [[f"{selected}/01/02", "24.00", "23", "24", "17"]]
    order = list(range(5)) if order is None else order
    options = ''.join(f'<option value="{y}" {"selected" if y == selected else ""}>{y}</option>'
                      for y in years)
    th = ''.join(f'<th>{headers[i]}</th>' for i in order)
    tr = ''.join('<tr>' + ''.join(f'<td>{row[i]}</td>' for i in order) + '</tr>' for row in rows)
    return f'''<html><form id="aspnetForm" action="./policyrates_fa.aspx" method="post">
        <input type="hidden" name="__EVENTTARGET" value="">
        <input type="hidden" name="__EVENTARGUMENT" value="">
        <input type="hidden" name="__LASTFOCUS" value="">
        <input type="hidden" name="__VIEWSTATE" value="{state}">
        <input type="hidden" name="__VIEWSTATEGENERATOR" value="generator-{state}">
        <input type="hidden" name="__VIEWSTATEENCRYPTED" value="">
        <input type="hidden" name="__EVENTVALIDATION" value="validation-{state}">
        <input type="hidden" name="__VIEWSTATEFIELDCOUNT" value="2">
        <input type="hidden" name="__VIEWSTATE1" value="chunk-{state}">
        <table><tr><th>Unrelated table</th></tr><tr><td>Ignore</td></tr></table>
        <select name="{FIELD}" onchange="__doPostBack('{FIELD}', '')">{options}</select>
        <div id="ctl00_ucBody_ucContent_ctl00_divRates"><table dir="rtl">
        <thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>
        </form></html>'''


@pytest.fixture
def provider(monkeypatch):
    state = dict(calls=[], initial=page(), pages={"1403": page(selected="1403", state="second"),
                                               "1399": page(selected="1399", state="third")})

    def request(session, method, url, **kwargs):
        state['calls'].append((method, url, kwargs, dict(session.headers)))
        if method == 'post':
            year = kwargs['data'][FIELD]
            result = state['pages'][year]
        else:
            result = state['initial']
        if isinstance(result, Exception):
            raise result
        response = requests.Response()
        response.url = url
        response.status_code = state.get('status', 200)
        response._content = result.encode('utf-8')
        return response

    monkeypatch.setattr(requests.Session, 'get', lambda s, url, **kw: request(s, 'get', url, **kw))
    monkeypatch.setattr(requests.Session, 'post', lambda s, url, **kw: request(s, 'post', url, **kw))
    return state


def test_dynamic_future_years_complete_history_and_refreshed_postbacks(provider):
    rates = fima.get_cbi_policy_rates()
    assert rates.JalaliDate.tolist() == ['1399-01-02', '1403-01-02', '1407-01-02']
    calls = provider['calls']
    assert [c[0] for c in calls] == ['get', 'post', 'post']
    assert all(c[1] == 'https://cbi.ir/PolicyRates/policyrates_fa.aspx' for c in calls)
    assert all(c[2]['timeout'] == (10, 30) and c[2].get('verify', True) for c in calls)
    assert 'text/html' in calls[0][3]['Accept']
    for call, year, token in zip(calls[1:], ['1403', '1399'], ['initial', 'second']):
        payload = call[2]['data']
        assert payload[FIELD] == year and payload['__EVENTTARGET'] == FIELD
        assert payload['__EVENTARGUMENT'] == ''
        assert payload['__VIEWSTATE'] == token
        assert payload['__VIEWSTATEGENERATOR'] == 'generator-' + token
        assert payload['__EVENTVALIDATION'] == 'validation-' + token
        assert payload['__VIEWSTATE1'] == 'chunk-' + token
        assert payload['__VIEWSTATEFIELDCOUNT'] == '2'
        assert payload['__VIEWSTATEENCRYPTED'] == ''


def test_one_year_persian_arabic_digits_missing_zeros_dtypes_sort_and_dedup(provider):
    rows = [['۱۴۰۳/۰۱/۰۲', '۲۴٫۰۰٪', '٢٣', '۲۴', '۱۷'],
            ['۱۴۰۳/۰۱/۰۱', '۰', '-', '', '—'],
            ['۱۴۰۳/۰۱/۰۲', '۲۴٫۰۰٪', '٢٣', '۲۴', '۱۷']]
    provider['initial'] = page(years=['1403'], selected='1403', rows=rows)
    rates = CBI.get_cbi_policy_rates()
    assert list(rates.columns) == COLUMNS
    assert rates.JalaliDate.tolist() == ['1403-01-01', '1403-01-02']
    assert rates.GregorianDate.tolist() == [pd.Timestamp('2024-03-20'), pd.Timestamp('2024-03-21')]
    assert rates.loc[1, COLUMNS[2:]].tolist() == [24.0, 23.0, 24.0, 17.0]
    assert rates.InterbankRate.iloc[0] == 0
    assert rates.loc[0, COLUMNS[3:]].isna().all()
    assert [str(dtype) for dtype in rates.dtypes] == ['string', 'datetime64[ns]'] + ['float64'] * 4
    assert rates.index.equals(pd.RangeIndex(2))
    assert len(provider['calls']) == 1


@pytest.mark.parametrize('order', [[0, 1, 2, 3, 4], [4, 3, 2, 1, 0], [0, 3, 4, 1, 2]])
def test_rtl_mapping_uses_header_semantics_in_actual_dom_order(provider, order):
    provider['initial'] = page(years=['1399'], selected='1399', order=order,
                               rows=[['۱۳۹۹/۱۱/۲۵', '19.85', '19.81', '22', '14']])
    rates = CBI.get_cbi_policy_rates()
    assert rates.iloc[0][COLUMNS[2:]].tolist() == [19.85, 19.81, 22.0, 14.0]


@pytest.mark.parametrize('year,values', [
    ('1405', ['24.00', '23', '24', '17']),
    ('1402', ['23.66', '23', '24', '17']),
    ('1399', ['19.99', '19.8', '22', '14']),
])
def test_observed_newest_middle_oldest_dom_rows(provider, year, values):
    dates = {'1405': '1405/07/23', '1402': '1402/12/29', '1399': '1399/12/28'}
    provider['initial'] = page(years=[year], selected=year, rows=[[dates[year], *values]])
    assert CBI.get_cbi_policy_rates().iloc[0][COLUMNS[2:]].tolist() == list(map(float, values))


@pytest.mark.parametrize('broken,match', [
    ('<html>no selector</html>', 'year selector'),
    (page().replace('<table dir="rtl">', '<section>').replace('</tbody></table>', '</tbody></section>'), 'table'),
    (page(headers=HEADERS[:2] + ['Unknown rate'] + HEADERS[3:]), 'headers'),
    (page().replace('name="__VIEWSTATE"', 'name="changed"'), 'VIEWSTATE'),
    ('<title>Request Rejected</title>', 'Request Rejected'),
    (page(years=[]), 'years'),
])
def test_unexpected_initial_structure_fails_clearly(provider, broken, match):
    provider['initial'] = broken
    with pytest.raises(RuntimeError, match=match):
        CBI.get_cbi_policy_rates()


@pytest.mark.parametrize('failure', [requests.Timeout('read timeout'), requests.ConnectionError('unreachable'),
                                   '<title>Request Rejected</title>',
                                   page(selected='1407'), page(selected='1403', rows=[])])
def test_one_advertised_year_fails_without_partial_history(provider, failure):
    provider['pages']['1403'] = failure
    with pytest.raises(RuntimeError, match='1403'):
        CBI.get_cbi_policy_rates()
    assert len(provider['calls']) == 2


@pytest.mark.parametrize('row', [
    ['1407/13/01', '24', '23', '24', '17'],
    ['1407/01/01junk', '24', '23', '24', '17'],
    ['', '24', '23', '24', '17'],
    ['1406/01/01', '24', '23', '24', '17'],
    ['1407/01/01', 'unknown', '23', '24', '17'],
    ['1407/01/01', 'inf', '23', '24', '17'],
])
def test_malformed_dates_wrong_year_and_numbers_raise_with_year(provider, row):
    provider['initial'] = page(rows=[row])
    with pytest.raises(RuntimeError, match='1407'):
        CBI.get_cbi_policy_rates()


def test_ambiguous_matching_tables_rejected(provider):
    html = page()
    table = html[html.index('<table dir="rtl">'):html.index('</tbody></table>') + len('</tbody></table>')]
    provider['initial'] = html.replace('</form>', table + '</form>')
    with pytest.raises(RuntimeError, match='table'):
        CBI.get_cbi_policy_rates()


def test_http_failure_is_visible(provider):
    provider['status'] = 503
    with pytest.raises(RuntimeError, match='503'):
        CBI.get_cbi_policy_rates()


def test_actual_page_does_not_require_eventvalidation(provider):
    provider['initial'] = page().replace(
        '<input type="hidden" name="__EVENTVALIDATION" value="validation-initial">', '')
    assert len(CBI.get_cbi_policy_rates()) == 3
    assert '__EVENTVALIDATION' not in provider['calls'][1][2]['data']


def test_selected_year_need_not_be_first_option(provider):
    provider['initial'] = page(selected='1403')
    provider['pages']['1407'] = page(selected='1407')
    assert len(CBI.get_cbi_policy_rates()) == 3
    assert [c[2]['data'][FIELD] for c in provider['calls'][1:]] == ['1407', '1403', '1399']


def test_persian_selector_wire_values_are_preserved(provider):
    provider['initial'] = page(years=['۱۴۰۷', '۱۳۹۹'], selected='۱۴۰۷')
    provider['pages']['۱۳۹۹'] = page(years=['۱۴۰۷', '۱۳۹۹'], selected='۱۳۹۹')
    assert CBI.get_cbi_policy_rates().JalaliDate.tolist() == ['1399-01-02', '1407-01-02']
    assert provider['calls'][1][2]['data'][FIELD] == '۱۳۹۹'


@pytest.mark.parametrize('html,match', [
    (page(years=['1403'], selected='1403'), 'years changed'),
    (page(selected='1403').replace('<td>23</td>', '<td colspan="2">23</td>'), 'row structure'),
    (page(selected='1403').replace('<th>تاریخ</th>', '<th colspan="2">تاریخ</th>'), 'grouped headers'),
])
def test_material_response_changes_fail_with_advertised_year(provider, html, match):
    provider['pages']['1403'] = html
    with pytest.raises(RuntimeError, match=f'1403.*{match}'):
        CBI.get_cbi_policy_rates()


@pytest.mark.parametrize('action', ['https://unrelated.example/post', 'http://cbi.ir/post'])
def test_unexpected_postback_origin_is_not_submitted(provider, action):
    provider['initial'] = page().replace('./policyrates_fa.aspx', action)
    with pytest.raises(RuntimeError, match='1403.*HTTPS origin'):
        CBI.get_cbi_policy_rates()
    assert len(provider['calls']) == 1


@pytest.mark.parametrize('years', [['1407', '1407'], ['future'], ['']])
def test_invalid_or_empty_advertised_years_fail(provider, years):
    provider['initial'] = page(years=years)
    with pytest.raises(RuntimeError, match='years'):
        CBI.get_cbi_policy_rates()


def test_empty_initial_year_is_not_silently_omitted(provider):
    provider['initial'] = page(rows=[])
    with pytest.raises(RuntimeError, match='1407.*empty'):
        CBI.get_cbi_policy_rates()


@pytest.mark.parametrize('html', [
    '<html><head><title> Request Rejected </title></head><body>Access denied</body></html>',
    '<html><body>The requested URL was rejected. Please consult with your administrator.'
    '<br>Your support ID is: &lt;example&gt;</body></html>',
])
@pytest.mark.parametrize('annual', [False, True])
def test_http_200_rejection_is_an_explicit_access_error_not_data(provider, html, annual):
    if annual:
        provider['pages']['1403'] = html
    else:
        provider['initial'] = html
    with pytest.raises(RuntimeError, match='CBI rejected ordinary programmatic access') as error:
        CBI.get_cbi_policy_rates()
    assert isinstance(error.value.__cause__, ValueError)
    assert str(error.value.__cause__) == CBI._ACCESS_ERROR
    if annual:
        assert '1403' in str(error.value)


def test_schema_failure_is_not_classified_as_known_provider_rejection(provider):
    provider['initial'] = '<title>CBI</title><body>Unexpected provider response</body>'
    with pytest.raises(RuntimeError, match='year selector') as error:
        CBI.get_cbi_policy_rates()
    assert str(error.value.__cause__) != CBI._ACCESS_ERROR


def test_mixed_header_and_data_row_is_rejected(provider):
    provider['initial'] = page().replace('<td>24.00</td>', '<th>24.00</th>')
    with pytest.raises(RuntimeError, match='1407.*headers'):
        CBI.get_cbi_policy_rates()


def test_public_api_signature_exports_and_import_without_network():
    assert fima.get_cbi_policy_rates is CBI.get_cbi_policy_rates
    assert str(inspect.signature(CBI.get_cbi_policy_rates)) == '()'
    namespace = {}
    exec('from fima.CBI import *', namespace)
    assert set(namespace) - {'__builtins__'} == {
        'get_cbi_policy_rates', 'get_cbi_inflation_rates',
        'get_cbi_exchange_rates', 'get_cbi_ets_rates'}
    subprocess.run([sys.executable, '-c', '''
import requests
def fail(*args, **kwargs):
    raise AssertionError("network request during import")
requests.sessions.Session.request = fail
import fima.CBI
from fima import get_cbi_policy_rates
from fima.CBI import get_cbi_policy_rates as direct
assert get_cbi_policy_rates is direct
'''], check=True, capture_output=True)
