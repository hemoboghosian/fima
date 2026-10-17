"""Small opt-in live contract checks; provider outages must remain visible."""
import datetime as dt

import pandas as pd
import pytest

import fima.TGJU as TGJU

pytestmark = pytest.mark.integration


@pytest.mark.parametrize('instrument,category', [
    ('دلار', 'ارز'),
    ('طلای 18 عیار / 750', 'طلا'),
    ('سکه امامی', 'سکه'),
    ('نفت برنت', 'انرژی'),
    ('بیت کوین', 'ارز دیجیتال'),
])
def test_live_snapshot_details_and_daily_history(monkeypatch, instrument, category):
    captured = []
    original = TGJU._Client.get

    def get(client, url, *args, **kwargs):
        result = original(client, url, *args, **kwargs)
        captured.append((url, result))
        return result

    monkeypatch.setattr(TGJU._Client, 'get', get)
    instruments = TGJU.get_tgju_instruments(category, search=instrument)
    assert not instruments.empty
    market = TGJU.get_tgju_market(category, search=instrument)
    exact = market[market.Name.map(TGJU._norm) == TGJU._norm(instrument)]
    assert len(exact) == 1
    quote = exact.iloc[0]
    assert quote.HasSnapshot and pd.notna(quote.Price)
    raw_quotes = [q for url, result in captured if url.endswith('/widget/tmp') for q in result['response']['indicators']]
    assert any(TGJU._number(q.get('p')) == quote.Price for q in raw_quotes if TGJU._norm(q['title']) == TGJU._norm(instrument))

    history = TGJU.get_tgju_history(instrument, category, start_date=(dt.date.today() - dt.timedelta(days=30)))
    assert not history.empty and history.Date.is_monotonic_increasing
    assert history.attrs['Currency'] == quote.Currency
    # TGJU currently leaves the crypto profile's volume unit blank.
    assert history.attrs['Unit'] is None or isinstance(history.attrs['Unit'], str)
    assert history.attrs['ProfileURL'].startswith('https://www.tgju.org/profile/')
    raw_rows = [r for url, result in captured if 'summary-table-data' in url for r in result['data']]
    for _, row in history.iterrows():
        assert any(TGJU._date(raw[6]) == row.Date and
                   [TGJU._number(value) for value in raw[:4]] == [row.Open,row.Low,row.High,row.Close]
                   for raw in raw_rows)
