# Official IME investor-data audit

Investigation: 2026-11-09, baseline `a52928a779a2a650a3c01ab0948df36bd63a95f0`,
fima/PyPI 0.14.0; [tracking issue #135](https://github.com/hemoboghosian/fima/issues/135).
This records observed contracts, not a promise of exhaustive exchange coverage.

| Official source/page | Existing fima overlap | Useful gap / investor use | Coverage and reliability | Decision / priority |
| --- | --- | --- | --- | --- |
| [Options statistics](https://www.ime.co.ir/optionboard.html) | `get_all_ime_option_trades`, same handler | Complete contract histories, exact selection | Historical statistics; active/all and Call/Put verified; total/offset pagination works | Improve existing API, priority 1, [#136](https://github.com/hemoboghosian/fima/issues/136); no duplicate board API |
| [CDC statistics](https://cdc.ime.co.ir/Main/TransactionStatistics) | `get_gold_and_silver_cd_trades` uses older API | Copper and wider continuous certificates; OHLC/volume/value histories | Rendered default gold view has 77 observations, 25 per page; interactive filter contract unverified | Further verification, priority 2; [#62](https://github.com/hemoboghosian/fima/issues/62) remains scoped to legacy gold/silver filters |
| [Financial transactions](https://www.ime.co.ir/standard-transactions.html) | `get_all_ime_cd_trades`, `get_all_ime_salaf_trades` | Complete individual instrument histories; funds category also present | CD=1, salaf=0, funds=2, ALL=all; instrument discovery and pagination verified | Improve CD/salaf separately; funds already have TSETMC histories, so no duplicate API justified yet |
| [Futures statistics](https://www.ime.co.ir/fut-report.html) | `get_all_ime_futures_trades` | Contract/settlement/open-interest history | Existing `FutureAmareMoamelatHnadler.ashx` consumer and active/all selectors | Already covered in API scope; failed-window handling warrants separate follow-up |
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

## CDC verification boundary

CDC is a server-interactive Blazor application. Public HTML includes silver,
gold, base-metals and other-certificate navigation. Default statistics render
gold bars/coins, date/first/last/low/high/closing/quantity/value, with 25 of 77
rows; this is not a complete export. Custom date controls and export buttons
exist. Their backend parameters, complete universe, date inclusivity and export
completeness remain unverified: no Browser connection was available.

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
