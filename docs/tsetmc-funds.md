# TSETMC fund data

[User guide](../README.md) | [Fund guide](funds.md) | [Migration](data-migration.md#funds)

```python
from fima import get_tsetmc_fund_types, get_tsetmc_funds, get_tsetmc_fund_details

types = get_tsetmc_fund_types()
funds = get_tsetmc_funds("mixed")
print(funds[["FundName", "RegistrationNumber", "SubscriptionNAV", "RedemptionNAV"]])
details = get_tsetmc_fund_details(funds.iloc[0]["FundName"], fund_type="mixed")
# Explicit registration selection also remains supported.
details = get_tsetmc_fund_details(reg_no=funds.iloc[0]["RegistrationNumber"])
```

Snapshots use canonical PascalCase columns, numeric per-unit NAVs and separate
TotalNAV, pandas Gregorian date columns, string identifiers and percentage-point
weights/returns. The actual fund name is source mfName (FundName); source name
becomes ProviderName and can be null. fixIncome becomes FundTypeID, while the
different source fundType remains ProviderFundTypeCode. ProviderFundSize is not
assumed to mean total assets. See the full mapping in the migration notes.
Unknown additional columns capitalize the source's initial letter; nested
Stats/FundProfits payloads keep raw provider keys and row order. An explicitly
empty group returns an empty frame without columns.

The detail API intentionally returns the **complete raw provider dict**, including
regNo/mfName/stats/fundProfits with their original types, keys and ordering. It is
not a normalized history table. To inspect raw history explicitly, use
`pd.DataFrame(details.get("stats") or [])`. Snapshot and detail dates/coverage
can differ; do not fill one from the other.

Name selection is exact after Arabic/Persian letter, whitespace and English-case
normalization. With no fund_type, all ten supported individual groups are checked;
a failed group propagates instead of assuming uniqueness. Repeated matches for
one registration are accepted; multiple registrations raise ValueError. Numeric
positional registration arguments and reg_no= are still supported. Conflicting
name/registration selectors fail before HTTP. No fuzzy match is attempted.

Numeric group arguments still accept nonnegative whole numbers or ASCII digit
strings. Registration arguments require positive whole numbers; these are not
instrument codes. Offline type discovery has string FundTypeID values, Persian
FundTypeName and EnglishName. Group 0 is an advanced provider selector, not a
listed supported group, and can fail.

Invalid parameters, malformed JSON/records and mismatched registration raise
ValueError; transport/certificate/timeout/HTTP failures propagate as requests
exceptions. Requests retain verified HTTPS, finite timeouts and bounded retries.
There are no import-time network requests or Fipiran/website fallbacks.

Provider evidence: [official menu](https://tsetmc.ir/Fund/11172) and its public
frontend confirm mfName/fixIncome and the Fund/GetFunds and GetFundInDetail API
paths. Live October 2026 responses showed fundType=0 alongside real fixIncome
groups, null name alongside actual mfName, list/detail freshness differences,
unsorted stats and HTTP 500 for group 0 or nonexistent registration. These are
preserved source limitations, tracked in [Issue #42](https://github.com/hemoboghosian/fima/issues/42).
