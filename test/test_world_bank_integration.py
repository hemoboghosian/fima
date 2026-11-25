"""Opt-in checks against the official WDI endpoints."""

import math

import pytest

from fima import WORLD_BANK as wb


pytestmark = pytest.mark.integration


@pytest.fixture
def captured(monkeypatch):
    """Capture the exact responses used by the public adapter in this call."""
    original = wb._Client.get
    responses = {}

    def get(client, path, page, params):
        if path.startswith("country/") and "IRN;USA;HIC" in path:
            with monkeypatch.context() as smaller:
                smaller.setattr(wb, "_PAGE_SIZE", 3)
                payload, url = original(client, path, page, params)
        else:
            payload, url = original(client, path, page, params)
        responses.setdefault(path, []).append(payload)
        return payload, url

    monkeypatch.setattr(wb._Client, "get", get)
    return responses


def test_source_geography_and_indicator_discovery(captured):
    source = wb.get_world_bank_sources().iloc[0]
    official = captured["source/2"][0][1][0]
    assert (source.SourceId, source.SourceCode, source.Source) == ("2", "WDI", "World Development Indicators")
    assert source.SourceUpdateDate == official["lastupdated"]

    countries = wb.get_world_bank_countries(include_aggregates=True).set_index("Country")
    dimensions = {}
    for page in captured["sources/2/country/data"]:
        dimensions.update({item["id"]: item["value"]
                           for item in page["source"][0]["concept"][0]["variable"]})
    assert countries.CountryName.to_dict() == dimensions
    assert countries.loc["IRN", "CountryCode2"] == "IR"
    assert countries.loc["USA", "GeographyType"] == "Economy"
    assert countries.loc["WLD", "GeographyType"] == "World"
    assert countries.loc["HIC", "GeographyType"] == "IncomeGroup"

    catalog = wb.get_world_bank_indicators().set_index("Indicator")
    pages = captured["source/2/indicator"]
    official = {item["id"]: item for _, rows in pages for item in rows}
    assert len(catalog) == int(pages[0][0]["total"]) == len(official)
    code = "FP.CPI.TOTL.ZG"
    assert catalog.loc[code, "IndicatorName"] == official[code]["name"]
    assert catalog.loc[code, "Description"] == official[code]["sourceNote"]
    assert "consumer price index" in catalog.loc[code, "Description"].casefold()


@pytest.mark.parametrize("code, geos, unit, definition_fragment", [
    ("NY.GDP.MKTP.CD", ["IRN", "USA", "BRA"], "current US$", "gross domestic product"),
    ("FP.CPI.TOTL.ZG", ["IRN", "USA", "HIC"], "%", "consumer price index"),
    ("FP.CPI.TOTL", ["IRN", "USA"], "index (2010 = 100)", "prices of consumption goods and services"),
    ("PA.NUS.FCRF", ["IRN", "BRA"], "LCU per US$", "official exchange rate"),
    ("FS.AST.PRVT.GD.ZS", ["IRN", "BRA"], "%", "private sector"),
    ("BX.KLT.DINV.WD.GD.ZS", ["IRN", "BRA"], "%", "divided by gdp"),
    ("DT.DOD.DECT.CD", ["IRN", "USA", "BRA"], "current US$", "external debt"),
])
def test_series_matches_the_official_responses(captured, code, geos, unit, definition_fragment):
    start, end = 2023, 2025
    frame = wb.get_world_bank_series(code, geos, start, end)
    path = f"country/{';'.join(geos)}/indicator/{code}"
    pages = captured[path]
    records = {(item["countrycode"], item["date"]): item for _, rows in pages for item in rows}
    assert len(frame) == len(records) == int(pages[0][0]["total"])
    assert frame.attrs["SourceUpdateDate"] == pages[0][0]["lastupdated"]
    assert frame.attrs["Pagination"]["Pages"] == len(pages)
    if "HIC" in geos:
        assert len(pages) > 1
        assert frame.loc[frame.Country == "HIC", "GeographyType"].unique().tolist() == ["IncomeGroup"]
        assert any(not row["countryiso3code"] for (country, _), row in records.items() if country == "HIC")

    official_indicator = captured[f"source/2/indicator/{code}"][0][1][0]
    assert official_indicator["source"]["id"] == "2"
    assert frame.attrs["IndicatorMetadata"]["Description"] == official_indicator["sourceNote"]
    metadata_pages = captured[f"sources/2/series/{code}/metadata"]
    definitions = [item["value"] for page in metadata_pages
                   for item in page["source"][0]["concept"][0]["variable"][0]["metatype"]
                   if item["id"] == "Longdefinition"]
    assert definitions == [frame.attrs["IndicatorMetadata"]["LongDefinition"]]
    assert definition_fragment in definitions[0].casefold()
    assert frame.Unit.unique().tolist() == [unit]
    for row in frame.itertuples(index=False):
        source = records[row.Country, row.Period]
        assert row.CountryName == source["country"]["value"]
        assert row.Indicator == source["indicator"]["id"] == code
        assert row.IndicatorName == official_indicator["name"]
        assert row.SourceId == "2" and row.Frequency == "A"
        assert start <= int(row.Period) <= end
        assert (math.isnan(row.Value) if source["value"] is None else row.Value == source["value"])

    for coverage in frame.attrs["Coverage"]:
        country = coverage["Country"]
        expected = tuple(str(year) for year in range(start, end + 1))
        assert coverage["ReturnedPeriods"] == tuple(p for p in expected if (country, p) in records)
        assert coverage["NullPeriods"] == tuple(p for p in coverage["ReturnedPeriods"]
                                               if records[country, p]["value"] is None)
        assert coverage["OmittedPeriods"] == tuple(p for p in expected if (country, p) not in records)
