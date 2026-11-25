import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import inspect
import subprocess
import sys
from urllib.parse import parse_qs, urlsplit

import pandas as pd
import pytest
import requests

import fima
from fima import WORLD_BANK as wb


CPI = "FP.CPI.TOTL.ZG"
SOURCE = "World Development Indicators"
CPI_NAME = "Inflation, consumer prices (annual %)"
UPDATE = "2026-11-11"
DATA_PATH = f"country/IRN;USA/indicator/{CPI}"
META_PATH = f"sources/2/series/{CPI}/metadata"


def page(rows, *, number=1, pages=1, size=500, total=None, **extra):
    return {"page": number, "pages": str(pages), "per_page": str(size),
            "total": len(rows) if total is None else total, **extra}


def catalog(rows, **kwargs):
    return [page(rows, **kwargs), rows]


def dimension(rows, *, concept="country", **kwargs):
    return {**page(rows, **kwargs), "source": [{"id": "2", "name": SOURCE,
            "concept": [{"id": concept, "variable": rows}]}]}


def geography(code, iso2, name, region="LCN"):
    return {"id": code, "iso2Code": iso2, "name": name,
            "region": {"id": region, "value": "Aggregates" if region == "NA" else "Region "},
            "adminregion": {"id": "EAP" if code == "IRN" else "", "value": ""},
            "incomeLevel": {"id": "HIC", "value": "High income"},
            "lendingType": {"id": "IBD", "value": "IBRD"}}


def indicator(code=CPI, name=CPI_NAME, **updates):
    return {"id": code, "name": name, "source": {"id": "2", "value": SOURCE},
            "sourceNote": "Annual percentage change in a consumer basket.", "unit": "",
            "sourceOrganization": "International Monetary Fund",
            "topics": [{"id": "3", "value": "Economy & Growth"},
                       {"id": "7", "value": "Financial Sector "}], **updates}


def rich(code=CPI, **updates):
    fields = {"IndicatorName": "Inflation, consumer prices (annual % growth)",
              "Dataset": "WB_WDI", "Longdefinition": "Annual percentage change in the CPI.",
              "Periodicity": "Annual", "Referenceperiod": "1960-2025", "Unitofmeasure": "%",
              "License_Type": "CC BY-4.0", "License_URL": "https://example.test/license", **updates}
    return dimension([{"id": code, "metatype": [{"id": key, "value": value}
                      for key, value in fields.items() if value is not None]}], concept="Series",
                     total=sum(value is not None for value in fields.values()))


def observation(geo="IRN", year="2024", value=32.4558714029169, code=CPI, **updates):
    iso2, label = {"IRN": ("IR", "Iran, Islamic Rep."), "USA": ("US", "United States"),
                   "HIC": ("XD", "High income"), "BRA": ("BR", "Brazil")}[geo]
    return {"indicator": {"id": code, "value": CPI_NAME},
            "country": {"id": iso2, "value": label}, "countrycode": geo,
            "countryiso3code": "" if geo == "HIC" else geo,
            "date": year, "value": value, "unit": "", "obs_status": "", "decimal": 1,
            "footnote": "", **updates}


def observations(rows, **kwargs):
    return catalog(rows, **{"sourceid": "2", "lastupdated": UPDATE, **kwargs})


@pytest.fixture
def wire(monkeypatch):
    source = {"id": "2", "code": "WDI", "name": SOURCE, "lastupdated": UPDATE,
              "dataavailability": "Y", "metadataavailability": "N"}
    countries = [geography("IRN", "IR", "Iran, Islamic Rep."), geography("USA", "US", "United States"),
                 geography("XKX", "XK", "Kosovo"), geography("HIC", "XD", "High income", "NA"),
                 geography("EAP", "4E", "East Asia & Pacific (excluding high income)", "NA"),
                 geography("IBD", "XF", "IBRD", "NA"), geography("WLD", "1W", "World", "NA"),
                 geography("OED", "OE", "OECD members", "NA"), geography("ZZZ", "XX", "Outside WDI")]
    membership = [{"id": row["id"], "value": row["name"]} for row in countries[:-1]]
    membership.append({"id": "NEW", "value": "New WDI geography"})
    routes = {
        ("source/2", 1): catalog([source]),
        ("country", 1): catalog(countries),
        ("sources/2/country/data", 1): dimension(membership),
        ("incomelevel", 1): catalog([{"id": "HIC", "value": "High income"}]),
        ("lendingtype", 1): catalog([{"id": "IBD", "value": "IBRD"}]),
        ("region", 1): catalog([{"code": "EAP", "name": "East Asia & Pacific"},
                                {"code": "OED", "name": "OECD members"}]),
        ("source/2/indicator", 1): catalog([indicator()]),
        (f"source/2/indicator/{CPI}", 1): catalog([indicator()]),
        (META_PATH, 1): rich(),
        (DATA_PATH, 1): observations([
            observation(), observation("USA", "2025", None),
            observation("IRN", "2023", 0, obs_status="F", footnote=" Publisher note "),
            observation("USA", "2023", -1.25),
        ]),
    }
    calls = []
    closed = []

    def get(_session, url, **kwargs):
        assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
        assert all(0 < timeout <= 30 for timeout in kwargs["timeout"])
        parts = urlsplit(url)
        assert parts.scheme == "https" and parts.netloc == "api.worldbank.org"
        path = parts.path.removeprefix("/v2/")
        query = {key: values[0] for key, values in parse_qs(parts.query).items()}
        assert query["format"] == "json"
        calls.append((path, query))
        item = routes[path, int(query["page"])]
        if callable(item):
            item = item()
        if isinstance(item, BaseException):
            raise item
        status, headers, body = item if isinstance(item, tuple) else (200, {}, item)
        response = requests.Response()
        response.status_code = status
        response.url = url
        response.headers.update({"Content-Type": "application/json", **headers})
        response._content = body if isinstance(body, bytes) else json.dumps(body).encode()
        response._content_consumed = True
        response.close = lambda: closed.append(url)
        return response

    monkeypatch.setattr(requests.Session, "get", get)
    return routes, calls, closed


def test_sources(wire):
    frame = wb.get_world_bank_sources()
    assert frame.iloc[0].to_dict() == {
        "SourceId": "2", "SourceCode": "WDI", "Source": SOURCE, "SourceUpdateDate": UPDATE,
        "DataAvailable": True, "MetadataAvailable": False, "SourceURL": frame.attrs["SourceURL"],
    }
    assert frame.attrs["SourceUpdateDate"] == UPDATE
    assert frame.attrs["RequestURLs"] == (frame.attrs["SourceURL"],)


@pytest.mark.parametrize("field, bad_value, message", [
    ("id", "02", "WDI source 2"), ("code", "IDS", "unexpected source code"),
    ("dataavailability", True, "invalid WDI availability flag"),
])
def test_source_catalog_rejects_mismatches(wire, field, bad_value, message):
    wire[0]["source/2", 1][1][0][field] = bad_value
    with pytest.raises(RuntimeError, match=message):
        wb.get_world_bank_sources()


def test_geography_membership_and_aggregate_types(wire):
    assert wb.get_world_bank_countries()["Country"].tolist() == ["IRN", "USA", "XKX"]
    assert wb.get_world_bank_countries(search=" xK ")["CountryCode2"].tolist() == ["XK"]
    all_rows = wb.get_world_bank_countries(True).set_index("Country")
    assert all_rows["GeographyType"].to_dict() == {
        "EAP": "Region", "HIC": "IncomeGroup", "IBD": "LendingGroup", "IRN": "Economy",
        "NEW": "Unknown", "OED": "OtherAggregate", "USA": "Economy", "WLD": "World", "XKX": "Economy",
    }
    assert all_rows.loc["IRN", "Region"] == "Region "
    assert all_rows.loc[["HIC", "NEW"], ["Region", "IncomeLevel", "LendingType"]].isna().all().all()


def test_nested_geography_pages_reconcile(wire):
    routes, _, _ = wire
    path = "sources/2/country/data"
    members = routes[path, 1]["source"][0]["concept"][0]["variable"]
    routes[path, 1] = dimension(members[:5], pages=2, size=5, total=len(members))
    routes[path, 2] = dimension(members[5:], number=2, pages=2, size=5, total=len(members))
    assert len(wb.get_world_bank_countries(include_aggregates=True)) == len(members)
    routes[path, 2]["source"][0]["concept"][0]["variable"][0] = members[0]
    with pytest.raises(RuntimeError, match="duplicate record"):
        wb.get_world_bank_countries(include_aggregates=True)


def test_indicator_catalog_search_reconciles_every_page(wire):
    routes, calls, _ = wire
    routes["source/2/indicator", 1] = catalog([indicator("NY.GDP.MKTP.CD", "GDP (current US$)")],
                                              size=1, total=2, pages=2)
    routes["source/2/indicator", 2] = catalog([indicator()], number="2", size=1, total="2", pages=2)
    result = wb.get_world_bank_indicators("financial sector")
    assert result["Indicator"].tolist() == [CPI, "NY.GDP.MKTP.CD"]
    assert result.iloc[0]["Topics"] == ("Economy & Growth", "Financial Sector ")
    assert result.iloc[0]["TopicIds"] == ("3", "7")
    assert result["Unit"].isna().all()
    assert wb.get_world_bank_indicators("GDP (")["Indicator"].tolist() == ["NY.GDP.MKTP.CD"]
    assert wb.get_world_bank_indicators(".*").empty
    assert [q["page"] for p, q in calls if p == "source/2/indicator"] == ["1", "2"] * 3


def test_annual_values_and_coverage(wire):
    _, calls, _ = wire
    result = wb.get_world_bank_series(" fp.cpi.totl.zg ", [" irn ", "usa"], 2023, 2025)
    assert list(zip(result.Country, result.Period)) == [
        ("IRN", "2023"), ("IRN", "2024"), ("USA", "2023"), ("USA", "2025")]
    assert result.Value.iloc[:3].tolist() == [0, 32.4558714029169, -1.25]
    assert result.Value.isna().tolist() == [False, False, False, True]
    assert result.Unit.tolist() == ["%"] * 4
    assert result.iloc[0]["ObservationStatus"] == "F"
    assert result.iloc[0]["Footnote"] == " Publisher note "
    assert set(result.IndicatorName) == {CPI_NAME}
    assert result.attrs["IndicatorMetadata"]["MetadataIndicatorName"] == "Inflation, consumer prices (annual % growth)"
    assert result.attrs["Coverage"] == (
        {"Country": "IRN", "ReturnedPeriods": ("2023", "2024"), "NullPeriods": (), "OmittedPeriods": ("2025",)},
        {"Country": "USA", "ReturnedPeriods": ("2023", "2025"), "NullPeriods": ("2025",), "OmittedPeriods": ("2024",)},
    )
    assert result.attrs["Completeness"] == "ProviderCountsReconciled"
    assert result.attrs["SourceUpdateDate"] == UPDATE
    assert calls[-1][1] == {"format": "json", "page": "1", "per_page": "500", "source": "2",
                            "date": "2023:2025", "ctrycode": "y", "footnote": "y", "scale": "n"}


@pytest.mark.parametrize(("name", "signature", "schema"), [
    ("sources", "()",
     "SourceId SourceCode Source SourceUpdateDate DataAvailable:boolean MetadataAvailable:boolean SourceURL"),
    ("countries", "(include_aggregates: bool = False, *, search: str | None = None, "
     "source: Literal['WDI'] = 'WDI')",
     "Country CountryName CountryCode2 GeographyType Region IncomeLevel LendingType SourceId"),
    ("indicators", "(search: str | None = None, *, source: Literal['WDI'] = 'WDI')",
     "Indicator IndicatorName Description SourceId Source SourceOrganization Unit TopicIds:object Topics:object"),
    ("series", "(indicator: str, countries: str | list[str] | tuple[str, ...], start_year: int, "
     "end_year: int, *, source: Literal['WDI'] = 'WDI')",
     "Country CountryName GeographyType Indicator IndicatorName SourceId Source Period Frequency "
     "Value:float64 Unit ObservationStatus Footnote Decimals:Int64"),
])
def test_schema_and_public_signature(wire, name, signature, schema):
    function = getattr(wb, f"get_world_bank_{name}")
    assert getattr(fima, function.__name__) is function
    public_signature = inspect.signature(function)
    assert public_signature.return_annotation is pd.DataFrame
    assert str(public_signature.replace(return_annotation=inspect.Signature.empty)) == signature
    columns = [field.split(":", 1) for field in schema.split()]
    populated = function(CPI, ["IRN", "USA"], 2023, 2025) if name == "series" else function()
    frames = [populated]
    if name == "series":
        routes, _, _ = wire
        routes[DATA_PATH, 1] = [{"page": 0, "pages": 0, "per_page": 0, "total": 0,
                                 "sourceid": None, "lastupdated": None}, None]
        frames.append(function(CPI, ("IRN", "USA"), 2023, 2025))
        assert frames[-1].attrs["SourceUpdateDate"] is None
        assert frames[-1].attrs["Coverage"][0]["OmittedPeriods"] == ("2023", "2024", "2025")
        assert frames[-1].attrs["Pagination"] == dict(AdvertisedRecords=0, ReturnedRecords=0, Pages=0, PageSize=0)
    elif name != "sources":
        frames.append(function(search="no search match"))
    assert len(frames[0]) and (len(frames) == 1 or frames[1].empty)
    for frame in frames:
        assert isinstance(frame.index, pd.RangeIndex)
        assert list(frame.columns) == [column[0] for column in columns]
        assert list(map(str, frame.dtypes)) == [column[1] if len(column) == 2 else "string" for column in columns]
        assert frame.attrs["Provider"] == "World Bank" and frame.attrs["SourceId"] == "2"
        assert datetime.fromisoformat(frame.attrs["RetrievedAt"]).utcoffset() == timedelta(0)
        assert frame.attrs["SourceURL"] in frame.attrs["RequestURLs"]
        assert frame.attrs["DatasetURL"].startswith("https://datacatalog.worldbank.org/")
        assert frame.attrs["License"] == "CC BY 4.0"


def test_import_has_no_http():
    subprocess.run([sys.executable, "-c", """
import requests
def forbidden(*args, **kwargs):
    raise AssertionError('HTTP during import')
requests.sessions.Session.request = forbidden
import fima
import fima.WORLD_BANK
"""], check=True)


def test_placeholders_have_empty_topic_tuples(wire):
    routes, _, _ = wire
    routes["source/2/indicator", 1] = catalog([indicator("IC.MNG.IND", topics=[{}])])
    record = wb.get_world_bank_indicators().iloc[0]
    assert record.TopicIds == record.Topics == ()


def test_catalog_indicator_spelling_is_preserved(wire):
    code = "per_allsp.cov_pop_tot"
    routes, _, _ = wire
    routes["source/2/indicator", 1] = catalog([indicator(code)])
    routes[f"source/2/indicator/{code.upper()}", 1] = catalog([indicator(code)])
    routes[f"sources/2/series/{code}/metadata", 1] = rich(code)
    routes[f"country/IRN/indicator/{code}", 1] = observations([observation(code=code)])
    assert wb.get_world_bank_indicators(search=code.upper()).Indicator.tolist() == [code]
    assert wb.get_world_bank_series(f"  {code}  ", "IRN", 2024, 2024).Indicator.tolist() == [code]


@pytest.mark.parametrize("arguments, keywords, message", [
    ((CPI, "IRN", 2024, 2025), {"source": "IDS"}, "Unsupported"),
    (("CPI;GDP", "IRN", 2024, 2025), {}, "Invalid indicator"),
    (("İ.S", "IRN", 2024, 2025), {}, "Invalid indicator"),
    ((CPI, "IRN;USA", 2024, 2025), {}, "Invalid geography"),
    ((CPI, "IR", 2024, 2025), {}, "Invalid geography"),
    ((CPI, "all", 2024, 2025), {}, "wildcard"),
    ((CPI, [], 2024, 2025), {}, "one to 20"),
    ((CPI, ["IRN"] * 21, 2024, 2025), {}, "one to 20"),
    ((CPI, ["IRN", " irn "], 2024, 2025), {}, "distinct"),
    ((CPI, "IRN", True, 2025), {}, "integers"),
    ((CPI, "IRN", 1959, 2025), {}, "integers"),
    ((CPI, "IRN", 2025, 2024), {}, "integers"),
    ((CPI, "IRN", 2025, 9999), {}, "integers"),
])
def test_argument_failures_make_no_requests(wire, arguments, keywords, message):
    with pytest.raises(ValueError, match=message):
        wb.get_world_bank_series(*arguments, **keywords)
    assert wire[1] == []


@pytest.mark.parametrize("function, arguments", [
    (wb.get_world_bank_countries, {"include_aggregates": 1}),
    (wb.get_world_bank_indicators, {"search": " "}),
    (wb.get_world_bank_countries, {"search": 2}),
    (wb.get_world_bank_countries, {"source": "2"}),
])
def test_invalid_discovery_arguments(wire, function, arguments):
    with pytest.raises(ValueError):
        function(**arguments)
    assert wire[1] == []


def test_valid_catalog_distinguishes_unknown_indicator_from_provider_error(wire):
    routes, _, _ = wire
    error = [{"message": [{"id": "120", "value": "Invalid value"}]}]
    routes["source/2/indicator/ZX.UNKNOWN", 1] = error
    routes[f"source/2/indicator/{CPI}", 1] = error
    with pytest.raises(ValueError, match="Unknown WDI indicator .*ZX.UNKNOWN"):
        wb.get_world_bank_series("ZX.UNKNOWN", "IRN", 2024, 2024)
    with pytest.raises(RuntimeError, match="HTTP 200 provider error 120"):
        wb.get_world_bank_series(CPI, "IRN", 2024, 2024)


def test_geography_outside_wdi_rejected(wire):
    with pytest.raises(ValueError, match="Unknown WDI geographies .*ZZZ"):
        wb.get_world_bank_series(CPI, ["IRN", "ZZZ"], 2024, 2024)


def test_nonannual_and_absent_periodicity(wire):
    routes, _, _ = wire
    routes[META_PATH, 1] = rich(Periodicity="Quarterly")
    with pytest.raises(ValueError, match="Quarterly"):
        wb.get_world_bank_series(CPI, "IRN", 2024, 2024)
    routes[META_PATH, 1] = rich(Periodicity=None)
    routes[f"country/IRN/indicator/{CPI}", 1] = observations([observation()])
    frame = wb.get_world_bank_series(CPI, "IRN", 2024, 2024)
    assert frame.Frequency.tolist() == ["A"]
    assert frame.attrs["IndicatorMetadata"]["Periodicity"] is None


def test_aggregate_blank_iso3_and_source_null(wire):
    routes, _, _ = wire
    routes[f"country/HIC;IRN/indicator/{CPI}", 1] = observations([
        observation(value=None), observation("HIC", value=2.38158383281173),
    ])
    frame = wb.get_world_bank_series(CPI, ["HIC", "IRN"], 2024, 2024)
    assert frame.GeographyType.tolist() == ["IncomeGroup", "Economy"]
    assert frame.Value.iloc[0] == 2.38158383281173
    assert frame.attrs["Coverage"][1]["NullPeriods"] == ("2024",)


def test_pages_for_series_and_nested_metatypes(wire):
    routes, calls, _ = wire
    records = [observation(), observation("USA", "2025", None), observation("IRN", "2025", 1)]
    routes[DATA_PATH, 1] = observations(records[:2], size=2, pages=2, total=3)
    routes[DATA_PATH, 2] = observations(records[2:], number="2", size=2, pages=2, total="3", sourceid=2)
    metatypes = rich()["source"][0]["concept"][0]["variable"][0]["metatype"]
    for number, section in enumerate((metatypes[:5], metatypes[5:]), 1):
        routes[META_PATH, number] = dimension([{"id": CPI, "metatype": section}], concept="Series",
                                              number=number, size=5, pages=2, total=len(metatypes))
    frame = wb.get_world_bank_series(CPI, ["IRN", "USA"], 2024, 2025)
    assert frame.attrs["Pagination"] == dict(AdvertisedRecords=3, ReturnedRecords=3, Pages=2, PageSize=2)
    assert frame.attrs["IndicatorMetadata"]["License"] == "CC BY-4.0"
    assert [q["page"] for p, q in calls if p == DATA_PATH] == ["1", "2"]


@pytest.mark.parametrize("second, message", [
    (observations([observation()], number=2, size=1, pages=2, total=2), "duplicate record"),
    (observations([observation("USA")], number=1, size=1, pages=2, total=2), "invalid pagination"),
    (observations([observation("USA")], number=2, size=1, pages=3, total=3), "changed across pages"),
    (observations([observation("USA")], number=2, size=1, pages=2, total=2,
                  lastupdated="2026-11-12"), "changed across pages"),
    (observations([], number=2, size=1, pages=2, total=2), "page record count"),
    ([page([], number=2, size=1, pages=2, total=2, sourceid="2", lastupdated=UPDATE), None], "records list"),
    ((404, {}, b""), "HTTP 404"),
])
def test_bad_later_pages_never_return_partial_frames(wire, second, message):
    routes, _, _ = wire
    routes[DATA_PATH, 1] = observations([observation()], size=1, pages=2, total=2)
    routes[DATA_PATH, 2] = second
    with pytest.raises(RuntimeError, match=message) as error:
        wb.get_world_bank_series(CPI, ["IRN", "USA"], 2023, 2025)
    assert "page=2" in str(error.value)


@pytest.mark.parametrize("rows, counters, message", [
    ([observation(year="1960")], {}, "outside requested"),
    ([observation(year="2024M01")], {}, "annual YYYY"),
    ([observation("BRA")], {}, "unexpected observation geography"),
    ([observation(code="NY.GDP.MKTP.CD")], {}, "unexpected observation indicator"),
    ([observation(countryiso3code="USA")], {}, "conflicting ISO3"),
    ([observation(country={"id": "US", "value": "Iran"})], {}, "conflicting two-character"),
    ([observation(countrycode=None)], {}, "invalid observation geography code"),
    ([observation(value=True)], {}, "invalid numeric"),
    ([observation(value="32.5")], {}, "invalid numeric"),
    ([observation(value=10 ** 400)], {}, "too large to convert"),
    ([observation(decimal=-1)], {}, "decimal counter"),
    ([observation()], {"sourceid": "6"}, "unexpected source ID"),
    ([observation()], {"sourceid": None}, "missing WDI source ID"),
    ([observation()], {"lastupdated": "2026-02-31"}, "invalid lastupdated"),
    ([observation()], {"total": True}, "invalid total counter"),
    ([observation()], {"total": 7}, "exceeds the requested scope"),
    ([observation()], {"total": 21, "size": 1, "pages": 21}, "pagination"),
])
def test_bad_observation_records_and_counters(wire, rows, counters, message):
    routes, _, _ = wire
    routes[DATA_PATH, 1] = observations(rows, **counters)
    with pytest.raises(RuntimeError, match=message):
        wb.get_world_bank_series(CPI, ["IRN", "USA"], 2023, 2025)


@pytest.mark.parametrize("row, message", [
    (indicator(source={"id": "6", "value": "International Debt Statistics"}), "WDI source 2"),
    (indicator("NY.GDP.MKTP.CD"), "unexpected indicator identity"),
])
def test_exact_indicator_checks_source_and_code(wire, row, message):
    wire[0][f"source/2/indicator/{CPI}", 1] = catalog([row])
    with pytest.raises(RuntimeError, match=message):
        wb.get_world_bank_series(CPI, "IRN", 2024, 2024)


@pytest.mark.parametrize("code, metadata_fragments, catalog_unit, observation_units, expected, evidence", [
    (CPI, {"Unitofmeasure": None}, "", ("", ""), None, None),
    (CPI, {"Unitofmeasure": "%"}, "%", ("%", ""), "%", "Observation"),
    (CPI, {"Unitofmeasure": None}, "%", ("", ""), "%", "Catalog"),
    (CPI, {"Unitofmeasure": "%"}, "%", ("%", "current US$"), None, None),
    (CPI, {"Unitofmeasure": "current US$"}, "", ("", ""), None, None),
    ("FP.CPI.TOTL", {"Unitofmeasure": "index (2010 = 100)"}, "", ("", ""), "index (2010 = 100)", "Metadata"),
    ("CM.MKT.LCAP.GD.ZS", {"Unitofmeasure": "End-of-year total market capitalization of listed domestic companies, "
                          "divided by gross domestic product, expressed as a percentage."}, "", ("", ""), "%", "Metadata"),
    ("CM.MKT.LDOM.NO", {"Unitofmeasure": "Market capitalization as a percentage. (percentile)"}, "",
     ("", ""), None, None),
    ("BX.KLT.DINV.WD.GD.ZS", {"Unitofmeasure": None, "Longdefinition": "Net inflows divided by GDP."}, "",
     ("", ""), "%", "Definition"),
    ("CM.MKT.TRNR", {"Unitofmeasure": None, "Longdefinition": "The value of domestic shares traded divided by their market capitalization."},
     "", ("", ""), "%", "Definition"),
    ("DT.TDS.DECT.EX.ZS", {"Unitofmeasure": None, "Longdefinition": "Total debt service to exports of goods, services and primary income."},
     "", ("", ""), "%", "Definition"),
    ("TT.PRI.MRCH.XD.WD", {"Unitofmeasure": None, "Longdefinition": "Measured relative to the base year 2015."},
     "", ("", ""), "2015 = 100", "Definition"),
])
def test_unit_evidence(wire, code, metadata_fragments, catalog_unit, observation_units, expected, evidence):
    routes, _, _ = wire
    name = {CPI: CPI_NAME, "FP.CPI.TOTL": "Consumer price index (2010 = 100)",
            "CM.MKT.LCAP.GD.ZS": "Market capitalization of listed domestic companies (% of GDP)",
            "CM.MKT.LDOM.NO": "Listed domestic companies, total",
            "BX.KLT.DINV.WD.GD.ZS": "Foreign direct investment, net inflows (% of GDP)",
            "CM.MKT.TRNR": "Stocks traded, turnover ratio of domestic shares (%)",
            "DT.TDS.DECT.EX.ZS": "Total debt service (% of exports of goods, services and primary income)",
            "TT.PRI.MRCH.XD.WD": "Net barter terms of trade index (2015 = 100)"}[code]
    routes[f"source/2/indicator/{code}", 1] = catalog([indicator(code, name, unit=catalog_unit)])
    routes[f"sources/2/series/{code}/metadata", 1] = rich(code, IndicatorName=name, **metadata_fragments)
    routes[f"country/IRN;USA/indicator/{code}", 1] = observations([
        observation(code=code, unit=observation_units[0]), observation("USA", code=code, unit=observation_units[1]),
    ])
    frame = wb.get_world_bank_series(code, ["IRN", "USA"], 2024, 2024)
    assert frame.Unit.fillna("missing").tolist() == [expected or "missing"] * 2
    metadata = frame.attrs["IndicatorMetadata"]
    assert metadata["UnitSource"] == evidence
    assert metadata["MetadataUnit"] == metadata_fragments["Unitofmeasure"]
    assert metadata["ObservationUnits"] == tuple(sorted(set(filter(None, observation_units))))


@pytest.mark.parametrize("code", ["120", "175"])
def test_http_200_provider_error_in_data(wire, code):
    routes, _, _ = wire
    routes[DATA_PATH, 1] = [{"message": [{"id": code, "value": "Invalid query"}]}]
    with pytest.raises(RuntimeError, match=f"HTTP 200 provider error {code}.*Invalid query"):
        wb.get_world_bank_series(CPI, ["IRN", "USA"], 2024, 2025)


def test_retry_transient_status_and_provider_code(wire, monkeypatch):
    routes, calls, closed = wire
    key = ("source/2", 1)
    original = routes[key]
    date_header = format_datetime(datetime.now(timezone.utc) - timedelta(seconds=1), usegmt=True)
    outcomes = iter([
        (429, {"Retry-After": "2"}, None),
        (200, {"Retry-After": date_header}, {"message": [{"id": 105, "key": "Service unavailable"}]}),
        original,
    ])
    routes[key] = lambda: next(outcomes)
    delays = []
    monkeypatch.setattr(wb, "sleep", delays.append)
    frame = wb.get_world_bank_sources()
    assert delays == [2, 0]
    assert len(calls) == len(closed) == 3
    assert len(frame.attrs["RequestURLs"]) == 1


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retry_limit(wire, monkeypatch, status):
    wire[0]["source/2", 1] = (status, {}, None)
    delays = []
    monkeypatch.setattr(wb, "sleep", delays.append)
    with pytest.raises(RuntimeError, match=f"HTTP {status}.*retries exhausted"):
        wb.get_world_bank_sources()
    assert len(wire[1]) == len(wire[2]) == 3
    assert delays == [0.25, 0.5]


@pytest.mark.parametrize("retry_after", ["900", "tomorrow"])
def test_retry_after_cap_and_format(wire, retry_after):
    wire[0]["source/2", 1] = (429, {"Retry-After": retry_after}, None)
    with pytest.raises(RuntimeError, match="HTTP 429.*Retry-After.*Retry later"):
        wb.get_world_bank_sources()
    assert len(wire[1]) == len(wire[2]) == 1


@pytest.mark.parametrize("error, attempts", [(requests.Timeout, 3), (requests.exceptions.SSLError, 1)])
def test_transport_exception_is_chained(wire, monkeypatch, error, attempts):
    wire[0]["source/2", 1] = error("mocked failure")
    monkeypatch.setattr(wb, "sleep", lambda delay: None)
    with pytest.raises(RuntimeError, match=error.__name__) as exc:
        wb.get_world_bank_sources()
    assert len(wire[1]) == attempts
    assert isinstance(exc.value.__cause__, error)


@pytest.mark.parametrize("target, message", [
    ("https://example.test/v2/source/2", "unsafe URL"),
    ("http://api.worldbank.org/v2/source/2", "unsafe URL"),
    ("https://api.worldbank.org/v2/source/6", "changed the request scope"),
    ("https://api.worldbank.org/v2/source/2?format=json&page=9&per_page=500", "changed the request scope"),
])
def test_unsafe_redirect_is_not_followed(wire, target, message):
    wire[0]["source/2", 1] = (302, {"Location": target}, b"")
    with pytest.raises(RuntimeError, match=message):
        wb.get_world_bank_sources()
    assert len(wire[1]) == len(wire[2]) == 1


def test_safe_redirect_records_verified_final_url(wire):
    routes, calls, closed = wire
    routes["source/2/", 1] = routes["source/2", 1]
    routes["source/2", 1] = (302, {"Location": "/v2/source/2/?format=json&page=1&per_page=500"}, b"")
    frame = wb.get_world_bank_sources()
    assert len(calls) == len(closed) == 2
    assert frame.attrs["RequestURLs"] == (closed[-1],)
    assert frame.SourceURL.iloc[0] == closed[-1]


@pytest.mark.parametrize("headers, body, message", [
    ({"Content-Type": "text/html"}, b"<html>WAF page</html>", "unexpected Content-Type"),
    ({}, b"[{", "Expecting"),
    ({}, b'{"page":1,"page":2}', "duplicate JSON key"),
    ({}, b'{"value":1e9999}', "nonfinite"),
    ({}, b'{"value":NaN}', "nonfinite"),
    ({}, b'{"value":Infinity}', "nonfinite"),
])
def test_invalid_json_and_mime(wire, headers, body, message):
    wire[0]["source/2", 1] = (200, headers, body)
    with pytest.raises(RuntimeError, match=message):
        wb.get_world_bank_sources()
    assert len(wire[1]) == len(wire[2]) == 1


def test_decoded_response_size_and_deadline(wire, monkeypatch):
    monkeypatch.setattr(wb, "_MAX_BYTES", 10)
    with pytest.raises(RuntimeError, match="decoded byte limit"):
        wb.get_world_bank_sources()
    assert len(wire[2]) == 1
    monkeypatch.setattr(wb, "_DEADLINE", 0)
    with pytest.raises(RuntimeError, match="time budget"):
        wb.get_world_bank_sources()
    assert len(wire[1]) == 1
