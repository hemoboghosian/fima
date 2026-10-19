# Public data conventions

Public DataFrame columns, ordinary dict keys, Series labels and metadata keys
use English PascalCase. Python function and parameter names use snake_case.
The fund-detail and pagination key corrections are unreleased after 0.9.0; see
the [breaking migration](data-migration.md#unreleased-public-structured-keys).
Explicit provenance containers have the following precise exceptions:

- TSETMC fund `ProviderMetadata` preserves unknown/ambiguous source keys and
  payloads, including unverified `fundProfits`, in details and snapshot cells.
  Known `Stats` NAV records have normalized keys, not raw provider keys.
- TGJU `ProviderMetadata` preserves profile labels and `ProviderInstrument`
  preserves the catalog record for source inspection.
- Funds `ProviderAssets` uses unrecognized source asset labels as data keys;
  its record keys remain `Value` and `Weight`.

No other ordinary dict-returning API has a raw-provider default. The pure
adjust_historical_prices helper preserves caller-owned raw columns/index.
Values in opaque metadata are not assigned guessed financial meanings.

- Use `ClosingPrice` for the official/session closing price, `LastPrice` for the
  last trade, and `OpeningPrice`, `LowPrice`, `HighPrice` for session OHLC.
  TSETMC `YesterdayPrice` is its exchange reference, which can differ from the
  previous observed close. A snapshot `Price` is not assumed to be a last trade.
- `TransactionCount`, `TradeVolume`, and `TradeValue` are distinct. Volume may
  mean shares, contracts, or commodity quantity, according to the provider.
  `TradeNumber` is an individual trade sequence number. `IndexValue` is an
  index level, not monetary trade value.
- `InstrumentName`, `FundName`, and `ShareholderName` identify different things.
  Option tables use `Call`, `Put`, and `Underlying` prefixes rather than
  punctuation suffixes (for example `CallClosingPrice`).
- Gregorian date-only columns use pandas `datetime64[ns]` and `NaT`. Use
  `GregorianDate` when both calendars are relevant, and explicit calendar
  qualifiers for event dates. Do not turn timestamps into date-only values.
- Jalali date columns and date indexes contain ASCII `YYYY-MM-DD` strings;
  missing values are `pd.NA`. Use `JalaliDate`, or an event-qualified name.
  No custom Jalali dtype is required. Separate times use `HH:MM:SS` strings.
- Financial quantities are numeric, including formatted Persian/Arabic-digit
  values. Missing numbers use NaN/pd.NA; valid zero remains zero. Identifiers
  (instrument codes, registration numbers, etc.) are strings; leading zeros in
  source strings are preserved. Malformed nonmissing quantities raise errors.
- Public **DataFrame** percentages use percentage points: `2.5` means `2.5%`.
  This includes returns, asset weights, yields and option model rate/volatility
  columns. Do not infer a percentage scale from its observed magnitude.
- Analytical Python functions (`calculate_*`, `get_risk_free_rate`,
  `get_implied_volatility`, and the volatility in `black_scholes_merton`'s tuple)
  retain decimal rates/volatility: `.025` means `2.5%`. Their `r_f`/`sigma` inputs
  are decimal annual values, `t` is years. Greeks are derivatives per one whole
  decimal-unit change; theta is per year. DataFrame model outputs convert to
  percentage points only after calculation. Historical volatility uses the
  latest requested number of daily log returns and 252 trading sessions/year;
  expiry time uses calendar days/365. This is a modeling assumption, not an
  exchange-certified volatility or total-return model.
- Provider units are preserved: no implicit rial/toman/USD or physical-unit
  conversion. Currency/Unit metadata remains provider-specific. Missing fields
  are not automatically zero, and contradictory provider observations are not
  repaired by intuition. Raw provider metadata and heterogeneous display-value
  tables are documented exceptions to numeric conversion.

Fund details and nested `Stats` keep their existing JSON scalar values/types;
this focused key correction adds no date/dtype or calculation conversion there.
TGJU pagination attrs use `Page`, `HasMore` and `SourceURL`.

See [migration notes](data-migration.md) for unreleased keys and 0.9.0 schema/type changes.
