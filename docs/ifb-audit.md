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
At the conclusion of #121, independent IFB work remained in #122 (watches) and
#125 (Nelson semantics). The subsequent #122 investigation is recorded below.

## Phase #122 market-map and watch investigation — 2026-11-09

Preflight reconfirmed clean `master`/`origin/master` at
`a858bacc2a0410cd23134fa3e8b5671195ec8a2d`, Python 3.10.11, consistent installed
dependencies and 878 passing deterministic tests (143 integration deselected).
Version remains 0.13.2. This section supersedes the earlier watch/map transport
uncertainties where new observations are explicitly recorded; earlier counts
remain dated observations.

### Ranked decisions before implementation

| Priority / candidate | Official source | Observed endpoint | Data fields | Snapshot/history | Coverage | Existing overlap | Financial verification | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 / market map | [MarketMap.aspx](https://ifb.ir/DataReporter/MarketMap.aspx) | Same-session page GET, POST `/DataReporter/MarketMap.aspx/getData` | IFB ID, ticker, title, market, selected measure, closing price/change, EPS, P/E | Current selected snapshot; no dates/history | Entire `d` table collection, not 100-chart subset; metric-dependent; no independent total | Industry symbol values add exact integer values and industry; TSETMC index quotes have selected constituents, not this IFB map classification/universe | All four metric responses verified; nonzero trading measures; ID/price checks below | **Implement** one parameterized API; small HTTP/JSON parser, no dependency or architecture change |
| 2 / general watch | [StockQoute.aspx](https://ifb.ir/StockQoute.aspx) | Published SignalR `/negotiate`, `/connect`, `/send`, `/poll`; `myhub.letsStart` | Quotes/trades, ISIN/IFB IDs/market numbers, five best-limit levels, NAV/YTM-related fields | Initial client state plus subsequent deltas; not verified history | 1,254 unique IDs in an actual initial callback; authoritative total, exclusions, timestamp and removal semantics unresolved | TSETMC index quotes/history; possible useful IFB-specific order-book/coverage gap | Actual initial payload and replacement/merge code verified; NAV date is not quote time; order-book ordering/refresh not independently established | **Investigate further**, [#129](https://github.com/hemoboghosian/fima/issues/129); marginal value does not justify a new protocol implementation before validation |
| 3 / derivatives watch | [OptionStockQuote.aspx](https://ifb.ir/OptionStockQuote.aspx) | Page GET repeatedly timed out locally; shared public hub proxy exposes `letsStartForOption` | Full page-specific initial payload and authoritative metadata not verified | Unresolved snapshot | Not established for this IFB page | Existing Options IFB watch/chains/history/metadata/analytics; live source returned 235 call/put pairs | Existing route has separate contract/underlying codes, side, strike, expiry, size, quote/trade/open-position and best-quote fields | **Blocked locally / no duplicate API**; recheck access and demonstrate a gap in #129 |

The market map ranks first for usefulness, bounded completeness, live correctness,
compatibility and low maintenance cost. A general streaming implementation has
greater state/protocol complexity and weaker independently verified boundaries.
No generic watch architecture, report parser, new dependency or historical data
synthesis was added. Existing IFB, Options, TSETMC and risk-free-rate behavior is
preserved.

### Actual market-map transport and financial fields

GET `https://ifb.ir/DataReporter/MarketMap.aspx` returned HTTP 200 UTF-8 HTML,
without redirects. Its four radio labels map 1 to حجم, 2 to ارزش, 3 to تعداد and
4 to ارزش بازار. The published jQuery call sends POST body `{type:N}` with
`Content-Type: application/json; charset=utf-8` to
`https://ifb.ir/DataReporter/MarketMap.aspx/getData`. Same-session requests for
all four metrics returned HTTP 200 JSON `{"d":[...]}` with exactly nine record
fields. The API follows that ordinary sequence, with finite timeouts and TLS
verification; it does not manipulate cookies or send WebForms postback state.

A fresh-session POST with the published body returned HTTP 500 and the generic
WebMethod `Message`/`StackTrace`/`ExceptionType` error envelope. After a GET in
the same session, **strict JSON also returned HTTP 200**. Therefore the earlier
strict-JSON versus unquoted-key discrepancy does not establish that quoting is
the cause. Page bootstrap/session initialization appears significant; the exact
server-side requirement is not independently established. There is no fallback
request format or access-control workaround in the implementation.

| Wire field | Verified meaning / unit | Boundary |
| --- | --- | --- |
| `id` | IFB website instrument ID; links to `/Instruments.aspx?id=...` | Not TSETMC `insCode`; duplicate tickers can identify distinct instruments |
| `label` / `title` | Source ticker / instrument name | Preserve suffixes and source naming |
| `market` | Source market classification | Varies between metrics; no industry field |
| `value`, type 1 | Trade volume in native instrument quantity | Not outstanding share count; may represent units/contracts |
| `value`, type 2 | Trade value in rials | Not market value; no implicit display B/M scaling |
| `value`, type 3 | Transaction count | Not instrument count |
| `value`, type 4 | Instrument market value in rials | Includes debt/funds; not equity-only capitalization |
| `close` | Closing price in rials | Not last trade |
| `data` | Closing-price percentage change, percentage points | Page appends `%`; do not infer scale from magnitude or clamp outliers |
| `eps` | Source EPS, rials per instrument unit | Period/accounting basis and zero/missing convention unverified |
| `ptoe` | Source P/E ratio | Source zero displayed `--`; negative P/E retained |

There is no last price, industry, observation date/time or historical filter.
The implementation exposes ten documented PascalCase columns, including a
verified detail URL; see [full contract](ifb.md#metric-selected-market-map-snapshot).
It returns signed nullable integer EPS, preserves EPS zero without asserting
zero earnings, and maps source P/E zero to missing as the page does. P/E is not
recomputed using another provider's EPS.

Scientific monetary tokens include `2.392420692E+15`. Current per-record values
were below `2**53`, but that does not establish exact underlying amounts for all
future records or values already rounded by the server. Monetary `MetricValue`
is decoded directly to `Decimal`; no binary-float conversion followed by an
exact-integer-rial claim is made. Decimal preserves serialized precision only.

### Universe and independent checks

- Earlier metrics 1/2/3 each returned the same 761 unique IDs and zero selected
  measures. Later each returned 750 unique IDs, seven source classifications,
  and 55 nonzero selected measures in the live tests. They included ETF, equity,
  options and housing categories. This change is preserved, not repaired.
- Metric 4 returned 1,177 unique IFB IDs and 1,176 tickers across 11 source
  classifications, including 499 fixed-income records and 192 ETF records.
  The ticker `وملل1` occurred at distinct IDs 43064 and 18006. Only part of the
  trading-metric universe overlaps; never join these as one atomic quote.
- The page loops over every `msg.d` record for its table, but explicitly sends
  `msg.d.slice(0,100)` to the treemap chart. No pagination or independent total
  is published. The API preserves the whole collection and rejects malformed
  JSON/rows/IDs. A syntactically valid shorter provider list cannot be detected
  against a nonexistent independent total. No whole-IFB claim is made.
- All 1,177 metric-4 IDs matched the existing industry-page constituents.
  1,176 amounts matched exactly; ID30276 differed (`327061867335392` versus
  `327108027546688`) across separate requests. Preserve provenance and timing
  differences rather than replacing one snapshot's value with the other.
- Actual SignalR records use `TotalTradeQuantity`, `TotalTradeValue`,
  `TradeCount`, `MarketValue`, `ClosingPrice`, `ClosingPercent` and `EPS` for
  common IFB IDs, confirming the page's financial field distinctions. Trading
  and closing values changed as ETFs began trading; EPS matched on all common
  IDs in that comparison. Metric-2 nonzero values, such as ETF کارا's
  1,913,510,973,547 rials, are distinct from volume 49,350,355 and its market
  value; no count/volume/value substitution is made.
- Official IFB detail ID18620 identifies بپاس as ISIN `IRO3BIPZ0001`.
  TSETMC's existing `Instrument/GetInstrumentInfo/51971068201094874` response
  has the same `instrumentID`; the IFB ID is not its numeric TSETMC code.
  TSETMC's existing IFB index-constituent endpoint
  `ClosingPrice/GetIndexCompany/43685683301327984` returned 247 records and
  بپاس closing 13,730 versus last 13,740, confirming the closing/last distinction.
  IFB EPS 1,221 differs from TSETMC `estimatedEPS` 668; no common earnings
  period/basis or interchangeable EPS series is asserted.

### SignalR, derivatives and source limitations

The current general page, `StockPageCore.js`, `HubPreRequisite.js`,
`jquery.signalR-1.2.2.min.js` and `/signalr/hubs` all returned 200. The generated
public proxy exposes `letsStart`, `letsStartForOption`, `letsStartForOragh` and
`AbzarNovinLetsStart`. Source inspection showed protocol 1.2.2 client behavior:
GET `/signalr/negotiate` with subscribed `connectionData`, GET `/signalr/connect`
with the longPolling fallback, POST `/signalr/send` with a form-encoded JSON hub
invocation, then GET `/signalr/poll`. The server advertised protocol `1.2`.
No guessed newer `clientProtocol` parameter or `/start` request was added.

One bounded legitimate session invoked `myhub.letsStart(connection.id)` and
received `updateSingleTable` with 1,254 unique instrument records and a separate
three-element aggregate array. The callback passes `symId=-1`, replacing client
`gridData`; later `updateRow` callbacks merge by `SymbolId`. Market-number and
block/major `SymbolNum` selectors filter the cumulative client state locally.
Thus an arbitrary streamed delta is not a full snapshot. Records include ISIN
and five `ThisBestLimits` levels; level-ordering, quote timestamp, refresh cadence,
removal/reconnect behavior and authoritative coverage remain unverified.
`NAVDate`/`NAVTime` must not be relabeled quote timestamps. The ordinary public
`/signalr/abort` cleanup returned 200. No connection token was committed.

`OptionStockQuote.aspx` repeatedly hit bounded 30-second read/TLS timeouts in
this local environment. Other IFB requests succeeded, and web fetches also
failed; this does not establish global outage or permanent blocking. The shared
client has separate option initial/update callbacks but no independently verified
full derivative initial payload was obtained. Existing Options' official
`Instrument/GetInstrumentOptionMarketWatch/2` returned 235 paired call/put records
with separate contract and underlying codes, strike, expiry, size, trade/price,
open-position and best bid/ask fields. No derivative ticker parsing or duplicate
API was introduced. Follow-up [#129](https://github.com/hemoboghosian/fima/issues/129)
records both the achieved protocol evidence and remaining acceptance criteria.

Independent roadmap: [#125](https://github.com/hemoboghosian/fima/issues/125)
still concerns Nelson **bond-observation** semantics, not the already implemented
official fitted comparison nodes; [#127](https://github.com/hemoboghosian/fima/issues/127)
concerns financial extraction from report contents, legacy formats and revisions,
not catalog completeness. Neither is solved or expanded by this snapshot API.

### Validation of the focused addition

Tests were added before the new module/API, initially failing collection for
the missing module. All 76 new deterministic cases pass. The full suite passes
954 deterministic tests with 147 integration tests deselected, including prior
IFB, Options and TSETMC regressions. Four opt-in live tests compare **every row**
with its same captured official response, avoiding cross-request timing claims.
The final run passed with 751 records and 57 nonzero measures for each of metrics
1–3, and 1,177 records/all nonzero market values for metric 4. These live counts
changed from the earlier run's 750/55; no fixed count is enforced.

Existing public `Options.download_market_watch(market="IFB", stack="Vertical",
j_date=False)` also succeeded with 470 rows: 235 calls and 235 puts, 29 columns.
`TSETMC.get_index_companies` for the officially identified IFB total index
succeeded with 247 rows; بپاس closing/last retained the verified distinction.
Those modules and the risk-free-rate implementation were not changed.

Wheel/sdist builds, strict Twine metadata checks, source-byte comparisons,
package privacy/file inventory, documentation links/anchors, and dependency
checks passed. A fresh offline-installed wheel in a neutral directory passed
307 relevant deterministic tests on Python 3.10 / pytest 8.3.5; all 77 public
callables imported and import-time HTTP was prohibited. Normal deterministic
CI remains independent of providers. Raw investigation dumps, connection state,
temporary scripts and built distributions are excluded from commits. No version
bump, tag, release, distribution upload or publication is part of this work.

## Phase #129: SignalR financial and lifecycle validation — 2026-11-09

**Decision: defer a new public watch/order-book API.** Repeatable initial state,
incremental records and a short same-cursor reconnect are now observed, but the
implementation gates in [#129](https://github.com/hemoboghosian/fima/issues/129)
remain unmet. This phase changes documentation only. The issue stays open for
the explicitly unresolved questions below; deferral does not resolve them.
Existing IFB, TSETMC, Options and risk-free-rate behavior is preserved.

### Baseline and current public sources

The clean local `master` and fetched `origin/master` both matched published
0.14.0 commit `9028225bcf986e054891c58da16186251a8d9cf5`. The existing
`v0.14.0` tag and GitHub Release target matched that commit. No competing open
PR existed at preflight. The deterministic baseline passed **954 tests**, with
147 integration tests deselected. The package version, dependencies, release
workflow and tags are outside this change.

Ordinary verified-TLS requests on 2026-11-09, approximately 06:42–06:58 UTC:

| Official source | Current evidence |
|---|---|
| [General watch](https://ifb.ir/StockQoute.aspx) | 200, no redirect, empty HTML client grid; references the sources below |
| [HubPreRequisite.js](https://ifb.ir/Scripts/Common/v_639036512577336099/HubPreRequisite.js) | 200; general and derivative hub callbacks/start invocations |
| [SignalR 1.2.2 client](https://ifb.ir/Scripts/Common/v_638922376656000133/jquery.signalR-1.2.2.min.js) | 200; actual longPolling URL, cursor, reconnect, delay and abort behavior |
| [Generated hub proxy](https://ifb.ir/signalr/hubs) | 200; `myhub` and its published server methods |
| [StockPageCore.js](https://ifb.ir/Scripts/v_638922376581346876/StockPageCore.js) | 200; identity links, source EPS/P-E rendering and financial column bindings |
| [Derivatives watch](https://ifb.ir/OptionStockQuote.aspx) | Two bounded 30-second GET read timeouts locally; no successful page response, redirect, denial or global-outage conclusion |
| [IFB detail: بپاس](https://ifb.ir/Instruments.aspx?id=18620) | 200; exact ISIN, name, mnemonic and second-market classification |
| [TSETMC instrument identity](https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/51971068201094874) | 200; exact `instrumentID` match, distinct numeric `insCode` and `cIsin` |
| [Existing TSETMC options source](https://cdn.tsetmc.com/api/Instrument/GetInstrumentOptionMarketWatch/2) | 200; 235 authoritative call/put pairs |

Script response-byte SHA-256 fingerprints, for distinguishing a later source
revision from this investigation:

| Source | SHA-256 |
|---|---|
| HubPreRequisite.js | `8640180fa6dcfe7f13571d61e1bd6a09e5ae6e1133b29b10cfa5cebf6300ad20` |
| jquery.signalR-1.2.2.min.js | `d264da10ab81d6f7c655f4f058ea2c84245f5bca070703d7f0e5240275108e21` |
| /signalr/hubs | `2756f299815c316c67c3212ef31d04e4a73b9127a3b24d6bddb4820601b9bfff` |
| StockPageCore.js | `e5f897a58c4696170eda83886194968c04ecac55bf2ad675a439b626a0e9fdcf` |

### Actual request contract and bounded lifecycle observations

The currently referenced client supports ordinary HTTP longPolling; no browser,
new dependency, authentication workaround or guessed newer SignalR protocol is
needed for research. The initial three finite sessions followed this contract;
one further derivative session checked concurrent polling as described below:

1. GET `/signalr/negotiate?connectionData=[{"name":"myhub"}]` (URL encoded).
   The server advertised `ProtocolVersion="1.2"`, `TryWebSockets=false`,
   `KeepAliveTimeout=20` and `DisconnectTimeout=30` seconds. Connection token
   and ID are session state, not instrument identities.
2. GET `/signalr/ping` returned `{"Response":"pong"}`. GET `/signalr/connect`
   used `transport=longPolling`, negotiated `connectionToken`, `connectionData`
   and `tid`. There is no guessed `clientProtocol` or `/start` request.
3. POST `/signalr/send` used form field `data`, containing JSON
   `{"H":"myhub","M":"letsStart","A":[connection_id],"I":0}`.
   The general invocation returned `{"I":"0"}`. This acknowledgement does not
   contain the financial snapshot.
4. GET `/signalr/poll` continued with response cursor `C` as `messageId` and
   `G` as `groupsToken` when present. Callbacks are in envelope `M`, with hub
   `H`, method `M` and positional arguments `A`. Published transport controls
   `D`, `T` and `L` mean disconnect, reconnect and long-poll delay; none appeared
   in the observed envelopes. These are not financial completeness markers.
5. A short `/signalr/reconnect` request resumed session A using its current
   cursor. Each session ended with POST `/signalr/abort` in `finally`; all three
   returned 200. Requests had finite connect/read timeouts; no indefinite stream
   or high-frequency retry loop was run. Tokens/cursors are not committed.

| Session / UTC time | Observed callback and state |
|---|---|
| General A, connect 06:44:13 | `updateRowForOptionStock`, 357 paired rows, **before** requesting general initial state |
| A, requested initial 06:44:15 | `updateSingleTable`, 1,279 unique `SymbolId`, ISIN and ticker values; second argument is a three-number aggregate array |
| A, polls 06:44:22 / 06:44:42 | `updateRow`, 247 / 264 full-shaped records, each with the same keys as initial rows; no new IDs or observed status transitions |
| A, same-cursor reconnect 06:45:02 | `updateRow`, 164 records; **no** replacement initial callback; no new IDs |
| General B, connect 06:45:21 | `updateRow`, 216 records, **before** requesting initial state |
| B, requested initial 06:45:24 | `updateSingleTable`, 1,280 unique IDs/ISINs/tickers; one added ETF block ID29929, کاج2; no IDs removed relative to A |
| B, following poll 06:45:31 | `updateRow`, 259 records |
| Option session, connect 06:45:43 | `updateRowForOptionStock`, 347 paired rows, before the derivative initial invocation |
| Option invocation / cleanup | Published `letsStartForOption(connection.id)` send reached a 30-second read timeout; abort 200; **no verified `updateInitialOptionTable`** |
| Concurrent derivative recheck, 06:57:24–06:57:55 | Connect/general delta318, then polls/general deltas247/176 while the derivative send remained pending; send ReadTimeout30s, abort200; no derivative initial callback |

The general page's `updateSingleTable` calls `updateTable(...,-1)`, which replaces
`gridData`. `updateRow` calls `updateTable(...,0)`: replace an existing record by
`SymbolId`, append an unseen ID, then apply local filters. It does not apply
arithmetic increments to quote fields. No general record-deletion branch or
tombstone contract was found in that merge path. A removal from the displayed
grid can result from filtering and is not proof of source deletion. The
`StockPageCore.js` DOM removal for the floating book is not instrument removal.

No actual add callback, deletion, suspension transition, expired-cursor replay,
missed-message loss or forced server reconnect was observed. The fresh B
collection included one additional ID absent from A's bounded stream. Separate
collection times prevent an atomic equality claim. A transport resume returning
a delta does not establish complete recovery. The shared page error handler
stops the hub; no application-specific rebuild-on-reconnect handler was found
in the inspected general page/shared scripts. Fresh negotiation plus a requested
initial callback was repeatable, but no total, checksum, generation, server
as-of time or financial completion marker establishes its universe.

### Coverage, selectors and financial identities

| `MarketNumber` | Page category | A count | B count |
|---|---|---:|---:|
| 9 | First market | 131 | 131 |
| 14 | Second market | 309 | 309 |
| 24 / 25 / 26 | Yellow / orange / red base boards | 142 / 15 / 5 | 142 / 15 / 5 |
| 13 | نوآفرین (checkbox ID `SME`) | 9 | 9 |
| 2 | Fixed-income instruments | 304 | 304 |
| 6 | ETF | 191 | 192 |
| 4 | Housing facilities | 10 | 10 |
| 7 | Options | 160 | 160 |
| 18 | No selector in the inspected general filter | 3 | 3 |
| 27 / 28 / 12 | Negotiated shares / negotiated sukuk / futures selectors | 0 observed | 0 observed |

Checkboxes filter the already received collection locally. `SymbolNum="1"`
selects main symbols; the block/major selector selects `"2"` or `"4"` instead.
A contained 1,072 / 18 / 187 / 2 records for symbol numbers 1 / 2 / 3 / 4;
B added one number-2 record. Number 3 is excluded by that filter. With every
supported category selected, 1,069 main-symbol rows match the filter; raw
callback count and displayed market count are different quantities. Markets
27/28/12 being absent does not establish valid empty markets or provider policy.

A separate current `get_ifb_market_map()` returned 1,177 IDs: 894 common with
A, 283 map-only, 385 watch-only. For example ID18006 is in the map but absent
from A. The map has negotiated categories not observed in the watch, while the
watch includes options and auxiliary symbol numbers. Different source universes
do not prove a transport loss and must not be joined as one atomic quote.
There is no independently verified all-IFB denominator for this watch.

Official IFB ID18620 is بپاس, ISIN `IRO3BIPZ0001`, mnemonic `BIPZ1`, second
market. TSETMC's exact `instrumentID` matches that ISIN for numeric
`insCode="51971068201094874"`; its `cIsin="IRO3BIPZ0009"` is different.
An IFB `SymbolId`, option-pair `Code`, ISIN and TSETMC code are distinct
identifiers. Do not join by a numeric resemblance, normalized ticker alone or
the different `cIsin`. No complete cross-provider identity mapping was verified.

### Financial field evidence and limits

Types below describe observed JSON values, not a promised future schema.
Numeric tokens were inspected with decimal parsing. No null values appeared
in A's row fields; this does not prove nulls can never occur. No zero-to-price,
zero-to-date or missing-to-zero inference is justified.

| Exact source field(s) | Meaning / observed type and applicability | Units, zero/missing, timestamps and verification |
|---|---|---|
| `SymbolId`, `ISIN`, `SymbolName`, `InsTitle`, `EnSymbolName`, `EnTitle`, `SymbolNum` | IFB integer ID; string security identity/title/mnemonic/board-symbol suffix | Exact equity identity cross-check above; string IDs would be required in a public frame; suffix is not an option contract parser |
| `MarketNumber`, `SymbolState`, `StateTitle`, `EnStateTitle`, `OraghisFinished` | Integer category/state-related fields, string status labels, integer finished-related field | Categories follow page filters; multiple numeric states share the same status label and vice versa. No independently verified universal state/expiry enum |
| `ClosingPrice`, `PreClosing`, `LastTradePrice` | Numeric closing, previous closing and last trade values | Native price tokens, consistent with rial equity prices in existing map/TSETMC comparisons; no universal per-category price/contract-unit contract or per-row observation time verified. Closing is not last |
| `ClosingChange`, `LastChange`, `ClosingPercent`, `LastPercent` | Numeric absolute and percentage changes | All 422 main equity rows satisfied closing/last minus previous closing and `100*ClosingChange/PreClosing` (decimal tolerance 0.000001); percentage points, not fractional returns |
| `OpeningPrice`, `HighestPrice`, `LowestPrice` | Numeric opening/high/low-named fields | **All 1,279 openings were zero, including 627 rows with trades**. High/low can remain nonzero with zero current trade count. No verified opening or dated OHLC series may be fabricated from these |
| `TotalTradeQuantity`, `TotalTradeValue`, `TradeCount` | Numeric volume, integer value and integer count, separately bound in page | Equity quantities/counts and rial values consistent with existing source comparisons; contract-count versus underlying-unit and debt conventions not independently verified across this mixed universe; zero trades do not prove empty/stale book |
| `UnitCount`, `MarketValue` | Integer units and numeric market value | All 422 main equity rows satisfied `MarketValue=ClosingPrice*UnitCount`; not trade value. Does not verify share/contract multipliers for every category |
| `BestBuyPrice`, `BestBuyQuantity`, `BestBuyCount`, `BestSellPrice`, `BestSellQuantity`, `BestSellCount` | Numeric top bid/ask price, quantity and count | All six matched first `ThisBestLimits` level where present. No source quote timestamp; zero side is observed, not a verified executable zero-price order |
| `ThisBestLimits` | Array of `BuyCount`, `SellCount` integers and `BuyQuantity`, `SellQuantity`, `BuyAmount`, `SellAmount` numbers | Page explicitly renders count / quantity / price for each side; `Amount` here is **price**, not notional value. Order and variable depth evidence below; per-category quantity conventions unresolved |
| `ThisBestLimitsOption`, `OptionTrades` | Arrays present in general row schema | Empty in the examined general initial records; no separate five-level derivative contract inferred |
| `EPS` and rendered `PtoE` | Numeric source EPS; page computes close/EPS only when EPS is positive | Source earnings period/basis unverified; zero and negative EPS have different display handling. Prior IFB/TSETMC EPS difference remains, so providers are not interchangeable |
| `NAV`, `NAVDate`, `NAVTime` | Numeric NAV, string date/time | A: all zero, dates/times `"0"`; no valid NAV observation or quote timestamp established |
| `YTMOfClosingPrice`, `YTMOfPreClosingPrice`, `YTMOfLastTradePrice` | Numeric price-specific yield-named fields | 300 nonzero closing-YTM values, e.g. 25.05 for آبارا07. Percent/rate, compounding, accrued interest and coupon/discount basis not independently verified here; not a replacement for verified historical YTM/risk-free APIs |
| `*Changed`, `AnythingChanged` | Mixed numeric differences and boolean display-change markers | Page uses these for highlighting and resets some markers; not observation times, absolute financial values or deletion flags |
| `updateRow` argument `date`; HTML `lbldt` | String display-update label | Actual ` دوشنبه 18 آبان ماه ساعت 10:14:22`, then 10:14:42 and 10:15:02: omits year and timezone, not per-instrument trade/book time. Initial callback has no such argument; HTML label is page render time. Retrieval UTC is research metadata only |
| Callback aggregate arrays | General initial/update second/third argument, three numbers; option callback two numbers | Not instrument counts, completeness checks or quote timestamps. No public interpretation added without independently establishing their exact inclusion rules |

For بپاس in A, closing/previous/last were 13,770 / 13,730 / 13,780;
volume 3,656,845, value 50,347,485,540, trade count 129. Market value was
1,425,195,000,000,000 for 103,500,000,000 units. Later existing public TSETMC
index quotes returned closing 13,770 / last 13,800, volume 4,619,845 and value
63,633,475,540. These are separate retrievals during trading, not a discrepancy
to repair by replacing one source's numbers with another's.

### Five-level book: demonstrated gap and remaining limits

The page's `loadBestLimits` iterates the array in received order, with labeled
buy/sell count, volume and price columns. Throughout A, positive bid prices
descended and asks ascended; all present first levels matched the six top-level
fields. بپاس bid prices were 13,770 / 13,760 / 13,750 / 13,740 / 13,730,
asks 13,780 / 13,790 / 13,800 / 13,810 / 13,820. This supports level ordering
and price-field meaning, without independently establishing book freshness.

Actual lengths were **1,259 five-level, 7 empty, 12 one-level, 1 three-level**
records in A; B had one more empty book. ETF آوا2 ID24923 had `[]`;
اوصتا2 ID23661 had one all-zero level; halted آ س پ3 ID17800 had five
all-zero levels. Across A there were 6,116 zero-price sides. Three first levels
were locked (bid equals ask), including اتکاسا ID40874 at 8,910 with reserved
status `مجاز-محفوظ`. No crossed positive first level was observed. A universal
strict-spread rule, forced five-row padding, or interpreting a zero level as
an executable quote would misstate the source. Numeric state codes alone do
not resolve auction/halt/freshness semantics. No independent full book
comparison or per-level timestamp was verified.

This is the strongest potential nonduplicative capability: current public
TSETMC index quotes and Options watch expose no equivalent general IFB
five-level book. Implementing it still needs defined exclusions, dated state,
status/zero-side conventions and reliable bounded initial/recovery behavior.

### Derivatives: achieved evidence versus unverified initial state

The reachable **current shared client/proxy**, not a guessed endpoint, exposes
`letsStartForOption`, `updateInitialOptionTable` and
`updateRowForOptionStock`. Its ordinary public callback appeared before a
derivative initial request in two sessions. The derivative HTML GET timeouts
and the hub method timeout are distinct observed failures; neither establishes
access denial or global unavailability. No restriction bypass was attempted.

The final derivative recheck kept polling concurrently with the pending hub
invocation, as the JavaScript transport does. It again reached a 30-second send
read timeout, while receiving general update callbacks, and ended with abort200.
Thus the initial-state limitation is not inferred solely from a serial
send-then-poll probe. All **four** sessions performed ordinary abort cleanup;
there was no repeated subscription loop or attempt to evade a provider denial.

| Exact derivative field group | Achieved evidence / remaining uncertainty |
|---|---|
| `Code`, `BuySymbolId`, `SellSymbolId`, `BaseSymbolId`, `BaseSymbol` | IFB pair/call/put/base identities are separate fields. Example pair `2532227000014050824`, call42855, put42866, base25322 فزر. Pair Code exceeds JavaScript's safe integer range; do not parse via float or treat it as a TSETMC code |
| `BuySymbolName`, `SellSymbolName`, `BuyTitle`, `SellTitle`, English equivalents | Actual call/put titles and symbols, not merely bid/ask sides. No ticker-based strike/expiry extraction |
| `Price`, `Date`, `RemainingDay`, `BuyContractSize`, `SellContractSize` | Example فزر: 270,000, `"14050824"`, 5, 1,000 / 1,000. Strike/expiry/size interpretation is consistent with supplied titles, but full exact cross-provider contract mapping and unit/date conventions remain unverified |
| `Buy/SellTotalTradeQuantity`, `Buy/SellTotalTradeValue`, `Buy/SellTradeCount`, `Buy/SellClosingPrice`, `Buy/SellLastTradeprice` | Distinct native trade and price fields observed; no verified contract-size/value identity across every contract, settlement basis or observation timestamp |
| `Buy/SellOpenPositions`, `Buy/SellSpotValue`, `Buy/SellContractType`, `BaseClosingPrice` | Open positions and moneyness-related fields observed; example base close313,300 minus strike270,000 equals BuySpotValue43,300, SellSpotValue-43,300. Labels describe in/out-of-money, not instrument status. No separate history or settlement guarantee |
| `Buy/SellbestBuyPrice`, `Buy/SellbestSellPrice`, `Buy/SellbestBuyLimitQuantity`, `Buy/SellbestSellLimitQuantity` | Best bid/ask only in these paired rows; no five-level derivative book or quote timestamp established |

Connect callbacks contained 357 and 347 unique pair codes, with `Date` values
from `14050511` to `14051125`, including past dates and `RemainingDay=0`.
Neither callback is labeled initial. Do not interpret their changing sizes or
older contracts as broader complete **live** coverage. The derivative initial
invocation did not produce a verified initial state; replacement, removal,
expiry retention and reconnect behavior remain unresolved.

In particular, the source's `RemainingDay=5` for Date14050824 is not simply
the six-day calendar difference from the investigation date14050818. No
settlement-day, inclusion/exclusion or recalculation convention was established;
do not silently recompute it or claim a universally verified days-to-expiry field.

The existing official TSETMC option source still returned 235 pairs. Current
`Options.download_market_watch(market="IFB", stack="Vertical", j_date=False)`
succeeded with **470 rows, 235 calls and 235 puts, 29 documented columns**:
authoritative contract/underlying codes, strike, expiry, size, price/trades,
open positions and best bid/ask. Existing chains/history/analytics already
provide the corresponding capabilities. TSETMC's public IFB index-constituent
quotes succeeded with 247 rows; that is an index universe, not all IFB.
No fima bug or missing derivative capability was established by this comparison.

### Decision matrix before production implementation

| Candidate capability | Source / fields | Coverage, units and time | Existing overlap | Complexity / risk | Decision |
|---|---|---|---|---|---|
| Bounded IFB quote snapshot | General `letsStart` / `updateSingleTable`; identity, market, prices/trades | Repeatable 1,279/1,280 collections; no independent total or dated as-of; opening zeros; mixed-unit conventions unresolved | TSETMC constituent quotes/history and IFB map | Demultiplex callbacks, validate entire mixed collection, cleanup; risk of stale/incomplete financial claims | **Defer** |
| Five-level general book | `ThisBestLimits`; six fields per level | Ordering/top alignment verified; variable depth/zero sides; source exclusions and freshness unresolved | Useful gap beyond existing public APIs | Lifecycle/status/recovery contract needed; no general stream engine justified | **Defer**, strongest future candidate |
| Improve IFB/TSETMC | Existing verified map, constituent and history sources | Different source universes, not a reproduced implementation failure | Already implemented | Replacing sources would change established coverage/semantics | **Preserve** |
| Improve Options | Published IFB derivative callbacks | Only updates obtained; initial/expiry/units/times not independently established | Existing authoritative 470-row public watch, chains/history/metadata | Parallel protocol for unproven financial gain | **Preserve** |
| Add no API in this phase | Evidence and explicit implementation gates | Distinguishes achieved checks, valid source zeros, incomplete knowledge and network failures | All established APIs retained | No new dependency, architecture or fabricated observations | **Selected**, documentation only |

Future work in #129 must establish source exclusions/total or an honestly bounded
coverage contract, deletion and stale-ID behavior, missed-message recovery,
dated quote/book provenance, per-category financial units/status semantics,
and a reliable derivative initial collection before implementing that candidate.
The current counts are dated observations, not test constants or coverage promises.
No speculative deterministic fixtures, provider-dependent CI tests, version bump,
tag, GitHub Release, artifact upload or PyPI publication accompany this phase.

### Validation of this documentation-only decision

The full deterministic suite passed **954 tests / 147 integration deselected**.
All four existing opt-in market-map cases passed: the first run had three passes
and a TLS-handshake read timeout before a trade-volume response; a single
targeted retry of that case passed. No test was skipped, weakened or changed to
hide the network failure. Captured-evidence checks validated the counts,
identity-set change, zero/NAV/YTM observations and every present first book
level/order. Existing public Options and TSETMC checks are reported above.

Clean-copy wheel/sdist builds, strict Twine metadata checks, source/privacy
inventory and documentation links/anchors passed. The sdist includes both
updated IFB guides through the existing manifest. A fresh offline-installed
wheel imported all **77 public callables** with import-time HTTP prohibited;
`pip check` passed. Every Python source file matches `v0.14.0`; no public API,
deterministic/integration test, dependency, version or release workflow changes
are needed for this evidence-based deferral. Raw provider responses, connection
state, research scripts and build outputs are excluded from the PR.
