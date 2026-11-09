# Official IME investor-data audit

Investigation: 2026-11-09, baseline `a52928a779a2a650a3c01ab0948df36bd63a95f0`,
fima/PyPI 0.14.0; [tracking issue #135](https://github.com/hemoboghosian/fima/issues/135).
This records observed contracts, not a promise of exhaustive exchange coverage.

| Official source/page | Existing fima overlap | Useful gap / investor use | Coverage and reliability | Decision / priority |
| --- | --- | --- | --- | --- |
| [Options statistics](https://www.ime.co.ir/optionboard.html) | `get_all_ime_option_trades`, same handler | Complete contract histories, exact selection | Historical statistics; active/all and Call/Put verified; total/offset pagination works | Improve existing API, priority 1, [#136](https://github.com/hemoboghosian/fima/issues/136); no duplicate board API |
| [CDC statistics](https://cdc.ime.co.ir/Main/TransactionStatistics) | `get_gold_and_silver_cd_trades` uses older API | Copper and wider continuous certificates; OHLC/volume/value histories | Rendered default gold view has 77 observations, 25 per page; interactive filter contract unverified | Further verification, priority 2; [#62](https://github.com/hemoboghosian/fima/issues/62) remains scoped to legacy gold/silver filters |
| [Financial transactions](https://www.ime.co.ir/standard-transactions.html) | `get_all_ime_cd_trades`, `get_all_ime_salaf_trades` | Complete individual instrument histories; funds category also present | CD=1, salaf=0, funds=2, ALL=all; instrument discovery and pagination verified | Improve existing CD/salaf APIs in [#137](https://github.com/hemoboghosian/fima/issues/137); funds already have TSETMC histories, so no duplicate API justified yet |
| [Futures statistics](https://www.ime.co.ir/fut-report.html) | `get_all_ime_futures_trades` | Contract/settlement/open-interest history | Existing `FutureAmareMoamelatHnadler.ashx` consumer and active/all selectors | Existing API; failed-window/completeness correction in #144 |
| [Live derivatives board](https://cdn.ime.co.ir/) | Historical functions lack order books | Active option/futures bids, asks, metadata | Angular/SignalR consumer; initial HTML says no update; no browser connection or verified live message contract | High potential value, further verification; no speculative quote API |
| [Certificate specifications](https://www.ime.co.ir/CDCsymbols.html), [CDC details](https://cdc.ime.co.ir/Main/ContractDetails) | No standalone catalog | Instrument identity and units | Static symbols/units verified; no verified join to API filters | Semantic evidence; defer catalog until usable history identifiers can be joined |

## Existing API inventory

All eleven APIs are exported through `fima.IME` and `fima`. Date arguments are
Jalali; existing broad defaults are retained. Use explicit short intervals.

| Function | Baseline parameters/defaults after required arguments | Source / output |
| --- | --- | --- |
| `get_all_ime_physical_trades` | `start_date=None, end_date=None, _chunk_size=30, _max_workers=2, _timeout=(20,120), _max_retries=3, _strict=True, _verbose=False, _rescue_chunk_size=7` | `imedata.asmx/GetAmareMoamelatList`: goods/producer, prices, supply/demand, volume/value, currencies/units and trading/delivery/settlement dates; retries/rescue exist |
| `get_all_ime_futures_trades` | `only_active=False, start_date=None, end_date=None, _chunk_size=100, _offset=0, _timeout=(10,45)` | `futurereports/FutureAmareMoamelatHnadler.ashx`: contract, OHLC, settlement, open interest, activity/client types |
| `get_all_ime_option_trades` | `option_type='All', only_active=False, start_date=None, end_date=None, _chunk_size=100, _offset=0, _timeout=(10,45)` | `option/optionboarddata.ashx`: daily options; additive `contract_code` and full schema in [guide](ime.md) |
| `get_all_physical_producer_products` | `start_date=None, end_date=None, all_ime_physical_trades=None` | Physical aggregation: `ProducerName`, `Products` |
| `get_producer_physical_trades(producer, ...)` | `start_date=None, end_date=None, all_ime_physical_trades=None` | Local producer/date selection over physical trades |
| `get_all_ime_export_trades` | `start_date=None, end_date=None, _chunk_size=100, _offset=40, _timeout=(10,45)` | `fiziki/export.ashx`: export prices/quantities, currencies and producer/warehouse metadata |
| `get_all_ime_cd_trades` | `start_date=None, end_date=None, _chunk_size=100, _offset=30, _timeout=(10,45)` | `bazaremali/bazaremalidata.ashx`, `c=1`: Code/Symbol, prices, quantity/value/count, changes, dates |
| `get_all_export_producer_products` | No arguments | Export aggregation: `ProducerName`, `Products` |
| `get_producer_export_trades(producer, ...)` | `start_date=None, end_date=None` | Local producer/date selection over export trades |
| `get_all_ime_salaf_trades` | `start_date=None, end_date=None, _chunk_size=100, _offset=30, _timeout=(10,45)` | Same financial handler, `c=0`; same schema, different instruments |
| `get_gold_and_silver_cd_trades(contract_type, ...)` | `start_date=None, end_date=None, _timeout=(10,45)` | `dataapi.ime.co.ir/api/CDC/CDCTrades`: legacy gold/silver filters, paginated client activity/delivery dates; current filters unresolved |

## Historical consumers and evidence

Options inline JavaScript builds
`/subsystems/ime/option/optionboarddata.ashx?f=...&t=...&c=...&ot=...&lang=8`.
Dates are Jalali, `c=-1` means currently active, `c=0` all, `ot=0/1/2`
all/Call/Put. Individual contract IDs appear in the selector. Shared
`/scripts/Mobike/forms.js` creates a Bootstrap table with server-side pagination
and export-all support. Responses have integer `total` and `rows`; `limit` and
`offset` change the slice. These are public page parameters, not guessed APIs.

For 1405/08/16–17, active/all-type history reported 628 rows. `limit=2` returned
two; `offset=2` advanced with the same total. Omitting pagination returned all
628 in this sample: omission alone was **not** reproduced as truncation. The
confirmed bug was catching failed date windows and continuing; missing `rows`
also became empty success and totals were ignored. Deterministic regressions
characterize those failures. Pagination now validates reported completeness.

First/last/high/low and previous/today settlement are separate. Prices and trade
values are labelled rials; no multiplier is inferred. The page labels
`ChangeOpenInterest` as a percentage, but supplies values such as `-106`; fima
retains raw `OpenInterestChange` without scaling or claiming that this establishes
percentage units. No structured strike, underlying ID, multiplier, bid/ask, IV
or Greeks appears in this table. Description text is not parsed into metadata.

The financial page builds `/subsystems/ime/bazaremali/bazaremalidata.ashx` with
Jalali `f/t`, market `c`, instrument `ot`, `lang=8`. Its instrument selector calls
`/subsystems/ime/bazaremali/instruments.ashx?i=<market>` and returned 60 fund
instruments. Selection uses returned `id`, not display descriptions. For
1405/08/16–17, CD/funds/salaf totals were 20/163/5; limit/offset worked. Financial
record `id` repeatedly equals `1`, so it is **not a unique observation identity**;
`Namad` (public `Code`) plus trading date identifies history. `ZTotTran`,
`QTotTran5J`, `QTotCap` distinguish transaction count, quantity and value. Source
percentage fields were zero despite nonzero absolute changes; do not derive
replacement observations or promise independently verified returns from zeros.

The page explicitly states all monetary amounts are rials. Instrument selection
was also verified using `ot=IRK1A12405A6` (certificate) and `ot=IRBKKATD05A7`
(salaf): each returned exactly that code and both inclusive dates. The improved
APIs choose exact local filtering after full response validation, so no opaque
provider payload is required. The visible sortable symbol column establishes
`sort=LVal18AFC`; repeated first/second-page requests returned consistent slices.
The live two-record-page CD comparison once returned HTTP 500 at offset 6; exact
and adjacent diagnostic requests returned 200, and the unchanged test passed on
one bounded retry. This is an observed transient provider failure, not hidden by
skipping or returning partial data. The subsequent comparison also validates
symbol-sorted pages. The two-day salaf comparison passed.

## CDC verification boundary

CDC is a server-interactive Blazor application. Public HTML includes silver,
gold, base-metals and other-certificate navigation. Default statistics render
gold bars/coins, date/first/last/low/high/closing/quantity/value, with 25 of 77
rows; this is not a complete export. Custom date controls and export buttons
exist. Their backend parameters, complete universe, date inclusivity and export
completeness remain unverified: no Browser connection was available.
The wider catalog/copper verification is tracked in
[#139](https://github.com/hemoboghosian/fima/issues/139), separately from #62.

The established `CDCTrades` POST with `marketId=22`, `customFilter='CD1GOB0001'`,
Gregorian 2026-11-01–08 returned HTTP 200, `Success=true`, `TotalCount=0`,
`HasNextPage=false`, `Data=[]`. The website shows gold observations in that
interval. This reproduces #62's consumer/filter discrepancy, not an empty market
or proof of outage. The API root returned explicit request-rejected HTML; no
access-control workaround was attempted and no replacement filter was guessed.

Official specifications give `CopperCthd` as 1 kg/certificate, `GoldBar` 0.1 g,
`SilverBar` 1 g, `GoldCoin` one coin. Other continuous symbols include
`SteelRebar`, `Bitumen`, `ZincIngot`, `LeadIngot`, `IronOrePlt`, `PistaCL`, `KMCT9`.
These display symbols are **not established API filter identifiers**. Copper
salaf/futures must not substitute for copper certificate history. A CDC feature
must verify its current consumer, catalog and multi-product pagination first.

## Phase #139: continuous-certificate consumer investigation

Rechecked 2026-11-09 against published 0.14.1 and clean local/origin `master`
`14148d8a618e254232805245a679eefce889af23`. The existing `v0.14.1` tag and
GitHub Release target that commit. This phase does not authorize a release.
Tracking: [#139](https://github.com/hemoboghosian/fima/issues/139), with the
independent gold/silver filter investigation retained in
[#62](https://github.com/hemoboghosian/fima/issues/62).

### Current public-page evidence

Ordinary verified-HTTPS GETs to statistics, ContractDetails and CDCsymbols
returned HTTP 200 without redirects. This verifies public HTML access, not
successful interactive data requests. Two independent statistics GETs contained
identical default GoldBar table cells: 25 observations, a reported total of 77,
and descending dates from 1405/08/17 through 1405/07/19. Page-size controls show
10, 25, 50 and 100; the paginator shows four pages at the default size. Neither
the other pages nor an entire history has been downloaded or validated.

The table labels date, first, last, volume, low, high, closing price and value;
a percentage badge accompanies closing price. For example, the rendered
1405/08/17 gold row shows first 33,299,900, last 33,390,000, low 32,752,030,
high 33,498,990, closing 33,237,968, volume 581,323 and value
19,321,995,433,030. This is one displayed observation, not a verified raw
response schema or evidence of copper history. Source numeric precision beyond
the displayed values, transaction counts and settlement fields remain unknown.
No observations or missing trading days are synthesized.

HTML includes Blazor server-interactive markers and `_framework/blazor.web.js`.
Two prerendered forms declare `method=post` and
`action=/Main/TransactionStatistics`; those attributes do not establish the
requests actually used by the running application. Prerendered date-picker text
also does not establish the applied date interval or its boundary semantics.
The publicly linked [download helper](https://cdc.ime.co.ir/js/download.js)
accepts a server-provided `contentStreamReference`, creates a Blob and clicks a
temporary download link. It declares no standalone history/export endpoint.
Export format, scope, totals and correspondence to the selected filters remain
unverified. No speculative form submission, Blazor-circuit reconstruction,
market-ID search or alternate legacy filter request was attempted.

### Specification catalog and copper units

The [official symbol specifications](https://www.ime.co.ir/CDCsymbols.html)
currently list these eleven continuous display symbols:

| Display symbol | Underlying | Physical amount per certificate |
| --- | --- | --- |
| `CopperCthd` | Copper cathode | 1 kg |
| `GoldBar` | Gold bar | 0.1 g |
| `SilverBar` | Silver bar | 1 g |
| `GoldCoin` | Gold coin | One coin |
| `SteelRebar` | Steel rebar | 1 kg |
| `Bitumen` | Bitumen | 1 kg |
| `ZincIngot` | Zinc ingot | 1 kg |
| `LeadIngot` | Lead ingot | 1 kg |
| `IronOrePlt` | Iron-ore pellet | 1 kg |
| `PistaCL` | Pistachio | 1 kg |
| `KMCT9` | Kerman Motor T9 vehicle | 0.0001 vehicle |

This is the specification page's displayed product list, not a complete CDC
data-consumer instrument catalog. Its additional dated saffron warehouse
symbols must not be treated as the same source universe. The page lists no
maturity for the eleven continuous products; warehouse acceptance/expiry rules
still apply. No active-status flag, stable history ID, warehouse-contract join,
inception date or exhaustive historical instrument universe has been verified.
The display symbols are not established `customFilter` codes.

The symbol page links the [copper certificate contract](https://www.ime.co.ir/Cooper.html).
That page independently confirms `CopperCthd`, one kg per certificate, rials
per certificate, a 10-rial price tick, and a one-certificate trading lot. Its
1,000-certificate buy-order ceiling is labelled as one tonne; this does not
establish the CDC history response's volume unit or justify adding a derived
weight column. Copper OHLC, quantities, values, source decimals and date range
still require observation-level validation against the actual consumer.
The default [ContractDetails](https://cdc.ime.co.ir/Main/ContractDetails)
view confirms GoldBar quotation in rials per 0.1 g. Its gold tabs and units
must not be generalized to copper or other selected categories.

### Existing overlap and implementation decision

`get_all_ime_cd_trades` uses the standard-transactions financial handler, not
the CDC application. `get_all_ime_salaf_trades` uses that handler's separate
financing category; its copper salaf instrument is not a copper certificate.
`get_all_ime_futures_trades` downloads derivatives statistics, not deposit
certificates. `get_gold_and_silver_cd_trades` uses the older CDCTrades POST
contract with market/filter constants whose current support is unresolved in
#62. Current public resources inspected here do not establish those constants
as the CDC application's supported request contract. No such request was added
or used as substitute evidence in this phase. Existing APIs and the 0.14.1
completeness fixes remain unchanged.

| Candidate / priority | Source and universe | Coverage, units and dates verified | Existing overlap | Investor value / reliability / cost | Decision |
| --- | --- | --- | --- | --- | --- |
| Copper certificate history / 1 | CDC UI; CopperCthd specification | 1 kg/certificate and rial/certificate specification only; no consumer history IDs or date bounds | Separate from CD/salaf/futures histories | High value; consumer unverified; implementation cost unknown until capture | Defer runtime API pending genuine UI/history/export evidence |
| Gold/silver history correction / 2 | CDC UI versus legacy CDCTrades | Default gold first page and GoldBar quotation verified; no complete selected interval or silver observations | Existing gold/silver API; #62 | High value; filter mismatch unresolved; separate fix requires source contract | Keep #62 independently scoped; no guessed replacement |
| Instrument discovery / 3 | CDCsymbols, ContractDetails, linked copper contract | Eleven displayed products and physical sizes; no complete stable consumer-ID join or active dates | No usable catalog API | Useful with history; static specifications alone insufficient; modest parsing but unresolved joins | Record specification catalog; defer public catalog |
| Other certificate histories / 4 | CDC categories and specification list | Product labels/sizes only; no selected histories | Do not conflate dated standard-market CDs | Potential value; unverified source and coverage; unknown cost | No generalized collector |

### Required interactive evidence

The permitted browser runtime reported `No browser is available`; documented
browser discovery returned an empty list. After the maintainer explicitly
selected the in-app Browser, selecting that surface returned
`Browser is not available: iab`. This is a local browser capability blocker,
not a provider denial or a fima defect. The selected browser could not perform
any filter, date, pagination or export interaction. No alternate browser-control
mechanism or browser automation dependency was added.

If a connection cannot be provided, a narrowly scoped sanitized manual capture
is needed. In an ordinary public session, enable DevTools Network recording
with Preserve log, load statistics, select base metals and copper cathode, and
record the displayed product/contract identity. Apply a short custom date
interval, refresh, advance to page 2, change page size and export that same
selection. Repeat with gold or silver, including one interval with more than
25 rows and one known non-trading day. Include the selected controls, table
headers, first/last dates, source total/page count and resulting public exports;
these are needed to compare filters, units and export coverage.

For each actual data/export transaction, retain method, URL, ordinary parameter
names and nonsecret values, response status/content type/schema, totals and
instrument identifiers. A sanitized HAR may omit WebSocket messages: if the
site uses a Blazor/SignalR connection, include only the relevant sanitized
message structure and action correspondence, or report that the payload is
opaque. Do not decode opaque session/circuit state or infer an undocumented
JSON endpoint from it. An export plus UI evidence can establish financial
observations even when transport details remain insufficient for a client.

Before sharing, remove Cookie/Set-Cookie and Authorization headers, CSRF/
antiforgery values, bearer/access tokens, connection/circuit/session identifiers,
Blazor descriptors and personal/account data from URLs, headers, bodies and
messages. Do not share a complete authenticated capture or credentials. Leave
nonsecret field names and financial instrument/date/page parameters intact.
Keep raw captures, provider dumps and investigation scripts outside the repo.

### Validation and release boundary

The full strict non-integration suite passed: 1,049 tests, with 150 integration
cases deselected. Three opt-in comparisons of the existing option/CD/salaf
histories against their real source records passed, with 95 deterministic cases
deselected. These are existing-market regressions, not successful CDC browser
or copper-history validation. No new runtime API, schema, signature, supported
history boundary or live CDC test is claimed.

Clean-snapshot and working-tree wheel/sdist builds and strict metadata checks
passed. The clean sdist contains 34 files, including the eight explicitly
declared guides; its 14 Python sources match Git. Working-only cached public
extras and their generated SOURCES entries are the inherited #133 issue; common
source/documentation payloads agree after CRLF normalization. Repository
documentation file links resolve. Only this audit changes; runtime code,
dependencies, manifest and package version remain intact.

## Final bounded completion assessment

The investor-focused expansion is sufficiently scoped by the completed option,
CD and salaf history correctness/selection improvements, verified financial
contracts and investor documentation. Eleven existing public IME APIs cover
physical, derivatives, financial, export and producer aggregation use cases;
another API is not needed merely to cover another website page. CDC #139/#62
remain deferred provider-contract research, not resolved implementation bugs.
This assessment performs no further CDC/browser investigation.

The bounded remaining-risk review reproduced one shared failure class in the
older futures/export downloaders: a valid first window followed by a timeout or
missing `rows` still returned successful partial history; reported totals were
ignored. [#144](https://github.com/hemoboghosian/fima/issues/144) corrects that
class without new public functions or changed financial mappings. Physical
history already defaults to strict failure handling with bounded rescue;
producer wrappers inherit the underlying download behavior. Existing corrected
option/CD/salaf contracts are preserved rather than reopened.

Official futures 1404/01/01–1404/02/01 returned 487 observations; `limit=2`
offsets 0/2 matched successive full-response slices. Recent 1405/08/16–17
futures returned a valid empty report, not evidence of outage. Futures omit
some trade/activity/price fields legitimately, which must remain missing.
Export 1405/08/16–17 returned 92 observations without pagination; `limit=2`
offset 2 returned HTTP 500 both with and without the visible GoodsName sort.
This provider behavior is separate from fima's confirmed error suppression.
The fix validates complete export windows without relying on that failing
pagination path. The pages' published field lists and shared server-side table
helper establish the existing consumers; no new source discovery is required.
See the [guide](ime.md#futures-and-export-report-histories) for preserved units,
optional fields and explicit completeness/error limits. After the focused
correction, the IME milestone does not require further optional development.
Version 0.14.1 and its existing tag/release remain unchanged.

## Coverage, network and release limits

Traversal completeness is relative to the provider's reported total, not proof
of every historic trading day since inception. Missing days are not synthesized.
Stable totals cannot establish immutable snapshots or correct exchange records;
revisions between pages can still occur.

All required pages and the linked futures/specification/live-board HTML were
reachable over ordinary HTTPS without redirects. Sandbox probes initially hit
an unavailable local proxy. Outside-sandbox diagnosis separately reproduced
PyPI/files.pythonhosted.org connection timeouts. Maintainer VPN assistance
restored PyPI metadata access (0.14.0). TLS remains enabled; deterministic CI
does not require IME. No version change, tag, Release or publication is authorized.
The maintainer then disconnected the VPN for IME live checks; VPN state is
coordinated explicitly before switching between IME and PyPI-dependent checks.
