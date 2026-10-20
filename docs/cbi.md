# CBI — Central Bank of Iran

[User guide](../README.md) | [Public API](api.md) | [Data conventions](data-conventions.md)

`fima.CBI` provides official data from the Central Bank of the Islamic Republic
of Iran: policy/interest rates, inflation, the normal exchange-rate dataset, and
the separate electronic currency trading system (ETS) dataset.

## Policy rates: `get_cbi_policy_rates()`

```python
from fima import get_cbi_policy_rates

rates = get_cbi_policy_rates()
print(rates.tail())
```

The same function is available from `fima.CBI`. Imports make no network requests.
No arguments are required: every available year is discovered from the year
selector on the [official Persian page](https://cbi.ir/PolicyRates/policyrates_fa.aspx).
There is no fixed year list. New advertised years are included automatically.
The function returns one pandas DataFrame, sorted by date ascending with a
reset RangeIndex and exact duplicate records removed. Different observations
on the same date are retained; no rates are filled or inferred.

### Columns and financial meanings

Column meanings were checked against the Persian headings in actual DOM order
and CBI's [official English headings](https://cbi.ir/PolicyRates/policyrates_en.aspx).
Right-to-left visual positioning does not determine the mapping.

| Column | Dtype | Meaning / Persian heading |
| --- | --- | --- |
| `JalaliDate` | pandas `string` | Observation date, ASCII `YYYY-MM-DD`; تاریخ |
| `GregorianDate` | `datetime64[ns]` | The same date converted accurately from Jalali using `jdatetime`; timezone-free midnight |
| `InterbankRate` | `float64` | Interbank market rate; نرخ بازار بین‌بانکی |
| `RepoCutoffRate` | `float64` | Repo cut-off rate (minimum accepted repurchase-agreement rate); حداقل نرخ توافق بازخرید |
| `StandingLendingRate` | `float64` | CBI standing lending facility rate; نرخ اعتبارگیری قاعده‌مند |
| `StandingDepositRate` | `float64` | CBI standing deposit facility rate; نرخ سپرده‌گذاری قاعده‌مند |

All four rates use **percentage points**: `24.0` means `24%`, not `0.24`.
Persian/Arabic digits and numeric formatting are normalized. Missing provider
rates become `NaN`; legitimate zero values stay zero. Dates must be valid and
belong to the requested year. The Gregorian column supports joining other fima
time series without requiring callers to convert calendars themselves.

### Availability and errors

CBI can intermittently reject ordinary automated requests with an HTTP-200
`Request Rejected` page. fima detects this and raises `RuntimeError` identifying
the provider-access problem. It does not return fixture data, stale cached data,
an empty table or a partial history. Any failed advertised year, empty annual
table, changed schema, invalid nonmissing value or transport/HTTP failure also
raises `RuntimeError`; annual failures identify the year and chain the original
exception. An empty-year state has not been verified at CBI, so an empty table
is treated as an incomplete retrieval.

The function uses ordinary sequential HTTP requests in one session, refreshed
ASP.NET hidden fields, finite connect/read timeouts and verified HTTPS. It does
not bypass CBI access controls. It does not automatically retry rejected pages
or stateful postbacks. Availability and the extent of published history remain
under CBI's control; complete history means all years advertised at retrieval.

### Policy-rate validation evidence

During investigation on 2026-10-20, ordinary apex-domain access and sequential
ASP.NET postbacks successfully discovered and retrieved the following history:

| Advertised Jalali year | Rows retrieved |
| --- | ---: |
| 1405 | 30 |
| 1404 | 52 |
| 1403 | 52 |
| 1402 | 52 |
| 1401 | 51 |
| 1400 | 51 |
| 1399 | 6 |

These were **294 exploratory rows**, spanning `1399-11-25` through `1405-07-23`.
These counts are historical validation evidence, not configured limits or a
promise of current availability. Subsequent requests were rejected by CBI; a
later live test of the completed function retrieved the same 294 rows with zero
exact duplicates and verified all four rates for newest/middle/oldest samples.
Representative DOM rows from newest/middle/oldest years were preserved in small
deterministic tests for all four rate values. No raw page dump or security state
is shipped. See [Issue #72](https://github.com/hemoboghosian/fima/issues/72).

Deterministic tests run without CBI access. Run optional current live validation
separately:

```shell
python -m pytest test/test_cbi.py -q
python -m pytest test/test_cbi_integration.py -m integration -s -rs
```

Only the specifically recognized CBI rejection is reported as a visible live-test
skip. Other failures remain failures. This test policy does not alter public-call
error behavior or make normal CI depend on CBI availability.

## Inflation: `get_cbi_inflation_rates(frequency="monthly")`

```python
from fima import get_cbi_inflation_rates

monthly = get_cbi_inflation_rates()
annual = get_cbi_inflation_rates(frequency="annual")
```

The [official inflation page](https://cbi.ir/Inflation/Inflation_FA.aspx) has two
separate tables. Monthly output is CBI's **نرخ تورم منتهی به ماه** (rate ending in
the named month), also labelled “Monthly Inflation Rate” on its English page.
This API preserves that provider measure: it does **not** relabel it as
month-over-month CPI change or point-to-point inflation, and does not calculate
either measure from it. The page does not publish a CPI index or calculation
formula. Annual output is CBI's **نرخ تورم سالانه**, not an annual average computed
by fima from the monthly table.

| Frequency | Exact columns and dtypes |
| --- | --- |
| `monthly` (default) | `JalaliMonth`: `string` (`YYYY-MM`); `InflationRate`: `float64` |
| `annual` | `JalaliYear`: `string` (`YYYY`); `InflationRate`: `float64`; `Note`: nullable `string` |

Both rates are percentage points (`68.4` means `68.4%`). Monthly years are
discovered dynamically and retrieved sequentially with refreshed ASP.NET state.
All advertised years must succeed; a failed/empty year raises an error identifying
the year. No exact day or Gregorian daily date is invented for monthly data.
Annual annotations such as `تغییر سال پایه` are preserved in `Note`, separately
from the year. Provider missing markers (including `-.-`) become `NaN`; absent
notes are `pd.NA`. Both outputs remove exact duplicates, sort ascending and reset
the index. An invalid frequency raises `ValueError` before any HTTP request.

## Normal exchange rates: `get_cbi_exchange_rates(...)`

```python
from fima import get_cbi_exchange_rates

latest = get_cbi_exchange_rates()              # All available latest currencies
usd = get_cbi_exchange_rates("USD")           # Latest USD, not decades of requests
history = get_cbi_exchange_rates(
    ["USD", "JPY", "IQD"], start_date="2026-10-15", end_date="2026-10-19"
)
```

Signature:

```python
get_cbi_exchange_rates(currency=None, start_date=None, end_date=None, *, jalali=False)
```

The [normal page](https://cbi.ir/ExRates/rates_fa.aspx) currently describes a
**remittance rate calculated from the previous business day's foreign-exchange
transactions in the remittance hall of the Iran Center for Exchange of Currency
and Gold**. It is not ETS cash buy/sell data and is not described here as a
universal “official rate”. Earlier historical observations may belong to older
CBI rate regimes; the current definition must not be imposed retroactively.

| Column | Dtype | Meaning |
| --- | --- | --- |
| `JalaliDate` | `string` | Actual source date, ASCII `YYYY-MM-DD` |
| `GregorianDate` | `datetime64[ns]` | Converted source date |
| `CurrencyCode` | `string` | Actual export code, preserving denomination suffixes |
| `CurrencyName` | `string` | Normalized Persian currency name, denomination recorded separately |
| `CurrencyUnit` | `int64` | Foreign-currency units in the quoted rate |
| `ExchangeRate` | `float64` | Iranian rial for `CurrencyUnit` foreign units |

The quote unit was verified in CBI RSS (`1USD = … IRR`), independently of price
magnitude. Normal export codes such as `JPY100`, `IQD100`, `PKR100`, `LKR10` and
`KRW1000` retain their actual quoted values and imply units 100, 100, 100, 10 and
1000. fima does not divide these quotes into one-unit values. Advanced-search
catalog labels/codes can lag the export (for example `PKR` vs `PKR100`); the
returned export code determines `CurrencyUnit`. Use a base code such as `PKR`
or `JPY` to select that currency unambiguously.

## ETS: `get_cbi_ets_rates(...)`

```python
from fima import get_cbi_ets_rates

cash = get_cbi_ets_rates("USD", transaction_type="cash")
transfer = get_cbi_ets_rates("USD", transaction_type="transfer")
both = get_cbi_ets_rates(
    ["USD", "JPY", "IQD"], transaction_type="all",
    start_date="1405-07-23", end_date="1405-07-27", jalali=True,
)
latest_all = get_cbi_ets_rates()               # Latest cash + transfer, bounded requests
```

Signature:

```python
get_cbi_ets_rates(currency=None, transaction_type="all", start_date=None, end_date=None, *, jalali=False)
```

The [ETS page](https://cbi.ir/etsrates/etsrates_fa.aspx) is the electronic currency
trading system dataset (**سامانه معاملات الکترونیک ارز**). `cash` means **اسکناس**;
`transfer` means **حواله**; `all` combines both. The two exact Persian aliases are
also accepted. Invalid transaction types raise `ValueError` before network I/O.

Exact output order:

| Column | Dtype | Meaning |
| --- | --- | --- |
| `JalaliDate` | `string` | Source observation date |
| `GregorianDate` | `datetime64[ns]` | Converted source date |
| `CurrencyCode` | `string` | ETS currency code, e.g. `JPY` |
| `CurrencyName` | `string` | Normalized Persian currency name |
| `CurrencyUnit` | `int64` | Published foreign denomination |
| `TransactionType` | `string` | `cash` or `transfer` |
| `BuyRate` | `float64` | CBI **خرید** / XML `Buy`, in Iranian rial |
| `SellRate` | `float64` | CBI **فروش** / XML `Sell`, in Iranian rial |

One row represents a date, currency and transaction type. Source DOM order puts
sell before buy; mapping follows the headings and the explicit Buy/Sell export
controls, not visual RTL positions. CBI RSS independently names `<buy>`, `<sell>`
and `ریال ایران`. The inspected pages do not define a retail-customer counterparty
perspective, so `BuyRate` must not be interpreted as “the rate at which you buy”.
fima faithfully preserves CBI's labels without calculating a mid-rate or spread.

Denominations come from provider descriptions, not a hardcoded currency list:
`یک` = 1, `ده` = 10, `یکصد` = 100, `یک هزار` = 1000. Actual ETS descriptions verified
include `یکصد ین ژاپن`, `یکصد دینار عراق`, `ده روپیه سریلانکا` and
`یک هزار پوند لبنان`. Thus ETS `JPY`/`IQD` quotes remain for 100 units even though
the codes have no suffix. Unknown denominations fail clearly instead of assuming
one unit. Missing published rates stay `NaN`; buy/sell exports are joined on
actual source dates and denomination, with no filling of absent side observations.

## Currency history, filters and provider limitations

Both currency functions accept a code, exact normalized Persian currency name,
a nonempty list/tuple, or `None` for all advertised currencies. Arabic/Persian
letter forms and spacing are normalized; matching is exact and unambiguous,
without fuzzy search. Catalogs are discovered on every call and include historical
currencies when the provider advertises them.

With neither date supplied, the provider's **latest-day** export is requested.
For historical retrieval, supply **both** inclusive bounds; each call permits at
most **366 calendar days**. Use `YYYY-MM-DD` or `YYYY/MM/DD`, Gregorian by default;
`jalali=True` selects Jalali inputs, following the existing TGJU convention. To
retrieve a longer history, request explicit nonoverlapping bounded windows. There
is no automatic decades-long crawl or unbounded all-currency history default.

Investigation found that chart controls return rendered chart images (including
an all-history chart), while RSS feeds contain only a short recent window. The
official advanced searches provide numeric XML exports for currency selections
and complete bounded date ranges:

- [Normal advanced search](https://cbi.ir/exratesadv/exratesadv_fa.aspx)
- [ETS advanced search](https://cbi.ir/etsratesadv/etsratesadv_fa.aspx)

fima submits these normal public forms with fresh hidden state, XML output and
summary-only mode disabled. It parses `<rate>` observations, not summary statistics.
Normal retrieval uses one GET and one export POST; ETS uses two GET/POST pairs per
transaction type to retrieve buy and sell. Request count does not grow with the
number of days or currencies. HTTP requests remain sequential with finite timeouts
and verified TLS. No private/protected endpoint, browser state or access-control
bypass is used.

CBI states that no new rate is announced for holidays and the previous day's
rate applies operationally. fima **never creates holiday rows or forward-fills**.
However, the inspected CBI XML exports and dated pages themselves include some
holiday-dated repeated quotes (for example ETS 1405-07-23/24). Those source records
are retained faithfully; equal values are not evidence that an observation should
be deleted. The API cannot identify a fresh transaction from an operationally
carried provider quote when CBI does not distinguish them. Dates absent from the
export stay absent. No holiday calendar is inferred.

Outputs sort ascending by date/currency/type, remove exact duplicate records and
reset the index. A successfully returned XML report with no observations produces
an empty table with the documented dtypes. This is distinct from rejection or
malformed HTML/XML, which raises `RuntimeError`, never an empty or partial fallback.
Any failed ETS side/mode request aborts the whole call. Conflicting duplicate side
observations and changing selected metadata fail clearly.

The existing HTTP-200 rejection detection is shared by all CBI APIs, including
the known Persian rejection title. Only that specific condition may visibly skip
live integration tests; ordinary schema, parsing and network failures remain
failures. CBI availability and historical coverage remain provider-controlled.
