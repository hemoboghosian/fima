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

## Minimal example

This call and these columns were checked against live data on 2026-10-27,
including a 35-row Ahrom chain. Counts and quotes can change.

```python
from fima import download_chain_contracts

chain = download_chain_contracts(underlying_ticker="اهرم", bsm=False)
if chain is None:  # Released 0.13.0 can hide a download error this way.
    raise RuntimeError("Download failed; inspect the provider error printed above.")
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
