"""Opt-in live checks; only the recognized CBI access rejection is a visible skip."""
import json

import pandas as pd
import pytest

import fima.CBI as CBI

pytestmark = pytest.mark.integration


def test_live_complete_history_and_representative_dom_values(monkeypatch):
    captured = {}
    parse = CBI._parse_year

    def capture(soup, year):
        captured[year] = soup
        return parse(soup, year)

    monkeypatch.setattr(CBI, '_parse_year', capture)
    try:
        rates = CBI.get_cbi_policy_rates()
    except RuntimeError as exc:
        # Do not classify HTTP errors, timeouts, schema changes or parser bugs
        # as the known HTTP-200 rejection. Public callers still receive errors.
        if isinstance(exc.__cause__, ValueError) and str(exc.__cause__) == CBI._ACCESS_ERROR:
            pytest.skip(str(exc))
        raise
    assert not rates.empty
    assert rates.JalaliDate.is_monotonic_increasing and not rates.duplicated().any()
    assert rates.index.equals(pd.RangeIndex(len(rates)))
    assert list(rates.columns) == ['JalaliDate', 'GregorianDate', 'InterbankRate', 'RepoCutoffRate',
                                    'StandingLendingRate', 'StandingDepositRate']
    assert [str(d) for d in rates.dtypes] == ['string', 'datetime64[ns]'] + ['float64'] * 4
    # Discover advertised years independently from the captured live selector.
    first = next(iter(captured.values()))
    selector = first.find('select', attrs={'name': lambda n: n and n.endswith('$ddlYear')})
    digits = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
    years = [o['value'].translate(digits) for o in selector.find_all('option')
             if o.get('value') and not o.has_attr('disabled')]
    assert set(years) == set(captured)
    counts, raw_records = {}, []
    expected_headers = ['تاریخ', 'نرخ بازار بین‌بانکی(%)', 'حداقل نرخ توافق بازخرید(%)',
                        'نرخ اعتبارگیری قاعده‌مند(%)', 'نرخ سپرده‌گذاری قاعده‌مند(%)']

    def heading(text):
        return ''.join(text.split()).replace('\u200b', '').replace('\u200c', '')

    for year, soup in captured.items():
        container = soup.find(id=lambda value: value and value.endswith('_divRates'))
        table = container.find('table')
        # These are the observed DOM headings, not the browser's visual RTL order.
        assert [heading(h.get_text()) for h in table.find_all('th')] == list(map(heading, expected_headers))
        rows = table.select('tbody tr')
        assert rows
        counts[year] = len(rows)
        for row in rows:
            values = [c.get_text(strip=True).translate(digits) for c in row.find_all('td')]
            assert len(values) == 5
            raw_records.append([values[0].replace('/', '-'), *values[1:]])
    # Independently compare ALL four rate values for newest, middle and oldest years.
    ordered = sorted(years)
    samples = {}
    for year in [ordered[-1], ordered[len(ordered) // 2], ordered[0]]:
        source = next(row for row in raw_records if row[0].startswith(year + '-'))
        actual = rates.loc[rates.JalaliDate == source[0]].iloc[0]
        for column, value in zip(rates.columns[2:], source[1:]):
            if value in ('', '-', '—'):
                assert pd.isna(actual[column])
            else:
                assert actual[column] == float(value.replace('٫', '.').rstrip('%٪'))
        samples[year] = source
    unique_records = pd.DataFrame(raw_records).drop_duplicates()
    assert len(rates) == len(unique_records)
    assert rates.JalaliDate.min() == unique_records[0].min()
    assert rates.JalaliDate.max() == unique_records[0].max()
    print(json.dumps({'Years': years, 'RowsPerYear': counts, 'TotalRows': len(rates),
                      'EarliestDate': rates.JalaliDate.min(), 'LatestDate': rates.JalaliDate.max(),
                      'DuplicatesDetected': len(raw_records) - len(unique_records),
                      'Columns': list(rates.columns), 'Dtypes': {c: str(d) for c, d in rates.dtypes.items()},
                      'RepresentativeRowsInDOMOrder': samples}, ensure_ascii=True))
