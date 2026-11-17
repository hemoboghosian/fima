"""Opt-in small IMF comparisons; outages/schema failures are never skipped.

Run: python -m pytest -m integration test/test_imf_integration.py -v -s
Only user-selected indicators are requested; no datasets/archives are mirrored.
"""
import json
import time

import pandas as pd
import pytest

import fima.IMF as imf

pytestmark = pytest.mark.integration


@pytest.fixture
def capture(monkeypatch):
    original = imf._requests.get
    records = []

    def get(url, **kwargs):
        time.sleep(0.25)
        response = original(url, **kwargs)
        record = {"URL": url, "Chunks": []}
        records.append(record)
        chunks = response.iter_content

        def read(**read_kwargs):
            for chunk in chunks(**read_kwargs):
                record["Chunks"].append(chunk)
                yield chunk

        response.iter_content = read
        return response

    monkeypatch.setattr(imf._requests, "get", get)
    return records


@pytest.mark.parametrize("indicator,countries,start,end", [
    ("NGDP_RPCH", ["IRN", "USA"], 2024, 2027),
    ("PCPIPCH", ["IRN"], 2024, 2027),
    ("GGXWDG_NGDP", ["IRN", "USA"], 2024, 2027),
    ("GGXCNL_NGDP", ["IRN"], 2024, 2027),
    ("LUR", ["IRN", "USA"], 2024, 2027),
    ("NGDP_RPCH", ["IRN"], 1900, 1901),
])
def test_live_every_selected_value_and_metadata(capture, indicator, countries, start, end):
    frame = imf.get_imf_series(indicator, countries, start, end)
    raw = json.loads(b"".join(capture[-1]["Chunks"]))
    country_catalog = json.loads(b"".join(capture[1]["Chunks"]))["countries"]
    meta = raw["indicators"][indicator]
    expected = []
    for country in countries:
        for period, value in sorted(raw["values"][indicator][country].items()):
            if start <= int(period) <= end:
                expected.append((country, period, value))
    assert len(frame) == len(expected)
    for row, (country, period, value) in zip(frame.itertuples(index=False), expected):
        assert (row.Country, row.Period) == (country, period)
        assert pd.isna(row.Value) if value is None else row.Value == value
        assert row.CountryName == country_catalog[country]["label"]
        assert row.GeographyType == "Country" and row.Frequency == "A"
        assert row.Unit == meta["unit"]
    actual = frame.attrs["IndicatorMetadata"]
    for column, key in [("Source", "source"), ("SourceLastModified", "last-modified"),
                        ("SourceProjectionYear", "projection-year"), ("Description", "description")]:
        assert actual[column] == meta.get(key)
    assert actual["Dataset"] == "WEO" and frame.attrs["ObservationStatus"] == "Unknown"
    assert len(capture) == 3  # Catalog, countries, one selected indicator.
    print(indicator, countries, len(frame), actual["Source"], frame.Value.tolist())


def test_live_missing_country_coverage_and_catalogs(capture):
    # Source-wide geography discovery does not imply WEO unemployment coverage.
    with pytest.warns(RuntimeWarning, match="CUB"):
        frame = imf.get_imf_series("LUR", ["IRN", "CUB"], 2025, 2026)
    assert frame.Country.tolist() == ["IRN", "IRN"]
    assert not frame.attrs["Coverage"][1]["SourceSeriesPresent"]
    geo = imf.get_imf_countries(True).set_index("Country")
    assert geo.loc["IRN", "GeographyType"] == "Country"
    assert geo.loc["WEOWORLD", "GeographyType"] == "Group"
    indicators = imf.get_imf_indicators(search="current account")
    assert {"BCA", "BCA_NGDPD"} <= set(indicators.Indicator)
    datasets = imf.get_imf_datasets()
    assert datasets.Dataset.tolist() == ["WEO"] and datasets.IndicatorCount.iloc[0] >= 15
    world = imf.get_imf_series("NGDP_RPCH", "WEOWORLD", 2025, 2025)
    raw = json.loads(b"".join(capture[-1]["Chunks"]))
    assert world.GeographyType.tolist() == ["Group"]
    assert world.Value.tolist() == [raw["values"]["NGDP_RPCH"]["WEOWORLD"]["2025"]]
