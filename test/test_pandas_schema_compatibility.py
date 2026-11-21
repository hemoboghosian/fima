"""Financial dtype contracts apply to pandas 2 and 3, without global options."""
import pandas as pd
import pytest

import fima.Funds as funds
import fima.IME as ime
from test.test_funds_coverage import public_fund
from test.test_funds_http import response
from test.test_funds_parent_identity import allocation_html


@pytest.mark.parametrize('value', [0, 1250, 9007199254740993])
def test_tadbir_replaces_numeric_columns_without_changing_values(monkeypatch, value):
    public_fund(monkeypatch, 'گروه رایانه تدبیر پرداز')
    html = allocation_html(f'{value:,}').replace('1 %', '2.5 %')

    def get(url, **kwargs):
        if url == 'https://fund.example':
            return response(text='<select id="basketId"><option value="2">Fund A</option></select>', url=url)
        assert url == 'https://fund.example/Reports/FundDailyAssetDistribution'
        assert kwargs['params'] == {'basketId': 2, 'page': 1}
        return response(text=html, url=url)

    monkeypatch.setattr(funds.requests, 'get', get)
    result = funds.get_daily_asset_allocation('Fund A')
    assert result.JalaliDate.tolist() == ['1405-07-19']
    for column in ['TopFiveStocks', 'OtherStocks', 'Bonds', 'CDs', 'CashAndBank', 'FundUnits', 'OtherAssets']:
        assert pd.api.types.is_integer_dtype(result[column])
        assert result[column].tolist() == [value]
        assert result[column + 'Weight'].tolist() == [2.5]  # Percentage points.
        assert pd.api.types.is_numeric_dtype(result[column + 'Weight'])


@pytest.mark.parametrize('unit', ['s', 'us', 'ns'])
def test_creation_timestamp_keeps_values_and_missing_with_ns_precision(unit):
    stamp = {'s': '2026-10-12T09:30:45', 'us': '2026-10-12T09:30:45.123456',
             'ns': '2026-10-12T09:30:45.123456789'}[unit]
    source = pd.Series([stamp, None], dtype=f'datetime64[{unit}]')
    result = ime._public_frame(pd.DataFrame({'CreateDateTime': source}))
    assert result.columns.tolist() == ['CreateDateTime']
    assert str(result.CreateDateTime.dtype) == 'datetime64[ns]'
    assert result.CreateDateTime.iloc[0] == source.iloc[0]
    assert pd.isna(result.CreateDateTime.iloc[1])


@pytest.mark.parametrize('values', [[], [None, None], ['invalid', None],
                                    ['3000-01-01', '1600-01-01', None]])
def test_empty_or_missing_creation_timestamps_keep_typed_schema(values):
    result = ime._public_frame(pd.DataFrame({'CreateDateTime': pd.Series(values, dtype=object)}))
    assert str(result.CreateDateTime.dtype) == 'datetime64[ns]'
    assert len(result) == len(values)
    assert result.CreateDateTime.isna().all()


def test_creation_timestamp_preserves_supplied_timezone_and_fractional_seconds():
    source = pd.Series(pd.DatetimeIndex(['2026-10-12T09:30:45.123456789+03:30', None]))
    result = ime._public_frame(pd.DataFrame({'CreateDateTime': source}))
    assert result.CreateDateTime.dtype.unit == 'ns'
    assert result.CreateDateTime.dt.tz == source.dt.tz
    assert result.CreateDateTime.iloc[0] == source.iloc[0]
    assert pd.isna(result.CreateDateTime.iloc[1])
