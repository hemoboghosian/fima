# IME historical market data

Use explicit short Jalali intervals. Existing broad defaults are retained for
compatibility and do not prove history since inception. The [source audit](ime-audit.md)
explains API overlap and unresolved continuous-certificate filters.

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
