# IME historical market data

Use explicit short Jalali intervals. Existing broad defaults are retained for
compatibility and do not prove history since inception. The [source audit](ime-audit.md)
explains API overlap and unresolved continuous-certificate filters.

## Futures and export report histories

```python
get_all_ime_futures_trades(
    only_active=False, start_date=None, end_date=None,
    _chunk_size=100, _offset=0, _timeout=(10, 45),
)
get_all_ime_export_trades(
    start_date=None, end_date=None, _chunk_size=100,
    _offset=40, _timeout=(10, 45),
)
```

Both existing APIs remain available from `fima` and `fima.IME`, with unchanged
positional arguments and financial mappings. Use inclusive Jalali intervals
(`YYYY-MM-DD` or `YYYY/MM/DD`). Missing/earlier start dates clamp to the legacy
floors 1387-01-01 (futures) and 1387-12-01 (export); end defaults to today.
These floors do not establish verified inception or exhaustive archive coverage.
Reversed ranges retain `None`, and valid empty reports retain empty DataFrames.
`_chunk_size` is a nonnegative integer, with zero requesting one day per window;
`_offset` remains unused for compatibility. No current-day finality is implied.

Futures use the [official futures report](https://www.ime.co.ir/fut-report.html).
`only_active` selects currently active contracts, including for historical
requests; it does not reconstruct a point-in-time active universe. Pages must
satisfy the source `total`; duplicate `ContractCode`/`JalaliDate` observations,
changed totals and missing/repeated pages raise. A 10,000-page safety bound
raises rather than truncates. The source has no Gregorian trading-date field
in this report; none is invented.

`TradeVolume` and `OpenInterest` retain source contract counts; `TradeValue`,
`OpeningPrice`, `LastPrice`, `HighPrice`, `LowPrice`, `LastSettlementPrice` and
`TodaySettlementPrice` retain native rials and distinct financial meanings.
Instrument quotation conventions and multipliers are not inferred or converted.
`SettlementPricePercent` and weekly/monthly percentage fields remain reported
values. `OpenInterestChange` retains the raw source value without resolving the
page's ambiguous percentage label. Customer counts and retail/institutional
volumes/values remain separate. The provider legitimately omits some trade,
price and activity metrics: omissions remain absent/NaN, not fabricated zeros.
`ContractCode` is a string; `JalaliDate` and `DeliveryJalaliDate` are canonical
Jalali strings. Delivery date is not the record's trading date.

Exports use the [official export report](https://www.ime.co.ir/export-stat.html).
The established whole-window request is retained because small second-page
requests returned HTTP 500 during the bounded audit. Every window must contain
exactly its reported total; a truncated response raises with advice to request
a smaller interval. There is no speculative pagination fallback or automatic
retry. Export `ID` is a string observation identity, while `Symbol` and
`ProducerName` identify the reported product/producer. Duplicates across windows
are rejected. `JalaliDate` and `DeliveryJalaliDate` remain distinct.

Export `ClosingPrice`/`LowPrice`/`HighPrice`, `SupplyVolume`, `TradeVolume`,
`TradeValue`, `SupplyBasePrice`, `Demand`, `Currency`, `Unit` and `FXRate` retain
their existing source mappings. There is no universal rial, toman, kilogram or
tonne conversion. The quantity `Unit` alone does not establish price quotation
units; do not assume `TradeValue == ClosingPrice * TradeVolume`. Missing FX
rates remain missing. Existing producer wrappers inherit fail-closed download
behavior without changed signatures.

```python
from fima import get_all_ime_futures_trades, get_all_ime_export_trades

futures = get_all_ime_futures_trades(start_date='1404-01-01', end_date='1404-02-01')
exports = get_all_ime_export_trades(start_date='1405-08-16', end_date='1405-08-17')
```

Invalid dates/window sizes raise `ValueError`. HTTP/TLS/timeouts, invalid JSON,
malformed envelopes/required fields, invalid identities/dates/numbers and
incomplete reports raise chained `RuntimeError`, without printing and returning
partial data. Dates and financial parsing are validated before returning.
Completeness is relative to provider totals, not proof of missing trading days,
immutable snapshots or provider-record accuracy. Opt-in comparisons validate
real futures pages and export date windows against complete official responses;
deterministic CI uses synthetic source-shaped records.

## Option contract history

```python
get_all_ime_option_trades(
    option_type='All', only_active=False, start_date=None, end_date=None,
    _chunk_size=100, _offset=0, _timeout=(10, 45), *, contract_code=None,
)
```

Available from `fima` and `fima.IME`. Downloads official daily statistics from
[IME's options statistics page](https://www.ime.co.ir/optionboard.html).
Existing positional arguments and financial mappings are retained.

| Parameter | Meaning |
| --- | --- |
| `option_type` | Exactly `'All'`, `'Call'` or `'Put'`; source-side selection |
| `only_active` | Boolean; source's **currently** active contracts, even for past dates; not a historical point-in-time active universe |
| `start_date`, `end_date` | Inclusive Jalali `YYYY-MM-DD` or `YYYY/MM/DD`; start defaults/clamps to `1395-01-01`, end defaults to yesterday in the local system date |
| `_chunk_size` | Nonnegative integer; window spans this many days plus its inclusive first day; zero requests one day per window |
| `_offset` | Legacy unused argument, retained; pagination always starts at zero |
| `_timeout` | Requests connect/read timeouts, default `(10, 45)` seconds |
| `contract_code` | Optional nonempty exact, case-sensitive `ContractCode`; applied locally **after** all windows pass validation; unknown code returns typed empty schema |

Legacy behavior remains: reversed ranges return `None`; with `only_active=True`
and start today, start becomes yesterday. Explicit end dates are not clamped.
These rules do not establish finalized current-day statistics.

```python
from fima import get_all_ime_option_trades

# Includes active contracts reporting zero trades.
history = get_all_ime_option_trades(
    only_active=True, start_date='1405-08-16', end_date='1405-08-17',
)
contracts = history[['ContractID', 'ContractCode', 'ContractDescription']].drop_duplicates()

# Code observed in the official report; later active status may differ.
gold_option = get_all_ime_option_trades(
    start_date='1405-08-16', end_date='1405-08-17', contract_code='GBAB05C1800',
)
print(gold_option[['JalaliDate', 'LastPrice', 'TradeVolume', 'TradeValue', 'OpenInterest']])
```

Complete returned schema, in source order:

| Columns | Type / meaning |
| --- | --- |
| `ID` | String observation ID; duplicates rejected |
| `ContractID`, `ContractCode` | String official contract identifiers |
| `ContractDescription` | Source description; strike, underlying and multiplier are not inferred |
| `IsActive` | Nullable boolean; active requests reject false/missing flags |
| `TradeVolume`, `TradeValue` | Numeric source contract count and transaction value in rials |
| `HighPrice`, `LowPrice`, `LastPrice`, `OpeningPrice` | Numeric source-quoted rials; opening is first trade, not previous close; no multiplier conversion |
| `OpenInterest` | Numeric reported open contracts |
| `OpenInterestChange` | Raw `ChangeOpenInterest`; page label conflicts with values, so no percentage/count reinterpretation |
| `ActiveCustomers`, `ActiveBrokers`, `CBuy`, `CSell` | Numeric source customer/broker/buyer/seller counts, not quantities |
| `InstitutionalBuyVolume`, `InstitutionalBuyValue`, `InstitutionalSellVolume`, `InstitutionalSellValue` | Institutional contract counts and rial values |
| `RetailBuyVolume`, `RetailBuyValue`, `RetailSellVolume`, `RetailSellValue` | Individual contract counts and rial values |
| `LastSettlementPrice`, `TodaySettlementPrice` | Numeric previous/today settlement in source rials; distinct from last trade and equity closing price |
| `SettlementPricePercent` | Numeric source percentage-point settlement change, unchanged |
| `JalaliDate`, `GregorianDate` | Trading date as ASCII Jalali `YYYY-MM-DD` and normalized `datetime64[ns]`; calendars must agree |
| `DeliveryJalaliDate` | Source `DeliveryDate`, labelled exercise date on this page |
| `CreateDateTime` | Record-creation timestamp with fractional seconds; timezone unspecified; not a live quote timestamp |

Rows sort by trading date ascending; within-date order is unspecified. Valid
empty responses retain schema. Source precision and zero are retained; no toman
conversion, normalized premiums, IV, Greeks, bid/ask or synthetic observations
are added. Cross-underlying premium comparisons require official contract
specifications for quotation units and multipliers.

`ValueError` reports invalid inputs. `RuntimeError` reports HTTP/TLS/timeouts,
invalid JSON/envelopes, missing fields, changing totals, missing/repeated pages,
duplicate identities, conflicting/out-of-range dates or malformed data, with
chained underlying exceptions. Each window requests pages of at most 1,000
records until its reported total is satisfied; short pages do not imply
completion. A 10,000-page bound raises instead of truncating. No automatic retry
loop is added. Requests uses short-lived sessions and TLS verification.
Financial parsing precedes local selection, which cannot hide failed pages.

Completeness is against reported counts, not proof of every historic trading
day or an immutable source snapshot. Missing dates are not filled. Integration
comparisons must be explicitly selected; routine CI uses mocked source records.

## Certificate and standard parallel salaf histories

```python
get_all_ime_cd_trades(
    start_date=None, end_date=None, _chunk_size=100, _offset=30,
    _timeout=(10, 45), *, ticker=None, instrument_code=None,
)
get_all_ime_salaf_trades(
    start_date=None, end_date=None, _chunk_size=100, _offset=30,
    _timeout=(10, 45), *, ticker=None, instrument_code=None,
)
```

These existing APIs use [IME financial transaction statistics](https://www.ime.co.ir/standard-transactions.html),
with certificate market `c=1` or salaf market `c=0`. They do not use the separate
continuous-certificate CDC consumer and do not establish copper/GoldBar CDC
history coverage. See unresolved [#62](https://github.com/hemoboghosian/fima/issues/62)
and [#139](https://github.com/hemoboghosian/fima/issues/139).

Both APIs are exported from `fima` and `fima.IME`. Optional `ticker` matches the
exact, case-sensitive source `Symbol`; `instrument_code` matches exact string
`Code` (source `Namad`, usually ISIN-like). Select at most one. No Persian/Arabic
letter normalization or fuzzy search is performed. Prefer the stable code when
similar/reused display symbols could be ambiguous. Ticker selection returns all
matching codes in the interval; it does not invent a unique identity.

Dates are inclusive Jalali `YYYY-MM-DD` or `YYYY/MM/DD`. Missing or earlier start
clamps to `1394-03-01` for certificates and `1393-05-01` for salaf. These are
legacy request floors, **not verified inception dates or complete-history claims**.
End defaults to today according to the system date. Explicit end dates are not
clamped; reversed ranges retain `None`. Use explicit short intervals by default
in your own programs. `_chunk_size`, `_offset`, `_timeout`, validation/errors,
page bounds and TLS rules follow the options contract above. The source table's
symbol sort (`sort=LVal18AFC`) is used for pagination; within-day output order
remains unspecified. Each market response is fully validated before local
ticker/code selection, even though the website also has server-side selectors.

```python
from fima import get_all_ime_cd_trades, get_all_ime_salaf_trades

saffron = get_all_ime_cd_trades(
    start_date='1405-08-16', end_date='1405-08-17', ticker='زعف0510پ20',
)
print(saffron[['Code', 'JalaliDate', 'ClosingPrice', 'TradeVolume', 'TradeValue']])

# Verified copper salaf instrument; this is not a copper deposit certificate.
copper_salaf = get_all_ime_salaf_trades(
    start_date='1405-08-16', end_date='1405-08-17', instrument_code='IRBKKATD05A7',
)
```

Complete returned schema:

| Column | Type / meaning |
| --- | --- |
| `ID` | Source string `id`; observed repeated `1`, not a unique observation/instrument ID |
| `Code` | Stable string `Namad`, combined with trading date for uniqueness |
| `Symbol`, `Description` | Source ticker and instrument description |
| `JalaliDate`, `GregorianDate` | Trading date as ASCII `YYYY-MM-DD` and normalized `datetime64[ns]`; calendars must agree |
| `ClosingPrice`, `LastPrice` | Numeric source closing and last traded prices, distinct quotations in rials per traded security/certificate |
| `TransactionCount` | Numeric executed transaction count (`ZTotTran`) |
| `TradeVolume` | Numeric traded security/certificate quantity (`QTotTran5J`), not transaction count or universal kg/gram quantity |
| `TradeValue` | Numeric transaction value in rials (`QTotCap`), not nominal outstanding value |
| `LowPrice`, `HighPrice`, `YesterdayPrice` | Numeric minimum/maximum/previous-day source prices, rials |
| `LastPriceChange`, `ClosingPriceChange` | Numeric absolute source changes, rials |
| `LastPricePercentageChange`, `ClosingPricePercentageChange` | Raw source percentage-point changes; observed zeros despite nonzero absolute changes are preserved, not recomputed |

The page explicitly labels **all monetary amounts as rials**. No toman/thousand-
rial conversion is applied. TradeVolume retains instrument-specific units. For
the observed saffron certificate, the specification gives one gram/certificate;
this does not generalize to other certificates or financing instruments. The
statistics handler does not supply certificate size, contract multiplier,
opening price, delivery/expiry dates or underlying weight units: no columns for
these are invented. Closing price need not equal TradeValue/TradeVolume exactly,
and source floating-point serialization limits recoverable precision.

Typed empty results retain all 18 columns, including string `ID`/`Code` and
Gregorian datetime dtype. Missing days are not synthesized. Failed windows and
invalid/missing/duplicate observations now raise instead of silently returning
partial history. Live checks compare actual fields and inclusive dates across
multiple real pages for both categories; a provider HTTP 500 was correctly raised
during investigation and the unchanged comparison passed on a bounded retry.
