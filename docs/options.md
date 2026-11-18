# Options data and migration

[User guide](../README.md) | [Migration](data-migration.md#tsetmc-and-options) | [Data conventions](data-conventions.md)

The public functions are exported from both `fima` and `fima.Options`.
The 0.9.0 output migration predates 0.13.0: `Options.py` is identical in the
0.9.0 through 0.13.0 release tags. Upgrading to 0.13.0 did not introduce another
options column migration.

## Current data APIs

| Function and parameters | Input and result |
| --- | --- |
| `download_market_watch(market='All', stack='Horizontal', j_date=True, bsm=False, greeks=False, implied_volatility=False)` | `market` is `All`, `TSE` or `IFB`. Horizontal rows pair Call/Put contracts; `Vertical` rows carry `OptionType`. |
| `download_chain_contracts(underlying_ticker, j_date=True, bsm=False, greeks=False, implied_volatility=False)` | Exact underlying ticker, not an option ticker or instrument code. Returns the paired chain sorted by expiry and strike. |
| `download_all_underlying_assets(_all_options_market_watch=None, market='All')` | Extracts distinct underlying rows from a current-format watch, downloading one if omitted. Returns `Ticker`, `InstrumentCode`, `ClosingPrice`, `LastPrice`, `YesterdayPrice`, `URL`. |
| `ticker_info(ticker, j_date=True)` | Exact option ticker. Returns one metadata row: `UnderlyingTicker`, `StrikePrice`, `MaturityJalaliDate` (or `MaturityGregorianDate` when `j_date=False`), `DaysToMaturity`, `OptionType`, `LastPrice`, `UnderlyingLastPrice`. The date selector was restored in 0.13.1. |
| `download_historical_data(ticker, start_date=None, end_date=None)` | Exact option ticker and optional inclusive Jalali bounds. Returns `(option_history, underlying_history)` in ascending date order; unavailable source history retains the legacy `(None, None)` result. |

History columns are `JalaliDate`, `TransactionCount`, `TradeVolume`, `TradeValue`,
`LowPrice`, `HighPrice`, `OpeningPrice`, `LastPrice`, `ClosingPrice`.
An empty date-filtered history differs from an unavailable source history.
HTTP failures in history downloads propagate.

The horizontal watch/chain has 45 columns. Each of `Call` and `Put` prefixes:
`Ticker`, `InstrumentName`, `InstrumentCode`, `Status`, `TransactionCount`,
`TradeVolume`, `TradeValue`, `NotionalValue`, `OpenPositions`, `ClosingPrice`,
`LastPrice`, `YesterdayPrice`, `BidPrice`, `BidVolume`, `AskPrice`, `AskVolume`, `URL`.
Shared columns are `ContractSize`, `StrikePrice`, `DaysToMaturity`,
`BeginJalaliDate`, `EndJalaliDate`, `UnderlyingTicker`, `UnderlyingInstrumentCode`,
`UnderlyingClosingPrice`, `UnderlyingLastPrice`, `UnderlyingYesterdayPrice`, `UnderlyingURL`.
With `j_date=False`, event dates are `BeginGregorianDate` and `EndGregorianDate`.
Vertical output has 29 columns: the unprefixed side fields, shared fields and
`OptionType` (`Call` or `Put`).

Prices and trade values retain provider rial units. `TransactionCount` counts
trades, `TradeVolume` is option contract volume, and `TradeValue` is monetary
value; do not interchange them or multiply a supplied value by contract size.
`ClosingPrice` and `LastPrice` are distinct. Instrument codes are strings;
Jalali dates are `YYYY-MM-DD` strings and Gregorian dates are pandas datetimes.

## Discover underlyings and contracts

```python
from fima import download_all_underlying_assets, download_chain_contracts, ticker_info

assets = download_all_underlying_assets(market="All")
print(assets[["Ticker", "InstrumentCode"]])
chosen = assets.loc[assets["Ticker"].eq("اهرم")]
if len(chosen) == 1:
    chain = download_chain_contracts(chosen.iloc[0]["Ticker"])
    print(chain[["CallTicker", "PutTicker", "StrikePrice", "EndJalaliDate"]])
    if not chain.empty:
        metadata = ticker_info(chain.iloc[0]["CallTicker"])
        print(metadata)
```

The first contract illustrates metadata lookup, not a liquidity/expiry selection.
Choose the intended strike, side and expiry before analysis. InstrumentCode is a
TSETMC code; an underlying ticker and an option ticker are different arguments.
`market` supports All/TSE/IFB and `stack` Horizontal/Vertical; misspellings retain
legacy All/Horizontal fallback. They remain `str` annotations rather than a
falsely closed runtime contract. Calendar and analytics flags are booleans.

## Minimal example

This call and these columns were checked against live data on 2026-10-27,
including a 35-row Ahrom chain. Counts and quotes can change.

```python
from fima import download_chain_contracts

chain = download_chain_contracts(underlying_ticker="اهرم", bsm=False)
if chain.empty:
    raise RuntimeError("No contracts matched this underlying.")
print(chain[["CallTicker", "PutTicker", "StrikePrice", "EndJalaliDate",
             "CallLastPrice", "PutLastPrice", "CallTradeVolume"]].head())
```

Select option tickers from the returned chain for `ticker_info()` and history
calls. The provider can include expired contracts or zero-trade rows; a row
is not proof of an active or recently traded contract. If an application needs
unexpired contracts, compare `EndJalaliDate` with today's Jalali date explicitly.
Do not assume that a historical example ticker is still active.

## Contract comparison

`calculate_contract_metrics(watch, *, price='Ask', underlying_price='Last')`
works on an existing **Vertical** watch; it never downloads data. Inspect the
available underlyings and contracts, then select an exact `InstrumentCode` from
the displayed table. The example reads that choice rather than picking the first
contract as a recommendation:

```python
from fima import (download_market_watch, download_all_underlying_assets,
                  calculate_contract_metrics)

watch = download_market_watch(stack="Vertical")
print(download_all_underlying_assets(watch)[["Ticker", "InstrumentCode"]])
underlying = input("Underlying ticker from the table: ").strip()
contracts = watch.loc[watch["UnderlyingTicker"].eq(underlying)]
print(contracts[["Ticker", "InstrumentCode", "OptionType", "EndJalaliDate",
                 "StrikePrice", "ContractSize", "BidPrice", "AskPrice"]])
code = input("Exact option InstrumentCode from the table: ").strip()
selected = contracts.loc[contracts["InstrumentCode"].eq(code)]
if len(selected) != 1:
    raise ValueError("Select exactly one displayed contract.")
comparison = calculate_contract_metrics(selected, price="Ask", underlying_price="Last")
print(comparison[["Ticker", "QuoteStatus", "SpreadPercent", "IntrinsicValue",
                  "TimeValue", "BreakevenPrice", "PremiumPerContract"]])
```

Check the expiration and intended side/strike before choosing a contract. The
helper does not filter expirations. Existing `Status` is retained unchanged: it
uses underlying last price, even if you select a closing-price basis here.

`price` choices are `Ask`, `Bid`, `Mid`, `Last`, `Closing`; `underlying_price`
choices are `Last`, `Closing`. Ask is an indicative buy/cover price; Bid is an
indicative sell price. A midpoint is a valuation reference, not an executable
quote. Last/closing prices can be stale or asynchronous with the underlying.
No other price is substituted when the selected basis is missing.

The result copies all input columns, index, row order and attrs and adds these
columns. Numeric additions have dtype `float64` and use NaN; `QuoteStatus` has
pandas string dtype. `S` is the chosen underlying price, `K` the strike and `P`
the chosen premium. Prices retain rials per underlying share or fund unit.

| Added column | Formula / interpretation |
| --- | --- |
| `QuoteStatus` | `TwoSided`, `Locked`, `Crossed`, `BidOnly`, `AskOnly`, `NoQuote`, `Incomplete` |
| `MidPrice` | `(ask + bid) / 2`, only for usable ordered two-sided books |
| `Spread` | `ask - bid`, rials per underlying unit |
| `SpreadPercent` | `100 * Spread / MidPrice`, percentage points; 20 means 20% |
| `ReferencePrice`, `UnderlyingReferencePrice` | Explicitly selected premium and spot, rials per underlying unit |
| `SpotStrikeRatio` | `S / K`, dimensionless; higher values favor call rather than put intrinsic value |
| `IntrinsicValue` | Call: `max(S-K, 0)`; put: `max(K-S, 0)`, rials per unit |
| `TimeValue` | `P - IntrinsicValue`, signed rials per unit; negative residuals are retained |
| `BreakevenPrice` | Call: `K+P`; put: `K-P`, underlying price at economic expiration breakeven before costs |
| `PremiumPerContract` | `P * ContractSize`, **rials per contract**; supplied trade value is not multiplied again |
| `VolumeOpenPositionsRatio` | `TradeVolume / OpenPositions`, dimensionless, not a percentage |

A quote side requires positive price **and** quantity. A locked book has valid
zero spread; crossed books have missing spread/midpoint and Ask/Bid/Mid reference
metrics. A known one-sided quote remains usable. Missing, negative or nonfinite
book fields make `QuoteStatus="Incomplete"`; a known opposite side can still be
used. Explicit zeros are empty sides, not missing observations. Price with zero
quantity is not usable. No quote status certifies liquidity, freshness, trading
permission or a fill.

Missing, negative and nonfinite numeric observations invalidate only dependent
metrics. Zero snapshot prices, strike or size are unavailable. Zero trading
volume remains valid; zero OI gives a missing ratio, including 0/0. A negative
put breakeven is missing because it cannot occur at a nonnegative spot price;
zero breakeven is valid. Premium exposure/breakeven do not require spot, and
intrinsic value does not require a premium. Contract size is taken from each
row: it must not default to 1,000. No dividend, rate or pricing model is used.
Negative time value alone is not an arbitrage signal.

Required fields are `OptionType`, `StrikePrice`, `ContractSize`, `BidPrice`,
`BidVolume`, `AskPrice`, `AskVolume`, `TradeVolume`, `OpenPositions`, the selected
`UnderlyingLastPrice`/`UnderlyingClosingPrice`, and `LastPrice`/`ClosingPrice`
when selected. Missing cells are allowed; missing columns, duplicate columns,
unknown/missing option types, malformed required numeric cells and invalid selectors
raise `ValueError`. Do not pass a horizontal chain or an already-enriched result;
reuse the original Vertical watch to change the basis. Empty valid-schema input
returns the same empty result schema. Source columns and their dtypes are retained.

## Expiration scenarios

`calculate_expiration_payoff(underlying_prices, strike_price, premium, option_type,
*, contract_size, contracts=1, position='Long')` is entirely offline. Select
`StrikePrice`, `OptionType` and `ContractSize` from the exact contract above;
`ticker_info` alone does not return the multiplier. Supply your actual entry
premium when known. Use one currency throughout; fima watch prices are rials,
not tomans. Do not pass a full-contract premium as the per-unit `premium`.

This independent example is **synthetic**, not a market quote or forecast:

```python
from fima import calculate_expiration_payoff

scenarios = calculate_expiration_payoff(
    [800, 1000, 1200], strike_price=1000, premium=80, option_type="Call",
    contract_size=1254, contracts=2, position="Long",
)
print(scenarios)
```

For `a=1` (Long) or `a=-1` (Short), `Q=contracts*contract_size` and intrinsic
`I=max(S_T-K,0)` for Call or `max(K-S_T,0)` for Put, the five `float64` columns are:

| Column | Meaning and unit |
| --- | --- |
| `UnderlyingPrice` | Supplied scenario price, rials per underlying unit |
| `IntrinsicValue` | `I`, rials per underlying unit |
| `ExpirationPayoff` | `a * Q * I`, signed total rials, excluding entry premium |
| `PremiumCashFlow` | `-a * Q * premium`, signed total entry rials |
| `GrossProfit` | Payoff plus entry cash flow, total rials before costs/financing |

The example's gross profits are `[-200640, -200640, 300960]` rials. Long buys the
option and Short writes it; buying back a short is a closing transaction, not a
new Long scenario. Calls break even at `K+premium`, puts at `K-premium` if that
price is nonnegative. The calculation does not discount or annualize cash flows.

The economic payoff assumes exercise when beneficial using fixed supplied terms.
It does not model automatic exercise or missing a manual request deadline,
physical delivery or strike funding, allocation, fees, tax, financing, margin,
default, future term adjustments or closing a position before expiry. It is not
a guarantee of actual cash settlement. Exchange/contract-specific settlement
rules still apply; see the official contract notice before exercising.

Option type is exactly `Call`/`Put`, position `Long`/`Short`. Scenario prices and
premium must be finite nonnegative real numbers; strike is positive. Counts and
multiplier are positive integers (including NumPy integers), not booleans or
floating-point counts. Invalid inputs or overflowing monetary results raise
`ValueError`. Zero premium/spot is allowed here as a supplied scenario, unlike
an unavailable zero snapshot price. Scenario order/duplicates are preserved
without mutating input; output uses a new RangeIndex. Empty scenarios return
the five documented empty float columns. Neither helper makes an HTTP request.

To use the selected contract from the comparison example, keep its exact terms
and enter your actual per-unit entry premium. These three spots are scenarios
around the strike, not price predictions:

```python
from fima import calculate_expiration_payoff

row = selected.iloc[0]  # The exact contract selected above.
entry_premium = float(input("Actual entry premium per unit, in rials: "))
position_payoff = calculate_expiration_payoff(
    [row["StrikePrice"] * .9, row["StrikePrice"], row["StrikePrice"] * 1.1],
    strike_price=row["StrikePrice"], premium=entry_premium,
    option_type=row["OptionType"], contract_size=row["ContractSize"], position="Long",
)
print(position_payoff)
```

## Analytics

`get_greeks`, `get_implied_volatility` and `black_scholes_merton` each accept
`ticker`, `_ticker_info_df=None`, `volatility_window_size=None`, `r_f=None`,
`minimum_required_history=30`, `_ua_historical_data=None`. Injected data avoids
the corresponding provider downloads. They return a Greek Series, decimal
implied volatility, and `(decimal_volatility, price)` respectively. Insufficient
history or near-expiry contracts can return missing analytical values with a
diagnostic; a successful watch download does not guarantee a model estimate.

Watch/chain flags add side-specific `Volatility`/`BSMPrice`,
`Delta`/`Gamma`/`Theta`/`Vega`/`Rho`, or `ImpliedVolatility`, and shared
`RiskFreeRate`. DataFrame rate/volatility fields use percentage points; scalar
analytical functions and injected `r_f` use decimal annual values.
The independent `calculate_black_scholes_merton`, `calculate_delta`,
`calculate_gamma`, `calculate_theta`, `calculate_vega` and `calculate_rho`
functions perform no provider download; `t` is years, `r_f`/`sigma` are decimals.
See [conventions](data-conventions.md) for annualization and Greek units.

### Model input and missing-result contract

| Argument | Meaning |
| --- | --- |
| `s`, `k` | Spot and strike in the same price unit; positive and finite for scalar pricing |
| `t` | Years; convenience APIs use calendar days/365 |
| `r_f` | Annual decimal model rate; BSM uses continuous discounting `exp(-r_f*t)` |
| `sigma` | Annual decimal volatility; .20 = 20% |
| `option_type` | Exact Call/Put; scalar pricing rejects other strings, legacy side-dependent Greeks return None |
| `volatility_window_size=None` | `min(30, max(5, min(history_rows, days_to_maturity)//2))`; explicit window is capped at that safe history/maturity limit |
| `minimum_required_history=30` | Underlying row-count eligibility, including the IV convenience function |
| `_ticker_info_df`, `_ua_historical_data` | Optional legacy data injection; current metadata/history schemas avoid the corresponding downloads |

Convenience analytics use **raw official ClosingPrice** daily log returns with
sample standard deviation and sqrt(252). Corporate-action jumps are not removed.
No dividend yield is modeled. `r_f=None` passes the IFB treasury-yield proxy
directly, without compounding conversion; its equivalence to a continuous model
rate is not certified. Supply an explicitly chosen model rate when that matters.
This documentation does not change the default calculation.

`black_scholes_merton` returns `(decimal_volatility, price)`, not the reverse.
`get_implied_volatility` returns a decimal or None; `get_greeks` returns a labeled
Series, possibly all missing. Unavailable/insufficient history, less than ten
remaining days, a window below five or zero-volatility checks produce diagnostics
and missing outcomes; other request/schema errors may propagate. IV retains
history eligibility checks even though it solves from a premium.

Pure pricing validates its domain and handles expiry/zero-volatility limits.
Pure Greeks retain existing numerical behavior without full domain validation:
expiry/zero volatility can warn, raise or yield nonfinite values. Theta is annual;
Vega/Rho are per whole decimal unit. Divide by 100 only when deliberately reporting
a sensitivity per one percentage point. Use keyword arguments: pricing orders
`sigma, r_f`, while Greek functions order `r_f, sigma`.

## Provider and failure diagnosis

The official [TSETMC frontend](https://tsetmc.ir/) uses
`https://cdn.tsetmc.com/api/Instrument/GetInstrumentOptionMarketWatch/{market}`,
with market codes `0` (All), `1` (TSE), `2` (IFB). Chains filter the All response.
Ticker lookup uses `Instrument/GetInstrumentSearch/{ticker}`; metadata uses
`Instrument/GetInstrumentInfo/{code}` and `ClosingPrice/GetClosingPriceInfo/{code}`;
history uses `ClosingPrice/GetClosingPriceDailyList/{code}/0` under the same API.
Requests use finite timeouts and normal TLS verification. No fallback endpoint
or access-control bypass is used.

On 2026-10-27 the three watch endpoints returned HTTP 200 JSON with 825, 645,
180 paired rows respectively. Published 0.3.1/0.8.0 watch and chain implementations
also returned data. That does not establish why an individual application
stopped receiving data earlier, or guarantee provider freshness/availability.
Record the exact call, installed version, printed error/exception and filtering
code before attributing an empty application screen to an API change.

### Fixes published in 0.13.1

These fixes are published in **0.13.1** and are not included in 0.13.0:

- [#109](https://github.com/hemoboghosian/fima/pull/109): watch/chain request,
  HTTP, JSON, schema and analytical failures propagate instead of being printed
  and replaced by `None`. A valid empty provider list returns an empty table
  with the public schema, including requested analytics, without unnecessary
  history/rate requests. A failure is therefore distinct from a valid empty result.
- [#110](https://github.com/hemoboghosian/fima/pull/110): `ticker_info` parses
  both `14050817` and `1405/08/17` expiry formats, checks metadata/price HTTP status
  and rejects unknown option types. Active IFB Atlas Call/Put metadata crashed
  before this fix. `ticker_info(ticker, j_date=True)` also restores the old date
  selector on the current metadata contract; `False` returns `MaturityGregorianDate`.

Older full watch-row users should follow the
[legacy API migration](data-migration.md#legacy-options-api). No duplicate legacy
columns are returned: some old labels confused transaction counts and volume.
