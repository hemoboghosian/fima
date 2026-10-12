# Changelog

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
