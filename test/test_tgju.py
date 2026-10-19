"""Minimal independent mocks shaped like the observed public TGJU responses."""
import datetime as dt
import json
import subprocess
import sys

import jdatetime as jd
import pandas as pd
import pytest
import requests

import fima
import fima.TGJU as TGJU


HOME = '''<script>const search_config = [
{title: "طلا", source: "https://api.tgju.org/v1/newsearch?module=markets.internal&batch=internal_gold"},
{title: "ارز", source: "https://api.tgju.org/v1/newsearch?module=markets.internal&batch=internal_currency"},
{title: "انرژی", source: "https://api.tgju.org/v1/newsearch?module=markets.global&batch=global_energy"},
{title: "ارز دیجیتال", source: "https://api.tgju.org/v1/newsearch?module=markets.global&batch=crypto"},
{title: "commodity", source: "https://api.tgju.org/v1/newsearch?module=markets.global&batch=global_commodity"},
{title: "خبر", source: "https://api.tgju.org/v1/newsearch?module=news"}
];</script>'''
PROFILE = '''<h1 class="title">دلار</h1>
<h3 class="line"><span class="label">واحد پولی :</span><span class="value">ریال</span></h3>
<h3 class="line"><span class="label">واحد حجمی :</span><span class="value">اسکناس <a>راهنما</a></span></h3>
<h3 class="line"><span class="label">کشور :</span><span class="value">ایالات متحده آمریکا</span></h3>'''
USD = dict(mid=137202, n1=137203, title="دلار", title_en="USD", grade="price_dollar_rl",
           s1="دلار", s2="irr", s3="price_dollar_rl", category="ارز آزاد", type="markets.internal", batch="internal_currency")
GOLD = dict(mid=137120, n1=137121, title="طلای 18 عیار / 750", title_en="Gram Gold 18",
            grade="geram18", s1="گرم-طلای-۱۸", s2="irr", s3="geram18", category="طلا", type="markets.internal", batch="internal_gold")
BRENT = dict(mid=131398, n1=131398, title="نفت برنت", title_en="Brent", grade="commodities-brent-oil",
             s1="energy-brent-oil", s2="usd", s3="", category="بازار جهانی", type="markets.global", batch="global_energy")


def snapshot(row=USD, **overrides):
    return dict(item_id=row['n1'], name=row['s3'], slug=row['s1'], title=row['title'],
                p="۲٬۶۳۸٬۰۵۰", h="2,658,000", l="2,633,600", o="2,648,000", d="40950", dp=1.55,
                dt="low", t="۱۴:۲۰:۴۸", updated_at="2026-10-17 14:20:48", **overrides)


def history_row(date="2026/10/15", jdate="1405/07/23", close="2,679,000", direction="high"):
    return ["2,674,050", "2,669,000", "2,679,000", close,
            f'<span class="{direction}">40000</span>', f'<span class="{direction}">1.52%</span>', date, jdate]


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(TGJU, '_categories_cache', None)
    monkeypatch.setattr(TGJU._time, "sleep", lambda _: None)
    state = dict(calls=[], rows=[USD], last=True, snapshots=None,
                 history=[history_row()], total=None, error=None, bad_json=False, profile=PROFILE)

    def get(session, url, **kwargs):
        state['calls'].append((url, kwargs))
        if state['error']:
            raise state['error']
        response = requests.Response()
        response.url = url
        response.status_code = state.get('status', 200)
        response._content_consumed = True
        params = kwargs.get('params', {})
        if url.endswith('/newsearch'):
            rows = state['rows']
            if callable(rows):
                rows = rows(params)
            data = {'list': rows, 'last': state['last']}
        elif '/widget/tmp' in url:
            data = {'response': {'indicators': state['snapshots'] if state['snapshots'] is not None else [snapshot()]}}
        elif 'summary-table-data' in url:
            rows = state['history']
            offset = params['start']
            data = {'recordsTotal': len(rows), 'recordsFiltered': len(rows) if state['total'] is None else state['total'],
                    'data': rows[offset:offset + params['length']]}
        else:
            text = state['profile'] if '/profile/' in url else HOME
            response._content = text.encode()
            response.encoding = 'utf-8'
            return response
        if 'payload' in state:
            data = state['payload']
        response._content = b'not json' if state['bad_json'] else json.dumps(data).encode()
        return response

    monkeypatch.setattr(requests.Session, 'get', get)
    return state


def test_dynamic_category_discovery_and_independent_results(provider):
    table = TGJU.get_tgju_categories()
    assert list(table.columns) == ['Category', 'Market', 'EnglishName']
    assert table.Category.tolist() == ['طلا', 'ارز', 'انرژی', 'ارز دیجیتال', 'commodity']
    table.loc[0, 'Category'] = 'changed'
    assert TGJU.get_tgju_categories().Category.iloc[0] == 'طلا'
    assert len(provider['calls']) == 1


@pytest.mark.parametrize('category', ['ارز', '  ارز  ', 'currency', 'FX'])
def test_category_names_and_pagination(provider, category):
    provider['last'] = False
    table = TGJU.get_tgju_instruments(category, page=2)
    assert table.Symbol.tolist() == ['price_dollar_rl']
    assert table.Currency.tolist() == ['IRR']
    assert table.attrs['HasMore'] is True and table.attrs['Page'] == 2
    params = provider['calls'][-1][1]['params']
    assert params['batch'] == 'internal_currency' and params['page'] == 2
    assert all(call[1]['timeout'] == (10, 30) for call in provider['calls'])


def test_catalog_combines_both_markets_and_preserves_distinct_identifiers(provider):
    provider['rows'] = lambda p: [USD] if p['module'] == 'markets.internal' else [BRENT]
    table = TGJU.get_tgju_instruments()
    assert table.Symbol.tolist() == ['price_dollar_rl', 'energy-brent-oil']
    assert table.EnglishName.tolist() == ['USD', 'Brent']


def test_snapshot_fields_signs_missing_values_and_provider_timestamp(provider):
    table = TGJU.get_tgju_market('ارز')
    row = table.iloc[0]
    assert row.Price == 2638050 and row.OpeningPrice == 2648000
    assert row.PriceChange == -40950 and row.PercentageChange == -1.55
    assert row.UpdateTime == '14:20:48' and row.UpdatedAt == dt.datetime(2026, 10, 17, 14, 20, 48)
    assert row.ChangeDirection == 'low' and row.Currency == 'IRR'
    assert pd.isna(row.Unit)


def test_snapshot_empty_does_not_invent_data(provider):
    provider['snapshots'] = []
    table = TGJU.get_tgju_market('ارز')
    assert len(table) == 1 and not table.HasSnapshot.iloc[0]
    assert pd.isna(table.Price.iloc[0])


def test_widget_requests_are_batched_and_matched_by_id(provider):
    provider['rows'] = [dict(USD, n1=n, mid=n, s3=f'test{n}') for n in range(1, 26)]
    provider['snapshots'] = []
    TGJU.get_tgju_market('ارز')
    batches = [c[1]['params']['keys'].split(',') for c in provider['calls'] if '/widget/tmp' in c[0]]
    assert [len(x) for x in batches] == [20, 5]


def test_persian_english_and_symbol_lookup(provider):
    for name in ['دلار', '  دلار\u200c ', 'usd', 'price_dollar_rl']:
        result = TGJU.get_tgju_instrument_details(name, 'ارز')
        assert result['Symbol'] == 'price_dollar_rl'
        assert result['Unit'] == 'اسکناس'
        assert result['CurrencyName'] == 'ریال'
        assert result['Country'] == 'ایالات متحده آمریکا'


def test_lookup_must_check_later_pages_before_choosing(provider):
    provider['last'] = False
    provider['rows'] = lambda p: [USD] if p['page'] == 1 else []
    TGJU.get_tgju_instrument_details('دلار', 'ارز')
    assert [c[1]['params']['page'] for c in provider['calls'] if c[0].endswith('/newsearch')] == [1, 2]


def test_ambiguous_name_never_silently_chooses(provider):
    provider['rows'] = [USD, dict(USD, mid=9, n1=10, s3='bank-dollar', category='ارز دولتی')]
    with pytest.raises(ValueError, match='[Aa]mbiguous.*price_dollar_rl.*bank-dollar'):
        TGJU.get_tgju_history('دلار', 'ارز')


def test_partial_name_ambiguity(provider):
    provider['rows'] = [GOLD, dict(GOLD, n1=391292, s3='gold_740k', title='طلای 18 عیار / 740')]
    with pytest.raises(ValueError, match='[Aa]mbiguous'):
        TGJU.get_tgju_history('طلای ۱۸ عیار', 'طلا')


def test_unknown_name_and_category(provider):
    provider['rows'] = []
    with pytest.raises(ValueError, match='get_tgju_instruments'):
        TGJU.get_tgju_history('unknown', 'ارز')
    with pytest.raises(ValueError, match='get_tgju_categories'):
        TGJU.get_tgju_instruments('unknown')


def test_history_descending_provider_order_sorted_output_and_duplicates(provider):
    provider['history'] = [history_row(), history_row(), history_row('2026/10/14', '1405/07/22', direction='low')]
    table = TGJU.get_tgju_history('دلار', 'ارز')
    assert len(table) == 2 and table.GregorianDate.is_monotonic_increasing
    assert table.GregorianDate.iloc[-1] == pd.Timestamp("2026-10-15")
    assert table.JalaliDate.iloc[-1] == "1405-07-23"
    assert table.PriceChange.iloc[0] == -40000 and table.ClosingPrice.iloc[-1] == 2679000
    assert table.attrs['Unit'] == 'اسکناس' and table.attrs['Currency'] == 'IRR'
    params = [c[1]['params'] for c in provider['calls'] if 'summary-table-data' in c[0]][0]
    assert params['order_col'] == 'timestamp' and params['order_dir'] == 'desc'


def test_history_fetches_every_page(provider, monkeypatch):
    monkeypatch.setattr(TGJU, '_HISTORY_PAGE_SIZE', 1)
    provider['history'] = [history_row(), history_row('2026/10/14', '1405/07/22')]
    assert len(TGJU.get_tgju_history('دلار', 'ارز')) == 2
    assert [c[1]['params']['start'] for c in provider['calls'] if 'summary-table-data' in c[0]] == [0, 1]


@pytest.mark.parametrize('jalali,start,end', [(False,'2026-10-14','2026-10-15'), (True,'۱۴۰۵/۰۷/۲۲','۱۴۰۵/۰۷/۲۳')])
def test_history_date_bounds_converted_to_provider_jalali(provider, jalali, start, end):
    TGJU.get_tgju_history('دلار', 'ارز', start_date=start, end_date=end, jalali=jalali)
    params = [c[1]['params'] for c in provider['calls'] if 'summary-table-data' in c[0]][0]
    assert params['from'] == '1405/07/22' and params['to'] == '1405/07/23'


@pytest.mark.parametrize('kwargs', [{'start_date':'bad'}, {'start_date':'2026-10-17','end_date':'2026-10-10'}, {'jalali':'false'}])
def test_invalid_dates_fail_before_http(provider, kwargs):
    with pytest.raises(ValueError):
        TGJU.get_tgju_history('دلار', **kwargs)
    assert provider['calls'] == []


def test_empty_history_has_stable_columns(provider):
    provider['history'] = []
    table = TGJU.get_tgju_history('دلار', 'ارز')
    assert table.empty and list(table.columns) == ['GregorianDate', 'JalaliDate', 'OpeningPrice', 'LowPrice', 'HighPrice', 'ClosingPrice', 'PriceChange', 'PercentageChange', 'ChangeDirection']


def test_repeated_history_page_fails_instead_of_looping(provider, monkeypatch):
    monkeypatch.setattr(TGJU, '_HISTORY_PAGE_SIZE', 1)
    provider['history'] = [history_row(), history_row()]
    provider['total'] = 3
    with pytest.raises(ValueError, match='pagination'):
        TGJU.get_tgju_history('دلار', 'ارز')


@pytest.mark.parametrize('text,expected', [('۱۲٬۳۴۵٫۶',12345.6), ('١٢٣',123), ('-1,200',-1200), ('0',0), ('-',None), ('',None), ('9007199254740993',9007199254740993), ('5e-8',5e-8)])
def test_numeric_parsing(text, expected):
    assert TGJU._number(text) == expected


@pytest.mark.parametrize('text', ['not a price','NaN','inf','1,2,3'])
def test_invalid_numeric_fields_are_not_silently_missing(text):
    with pytest.raises(ValueError, match='TGJU'):
        TGJU._number(text)


@pytest.mark.parametrize('payload', [None, [], {}, {'list':{}}, {'list':[{}], 'last':True}])
def test_malformed_catalog_response(provider, payload):
    provider['payload'] = payload
    with pytest.raises(ValueError, match='TGJU'):
        TGJU.get_tgju_instruments('ارز')


def test_malformed_json(provider):
    provider['bad_json'] = True
    with pytest.raises(ValueError, match='TGJU.*JSON'):
        TGJU.get_tgju_instruments('ارز')


def test_timeout_is_public_and_finite(provider):
    provider['error'] = requests.Timeout('timeout')
    with pytest.raises(requests.Timeout, match='TGJU'):
        TGJU.get_tgju_categories()
    assert len(provider['calls']) == 1


@pytest.mark.parametrize('status,attempts', [(401,1),(403,1),(429,1),(500,2),(503,2)])
def test_http_errors_are_not_bypassed(provider, status, attempts):
    provider['status'] = status
    with pytest.raises(requests.HTTPError):
        TGJU.get_tgju_categories()
    assert len(provider['calls']) == attempts


def test_public_exports_are_exact():
    expected = {'get_tgju_categories','get_tgju_instruments','get_tgju_market','get_tgju_history','get_tgju_instrument_details'}
    assert set(TGJU.__all__) == expected
    namespace = {}
    exec('from fima.TGJU import *', namespace)
    assert set(namespace) - {'__builtins__'} == expected
    for name in expected:
        assert getattr(fima,name) is getattr(TGJU,name)


def test_import_does_not_request_network():
    result = subprocess.run([sys.executable, '-c',
        "from unittest.mock import patch; "
        "guard = patch('requests.sessions.Session.request', side_effect=AssertionError('network at import')); "
        "guard.start(); import fima.TGJU"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_conflicting_snapshot_duplicates_are_reported(provider):
    raw = snapshot()
    provider['snapshots'] = [raw, dict(raw, p='1')]
    with pytest.raises(ValueError, match='conflicting duplicate'):
        TGJU.get_tgju_market('ارز')


def test_blank_profile_unit_is_missing_without_imputation(provider):
    provider['profile'] = PROFILE.replace('اسکناس <a>راهنما</a>', '')
    details = TGJU.get_tgju_instrument_details('دلار', 'ارز')
    assert details['Unit'] is None
    assert details['ProviderMetadata']['واحد حجمی'] == ''


@pytest.mark.parametrize('payload', [{}, {'data':{}}, {'data':[], 'recordsFiltered':'2'}, {'data':[[1]], 'recordsFiltered':1}, {'data':[history_row()], 'recordsFiltered':0}])
def test_malformed_history_is_reported(provider, monkeypatch, payload):
    original = TGJU._Client.get
    def get(client, url, *args, **kwargs):
        return payload if 'summary-table-data' in url else original(client, url, *args, **kwargs)
    monkeypatch.setattr(TGJU._Client, 'get', get)
    with pytest.raises(ValueError, match='TGJU'):
        TGJU.get_tgju_history('دلار', 'ارز')


def test_null_history_values_are_preserved_as_missing(provider):
    row = history_row()
    row[0] = row[4] = row[5] = None
    provider['history'] = [row]
    table = TGJU.get_tgju_history('دلار', 'ارز')
    assert table.OpeningPrice.isna().all() and table.PriceChange.isna().all() and table.PercentageChange.isna().all()


def test_profile_with_only_a_title_is_not_valid_metadata(provider):
    provider['profile'] = '<h1 class="title">دلار</h1>'
    with pytest.raises(ValueError, match='TGJU.*metadata'):
        TGJU.get_tgju_instrument_details('دلار', 'ارز')


def test_suspicious_provider_ohlc_is_preserved_without_repair(provider):
    provider['rows'] = [BRENT]
    provider['history'] = [['101.031','100.2','99.556','103.356','-','-','2026/10/08','1405/07/16']]
    history = TGJU.get_tgju_history('نفت برنت', 'انرژی')
    assert history[['OpeningPrice','LowPrice','HighPrice','ClosingPrice']].iloc[0].tolist() == [101.031,100.2,99.556,103.356]
    assert history.HighPrice.iloc[0] < history.LowPrice.iloc[0]


def test_commodity_with_null_grade_uses_public_symbol(provider):
    # Observed newsearch record: grade is optional even when s3 and n1 exist.
    provider['rows'] = [dict(BRENT, mid=2172884, n1=2150998,
        title='روغن کلزا', title_en='Canola Oil', grade=None,
        s1='روغن-کلزا', s2='cad', s3='commodity_canola_oil',
        batch='global_commodity', category='محصولات کشاورزی')]
    table = TGJU.get_tgju_instruments('commodity')
    assert table.Symbol.tolist() == ['commodity_canola_oil']
    assert table.Currency.tolist() == ['CAD']


def test_catalog_without_any_public_symbol_is_rejected(provider):
    provider['rows'] = [dict(USD, grade=None, s1=None, s3=None)]
    with pytest.raises(ValueError, match='TGJU.*symbol'):
        TGJU.get_tgju_instruments('currency')


def test_symbol_lookup_retries_readable_words_without_changing_selection(provider):
    canola = dict(BRENT, grade=None, s3='commodity_canola_oil', title_en='Canola Oil')
    provider['rows'] = lambda params: [] if params.get('q') == 'commodity_canola_oil' else [canola]
    details = TGJU.get_tgju_instrument_details('commodity_canola_oil', 'commodity')
    assert details['Symbol'] == 'commodity_canola_oil'
    queries = [kwargs['params']['q'] for url, kwargs in provider['calls'] if url.endswith('/newsearch')]
    assert queries == ['commodity_canola_oil', 'commodity canola oil']



def test_snapshot_display_date_label_is_not_a_clock_time(provider):
    provider['snapshots'] = [dict(snapshot(), t='2 \u0628\u0647\u0645\u0646')]
    result = TGJU.get_tgju_market('currency')
    assert result.iloc[0].UpdateLabel == '2 \u0628\u0647\u0645\u0646'
    assert pd.isna(result.iloc[0].UpdateTime)
    assert result.iloc[0].UpdatedAt == pd.Timestamp('2026-10-17 14:20:48')
