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

```text
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

```text
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

## Discover contracts and financial instrument codes

```python
from fima import get_all_ime_cd_trades, get_all_ime_option_trades

certificates = get_all_ime_cd_trades("1405-08-16", "1405-08-17")
print(certificates[["Symbol", "Code", "Description"]].drop_duplicates())
if not certificates.empty:
    code = certificates.iloc[0]["Code"]
    selected = get_all_ime_cd_trades("1405-08-16", "1405-08-17", instrument_code=code)

options = get_all_ime_option_trades(start_date="1405-08-16", end_date="1405-08-17")
print(options[["ContractCode", "ContractDescription"]].drop_duplicates())
```

Choose the intended description/identity; the first row here only illustrates
code reuse. `Code` is not row `ID`; ticker can match several codes across history.
For salaf use the same short-report discovery with `get_all_ime_salaf_trades`.
For futures inspect `ContractCode`/description in a short futures report and
filter locally; there is no futures contract selector argument. Report membership
does not establish an exhaustive instrument catalog or contract multiplier.

## Physical trades and producers

`get_all_ime_physical_trades(start_date=None, end_date=None, ...)` takes inclusive
Jalali YYYY-MM-DD or YYYY/MM/DD. Start defaults/clamps to 1385-01-01, end to today,
and future end dates clamp to today. Reversed/empty intervals give an empty,
possibly columnless DataFrame. The floor is not independently verified inception.

Important columns: `GoodsName`, `Symbol`, `ProducerName`, `ClosingPrice` (source
weighted price), low/high prices, supply/demand, `TradeVolume`, `TradeValue`,
`Currency`, `Unit`, trading/delivery/settlement Jalali dates. Quotation, quantity
and value bases can differ, including thousand-rial physical trade-value displays.
Keep native units; do not assume price times volume equals value or that export
and physical quotations share a scale.

Internal compatibility controls remain `_chunk_size=30`, `_max_workers=2`,
`_timeout=(20,120)`, `_max_retries=3`, `_strict=True`, `_verbose=False`,
`_rescue_chunk_size=7`. Windows are retried/rescued; default strict mode raises
RuntimeError for final failures. `_strict=False` can return partial data without
a completeness report. Shape/date errors can raise; no source-total guarantee
is introduced for physical reports.

```python
from fima import (
    get_all_ime_physical_trades, get_all_physical_producer_products,
    get_producer_physical_trades,
)

trades = get_all_ime_physical_trades("1405-07-20", "1405-07-21")
producers = get_all_physical_producer_products(all_ime_physical_trades=trades)
print(producers)
if not producers.empty:
    producer = producers.iloc[0]["ProducerName"]
    selected = get_producer_physical_trades(producer, all_ime_physical_trades=trades)
```

Producer matching is exact. The product aggregator returns `ProducerName` and
sorted distinct `Products` lists; supplied-frame aggregation uses all supplied
rows without applying date arguments. The producer-trades function does apply
inclusive local date bounds to supplied data. Unknown producers print/return empty.

For exports, discover exact `ProducerName` from a short `get_all_ime_export_trades`
result and pass it to `get_producer_export_trades(producer, start_date, end_date)`.
`get_all_export_producer_products()` has no bounds/reuse parameter and downloads
default export history from 1387-12-01 to today before grouping; it is expensive
catalog discovery. Columnless empty/reversed export results can cause legacy
producer wrappers to raise KeyError/TypeError. Download failures propagate.

## Legacy gold and silver CDC

`get_gold_and_silver_cd_trades(contract_type, start_date=None, end_date=None,
_timeout=(10,45))` accepts the configured strings `gold_coin_cd`, `gold_bar_cd`,
`silver_bar_cd`. **Accepted syntax is not verified current filter coverage**:
[#62](https://github.com/hemoboghosian/fima/issues/62) and
[#139](https://github.com/hemoboghosian/fima/issues/139) remain unresolved.

Dates here require Jalali YYYY-MM-DD, unlike other slash-capable IME functions.
Start defaults/clamps to 1401-12-01 and end to today; reversed returns None.
Unknown contract_type raises KeyError. Non-200 responses raise a generic Exception;
network/JSON/schema/date errors also propagate. A valid empty response has a small
typed date/volume/value schema, not the full nonempty contract/activity schema and
not proof of an empty market. Source values are not multiplied by contract sizes.
Do not substitute copper salaf, futures or standard certificates for CDC history.
