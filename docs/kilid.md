# KILID housing-market data

[User guide](../README.md) | [API](api.md) | [Data conventions](data-conventions.md)

Added in **0.15.0**. This module reads KILID's public, server-rendered aggregate tables at
<https://kilid.com/house-prices>. It adds no dependency, paid-service requirement,
import-time HTTP or recursive crawler.

## Financial meaning

The ordinary housing series is the **median apartment asking/listing price per
square meter**. It is not completed transaction data, an official registered
transaction average, a hedonic index or a constant-quality price index. Changes
in the composition of listings can change a median. KILID's generic FAQ also
discusses other indices; those definitions must not be applied to this table.

Use source denominations directly:

| Argument | `Unit` | Meaning |
| --- | --- | --- |
| `toman` | `TomanPerSquareMeter` | Tomans per m²; no rial conversion |
| `usd` | `USDPerSquareMeter` | Published dollars per m², using the corresponding month's free-market USD price |
| `gold` | `Gram18KGoldPerSquareMeter` | Published grams of 18-karat gold per m², using the corresponding month's gold price |

Gold is neither a mithqal nor 24-karat gold. No conversion is recomputed through
TGJU, current exchange rates or another provider. Values retain the precision
displayed by KILID (including rounded million/billion toman figures), rather
than claiming unavailable underlying precision. Percentage values use percentage
points: `24.3` means `24.3%`.

## Discover locations

```python
from fima import get_kilid_areas

cities = get_kilid_areas()
tehran_areas = get_kilid_areas("tehran")
neighborhoods = get_kilid_areas("tehran-region5")
print(neighborhoods[["Area", "AreaName", "DataBasis"]])
```

`get_kilid_areas(area=None) -> pandas.DataFrame` performs one GET. `None` reads
the published city list; a source slug reads that page's related-area comparison
list, including folded rows. It does not fetch every listed area's history or
promise nationwide historical coverage. Slugs, including source punctuation
such as `sowme'eh_sara`, are string identifiers. Display names alone are not
unique identifiers. Numeric area codes were not established.

Columns (all pandas `string`): `Area`, `AreaName`, `AreaLevel`,
`ListedUnderArea`, `DataBasis`, `SourceURL`. `ListedUnderArea` is missing for
the country list. Source model estimates remain discoverable and classified.

`AreaLevel` is conservative: root entries are published as cities; explicitly
named numbered regions are `Region`; areas displayed under a verified region
are `Neighborhood`. Unestablished levels remain `Area`. The Tehran city page
mixes regions with other areas. A neighborhood page can compare siblings,
including itself: **ListedUnderArea describes display context, not verified
parentage**. No universal Tehran-style 22-region hierarchy is hardcoded.

History and snapshot identities additionally include `SourceParentArea` from
the page's JSON-LD breadcrumb (missing for a city directly under the index).
This preserves the source hierarchy, not a guarantee of administrative
boundaries. In the audited source, Shahriar appears in the city list while its
own breadcrumb sits under Tehran; its individual-page level remains `Area`.
Neighborhood slugs need not contain their region number. Boundary revisions and
stable numeric geographic IDs were not established.

## Monthly price history

```python
from fima import get_kilid_house_price_history

usd = get_kilid_house_price_history("tehran-region5", period="3y", denomination="usd")
print(usd[["JalaliMonth", "MedianListingPricePerSquareMeter", "Unit"]].tail())
gold = get_kilid_house_price_history("tehran-region5", "3y", "gold")
```

`get_kilid_house_price_history(area, period="1y", denomination="toman")`
returns a DataFrame. Only advertised `6m`, `1y` and `3y` periods and `toman`,
`usd`, `gold` denominations are supported. Arbitrary date ranges and the paid
1389–1405 report are outside this API.

| Columns | dtype / meaning |
| --- | --- |
| `JalaliMonth` | `string`, ASCII `YYYY-MM`, chronological reporting-month label |
| `Area`, `AreaName`, `AreaLevel`, `SourceParentArea` | `string`, source identity |
| `MedianListingPricePerSquareMeter` | nullable `Float64`, in the explicit `Unit` |
| `Denomination`, `Unit`, `SourceURL` | `string`, selection and provenance |

The index is an ordinary RangeIndex. No day or Gregorian observation date is
invented for a month label. Different denominations can end in different months;
align explicitly on `Area` and `JalaliMonth`, retaining missing observations.
The latest local-currency month can be incomplete. `CurrentMonthIncluded` in
`attrs` identifies whether the last returned month is the retrieval month in
`Asia/Tehran`, including hours when UTC still has the previous calendar date.

The parser validates the canonical URL, structured identity, visible heading,
selected period/price mode/denomination, unit suffixes, methodology, full table,
chart/table bounds, chronological unique months and numerical values. It checks
every month between the published endpoints, without requiring the number of
rows to equal the selected window. A published missing-value marker remains
`pd.NA`; a missing *row* inside the bounds causes `RuntimeError` because a
continuous history cannot be verified. Modeled/imputed area statistics are not
accepted as proof of an observed listing history. Empty, missing, all-missing or
unverifiable history tables raise; no successful empty-history contract was
observed and none is invented.

`Completeness="PublishedTableAndMonthBounds"` means the complete validated
displayed table, not all historical KILID records or an independently audited
database. Historical revisions, window inclusivity beyond the displayed month
endpoints and a fixed update schedule were not established. No records are
filled, interpolated, deduplicated silently or reconstructed from chart geometry.

## Published snapshots

```python
from fima import get_kilid_house_price_snapshot

snapshot = get_kilid_house_price_snapshot("tehran-region5-moradabad")
print(snapshot[["JalaliMonth", "Metric", "Value", "Unit", "DataBasis"]])
```

`get_kilid_house_price_snapshot(area)` returns the latest available published
market-statistic sections in **long format**, with one row per supported metric:

| `Metric` | `Unit` |
| --- | --- |
| `MedianListingPricePerSquareMeter` | `TomanPerSquareMeter` |
| `MedianTotalListingPrice` | `Toman` |
| `MonthlyListingPriceChange` | `Percent` |
| `MedianEffectiveRentalListingPricePerSquareMeter` | `TomanPerSquareMeterPerMonth` |
| `EstimatedTypicalDwellingEffectiveMonthlyRent` | `TomanPerMonth` |
| `RentalListingCount` | `Listings` |

Columns: `Area`, `AreaName`, `AreaLevel`, `SourceParentArea`, `JalaliMonth`,
`Metric`, `Value`, `Unit`, `DataBasis`, `SourceURL`. Only `Value` is nullable
`Float64`; the other columns are pandas `string`. Counts are whole numbers in
this common numeric column. Rental measures are KILID's published effective
monthly rental-listing statistics; no deposit-to-rent formula is inferred or
recalculated. A median total listing price is distinct from an estimated typical
dwelling price; the separate highlight card is not used as a substitute.

Each row retains its section's reporting month. A missing rental section with
the source's explicit empty message adds `RentalListings` to
`attrs["UnavailableSections"]` and yields no fabricated zero rental rows.
Unsupported indicators are omitted. The undefined liquidity indicator,
property-size distribution, forecast outputs and uncertain rental-yield/deposit
definitions are not exposed in this first version.

`DataBasis` is `PublishedListings` when no model/imputation badge is present,
`Modeled` for source `MODELED`, and `Imputed` for source `IMPUTED`.
The explicitly estimated typical rental dwelling metric uses `SourceEstimate`
when there is no stronger source badge. These labels do not certify data quality;
modeled values are not observed medians despite the source card's generic label.

## Compare areas

```python
from fima import get_kilid_area_comparison

comparison = get_kilid_area_comparison("tehran-region5")
print(comparison[["Area", "AreaName", "PublishedPricePerSquareMeterToman",
                  "PublishedYearlyPriceChange", "DataBasis"]])
```

`get_kilid_area_comparison(area)` reads every published related-area table row,
including the collapsed continuation. It excludes the unlabeled aggregate parent
row, preserves source order and cross-checks the area-chip enumeration where
present. City discovery also checks the separately published city count. Missing
comparison tables/rows or conflicting month labels fail instead of producing a
partial result.

Identity/context columns are `Area`, `AreaName`, `AreaLevel`, `ListedUnderArea`,
`JalaliMonth`, `DataBasis`, `SourceURL` (all `string`). Numerical `Float64`
columns are:

- `PublishedPricePerSquareMeterToman`
- `PublishedPricePerSquareMeterUSD`
- `PublishedPricePerSquareMeterGold18KGrams`
- `PublishedMonthlyPriceChange`
- `PublishedYearlyPriceChange`

Prices retain the named currency/18K-gold-per-m² units; growth values are
percentage points. The source's absent USD/gold values remain missing even when
a toman value is present. `Published` acknowledges that some comparison rows are
explicitly model estimates. Comparison growth is taken from its own table, not
from the chart's indicator tiles.

## Provenance, errors and access

Every result has PascalCase `attrs` including `SourceURL`, `RetrievedAt` (UTC),
`SourceDateModified`, `SourceTemporalCoverage`, `MetadataWarnings` and
`SourceBreadcrumb` (records containing `AreaName` and `SourceURL`). Raw source
modification/coverage metadata is retained separately from table month labels;
it is not a verified freshness timestamp. History attrs additionally contain
`RequestedMonths`, `SourceRowCount`, `FirstJalaliMonth`, `LastJalaliMonth`,
`CurrentMonthIncluded`, `PriceBasis` and `Completeness`. Snapshot/comparison
attrs identify `SourceSection`; comparisons also give `SourceRowCount`,
`Scope`, `PercentageUnit` and the ordered `PriceUnits`.

Warnings identify future, invalid or conflicting modification metadata and
metadata coverage that differs from actual table bounds. The future-date check
uses retrieval time; it does not alter data periods. Future history months are
rejected. Neither source update frequency nor retrospective revision policy has
been verified. There is no cache or freshness guarantee.

All functions raise `ValueError` for invalid arguments and `RuntimeError` for
HTTP/network/TLS errors, redirects, access restrictions, malformed or incomplete
responses, wrong identity/selection/units and unverified history completeness.
Underlying network exceptions are chained. HTTP 429 preserves `Retry-After` in
the message; there are **no automatic retries**. Respect the provider's waiting
period and access restrictions. Requests use a declared fima User-Agent, verified
HTTPS, connect/read timeouts of 10/30 seconds and no cookies or redirect following.
Each call performs one public GET. It does not solve challenges or switch to
private endpoints when access fails.

Access audit on **2026-11-17**:

- [robots.txt](https://kilid.com/robots.txt) permits `/house-prices` under its
  general rule; `/neighborhoods-preview/` is explicitly disallowed and unused.
- [Current terms](https://kilid.com/terms), general section article 8, reserve
  content/intellectual-property rights. No express automated-access prohibition
  was found. Public visibility, free-access metadata and crawler permission do
  **not** establish an open data or redistribution license. Permission for
  automated reuse/redistribution remains unresolved; obtain a KILID data
  agreement or written clarification for those uses. fima's MIT license does not
  grant rights in KILID data. Recheck current provider rules before collection;
  stop if access is prohibited or restricted.
- The audited pages and numerical tables were accessible without authentication,
  payment or a challenge. No documented reusable public API or aggregate export
  was established from these pages; none is assumed. An official API/export or
  data agreement would be legitimate alternatives if public access changes.
- The separately purchasable 1389–1405 market report, private listings, contacts
  and authenticated services are outside this module. No access-control, rate
  limit, WAF, CAPTCHA or TLS bypass is supported.
- Fixtures retain only small aggregate-table/identity excerpts with source
  attribution; they are not a public historical-data redistribution product.

## Source validation record

Representative ordinary requests all returned HTTP 200 without redirects:
the index, Tehran, Tehran region 5 (default/36-month toman, 6/36-month USD,
36-month gold), Tehran region 1, Moradabad and linked city Shahriar.
No exhaustive crawl was performed.

| Region 5 selection | Rows | First month | Last month | First → last price per m² |
| --- | ---: | --- | --- | --- |
| 3y toman | 36 | 1402-09 | 1405-08 | 90,000,000 → 290,900,000 toman |
| 3y USD | 35 | 1402-09 | 1405-07 | 1,783 → 1,060 USD |
| 3y gold | 35 | 1402-09 | 1405-07 | 36.6 → 10.7 grams of 18K gold |
| 6m USD | 6 | 1405-02 | 1405-07 | 1,180 → 1,060 USD |
| 1y toman | 12 | 1404-09 | 1405-08 | 126,200,000 → 290,900,000 toman |

The index listed 36 cities; Tehran's comparisons had 22 regions and 18 other
areas; region 5 had 25 neighborhood comparisons. These are observations, not
fixed parser constants or a claim that every listed area has history.

Source limitations intentionally retained:

- Dataset/WebPage `dateModified=2026-11-22T00:00:00.000Z` was future-dated
  relative to retrieval. USD/gold table endpoints also differed from shared
  temporal metadata; warnings expose this rather than changing observations.
- Region 1's latest chart value was 571.3 million toman, while listing statistics
  showed 571.4 million. Moradabad's chart showed 367.8 million versus 371.4
  million in statistics for the same labeled month. Functions preserve their
  source sections; they do not force them to agree.
- Region 5's annual-growth indicator tile differed from the comparison parent
  aggregate. Snapshot omits that ambiguous annual tile. Comparisons retain each
  child's published table growth rather than substituting tile values.
- Shahriar's chart had interior missing months and its sale statistics were
  modeled/imputed; history is rejected. Its rental section reported 1402-04,
  while sale statistics reported 1405-08; snapshot rows retain both periods.

Deterministic source-shaped tests exercise these contracts without HTTP. Live
tests compare every numerical history row against the same returned public
HTML, plus discovery/comparisons/statistics, without fixed live market counts:

```shell
python -m pytest test/test_kilid.py -q --strict-markers
python -m pytest -m "not integration" --strict-markers
python -m pytest test/test_kilid_integration.py -m integration -q -s --strict-markers
```

Live failures are reported, not silently skipped. A reachable source is not
evidence of a data license, complete nationwide coverage or future reliability.
