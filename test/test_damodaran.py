"""Offline tests using synthetic catalogs and workbooks."""

from datetime import datetime
from inspect import Parameter, signature
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import openpyxl
import pandas as pd
import pytest
import requests

from fima import get_damodaran_data, get_damodaran_datasets
import fima.DAMODARAN as dam


SITE = "https://pages.stern.nyu.edu/~adamodar/"
CURRENT = SITE + "New_Home_Page/datacurrent.html"
ARCHIVE = SITE + "New_Home_Page/dataarchived.html"
ROOT = SITE + "pc/"
JULY = ROOT + "datasets/ctrypremJuly26.xlsx"
APRIL = ROOT + "datasets/ctrypremApr26.xlsx"
JAN = ROOT + "datasets/ctryprem.xlsx"
COUNTRY_ARCHIVE = ROOT + "archives/ctryprem24.xlsx"
BETA = ROOT + "datasets/betaGlobal.xls"
BETA_ARCHIVE = ROOT + "archives/betaGlobal24.xls"
WACC = ROOT + "datasets/wacc.xls"
XLSX_MIME = "application/vnd.openxmlformats"
XLS_MIME = "application/vnd.ms-excel"

CURRENT_HTML = b"""
<html><h4>Data of last full update: January 9, 2026; Country risk premiums last updates: January 5, 2026</h4>
<table><tr><td>Unrelated table</td></tr></table><table>
<tr><td>Topic</td><td>Current data set as html (just US)</td><td>Regional datasets (downloadable Excel)</td></tr>
<tr><td rowspan="4">Risk</td><td><a href="ctryprem.html">Risk
 Premiums for Other Markets</a> (reflects Jan 2026 numbers)</td>
<td><a href="../pc/datasets/ctryprem.xlsx">January 1, 2026 update</a>
<a href="../pc/datasets/ctrypremJuly26.xlsx">July 1, 2026 update</a>
<a href="../pc/datasets/ctrypremApr26.xlsx">April 1, 2026 update</a>
<a href="../pc/datasets/ctrypremJuly25.xlsx">July 1, 2025 update</a>
<a href="../pc/datasets/old.xls"></a></td></tr>
<tr><td><a href="Betas.html">Levered and Unlevered Betas by Industry</a></td>
<td><a href="../pc/datasets/betas.xls">U.S.</a><a href="../pc/datasets/betaGlobal.xls">Global</a>
<a href="../pc/datasets/betaEurope.xls">Europe</a></td></tr>
<tr><td><a href="wacc.html">Costs of Capital by Industry Sector</a></td>
<td><a href="../pc/datasets/wacc.xls">US</a><a href="../pc/datasets/waccGlobal.xls">Global</a></td></tr>
<tr><td><a href="totalbeta.html">Total Betas by Industry</a></td><td></td></tr>
</table></html>
"""
ARCHIVE_HTML = b"""
<html><table>
<tr><td>Topic</td><td>Data Item</td><td>US</td><td>Europe</td><td>Japan</td>
<td>Emerging Markets</td><td>Global</td></tr>
<tr><td rowspan="3">Risk</td><td><a href="file:///editor">Risk Premiums for Other Markets</a></td>
<td colspan="5"><a href="../pc/archives/ctryprem00.xls">1/01</a>
<a href="../pc/archives/ctryprem24.xlsx">1/25</a></td></tr>
<tr><td><a href="file:///editor">Levered and Unlevered Betas by Industry</a></td>
<td><a href="../pc/archives/betas98.xls">1/99</a></td>
<td><a href="../pc/archives/betaEurope24.xls">1/25</a></td><td></td><td></td>
<td><a href="../pc/archives/betaGlobal24.xls">1/25</a>
<a href="../pc/archives/betaGlobal24.xls">1/25</a></td></tr>
<tr><td><a href="file:///editor">Costs of Capital by Industry</a> (in US $)</td><td></td>
<td></td><td></td><td></td><td><a href="../pc/archives/waccGlobal24.xls">1/25</a></td></tr></table></html>
"""
COMMON = ("Dataset", "Region", "Edition", "DataAsOf", "DataAsOfPeriod", "Source", "SourceURL",
          "SourceUpdateDate", "RetrievedAt")
INDUSTRY = ("IndustryName", "IndustryClassification", "RowType", "NumberOfFirms")
CATALOG = ("Dataset", "DatasetName", "Category", "Description", "Region", "Edition", "IsLatest",
           "UpdateFrequency", "Source", "SourceURL", "CatalogURL", "FileFormat", "DefinitionsURL")
COUNTRY = ("Country", "CountryRegion", "RiskMethod", "MoodysRating", "DefaultSpreadPercent",
           "CountryRiskPremiumPercent", "EquityRiskPremiumPercent", "SovereignCdsNetSpreadPercent",
           "CdsBenchmark", "CdsBasedCountryRiskPremiumPercent", "CdsBasedEquityRiskPremiumPercent")
BETA_COLUMNS = ("LeveredBeta", "DebtToEquityPercent", "EffectiveTaxRatePercent", "UnleveredBeta",
                "CashToFirmValuePercent", "CashAdjustedUnleveredBeta", "HiLoRisk", "EquityVolatilityPercent",
                "OperatingIncomeVariation10YearPercent", "UnleveringTaxBasis")
WACC_COLUMNS = ("Beta", "CostOfEquityPercent", "EquityWeightPercent", "EquityVolatilityPercent",
                "PretaxCostOfDebtPercent", "ReportedTaxRatePercent", "AfterTaxCostOfDebtPercent", "DebtWeightPercent",
                "CostOfCapitalPercent", "Currency")


class Response:
    def __init__(self, body=b"", *, mime="text/html", status=200, **headers):
        self.body = body
        self.status_code = status
        self.headers = {"Content-Type": mime, "Content-Length": str(len(body)), **headers}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, chunk_size):
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start:start + chunk_size]


def xlsx(edition="2026-07", edits=(), sheet_name="ERPs by country"):
    """Invented countries, ratings and values, including unrelated lookup blocks."""
    year, month = map(int, edition.split("-"))
    old = year == 2025
    workbook = openpyxl.Workbook()
    workbook.active.title = "Unrelated"
    workbook.active.append(["Country", "Default Spread"])
    sheet = workbook.create_sheet(sheet_name)
    sheet.append(["Country and Equity Risk Premiums"])
    note = ("Default spreads corrected on July 9, 2026" if month == 7
            else "(Updated Feb 16 for sovereign ratings" if not old else None)
    sheet.append(["Date of update:", datetime(year, month, 1), note])
    sheet.append(["Enter the current risk premium for a mature equity market", None, None, None, 0.043])
    sheet["E3"].number_format = "0.00%"
    sheet.merge_cells("A3:D3")
    if not old:
        sheet.append(["Enter the current risk premium for the US =", None, None, None, 0.051])
        sheet["E4"].number_format = "0.00%"
    sheet.append(["Do you want to adjust the country default spread for the additional volatility of the equity market to get to a country premium?",
                  None, None, None, "Yes"])
    sheet.append(["If yes, enter the multiplier to use on the default spread (See worksheet for volatility numbers for selected emerging markets)",
                  None, None, None, 1.5])
    sheet.append([None])
    benchmark = "US" if old else "Swiss CDS"
    sheet.append(["Country", "Africa", "Moody's rating", "Rating-based Default Spread", "Total Equity Risk Premium",
                  "Country Risk Premium", f"Sovereign CDS, net of {benchmark}", "Total Equity Risk Premium2",
                  "Country Risk Premium3"])
    for row in (
        ["Test Coast", "Asia", "Aa2", 0.015, 0.061, 0.018, -0.005, 0.038, -0.005, "Rating", "Default spread in basis points"],
        ["Test Sound (Islands)", "Oceania", "Aaa", 0, 0.043, 0, 0, 0.043, 0, "Aaa", 0],
        ["Test Peninsula", "Asia", "Ba1", 0.02, 0.071, 0.028, "NA", "#N/A", "NA", "Aa2", 151.75],
    ):
        sheet.append(row)
        for col in range(4, 10):
            sheet.cell(sheet.max_row, col).number_format = "0.00%"
    sheet.append(["Frontier Markets (no sovereign ratings)"])
    sheet.append(["Country", "PRS Composite Risk Score", "ERP", "CRP", "Default Spread"])
    sheet.append(["Test Frontier, Republic", 57, 0.17, 0.127, 0.09])
    for col in range(3, 6):
        sheet.cell(sheet.max_row, col).number_format = "0.00%"
    sheet.append([None])
    sheet.append([None, "Rating", "Default spread in basis points"])
    sheet.append([None, "Aaa", 0])
    for cell, value in edits:
        sheet[cell].value = value
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def xls(name):
    """Synthetic BIFF files written with xlwt, with no publisher observations."""
    return (Path(__file__).parent / "fixtures" / "damodaran" / f"{name}.xls").read_bytes()


@pytest.fixture
def provider(monkeypatch):
    routes = {CURRENT: Response(CURRENT_HTML), ARCHIVE: Response(ARCHIVE_HTML)}
    calls = []

    def get(session, url, *, stream, allow_redirects, headers, timeout):
        assert stream and not allow_redirects and session.verify is True
        assert 0 < timeout[0] <= 5 and 0 < timeout[1] <= 20
        calls.append((url, headers))
        result = routes[url]
        if isinstance(result, list):
            result = result.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result

    dam._catalogs.clear()
    dam._artifacts.clear()
    monkeypatch.setattr(requests.Session, "get", get)
    monkeypatch.setattr(dam, "sleep", lambda delay: None)
    yield routes, calls
    dam._catalogs.clear()
    dam._artifacts.clear()


def test_public_signatures():
    assert dam.__all__ == ["get_damodaran_datasets", "get_damodaran_data"]
    for direct, public, expected in (
        (dam.get_damodaran_datasets, get_damodaran_datasets,
         {"dataset": None, "include_history": False, "refresh": False}),
        (dam.get_damodaran_data, get_damodaran_data,
         {"dataset": Parameter.empty, "region": None, "edition": None, "refresh": False}),
    ):
        assert direct is public
        params = signature(public).parameters
        assert list(params) == list(expected)
        assert {name: p.default for name, p in params.items()} == expected
        assert params["dataset"].kind is Parameter.POSITIONAL_OR_KEYWORD
        assert all(params[name].kind is Parameter.KEYWORD_ONLY for name in list(expected)[1:])


def test_catalog_only_downloads_and_lists_verified_combinations(provider):
    _, calls = provider
    latest = get_damodaran_datasets()
    assert tuple(latest) == CATALOG
    assert list(latest.Edition) == ["2026-07"] + ["2026-01"] * 4
    assert latest.IsLatest.dtype == bool and latest.IsLatest.all()
    assert latest.Region.isna().tolist() == [True, False, False, False, False]
    assert [url for url, _ in calls] == [CURRENT]
    betas = get_damodaran_datasets("　بتای صنعت ", include_history=True)
    assert list(zip(betas.Region, betas.Edition)) == [("Global", "2026-01"), ("Global", "2025-01"), ("US", "2026-01")]
    assert betas.SourceURL.iloc[1] == BETA_ARCHIVE
    assert betas.IsLatest.tolist() == [True, False, True]
    assert [url for url, _ in calls] == [CURRENT, ARCHIVE]
    country = get_damodaran_datasets("country risk premium", include_history=True)
    assert list(country.Edition) == ["2026-07", "2026-04", "2026-01", "2025-01"]
    assert country.CatalogURL.iloc[-1] == ARCHIVE


@pytest.mark.parametrize("dataset,kwargs,match", [
    ("risk", {}, "Unknown Damodaran dataset"),
    (False, {}, "Unknown Damodaran dataset"),
    ("betas", {"region": "Europe"}, "Choose Global or US"),
    ("country risk premium", {"region": "US"}, "Omit region"),
    ("wacc", {"edition": "2026"}, "YYYY-MM"),
    ("betas", {"edition": "2026-13"}, "YYYY-MM"),
    ("betas", {"edition": "1999-01"}, "Unverified edition"),
    ("country risk premiums", {"edition": "2025-07"}, "Unverified edition"),
    ("betas", {"refresh": 1}, "must be True or False"),
])
def test_invalid_selections_fail_without_http(provider, dataset, kwargs, match):
    with pytest.raises(ValueError, match=match):
        get_damodaran_data(dataset, **kwargs)
    assert not provider[1]


def test_country_mappings_and_corrected_provenance(provider):
    routes, calls = provider
    routes[JULY] = Response(xlsx(), mime=XLSX_MIME, **{"Last-Modified": "Fri, 10 Jul 2026 16:59:20 GMT"})
    result = get_damodaran_data(" Country  Risk Premiums ")
    assert tuple(result) == COUNTRY + COMMON
    assert [url for url, _ in calls] == [CURRENT, JULY]
    assert result.Country.tolist() == ["Test Coast", "Test Sound (Islands)", "Test Peninsula", "Test Frontier, Republic"]
    assert result.RiskMethod.tolist() == ["RatingBased"] * 3 + ["FrontierPrs"]
    assert result.Edition.eq("2026-07").all() and result.SourceURL.eq(JULY).all()
    assert result.Source.eq("Aswath Damodaran, NYU Stern").all()
    assert result.SourceUpdateDate.eq(pd.Timestamp("2026-07-09")).all()
    assert result[["Region", "DataAsOf", "DataAsOfPeriod"]].isna().all().all()
    assert str(result.RetrievedAt.dtype) == "datetime64[ns, UTC]"
    assert result.attrs["SourceEditionDate"] == "2026-07-01"
    assert result.attrs["SourceRevisionNote"] == "Default spreads corrected on July 9, 2026"
    assert result.attrs["SourceHttpLastModified"] == "Fri, 10 Jul 2026 16:59:20 GMT"
    assert result.attrs["SourceAssumptions"]["RelativeEquityVolatility"] == 1.5
    assert result.attrs["SourceAssumptions"]["MatureMarketErpPercent"] == pytest.approx(4.3)
    assert result.attrs["ColumnMetadata"]["CountryRegion"]["SourceLabel"] == "Africa"
    assert result.attrs["ColumnMetadata"]["DefaultSpreadPercent"]["NativeUnit"] == "PercentagePoint"
    first = result.iloc[0]
    assert first.CountryRegion == "Asia" and first.MoodysRating == "Aa2"
    assert first.CdsBenchmark == "Switzerland"
    assert first[list(COUNTRY[4:8]) + list(COUNTRY[9:])].tolist() == pytest.approx([1.5, 1.8, 6.1, -0.5, -0.5, 3.8])
    assert result.loc[1, "SovereignCdsNetSpreadPercent"] == 0
    assert pd.isna(result.loc[2, "SovereignCdsNetSpreadPercent"])
    assert result.loc[3, ["MoodysRating", "CountryRegion", "CdsBenchmark"]].isna().all()
    assert result.loc[3, list(COUNTRY[4:7])].tolist() == pytest.approx([9, 12.7, 17])
    assert str(result.EquityRiskPremiumPercent.dtype) == "Float64"


@pytest.mark.parametrize("edition,url,benchmark,date", [
    ("2025-01", COUNTRY_ARCHIVE, "US", "2025-01-01"),
    ("2026-01", JAN, "Switzerland", "2026-02-16"),
    ("2026-04", APRIL, "Switzerland", "2026-04-01"),
])
def test_country_selections_keep_their_dates(provider, edition, url, benchmark, date):
    provider[0][url] = Response(xlsx(edition), mime=XLSX_MIME)
    result = get_damodaran_data("country risk premium", edition=edition)
    assert result.CdsBenchmark.dropna().eq(benchmark).all()
    assert result.Edition.eq(edition).all()
    assert result.SourceUpdateDate.eq(pd.Timestamp(date)).all()
    assert bool(result.attrs["MetadataWarnings"]) == (edition == "2026-04")


def test_industry_xls_preserves_values_and_classifications(provider):
    routes, _ = provider
    routes[BETA] = Response(xls("beta-current"), mime=XLS_MIME)
    routes[BETA_ARCHIVE] = Response(xls("beta-archive"), mime=XLS_MIME)
    latest = get_damodaran_data("　ＢＥＴＡＳ ", region="world")
    archived = get_damodaran_data("بتای صنعت", region="Global", edition="2025-01")
    assert tuple(latest) == INDUSTRY + BETA_COLUMNS + COMMON
    assert latest.SourceURL.eq(BETA).all() and latest.Region.eq("Global").all()
    assert latest.SourceUpdateDate.eq(pd.Timestamp("2026-01-05")).all()
    assert latest.NumberOfFirms.dtype == "Int64"
    assert latest.RowType.tolist() == ["Industry", "MarketAggregate", "MarketAggregate"]
    assert archived.loc[1, "IndustryName"] == "Tiotal Market"
    first = latest.iloc[0]
    assert first.IndustryName == "Paper Widgets & Parts" and first.NumberOfFirms == 35
    assert first[list(BETA_COLUMNS[:8])].tolist() == pytest.approx([-0.8, 140, 12.5, -0.55, 0, -0.5, 0.34, 45])
    assert pd.isna(first.OperatingIncomeVariation10YearPercent)
    assert latest.attrs["ColumnMetadata"]["HiLoRisk"]["NativeUnit"] == "Ratio"
    assert first.UnleveringTaxBasis == "Marginal"
    joined = pd.concat([latest, archived], ignore_index=True)
    same_labels = joined.loc[joined.IndustryName == first.IndustryName]
    assert set(same_labels.Edition) == {"2026-01", "2025-01"}
    assert same_labels.IndustryClassification.nunique() == 2


def test_wacc_xls_keeps_published_costs_and_assumptions(provider):
    provider[0][WACC] = Response(xls("cost-current"), mime=XLS_MIME)
    result = get_damodaran_data("WACC", region="United States")
    assert tuple(result) == INDUSTRY + WACC_COLUMNS + COMMON
    assert result.Currency.eq("USD").all() and result.Region.eq("US").all()
    assert result.iloc[0][list(WACC_COLUMNS[:-1])].tolist() == pytest.approx(
        [1.12, 11, 70, 45, 6, 18, 4.5, 30, 9.4])
    assert result.attrs["SourceAssumptions"]["MarginalTaxRatePercent"] == 25
    assert result.attrs["SourceAssumptions"]["UseMarginalTaxRate"] is True
    assert result.attrs["MetadataWarnings"] == ()


def test_missing_historical_link_and_newer_current_edition(provider):
    routes, calls = provider
    with pytest.raises(ValueError, match="currently lists no 2025-01 link"):
        get_damodaran_data("betas", region="US", edition="2025-01")
    marker = b'<a href="../pc/datasets/ctryprem2027.xlsx">January 1, 2027 update</a>'
    routes[CURRENT] = Response(CURRENT_HTML.replace(b"April 1, 2026 update</a>", b"April 1, 2026 update</a>" + marker))
    with pytest.raises(RuntimeError, match="2027-01.*unverified layout"):
        get_damodaran_data("country risk premium", refresh=True)
    routes[JULY] = Response(xlsx(), mime=XLSX_MIME)
    assert get_damodaran_data("country risk premium", edition="2026-07").Edition.eq("2026-07").all()
    assert not any("ctryprem2027.xlsx" in url for url, _ in calls)


@pytest.mark.parametrize("edits,sheet,match", [
    ([("C2", None)], "ERPs by country", "July 9"),
    ([("B2", datetime(2026, 7, 2))], "ERPs by country", "edition date"),
    ([("B2", datetime(2026, 4, 1))], "ERPs by country", "does not match edition"),
    ([], "Another sheet", "Missing XLSX worksheet"),
    ([("F8", "Total Equity Risk Premium")], "ERPs by country", "worksheet heading"),
    ([("D9", "unknown")], "ERPs by country", "Excel row 9: DefaultSpreadPercent"),
    ([("D9", "=42")], "ERPs by country", "missing cached value"),
    ([("D9", "#DIV/0!")], "ERPs by country", "invalid number"),
    ([("G9", "NA")], "ERPs by country", "Inconsistent missing values"),
    ([("A10", "Test Coast")], "ERPs by country", "Duplicate country identity"),
    ([("A14", None)], "ERPs by country", "separate trailing spread lookup"),
])
def test_rejects_malformed_country_layouts(provider, edits, sheet, match):
    provider[0][JULY] = Response(xlsx(edits=edits, sheet_name=sheet), mime=XLSX_MIME)
    with pytest.raises(RuntimeError, match=match) as error:
        get_damodaran_data("country risk premiums")
    assert JULY in str(error.value) and error.value.__cause__ is not None
    assert not dam._artifacts


def test_cached_formula_value_is_read_as_published(provider):
    formula_file = xlsx(edits=[("D9", "=42")])
    updated = BytesIO()
    with ZipFile(BytesIO(formula_file)) as initial, ZipFile(updated, "w") as output:
        for name in initial.namelist():
            body = initial.read(name)
            if name == "xl/worksheets/sheet2.xml":
                body = body.replace(b"<f>42</f><v></v>", b"<f>42</f><v>0.0375</v>")
            output.writestr(name, body)
    provider[0][JULY] = Response(updated.getvalue(), mime=XLSX_MIME)
    assert get_damodaran_data("country risk premium").DefaultSpreadPercent.iloc[0] == 3.75


def test_rejects_wrong_xls_region_and_edition(provider):
    routes, _ = provider
    routes[ROOT + "datasets/betas.xls"] = Response(xls("beta-current"), mime=XLS_MIME)
    routes[BETA_ARCHIVE] = Response(xls("beta-current"), mime=XLS_MIME)
    with pytest.raises(RuntimeError, match="Unexpected industry workbook identity for US"):
        get_damodaran_data("betas", region="US")
    with pytest.raises(RuntimeError, match="does not match edition 2025-01"):
        get_damodaran_data("betas", edition="2025-01")


@pytest.mark.parametrize("modified,match", [
    (CURRENT_HTML.replace(b"<td>Topic</td>", b"<td>Topic changed</td>"), "official data catalog table"),
    (CURRENT_HTML.replace(b'<a href="../pc/datasets/betaGlobal.xls">Global</a>',
                          b'<a href="../pc/datasets/betaGlobal.xls">Global</a>'
                          b'<a href="../pc/datasets/betaOther.xls">Global</a>'), "Conflicting catalog links"),
    (CURRENT_HTML.replace(b"datasets/betas.xls", b"datasets/betaGlobal.xls"), "Shared catalog link"),
])
def test_rejects_ambiguous_catalog(provider, modified, match):
    provider[0][CURRENT] = Response(modified)
    with pytest.raises(RuntimeError, match=match):
        get_damodaran_datasets()
    assert not dam._catalogs


@pytest.mark.parametrize("response,match", [
    (Response(status=403), "HTTP 403"),
    (Response(status=404), "HTTP 404"),
    (Response(status=304), "HTTP 304"),
    (Response(b"<html>Challenge</html>"), "unexpected Content-Type"),
    (Response(b"<html>Challenge</html>", mime=XLSX_MIME), "ZIP signature"),
    (Response(b"PK\x03\x04broken", mime=XLSX_MIME), "File is not a zip file"),
    (Response(b"a", mime=XLSX_MIME, **{"Content-Length": "99"}), "truncated response"),
    (Response(b"a", mime=XLSX_MIME, **{"Content-Length": str(9 * 1024**2)}), "oversized"),
    (Response(status=302, Location="https://other.invalid/ctryprem.xlsx"), "Unsafe source URL"),
    (Response(status=302, Location=JULY.replace("https:", "http:")), "Unsafe source URL"),
    (Response(status=302, Location=JULY.replace("//", "//user:password@")), "Unsafe source URL"),
    (Response(status=302, Location=ROOT + "not-a-dataset.xlsx"), "Unexpected XLSX artifact URL"),
    (Response(status=429, **{"Retry-After": "120"}), "longer retry delay"),
])
def test_http_failures_are_scoped_and_do_not_retry_permanent_failures(provider, response, match):
    routes, calls = provider
    routes[JULY] = response
    with pytest.raises(RuntimeError, match=match):
        get_damodaran_data("country risk premiums")
    assert [url for url, _ in calls] == [CURRENT, JULY]
    assert not dam._artifacts


def test_requests_does_not_read_the_body_of_an_untrusted_redirect(monkeypatch):
    class RedirectBody:
        def stream(self, *args, **kwargs):
            pytest.fail("The redirect body must not be read")

        def close(self):
            pass

    def send(adapter, request, **kwargs):
        assert request.url == JULY and kwargs["stream"]
        response = requests.Response()
        response.status_code = 302
        response.headers["Location"] = "https://other.invalid/ctryprem.xlsx"
        response.url = request.url
        response.raw = RedirectBody()
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    with dam._Session() as session, pytest.raises(dam._SourceError, match="Unsafe source URL"):
        dam._download(session, JULY, "xlsx")


def test_size_limit_without_content_length(provider, monkeypatch):
    routes, _ = provider
    get_damodaran_datasets()
    monkeypatch.setattr(dam, "_MAX_BYTES", 128)
    response = Response(b"x" * 129, mime=XLSX_MIME)
    del response.headers["Content-Length"]
    routes[JULY] = response
    with pytest.raises(RuntimeError, match="exceeds the byte limit"):
        get_damodaran_data("country risk premium")


def test_retries_are_bounded_and_redirect_loop_is_bounded(provider):
    routes, calls = provider
    routes[JULY] = [requests.Timeout("provider timeout"), Response(status=503)]
    with pytest.raises(RuntimeError, match="HTTP 503"):
        get_damodaran_data("country risk premiums")
    assert [url for url, _ in calls].count(JULY) == 2
    routes[JULY] = Response(status=302, Location=JULY)
    with pytest.raises(RuntimeError, match="excessive redirects"):
        get_damodaran_data("country risk premiums")
    assert [url for url, _ in calls].count(JULY) == 6
    routes[JULY] = [Response(status=429, **{"Retry-After": "0"}), Response(xlsx(), mime=XLSX_MIME)]
    assert get_damodaran_data("country risk premiums").SourceURL.eq(JULY).all()


def test_redirected_cache_revalidation_and_copy_safety(provider, monkeypatch):
    routes, calls = provider
    redirected = ROOT + "datasets/renamedJuly.xlsx"
    routes[JULY] = Response(status=302, Location=redirected)
    routes[redirected] = Response(xlsx(), mime=XLSX_MIME, ETag='"version-1"')
    first = get_damodaran_data("country risk premiums")
    assert first.SourceURL.eq(redirected).all()
    first.loc[0, "Country"] = "Changed locally"
    first.attrs["ColumnMetadata"]["Country"]["SourceLabel"] = "Changed locally"
    second = get_damodaran_data("country risk premiums")
    assert len(calls) == 3
    assert second.loc[0, "Country"] == "Test Coast"
    assert second.attrs["ColumnMetadata"]["Country"]["SourceLabel"] == "Country"

    routes[redirected] = Response(status=304)
    refreshed = get_damodaran_data("country risk premiums", refresh=True)
    assert calls[-3][0] == CURRENT
    assert "If-None-Match" not in calls[-2][1]
    assert calls[-1][1]["If-None-Match"] == '"version-1"'
    assert refreshed.RetrievedAt.equals(second.RetrievedAt)
    assert refreshed.attrs["RevalidatedAt"] >= second.RetrievedAt.iloc[0]

    now = dam.monotonic()
    monkeypatch.setattr(dam, "monotonic", lambda: now + dam._ARTIFACT_TTL + 1)
    routes[redirected] = Response(status=404)
    with pytest.raises(RuntimeError, match="HTTP 404"):
        get_damodaran_data("country risk premiums")
    assert list(dam._artifacts.values())[0].value.RetrievedAt.equals(second.RetrievedAt)


def test_changed_catalog_mapping_never_uses_old_validator(provider):
    routes, calls = provider
    routes[JULY] = Response(xlsx(), mime=XLSX_MIME, ETag='"original"')
    get_damodaran_data("country risk premium")
    new = ROOT + "datasets/newJuly.xlsx"
    routes[CURRENT] = Response(CURRENT_HTML.replace(b"ctrypremJuly26.xlsx", b"newJuly.xlsx"))
    routes[new] = Response(xlsx(), mime=XLSX_MIME, ETag='"new"')
    result = get_damodaran_data("country risk premium", refresh=True)
    assert result.SourceURL.eq(new).all()
    assert "If-None-Match" not in calls[-1][1]
