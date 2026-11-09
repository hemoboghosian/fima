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

## Issue #120 fixed-income investigation — 2026-11-08

This follow-up starts from `edf02f0`, with 760 deterministic tests passing.
YTM/Nelson are ordinary public HTTPS sources; one initial YTM timeout recovered
on a bounded retry. Existing bond snapshots and the decimal scalar risk-free
estimate remain separate, unchanged APIs.

| Candidate | Verified source/request | Snapshot/history and filters | Units | Overlap | Completeness/evidence | Uncertainty and decision |
| --- | --- | --- | --- | --- | --- | --- |
| Historical bond YTM | GET/POST `YTM.aspx`; `Button1` filter then `btnYTMHistoryExport` | History; explicit inclusive dates and selected IFB instrument ID | Closing price rials, volume securities, YTM effective annual percentage points | Existing bond APIs are snapshots | Whole HTML-table `.xls` export, not the 25-row grid; default 689 records; broad export 29,663 records, 1401-10-26..1405-08-16 | Implement selected verified instruments; reject ambiguous ticker labels and conflicting dates by default; explicit preserve mode flags conflicts |
| Official fitted nodes | POST referenced `GetGovermentNelsonIndex`, `GetITBtNelsonIndex`, `GetNonGovermentNelsonIndex` ASMX methods, no body | Comparison snapshot, categories government/treasury/nongovernment | Tenor days, published YTM percentage points | No previous fitted-node API | All returned 200; 42/37/53 nodes across three relative comparison series | Implement `get_ifb_yield_curve` as a separate focused feature; no arbitrary-date archive, calibration dates, parameters or refitting inferred |
| Nelson bond scatter observations | POST corresponding `GetGovermentNelsonSymbolData`, `GetITBNelsonSymbolData`, `GetNonGovermentNelsonSymbolData` | Dated current/stale quoted instruments | Yield points verified; price/accrual scaling not fully established | Existing yield snapshots overlap | All returned 200, with 153/16/339 observations; source distinguishes `IsTodayMarket` | Exclude interpreted settlement/accrued-interest, duration/convexity and contributor APIs pending financial verification |

History filter names are `ctl00$ContentPlaceHolder1$SymbolComboboxYTMHistory`,
`TxtDateFrom`, `TxtDateTo`, and submit `Button1` under the same prefix. Both
dates are required: blank bounds produce `ContentPlaceHolder1_lblerror` and
must not be mistaken for an unfiltered archive. Preserve current form fields,
hidden viewstate and the session between requests. The export submit is
`ctl00$ContentPlaceHolder1$btnYTMHistoryExport`. HTTP 200 with
`application/vnd.ms-excel; charset=utf-8`, filename `YTMHistory.xls`, contains
one complete seven-column HTML table, not a binary XLS or XLSX workbook.
It omits IDs; attach an ID only after resolving a unique official selector
option and validating the filtered grid's instrument links and export ticker.
The selector contains duplicate `اراد157` labels for IDs `33136` and `33302`.
Some historical export labels are absent from the current selector; an
all-instrument ID reconstruction is therefore not justified.

Broad all-instrument evidence: 784 exported ticker labels, 29,663 source records,
3,492 identical repeats, and 21 conflicting ticker/trade/issue/maturity keys.
This establishes the observed **provider archive**, not uninterrupted market
history. Selected treasury `33029` exported 456 records in a broad window,
starting 1403-06-05; repeated 1403-11-23 records contain closes 574,190/576,910
and yields 33.60/33.27. An exact one-day filter reproduced both. Do not choose a
revision arbitrarily. Normalize identical repeats with provenance; default
conflicts to errors and permit explicitly requested flagged source records.
A valid no-trading-date filter displays `.داده ای یافت نشد`; its export returns
the whole normal page rather than a download. Return a typed empty result from
the validated filtered grid without pretending that page is an Excel export.

Financial validation uses the linked official
[YTM/YTC definition](https://ifb.ir/Files/MFI/%D9%85%D8%B9%D8%B1%D9%81%D9%8A%20%D9%86%D8%B1%D8%AE%20%D8%A8%D8%A7%D8%B2%D8%AF%D9%87.pdf)
and [worked examples](https://ifb.ir/Files/MFI/YTM%20vs%20YTC.pdf), including visual
inspection of their zero-coupon and dated-cash-flow formulas. YTM is an
effective annual yield, distinct from nominal coupon, simple return and YTC.
Treasury [33029](https://ifb.ir/InstrumentsMFI.aspx?id=33029) verifies face value
1,000,000 rials, no coupon, maturity 1405-10-21. Close 937,500 on 1405-08-16
gives `(1000000 / 937500) ** (365 / 65) - 1 = 0.4367859`, matching 43.68%.
Coupon [40578](https://ifb.ir/Instruments.aspx?id=40578) verifies face 1,000,000,
nominal coupon 23%, quarterly dates and actual payment amounts. Discounting its
seven published cash flows (including principal) from 1404-10-22 at price
864,000 gives effective annual 39.93253%, matching 39.93%. The source labels the
historical date as last trade; it is not renamed settlement/valuation date, and
no universal clean/dirty-price or fee convention is inferred from these cases.

Nelson JavaScript labels the ordinate YTM and appends a percentage sign; tenor
nodes share the days axis used by individual remaining-maturity days. Current,
one-month-before and six-month-before labels are relative strings. They do not
give exact calibration dates. Published nodes are fitted theoretical YTMs, not
individual executed yields, zero-coupon spot rates or forward rates. Bond
scatter `Date` and `MarketDate` can differ substantially; stale observations are
explicitly separate. A treasury `SettlePrice` of 965.88 corresponds numerically
to a 965,880-rial quote, but that comparison alone does not establish a universal
price unit or clean/dirty definition. No such conversion is authorized here.

The fitted-node API exposes only the verified category, source comparison labels,
tenor days and original YTM values. It validates the three comparison series and
each node without manufacturing observation dates. Interpreted scatter prices,
accruals, duration/convexity and contributor/calibration provenance remain in
[follow-up #125](https://github.com/hemoboghosian/fima/issues/125).

## Issue #121 periodical-report investigation — 2026-11-09

Baseline: clean `c296248`, equal to freshly fetched origin/master; 823
deterministic tests passed. Existing IFB exports/helpers, Options and TSETMC
APIs expose neither this catalog nor its report identities. Scope is one
additive catalog function; no generic report parser or financial series.

| Candidate | Verified evidence | Completeness/semantics | Decision |
| --- | --- | --- | --- |
| Report catalog | Public GET and ordinary WebForms POST to [periodicalreport.aspx](https://ifb.ir/datareporter/periodicalreport.aspx), UTF-8 HTML 200; hidden viewstate and same-session cookies | Explicit reporting-period-end filters, sequential 50-row pages, advertised last page, two matching traversals of all IDs/records/pager metadata | Implement `get_ifb_periodical_reports`; fail rather than return partial/changed results |
| Visible Excel/PDF links | Eight representative GETs returned 200, no redirects; four real XLSX and four PDF files | Visible links identify a report, not an immutable file version; hidden Word links do not establish availability | Return visible validated-structure HTTPS links; no individual downloader in this focused batch |
| Heterogeneous financial contents | Daily/monthly one-sheet tables; weekly 16 and annual 42 sheets with formulas/hidden sheets; units and percentage storage differ | Requires family/table-specific units, revision and formula-error decisions; no universal frame or inferred historical series | Defer to [#127](https://github.com/hemoboghosian/fima/issues/127) |

### Source request and filter contract

The initial GET has no query parameters and no redirects observed. POST to the
same URL retains current `__VIEWSTATE`, `__VIEWSTATEGENERATOR` and any other
published hidden fields in the same session. Controls have prefix
`ctl00$ContentPlaceHolder1$`:

- `FromDT`, `ToDT`: slash-form Jalali bounds; single-date 1405/08/16 returns
  IDs 27713/27714, **uploaded 1405/08/17**. A 1405/08/17-only filter is explicitly
  empty. Thus dates filter منتهی به / period end, not upload dates.
- `comboReportType`: 0 all, 1 آمار معاملات (trading statistics), 2 گزارش آماری
  توصیفی (descriptive statistics), 5 رتبه‌بندی (ranking).
- `comboReportPeriod`: 0 all, 10 روزانه (daily), 20 هفتگی (weekly), 30 ماهانه
  (monthly), 40 سالانه (annual).
- `txtTitle`: at most 40 characters. The قیمت search returned 11 matching
  descriptions in 1405/08/01..1405/08/17. Preserve source matching semantics.
- `TafkikCheckboxlist$0..6`: values 1/2/4/8/16/32/64 mean market, industry,
  symbol, institutional/individual, buy/sell, online/station and broker. A single
  industry filter returned the three weekly descriptions in that recent window;
  combinations' AND/OR behavior is not exposed by the API.
- `BtnSearch` submits جستجو. The visible page-size select supports 10/25/50;
  changing its value to 50 during search works. Its control name is dynamic,
  e.g. `grdPRs$ctl13$ctl10`, and is read from each current form, not hardcoded.
- Pagination posts `__EVENTTARGET=ctl00$ContentPlaceHolder1$grdPRs` and
  `__EVENTARGUMENT=Page$N`, using the actual advertised link. Row numbers continue
  across pages; page 2 differs from page 1, filters persist, and revisiting page 1
  reproduced its IDs. Numbered blocks use an ellipsis link to the next block.

The source table `ContentPlaceHolder1_grdPRs` has exactly eight headings: row,
report type, reporting period, period end, breakdown, upload date, description,
file. No period-start date or exact upload timestamp is supplied. Report ID is
from visible file links; identity must agree across a row's formats. Titles and
period dates are not unique IDs or authoritative revision indicators. Upload can
precede period end (e.g. annual 1403/12/30 uploaded 1403/12/28); preserve this.

### Coverage and completeness boundary

All 36 annual reports fit on one 50-row page, with observed period ends
**1388-12-29..1404-12-29**. Latest catalog observations on the investigation date
end **1405-08-16**, uploaded **1405-08-17**. The 1405/07/01..1405/08/17 query has
eight pages at 10 rows, two at 50. Live tests independently compared **every**
returned ID, end/upload date and visible format to all raw pages in both the
recent and annual queries; valid empty searches were separately verified.

No independent total-record count or full-catalog export was found. The
unfiltered all-frequency catalog was not aggressively enumerated, so its total
population and absolute earliest boundary are **not claimed**. Further boundary
queries encountered TLS handshake timeouts; they do not prove absent data.
The oldest annual observation is an observed coverage fact, not proof that no
older report in another category exists.

The API requires two explicit inclusive bounds and 50-row source pages, with
`max_pages=20` (user-selectable 1..100) per pass. It follows every consecutive
advertised page to the verified terminal page, then repeats the whole search.
Rows, IDs, ordering, filters, schema and pager topology must match. Count changes,
duplicate IDs, repeated/missing pages, unknown schemas and limit exhaustion fail;
no title deduplication or partially accumulated data is returned. The explicit
`.داده ای یافت نشد` grid must repeat in both passes to yield typed empty output.
This provides complete matching **filtered** traversals, not a provider atomic
snapshot, every report ever published, or immutable file-version guarantees.

Initial catalog/file connection attempts sometimes timed out during TLS
handshakes. Ordinary verified HTTPS later succeeded for the live tests and all
eight downloads; no access-denial/rate-limit response, bypass or TLS weakening
was used. The library keeps 30/30-second finite timeouts, one connect/transient
502/503/504 retry, no read/access-denial retry, sequential requests and 0.25-second
pauses before POSTs. Deterministic CI does not depend on IFB availability.

### Representative files and financial checks

Actual GET pattern (each visible source link):
`https://ifb.ir/GetFiles/GetPeriodicalFile.aspx?id=<ID>&type=Excel|PDF&EnData=False`.
All eight responses were 200, no redirects, with attachment Content-Disposition
and matching content length. Excel MIME was
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`; ZIP integrity,
OpenXML workbook/relationships/worksheets confirmed XLSX. PDFs had
`application/pdf`, `%PDF-` signatures and parsed page counts. Relevant PDF pages
were rendered and visually checked. No original files/binaries are committed.

| Frequency / ID | Period end / upload | Attachment filenames (URL-encoded spaces retained) | XLSX bytes / sheets | PDF bytes / pages |
| --- | --- | --- | --- | --- |
| Daily 27713 | 1405-08-16 / 1405-08-17 | `1405.08.16%20H&H.xlsx`, `.pdf` | 179,191 / 1 | 1,252,972 / 8 |
| Weekly 27709 | 1405-08-15 / 1405-08-16 | `Weekly_Report_Ended_to-1405.08.15.xlsx`, `.pdf` | 380,479 / 16 | 582,340 / 9 |
| Monthly 27712 | 1405-07-30 / 1405-08-16 | `1405.07%20H&H.xlsx`, `.pdf` | 319,742 / 1 | 4,071,468 / 13 |
| Annual 27339 | 1404-12-29 / 1405-01-23 | `Annual_Report_Ended_to-1404.xlsx`, `.pdf` | 746,808 / 42 | 1,644,582 / 33 |

Daily/monthly sheet `حقيقي و حقوقي` has multirow buy/sell, institutional/individual,
buyer/seller headers and distinct person counts, transaction counts, volume and
value columns. Daily dates B7/B8 are 14050816; monthly 14050701..14050730. These
starts are file-specific evidence and **not manufactured catalog columns**.
Daily row 17 buy volumes 74,660 + 27,695 = 102,355; corresponding values
72,568,863,630 + 26,893,760,410 = 99,462,624,040. Monthly row 17 buy-component
checks also reconcile, with total volume 439,349 and value 436,104,018,190.
Representative exact XLSX figures agree independently with the corresponding
PDF tables. Generic ارزش headers do not establish one universal monetary scale;
no magnitude-based conversion is inferred.

Weekly `نمودار شاخص و ارزش بازار` C19 is 71,760,956.665573299 **billion rials**;
PDF page 3 displays 71,760,957, while its chart uses thousand-billion rials.
E18 stores a fractional change 0.0094814627607031597, displayed as 0.9%; F18/F19
contain original `#REF!` formulas. These must not be silently repaired or treated
as valid observations. Annual `خلاصه عملکرد و تعداد نماد` D7 is
37,654,931.941141002 billion-rial market value, D9 is 492,454,069.08229798
billion-rial **trade value**, D10 is 3,520,784.5670420001 **million securities**;
PDF page 3 displays their separately rounded figures. D18's 1,073 means symbols,
not unique companies. Annual F7 computes `((D7-E7)/E7)*100` in percentage points,
unlike weekly fractional storage. Turnover's annual source footnote excludes
open-market operations; no uniform turnover interpretation is exposed here.

Worksheet inventories (including hidden sheets, preserving source names):

- Daily/monthly: `حقيقي و حقوقي` only.
- Weekly visible: `جلد`, `Contents`, `نمودار شاخص و ارزش بازار`,
  `آمار معاملات بازار در یک نگاه_x0009__x0009_` (OpenXML escaped tabs),
  `آمار معاملات به تفکیک ابزار  `, `معاملات بازار پایه`, `صنایع پیشرو بازار سهام`,
  `ارزش بازاربه تفکیک صنعت`, `ارزش بازار به تفکیک بازار`.
  Hidden: `نمودار سهم ارزش و حجم معاملات`, `معاملات سهام`, `معاملات اوراق م.اسلامی`,
  `معاملات صندوق قابل معامله`, `معاملات ابزار مشتقه`, `معاملات اوراق مسکن`,
  `معاملات بازار ابزار نوین مالی`.
- Annual visible: `جلد`, `فهرست`, `خلاصه عملکرد و تعداد نماد`,
  `نمودار شاخص و ارزش بازار`, `نمودار ارزش و حجم معاملات`, `معاملات ماهانه`,
  `نمودار شاخص و ارزش ماهانه`, `نمودارحجم وارزش ماهانه معاملات`, `معاملات کل بازارها`,
  `مقایسه ارزش‌وحجم به تفکیک بازار`, `معاملات بازارها به تفکیک ابزار`,
  `نمودارمعاملات بازارها-ابزار`, `ارزش بازار به تفکیک ابزار`, `ارزش بازار به تفکیک بازار`,
  `ارزش بازار-معاملات و نسبت گردش`, `مقایسه P.E  صنعت و بازار`,
  `کمترین و بیشترین P.E صنعت`, `سهام شناور آزاد-صنعت و بازار`,
  `مقایسه ارزش و حجم معاملات`, `صنایع پیشرو بازار سهام`, `ارزش بازار به تفکیک صنعت`,
  `نمودار ارزش و معاملات‌-صنعت`, `نمودار ارزش و حجم بازار اول`,
  `نمودار ارزش و حجم بازار دوم`, `معاملات بازار ابزار نوین-ابزار`,
  `نمودار ارزش و حجم ابزار نوین`, `نمودار ارزش و حجم بازار پایه`, `معاملات بازار توافقي`,
  `پذیره نویسی`, `عرضه اولیه`, `تامین مالی`, `عملکرد و تنوع تامین مالی`.
  Hidden: `سود سهام-صنعت`, `Sheet1`, `Sheet3`, `Sheet4`, `Sheet2`, `Sheet5`,
  `Sheet8`, `Sheet6`, `Sheet7`, `DPS`.

Four samples do not establish every legacy download format or revision contract.
Keep the initial change focused on discovery; do not add a universal downloader
or parser based only on current samples. Further family-specific extraction,
cached/error cells, units, legacy formats and revision provenance are in #127.
Other independent IFB work remains in #122 (watches) and #125 (Nelson semantics).
