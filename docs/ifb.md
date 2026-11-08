# IFB market values

[API](api.md) | [Data conventions](data-conventions.md) | [Source audit and priorities](ifb-audit.md)

These three additions are **unreleased**. Existing IFB functions and signatures
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
