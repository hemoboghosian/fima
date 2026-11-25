"""Opt-in verification against selected current and January 2025 NYU Stern snapshots."""

import pandas as pd
import pytest

from fima import get_damodaran_data, get_damodaran_datasets


pytestmark = pytest.mark.integration
SITE = "https://pages.stern.nyu.edu/~adamodar/"
ARCHIVE = SITE + "New_Home_Page/dataarchived.html"


def test_live_catalog_lists_official_links_without_opening_workbooks():
    frame = get_damodaran_datasets(include_history=True)
    assert set(frame.Dataset) == {"country_risk_premiums", "industry_betas", "industry_cost_of_capital"}
    assert len(frame) == 12
    assert frame.loc[frame.IsLatest & frame.Region.isna(), "Edition"].tolist() == ["2026-07"]
    assert frame.loc[frame.Edition.eq("2025-01"), "CatalogURL"].eq(ARCHIVE).all()
    assert frame.groupby("Dataset").FileFormat.first().to_dict() == {
        "country_risk_premiums": "xlsx", "industry_betas": "xls", "industry_cost_of_capital": "xls",
    }


@pytest.mark.parametrize("edition,filename,benchmark,update,spread,crp,erp,cds,cds_crp,cds_erp", [
    (None, "datasets/ctrypremJuly26.xlsx", "Switzerland", "2026-07-09",
     0.3930214513416281, 0.610950087834357, 4.810950087834357, 0.52, 0.8083376736546494, 5.008337673654649),
    ("2025-01", "archives/ctryprem24.xlsx", "US", "2025-01-01",
     0.4888978427969253, 0.6587887954577641, 4.988788795457764, 0.35, 0.4716242499478411, 4.801624249947841),
])
def test_live_country_rating_and_frontier_blocks(edition, filename, benchmark, update, spread, crp, erp,
                                                cds, cds_crp, cds_erp):
    frame = get_damodaran_data("country risk premiums", edition=edition)
    assert frame.SourceURL.eq(SITE + "pc/" + filename).all()
    assert frame.Edition.eq(edition or "2026-07").all()
    assert frame.SourceUpdateDate.eq(pd.Timestamp(update)).all()
    assert frame.Region.isna().all()
    assert frame.RiskMethod.value_counts().to_dict() == {"RatingBased": 157, "FrontierPrs": 21}
    assert not frame.duplicated(["Country", "RiskMethod"]).any()
    country = frame.set_index("Country")
    abu_dhabi = country.loc["Abu Dhabi"]
    assert (abu_dhabi.CountryRegion, abu_dhabi.MoodysRating, abu_dhabi.CdsBenchmark) == ("Middle East", "Aa2", benchmark)
    assert abu_dhabi[[
        "DefaultSpreadPercent", "CountryRiskPremiumPercent", "EquityRiskPremiumPercent",
        "SovereignCdsNetSpreadPercent", "CdsBasedCountryRiskPremiumPercent", "CdsBasedEquityRiskPremiumPercent",
    ]].tolist() == pytest.approx([spread, crp, erp, cds, cds_crp, cds_erp])
    assert country.loc["Iran", "RiskMethod"] == "FrontierPrs"
    assert country.loc["Iran", ["MoodysRating", "CdsBenchmark"]].isna().all()
    assert country.loc["Switzerland", "CountryRiskPremiumPercent"] == 0


@pytest.mark.parametrize("edition,filename,count,beta,debt_to_equity,unlevered,cash_adjusted,hilo", [
    (None, "datasets/betaGlobal.xls", 419, 1.272831803339158, 40.55491701033854,
     0.9771010766469344, 1.0861161361977183, 0.4367319648294255),
    ("2025-01", "archives/betaGlobal24.xls", 417, 1.254409764675642, 28.05246276208235,
     1.03713445972192, 1.1534040974143316, 0.4264598163476225),
])
def test_live_betas_snapshot(edition, filename, count, beta, debt_to_equity, unlevered, cash_adjusted, hilo):
    frame = get_damodaran_data("industry betas", edition=edition)
    assert frame.SourceURL.eq(SITE + "pc/" + filename).all()
    assert frame.Region.eq("Global").all() and frame.Edition.eq(edition or "2026-01").all()
    assert frame.RowType.value_counts().to_dict() == {"Industry": 94, "MarketAggregate": 2}
    assert frame.IndustryName.iloc[-2] == ("Tiotal Market" if edition else "Total Market")
    assert frame.IndustryName.is_unique and frame.IndustryClassification.nunique() == 1
    advertising = frame.set_index("IndustryName").loc["Advertising"]
    assert advertising.NumberOfFirms == count and advertising.UnleveringTaxBasis == "Marginal"
    assert advertising[["LeveredBeta", "DebtToEquityPercent", "UnleveredBeta",
                        "CashAdjustedUnleveredBeta", "HiLoRisk"]].tolist() == pytest.approx(
        [beta, debt_to_equity, unlevered, cash_adjusted, hilo])


@pytest.mark.parametrize("edition,filename,region,count,equity,pretax,tax,after_tax,wacc", [
    (None, "datasets/wacc.xls", "US", 52, 9.348861074647324, 5.2913, 5.016660189213596,
     3.968475, 7.806123736168303),
    ("2025-01", "archives/waccGlobal24.xls", "Global", 417, 11.742679756297916, 6.82,
     14.376235296448503, 5.099996, 10.28746652029747),
])
def test_live_wacc_snapshot(edition, filename, region, count, equity, pretax, tax, after_tax, wacc):
    frame = get_damodaran_data("wacc", edition=edition, region=region)
    assert frame.SourceURL.eq(SITE + "pc/" + filename).all()
    assert frame.Region.eq(region).all() and frame.Edition.eq(edition or "2026-01").all()
    assert frame.RowType.value_counts().to_dict() == {"Industry": 94, "MarketAggregate": 2}
    assert frame.Currency.eq("USD").all() and frame.IndustryName.is_unique
    advertising = frame.set_index("IndustryName").loc["Advertising"]
    assert advertising.NumberOfFirms == count
    assert advertising[["CostOfEquityPercent", "PretaxCostOfDebtPercent", "ReportedTaxRatePercent",
                        "AfterTaxCostOfDebtPercent", "CostOfCapitalPercent"]].tolist() == pytest.approx(
        [equity, pretax, tax, after_tax, wacc])
    assert advertising.EquityWeightPercent + advertising.DebtWeightPercent == pytest.approx(100)
