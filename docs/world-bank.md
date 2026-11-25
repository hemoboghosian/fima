# World Bank World Development Indicators

`fima.WORLD_BANK` provides four pandas functions for the World Bank's current
World Development Indicators (WDI, source ID `2`). The official Indicators API
v2 uses public HTTPS endpoints and requires no API key. Source discovery shows
the source supported by fima. The World Bank's broader catalog lists additional
databases with their own contracts. [Indicators API v2](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api), [World Bank source catalog](https://api.worldbank.org/v2/source?format=json), [WDI dataset](https://datacatalog.worldbank.org/infrastructure-data/search/dataset/0037712/world-development-indicators)

## Discover an indicator and build a panel

```python
from fima import (
    get_world_bank_countries,
    get_world_bank_indicators,
    get_world_bank_series,
    get_world_bank_sources,
)

print(get_world_bank_sources())
print(get_world_bank_countries(search="iran"))
print(get_world_bank_indicators(search="consumer prices")[
    ["Indicator", "IndicatorName", "Description"]
])

history = get_world_bank_series("FP.CPI.TOTL.ZG", ["IRN", "USA"], 2000, 2025)
metadata = history.attrs.copy()
panel = history.pivot(index="Period", columns="Country", values="Value")
print(panel.sort_index())
print(metadata["IndicatorMetadata"])
print(metadata["Coverage"])
```

Search accepts a literal case-insensitive substring. Geography search examines
the World Bank code, its two-character code and published name. Indicator
search examines the code, name, definition, catalog unit and topic names.
`None` lists the catalog and no matches yield a typed empty frame. Choose the
exact codes from `Country` and `Indicator` for retrieval. The series function
trims whitespace and normalizes ASCII code case. It takes one indicator and
one to 20 distinct geography codes. Years are inclusive integers from 1960
through the current year. A same-year request is valid.

Geography discovery lists economies, including territories, by default. Use
`get_world_bank_countries(include_aggregates=True)` to include `World`, `Region`,
`IncomeGroup`, `LendingGroup`, `OtherAggregate`, and WDI geographies with
`GeographyType="Unknown"` when general country metadata is unavailable. `Country`
is the exact WDI provider code, including codes such as `XKX` and `HIC`.
`CountryCode2` preserves the published two-character identifier when available.
Keep `GeographyType` with your data when mixing economies and groups. Treat `WLD`
and `HIC` as separate aggregate series and account for overlapping membership
before computing totals. When stacking indicators, retain `SourceId` and
`Indicator` alongside `Country` and `Period`. Save each call's attrs before
concatenation or export.

## Public API and schemas

The functions are available in `fima` and `fima.WORLD_BANK`.

```python
def get_world_bank_sources() -> pd.DataFrame: ...

def get_world_bank_countries(
    include_aggregates: bool = False,
    *,
    search: str | None = None,
    source: Literal["WDI"] = "WDI",
) -> pd.DataFrame: ...

def get_world_bank_indicators(
    search: str | None = None,
    *,
    source: Literal["WDI"] = "WDI",
) -> pd.DataFrame: ...

def get_world_bank_series(
    indicator: str,
    countries: str | list[str] | tuple[str, ...],
    start_year: int,
    end_year: int,
    *,
    source: Literal["WDI"] = "WDI",
) -> pd.DataFrame: ...
```

All frames have a `RangeIndex`. Columns use pandas nullable `string` unless
marked otherwise below. Blank optional strings become `pd.NA`. Discovery sorts
by code. Series follow the requested geography order and ascending `Period`.

| Function | Columns in order and dtype exceptions |
| --- | --- |
| `get_world_bank_sources` | `SourceId`, `SourceCode`, `Source`, `SourceUpdateDate`, `DataAvailable` (`boolean`), `MetadataAvailable` (`boolean`), `SourceURL` |
| `get_world_bank_countries` | `Country`, `CountryName`, `CountryCode2`, `GeographyType`, `Region`, `IncomeLevel`, `LendingType`, `SourceId` |
| `get_world_bank_indicators` | `Indicator`, `IndicatorName`, `Description`, `SourceId`, `Source`, `SourceOrganization`, `Unit`, `TopicIds` (`object`), `Topics` (`object`) |
| `get_world_bank_series` | `Country`, `CountryName`, `GeographyType`, `Indicator`, `IndicatorName`, `SourceId`, `Source`, `Period`, `Frequency`, `Value` (`float64`), `Unit`, `ObservationStatus`, `Footnote`, `Decimals` (`Int64`) |

Discovery keeps the WDI geography name. `Region`, `IncomeLevel`, and
`LendingType` are published economy labels and are missing for aggregates.
`TopicIds` and `Topics` are aligned tuples in provider order, empty when no
topics are reported. Indicator discovery shows explicitly published catalog
units. Series keep observation geography labels and the primary catalog
indicator name. `ObservationStatus` can carry codes such as `F` for forecast
and `Footnote` carries published text. Missing statuses leave the observation
status unspecified. `Decimals` is the publisher's display hint.

## Values, periods and units

`Period` is the publisher's `YYYY` annual observation label and can reflect a
reporting calendar. `Frequency` is `A`. fima validates the annual labels and
checks published periodicity when available. A declared nonannual indicator
raises `ValueError`. An empty response requires annual periodicity metadata to
establish frequency.

`Value` is the finite JSON number at double precision. A value reported as
12.5 percent stays `12.5`. All values retain the publisher's scale and
precision, including zero and negative values. A JSON null becomes `NaN`.
Missing periods produce no rows. Refer to `Coverage` for the distinction.

Consistent observation or catalog units take precedence. For blank explicit
units, a recognized rich metadata unit must agree with the indicator's
explicit title unit. Reviewed definitions can supply the unit where rich unit
metadata is blank. Examples include the FDI inflows share of GDP and the 2015
base for the net barter terms of trade index. Conflicting or unsupported
evidence can leave `Unit` missing. `IndicatorMetadata` keeps the original unit
evidence, definitions, and chosen `UnitSource` for inspection.

| Example code | Meaning |
| --- | --- |
| `NY.GDP.MKTP.CD` | GDP at current prices in US dollars |
| `NY.GDP.MKTP.KD.ZG` | Growth in constant-price GDP, in annual percent |
| `FP.CPI.TOTL.ZG` | Annual percent change in consumer prices |
| `FP.CPI.TOTL` | Consumer price index with a 2010 base of 100 |
| `PA.NUS.FCRF` | Official period-average exchange rate, local currency per US dollar |
| `FS.AST.PRVT.GD.ZS` | Domestic credit to the private sector as a percent of GDP |
| `DT.DOD.DECT.CD` | External debt stock in current US dollars |
| `BX.KLT.DINV.WD.GD.ZS` | Net inward direct investment flows as a percent of GDP |

Read the definition and limitations before comparing series. Annual consumer
inflation and GDP-deflator inflation track different price baskets. Official
exchange rates reflect legally sanctioned rates. Lending rates describe loans
under provider definitions. Debt stocks and debt-service flows have distinct
measures and units. Market capitalization measures equity value, and traded
value measures trading activity.

## Coverage, provenance and errors

All results include `Provider`, `SourceId`, `SourceCode`, `Source`, `SourceURL`,
`RequestURLs`, `RetrievedAt`, `SourceUpdateDate`, `DatasetURL`, `License` and
`TermsURL` in `DataFrame.attrs`. `SourceURL` identifies the first page of the
primary result and `RequestURLs` lists verified page URLs in request order.
`RetrievedAt` is UTC. `SourceUpdateDate` is the API's date for the current source
snapshot when supplied. This date can differ from the Data Catalog update date.
WDI can revise or remove historical values, including within the same day.
The observation period carries no vintage or publication date. The separate
WDI archive serves historical editions. [WDI revisions policy](https://datahelpdesk.worldbank.org/knowledgebase/articles/114939-how-are-revisions-managed), [WDI archives](https://datatopics.worldbank.org/world-development-indicators/wdi-archives.html)

Series also include:

- `IndicatorMetadata` with the primary name, rich metadata name, definition,
  source organizations, periodicity, reference period, unit evidence,
  limitations, indicator rights and metadata URL.
- `Coverage` with an ordered entry per requested `Country`, including
  `ReturnedPeriods`, `NullPeriods` and `OmittedPeriods`.
- `Pagination` with `AdvertisedRecords`, `ReturnedRecords`, `Pages`, and `PageSize`.
- `Completeness="ProviderCountsReconciled"`, `RequestedCountries`, `StartYear`
  and `EndYear`.

The client checks page numbers, counts and source update metadata, and validates
every observation against the requested geography, indicator and years. Some
World Bank date filters have returned default history. Out-of-scope periods
raise an error. Duplicated records, inconsistent pages and page failures also
raise an error before any frame is returned. Reconciled counts describe the
transfer from the provider. Historical coverage varies by economy and indicator.
A verified empty response lists every requested year as omitted. Returned rows
with null values count toward the reported page totals.

Invalid arguments, unknown identifiers, and declared unsupported frequencies
raise `ValueError`. Provider, HTTP, network, budget and validation failures
raise `RuntimeError`, including error envelopes sent with HTTP 200. The client
uses verified HTTPS, bounded retries for transient failures, pages of up to 500
records, a 20-page limit per endpoint, a 2 MiB decoded response limit, and a
120-second call budget. Each call fetches fresh metadata and may receive a
provider-cached response.

Run the optional provider tests with
`python -m pytest -m integration test/test_world_bank_integration.py`.

## Attribution

WDI's dataset-level license is CC BY 4.0 under the World Bank dataset terms.
Check the indicator license and source organization before redistribution.
Third-party data can carry separate rights. When sharing data, credit the World
Bank, World Development Indicators and the known underlying source in that
order. Include the dataset link, terms, retrieval date and applicable indicator
rights, and identify substantive transformations. The MIT license covers fima's
code. [World Bank dataset terms](https://www.worldbank.org/ext/en/legal/terms-conditions/datasets), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

For the CPI example, the credit is “The World Bank, World Development
Indicators, International Financial Statistics database, International
Monetary Fund (IMF).” Consult the current `SourceOrganization` when exporting.
