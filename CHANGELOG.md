# Changelog

## 0.19.1

- A standard `pip install fima` now installs Playwright. The
  `fima[codal-browser]` extra remains available for compatibility. For manual
  CAPTCHA completion, fima prefers installed Google Chrome and falls back to
  Playwright-managed Chromium. If neither browser is available, install Chrome
  or run `python -m playwright install chromium` in the same Python environment.
  See the [CODAL guide](docs/codal.md) for browser setup.
- Reuse validated CODAL report taxonomy for up to ten minutes from the fetch,
  including across fresh Python processes. This reduces unnecessary taxonomy
  requests when resolving Persian report names and keeps category IDs,
  letter-type IDs, and textual filing codes distinct.
- HTTP 429 errors explain CODAL's rate limit and show `Retry-After` when
  provided. Retrieval stops immediately, and a valid `Retry-After` blocks new
  CODAL requests in the same process until the deadline. Browser verification
  cannot bypass this rate limit. Availability depends on CODAL, and completing
  a real CAPTCHA followed by live retrieval remains unverified.

## 0.19.0

- Add `get_codal_data`, `search_codal_filings`, `fetch_codal_report`, and
  `list_codal_report_types` for discovering and downloading supported CODAL
  reports from Python. Use Persian report names such as «گزارش عملکرد ماهانه»,
  «گزارش فعالیت ماهانه», «صورت‌های مالی», «صورت سود و زیان»,
  «صورت وضعیت مالی», and «صورت جریان وجوه نقد». fima resolves CODAL category
  and letter-type IDs and finds report URLs automatically.
- Select filings by issuer and Jalali reporting period, with statement-sheet
  selection for financial reports. Search retains original and corrected
  filings and raises an error if pagination cannot complete. Automatic
  retrieval validates the issuer, period, statement, separate scope, and
  revision history before selecting a report. Supported normalized templates
  preserve exact values, original units and scales, and source provenance
  including SHA-256. See the [CODAL guide](docs/codal.md) for template coverage.
- Pass `interactive=True` to let a person complete a supported CAPTCHA on
  CODAL's own page in a visible browser. Install the optional
  `fima[codal-browser]` extra for Playwright and use installed Google Chrome or
  Playwright Chromium. CAPTCHA completion is manual. HTTP 429 stops retrieval,
  and a valid `Retry-After` blocks further CODAL requests in the same process
  until the deadline.
- Previous live tests verified automatic retrieval, including a successful
  call with `interactive=True` where CODAL did not present a CAPTCHA. Local
  Chrome tests verified the browser handoff and continuation. Completing a
  real CAPTCHA and then retrieving the report remains unverified end to end.
  CODAL availability can vary.

## 0.18.0

- Add offline `get_codal_report` and `get_codal_tables` to read filing metadata
  and extract tables from saved structured CODAL HTML with an embedded
  datasource. Sheet coverage distinguishes loaded sheets from sheets that
  still need their own saved files.
- Add `get_codal_monthly_activity` for the production-and-sales grid in
  one-month manufacturing Monthly Activity Product V3 and V4 filings. Add
  `get_codal_financial_statements` for balance sheets, income statements and
  cash flows from verified six- and twelve-month separate industrial filings.
  Both preserve reported values, units and scales.
- See [the CODAL guide](docs/codal.md) for supported templates and save
  instructions. The maintainer verified browser HTML Only and Complete HTML
  saves for filing 1106536, income statement sheet 1, with 92 normalized
  observations from each format. Automated CODAL access is unavailable in this
  release and remains tracked in [#177](https://github.com/hemoboghosian/fima/issues/177).

## 0.17.1

- Preserve financial schemas across pandas 2 and 3: object-typed option
  moneyness with `pd.NA`, numeric Tadbir allocation values/percentage points,
  and nanosecond IFB/IME dates and timestamps, including empty results. Keep
  financial classifications, values, identities and public APIs unchanged.
- Mitigate Soup Sieve descendant-selector backtracking on provider HTML while
  preserving Python 3.10, extraction scope, financial values and pagination.
  The compatible dependency remains advisory-affected; see docs/security.md.

## 0.17.0

- Add offline `calculate_contract_metrics` for Vertical option watches: quote
  status, absolute/relative bid-ask spread, intrinsic/time value, expiration
  breakeven, multiplier-aware contract premium and volume/open-interest ratio.
  Price bases and missing-value rules are explicit; negative time value is kept.
- Add offline `calculate_expiration_payoff` for Call/Put and Long/Short scenario
  prices, with a required contract multiplier. Separate full-position economic
  payoff, entry premium cash flow and gross profit before costs.
- Validate implied-volatility premiums against European no-dividend bounds and
  independently reprice solutions. Refine rounded/unverified candidates with
  finite numerical budgets, including valid high IV. Invalid/unverified results
  remain missing; eligible zero-volatility boundary premiums return zero IV.
- Preserve unknown watch/chain moneyness as `pd.NA` when underlying last price or
  strike is missing, nonfinite or nonpositive. Valid ITM/ATM/OTM classifications,
  schemas, existing signatures and financial units are retained.
- Document discovery workflows and the intentional corrections to invalid-data
  outcomes. No dividend model is added; existing rate-proxy and historical-
  volatility eligibility conventions remain. Quotes do not guarantee freshness
  or execution. Economic expiration payoff excludes actual settlement mechanics,
  fees, financing, margin, allocation and default.

## 0.16.1

- Complete public API usability guidance for all 85 existing functions. Improve
  82 interfaces through public docstrings and verified annotations, including
  finite Literal choices, corrected boolean hints and accurate optional returns.
  Preserve dynamic identifiers and permissive legacy argument behavior.
- Refresh the primarily Persian README and provider guides with discovery-led
  workflows, financial units, calendar/coverage/error guidance and model
  assumptions. Correct the string-date adjustment example and stale TGJU names.
- Add structural import/signature compatibility and deterministic documentation
  example checks. Public parameters/defaults, return schemas, calculations,
  financial meanings, providers, networking and dependencies remain unchanged.

## 0.16.0

- Add official IMF DataMapper v2 annual WEO dataset/indicator/geographic
  discovery and selected time series. Preserve native units, source identities,
  edition/revision/projection metadata, missing values and explicit coverage;
  document client-side filtering and unknown actual/estimate/projection status.
  Add deterministic contracts, separate live comparisons and IMF usage terms.
  Existing provider behavior and dependencies are unchanged.

## 0.15.0

- Add public KILID area discovery, native monthly toman/USD/18-karat-gold
  listing-price histories, per-metric listing-statistic snapshots and geographic
  comparisons. Validate source identity, period/denomination, units, complete
  published month bounds and comparison rows; preserve source-missing values,
  modeled/imputed classifications, separate reporting periods and contradictory
  metadata. Add deterministic source fixtures, opt-in live numerical comparisons
  and an access/methodology guide. Listing medians are not completed transaction
  prices; public access is not a redistribution license. Existing provider
  behavior and dependencies are unchanged. The maintainer chose to publish the
  public-data client while retaining the documented uncertainty about affirmative
  data-reuse licensing; this is not legal clearance or KILID endorsement.

## 0.14.2

- Make existing IME futures and export histories reject failed date windows,
  malformed responses, inconsistent totals, duplicate observations and invalid
  dates instead of returning partial history as success. Validate futures
  pagination; retain the export provider's working whole-window requests and
  reject truncated reports. Preserve public signatures, native financial fields,
  source-omitted futures metrics, export currency/quantity units and valid empty
  results. Failures now raise chained `RuntimeError`; invalid dates/window sizes
  raise `ValueError`. No new APIs; valid-call signatures, date defaults,
  successful values/dtypes and native financial units remain compatible.

The release also includes documentation-only CDC investigation PR #143;
no CDC runtime API was added. Deferred investigations #139/#62 remain open.
The inherited selective sdist documentation contract remains tracked in #133;
the clean sdist includes the eight explicitly declared guides.

## 0.14.1

- Make existing `get_all_ime_cd_trades` and `get_all_ime_salaf_trades` validate
  complete paginated histories and fail on missing/failed windows. Add optional
  exact `ticker` or `instrument_code` selection after full validation. Preserve
  source rials, instrument quantities, reported percentage zeros, positional
  arguments and date defaults; document nonunique row IDs and CDC limitations.

- Make `get_all_ime_option_trades` reject failed/inconsistent history pages
  instead of returning partial results. Validate totals, identities and trading
  calendars; retain typed empty results. Add keyword-only exact `contract_code`
  selection after full validation. Preserve existing positional arguments,
  financial mappings and date defaults. Document official source overlap,
  historical versus live data and unresolved CDC filters.

Failed HTTP/TLS/timeout requests, malformed responses and incomplete histories
now raise `RuntimeError` with the underlying cause instead of returning partial
data as success. Invalid selectors raise `ValueError`. Existing valid-call
positional arguments, date defaults, public imports and financial units remain
unchanged; the new selectors are optional and keyword-only.

The release includes the IME guide/source audit and the already merged IFB
SignalR validation/deferral documentation (#134), without IFB runtime changes.
CDC investigations #62/#139 and IFB investigations #125/#127/#129 remain open.
The sdist includes the eight guides explicitly listed in `MANIFEST.in`;
the inherited selective offline-documentation limitation remains in #133.

## 0.14.0

- Add `get_ifb_market_map` for full metric-selected IFB snapshot responses,
  with four verified measures, IFB identities/classifications, closing price,
  percentage change and source EPS/P/E. Preserve serialized monetary precision
  with Decimal; document metric-dependent coverage and absent quote timestamps.
  Validate entire responses before exact local filters; keep SignalR/derivative
  follow-up separate and preserve all existing APIs.
- Add `get_ifb_periodical_reports` for bounded IFB report discovery with source filters, string report
  IDs, separate reporting/upload dates and visible Excel/PDF links. Require two
  matching complete traversals; reject incomplete or changing catalogs.

- Add `get_ifb_yield_curve` for official fitted YTM comparison nodes for treasury, government and
  nongovernment, preserving source values, tenor days and relative labels.

- Add `get_ifb_bond_yield_history` for complete filtered historical YTM exports with verified instrument
  selection, explicit date bounds, effective annual percentage-point yields,
  typed empty responses and source conflict handling. Preserve existing bond
  snapshots and the decimal scalar risk-free estimate.

- Add `get_ifb_market_values`, `get_ifb_symbol_market_values` and
  `get_ifb_market_value_history` for verified snapshots and all three
  official historical CSV archives. Preserve exact integer rials, source
  universe/total differences, missing historical values and separate market
  regimes. Validate constituent counts, identities and export schemas; surface
  provider failures. Include a full Data Center audit and an IFB usage guide.

All seven APIs are additive. Existing signatures, provider behavior, dependency
requirements and the decimal scalar risk-free estimate are preserved. Coverage
is bounded to the verified source tables/exports; no missing observations,
calibration dates or whole-market completeness are invented. Fitted curves retain
relative comparison labels. Reports are metadata catalogs, not parsed financial
series. Market-map universes depend on the metric and supply no quote timestamp.
Nelson bond-observation semantics, report-content extraction and SignalR/
derivatives validation remain deferred in #125, #127 and #129 respectively.

## 0.13.2

- Retry transient TGJU GET disconnects and timeouts once using the existing
  two-attempt request budget. Preserve the failing request URL and timeout
  subtype, retry the same history page, and keep incomplete downloads as errors.
  Persistent TGJU/network failures remain errors; a successful live full-history
  download has not been verified from the restricted development environment.

## 0.13.1

Fix independently reproduced options compatibility and error-handling issues
found while investigating a user report. The original application's exact
outage was not reproduced; this release does not claim to resolve that outage.

- Use absolute README documentation links for PyPI and document verified options
  API/schema migrations, current columns, provider failures and the 0.13.1 fixes.
- Parse both compact and slash-separated TSETMC option expiry dates in
  `ticker_info()`, reject unknown option types and surface metadata HTTP errors.
  Restore its optional `j_date` selector on the current metadata output.
- Options market-watch and chain downloads now propagate request, HTTP, JSON,
  schema and analytical failures instead of printing an error and returning
  `None`. Valid empty provider lists return the public empty table schema,
  including requested analytical columns, without fetching unneeded inputs.

## 0.13.0

### Funds coverage and identity

- Substantially improve complete-history coverage for `get_daily_navs()` and
  `get_daily_asset_allocation()`, especially sector funds. In the fixed 516-row
  non-market-maker audit, correct NAV coverage increased from 320 to 389 and
  allocation coverage from 348 to 418; sector coverage increased from 36 to 59
  of 62 known-reachable funds for both histories.
- Correct 18 known wrong-child cases using verified registration, instrument
  identifiers, canonical parent selection and exact numbered legal compartments
  across Tadbir, Rayan and Mabna. Shared tickers do not substitute child histories.
- Preserve Tadbir's published date filters and basket identity across allocation
  pagination, and resolve verified fund-domain migrations without changing the
  raw catalog or weakening target identity and HTTPS checks.
- Check actual published reports instead of refusing entire fund categories;
  support verified legal-name variants and Nika's historical allocation contract
  with disjoint date windows, effective dates and source amounts/weights.

### Compatibility and provider limitations

- Public signatures and documented data contracts remain compatible. Provider
  conflicts, unavailable sources, incompatible periodic reports and incomplete
  history remain explicit failures; no failed page/window is silently omitted.
- Nika supplied no complete allocation history in the 13-fund live validation.
  The known Tadbir NAV and Kian allocation conflicts remain unresolved. Provider
  availability and valid HTTPS certificates are still required; not all funds
  are downloadable. See the [Funds guide](docs/funds.md) and
  [complete audit](https://github.com/hemoboghosian/fima/issues/82#issuecomment-6383302421).

## 0.12.0

### Added

- Extend `fima.CBI` with `get_cbi_inflation_rates()` for complete dynamically
  discovered monthly years and the published annual table, preserving period
  labels, percentage-point values and base-year notes without invented dates.
- Add separate `get_cbi_exchange_rates()` and `get_cbi_ets_rates()` APIs using
  official advanced-search XML exports, latest-day defaults and explicit bounded
  history. Preserve Iranian-rial quote values and foreign denominations; ETS
  combines cash/transfer modes with faithful `BuyRate`/`SellRate` columns.
- Add deterministic/live validation, exports and CBI documentation for units,
  historical rate regimes, source-provided repeated dates and access limitations.
  No calendar filling, rate conversion or daily crawling is performed.

## 0.11.0

### Added

- New public `fima.CBI` module and package-level `get_cbi_policy_rates()` for
  official CBI policy-rate history across every dynamically advertised year.
  Sequential ASP.NET postbacks refresh hidden state; validated semantic headers
  map interbank, repo cut-off, standing lending and standing deposit rates.
- Normalized Jalali/Gregorian dates and numeric percentage-point rates, exact
  deduplication and chronological ordering. Failed years or HTTP-200 CBI access
  rejections raise clear errors rather than returning partial data.
- Deterministic CBI tests, separate live validation, public-import verification
  and a [CBI guide](docs/cbi.md) documenting intermittent provider restrictions.

## 0.10.0

### Breaking public structured keys

- Normalize TSETMC fund-detail keys and nested `Stats` NAV records, sharing
  verified snapshot meanings (`FundName`, `RegistrationNumber`, NAVs, totals,
  returns and type codes). Snapshot `Stats` cells use the same nested keys.
- Preserve unknown/ambiguous fields only inside explicit `ProviderMetadata`,
  including `fundProfits` and unverified investor/unit-subtype fields. Do not
  invent semantics or return duplicate source-key aliases. Detail/history
  scalar values/types and ordering remain unchanged.
- Rename TGJU pagination attrs to `Page`/`HasMore`. Public call parameters and
  pagination behavior are unchanged. Existing explicit TGJU provenance and
  Funds unknown-asset metadata remain documented exceptions.
- See [the complete breaking-key migration](docs/data-migration.md#fima-0100-public-structured-keys).
  The 0.9.0 DataFrame naming, dtype, date, percentage and calculation conventions
  remain in effect.

## 0.9.0

### Breaking public data contracts

This minor release intentionally changes public DataFrame schemas, dtypes,
percentage scales and some calculations. Read the [exhaustive migration
guide](https://github.com/hemoboghosian/fima/blob/v0.9.0/docs/data-migration.md)
before upgrading. Public Python function and parameter names are unchanged.

- Standardize parsed DataFrame columns to PascalCase, Gregorian dates to pandas
  datetime, and Jalali dates to `YYYY-MM-DD` strings.
- Normalize numeric and identifier dtypes, preserving missing values, valid
  zeros and source leading zeros. DataFrame percentages use percentage points;
  analytical scalar rates and volatility retain decimal units.
- Correct TSETMC individual/institutional mappings and index high/low fields.
- Correct Options/IME transaction-count and trade-volume mappings using named
  source fields instead of JSON positions.
- Correct Funds NAV semantics: per-unit NAVs remain separate from total assets
  and explicitly named subscription/redemption valuation totals.
- Correct Mibian risk-free-rate scaling, trailing annualized volatility, and
  zero-volatility/expiry pricing limits.
- Preserve complete IME timestamps and interpret TGJU display-date labels
  without inventing a year or treating dates as clock times.

See [data conventions](docs/data-conventions.md) for units and exceptions.
Unverified fund-provider semantics [#59](https://github.com/hemoboghosian/fima/issues/59)
and IME CDC coverage [#62](https://github.com/hemoboghosian/fima/issues/62)
remain unresolved; no speculative provider corrections are included.

## 0.8.0

### TGJU

- افزودن پنج تابع عمومی برای کشف گروه‌ها و نمادها، آخرین داده‌های بازار،
  تاریخچهٔ روزانه و مشخصات نماد با نام فارسی، انگلیسی یا `Symbol`.
- دریافت داده از نقاط دسترسی عمومی TGJU بدون توکن، با صفحه‌بندی، مهلت محدود،
  بررسی گواهی و حفظ واحدها و داده‌های مفقود؛ بدون وابستگی یا تأیید رسمی TGJU.
- آزمون‌های قطعی مستقل از شبکه، آزمون زندهٔ جداگانه و راهنمای فارسی در
  `docs/tgju.md`.

## 0.7.0

### Added

- `get_tsetmc_funds(fund_type)` returns the public TSETMC fund-group snapshot
  as a DataFrame with original provider columns and row order.
- `get_tsetmc_fund_details(...)` returns the complete fund object, including
  nested histories. Both functions are exported from `fima` and `fima.Funds`.
- TSETMC group selection accepts Persian/English names. The offline
  `get_tsetmc_fund_types()` table makes available names discoverable.
- Fund details can be selected by full fund name, with optional named/numeric
  group restriction. Resolution uses official catalogs, rejects ambiguous or
  missing names and preserves numeric positional and `reg_no=` calls.
- Persian examples document TSETMC identifiers, raw fields, error handling
  and snapshot/history limitations. Existing Funds APIs remain unchanged.

### Provider limitations

- Fund-list and detail dates can disagree, and history order/coverage is not
  guaranteed. The provider returned HTTP 500 for selector 0 and a nonexistent
  registration during investigation; a valid empty list is preserved while
  transport, HTTP and malformed-response errors remain visible.
  Further source investigation is tracked separately in Issue #42.

### Compatibility

- Existing Fipiran/site-based Funds APIs remain unchanged. Numeric TSETMC group
  selectors, positional registration numbers and `reg_no=` remain supported.
- Name lookup checks exact normalized names and rejects ambiguity. Without a
  supplied group it checks all ten known individual catalogs and propagates
  any failed group; supplying `fund_type` narrows the lookup.
- Provider columns, dates, nested values and row order are preserved. No fuzzy
  selection, data imputation, Fipiran identity mapping or TLS bypass is added.

## 0.6.1

### Fixed

- TSETMC adjustment accepts an official zero opening field on traded rows,
  preserving raw/adjusted zero without imputing a price. Closing/reference
  ratio validation and checks for other price fields remain enforced.
- The README's TSETMC explanation is in Persian, with API identifiers and
  formulas preserved and the zero-opening behavior documented.

### Compatibility and provider limitations

- Existing imports, signatures, default raw output, adjustment factors and
  non-price fields remain compatible. Negative/missing/nonfinite opening
  prices and invalid closing/reference ratio inputs still raise `ValueError`.
- Official responses can disagree on opening fields and row coverage; a zero
  opening is preserved without fetching or guessing a replacement. Further
  source investigation is tracked in Issue #38, and economic/event validation
  remains in Issue #33. HTTPS verification stays enabled.

## 0.6.0

### Added

- Optional TSETMC reference-price-based backward adjustment via keyword-only
  `get_ticker_historical_data(..., adjust_prices=True)` and the pure
  `adjust_historical_prices` helper. Raw prices, row order, zero-trade records
  and non-price fields are preserved; adjusted prices keep floating precision
  and anchor at the latest supplied observation.
- Deterministic adjustment/validation tests and a separate live smoke test.
  Invalid references, duplicate dates and instrument mixing raise `ValueError`.
  Empty provider histories return a dataframe with the historical schema.

### Compatibility and provider limitations

- Adjustment is opt-in. Existing positional arguments, raw price/reference
  columns, Jalali index, row order and non-price fields remain compatible.
  The pure helper and download option are available from both `fima.TSETMC`
  and the top-level `fima` package.
- The endpoint is the latest supplied observation. Later reference changes
  can revise earlier adjusted levels; filter raw history before adjustment
  to choose an earlier anchor. The result is not a validated total-return
  series or a guarantee of exact rights/cash-subscription treatment.
- Official chart and pinned-library comparisons were verified for one
  instrument with aligned dates/endpoints. Event classifications and archive
  completeness remain uncertain; broader validation is tracked in Issue #33.
  Provider availability and valid HTTPS certificates remain necessary.

## 0.5.2

### Fixed

- Funds history downloads include market-maker funds with supported public data
  instead of rejecting their category. Rayan market-maker NAVs use the published
  aggregate history rather than an unrelated instrument basket.
- Multi-fund websites resolve the requested fund or compartment using published
  names and tickers instead of assuming basket or portfolio 1.
- Tadbir NAV parsing supports current leveraged-fund series and removes exact
  duplicate chart points while continuing to reject conflicting prices.
  Allocation histories retain additional holdings when the provider supplies them.
- Mabna downloads support current portfolio-specific NAV and allocation reports,
  named response fields, and complete pagination while retaining legacy support.
- Each public history download reuses its catalog lookup and HTTP session.

### Compatibility and provider limitations

- Existing public imports, function signatures, core columns, and provider-specific
  units remain compatible. Additional provider series and holdings appear only
  when supplied. Ambiguous identities and conflicting data raise useful errors.
- Provider availability and valid HTTPS certificates remain necessary. The known
  emacofund.ir certificate hostname mismatch is external; TLS verification remains
  enabled. No guarantee is made that every catalog fund exposes downloadable data.
- Aggregate Rayan market-maker allocation, conflicting Tadbir chart prices, and
  renamed fund identities require separate investigation in Issues #26, #27,
  and #28. Nika allocation and unverified Rahkar providers remain unsupported.

## 0.5.1

### Fixed

- Funds catalog filtering excludes market-maker instrument rows while retaining
  market-maker funds and other funds' legitimate compartments.
- `fima.Funds` wildcard imports and runtime discovery expose the three public
  functions through `__all__` and `__dir__`.
- Funds reload regression checks run in an isolated process so deterministic
  public-alias tests pass regardless of test order.

### Compatibility and provider limitations

- Explicit imports, top-level aliases, and public signatures remain compatible,
  including the existing `_set_website_developers` keyword. Private helpers
  remain accessible explicitly; static IDE completion can vary.
- During release preparation, emacofund.ir NAV requests failed certificate
  hostname verification independently of fima. This external provider/environment
  problem prevents access to that site's data; HTTPS verification remains enabled.

## 0.5.0

### Added

- Public Funds API: `get_all_funds`, `get_daily_navs`, and
  `get_daily_asset_allocation`, available from both `fima` and `fima.Funds`.
- Deterministic regression coverage for provider requests, malformed responses,
  chart alignment, history dates, and current and legacy Rayan allocation data.
  Live provider checks remain separate from deterministic CI.

### Fixed

- Fipiran catalog requests use the provider's POST contract, include market-maker
  funds, and normalize website addresses and optional metadata.
- Funds requests verify HTTPS certificates, follow redirects, and use finite
  timeouts. Selected transient GET errors have a bounded retry; transport and
  provider-response failures raise useful exceptions instead of empty results.
- Tadbir charts use named series and align values by reporting date. Duplicate
  chart dates and repeated allocation pages are rejected.
- Pikad NAV parsing selects named fields instead of depending on JSON key order.
- Mabna NAV requests include history through the current UTC time instead of a
  fixed historical cutoff.
- Rayan allocation parsing supports the current public endpoint and lower-camel
  field names while retaining support for the legacy endpoint and schema.
- Release smoke tests verify imports from the wheel installed in a clean
  environment, including the public Funds exports.

### Compatibility and provider limitations

- Public Funds signatures and output column names are preserved. Network and
  HTTP failures raise `requests.RequestException` subclasses; malformed or empty
  provider data raises `ValueError`. Unsupported providers can raise
  `NotImplementedError`.
- Live data depends on each provider's availability, certificates, and current
  API. Provider outages or site migrations can prevent requests from succeeding.
  HTTPS verification is not disabled to accommodate invalid certificates.
- Nika asset allocation remains unsupported. Current Mabna and Rahkar responses
  could not be validated against a working live site during release preparation;
  no speculative replacement endpoints or response schemas were introduced.

## 0.4.0

- Previous published version; the public Funds API was added afterward.
