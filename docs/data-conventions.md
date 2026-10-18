# Public data conventions

Public DataFrames use English PascalCase columns. Python function and parameter
names use snake_case. These conventions describe parsed fima tables; explicitly
raw provider dicts and nested payloads retain source keys and values. The pure
adjust_historical_prices helper preserves the caller's raw columns/index; downloaded
tables use the canonical schemas.

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

See [migration notes](data-migration.md) for the 0.9.0 schema/type changes.
