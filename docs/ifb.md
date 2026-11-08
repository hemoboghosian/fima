# IFB data

[API](api.md) | [Data conventions](data-conventions.md) | [Source audit and priorities](ifb-audit.md)

The additions documented here are **unreleased**. Existing IFB functions and signatures
are unchanged. Import each from `fima` or `fima.IFB`.

## Aggregate snapshots

```python
from fima import get_ifb_market_values

industries = get_ifb_market_values()  # group_by="industry"
markets = get_ifb_market_values(group_by="market")
print(industries.head())
print(markets[["Market", "MarketValue", "SymbolCount", "PercentageShare"]])
```

`get_ifb_market_values(group_by="industry")` accepts `"industry"` or `"market"`.
It returns the full source breakdown, including small industries hidden in the
chart's “Other” slice. No snapshot history or historical industry weights are
implied.

| Field | Meaning and type |
| --- | --- |
| `Industry` / `Market` | Provider's Persian classification label, trimmed of surrounding/repeated whitespace; exactly one column according to `group_by` |
| `MarketValue` | Published aggregate value, nullable `Int64`, **rials**, not billions of rials |
| `SymbolCount` | Published number of symbols, nullable `Int64`; not a unique-company count |
| `PercentageShare` | Published contribution in percentage points; `6.24` means `6.24%`; no inferred decimal fraction conversion |

Source GETs: [industry](https://ifb.ir/SepratedByIndustry.aspx) and
[market](https://ifb.ir/DataReporter/GroupByMarket.aspx). The industry URL's
spelling is intentional and follows the official navigation.

Amounts come from full numeric source values, never rounded B/M display labels.
Industry aggregate values come from the full inline data array, verified against
all group headings and constituent counts. Market aggregate values come from
exact HTML title attributes; the final source total row is excluded from the
rows and retained in `attrs["TotalMarketValue"]` / `attrs["TotalSymbolCount"]`.
Reported totals/shares are preserved even when they do not reconcile exactly.

Both universes include debt and investment funds. `MarketValue` is the IFB
measure; it is not uniformly equity-company market capitalization or a verified
free-float-adjusted measure. The industry and market pages publish different
universes: 1,177 versus 1,125 symbols in the 2026-11-08 audit. Do not combine
their totals or treat them as interchangeable denominators.

Snapshot attrs: `SourceURL`, `Snapshot=True`, `Unit="IRR"`,
`ProviderUpdateLabel`. The generic page label has day/month/weekday/time **without
a year** and is not established as a dataset-specific valuation timestamp.
It is preserved as text (or `pd.NA` if absent). No observation date, live-data
freshness guarantee, or date filter is invented.

## Symbol drill-down

```python
from fima import get_ifb_symbol_market_values

symbols = get_ifb_symbol_market_values()
print(symbols[["InstrumentID", "Ticker", "Market", "Industry", "MarketValue"]].head())

# Copy exact labels/tickers from the returned table; Arabic/Persian spelling
# variants are not fuzzy-matched or guessed.
chosen = symbols.iloc[0]
selected = get_ifb_symbol_market_values(
    ticker=chosen["Ticker"], market=chosen["Market"], industry=chosen["Industry"]
)
```

`get_ifb_symbol_market_values(ticker=None, market=None, industry=None)` retrieves
the complete [industry-page](https://ifb.ir/SepratedByIndustry.aspx) constituent
table before filtering. Each selector is an exact nonempty source string; all
supplied selectors combine with AND. No match returns a typed empty DataFrame.
This is a snapshot, not a symbol history or the market-map endpoint's universe.

| Field | Meaning and type |
| --- | --- |
| `InstrumentID` | Public **IFB website ID**, pandas string, leading zeros preserved; not a TSETMC instrument code |
| `Ticker` | Source trading-symbol label, including source suffixes (for example a trailing `1`); text |
| `InstrumentName` | Published security/company description; text |
| `MarketValue` | Exact source symbol value in rials, nullable `Int64` |
| `Market` | Source market segment label; text |
| `Industry` | Source industry label; text |
| `SubIndustry` | Source subindustry label; text; an unpublished blank stays blank |
| `DetailURL` | Official public IFB instrument link identifying this record; text |

Snapshot attrs have the same meanings as above. Values are not reconstructed
from TSETMC prices/shares. There is no historical date selector because this
source does not publish a historical industry constituent table.

## Official historical market values

```python
from fima import get_ifb_market_value_history

# Every observation supplied by all three official CSV archives.
history = get_ifb_market_value_history()
print(history[["JalaliDate", "GregorianDate", "MarketRegime", "TotalMarketValue"]].tail())

# Inclusive local filters applied AFTER obtaining and validating full exports.
month = get_ifb_market_value_history("1405-07-01", "1405-07-30")
gregorian = get_ifb_market_value_history("2026-10-01", "2026-10-31", jalali=False)
```

`get_ifb_market_value_history(start_date=None, end_date=None, *, jalali=True)`
accepts either or both inclusive `YYYY-MM-DD` bounds. `jalali=False` selects
Gregorian **input** dates; both date columns always appear in the result.
An empty filtered window returns the same typed schema.

| Field | Meaning and type |
| --- | --- |
| `JalaliDate` | Source observation date, ASCII `YYYY-MM-DD` text |
| `GregorianDate` | Same date converted to pandas `datetime64[ns]`, no invented time/zone |
| `MarketRegime` | `ColoredBase`, `LetterBase`, or `LegacyBase`, indicating the source classification table |
| `TotalMarketValue` | Published total across the source markets; may be missing even when components exist |
| `FirstMarketValue`, `SecondMarketValue` | Published first/second market values |
| `ModernFinancialInstrumentsMarketValue` | Published modern financial instruments market value (including debt/funds) |
| `YellowBaseMarketValue`, `OrangeBaseMarketValue`, `RedBaseMarketValue` | Separate colored-base values, only in `ColoredBase` |
| `SMEMarketValue` | Export's `SME` field in colored/letter regimes; current HTML calls this market نوآفرین. This does not establish an unchanged historical eligibility universe |
| `ABaseMarketValue`, `BBaseMarketValue`, `JBaseMarketValue` | Separate letter-base A/B/J values, only in `LetterBase` |
| `AuctionBaseMarketValue`, `NegotiatedBaseMarketValue` | Original auction/negotiation base-market values, only in `LegacyBase` |

All value columns are nullable **`Int64` rials**, preserving individual rials
above JavaScript's exact-integer range and missing source values as `pd.NA`.
Columns inapplicable to a regime are missing, never zero. The CSV colored
export's stale `Paye A/B/J` headers are interpreted only after validating the
actual yellow/orange/red HTML grid headings. These series are not spliced into
one purportedly equivalent base-market classification.

The [official source page](https://ifb.ir/DataReporter/GroupByMarket.aspx) exposes
three whole-file CSV downloads through ordinary WebForms exports. The function
uses one session, the page's current hidden state, then all three export buttons;
it does not return the ten-row HTML first page or crawl hundreds of grid pages.
Every displayed first-page date must appear in the corresponding CSV. Headers,
row widths, dates, regime bounds, integer values and duplicate dates are checked.
The completeness boundary is **all records in all three official exports**;
there is no independently verified guarantee that IFB itself has published every
trading day. No absent dates are filled or reconstructed.

Observed archive coverage on 2026-11-08:

| Regime | Source dates | Export records |
| --- | --- | --- |
| `ColoredBase` | 1398-06-25 through 1405-08-17 | 1,783 |
| `LetterBase` | 1395-12-23 through 1398-06-24 | 602 (601 unique dates) |
| `LegacyBase` | 1393-07-14 through 1395-12-22 | 592 |

Exact repeated records are normalized once, with the removed count recorded in
`attrs["DuplicateRowCount"]`; conflicting records on one date raise an error.
The source repeats 1396-08-15 identically, so the audited combined result has
2,976 unique observations. Fourteen early letter-regime total and J-base values
are missing and stay missing. Source totals can differ from summed components
or HTML values by small amounts; the original CSV integers are retained.
The current observation can change during the session; the provider page itself
warns that today's value may vary before 16:00. These are date observations, not
certified final closes.

History attrs: `SourceURL`, `Snapshot=False`, `Unit="IRR"`,
`ExportRowCounts` (per-regime records before filtering/deduplication) and
`DuplicateRowCount`. Counts are provenance for the fetched exports, not the
number of rows in a date-filtered result.

## Errors and provider constraints

- Invalid selectors/bounds and malformed, changed or incomplete schemas raise
  `ValueError`. Missing tables/empty exports that contradict visible source rows
  are failures, not successful empty datasets.
- `requests.RequestException` subclasses propagate for HTTP/network failures.
  Connect/read timeouts are 10/30 seconds; transient 502/503/504 and connect
  failures have at most one retry. 401/403/429 are not retried. Certificate
  verification stays enabled. Sessions close on success and failure.
- There are no import-time requests, cache, browser dependency, alternate
  provider fallback or access-control workaround. If IFB is unreachable, no
  valid snapshot/history is claimed.
- Existing Options APIs remain the route for IFB derivative chains/watches and
  instrument histories. TSETMC symbol capitalization is a separate calculation
  using its closing prices and share counts; it does not replace these IFB totals.

## Historical bond YTM

```python
from fima import get_ifb_bond_yield_history

history = get_ifb_bond_yield_history("1405-07-01", "1405-08-17", ticker="اخزا204")
print(history[["InstrumentID", "LastTradeJalaliDate", "ClosingPrice", "TradeVolume", "YTM"]].tail())

# IFB website ID, distinct from TSETMC's instrument code. Both calendars appear
# in output regardless of the input calendar selected here.
gregorian = get_ifb_bond_yield_history(
    "2026-10-01", "2026-11-08", instrument_id="33029", jalali=False
)

# Inspect all distinct official observations, including explicitly flagged
# contradictions. Default behavior raises on such dates.
archive = get_ifb_bond_yield_history(
    "1402-01-01", "1405-08-17", instrument_id="33029", on_conflict="preserve"
)
print(archive.loc[archive["HasConflictingObservation"]])
```

`get_ifb_bond_yield_history(start_date, end_date, ticker=None, *, instrument_id=None,
jalali=True, on_conflict="raise")` obtains a verified selected instrument's complete
official [YTM history export](https://ifb.ir/YTM.aspx). Both inclusive date bounds
are required, as `YYYY-MM-DD` strings. The source requires explicit dates; no
default one-month window is silently called complete history.

Supply an exact nonempty ticker or string IFB `instrument_id`. If both are
provided, both must identify the same current selector option. Ambiguous names
raise `ValueError`; for example, the provider's `اراد157` label maps to two IDs.
Copy the ID from the official instrument link/selector, preserving leading zeros.
Unknown/unlisted instruments raise an error rather than returning another bond.
This API deliberately does not reconstruct IDs for the all-instrument export,
whose older labels can be absent from the current instrument selector.

| Column | Meaning/type |
| --- | --- |
| `InstrumentID` | Verified public IFB website instrument ID, pandas string |
| `Ticker` | Exact provider instrument label, whitespace trimmed; text |
| `LastTradeJalaliDate` | Published last-trading date, ASCII `YYYY-MM-DD` |
| `LastTradeGregorianDate` | Same date as pandas `datetime64[ns]` |
| `IssueJalaliDate`, `IssueGregorianDate` | Provider issue date in each calendar; missing stays missing |
| `MaturityJalaliDate`, `MaturityGregorianDate` | Provider maturity date in each calendar; missing stays missing |
| `ClosingPrice` | Published historical closing price, numeric **rials per security**; not last-traded or Nelson settlement price |
| `TradeVolume` | Published number of securities traded, nullable `Int64`; zero remains zero |
| `YTM` | Published **effective annual yield to maturity in percentage points**; 43.68 means 43.68%, not 0.4368 |
| `HasConflictingObservation` | Boolean; true for every distinct observation on a conflicting last-trade date |

The date filter applies to the published **last-trading date**, not an inferred
quote timestamp, settlement date or curve-calibration date. Rows are ascending
by that date. Missing numeric values remain missing; source negative/extreme
yields are not silently clamped. The table does not expose historical coupon
rates, simple returns, YTC, accrued interest, clean/dirty classifications or fees.
Do not equate these with YTM or infer them from its magnitude.

The official definition describes effective annual dated-cash-flow discounting:
for a discount treasury, `(face / price) ** (365 / days) - 1`; for a coupon bond,
all dated payments and principal enter the annual cash-flow equation. Independent
source comparisons reproduced a treasury's 43.68% and a coupon bond's 39.93%
against a 23% nominal coupon. These are interpretation checks; fima returns the
provider's historical YTM without recomputing or correcting it. See the
[financial investigation](ifb-audit.md#issue-120-fixed-income-investigation--2026-11-08)
for verified instruments, payment schedules and official definition links.

Retrieval uses one ordinary WebForms session: GET, filter POST with current
hidden fields/cookies, then the full export POST. The source's `.xls` download is
a seven-column HTML table. The API verifies filter state, instrument IDs in
displayed rows, column schemas, date/identity bounds, all visible records and
presence of later records when the grid advertises pagination. It rejects
truncated exports and normal/error HTML substituted for downloads. A confirmed
empty filtered grid returns the typed schema without requesting the misleading
empty export, which the provider serves as a normal page.

Completeness means **all records in the selected official filtered export**,
not proof that IFB publishes every trading day or that the current selector
covers every expired instrument. A broad all-instrument investigation observed
29,663 source records across 784 ticker labels, dated 1401-10-26..1405-08-16.
The source contains exact repeats and conflicting values. Selected treasury
33029 had 456 source records, starting 1403-06-05; coupon 40578 had only one
observed trading date, 1404-10-22. These are observed coverage limits, not fixed
promises or invented daily continuity.

Identical repeated rows are normalized and counted in `attrs["DuplicateRowCount"]`.
With default `on_conflict="raise"`, different source observations for one selected
instrument/date raise `ValueError`. With `"preserve"`, all distinct observations
remain, every affected row is flagged, and `attrs["ConflictingDates"]` lists the
dates. No authoritative revision is chosen and volumes must not be summed across
contradictory records as though they were separate trading sessions.

Other attrs: `SourceURL`, `Snapshot=False`, `PriceUnit="IRR"`,
`YieldUnit="PercentagePoints"`, `VolumeUnit="Securities"`, `ExportRowCount`
(before duplicate normalization). Valid empty windows have zero counts.
Invalid inputs, source validation errors, ambiguous identity, changed schemas,
incomplete exports and default conflicts raise `ValueError`. HTTP/network errors
propagate as `requests.RequestException` subclasses. Connect/read timeouts are
10/30 seconds with at most one transient 502/503/504/connect retry; no access
denial/rate-limit retry or TLS bypass. Importing the API makes no HTTP requests.

Existing `get_all_bonds_without_coupons`, `get_all_bonds_with_coupons` and
`get_risk_free_rate` retain their signatures, source behavior and units. The
scalar risk-free estimate remains decimal and is not redefined as a curve rate.
