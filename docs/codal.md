# CODAL reports

## دریافت مستقیم گزارش با نام فارسی

برای شروع، نماد و نام گزارش را وارد کنید. تاریخ پایان دوره را می‌توانید
به‌شکل ماه یا روز شمسی بنویسید. این مثال، نسخهٔ اصلاح‌شدهٔ گزارش عملکرد
شهریور ۱۴۰۵ فولاد را در یک DataFrame برمی‌گرداند.

```python
from fima import get_codal_data

df = get_codal_data(
    symbol="فولاد",
    report_type="گزارش عملکرد ماهانه",
    period="1405/06",
)
print(df[["ProductName", "PeriodBasis", "Metric", "Value", "Unit", "Scale"]].head())
print(df.attrs["Filing"]["TracingNo"])
```

برای صورت‌های مالی، نام صورت را در `statement` بنویسید یا همان نام را
در `report_type` وارد کنید. نمونهٔ بمپنا ۹۲ مشاهده از صورت سود و زیان
حسابرسی‌شدهٔ شش‌ماهه برمی‌گرداند.

```python
income = get_codal_data(
    symbol="بمپنا",
    report_type="صورت‌های مالی",
    statement="سود و زیان",
    period="1402/06",
    audited=True,
)
print(income[["AccountLabel", "PeriodBasis", "Value", "Unit", "Scale"]].head())
```

| نام گزارش | نام‌های دیگر و پوشش |
| --- | --- |
| گزارش عملکرد ماهانه | گزارش فعالیت ماهانه، گزارش ماهانه. تبدیل به دادهٔ مالی برای قالب‌های تولیدی V3 و V4. |
| صورت‌های مالی | صورت مالی، صورت‌های مالی میان‌دوره‌ای، صورت‌های مالی سالانه. پوشش مالی برای صورت‌های جداگانهٔ تولیدی در قالب‌های زیر. |
| صورت سود و زیان | سود و زیان. صورت پیش‌فرض برای «صورت‌های مالی». |
| صورت وضعیت مالی | ترازنامه. |
| صورت جریان وجوه نقد | جریان وجوه نقد، صورت جریان‌های نقدی. |
| افشای اطلاعات بااهمیت | اطلاعات بااهمیت. جست‌وجوی اطلاعیه. |
| آگهی دعوت به مجمع، تصمیمات مجمع | جست‌وجوی انواع آگهی دعوت یا تصمیمات مجمع. |

یک ماه مانند `۱۴۰۵/۰۶` یا `شهریور ۱۴۰۵` با تاریخ **پایان دوره** مطابقت
دارد. تاریخ انتشار در `PublishDateTime` است. بدون `period`، جدیدترین
تاریخ پایان دوره انتخاب می‌شود. اگر چند تاریخ، مدت یا وضعیت حسابرسی
در محدودهٔ خواسته شده باقی بماند، روز دقیق یا `duration_months` و
`audited` را مشخص کنید. دریافت خودکار گزارش خود ناشر و صورت‌های جداگانه
را انتخاب می‌کند. اگر چند نسخهٔ مرتبط وجود داشته باشد، جدیدترین نسخه با
بررسی پیوندهای اصلاحیهٔ کدال برگزیده می‌شود. شماره‌های زنجیره در
`df.attrs["RevisionTracingNos"]` و مشخصات گزارش و منبع در `df.attrs`
قرار دارند.

### تأیید انسانی در مرورگر

دریافت عادی با HTTP انجام می‌شود. برای فعال کردن تأیید انسانی، یک‌بار
وابستگی اختیاری را نصب کنید. اگر Google Chrome از قبل نصب است، نصب
Chromium اختیاری است.

```sh
python -m pip install "fima[codal-browser]"
```

اگر Chrome نصب نیست، Chromium را نصب کنید.

```sh
python -m playwright install chromium
```

اگر fima را از مخزن اجرا می‌کنید، از پوشهٔ مخزن
`python -m pip install ".[codal-browser]"` را برای نصب بسته اجرا کنید.

```python
from fima import get_codal_data

df = get_codal_data(
    symbol="فولاد",
    report_type="گزارش عملکرد ماهانه",
    period="1405/06",
    interactive=True,
)
```

اگر کدال نیاز به تأیید انسانی را اعلام کند، مرورگر صفحهٔ رسمی کدال را برای
همان جست‌وجو یا گزارش باز می‌کند. کد را در فرم خود کدال وارد و تأیید کنید.
fima پس از تأیید، دریافت را در همان نشست مرورگر ادامه می‌دهد و همان
DataFrame را با اطلاعات منبع برمی‌گرداند. برای لغو، پنجره را ببندید.
برای تکمیل تأیید تا چهار دقیقه فرصت دارید.

`search_codal_filings` و `fetch_codal_report` نیز `interactive=True` را
می‌پذیرند و پیش‌فرض هر سه تابع `False` است. اگر فرم قابل استفاده نمایش
داده نشود یا کدال پس از تأیید دسترسی به درخواست بعدی را رد کند،
`CodalRequestError` دریافت می‌کنید. پاسخ HTTP 429 دریافت را فوراً متوقف
می‌کند و مهلت اعلام‌شده در `Retry-After` رعایت می‌شود.

### Search results, raw cells, and source limits

`list_codal_report_types()` lists the current Persian names and IDs
under CODAL's exchange-issuer publisher type. `search_codal_filings(symbol,
report_type, period=None, *, max_pages=100, interactive=False)` returns
filing metadata with separate category, letter-type and textual letter-code
fields. Search keeps original and corrected notices, subsidiary reports under
the exact publisher symbol, and both separate and consolidated reports where
present. It walks the
provider's reported pages and raises `CodalRequestError` if the page limit,
changing counts, duplicate tracing numbers, HTTP errors, or human verification
prevent full coverage. A completed query with no matching rows returns an empty
DataFrame. Reporting-period filters apply to monthly and financial types. Search
disclosures and meeting notices using the Persian name alone.

`get_codal_data(..., raw=True)` returns source cells and sheet coverage when
the filing carries structured data. This can be used with newer templates such
as the فولاژ income statement for `1405/06` (`audited=False`). To choose a
specific filing from search results, pass a single row to
`fetch_codal_report(row, statement="سود و زیان")`. It preserves the original
HTML bytes, SHA-256, source URL and provider metadata. Pass its result to
`get_codal_tables(report)` for separate cell tables. PDF-only filings, legacy
HTML grids, and files lacking the structured datasource are outside this reader's
coverage. An unavailable statement or unsupported normalization raises
`ValueError`. `from fima.codal import CodalRequestError` provides the exception
for transport, access, and incomplete search failures. HTTP 429 stops the
operation and reports the `Retry-After` value when provided. A valid wait
in seconds or an HTTP date also stops new CODAL requests in the same Python
process until the deadline. With the default `interactive=False`, human
verification raises `CodalRequestError`.

### Request count and complete results

Successful searches exhaust the advertised pages. CODAL's browser UI exposes
date and subject controls, and their saved frontend contract does
not establish an exhaustive reporting-period filter. Keeping reporting-period
matching local preserves older filings and late corrections. An explicitly
requested period that is already ambiguous can fail before reading the remaining
pages. Complete metadata search still reads all pages.

The recorded فولاد monthly query advertised nine search pages. In a deterministic
replay with a redirect per search-result report URL, the corrected filing and
its predecessor went from four report GETs to three. That is 14 to 13 total
GETs with a cold taxonomy cache, or 13 to 12 with a warm cache. Actual counts
depend on page totals and redirects. For a financial correction, the older
filing's already loaded statement can establish its identity and revision links.
The requested statement is always validated on the returned filing. The client
uses the existing sheet-selection path when the older default page has no usable
statement.

The public CODAL search page uses `/api/search/v1/categories` and
`/api/search/v2/q`. On November 24, 2026, its taxonomy contained 11 report
categories plus the all-categories entry, 167 distinct letter-type IDs, and
105 category/type pairs for exchange issuers. The issuer taxonomy linked
monthly activity to category `3` and letter type `58`. Filings carry the
separate letter code `ن-۳۰`. Issuer financial statements used category
`1` and letter type `6`, including both annual and interim filings, with
`ن-۱۰` as the observed letter code. fima reads the current taxonomy when
called and reuses it for up to ten minutes. The public site uses these routes
for anonymous lookups.
[CODAL search page](https://www.codal.ir/ReportList.aspx?search)

### Public endpoint availability

The verified workflow uses CODAL's public taxonomy, search, and report pages
over HTTPS. CODAL served the tested filings anonymously. Availability can
vary by request and over time. CODAL may rate-limit requests, require human
verification, or change the endpoints or report formats. The public search
page submits its own CAPTCHA and signals successful verification inside its
browser application. That application can also display a CAPTCHA after HTTP 429.
fima stops on HTTP 429, including during an interactive call. A search verification
flag can open the public search page, and continuation requires the page to show
a usable challenge and CODAL to accept the request in the browser session.
[CODAL search page](https://www.codal.ir/ReportList.aspx?search)
Published quotas and operator terms for sustained automated use remain unconfirmed.

The deterministic suite runs without contacting CODAL. When the public
endpoints are available, run a single live manufacturing case with
`python -m pytest -x -m integration -k foolad_monthly_correction test/test_codal_integration.py`.
Stop on a rate limit or human-verification response.

## Read saved files

Stage 1 reads a local copy of a CODAL filing page and returns the structured
cells carried by that page. It keeps provider identities, native values, source
coordinates, unit notes and the original document bytes.

## Obtain a supported file

The supported representation is UTF-8 HTML, optionally with a BOM, with an
inline `var datasource = …;` JavaScript declaration whose value is JSON.
The declaration ends its script and contains `sheets`, with `tables` and `cells`
arrays. fima reads the data without running scripts or loading page resources.

### Save from a browser

1. Open a supported CODAL filing in your browser and select the financial
   statement sheet you need.
2. Use the browser's **Save As** command, choose **HTML Only** or **Complete
   HTML**, and save the page.
3. Pass the saved HTML file to `get_codal_report`, then use the CODAL function
   for that report type. For the income statement, use
   `get_codal_financial_statements`.

```python
from fima import get_codal_report, get_codal_financial_statements

report = get_codal_report("income_only.html", sheet_id=1)
df = get_codal_financial_statements(report)
print(len(df))
```

The maintainer tested both formats on [filing 1106536, income statement sheet
`1`](https://codal.ir/Reports/Decision.aspx?LetterSerial=X2OX1hOJ2JKt9DK%2bTia50Q%3d%3d&rt=0&let=6&ct=0&ft=-1&sheetId=1).
Both `income_only.html` and `income_complete.html` preserved the embedded
`datasource`, loaded sheet `1`, and produced 92 normalized observations.
Browser saves must retain the embedded `datasource`. Normalization supports
the verified templates described below. Browser-save verification covers
this filing and sheet.

### Download the HTML response

1. Open the announcement on CODAL and select the sheet you need when a menu is
   present. Copy the public filing or sheet URL from the browser.
2. Where the URL permits a direct anonymous download, save the HTML response
   to disk with `curl`. Use `curl.exe` in Windows PowerShell.

   ```sh
   curl --fail --location --max-redirs 4 --max-time 30 --output report.html "PASTE_PUBLIC_REPORT_URL_HERE"
   ```

The direct download was verified on November 24, 2026 against CODAL filings
1494376 and 1492711 (monthly manufacturing reports) and sheets `0` and `1`
of filing 1106536 (an audited interim financial statement). All four saved
responses retained the structured data. An independent JSON read matched all
3,055 output cells across 13 tables, including the signed string `'-2402795'`
in income-statement cell `B5`. CODAL served the balance sheet and
income statement in separate responses under the same filing identity. See
[CODAL monthly filing
1494376](https://codal.ir/Reports/Decision.aspx?LetterSerial=dz8uAPkDiymNiKygk9FSoA%3d%3d&rt=0&let=58&ct=0&ft=-1),
[monthly filing 1492711](https://www.codal.ir/Reports/Decision.aspx?LetterSerial=jpQQQaQQQqfZKLzOnAkQQQaQQQAA1yexDg%3d%3d&rt=0&let=58&ct=0&ft=-1),
[balance sheet](https://codal.ir/Reports/Decision.aspx?LetterSerial=X2OX1hOJ2JKt9DK%2bTia50Q%3d%3d&rt=0&let=6&ct=0&ft=-1&sheetId=0),
[income statement](https://codal.ir/Reports/Decision.aspx?LetterSerial=X2OX1hOJ2JKt9DK%2bTia50Q%3d%3d&rt=0&let=6&ct=0&ft=-1&sheetId=1).

The offline reader accepts copies of authorized filings saved using CODAL's
browser workflow. CAPTCHA pages, legacy HTML grids without
the structured payload, auditor-only pages without it, PDF, Excel, MHTML and
standalone JSON are outside this interface.

## Read a report and its tables

```python
from pathlib import Path

from fima import get_codal_report, get_codal_tables

report = get_codal_report(Path("report.html"), sheet_id="0")
tables = get_codal_tables(report)
print(report["Coverage"]["LoadedSheetIds"])
print(tables[0]["Cells"][["Address", "Value", "CellGroup"]].head())
```

`get_codal_report(path, sheet_id=None)` accepts a local string or path-like
object. `sheet_id` accepts a string or an integer such as `0`. Strings match
exactly, including leading zeros. The report retains all embedded sheets, and
the selector limits the result of `get_codal_tables(report)`. The default
extracts tables from every embedded sheet.

### Report dictionary

| Key | Contents |
| --- | --- |
| `Source` | `Provider` (`CODAL`), `Format` (`CodalDatasourceHTML`), absolute local `Path`, hex `ContentSha256` of the exact bytes, and source `LetterSerial` and `FormAction` when embedded. The last two are `None` when absent. `FormAction` is the original HTML attribute and can be relative or empty. |
| `Content` | The original file as `bytes`, including any BOM. |
| `ProviderMetadata` | All top-level JSON fields outside `sheets`, using CODAL's keys. Examples include the template titles and `type`, `tracingNo`, `subject`, `period`, `periodEndToDate`, `yearEndToDate`, `publishDateTime`, audit and consolidation fields. |
| `PageMetadata` | Present source fields among `Title`, `CompanyName`, `Symbol`, `DisplaySymbol`, `Isic`, `ReportName`, `PeriodLabel`, `PeriodEndDate`, `FiscalYearEndDate`, `AuditLabel`, `PriceNote`, `FilingVersion` and `RevisionLinks`. Revision links retain `ElementId`, `Text` and `Href`. Company and symbol labels are copied without inferring an issuer or subsidiary relationship. |
| `Coverage` | `LoadedSheetIds` in payload order, `SheetOptions` in HTML menu order (each with `SheetId`, `Title`, `IsSelected`, or `None` for an absent menu), `UnloadedSheetIds` from that menu, `SelectedSheetId` from an explicit menu selection if present, and `RequestedSheetId` from the call. |
| `Sheets` | Loaded sheet records with `SheetId` from the source `code` as a string, `ProviderMetadata` with original fields and `Tables` with the original provider table records. |

Coverage describes the saved file. An empty `UnloadedSheetIds` only means
there are no known missing sheets in its menu. In filing 1106536, the file
for sheet `0` listed eleven other sheets, including sheet `1`. Save additional
sheets individually when needed and keep each file's provenance. The
reader also recognizes the alternate sheet menu in [corrected filing
1619870](https://www.codal.ir/Reports/Decision.aspx?LetterSerial=zRjmF4UpaQQQaQQQXPVuXgXg0zQQQaQQQQ%3d%3d&rt=0&let=6&ct=0&ft=-1&sheetId=1).
That income statement file embeds sheet `1` and lists nine other sheets.

### Table dictionaries and cell DataFrames

`get_codal_tables(report)` returns a list in payload order. Every table includes
`SheetId`, `TableId` (the provider's `code` as a string), and `TableOrder`
(zero-based within its sheet). It includes the original `TitleFa`, `TitleEn`,
`Version`, and `Description` when present, plus the separate `PagePriceNote`,
`ProviderMetadata` (including provider `metaTableId` and `sequence` when
present), the document's `Source`, and `Cells`.

`Cells` has one row per source entry with these columns:

| Columns | Contents |
| --- | --- |
| `SheetId`, `TableId`, `CellOrder` | Source sheet and table codes, and zero-based position in the cell array. |
| `RowSequence`, `ColumnSequence`, `RowCode`, `ColumnCode`, `Address` | Original coordinates, codes and address, as supplied. |
| `Value`, `ValuePresent` | Original decoded value and whether the source had a `value` key. |
| `RowSpan`, `ColumnSpan`, `IsVisible`, `CellGroup` | Source spans, visibility and group label, when present. |
| `ProviderMetadata` | The entire source cell object, including original keys such as formula, data type, period and financial concept when provided. |

All columns use pandas `object` dtype. Strings keep their original digits,
formatting and signs. Integral JSON numbers are Python `int`. Fractional and
exponent-form numbers and signed integer zero are `decimal.Decimal`. A missing
value key and an explicit JSON null both have `Value=None` with different
`ValuePresent` values. Empty strings and zero remain distinct. Hidden cells,
duplicate coordinates and source order survive extraction. Source bytes retain
the exact JSON spelling, including escapes and exponent notation.

Table `Description` and the page-level price note are separate source strings.
Column headers and individual cells may supply more specific units or periods.
fima applies no unit conversions, formula evaluation, period alignment,
pivoting, or financial interpretation.

`get_codal_report` raises an `OSError` subclass for local file access failures
and `ValueError` for unsupported or malformed content, inconsistent structural
identities, or a requested sheet absent from the payload. `get_codal_tables`
expects the dictionary returned by `get_codal_report` and raises `TypeError`
for an unrelated input.

## Normalize manufacturing production and sales

`get_codal_monthly_activity(report)` accepts the dictionary returned by
`get_codal_report`. It reads the **Production and sales** table (code `1197`,
table version `4`, sheet `1000000`) in standalone one-month **Monthly Activity
Product V3 and V4** filings. It validates the grid, merged headings, period
metadata and row groups. V3 leaves two rows between the headers and the body.
The rest of the report remains available through the Stage 1 functions.

```python
from fima import get_codal_monthly_activity, get_codal_report

activity = get_codal_monthly_activity(get_codal_report("report.html"))
monthly_export = activity.loc[
    (activity["PeriodBasis"] == "CurrentMonth")
    & (activity["MarketSegment"] == "Export")
    & (activity["Metric"] == "SalesAmount")
    & (activity["RowKind"] == "Detail"),
    ["ProductName", "Value", "Unit", "Scale", "Address"],
]
```

The DataFrame has one row per metric cell in each named detail, subtotal,
discount and total row. Physically present blank cells in these rows are
included. Section headings and unfilled CODAL entry rows are omitted. Results
are ordered by source row sequence and then by column sequence. All columns
use pandas `object` dtype.

| Columns | Contents |
| --- | --- |
| `TracingNo`, `CompanyName`, `SubjectName`, `Symbol`, `FilingKind` | The filing tracing number, the company label, the provider's `subject` when present, the page symbol (or display symbol when the first is empty), and the original provider `kind`. Persistent issuer and product IDs were unavailable in the verified grid. |
| `ReportPeriodEndJalaliDate`, `PeriodEndJalaliDate`, `FiscalYearEndJalaliDate`, `PeriodBasis` | The filing end date, the observation end date, the source cell's fiscal year end and one of `PreviousYTD`, `Adjustment`, `AdjustedYTD`, `CurrentMonth`, `CurrentYTD`, or `PriorYearYTD`. Adjustment cells have undated headings in the verified grid and carry `None` in both observation date columns. |
| `ActivitySection`, `MarketSegment`, `RowKind` | The source section (`DomesticSales`, `ExportSales`, `Services`, `SalesReturns`, `Discounts`, or `Total`), market (`Domestic`, `Export`, or `None`), and row kind (`Detail`, `Subtotal`, `Discount`, or `Total`). A market identifies the source subsection, including when that subsection reports production. |
| `RowLabel`, `ProductName`, `ProductUnit`, `ProductStatus` | The exact source row label and, on detail rows, the original product name, product-unit label and product status. Different rows remain separate even if they share a product label. |
| `Metric`, `Value`, `Unit`, `Scale` | `ProductionQuantity`, `SalesQuantity`, `SalesRate`, or `SalesAmount`. `Value` is the exact reported number as `Decimal`, or `None` for a blank. Product quantities use the original product unit and scale 1. Rates keep the heading's `IRR` and scale 1, with the product unit recorded separately. Amounts have unit `IRR` and scale 1,000,000 because the heading specifies millions of rials. Unlabelled subtotal or total quantities keep their values with unknown unit and scale. |
| `RawValue`, `ValuePresent` | Original decoded value and whether the source cell had a `value` key. Together these distinguish empty text, explicit null, a missing value key and zero. |
| `ContentSha256`, `SheetId`, `TableId`, `RowSequence`, `ColumnSequence`, `Address`, `CellOrder` | Hash of the exact source HTML, provider codes, source grid coordinates, address and position in the original cell array. |

The DataFrame's `attrs` contain copies of the Stage 1 `Source`,
`ProviderMetadata`, `PageMetadata` and `Coverage`, including source revision
links where supplied. Each call represents one filing. Keep its metadata with
the result when combining filings. There is no rescaling, rate recomputation,
aggregation, conversion of year-to-date values to monthly values, or automatic
selection of a corrected version.

An unrelated input raises `TypeError`. A different template, a missing target
table or an ambiguous grid raises `ValueError`. This function requires the
supported Stage 1 HTML representation. It covers only the verified
production-and-sales grid, so raw-material, energy, currency, and narrative
tables and non-manufacturing templates remain outside this API.

The grid was verified using [کترام 1494376](https://codal.ir/Reports/Decision.aspx?LetterSerial=dz8uAPkDiymNiKygk9FSoA%3d%3d&rt=0&let=58&ct=0&ft=-1),
[شیفته 1482763](https://codal.ir/Reports/MonthlyActivity.aspx?LetterSerial=fjWk0Qaja8r9lxGyp53EXw%3d%3d),
[1492711](https://www.codal.ir/Reports/MonthlyActivity.aspx?LetterSerial=jpQQQaQQQqfZKLzOnAkQQQaQQQAA1yexDg%3d%3d),
[its correction 1500481](https://www.codal.ir/Reports/MonthlyActivity.aspx?LetterSerial=WVDQQQaQQQOOOObOOOOOObOOOtcchv3IoOnp9spQ%3d%3d),
[1612377](https://codal.ir/Reports/Decision.aspx?LetterSerial=EMme9rpkeQQQaQQQR6rFXe75w6Vg%3d%3d&ct=0&ft=-1&let=58&rt=0),
and [سآبیک 1063618](https://www.codal.ir/Reports/MonthlyActivity.aspx?LetterSerial=KoPobBXLPGSYeU8m8LLOiw%3d%3d)
and [1225799](https://www.codal.ir/Reports/MonthlyActivity.aspx?LetterSerial=I5i8m1JusmQQQaQQQXJzoDADOOObOOOOYQ%3d%3d).
The original and corrected production-and-sales grids have identical values.
The source correction links and separate tracing numbers preserve the
distinction. The adjustment columns in these filings contain blanks or zeros.

## Normalize separate industrial financial statements

`get_codal_financial_statements(report)` reads the supported statement sheets
in a report from `get_codal_report`. It uses the requested sheet when supplied.
Otherwise it processes supported loaded sheets in payload order. A listed
sheet may require its own saved HTML file, even when it belongs to the same
filing.

```python
from fima import get_codal_financial_statements, get_codal_report

report = get_codal_report("income.html", sheet_id=1)
statements = get_codal_financial_statements(report)
current = statements.loc[
    statements["PeriodBasis"].eq("Current"),
    ["AccountLabel", "Value", "Unit", "Scale", "Address"],
]
```

The verified filing templates are `FinancialStatement-OTC-Product-V5` and
`FinancialStatement-Registered-Product-V5` for cumulative six-month statements,
and `Financial Statement - Product - Other - Child Companies - V2` for
12-month statements. All are separate production filings (CODAL report type
`6`) with regular fiscal periods. The grids use the following sheet and table versions.

| StatementType | Sheet | Sheet version | Table | Table version |
| --- | --- | --- | --- | --- |
| `BalanceSheet` | `0` | `1` | `899` | `5` |
| `IncomeStatement` | `1` | `0` | `904` | `7` |
| `CashFlow` | `9` | `1` | `906` | `4` |

Each output row represents a visible value cell in account row and column
order. Section headings are carried as metadata. The balance sheet's two
unlabelled subtotals keep their empty labels. The annual income and cash-flow
tables hide the duplicate comparison column. Hidden cells and narrative
tables remain accessible through `get_codal_tables`.

| Columns | Contents |
| --- | --- |
| `TracingNo`, `CompanyName`, `SubjectName`, `Symbol`, `FilingKind` | CODAL tracing number, page company, provider subject, page symbol (or display symbol), and original provider filing kind. A subsidiary's company label can differ from the symbol that announced the filing. |
| `StatementType`, `Scope`, `AccountLabel`, `StatementSection` | Statement name from the table above, `Separate`, original account label, and nearest applicable source section heading or `None`. |
| `ReportPeriodEndJalaliDate`, `ColumnEndJalaliDate`, `FiscalYearEndJalaliDate`, `AsOfJalaliDate` | Filing period end, the source column's measurement or reporting date, the source column's fiscal year end, and a measurement date for balance-sheet rows and cash-flow closing cash. Dates keep the source format `YYYY/MM/DD`. The cash-flow opening balance carries its column's reporting context. Its own exact opening date does not appear in the grid. |
| `PeriodBasis`, `DurationMonths` | `Current`, `ComparativeInterim`, `PriorFiscalYear`, `PriorFiscalYearEnd`, `PriorFiscalYearOpening`, or `ReportedChange`. The duration is 6 or 12 for cumulative flows, noncash transactions and per-share results. Other observations have no duration. |
| `ColumnHeading`, `ColumnAuditLabel`, `ColumnIsAudited`, `FilingIsAudited`, `IsRestated` | Original period and assurance headings, separate column and filing assurance booleans, and whether the period column is marked restated. A reported change has no assurance or restatement status. |
| `Measurement`, `Currency`, `Unit`, `Scale` | Measurement of the account row: `Stock`, `Flow`, `OpeningCash`, `ClosingCash`, `NonCashTransactions`, `ReportedCapital`, `BasicEPS`, or `NetProfitPerShare`. The unit and scale describe the individual value cell: `IRR` with scale 1,000,000, `IRR/Share` with scale 1, or `Percent` with scale 1 and no currency. Reported percentage changes keep the source's percentage-point values and have no assigned measurement date. |
| `Value`, `RawValue`, `ValuePresent` | Exact `Decimal` in reported units, original decoded value, and presence of the source `value` key. Blank text, null, an absent value key, and a reported `--` in the percentage column have `Value=None`. Reported zero is a Decimal zero. |
| `ContentSha256`, `SheetId`, `TableId`, `RowSequence`, `ColumnSequence`, `Address`, `CellOrder` | Source byte hash, CODAL sheet and table codes, source coordinates, and zero-based source cell order. |

All columns use pandas `object` dtype. The DataFrame's `attrs` preserve
`Source`, `ProviderMetadata`, `PageMetadata` and `Coverage` from Stage 1,
including revision links when present. A restated column and a corrected
filing are separate concepts. The function keeps each filing's reported
observations and leaves filing version selection to the caller.

Within each dated column, selected reported totals are checked using exact
arithmetic. The checks cover the balance sheet's asset and capital structure
totals, gross through net income, cash-flow activity subtotals, net movement
and the closing cash bridge including exchange-rate effects.
`result.attrs["Reconciliations"]` gives `StatementType`, `Address`,
`Operands` and `Status` for every check. A check with a blank operand or
total is marked `Missing`. A complete reconciliation that fails raises
`ValueError` with its cell addresses. Original cells are available through
`get_codal_tables(report)`. Cross-filing and cross-period stitching,
inferred dates, recomputation of reported values, and conversion to
standalone quarters or TTM are outside this interface.

An unrelated input raises `TypeError`. An unsupported filing, no supported
loaded or requested sheet, or an unfamiliar layout on a statement sheet
raises `ValueError`. Consolidated statements, other report durations and
template versions, comprehensive income, equity changes, diluted EPS and
dividends per share are outside the verified scope. Account labels and
source coordinates are the public identifiers for observations.

The financial audit matched 1,323 normalized observations to the original
structured payloads in ten saved sheets. All 134 within-column
reconciliations passed across the four filings below.

| Filing | Coverage |
| --- | --- |
| 1106536, Asaluyeh MAPNA Power Generation | Audited six months ended `1402/06/31`, Esfand fiscal year end, all three sheets. [Balance sheet](https://codal.ir/Reports/Decision.aspx?LetterSerial=X2OX1hOJ2JKt9DK%2bTia50Q%3d%3d&rt=0&let=6&ct=0&ft=-1&sheetId=0), [income statement](https://codal.ir/Reports/Decision.aspx?LetterSerial=X2OX1hOJ2JKt9DK%2bTia50Q%3d%3d&rt=0&let=6&ct=0&ft=-1&sheetId=1), [cash flow](https://codal.ir/Reports/Decision.aspx?LetterSerial=X2OX1hOJ2JKt9DK%2bTia50Q%3d%3d&rt=0&let=6&ct=0&ft=-1&sheetId=9). |
| 1367760, Mashhad Packaging Industries | Unaudited six months ended `1404/03/31`, Azar fiscal year end, all three sheets and audited comparison columns. [CODAL filing](https://codal.ir/Reports/Decision.aspx?LetterSerial=RmK5xMmGyadZVk3PGHle7g%3d%3d&ct=0&ft=-1&let=6&rt=0). |
| 1492894, Zayandeh Rud Fibers | Audited year ended `1404/09/30`, all three sheets. The default page is the auditor's report. Select a statement before saving. [CODAL filing](https://codal.ir/Reports/Decision.aspx?LetterSerial=FGzQQQaQQQfD4kzNX1dhFukJUWsQ%3d%3d&ct=0&ft=-1&let=6&rt=0&sheetId=1). |
| 1352953, No Andishan Sanat Foolad | Audited year ended `1403/12/30`, income statement. [CODAL income statement](https://codal.ir/Reports/Decision.aspx?LetterSerial=UujVb26Yxee2Nd2eINSrUw%3d%3d&ct=0&ft=-1&let=6&rt=0&sheetId=1). |

The sample covers restated columns. A linked original and corrected financial
statement pair still needs independent verification. For example, the current
period of 1106536 reports 274 rials of basic EPS and 275 rials of net profit
per share. Its opening cash is 69,040 million rials, while its restated
previous fiscal-year-end cash is 52,480 million rials. The current cash-flow
bridge closes at the reported 181,717 million rials.

## Coverage limits

The feasibility decision was limited go. Families such as manufacturing,
services, portfolios and financial statements use different templates and
financial conventions. This interface recognizes a shared source
representation and does not certify every family, template, or filing status.
Corrections, audits and consolidated filings can be distinguished only where
the source carries that metadata.

Automatic retrieval hands the downloaded HTML to the same parser. Predictable sheet coverage and new templates require verification against published reports.
