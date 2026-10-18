# Unreleased public-data migration

These changes are **breaking output contracts**, pending release review. No
function or public parameter has been renamed. Do not retain old and new columns
in the same frame. Unlisted fields retain their meanings/units.

## TSETMC and Options

| Old public name | New public name | Scope |
| --- | --- | --- |
| ClosePrice | ClosingPrice | Price tables and adjustment input |
| FirstPrice | OpeningPrice | Daily prices and adjustment input |
| MinPrice / MaxPrice | LowPrice / HighPrice | Daily prices and adjustment input |
| AdjustedClosePrice / AdjustedFirstPrice / AdjustedMinPrice / AdjustedMaxPrice | AdjustedClosingPrice / AdjustedOpeningPrice / AdjustedLowPrice / AdjustedHighPrice | Adjusted history |
| NotAdjustedClosePrice | UnadjustedClosingPrice | TSETMC price adjustments |
| TransactionNo / TransactionsNo | TransactionCount | TSETMC daily/company tables and adjustment input |
| Volume / Value | TradeVolume / TradeValue | TSETMC trade/company tables |
| TransitionsNo | TradeNumber | TSETMC intraday sequence, **not a count** |
| SharesNo | NumberOfShares | Shareholder and market-cap tables |
| Name | InstrumentName or ShareholderName | TSETMC instrument or shareholder tables |
| JDate / GDate | JalaliDate / GregorianDate | Columns, indexes, adjustment input |
| Value / MinValue / MaxValue | IndexValue / LowIndexValue / HighIndexValue | TSETMC index tables |
| HourMinute | Time | TSETMC index snapshot |
| Date / Quantity / Volume / Value | JalaliDate / TransactionCount / TradeVolume / TradeValue | Option/underlying daily history |
| Volume-C, Volume-P | CallTransactionCount, PutTransactionCount | Option watch/chain; old volume was actually count |
| Quantity-C, Quantity-P | CallTradeVolume, PutTradeVolume | Option watch/chain; old quantity was contract volume |
| *-C / *-P / *-UA | Call* / Put* / Underlying* | All option watch/chain columns, applying base renames above |
| Name / Type | InstrumentName / OptionType | Vertical option watch |
| UATicker / LastPrice-UA / Type | UnderlyingTicker / UnderlyingLastPrice / OptionType | ticker_info |
| BeginDate / EndDate | BeginJalaliDate / EndJalaliDate, or BeginGregorianDate / EndGregorianDate | Option watch/chain, selected by existing j_date |
| MaturityDate | MaturityJalaliDate | Option ticker_info |

The suffix rule also covers Ticker, InstrumentCode, Status, TradeValue,
NotionalValue, OpenPositions, ClosingPrice, LastPrice, YesterdayPrice, BidPrice,
BidVolume, AskPrice, AskVolume, URL, and optional BSMPrice/Volatility/Greeks/
ImpliedVolatility columns. The underlying-extraction function strips the new
Underlying prefix and returns the same canonical base names.

Jalali date columns/indexes now contain canonical strings instead of jdatetime
objects. Option Gregorian event dates are datetime64[ns] instead of Python date
objects. Time is HH:MM:SS text instead of datetime.time/packed integers.
InstrumentCode columns are pandas string dtype, preserving source leading zeros.
Prices, quantities, share counts, index levels and client fields parse formatted
numbers; integer/float inference is retained rather than forcing every quantity
to nullable integers. Empty known daily-history schemas have numeric columns.
Option ticker_info's initially object-typed financial fields become numeric.
DataFrame RiskFreeRate, Volatility and ImpliedVolatility change from decimal
fractions to percentage points; scalar analytical API units stay decimal.

Behavioral corrections: official client `I` fields map to Retail and `N` to
Institutional; index high/low source mappings are corrected; options map keys
rather than JSON object positions; Mibian receives r_f*100; historical volatility
uses the trailing window in date order with sqrt(252) annualization. Zero
volatility pricing uses discounted intrinsic value, and expiry pricing avoids
undefined divisions. Option history supports either inclusive date bound and
returns ascending dates. Provider zero opening prices remain zero; index and
market-cap calculations are not redefined.

Evidence: official TSETMC [frontend](https://tsetmc.ir/), option/closing/client API
responses inspected during the audit, and [Mibian source](https://github.com/yassinemaaroufi/MibianLib/blob/master/mibian/__init__.py).
