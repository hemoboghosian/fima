# Public data conventions

Public DataFrame columns, ordinary dict keys, Series labels and metadata keys
use English PascalCase. Python function and parameter names use snake_case.
The fund-detail and pagination key corrections are published in 0.10.0; see
the [breaking migration](data-migration.md#fima-0100-public-structured-keys).
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
- IME `CreateDateTime` keeps nanosecond precision, fractional seconds and any
  supplied timezone. Naive source timestamps remain naive; missing or malformed
  timestamps remain `NaT`. These dtype contracts apply across pandas 2 and 3.
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

Options watch/chain moneyness `Status` fields retain object dtype with ITM/ATM/OTM
strings or `pd.NA`. Missing, nonfinite or nonpositive underlying last price or
strike is unknown; only equal finite positive prices are ATM. This is distinct
from a source instrument's trading-permission state and from quote quality.

Offline option contract metrics use the caller-selected quote/underlying basis
without substitution. `SpreadPercent` is percentage points; `SpotStrikeRatio`
and `VolumeOpenPositionsRatio` are dimensionless ratios. Intrinsic/time value
are per underlying unit, while `PremiumPerContract` applies the supplied
multiplier once. Negative time-value residuals are preserved. Expiration
scenarios separate signed payoff, entry premium cash flow and gross profit;
the latter three are total money amounts for all specified contracts, before
costs and financing. Economic exercise is assumed, without modeling settlement,
margin, default or automatic exercise. See [examples and missing-value rules](options.md#contract-comparison).

Fund details and nested `Stats` keep their existing JSON scalar values/types;
this focused key correction adds no date/dtype or calculation conversion there.
TGJU pagination attrs use `Page`, `HasMore` and `SourceURL`.

See [migration notes](data-migration.md) for the 0.10.0 structured keys and 0.9.0 schema/type changes.

KILID uses `JalaliMonth` (`YYYY-MM`) for monthly labels without fabricated daily
dates. Histories retain native toman/USD/grams-of-18K-gold per-square-meter units
and source rounding. Listing medians are distinct from completed transactions,
modeled prices and typical-dwelling estimates. Snapshot `Metric`/`Value` rows
retain their own reporting months and `DataBasis`; comparison missing values
are not derived conversions. `SourceParentArea` records the source breadcrumb;
`ListedUnderArea` is comparison display context, not verified parentage. Source
modification/coverage metadata stays separate from UTC `RetrievedAt` and actual
table months, with explicit metadata warnings. See the [KILID guide](kilid.md)
for the complete schemas, validation limits and unresolved data licensing.

IMF WEO (0.16.0) uses annual `Period` strings (`YYYY`) and `Frequency="A"`,
without fabricated day/month labels or calendar alignment. `Value` retains
native source units/scales and source nulls; omitted periods stay absent with
explicit `Coverage` attrs. Country/region/group identifiers remain distinct,
including non-ISO source IDs and null source names. Edition, revision timestamp
and source projection-year stay in `IndicatorMetadata`; `ObservationStatus`
remains `Unknown` because country-specific actual/estimate/projection boundaries
are unavailable. Client-side geographic/year filtering is explicit. See the
[IMF guide](imf.md) for schemas, completeness limits and statistical-data terms.

Damodaran snapshots use `Edition="YYYY-MM"`, the publisher's `SourceUpdateDate`,
and a UTC `RetrievedAt`. All `Percent` columns use percentage points. Beta
and `HiLoRisk` are dimensionless. The cost of capital basis is `Currency="USD"`.
`IndustryClassification` identifies a source edition and geography, and
`RowType` distinguishes industries from market aggregates. Country names
are source labels, and `CdsBenchmark` identifies the reference sovereign
for net CDS spreads. See the [Damodaran guide](damodaran.md) for schemas
and observation-date limitations.

## Ordering, missing results and model rates

There is no universal ordering/failure policy across older adapters. TSETMC raw
history and IFB legacy index history preserve source order; sort explicitly before
returns/rolling calculations. Legacy IFB index failures can return empty frames,
bond snapshots can print/return None, and TSETMC per-date shareholder/client failures
can omit dates. An empty/missing observation is not automatically an empty market
or a verified complete history. Provider guides and docstrings state each contract.

BSM uses continuous discounting; annual decimal scale alone does not establish
compounding equivalence. Options convenience functions pass the default IFB
treasury-yield proxy directly and estimate volatility from raw underlying closing
prices. No automatic conversion, dividend model or corporate-action adjustment is
implied. See [the model contract](options.md#analytics).

Options IV candidates are checked against the same European no-dividend price
bounds and independently repriced against the original premium. Lower-bound
premiums can return zero model volatility; exact upper-bound premiums require
infinite volatility and remain missing. Unverified/invalid estimates return
None (NaN in watch/chain tables), not a numerical search ceiling. See
[IV bounds, residual precision and numerical limits](options.md#iv-validation).
