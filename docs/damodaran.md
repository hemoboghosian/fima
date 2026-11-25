# Damodaran valuation inputs

fima retrieves three tables published by Aswath Damodaran at NYU Stern. It finds the official workbook, checks its edition and layout, and returns a pandas DataFrame. A regular `pip install fima` includes `xlrd` for XLS and `openpyxl` for XLSX.

## Discover datasets and editions

```python
from fima import get_damodaran_datasets

catalog = get_damodaran_datasets(include_history=True)
print(catalog[["Dataset", "Region", "Edition", "IsLatest"]].to_string(index=False))
```

Without `include_history=True`, discovery lists the current workbook per supported dataset and region. Pass a dataset name to narrow the table. Discovery reads the publisher's catalogs and does not open the workbooks. `SourceURL` in this table is the selected link.

| Dataset ID | Other accepted names | Region | Verified editions |
| --- | --- | --- | --- |
| `country_risk_premiums` | `country risk premiums`, `country risk premium` | Omit `region`. The workbook contains countries and territories. | `2025-01`, `2026-01`, `2026-04`, `2026-07` |
| `industry_betas` | `industry betas`, `industry beta`, `betas`, `بتای صنعت` | `Global` or `US` | `2025-01`, `2026-01` |
| `industry_cost_of_capital` | `industry cost of capital`, `cost of capital`, `wacc` | `Global` or `US` | `2025-01`, `2026-01` |

Names ignore case and normalize Unicode and whitespace. Industry calls default to `Global`. `World` also means `Global`, and `U.S.` and `United States` mean `US`. The author's Global universe includes overlapping regional coverage. Use `edition="YYYY-MM"` for a specific snapshot. The default follows the latest link for the selection in the [current catalog](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datacurrent.html). January 2025 is in the [archive](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/dataarchived.html). An unverified new current edition raises an error. Earlier verified editions remain selectable while their links are available.

## Country risk premiums

```python
from fima import get_damodaran_data

country = get_damodaran_data("country risk premiums")
print(country.loc[country["Country"].eq("Iran"), [
    "Country", "RiskMethod", "CountryRiskPremiumPercent", "EquityRiskPremiumPercent", "Edition",
]])
```

| Columns | Meaning |
| --- | --- |
| `Country`, `CountryRegion` | Published country or territory name and source grouping. Names can include subnational markets such as Abu Dhabi. The rated table's region header displays `Africa`, but the values describe the individual countries' regions. |
| `RiskMethod`, `MoodysRating` | `RatingBased` for the Moody's sovereign rating method or `FrontierPrs` for the publisher's frontier-market method. Frontier observations have missing region and rating fields. |
| `DefaultSpreadPercent` | Rating-based sovereign credit spread or the default spread implied by the frontier method. The output is in percentage points. The separate workbook lookup in basis points is outside the output. |
| `CountryRiskPremiumPercent`, `EquityRiskPremiumPercent` | Incremental country equity premium and total equity premium, respectively. The total normally includes the mature-market equity base. The source applies its own benchmark treatment, including a separate US input in 2026. |
| `SovereignCdsNetSpreadPercent`, `CdsBenchmark` | Sovereign credit default swap (CDS) spread net of the reference sovereign. The reference is `US` in January 2025 and `Switzerland` in the verified 2026 editions. Signed spreads are preserved. |
| `CdsBasedCountryRiskPremiumPercent`, `CdsBasedEquityRiskPremiumPercent` | Incremental and total equity premiums from the CDS method. Frontier rows and rated markets without CDS inputs have missing CDS values. Published zeroes are retained. |

`Edition="2026-07"` identifies the July 1 snapshot. `SourceUpdateDate` is July 9 for the corrected default spreads. January 2026 records the February 16 sovereign rating revision. April records April 1 and preserves the inherited February note separately in attrs.

## Industry betas

```python
from fima import get_damodaran_data

betas = get_damodaran_data("industry betas", region="US", edition="2025-01")
print(betas.loc[betas["RowType"].eq("Industry"), [
    "IndustryName", "LeveredBeta", "UnleveredBeta", "CashAdjustedUnleveredBeta",
]].head())
```

| Columns | Meaning |
| --- | --- |
| `LeveredBeta`, `UnleveredBeta`, `CashAdjustedUnleveredBeta` | Average equity regression beta, beta after removing the effect of leverage, and the latter adjusted for cash to estimate operating-asset beta. All three are dimensionless. |
| `DebtToEquityPercent`, `CashToFirmValuePercent` | Published aggregate debt divided by market equity and cash divided by equity plus debt, respectively. The workbook uses debt including leases. |
| `EffectiveTaxRatePercent`, `UnleveringTaxBasis` | Displayed trailing effective tax rate and separate workbook setting for the rate used when unlevering. |
| `HiLoRisk` | Average annual high-low share price range divided by the sum of high and low prices, a dimensionless ratio. |
| `EquityVolatilityPercent`, `OperatingIncomeVariation10YearPercent` | Published equity volatility and the average firm-level coefficient of variation of ten years of operating income. The workbook can report the latter as missing. |

The main beta table has separate rolling references in the workbook. The API returns the main table's snapshot metrics. See the workbook FAQ for the edition-specific regression methodology.

## Industry cost of capital

```python
from fima import get_damodaran_data

capital = get_damodaran_data("wacc", region="Global")
print(capital[["IndustryName", "CostOfEquityPercent", "AfterTaxCostOfDebtPercent",
               "CostOfCapitalPercent", "Currency"]].head())
```

| Columns | Meaning |
| --- | --- |
| `Beta`, `EquityVolatilityPercent` | Average regression beta and stock return volatility used in the workbook. |
| `CostOfEquityPercent`, `EquityWeightPercent`, `DebtWeightPercent` | Required equity return and the market equity and debt weights in aggregate equity plus debt. |
| `PretaxCostOfDebtPercent`, `AfterTaxCostOfDebtPercent`, `ReportedTaxRatePercent` | Published debt costs before and after the tax shield, with the displayed tax rate in its own column. The rate used for the tax shield can differ from the displayed rate. |
| `CostOfCapitalPercent`, `Currency` | Published weighted average cost of capital (WACC) and its `USD` basis for both US and Global. The optional local-currency calculation is outside the API. |

The table preserves the workbook's cached WACC. It also reports the debt and equity costs, weights and tax data as published. Pricing and tax assumptions are available in `SourceAssumptions`.

## Schemas and provenance

- Discovery columns, in order, are `Dataset`, `DatasetName`, `Category`, `Description`, `Region`, `Edition`, `IsLatest`, `UpdateFrequency`, `Source`, `SourceURL`, `CatalogURL`, `FileFormat`, `DefinitionsURL`.
- Country data starts with `Country`, `CountryRegion`, `RiskMethod`, `MoodysRating`, `DefaultSpreadPercent`, `CountryRiskPremiumPercent`, `EquityRiskPremiumPercent`, `SovereignCdsNetSpreadPercent`, `CdsBenchmark`, `CdsBasedCountryRiskPremiumPercent`, `CdsBasedEquityRiskPremiumPercent`.
- Both industry tables start with `IndustryName`, `IndustryClassification`, `RowType`, `NumberOfFirms`. Beta adds `LeveredBeta`, `DebtToEquityPercent`, `EffectiveTaxRatePercent`, `UnleveredBeta`, `CashToFirmValuePercent`, `CashAdjustedUnleveredBeta`, `HiLoRisk`, `EquityVolatilityPercent`, `OperatingIncomeVariation10YearPercent`, `UnleveringTaxBasis`.
- Cost of capital adds `Beta`, `CostOfEquityPercent`, `EquityWeightPercent`, `EquityVolatilityPercent`, `PretaxCostOfDebtPercent`, `ReportedTaxRatePercent`, `AfterTaxCostOfDebtPercent`, `DebtWeightPercent`, `CostOfCapitalPercent`, `Currency`.
- Each retrieval appends `Dataset`, `Region`, `Edition`, `DataAsOf`, `DataAsOfPeriod`, `Source`, `SourceURL`, `SourceUpdateDate`, `RetrievedAt`.

Percentages are percentage points, so `12.5` is 12.5%. Financial columns use pandas nullable `Float64`, firm counts use nullable `Int64`, identities use nullable strings, and `IsLatest` is a boolean. `SourceUpdateDate` is a publisher-supplied date and `RetrievedAt` is the original download time in UTC. `DataAsOf` and `DataAsOfPeriod` are missing because the supported workbooks combine inputs with different observation periods. The final workbook link is in `SourceURL`.

`Region` represents the selected industry universe and is missing for country risk. `RowType` identifies `Industry` and `MarketAggregate`. The source spelling `Tiotal Market` is preserved in the affected January 2025 Global files. `IndustryClassification` identifies a publication slice using dataset, region, edition and a fingerprint of its labels. Treat every edition as a separate cross-section. Even matching labels across years can correspond to different industry groupings.

`df.attrs` carries the original sheet and headings, definitions, source assumptions, revision notes when available, and separate HTTP metadata. Pandas may drop attrs during operations such as concatenation or serialization. Use the row-level columns to retain identity and edition. Validation can confirm that the published tables include both country sections or both industry market aggregates. It cannot verify that the publisher included every possible country or industry.

## Verified workbook links

These are the links inspected for the supported layouts. Discovery follows the official catalogs at runtime.

| Selection | January 2025 | January 2026 | April 2026 | July 2026 |
| --- | --- | --- | --- | --- |
| Country risk premiums | [XLSX](https://pages.stern.nyu.edu/~adamodar/pc/archives/ctryprem24.xlsx) | [XLSX](https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx) | [XLSX](https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctrypremApr26.xlsx) | [Corrected XLSX](https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctrypremJuly26.xlsx) |
| Global industry betas | [XLS](https://pages.stern.nyu.edu/~adamodar/pc/archives/betaGlobal24.xls) | [XLS](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betaGlobal.xls) | | |
| US industry betas | [XLS](https://pages.stern.nyu.edu/~adamodar/pc/archives/betas24.xls) | [XLS](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls) | | |
| Global cost of capital | [XLS](https://pages.stern.nyu.edu/~adamodar/pc/archives/waccGlobal24.xls) | [XLS](https://pages.stern.nyu.edu/~adamodar/pc/datasets/waccGlobal.xls) | | |
| US cost of capital | [XLS](https://pages.stern.nyu.edu/~adamodar/pc/archives/wacc24.xls) | [XLS](https://pages.stern.nyu.edu/~adamodar/pc/datasets/wacc.xls) | | |

## Downloads, errors and data use

The module uses HTTPS with size limits, timeouts and at most one retry for eligible transient errors. It keeps a six-hour in-process catalog cache and up to 16 validated workbooks as parsed DataFrames for 24 hours. `refresh=True` immediately revalidates the relevant catalog and download. If the publisher returns HTTP 304, `RetrievedAt` keeps the download time and the DataFrame records `RevalidatedAt` in attrs. An unavailable source, failed revalidation or unexpected workbook raises `RuntimeError` with source context. An invalid or unavailable selection raises `ValueError`.

All data comes from Aswath Damodaran, NYU Stern. The API retrieves published aggregate valuation inputs on demand. Company-specific commercial data, unrelated workbook fields and historical industry crosswalks are outside its scope. Consult the publisher's [usage rules](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datahistory.html#rules), [data definitions](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/variable.htm), and [industry and regional methodology](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/databreakdown.html) before using or redistributing the data. fima ships only the retrieval code and documentation.
