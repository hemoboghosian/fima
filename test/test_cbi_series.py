"""Reduced DOM/XML examples from CBI's public inflation and advanced search."""
import inspect

import pandas as pd
import pytest
import requests

import fima
import fima.CBI as CBI


PREFIX = 'ctl00$ucBody$ucContent$ctl00$'
MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
          'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']


def inflation(year='1407', state='initial', rows=None):
    rows = rows if rows is not None else [('شهریور', '۶۸.۴'), ('فروردین', '۰')]
    options = ''.join(f'<option value="{y}" {"selected" if y == year else ""}>{y}</option>'
                      for y in ['1407', '1361'])
    return f'''<form method="post" action="./Inflation_FA.aspx">
    <input type="hidden" name="__VIEWSTATE" value="{state}">
    <input type="hidden" name="__EVENTVALIDATION" value="validation-{state}">
    <select name="{PREFIX}ddlYear">{options}</select>
    <table><tr><td>ماه</td><td>نرخ تورم</td></tr>
    {''.join(f'<tr><td>{m}</td><td>{r}</td></tr>' for m, r in rows)}</table>
    <table><tr><td>سال</td><td>نرخ تورم</td></tr>
    <tr><td>۱۴۰۴</td><td>۴۸.۳</td></tr><tr><td>1401(تغییر سال پایه)</td><td>۵۳.۱</td></tr>
    <tr><td>۱۳۱۵</td><td>-.-</td></tr></table></form>'''


def advanced(ets=False):
    prefix = PREFIX + ('ucForm2$' if ets else 'ucForm$')
    controls = ''
    for field in ['ddlStartDay', 'ddlEndDay', 'ddlStartMonth', 'ddlEndMonth',
                  'ddlStartYear', 'ddlEndYear']:
        values = ['', *map(str, range(1, 32))] if field.endswith('Day') else (
            ['', *map(str, range(1, 13))] if field.endswith('Month') else ['', '1405', '1407'])
        controls += f'<select name="{prefix}{field}">' + ''.join(
            f'<option value="{v}">{v}</option>' for v in values) + '</select>'
    controls += f'<select name="{prefix}ddlWeeks"><option value="0">آخرین روز</option></select>'
    if ets:
        controls += f'''<select name="{prefix}payTypeDropDown"><option value="اسکناس">اسکناس</option>
        <option value="حواله">حواله</option></select><select name="{prefix}payPriceDropDown">
        <option value="Buy">خرید</option><option value="Sell">فروش</option></select>'''
    currencies = [('USD', 'یک دلار آمریکا' if ets else 'دلار آمريکا'),
                  ('JPY' if ets else 'JPY100', 'یکصد ین ژاپن'),
                  ('LKR', 'ده روپیه سریلانکا' if ets else 'روپیه سریلانکا')]
    rows = ''.join(f'''<tr><td><input type="checkbox" name="{prefix}row{i}$chkCurrency"></td>
        <td>{code}</td><td>{name}<input type="hidden" name="{prefix}row{i}$hdnCurrencyID"
        value="{i}"></td></tr>''' for i, (code, name) in enumerate(currencies, 1))
    return f'''<form method="post" action="./{'etsratesadv' if ets else 'exratesadv'}_fa.aspx">
    <input type="hidden" name="__VIEWSTATE" value="fresh">
    {controls}<input type="radio" name="{prefix}Output" value="rdbHTML">
    <input type="radio" name="{prefix}Output" value="rdbXML">
    <input type="radio" name="{prefix}Output" value="rdbCSV">
    <input type="submit" name="{prefix}btnShowRateByDate" value="نرخ ارز">
    <input type="submit" name="{prefix}btnShowRateByWeek" value="نرخ ارز">
    <table><tr><td></td><td>کد ارز</td><td>عنوان ارز</td></tr>{rows}</table></form>'''


def xml(currencies=None, dates=('1405/07/27', '1405/07/25'), offset=0):
    currencies = currencies or [('USD', 'US Dollar')]
    return '<exchangerates>' + ''.join(
        f'<currency id="{code}" name="{name}"><summary id="Average"><date>range</date><value>999</value></summary>'
        + ''.join(f'<rate><date>{date}</date><value>{100 + offset + i}</value></rate>'
                  for i, date in enumerate(dates)) + '</currency>' for code, name in currencies) + '</exchangerates>'


@pytest.fixture
def provider(monkeypatch):
    state = dict(calls=[], initial=inflation(), monthly=inflation('1361', 'next'), error=None,
                 history=None, currencies=None, dates=('1405/07/27', '1405/07/25'))

    def request(session, method, url, **kwargs):
        state['calls'].append((method, url, kwargs))
        if state['error']:
            raise state['error']
        ets = '/etsratesadv/' in url
        if '/Inflation/' in url:
            text = state['initial'] if method == 'get' else state['monthly']
            if callable(text):
                text = text(kwargs['data'])
        elif method == 'get':
            text = state.get('advanced', advanced(ets))
        elif state['history'] is not None:
            text = state['history']
            if callable(text):
                text = text(kwargs['data'])
        else:
            prefix = PREFIX + ('ucForm2$' if ets else 'ucForm$')
            data = kwargs['data']
            offset = (20 if data.get(prefix+'payTypeDropDown') == 'حواله' else 0)
            offset += 10 if data.get(prefix+'payPriceDropDown') == 'Sell' else 0
            currencies = state['currencies'] or [('USD', 'US Dollar')]
            text = xml(currencies, state['dates'], offset)
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response._content = text.encode('utf-8')
        return response

    monkeypatch.setattr(requests.Session, 'get', lambda s, url, **kw: request(s, 'get', url, **kw))
    monkeypatch.setattr(requests.Session, 'post', lambda s, url, **kw: request(s, 'post', url, **kw))
    return state


def test_monthly_dynamic_future_years_and_postback(provider):
    result = fima.get_cbi_inflation_rates()
    assert list(result.columns) == ['JalaliMonth', 'InflationRate']
    assert result.JalaliMonth.tolist() == ['1361-01', '1361-06', '1407-01', '1407-06']
    assert result.InflationRate.tolist() == [0.0, 68.4, 0.0, 68.4]
    assert [str(d) for d in result.dtypes] == ['string', 'float64']
    payload = provider['calls'][1][2]['data']
    assert payload[PREFIX+'ddlYear'] == '1361'
    assert payload['__EVENTTARGET'] == PREFIX+'ddlYear'
    assert payload['__VIEWSTATE'] == 'initial'
    assert payload['__EVENTVALIDATION'] == 'validation-initial'


def test_all_months_and_exact_duplicates(provider):
    provider['initial'] = inflation(rows=[*zip(MONTHS, ['1']*12), ('فروردین', '1')])
    result = CBI.get_cbi_inflation_rates()
    assert result[result.JalaliMonth.str.startswith('1407')].JalaliMonth.tolist() == [
        f'1407-{m:02d}' for m in range(1, 13)]


def test_annual_notes_missing_values_and_no_fabricated_dates(provider):
    result = CBI.get_cbi_inflation_rates('annual')
    assert list(result.columns) == ['JalaliYear', 'InflationRate', 'Note']
    assert result.JalaliYear.tolist() == ['1315', '1401', '1404']
    assert result.Note.iloc[1] == 'تغییر سال پایه' and pd.isna(result.Note.iloc[0])
    assert pd.isna(result.InflationRate.iloc[0]) and result.InflationRate.iloc[2] == 48.3
    assert [str(d) for d in result.dtypes] == ['string', 'float64', 'string']
    assert len(provider['calls']) == 1


@pytest.mark.parametrize('frequency', ['daily', None, 1])
def test_invalid_frequency_before_io(provider, frequency):
    with pytest.raises(ValueError, match='frequency'):
        CBI.get_cbi_inflation_rates(frequency)
    assert not provider['calls']


@pytest.mark.parametrize('broken', ['<title>Request Rejected</title>', '<html>missing table</html>',
                                   inflation('1407'), inflation('1361', rows=[]),
                                   inflation('1361', rows=[('Unknown', '2')])])
def test_monthly_failure_never_returns_partial(provider, broken):
    provider['monthly'] = broken
    with pytest.raises(RuntimeError, match='1361'):
        CBI.get_cbi_inflation_rates()


def test_exchange_bounded_xml_history_dates_units_and_not_summary(provider):
    provider['currencies'] = [('JPY100', 'Japanese 100 Yens')]
    result = CBI.get_cbi_exchange_rates('JPY', '1405-07-25', '1405-07-27', jalali=True)
    assert list(result.columns) == ['JalaliDate', 'GregorianDate', 'CurrencyCode', 'CurrencyName',
                                     'CurrencyUnit', 'ExchangeRate']
    assert result.CurrencyCode.tolist() == ['JPY100', 'JPY100']
    assert result.CurrencyUnit.tolist() == [100, 100]
    assert result.ExchangeRate.tolist() == [101.0, 100.0]
    assert result.JalaliDate.tolist() == ['1405-07-25', '1405-07-27']
    assert result.GregorianDate.tolist() == [pd.Timestamp('2026-10-17'), pd.Timestamp('2026-10-19')]
    assert [str(d) for d in result.dtypes] == ['string', 'datetime64[ns]', 'string', 'string', 'int64', 'float64']
    assert len(provider['calls']) == 2
    data = provider['calls'][1][2]['data']
    assert data[PREFIX+'ucForm$Output'] == 'rdbXML'
    assert data[PREFIX+'ucForm$ddlStartDay'] == '25'
    assert PREFIX+'ucForm$row2$chkCurrency' in data
    assert PREFIX+'ucForm$chkSummary' not in data


def test_latest_default_and_exact_persian_currency_name(provider):
    CBI.get_cbi_exchange_rates('دلار آمریکا')
    data = provider['calls'][1][2]['data']
    assert data[PREFIX+'ucForm$ddlWeeks'] == '0'
    assert PREFIX+'ucForm$btnShowRateByWeek' in data


@pytest.mark.parametrize('transaction,expected', [('cash', ['cash']), ('transfer', ['transfer']),
                                                ('all', ['cash', 'transfer']), ('حواله', ['transfer'])])
def test_ets_wide_buy_sell_and_transaction_modes(provider, transaction, expected):
    result = CBI.get_cbi_ets_rates('USD', transaction)
    assert list(result.columns) == ['JalaliDate', 'GregorianDate', 'CurrencyCode', 'CurrencyName',
                                     'CurrencyUnit', 'TransactionType', 'BuyRate', 'SellRate']
    assert sorted(result.TransactionType.unique()) == expected
    assert (result.SellRate-result.BuyRate).eq(10).all()
    assert set(result.CurrencyUnit) == {1}
    assert len([c for c in provider['calls'] if c[0] == 'post']) == 2 * len(expected)
    assert len(provider['calls']) <= 4 * len(expected)


@pytest.mark.parametrize('code,unit', [('JPY', 100), ('LKR', 10)])
def test_ets_denominations_from_provider_description(provider, code, unit):
    provider['currencies'] = [(code, 'denominated currency')]
    result = CBI.get_cbi_ets_rates(code, 'cash')
    assert result.CurrencyUnit.eq(unit).all()
    assert result.BuyRate.tolist() == [101.0, 100.0]


def test_no_synthetic_missing_days_and_exact_deduplication(provider):
    provider['dates'] = ['1405/07/27', '1405/07/25', '1405/07/27']
    provider['history'] = xml(dates=['1405/07/27', '1405/07/25'])
    result = CBI.get_cbi_exchange_rates('USD')
    assert result.JalaliDate.tolist() == ['1405-07-25', '1405-07-27']
    assert '1405-07-26' not in result.JalaliDate.tolist()


@pytest.mark.parametrize('function', ['get_cbi_exchange_rates', 'get_cbi_ets_rates'])
@pytest.mark.parametrize('kwargs', [{'start_date':'2026-10-01'},
                                  {'start_date':'2026-10-20','end_date':'2026-10-01'},
                                  {'start_date':'2024-01-01','end_date':'2026-01-01'},
                                  {'start_date':'not a date','end_date':'2026-10-01'},
                                  {'jalali':'yes'}, {'currency':[]}])
def test_invalid_inputs_before_network(provider, function, kwargs):
    with pytest.raises(ValueError):
        getattr(CBI, function)(**kwargs)
    assert not provider['calls']


@pytest.mark.parametrize('function', ['get_cbi_exchange_rates', 'get_cbi_ets_rates'])
@pytest.mark.parametrize('bad', ['<title>Request Rejected</title>', '<html>malformed</html>',
                               '<exchangerates><currency id="USD"><rate><value>2</value></rate></currency></exchangerates>'])
def test_malformed_export_or_rejection_raises(provider, function, bad):
    provider['history'] = bad
    with pytest.raises(RuntimeError):
        getattr(CBI, function)('USD')


def test_invalid_transaction_and_unknown_currency(provider):
    with pytest.raises(ValueError, match='transaction_type'):
        CBI.get_cbi_ets_rates(transaction_type='spot')
    assert not provider['calls']
    with pytest.raises(ValueError, match='currency'):
        CBI.get_cbi_exchange_rates('not a currency')


def test_all_public_exports_and_signatures():
    names = {'get_cbi_policy_rates', 'get_cbi_inflation_rates', 'get_cbi_exchange_rates', 'get_cbi_ets_rates'}
    assert set(CBI.__all__) == names
    for name in names:
        assert getattr(fima, name) is getattr(CBI, name)
    assert str(inspect.signature(CBI.get_cbi_inflation_rates)) == "(frequency='monthly')"


def test_monthly_refreshed_state_and_initial_selected_year_reuse(provider):
    def three_years(year, state):
        return inflation(year, state).replace('<option value="1361"',
                    f'<option value="1406" {"selected" if year == "1406" else ""}>۱۴۰۶</option><option value="1361"')
    provider['initial'] = three_years('1407', 'first')
    provider['monthly'] = lambda data: three_years(data[PREFIX+'ddlYear'], 'updated')
    result = CBI.get_cbi_inflation_rates()
    assert len(result) == 6
    assert [c[2]['data']['__VIEWSTATE'] for c in provider['calls'][1:]] == ['first', 'updated']


def test_source_all_currency_catalog_and_multiple_filters(provider):
    provider['currencies'] = [('USD', 'US Dollar'), ('JPY100', 'Japanese 100 Yens'), ('LKR10', 'Sri Lanka 10 Rupees')]
    result = CBI.get_cbi_exchange_rates()
    assert set(result.CurrencyCode) == {'USD', 'JPY100', 'LKR10'}
    assert result.groupby('CurrencyCode').CurrencyUnit.first().to_dict() == {'USD':1, 'JPY100':100, 'LKR10':10}
    data = provider['calls'][1][2]['data']
    assert all(PREFIX+f'ucForm$row{i}$chkCurrency' in data for i in [1,2,3])
    provider['currencies'] = [('USD', 'US Dollar'), ('JPY100', 'Japanese 100 Yens')]
    result = CBI.get_cbi_exchange_rates(['USD', 'JPY100'])
    assert set(result.CurrencyCode) == {'USD', 'JPY100'}


def test_ets_all_currency_units_wide_types_and_numeric_persian_values(provider):
    provider['currencies'] = [('USD', 'one'), ('JPY', 'hundred'), ('LKR', 'ten')]
    result = CBI.get_cbi_ets_rates()
    assert len(result) == 12
    assert result.groupby('CurrencyCode').CurrencyUnit.first().to_dict() == {'USD':1,'JPY':100,'LKR':10}
    assert [str(d) for d in result.dtypes] == ['string','datetime64[ns]','string','string','int64','string','float64','float64']
    provider['history'] = xml().replace('<value>100</value>', '<value>۱٬۲۳۴٫۵</value>').replace('<value>101</value>','<value>۰</value>')
    result = CBI.get_cbi_ets_rates('USD', 'cash')
    assert result.BuyRate.tolist() == [0.0, 1234.5]
    assert result.SellRate.tolist() == [0.0, 1234.5]


def test_thousand_units_are_description_driven_not_a_currency_lookup(provider):
    provider['advanced'] = advanced(True).replace('ده روپیه سریلانکا', 'یک هزار روپیه سریلانکا')
    provider['currencies'] = [('LKR', 'thousand')]
    assert CBI.get_cbi_ets_rates('LKR','cash').CurrencyUnit.eq(1000).all()


def test_unknown_ets_denomination_fails_instead_of_assuming_one(provider):
    provider['advanced'] = advanced(True).replace('یکصد ین ژاپن','نامشخص ین ژاپن')
    with pytest.raises(RuntimeError,match='denomination'):
        CBI.get_cbi_ets_rates('JPY')


@pytest.mark.parametrize('function', ['get_cbi_exchange_rates','get_cbi_ets_rates'])
def test_valid_empty_export_has_documented_typed_schema(provider,function):
    provider['history'] = '<exchangerates/>'
    result = getattr(CBI,function)('USD')
    assert result.empty
    assert str(result.GregorianDate.dtype) == 'datetime64[ns]'
    assert str(result.CurrencyUnit.dtype) == 'int64'
    assert str(result.iloc[:,-1].dtype) == 'float64'


@pytest.mark.parametrize('bad', [xml().replace('<value>100</value>','<value>oops</value>'),
                               xml().replace('<value>100</value>','<value>inf</value>'),
                               xml().replace('1405/07/27','1405/13/01'),
                               xml([('EUR','Euro')]), '<exchangerates><unexpected/></exchangerates>'])
def test_bad_observations_are_not_provider_skips(provider,bad):
    provider['history'] = bad
    with pytest.raises(RuntimeError) as error:
        CBI.get_cbi_exchange_rates('USD')
    assert str(error.value.__cause__) != CBI._ACCESS_ERROR


def test_xml_date_range_must_be_respected(provider):
    provider['dates'] = ['1405/07/24']
    with pytest.raises(RuntimeError,match='outside'):
        CBI.get_cbi_exchange_rates('USD','1405-07-25','1405-07-27',jalali=True)


def test_duplicate_records_removed_but_repeated_rates_on_distinct_source_dates_kept(provider):
    one = '<rate><date>1405/07/23</date><value>200</value></rate>'
    next_day = '<rate><date>1405/07/24</date><value>200</value></rate>'
    provider['history'] = '<exchangerates><currency id="USD">'+one+one+next_day+'</currency></exchangerates>'
    result = CBI.get_cbi_ets_rates('USD','cash')
    assert result.JalaliDate.tolist() == ['1405-07-23','1405-07-24']
    assert result.BuyRate.tolist() == [200.0,200.0]


def test_conflicting_ets_side_records_fail(provider):
    provider['history'] = xml(dates=['1405/07/27','1405/07/27'])
    with pytest.raises(RuntimeError,match='conflicting'):
        CBI.get_cbi_ets_rates('USD','cash')


@pytest.mark.parametrize('function', ['get_cbi_inflation_rates','get_cbi_exchange_rates','get_cbi_ets_rates'])
def test_transport_errors_propagate_without_fallback_data(provider,function):
    provider['error'] = requests.Timeout('finite timeout')
    with pytest.raises(RuntimeError,match='timeout'):
        getattr(CBI,function)()


def test_persian_known_rejection_is_preserved(provider):
    provider['initial'] = '<title>درخواست رد شد</title>'
    with pytest.raises(RuntimeError) as error:
        CBI.get_cbi_inflation_rates()
    assert str(error.value.__cause__) == CBI._ACCESS_ERROR


def test_observed_normal_and_ets_rows_keep_exact_rates_and_denomination(provider):
    provider['history'] = ('<exchangerates><currency id="JPY100" name="Japanese 100 Yens">'
        '<rate><date>1405/07/27</date><value>1155888</value></rate></currency></exchangerates>')
    result = CBI.get_cbi_exchange_rates('JPY')
    assert result.CurrencyUnit.iloc[0] == 100 and result.ExchangeRate.iloc[0] == 1155888.0
    def ets_export(data):
        value = '1641552' if data[PREFIX+'ucForm2$payPriceDropDown'] == 'Sell' else '1626778'
        return ('<exchangerates><currency id="JPY                                 " name="One Hundred Japanese Yen">'
                f'<rate><date>1405/07/27</date><value>{value}</value></rate></currency></exchangerates>')
    provider['history'] = ets_export
    result = CBI.get_cbi_ets_rates('JPY','cash')
    assert result.CurrencyUnit.iloc[0] == 100 and result.CurrencyCode.iloc[0] == 'JPY'
    assert result.BuyRate.iloc[0] == 1626778.0 and result.SellRate.iloc[0] == 1641552.0


def test_one_ets_side_failing_aborts_the_whole_call(provider):
    def export(data):
        if data[PREFIX+'ucForm2$payPriceDropDown'] == 'Sell':
            return '<title>Request Rejected</title>'
        return xml()
    provider['history'] = export
    with pytest.raises(RuntimeError,match='cash Sell') as error:
        CBI.get_cbi_ets_rates('USD','cash')
    assert str(error.value.__cause__) == CBI._ACCESS_ERROR


def test_missing_ets_buy_sell_selector_is_not_silently_ignored(provider):
    provider['advanced'] = advanced(True).replace('payPriceDropDown','unexpected')
    with pytest.raises(RuntimeError,match='payPriceDropDown'):
        CBI.get_cbi_ets_rates('USD','cash')
