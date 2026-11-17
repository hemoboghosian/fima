# IMF annual WEO data (0.16.0)

`fima.IMF` provides four pandas functions for the **selected annual World
Economic Outlook indicators in the official IMF DataMapper v2**. It is available
starting with fima 0.16.0.
No account or API key is needed for the tested DataMapper requests.

## Source feasibility and choice

Checked 2026-11-17 with ordinary GET, finite timeouts and verified HTTPS.
[Official API documentation](https://www.imf.org/external/datamapper/api/help)
explicitly identifies v2 and links its catalogs and series examples.

| Candidate | Evidence and access | Scope/metadata | Decision |
| --- | --- | --- | --- |
| [Modern Data Portal APIs](https://data.imf.org/en/Resource-Pages/IMF-API) | SDMX 2.1 and 3.0 WEO dataflows returned HTTP 200 without credentials at `api.imf.org/external/sdmx`. A country-selected SDMX 3.0 data query also returned real annual observations. The linked API explorer redirects to sign-in; this did not prevent these public API queries. | Broader datasets, dimensional metadata and native scales; advanced attributes require additional parsing and source validation. | Viable future expansion; a general SDMX client is outside this small integration. |
| [DataMapper v2](https://www.imf.org/external/datamapper/api/v2/indicators) | HTTP 200 `application/json`, no credentials, no redirects; official help documents this version. GET catalogs and series work. | 132 indicators across 13 dataset IDs at investigation; this client deliberately supports the 15 WEO indicators only. Inline units, definitions, edition, modification timestamp, projection-year. Annual coverage varies by series/geography. | Selected: small documented JSON contract, using existing requests/pandas dependencies. |
| DataMapper v1 | Indicator catalog and selected series also returned HTTP 200 JSON unauthenticated. | Series omit inline indicator metadata and projection-year present in v2. | Not used: official help names v2 as current. |
| Legacy CompactData / SDMX Central | Not used or required for this implementation. | Legacy support was not established; SDMX Central metadata is not evidence of Data Portal observation access. | No fallback to retired/unsupported services. |

Exact modern SDMX checks: `/external/sdmx/2.1/dataflow/IMF.RES/WEO/latest`,
`/external/sdmx/3.0/structure/dataflow/IMF.RES/WEO/+`, and
`/external/sdmx/3.0/data/dataflow/IMF.RES/WEO/+/IRN.NGDP_RPCH.A`.
The first observation probe appended `startPeriod`/`endPeriod`, which the server
ignored; a later 3.0 time-constraint probe did not establish a working bounded
time filter. No production SDMX parser or filter contract is claimed here.
The SDMX GDP response has more precision than DataMapper's rounded values;
rounded agreement is not an assertion that every edition/definition matches.

Tested DataMapper endpoints use base
`https://www.imf.org/external/datamapper/api/v2/`:

- `indicators`, `countries`, `regions`, `groups`.
- `NGDP_RPCH/IRN/USA?periods=2024,2025,2026,2027`.
- `PCPIPCH/IRN?periods=2025,2026`, `LUR/IRN?periods=2025`.
- `GGXWDG_NGDP/IRN?periods=2025,2026` and selected fiscal-balance requests.
- An invalid indicator returned catalogs with HTTP 200, not an error status.
  fima validates IDs before requesting observations and requires the expected
  series schema rather than treating any HTTP 200 JSON as data.

**Observed filtering limitation:** both v1 and v2 currently ignore country and
`periods` filters in these requests and supply the chosen indicator's available
geographies/history (for example GDP growth, 229 geographies, 1980–2031, about
122 kB). fima sends the documented filters, retrieves this one selected indicator
and filters locally. It never iterates all indicators or downloads the whole
WEO dataset/archive. Each response has a 2 MiB decoded size limit. Do not use
this client to mirror IMF data. The series response's observed empty-key/null
artifact is accepted precisely; unexpected additional indicator values fail.

## Public API and schemas

All four functions are also exported from `fima`. Outputs use a RangeIndex and
PascalCase columns. Text columns use pandas `string`.

### `get_imf_datasets()`

One current supported subset: `Dataset`, `DatasetName`, `Frequency`,
`IndicatorCount` (nullable `Int64`), `SourceURL`. Currently WEO, World Economic
Outlook, annual `A`. Count derives from the current live indicator catalog;
this is not a catalog of every IMF dataset.

### `get_imf_indicators(dataset=None, search=None)`

`dataset` accepts `None` or `"WEO"`. `search` is a nonempty literal,
case-insensitive substring of code, name, definition or unit. Filtering follows
one catalog request. No hand-maintained list controls discovery.

Columns: `Indicator`, `IndicatorName`, `Description`, `Dataset`, `Unit`,
`Frequency`, `Source`, `SourceProjectionYear`, `SourceLastModified`, `SourceURL`.
`SourceProjectionYear` is nullable `Int64`; source last-modified timestamps are
retained as strings without inventing a timezone. `Source` includes the source
edition (October 2026 in the investigated responses). Descriptions can contain
source HTML/line breaks; fima preserves their text. No historical-edition
selector is provided, and future calls can contain revised data.

The following verified WEO IDs illustrate the current catalog:

| Meaning | ID | Native unit/interpretation |
| --- | --- | --- |
| Real GDP growth | `NGDP_RPCH` | Annual percent change in constant-price GDP |
| Nominal GDP | `NGDPD` | Billions of U.S. dollars, current prices |
| Nominal GDP per capita | `NGDPDPC` | U.S. dollars per capita, current prices |
| PPP GDP / per capita | `PPPGDP`, `PPPPC` | Billions of international dollars / international dollars per capita |
| PPP world GDP share | `PPPSH` | Percent of world |
| Implied PPP conversion | `PPPEX` | National currency per international dollar; not a market USD exchange rate |
| Average CPI inflation | `PCPIPCH` | Annual percent change in average CPI |
| End-period CPI inflation | `PCPIEPCH` | Annual percent change in end-period CPI |
| Unemployment | `LUR` | Percent of labor force |
| General-government gross debt | `GGXWDG_NGDP` | Percent of GDP, not a debt level |
| General-government fiscal balance | `GGXCNL_NGDP` | Net lending/borrowing, percent of GDP, not primary balance |
| Current account | `BCA`, `BCA_NGDPD` | Billions of U.S. dollars / percent of GDP |
| Population | `LP` | Millions of people |

Real GDP levels, domestic-currency GDP levels, CPI index levels, reserves
levels, external-debt levels, market exchange rates and monthly/quarterly data
are **not supported** by this selected subset. DataMapper's broader catalog
contains reserve-adequacy ratios; these are not reserve levels and are outside
this client's WEO scope. Searching `"reserves"` returns an empty table rather
than a falsely relabeled series. Ratios, nominal levels, real growth and PPP
measures are not interchangeable. Consult source definitions and current units.

### `get_imf_countries(include_aggregates=False)`

Columns: `Country`, `CountryName`, `GeographyType`, `SourceURL`.
Default discovery fetches countries; `True` additionally fetches regions and
analytical groups, labeled `Region` and `Group` rather than `Country`.
Despite the parameter/column name, `Country` retains the provider's exact
geographic identifier. Some are not ISO3 codes, and alternate source identifiers
are not merged by country name. The live countries catalog had 241 entries;
`ATI` and `ATL` had null labels, preserved as `pd.NA` without guessed names.
Catalog membership does not promise a series for every WEO indicator.

### `get_imf_series(indicator, countries, start_year, end_year)`

Specify an exact supported indicator; `countries` is one exact source ID or a
list/tuple of 1–20 distinct IDs. Countries, regions and groups can be selected
using the discovery result. Years are inclusive integers from 1000 to 9999,
ordered, with at most 200 requested years. Broad defaults and arbitrary source
query syntax are not exposed.

Columns: `Country`, `CountryName`, `GeographyType`, `Indicator`, `Period`,
`Frequency`, `Value`, `Unit`. `Value` is `float64` with NaN for source nulls;
other columns use pandas `string`. Rows follow the requested geography order,
then ascending annual label. `Period` is `YYYY`, with `Frequency="A"`; no daily
dates or monthly observations are invented. Year labels preserve WEO's source
reporting periods, which need not correspond to January–December for every
country. DataMapper does not expose country-specific reporting calendars here.

The DataFrame's `attrs` contain:

- `IndicatorMetadata`: one row's complete normalized discovery metadata,
  including definition, unit/scale, edition, source timestamp and projection-year.
- `SourceURL`: actual HTTPS request URL, including requested countries/years;
  `Source` and `TermsURL` identify the IMF and applicable terms.
- `Filtering="ClientSide"`: country/year filters are enforced after retrieval.
- `Coverage`: per requested `Country`, `SourceSeriesPresent`, `ReturnedPeriods`
  and `MissingPeriods`. A source-null observation is a returned period with
  NaN; an omitted year is absent, not a fabricated zero or interpolated row.
- `ObservationStatus="Unknown"`: **no point is certified as actual, estimated
  or projected**. WEO mixes these. The source's `projection-year` is preserved
  without treating it as a country-specific actual/estimate cutoff.
- `Completeness="SourceProvidesNoObservationCounts"`: DataMapper has no total
  count/pagination/completeness marker to independently verify omissions.

An interval outside a supplied series' years returns a typed empty frame with
coverage metadata. A requested geography omitted entirely from the source
produces `RuntimeWarning` and explicit coverage information. For example,
Cuba (`CUB`) has no series in the tested unemployment response, while Iran
does. This warning makes mixed coverage visible; source unavailability and
truncation cannot independently be distinguished when the provider supplies
neither a series nor a completeness count. Metadata and observed records are
validated; fima cannot guarantee the publisher has supplied every observation.
Do not discard the coverage/status metadata when comparing countries.

## Examples

These examples require fima 0.16.0 or newer:

```python
from fima import get_imf_datasets, get_imf_indicators, get_imf_countries, get_imf_series

print(get_imf_datasets())
for term in ("GDP", "inflation", "unemployment", "debt", "current account", "reserves"):
    print(get_imf_indicators(search=term)[["Indicator", "IndicatorName", "Unit"]])

iran = get_imf_series("NGDP_RPCH", "IRN", 2010, 2027)
print(iran[["Period", "Value", "Unit"]])
print(iran.attrs["IndicatorMetadata"])
print(iran.attrs["Coverage"])

comparison = get_imf_series("NGDP_RPCH", ["IRN", "USA"], 2020, 2027)
wide = comparison.pivot(index="Period", columns="Country", values="Value")
wide.plot(title="IMF WEO GDP growth — includes estimates/projections")

print(get_imf_countries(include_aggregates=True))
```

Values and editions can change. Live tests compare every selected numerical
value and year directly with the exact JSON used in that call rather than
freezing future IMF values as permanent expectations.

## Errors and request behavior

Invalid IDs, duplicate selections, unsupported datasets or invalid year bounds
raise `ValueError`. HTTP/TLS/timeouts, malformed JSON, HTML responses, duplicate
JSON keys (including observations), nonnumeric/nonfinite values, nonannual
periods, incompatible scale/frequency metadata and changed metadata during
retrieval raise `RuntimeError`. Network exceptions remain chained causes.
Transport/parse failures return no partial DataFrame. All supplied observations
are validated before local filtering, including records outside the selection.

Requests use `(10, 30)` connect/read timeouts and normal TLS verification.
429/500/502/503/504 receive at most two retries. `Retry-After` seconds or HTTP
dates are respected; delays over 30 seconds fail with an instruction to retry
later, rather than sleeping less than requested. Other errors are not retried.
No authentication bypass, browser impersonation, proxy rotation or import-time
HTTP is used. Country-only series calls need three requests: indicator catalog,
country catalog, selected series. Aggregate/unknown IDs also require aggregate
discovery. No hidden persistent catalog cache masks source revisions.

## Attribution, rights and responsible use

The [IMF Copyright and Usage terms](https://www.imf.org/en/about/copyright-and-terms)
give statistical data special reuse conditions separate from general website
content. Preserve integrity, credit the IMF and database, disclose material
transformations, and communicate applicable terms to downstream users. For
**potential commercial reuse, request permission from `copyright@imf.org`**.
Automated bulk downloading requires explicit permission. Third-party data may
have separate rights; access to an API is not unlimited redistribution approval.

Suggested attribution: **Source: International Monetary Fund, World Economic
Outlook, [DataMapper WEO](https://www.imf.org/external/datamapper/datasets/WEO)**,
with the returned source edition and retrieval date. fima's local selection and
tidy reshaping preserve numeric units; identify further transformations in your
analysis. IMF data are supplied without warranty. The package's MIT license
covers its original code, not a replacement license for IMF data. fima has no
IMF affiliation or endorsement. This module includes no downloaded datasets;
deterministic fixtures use explicitly synthetic values.

## Verification

`python -m pytest test/test_imf.py -q` exercises synthetic source-shaped
contracts. Live checks are separate and opt-in:

```shell
python -m pytest -m integration test/test_imf_integration.py -v -s
```

They cover Iran/USA real GDP growth, Iranian average inflation, government
debt and fiscal balance, unemployment, forecast horizons, empty years, missing
geographic coverage, definitions and source revision metadata. Failures are
not converted into skips. Deterministic PR CI never relies on IMF availability.
