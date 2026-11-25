"""Versioned structural contracts and executable documentation workflows."""
import ast
from functools import wraps
import importlib
import inspect
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import get_args, get_type_hints

import pandas as pd
import pytest
import requests

import fima
from test.test_cbi_series import provider as cbi_provider
from test.test_imf import source as imf_source
from test.test_kilid import install as kilid_install, page, Response
from test.test_tgju import provider as tgju_provider


ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((Path(__file__).parent / 'fixtures/public_api_0160.json').read_text(encoding='utf-8'))


@pytest.fixture(autouse=True)
def forbid_http(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError('Documentation tests must use fixtures, never live HTTP')
    monkeypatch.setattr(requests.Session, 'send', unexpected)


def blocks(path):
    return re.findall(r'```python\n(.*?)```', (ROOT / path).read_text(encoding='utf-8'), re.S)


def run_example(path, contains, namespace=None):
    selected = [b for b in blocks(path) if contains in b]
    assert len(selected) == 1, (path, contains, len(selected))
    result = {} if namespace is None else namespace
    exec(compile(selected[0], path, 'exec'), result)
    return result


def substitute(monkeypatch, name, result):
    """Bind real signatures before supplying synthetic documentation tables."""
    original = getattr(fima, name)
    calls = []

    @wraps(original)
    def fake(*args, **kwargs):
        inspect.signature(original).bind(*args, **kwargs)
        calls.append((args, kwargs))
        return result(*args, **kwargs) if callable(result) else result.copy(deep=True)
    monkeypatch.setattr(fima, name, fake)
    return calls


def test_published_imports_and_signatures_preserved_with_only_approved_additions():
    public = {n: v for n, v in vars(fima).items() if not n.startswith('_') and callable(v)}
    assert set(public) == set(BASELINE) | {
        'calculate_contract_metrics', 'calculate_expiration_payoff', 'get_codal_report', 'get_codal_tables',
        'get_codal_monthly_activity', 'get_codal_financial_statements',
        'get_damodaran_datasets', 'get_damodaran_data',
        'get_world_bank_sources', 'get_world_bank_countries', 'get_world_bank_indicators', 'get_world_bank_series',
        'get_codal_data', 'search_codal_filings', 'fetch_codal_report', 'list_codal_report_types',
    }
    for name in BASELINE:
        function = public[name]
        expected = BASELINE[name]
        assert function.__module__ == expected['module']
        assert function is getattr(importlib.import_module(expected['module']), name)
        module = next(node.module for node in ast.parse(Path(inspect.getsourcefile(fima)).read_text()).body
                      if isinstance(node, ast.ImportFrom) and any(a.name == name for a in node.names))
        assert function is getattr(importlib.import_module('fima.' + module), name)
        assert [[p.name, p.kind.name, repr(p.default)]
                for p in inspect.signature(function).parameters.values()] == expected['parameters']


def test_every_public_function_has_parameter_help_and_api_navigation():
    api = (ROOT / 'docs/api.md').read_text(encoding='utf-8')
    for name, function in vars(fima).items():
        if name.startswith('_') or not callable(function):
            continue
        doc = inspect.getdoc(function)
        assert doc and len(doc.splitlines()) >= 5, name
        for parameter in inspect.signature(function).parameters:
            if not parameter.startswith('_'):
                assert parameter in doc, (name, parameter)
        assert f'`{name}(' in api, name
        get_type_hints(function)  # Detect unresolved imported/type annotation names.


@pytest.mark.parametrize('function,parameter,choices', [
    ('get_kilid_house_price_history', 'period', ('6m', '1y', '3y')),
    ('get_kilid_house_price_history', 'denomination', ('toman', 'usd', 'gold')),
    ('get_cbi_inflation_rates', 'frequency', ('monthly', 'annual')),
    ('get_cbi_ets_rates', 'transaction_type', ('cash', 'transfer', 'all', 'اسکناس', 'حواله')),
    ('get_ifb_market_map', 'metric', ('trade_volume', 'trade_value', 'transaction_count', 'market_value')),
    ('get_ifb_market_values', 'group_by', ('industry', 'market')),
    ('get_ifb_yield_curve', 'category', ('treasury', 'government', 'nongovernment')),
    ('get_ifb_bond_yield_history', 'on_conflict', ('raise', 'preserve')),
    ('get_all_ime_option_trades', 'option_type', ('All', 'Call', 'Put')),
    ('get_gold_and_silver_cd_trades', 'contract_type', ('gold_coin_cd', 'gold_bar_cd', 'silver_bar_cd')),
    ('calculate_black_scholes_merton', 'option_type', ('Call', 'Put')),
    ('calculate_contract_metrics', 'price', ('Ask', 'Bid', 'Mid', 'Last', 'Closing')),
    ('calculate_contract_metrics', 'underlying_price', ('Last', 'Closing')),
    ('calculate_expiration_payoff', 'option_type', ('Call', 'Put')),
    ('calculate_expiration_payoff', 'position', ('Long', 'Short')),
])
def test_verified_closed_choices_are_visible(function, parameter, choices):
    assert get_args(get_type_hints(getattr(fima, function))[parameter]) == choices


def test_permissive_selectors_and_dynamic_identifiers_are_not_narrowed():
    for function, parameter in [('download_market_watch', 'market'), ('download_market_watch', 'stack'),
                                 ('calculate_delta', 'option_type'), ('get_tgju_history', 'instrument'),
                                 ('get_imf_series', 'indicator'), ('get_kilid_house_price_history', 'area')]:
        assert get_type_hints(getattr(fima, function))[parameter] is str
    assert get_type_hints(fima.download_market_watch)['bsm'] is bool
    assert get_type_hints(fima.download_chain_contracts)['j_date'] is bool


def test_public_imports_do_not_make_http_requests():
    code = '''import requests
def forbidden(*a, **k):
    raise AssertionError("import made an HTTP request")
requests.Session.request = forbidden
import fima
import fima.DAMODARAN
'''
    subprocess.run([sys.executable, '-B', '-c', code], check=True, capture_output=True, text=True)


def test_documentation_python_syntax_and_local_file_links():
    for path in [ROOT / 'README.md', *sorted((ROOT / 'docs').glob('*.md'))]:
        text = path.read_text(encoding='utf-8')
        for code in re.findall(r'```python\n(.*?)```', text, re.S):
            compile(code, str(path), 'exec')
        for target in re.findall(r'\]\(([^)]+)\)', text):
            target = target.strip('<>').split('#')[0]
            if target and '://' not in target and not target.startswith('mailto:'):
                assert (path.parent / target).is_file(), (path, target)


@pytest.mark.parametrize('path', ['README.md', 'docs/tgju.md'])
def test_tgju_discovery_examples_use_actual_returned_symbol(tgju_provider, path):
    result = run_example(path, 'selected = matches.loc')
    assert result['symbol'] == 'price_dollar_rl'
    frame = result['usd'] if path == 'README.md' else result['history']
    assert frame.attrs['Symbol'] == result['symbol']
    assert frame.GregorianDate.tolist() == [pd.Timestamp('2026-10-15')]
    assert any('/summary-table-data/price_dollar_rl' in url for url, _ in tgju_provider['calls'])


@pytest.mark.parametrize('path', ['README.md', 'docs/imf.md'])
def test_imf_discovery_comparison_examples(imf_source, path):
    result = run_example(path, 'indicators = get_imf_indicators' if path == 'docs/imf.md' else 'get_imf_countries')
    series = result['growth'] if path == 'README.md' else result['series']
    assert set(series.Country) == {'IRN', 'USA'}
    assert series.attrs['ObservationStatus'] == 'Unknown'
    assert series.attrs['IndicatorMetadata']['Unit'] == 'Annual percent change'


def test_cbi_currency_discovery_example(cbi_provider):
    result = run_example('docs/cbi.md', 'drop_duplicates()')
    assert result['latest'].CurrencyCode.tolist() == ['USD', 'USD']


def test_kilid_discovered_area_example(kilid_install, monkeypatch):
    kilid_install()  # Fixed retrieval time, with the existing attributed fixtures.
    def get(url, **kwargs):
        name = 'tehran' if url.endswith('/tehran') else 'region5-usd-36'
        return Response(page(name), url)
    monkeypatch.setattr(requests, 'get', get)
    result = run_example('docs/kilid.md', 'selected = areas.loc')
    assert result['history'].Area.unique().tolist() == ['tehran-region5']
    assert result['history'].Unit.unique().tolist() == ['USDPerSquareMeter']


def stock_table():
    frame = pd.DataFrame({'ClosingPrice': [100., 50.], 'LastPrice': [100., 50.],
                          'OpeningPrice': [100., 50.], 'LowPrice': [100., 50.],
                          'HighPrice': [100., 50.], 'YesterdayPrice': [100., 50.],
                          'TradeVolume': [1., 2.]},
                         index=pd.Index(['1403-12-28', '1403-12-29'], name='JalaliDate'))
    return frame


def test_stock_discovery_and_corrected_as_of_example(monkeypatch):
    substitute(monkeypatch, 'get_tickers', pd.DataFrame({'Ticker':['فملی'], 'InstrumentCode':['000123']}))
    calls = substitute(monkeypatch, 'get_ticker_historical_data',
                       lambda *a, **k: fima.adjust_historical_prices(stock_table())
                       if k.get('adjust_prices') else stock_table())
    run_example('README.md', 'ticker="فملی"')
    result = run_example('docs/tsetmc.md', 'selected = tickers.loc')
    assert calls[-1][1]['ticker_instrument_code'] == '000123'
    assert result['history'].index.name == 'JalaliDate'
    # This block imports the function through its provider module.
    import fima.TSETMC as tse
    monkeypatch.setattr(tse, 'get_ticker_historical_data', getattr(fima, 'get_ticker_historical_data'))
    result = run_example('docs/tsetmc-adjustment.md', 'raw.index <=')
    assert result['as_of'].index.tolist() == ['1403-12-28', '1403-12-29']
    assert result['as_of'].AdjustmentFactor.tolist() == [.5, 1.]


def test_index_discovery_tuple_example(monkeypatch):
    substitute(monkeypatch, 'get_indexes_status', pd.DataFrame({'IndexValue':[123]}, index=['Synthetic index']))
    substitute(monkeypatch, 'get_index_historical_data', pd.DataFrame({'IndexValue':[123]}))
    calls = substitute(monkeypatch, 'get_index_companies', lambda *a, **k: (pd.DataFrame(), pd.DataFrame()))
    result = run_example('docs/tsetmc.md', 'index_name =')
    assert result['index_name'] == 'Synthetic index'
    assert calls[0][1] == {'thirty_days_history':True}


@pytest.mark.parametrize('path', ['README.md', 'docs/funds.md'])
def test_fund_website_examples_select_catalog_name(monkeypatch, path):
    catalog = pd.DataFrame({'FundName':['ثروت آفرین تمدن'], 'FundTypeName':['Synthetic'],
                            'WebsiteAddress':['fund.invalid'], 'TotalNAV':[100]})
    substitute(monkeypatch, 'get_all_funds', catalog)
    calls = substitute(monkeypatch, 'get_daily_navs', pd.DataFrame({'SubscriptionNAV':[10]}))
    substitute(monkeypatch, 'get_daily_asset_allocation', pd.DataFrame({'CashWeight':[20]}))
    run_example(path, 'from fima import get_all_funds')
    assert calls[0][0] == ('ثروت آفرین تمدن',)


def test_tsetmc_funds_discovery_example(monkeypatch):
    from test.test_funds_tsetmc_names import mock_catalogs
    mock_catalogs(monkeypatch, {7:[{'regNo':11172,'mfName':'Synthetic fund','navSub':10,'navRed':9}]})
    result = run_example('docs/tsetmc-funds.md', 'types = get_tsetmc_fund_types()')
    assert result['group'] == '7'
    assert result['details_by_id']['RegistrationNumber'] == 11172


def test_option_discovery_and_contract_example(monkeypatch):
    substitute(monkeypatch, 'download_all_underlying_assets', pd.DataFrame({'Ticker':['اهرم'], 'InstrumentCode':['001']}))
    chain = pd.DataFrame({'CallTicker':['SYNTHETIC-C'], 'PutTicker':['SYNTHETIC-P'],
                          'StrikePrice':[100], 'EndJalaliDate':['1405-09-01']})
    substitute(monkeypatch, 'download_chain_contracts', chain)
    calls = substitute(monkeypatch, 'ticker_info', pd.DataFrame({'OptionType':['Call']}))
    run_example('docs/options.md', 'assets = download_all_underlying_assets')
    assert calls[0][0] == ('SYNTHETIC-C',)


@pytest.mark.parametrize('path', ['README.md', 'docs/options.md'])
def test_offline_option_comparison_examples_select_exact_identity(monkeypatch, path):
    from types import SimpleNamespace
    from test.test_tsetmc_options_contracts import option_record
    import fima.Options as options
    raw = option_record()
    raw['contractSize'] = 1254
    monkeypatch.setattr(requests, 'get', lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {'instrumentOptMarketWatch': [raw]}))
    watch = options.download_market_watch(stack='Vertical')
    before = watch.copy(deep=True)
    calls = substitute(monkeypatch, 'download_market_watch', watch)
    replies = iter(['00002'] if path == 'README.md' else ['BASE', '00002'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(replies))
    result = run_example(path, 'comparison = calculate_contract_metrics')
    assert calls[0][1] == {'stack': 'Vertical'}
    assert result['comparison'].InstrumentCode.tolist() == ['00002']
    assert result['comparison'].PremiumPerContract.tolist() == [12540.]
    pd.testing.assert_frame_equal(watch, before)
    if path == 'docs/options.md':
        monkeypatch.setattr('builtins.input', lambda prompt: '8')
        result = run_example(path, 'position_payoff = calculate_expiration_payoff', result)
        assert result['position_payoff'].GrossProfit.tolist() == pytest.approx([-10032., -10032., 2508.])


def test_expiration_example_uses_real_offline_function():
    result = run_example('docs/options.md', 'scenarios = calculate_expiration_payoff')
    assert result['scenarios'].GrossProfit.tolist() == [-200640., -200640., 300960.]


def test_ime_discovery_and_physical_reuse_examples(monkeypatch):
    certificates = pd.DataFrame({'Symbol':['Synthetic'], 'Code':['0001'], 'Description':['Synthetic certificate']})
    calls = substitute(monkeypatch, 'get_all_ime_cd_trades', certificates)
    substitute(monkeypatch, 'get_all_ime_option_trades', pd.DataFrame({'ContractCode':['SYNTHETIC'], 'ContractDescription':['Synthetic option']}))
    result = run_example('docs/ime.md', 'certificates =')
    assert result['code'] == '0001' and calls[1][1] == {'instrument_code':'0001'}
    trades = pd.DataFrame({'ProducerName':['Synthetic producer'], 'GoodsName':['Synthetic goods'], 'JalaliDate':['1405-07-20']})
    substitute(monkeypatch, 'get_all_ime_physical_trades', trades)
    result = run_example('docs/ime.md', 'producers =')
    assert result['selected'].ProducerName.tolist() == ['Synthetic producer']


def test_ifb_catalog_payment_example(monkeypatch):
    substitute(monkeypatch, 'get_all_standard_financing_instruments', pd.DataFrame({'Ticker':['Synthetic bond']}))
    calls = substitute(monkeypatch, 'get_ticker_info', lambda *a, **k: (pd.DataFrame({'Value':['text']}), pd.DataFrame()))
    result = run_example('docs/ifb.md', 'selected = instruments.iloc')
    assert calls[0][0] == ('Synthetic bond',)
    assert result['info'].Value.tolist() == ['text']
