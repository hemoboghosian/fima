# Changelog

## Unreleased

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
- See [the complete breaking-key migration](docs/data-migration.md#unreleased-public-structured-keys).
  No version/tag/release is created by this correction.

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
