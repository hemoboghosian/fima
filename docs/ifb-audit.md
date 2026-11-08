# IFB Data Center audit — 2026-11-08

[API](api.md) | [IFB guide](ifb.md) | [Tracking issue #119](https://github.com/hemoboghosian/fima/issues/119)

This inventory precedes the implementation decision. Evidence comes from the
official homepage navigation, downloaded public HTML/JavaScript, and bounded
local HTTPS requests with certificate verification. Raw downloads are temporary
local investigation files, not repository fixtures. No screenshots were available
in this session. No browser was connected. The search/web fetcher timed out;
the sandbox's localhost proxy refused connections. Normal local HTTP outside
that sandbox reached the pages below. These are different access observations,
not proof of a general IFB outage.

## Inventory and priority matrix

P1 means useful, directly verified, little public API overlap. P2 needs further
financial/coverage investigation or more state handling. P3 is already covered,
duplicative or mainly presentational. Blocked means unverified from this session.
“History” describes source evidence, not a guarantee of an uninterrupted archive.
URLs and Persian titles below follow the actual navigation/page headings.

| Section | URL | Dataset | Snapshot | History | Inputs/filters | Format | Existing fima overlap | Accessibility | Priority | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ارزش بازار به تفکیک صنعت | [SepratedByIndustry.aspx](https://ifb.ir/SepratedByIndustry.aspx) | Industry values, symbol counts, constituent values/classification | Yes | None observed | Expand industries; full symbol table in HTML | HTML, inline numeric array, form Excel export | TSETMC symbol cap history is a different source/universe | GET 200 | P1 | Implement aggregate and full constituent snapshots |
| Supplied industry URL | [SeparatedByIndustry.aspx](https://ifb.ir/SeparatedByIndustry.aspx) | Unverified at this spelling | Unknown | Unknown | Unknown | Empty response | None | GET 404 | Blocked | Use the differently spelled destination actually linked by IFB |
| ارزش بازار به تفکیک بازار | [GroupByMarket.aspx](https://ifb.ir/DataReporter/GroupByMarket.aspx) | Market totals, symbol counts, shares; three historical classification regimes | Yes | Official CSV exports, 1393-07-14..1405-08-17 observed | Three separate grid pagers/exports; no active date filter | HTML, CSV despite Excel icons | No IFB aggregate history API | GET/three POST exports 200 | P1 | Implement source snapshot and all three historical exports |
| ارزش بازار به تفکیک نماد / نقشه بازار | [MarketMap.aspx](https://ifb.ir/DataReporter/MarketMap.aspx) | Symbol closing price/change, selected volume/value/count/market value | Yes | None observed | Radio metric 1/2/3/4; chart uses only first 100, table all returned records | AJAX JSON | TSETMC map helper is private and extracts IDs only; quote APIs and new IFB symbol values overlap | HTML 200; strict-JSON POST 500, later exact published body POST 200 | P2 | Source behavior/coverage follow-up; industry drill-down already provides selected symbol values |
| دیدبان بازار | [StockQoute.aspx](https://ifb.ir/StockQoute.aspx) | Equity/debt/ETF/housing/options/futures quotes and bid/ask levels | Intended | None observed | Market checkboxes, symbol/column filters and sorting; block/major selector | Empty HTML grid, SignalR, form export | TSETMC constituents/quotes overlap, but IFB market classification may add value | HTML/scripts 200; live hub not independently validated | P2 | Investigate snapshot completeness before adding another watch |
| دیدبان بازار اوراق مشتقه | [OptionStockQuote.aspx](https://ifb.ir/OptionStockQuote.aspx) | Derivative universe/contract fields not independently verified | Unknown | Unknown | Unknown for this page | Unknown; shared script has option hub startup | Options already has IFB watch, chain, underlying and history | Repeated local read timeouts (20–30 s); web fetch also failed | Blocked | Keep Options API; do not guess an IFB derivative endpoint |
| شاخص کل فرابورس ایران | [IFBindex.aspx#TotalDiv_tab](https://ifb.ir/IFBindex.aspx#TotalDiv_tab) | Total index level/history/intraday comparisons | Yes | Existing history endpoint | Chart ranges; no new historical selector found | AJAX JSON/chart | IFB total history, TSETMC index histories/status/intraday | HTML 200; source requests inspected | P3 | Retain existing API; separate error/completeness hardening |
| شاخص کل هم وزن فرابورس ایران | [IFBindex.aspx#TotalSameWeightDiv_tab](https://ifb.ir/IFBindex.aspx#TotalSameWeightDiv_tab) | Equal-weight total index | Yes | Existing history endpoint | Chart range | AJAX JSON | Existing IFB/TSETMC APIs | HTML 200 | P3 | No duplicate function |
| شاخص قیمت فرابورس ایران | [IFBindex.aspx#PriceDiv_tab](https://ifb.ir/IFBindex.aspx#PriceDiv_tab) | Price index | Yes | Existing history endpoint | Chart range | AJAX JSON | Existing IFB API | HTML 200 | P3 | No duplicate function |
| شاخص قیمت هم وزن فرابورس ایران | [IFBindex.aspx#SameWeightPriceDiv_tab](https://ifb.ir/IFBindex.aspx#SameWeightPriceDiv_tab) | Equal-weight price index | Yes | Existing history endpoint | Chart range | AJAX JSON | Existing IFB API | HTML 200 | P3 | No duplicate function |
| شاخص کل صکوک فرابورس ایران (Sindex) | [SukukIndex.aspx](https://ifb.ir/SukukIndex.aspx) | Sukuk index display | Yes | Existing IFB weighted-index history; current page inspected separately | No active date input | AJAX JSON | Existing IFB sukuk index function | HTML 200 | P3 | No new history API; revalidate old endpoint before future hardening |
| گزارش‌های دوره‌ای | [periodicalreport.aspx](https://ifb.ir/datareporter/periodicalreport.aspx) | Report catalog with reporting/upload dates and per-report files | Catalog | Archive paged; earliest date not established | Date bounds, title, type (1/2/5), period (10/20/30/40), breakdown checkboxes; 10/25/50 rows | WebForms HTML, visible PDF/Excel links (hidden Word links also exist) | Missing | GET 200; default first page checked | P2 | Catalog/structured report follow-up; do not label first page complete history |
| آمار معاملات روزانه اوراق مالی اسلامی | [DailySukukTrades.aspx](https://ifb.ir/datareporter/DailySukukTrades.aspx) | Buyer/seller sectors and open-market/government-subscription categories | Latest rows | Dated paged observations | Separate grids, 10/25/50 and exports | WebForms HTML, charts, Excel buttons | Both existing IFB sukuk functions | GET 200, latest displayed 1405-08-16 | P3 | Improve existing completeness/error handling separately |
| محاسبه بازده اوراق | [YTM.aspx](https://ifb.ir/YTM.aspx) | Coupon/discount-bond yield tables, calculator, dated yield history | Yes | Dated YTM grid; default 1405-07-16..1405-08-17, earliest unverified | Symbol, price, valuation date; history symbol/date bounds, 25/50/100, export | WebForms HTML | Existing bond snapshots/risk-free estimate; history missing | GET 200 | P2 | Historical YTM follow-up with dates, coupon treatment and full-export validation |
| منحنی بازده اوراق با درآمد ثابت | [NelsonIndex.aspx](https://ifb.ir/NelsonIndex.aspx) | Government/treasury/non-government fitted curves and bond observations | Yes | Relative comparison curves, not demonstrated arbitrary daily history | Tenor nodes, categories | AJAX JSON | Bond snapshots overlap; fitted curves/duration/convexity missing | HTML and government curve/observation POSTs 200 | P2 | Verify yield/settlement units and observation provenance before API |
| ماشین حساب ارزش‌گذاری اختیار معامله | [OptionCalculation.aspx](https://ifb.ir/OptionCalculation.aspx) | BSM/IV calculator, contract chooser | Calculator | None established | Side, spot, strike, tenor, rate, volatility/option price | WebForms/JSON | Existing Options analytics | GET 200 | P3 | Do not add calculator-generated values as published observations |
| مطالعات و پژوهش‌ها | [RnD.aspx](https://ifb.ir/RnD.aspx) | Research documents with reporting period, preparation/upload dates, author and code | Documents | Displayed report list, earliest boundary unverified | Document links | HTML, 112 displayed report rows | No tabular financial API | GET 200 | P3 | Document catalog has lower priority than numeric datasets |
| افزایش سرمایه در جریان | [Issuers.aspx?id=2](https://ifb.ir/Issuers.aspx?id=2) | Approval, amounts, funding components, rights deadlines | Yes | Displayed event list | WebForms display | HTML, 424 data rows observed | TSETMC adjustment/share changes overlap, different legal-event evidence | GET 200 | P2 | Event/units/issuer-identity investigation |
| وضعیت شفافیت اطلاعاتی ناشران | [IFBSymbolState.aspx](https://ifb.ir/IFBSymbolState.aspx) | Issuer state, effective date, message/reason | Yes | Displayed dated list, coverage unverified | No active filter seen | HTML, 15 data rows | TSETMC supervision overlaps partially | GET 200 | P2 | Verify status definitions and universe |
| تاریخچه اطلاعات مالی ناشران فرابورسی | [IssuersReport.aspx](https://ifb.ir/DataReporter/IssuersReport.aspx) | Issuer EPS and P/L archive UI | Intended | UI date inputs; actual coverage unverified | Symbols, markets, fiscal date, report period, date bounds | HTML/client ASMX requests | No equivalent verified IFB API | HTML and IssuersReportScript.js 200; data calls not live-tested | P2 | Validate EPS/capital-adjustment/accounting-period semantics first |
| فهرست اطلاعات بازارگردانی | [MarketMakingMenu.aspx](https://ifb.ir/MarketMaker/MarketMakingMenu.aspx) | Links to three public subpages below | Menu | Not established | Three public sublinks | HTML | Financing details contain some market-maker metadata | Menu 200 | P2 | Keep one coherent investigation of parameters/effective dates |
| فهرست بازارگردانی‌های مبتنی بر حراج | [MarketMakingAuctionBasedList.aspx](https://ifb.ir/MarketMaker/MarketMakingAuctionBasedList.aspx) | Market-maker names, start/end, quote spread, minimum orders/daily trading, term/status | Yes | Dated contracts; full coverage unverified | WebForms paged grid | HTML, 25 displayed records | Partial financing metadata overlap | GET 200 | P2 | Verify commitments, units and full export/pagination |
| پارامترهای بازارگردانی / طبقات نقدشوندگی | [LiquidityClasses.aspx](https://ifb.ir/MarketMaker/LiquidityClasses.aspx) | Liquidity classes, order/trading minima, percentage quote range and effective dates | Yes | Validity intervals, not demonstrated archive | First/second, base and fund tables | HTML, 463/185/129 displayed data rows | Missing distinct parameters | GET 200 | P2 | Useful dated metadata; verify quantity bases and update semantics |
| وضعیت بازارگردانی نمادها | [SymbolsMarketMakerStatus.aspx](https://ifb.ir/MarketMaker/SymbolsMarketMakerStatus.aspx) | Symbol market-maker status | Yes | Not established | WebForms paged grid | HTML, 25 displayed records | Partial metadata overlap | GET 200 | P2 | Define status semantics and complete universe |
| فهرست عرضه‌های اولیه | [IPO.aspx](https://ifb.ir/datareporter/IPO.aspx) | IPO dates, method, price, volume/value, shares | Catalog | Paged historical offerings | Symbol, method, market, dates, 10/25/50, export | WebForms HTML | Missing distinct IPO catalog | GET 200 | P2 | Useful next group; verify full export and financial units |
| فهرست اوراق بهادار پذیره‌نویسی شده | [AllUnderWrited.aspx](https://ifb.ir/ThirdMarket/AllUnderWrited.aspx) | Subscription period, securities/amount, issuer type/industry, documents | Catalog | Paged dated offerings | Symbol, issuer, instrument type, dates, 10/25/50, export | WebForms HTML | Financing instruments overlap partially | GET 200 | P2 | Verify issue identity and amount/quantity units |
| فهرست نمادهای متوقف | [SuspendedSymbols.aspx](https://ifb.ir/DataReporter/SuspendedSymbols.aspx) | Suspension/correction date and reason | Yes | Displayed paged list, not complete status history | Symbol, market, company, date bounds, 50/100/150 | WebForms HTML | TSETMC supervision/status partly overlaps | GET 200 | P2 | Define current-vs-event semantics first |
| فهرست نمادهای حذف شده | [AllDeletedSymbol.aspx](https://ifb.ir/AllDeletedSymbol.aspx) | Deleted symbols, market, date | Catalog | Paged dated records | Symbol, 10/25/50 | WebForms HTML | Historical symbol identity partially overlaps | GET 200 | P2 | Validate delisting vs matured debt coverage |
| انتقال بین بازارهای اول، دوم، نوآفرین و پایه | [Issuers.aspx?id=5](https://ifb.ir/Issuers.aspx?id=5) | From/to market, event date, notes | Catalog | Displayed dated events | WebForms display | HTML, 91 data rows observed | No dedicated transition API | GET 200 | P2 | Valuable market-regime/identity follow-up |
| شرکت‌های انتقالی به بورس تهران | [Issuers.aspx?id=3](https://ifb.ir/Issuers.aspx?id=3) | Last IFB trade/date/value and notes | Catalog | Dated events | WebForms display | HTML, 32 data rows | TSETMC history overlap, transition semantics missing | GET 200 | P2 | Combine transition investigation |
| شرکت‌های انتقالی از بورس تهران | [Issuers.aspx?id=6](https://ifb.ir/Issuers.aspx?id=6) | Industry, first trade date, capital | Catalog | Dated events | WebForms display | HTML, 83 data rows | Same partial overlap | GET 200 | P2 | Keep nominal capital distinct from market value |
| حاکمیت شرکتی ناشران | [PublisherCorporateGovernaceScore.aspx](https://ifb.ir/PublisherCorporateGovernaceScore.aspx) | Issuer governance scores | Yes | Unverified | Export button | HTML, 372 table rows | Missing | GET 200 | P2 | Verify scoring period/version and export completeness |

## Observed request contracts and limitations

- Snapshot industry/market pages: ordinary GET, no parameters or special headers,
  HTTP 200 UTF-8 HTML, no redirects observed. No snapshot date selector. Industry
  `ContentPlaceHolder1_tblContainer` includes all hidden-by-CSS `grpData` rows;
  each has ticker/link, name, exact value in `td[title]`, market, industry and
  subindustry. `indArray.push([industry, value, count])` is the full 49-industry
  array, before the chart folds everything after eight industries into “Other”.
  Parse literal data without executing JavaScript, and cross-check constituent
  counts. The market page has a four-column source table and total row; exact
  values are in title attributes. Counts mean **symbols**, not unique companies.
- History: GET `GroupByMarket.aspx`, then ordinary URL-encoded POST to the same
  page with its hidden form fields and one observed submit control:
  `ctl00$ContentPlaceHolder1$btnExportExcelAfterPayecolored`,
  `ctl00$ContentPlaceHolder1$Button1`, or
  `ctl00$ContentPlaceHolder1$btnExportExcel`. Cookies/viewstate belong to that
  session. Each returns HTTP 200 `text/csv; charset=utf-8`, attachment
  `valuehistory.csv`, not an XLSX workbook. No row pagination is needed when
  consuming these whole-file exports. The UI grids display only ten rows.
  Do not substitute those ten rows for complete export history.
- Observed export coverage: colored base **1,783** rows,
  1398-06-25..1405-08-17; letter base **602** records,
  1395-12-23..1398-06-24 (601 unique dates); legacy base **592** rows,
  1393-07-14..1395-12-22. One identical 1396-08-15 record is repeated; early
  letter-era total and J-base values are blank. Preserve missing observations.
  Export rows have an extra empty trailing CSV field. Colored CSV headers still
  say `Paye A/B/J`; the actual colored HTML grid explicitly says yellow/orange/red.
  Do not join those classifications into a continuous interchangeable series.
- Exact integer export values can differ by a few rials from HTML title values
  (e.g. current total 72,293,218,830,987,337 in CSV vs
  72,293,218,830,987,300 in the table). Industry totals sum to
  72,879,714,295,212,325 in the array vs 72,879,714,295,212,336 in constituent
  titles. Market totals describe 1,125 symbols; industry describes 1,177.
  These are provider discrepancies/coverage differences, not evidence for
  silently recomputing published totals. Neither is free-float capitalization.
- Market snapshot values are explicitly labelled rial. These totals include
  debt and funds; call the measure `MarketValue`, not uniformly equity company
  capitalization. Counts, values, contributions and trade values are separate.
  The generic `lbldt` label contains weekday/month/day/time without year and is
  not a verified per-dataset valuation timestamp. Preserve it as a display label;
  do not invent a full observation date from the computer clock.
- Market map: initial POST `/DataReporter/MarketMap.aspx/getData`, strict JSON
  `{"type":4}`, `Content-Type: application/json; charset=utf-8`, returned 500.
  A later request with the page's exact published body `{type:4}` returned 200
  and `d` records; this does not isolate the cause of the earlier 500. The first
  result must not be reported as permanent provider inaccessibility.
  Source code maps 1=volume, 2=trade value, 3=count, 4=market value and expects
  `d` records with `id,label,title,market,close,data,value,ptoe,eps`; `data` is
  closing percentage change, not historical observations. Values can use
  scientific notation. No alternate endpoint guessed.
- Market watch: referenced `StockPageCore.js`, `HubPreRequisite.js` and
  `/signalr/hubs` all returned 200. Published client calls `myhub.letsStart`
  and `letsStartForOption`; the HTTP GET grid is empty until hub callbacks.
  It is not a valid empty-market snapshot. No SignalR dependency added to fima.
- Index source HTML uses POST JSON requests to
  `HistoricalInstrumentData.asmx/getIndexHistory`,
  `getTotalSameWeightIndexHistory`, `getPriceIndexHistory` and
  `getSameWeightPriceIndexHistory`, body `{}`. Existing IFB functions already
  parse `[timestamp_ms, value]` in `d`; the sukuk function uses
  `GetWeightedIndexHistory` with nested `d`. The current Sukuk page separately
  references `GetLastSukukIndexValue`. No new index universe/constituents was
  established from these pages; TSETMC already exposes constituents.
- Nelson page: observed POST JSON content type, no body, to
  `GetGovermentNelsonIndex` and `GetGovermentNelsonSymbolData` under the same ASMX
  path returned 200. Curve `d` has relative-date series of `Date,EnDate,DayNum,Value`;
  relative “current/month/year” labels do not establish daily history. Bond
  records include observation/market/maturity dates, `yieldValue`, `SettlePrice`,
  `AccruedInterest`, duration/convexity and `IsTodayMarket`. Source also references
  `GetITBtNelsonIndex`, `GetITBNelsonSymbolData`, `GetNonGovermentNelsonIndex`,
  `GetNonGovermentNelsonSymbolData`, `GeytNelsonAvg`; these were not live-tested.
  Settlement-price scaling still needs verification; do not infer it from YTM.
- Periodical catalog: source file links use GET
  `/GetFiles/GetPeriodicalFile.aspx?id=27713&type=Excel&EnData=False`
  (and PDF). Individual reports and oldest archive boundary were not downloaded.
  Dates distinguish report period end (1405-08-16) from upload (1405-08-17).
  Other WebForms lists above show controls/pagers in source; their filtered POSTs
  and full historical exports are follow-up work, not claimed verified APIs.
- `IssuersReportScript.js` uses POST JSON through `getWebsiteDetails` to
  `HistoricalInstrumentData.asmx/GetIssuersArchiveEPS` (symbol/market/fiscal-date
  arrays and date bounds) and `GetIssuersArchivePL` (also period array).
  Their live schemas, fiscal calendars and historical coverage were not verified.

## Existing API comparison and selection

Baseline is master `94a3a16589ec778794675a6de5eb7770450c6768` (version 0.13.2).
All 15 IFB public functions and top-level exports were inspected. They cover five
index histories; two sukuk category tables; coupon/noncoupon yield tables and a
scalar treasury-yield proxy; standard/special financing lists and instrument
details/payments; crowdfunding plans/platforms. They do not expose aggregate
market values, the industry constituent universe, or market-value history.
Legacy failure handling is inconsistent: index failures can become empty tables,
bond failures can print/return None, and some pagers stop on repeats. This batch
must not reuse those silent-completeness behaviors or refactor unrelated APIs.

`Options.download_market_watch(market="IFB")` already returns paired or vertical
contracts with IDs, underlyings, strike/expiry, Call/Put type, quotes, volume/value,
bid/ask and open positions. `download_chain_contracts`, `ticker_info`,
`download_all_underlying_assets` and `download_historical_data` cover the related
analytical needs. A timed-out IFB derivative page is insufficient justification
for duplicating these functions or asserting identical coverage.

TSETMC exposes symbol histories, `get_ticker_historical_market_caps` (closing
price times historical shares), IFB ticker lists, index histories/status/intraday
and index-company quotes/optional thirty-day closing history. Its private market
map helper extracts identity only. Those functions do not reproduce IFB's
official aggregate market-regime history or source industry breakdown.

Select one coherent P1 group with three public functions: source aggregate
snapshots with an industry/market selector; full symbol drill-down with exact
filters; and historical market-value CSV exports with both calendar inputs.
Use the provider's available export archive, not reconstructed snapshot history.
Keep derivatives, yield history/curves, report extraction and event catalogs as
separate P2 investigations. Follow-ups with concrete evidence requirements:
[yield history/curves #120](https://github.com/hemoboghosian/fima/issues/120),
[report catalog #121](https://github.com/hemoboghosian/fima/issues/121), and
[watch/map coverage #122](https://github.com/hemoboghosian/fima/issues/122).
Next after those: IPO/subscription catalogs, market-transition events and dated
market-maker parameters. The matrix records their evidence and missing checks;
none is presented as an implemented API.
