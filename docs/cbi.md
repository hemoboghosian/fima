# CBI — Central Bank of Iran

[User guide](../README.md) | [Public API](api.md) | [Data conventions](data-conventions.md)

`fima.CBI` provides official data from the Central Bank of the Islamic Republic
of Iran, beginning with policy/interest-rate history. Its first public function is
`get_cbi_policy_rates()`.

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

## Columns and financial meanings

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

## Availability and errors

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

## Validation evidence

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
