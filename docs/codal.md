# CODAL offline report reader and monthly activity

Stage 1 reads a local copy of a CODAL filing page and returns the structured
cells carried by that page. It keeps provider identities, native values, source
coordinates, unit notes and the original document bytes.

## Obtain a supported file

The supported representation is UTF-8 HTML, optionally with a BOM, with an
inline `var datasource = …;` JavaScript declaration whose value is JSON.
The declaration ends its script and contains `sheets`, with `tables` and `cells`
arrays. fima reads the data without running scripts or loading page resources.

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
income statement in separate responses under the same filing identity. The
browser's Save As modes were not verified. A copy from the browser is usable
only if it retains the embedded declaration. Sources: [CODAL monthly filing
1494376](https://codal.ir/Reports/Decision.aspx?LetterSerial=dz8uAPkDiymNiKygk9FSoA%3d%3d&rt=0&let=58&ct=0&ft=-1),
[monthly filing 1492711](https://www.codal.ir/Reports/Decision.aspx?LetterSerial=jpQQQaQQQqfZKLzOnAkQQQaQQQAA1yexDg%3d%3d&rt=0&let=58&ct=0&ft=-1),
[balance sheet](https://codal.ir/Reports/Decision.aspx?LetterSerial=X2OX1hOJ2JKt9DK%2bTia50Q%3d%3d&rt=0&let=6&ct=0&ft=-1&sheetId=0),
[income statement](https://codal.ir/Reports/Decision.aspx?LetterSerial=X2OX1hOJ2JKt9DK%2bTia50Q%3d%3d&rt=0&let=6&ct=0&ft=-1&sheetId=1).

If CODAL requires human verification, use its normal browser workflow and save
a copy only through permitted site and browser features. fima accepts local
files and performs no online access. CAPTCHA pages, legacy HTML grids without
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
sheets individually when needed and keep each file's provenance.

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

## Feasibility and next stage

The feasibility decision was limited go. Families such as manufacturing,
services, portfolios and financial statements use different templates and
financial conventions. This interface recognizes a shared source
representation and does not certify every family, template, or filing status.
Corrections, audits and consolidated filings can be distinguished only where
the source carries that metadata.

Stage 2 should verify permitted filing discovery and retrieval with CODAL's
operator or documented access terms. An independent retrieval layer can
hand saved documents and retrieval provenance to the local parser. Unresolved
questions include machine access terms, predictable sheet coverage and the
availability of structured data across report families. Template-specific
financial normalization requires its own validation against published reports.
