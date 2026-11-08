"""Opt-in source comparisons; no fixed quote/date/count assumptions."""
import csv
from io import StringIO
import re

from bs4 import BeautifulSoup
import pandas as pd
import pytest

import fima.IFB as ifb
import fima._ifb_market_values as source


pytestmark = pytest.mark.integration


@pytest.fixture
def capture_source(monkeypatch):
    factory = source._session
    captured = []

    def capture():
        session = factory()
        request = session.request

        def record(method, url, **kwargs):
            response = request(method, url, **kwargs)
            captured.append((method, url, kwargs, response))
            return response

        monkeypatch.setattr(session, "request", record)
        return session

    monkeypatch.setattr(source, "_session", capture)
    return captured


def test_live_industry_and_constituent_source_values(capture_source):
    summary = ifb.get_ifb_market_values()
    symbols = ifb.get_ifb_symbol_market_values()
    assert not summary.empty and not symbols.empty
    soup = BeautifulSoup(capture_source[-1][3].content, "html.parser")
    rows = soup.select("#ContentPlaceHolder1_tblContainer tr.grpData")
    assert len(symbols) == len(rows)
    for parsed, row in zip(symbols.itertuples(index=False), rows):
        cells = row.find_all("td", recursive=False)
        assert parsed.InstrumentID == re.search(r"id=(\d+)", cells[0].a["href"])[1]
        assert parsed.MarketValue == int(cells[2]["title"].replace(",", ""))
        assert parsed.Market == cells[3].get_text(strip=True)
        assert parsed.Industry == cells[4].get_text(strip=True)
    # Independent source arrays/counts; snapshots were separate requests, so do
    # not require their financial totals to be identical during market updates.
    assert summary.SymbolCount.sum() > 0
    assert not symbols.InstrumentID.duplicated().any()


def test_live_market_snapshot_source_values(capture_source):
    frame = ifb.get_ifb_market_values("market")
    soup = BeautifulSoup(capture_source[0][3].content, "html.parser")
    rows = soup.select("#ContentPlaceHolder1_tblContainer table tr")[1:-1]
    assert len(frame) == len(rows)
    for parsed, row in zip(frame.itertuples(index=False), rows):
        cells = row.find_all("td", recursive=False)
        assert parsed.MarketValue == int(cells[2]["title"].replace(",", ""))
        assert parsed.SymbolCount == int(cells[1]["title"].replace(",", ""))
    assert frame.SymbolCount.sum() == frame.attrs["TotalSymbolCount"]


def test_live_history_whole_exports_and_exact_values(capture_source):
    frame = ifb.get_ifb_market_value_history()
    exports = [r for method, _, _, r in capture_source if method == "POST"]
    assert len(exports) == 3 and not frame.empty
    assert not frame.JalaliDate.duplicated().any()
    assert str(frame.TotalMarketValue.dtype) == "Int64"
    assert frame.GregorianDate.is_monotonic_increasing
    for regime, response in zip(("ColoredBase", "LetterBase", "LegacyBase"), exports):
        rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))[1:]
        assert len(rows) == frame.attrs["ExportRowCounts"][regime]
        subset = frame[frame.MarketRegime.eq(regime)].set_index("JalaliDate")
        assert len(subset) == len({row[0] for row in rows})
        for row in rows:
            value = subset.loc[row[0].replace("/", "-"), "TotalMarketValue"]
            if row[1]:
                assert value == int(row[1])
            else:
                assert pd.isna(value)
