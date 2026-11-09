"""Opt-in official-response comparisons, with no fixed market/session counts."""
from decimal import Decimal
import json

import pandas as pd
import pytest

import fima.IFB as ifb
import fima._ifb_market_map as source


pytestmark = pytest.mark.integration


@pytest.mark.parametrize("metric", ["trade_volume", "trade_value", "transaction_count", "market_value"])
def test_live_market_map_full_selected_response(monkeypatch, metric):
    factory = source._session
    captured = []

    def capture():
        session = factory()
        request = session.request

        def record(method, url, **kwargs):
            response = request(method, url, **kwargs)
            captured.append((method, response))
            return response

        monkeypatch.setattr(session, "request", record)
        return session

    monkeypatch.setattr(source, "_session", capture)
    frame = ifb.get_ifb_market_map(metric)
    assert [method for method, _ in captured] == ["GET", "POST"]
    rows = json.loads(captured[-1][1].content, parse_float=Decimal)["d"]
    # Empty is a valid bounded source collection. Do not turn an HTTP or schema
    # failure into a skip or enforce a fixed historical universe size.
    assert len(frame) == frame.attrs["SourceRowCount"] == len(rows)
    assert frame.InstrumentID.is_unique
    assert "ObservationDate" not in frame.attrs and "Timestamp" not in frame
    for parsed, raw in zip(frame.itertuples(index=False), rows):
        assert parsed.InstrumentID == str(raw["id"])
        assert parsed.Ticker == raw["label"].strip()
        assert parsed.InstrumentName == raw["title"].strip()
        assert parsed.Market == raw["market"].strip()
        for field, key in [("MetricValue", "value"), ("ClosingPrice", "close"), ("EPS", "eps")]:
            value = getattr(parsed, field)
            assert pd.isna(value) if raw[key] is None else value == raw[key]
        for field, key in [("ClosingPercentageChange", "data"), ("PE", "ptoe")]:
            value = getattr(parsed, field)
            if raw[key] is None or (key == "ptoe" and raw[key] == 0):
                assert pd.isna(value)
            else:
                assert value == float(raw[key])
        if metric in ("trade_value", "market_value") and raw["value"] is not None:
            assert isinstance(parsed.MetricValue, Decimal)
    print(f"{metric}: {len(rows)} IDs; {frame.Market.nunique()} classifications; "
          f"{sum(r['value'] not in (None, 0) for r in rows)} nonzero measures")
