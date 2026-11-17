"""Opt-in source comparisons; one captured public GET per selected history.

Run explicitly with pytest -m integration test/test_kilid_integration.py.
No outage/challenge/schema error is silently converted into a skip.
"""
from decimal import Decimal
import re
import time

from bs4 import BeautifulSoup
import pandas as pd
import pytest

import fima.KILID as kilid

pytestmark = pytest.mark.integration


@pytest.fixture
def capture(monkeypatch):
    original = kilid._requests.get
    responses = []

    def get(url, **kwargs):
        time.sleep(1)  # Bounded, modest request rate, no retries or circumvention.
        response = original(url, **kwargs)
        responses.append(response)
        return response

    monkeypatch.setattr(kilid._requests, 'get', get)
    return responses


def text_number(text, suffix):
    # Independent comparison of every displayed cell, not just nonempty output.
    value = text.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))
    value = re.sub('[\u200e\u200f]', '', value).strip().replace('−', '-').replace('٪', '%')
    if value in ('—', '–', '-', 'بدون داده'):
        return None
    assert value.endswith(suffix)
    value = value[:-len(suffix)].strip() if suffix else value
    scale = 1
    for word, multiple in [('میلیارد', 10**9), ('میلیون', 10**6), ('هزار', 10**3)]:
        if value.endswith(word):
            scale = multiple
            value = value[:-len(word)].strip()
            break
    return float(Decimal(value.replace('٬', '').replace(',', '').replace('٫', '.')) * scale)


@pytest.mark.parametrize('area,period,denomination', [
    ('tehran-region5', '3y', 'toman'),
    ('tehran-region5', '3y', 'usd'),
    ('tehran-region5', '3y', 'gold'),
    ('tehran-region5', '6m', 'usd'),
    ('tehran-region1', '1y', 'toman'),
    ('tehran-region5-moradabad', '1y', 'toman'),
])
def test_live_complete_numerical_history(capture, area, period, denomination):
    frame = kilid.get_kilid_house_price_history(area, period, denomination)
    assert len(capture) == 1
    soup = BeautifulSoup(capture[0].content, 'html.parser')
    rows = soup.select('[data-testid="trend-table"] tbody tr')
    assert len(rows) == len(frame) == frame.attrs['SourceRowCount']
    assert frame.JalaliMonth.is_unique
    suffix = {'toman': 'تومان', 'usd': 'دلار', 'gold': 'گرم'}[denomination]
    months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
              'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
    for raw, parsed in zip(rows, frame.itertuples(index=False)):
        label = raw.th.get_text(' ', strip=True).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
        month, year = [p.strip() for p in label.split('-')]
        assert parsed.JalaliMonth == f'{int(year):04d}-{months.index(month)+1:02d}'
        expected = text_number(raw.td.get_text(' ', strip=True), suffix)
        assert pd.isna(parsed.MedianListingPricePerSquareMeter) if expected is None else parsed.MedianListingPricePerSquareMeter == expected
        assert parsed.Area == area
    print(area, period, denomination, len(frame), frame.JalaliMonth.iloc[[0, -1]].tolist(),
          frame.MedianListingPricePerSquareMeter.iloc[[0, -1]].tolist())


def test_live_discovery_comparison_and_snapshot(capture):
    cities = kilid.get_kilid_areas()
    assert 'tehran' in set(cities.Area)
    comparison = kilid.get_kilid_area_comparison('tehran-region5')
    soup = BeautifulSoup(capture[-1].content, 'html.parser')
    raw = soup.select('[data-testid="area-comparison"] tr[data-testid="comparison-row"]')
    assert len(comparison) == len(raw)
    for row, parsed in zip(raw, comparison.itertuples(index=False)):
        assert parsed.SourceURL == 'https://kilid.com' + row.select_one('a[data-testid="comparison-link"]')['href']
        expected = text_number(row.find_all('td', recursive=False)[0].get_text(' ', strip=True), 'تومان')
        assert pd.isna(parsed.PublishedPricePerSquareMeterToman) if expected is None else parsed.PublishedPricePerSquareMeterToman == expected
    snapshot = kilid.get_kilid_house_price_snapshot('tehran-region5-moradabad')
    soup = BeautifulSoup(capture[-1].content, 'html.parser')
    raw = {r.dt.get_text(' ', strip=True): r.find('dd').get_text(' ', strip=True)
           for r in soup.select('[data-testid="market-stat"]')}
    value = snapshot.set_index('Metric').loc['MedianListingPricePerSquareMeter', 'Value']
    assert value == text_number(raw['میانه قیمت هر متر مربع در آگهی‌ها'], 'تومان')
    print('Public cities:', len(cities), 'Region 5 comparisons:', len(comparison), 'snapshot metrics:', len(snapshot))
