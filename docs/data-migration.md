# Unreleased public-data migration

These changes are **breaking output contracts**, pending release review. No
function or public parameter has been renamed. Do not retain old and new columns
in the same frame. Unlisted fields retain their meanings/units.

## TSETMC and Options

| Old public name | New public name | Scope |
| --- | --- | --- |
| ClosePrice | ClosingPrice | Price tables and adjustment input |
| FirstPrice | OpeningPrice | Daily prices and adjustment input |
| MinPrice / MaxPrice | LowPrice / HighPrice | Daily prices and adjustment input |
| AdjustedClosePrice / AdjustedFirstPrice / AdjustedMinPrice / AdjustedMaxPrice | AdjustedClosingPrice / AdjustedOpeningPrice / AdjustedLowPrice / AdjustedHighPrice | Adjusted history |
| NotAdjustedClosePrice | UnadjustedClosingPrice | TSETMC price adjustments |
| TransactionNo / TransactionsNo | TransactionCount | TSETMC daily/company tables and adjustment input |
| Volume / Value | TradeVolume / TradeValue | TSETMC trade/company tables |
| TransitionsNo | TradeNumber | TSETMC intraday sequence, **not a count** |
| SharesNo | NumberOfShares | Shareholder and market-cap tables |
| Name | InstrumentName or ShareholderName | TSETMC instrument or shareholder tables |
| JDate / GDate | JalaliDate / GregorianDate | Columns, indexes, adjustment input |
| Value / MinValue / MaxValue | IndexValue / LowIndexValue / HighIndexValue | TSETMC index tables |
| HourMinute | Time | TSETMC index snapshot |
| Date / Quantity / Volume / Value | JalaliDate / TransactionCount / TradeVolume / TradeValue | Option/underlying daily history |
| Volume-C, Volume-P | CallTransactionCount, PutTransactionCount | Option watch/chain; old volume was actually count |
| Quantity-C, Quantity-P | CallTradeVolume, PutTradeVolume | Option watch/chain; old quantity was contract volume |
| *-C / *-P / *-UA | Call* / Put* / Underlying* | All option watch/chain columns, applying base renames above |
| Name / Type | InstrumentName / OptionType | Vertical option watch |
| UATicker / LastPrice-UA / Type | UnderlyingTicker / UnderlyingLastPrice / OptionType | ticker_info |
| BeginDate / EndDate | BeginJalaliDate / EndJalaliDate, or BeginGregorianDate / EndGregorianDate | Option watch/chain, selected by existing j_date |
| MaturityDate | MaturityJalaliDate | Option ticker_info |

The suffix rule also covers Ticker, InstrumentCode, Status, TradeValue,
NotionalValue, OpenPositions, ClosingPrice, LastPrice, YesterdayPrice, BidPrice,
BidVolume, AskPrice, AskVolume, URL, and optional BSMPrice/Volatility/Greeks/
ImpliedVolatility columns. The underlying-extraction function strips the new
Underlying prefix and returns the same canonical base names.

Jalali date columns/indexes now contain canonical strings instead of jdatetime
objects. Option Gregorian event dates are datetime64[ns] instead of Python date
objects. Time is HH:MM:SS text instead of datetime.time/packed integers.
InstrumentCode columns are pandas string dtype, preserving source leading zeros.
Prices, quantities, share counts, index levels and client fields parse formatted
numbers; integer/float inference is retained rather than forcing every quantity
to nullable integers. Empty known daily-history schemas have numeric columns.
Option ticker_info's initially object-typed financial fields become numeric.
DataFrame RiskFreeRate, Volatility and ImpliedVolatility change from decimal
fractions to percentage points; scalar analytical API units stay decimal.

Behavioral corrections: official client `I` fields map to Retail and `N` to
Institutional; index high/low source mappings are corrected; options map keys
rather than JSON object positions; Mibian receives r_f*100; historical volatility
uses the trailing window in date order with sqrt(252) annualization. Zero
volatility pricing uses discounted intrinsic value, and expiry pricing avoids
undefined divisions. Option history supports either inclusive date bound and
returns ascending dates. Provider zero opening prices remain zero; index and
market-cap calculations are not redefined.

Evidence: official TSETMC [frontend](https://tsetmc.ir/), option/closing/client API
responses inspected during the audit, and [Mibian source](https://github.com/yassinemaaroufi/MibianLib/blob/master/mibian/__init__.py).


## Funds

| Old public name | New public name | Scope |
| --- | --- | --- |
| Name / FundType / RegNo | FundName / FundTypeName / RegistrationNumber | Fipiran catalog |
| InceptionDate / UpdateDate | InceptionJalaliDate / UpdateJalaliDate | Fipiran catalog |
| DividendFrequency (Month) | DividendFrequencyMonths | Fipiran catalog |
| Upper5%Stocks / Upper5%Bonds | TopFiveStocks / TopFiveBonds | Allocations/concentration; **five holdings, not five percent** |
| * Weight | *Weight | All allocation/catalog columns, after the TopFive rename |
| Others Weight / Bank CDs Weight | OtherAssetsWeight / DepositWeight | Catalog; deposit subtype is not inferred |
| JDate / Date | JalaliDate | Website NAV / allocation histories |
| Subscription / Redemption / Statistical | SubscriptionNAV / RedemptionNAV / StatisticalNAV | Website histories, always per unit |
| SubscriptionPerUnit / RedemptionPerUnit / StatisticalPerUnit | SubscriptionNAV / RedemptionNAV / StatisticalNAV | Leveraged Mabna |
| CommonSubscriptionPerUnit | OrdinarySubscriptionNAV | Leveraged Mabna |
| SpecialSubscription / SpecialRedemption / SpecialStatistical | PreferredSubscriptionNAV / PreferredRedemptionNAV / PreferredStatisticalNAV | Leveraged Tadbir |
| TotalPrefferedUnits | TotalPreferredUnits | Leveraged Mabna spelling correction |
| TotalNAV | TotalSubscriptionNAV | Ordinary Mabna subscription-basis total (source buy-commission valuation) |
| total_net_asset_value_with_buy_commission_and_discount / total_net_asset_value_with_sell_commission_and_discount | TotalSubscriptionNAV / TotalRedemptionNAV | Leveraged Mabna, where supplied |
| Non-English additional asset columns | ProviderAssets nested mapping | Unknown source labels/values preserved as metadata |

All remaining source snake_case fields in leveraged Mabna frames use PascalCase
formed from the same words. No semantic renaming is inferred for unknown fields.
The legacy Tadbir `Common` remains distinct and its subtype remains unspecified.

TSETMC snapshot renames (the **detail dict is unchanged**):

| Source/public old key | New column |
| --- | --- |
| regNo / mfName / mfNameEng | RegistrationNumber / FundName / FundEnglishName |
| name / nameEN | ProviderName / ProviderNameEN |
| fixIncome / fundType / fundSize | FundTypeID / ProviderFundTypeCode / ProviderFundSize |
| recordDate / initiationDate | UpdateGregorianDate / InceptionGregorianDate |
| navSub / navRed / navStat / netAsset | SubscriptionNAV / RedemptionNAV / StatisticalNAV / TotalNAV |
| portfolioFiveBest / portfolioStock / portfolioBond | TopFiveStocksWeight / StocksWeight / BondsWeight |
| portfolioDeposit / portfolioOther / portfolioCash | DepositWeight / OtherAssetsWeight / CashWeight |
| dividentIntervalPeriod | DividendFrequencyMonths |
| day1Return / day7Return / day30Return / day90Return / day180Return / day365Return / dayFirstReturn | DailyReturn / WeeklyReturn / MonthlyReturn / QuarterlyReturn / SemiAnnualReturn / AnnualReturn / ReturnFromInception |

All other snapshot keys capitalize their existing initial letter (`stats` ?
`Stats`, `fundProfits` ? `FundProfits`, etc.); nested payload keys stay raw. The
source group `fixIncome` is not interchangeable with source `fundType` or with
Fipiran identifiers. Type-discovery FundTypeID values are also strings; numeric
and named function arguments remain accepted. Fipiran adds FundTypeID alongside
the mapped display name, and preserves unknown InvestmentType source labels
instead of calling every non-Negotiable value Open-Ended.

Dtypes: website/catalog Jalali dates are strings; TSETMC Gregorian dates are
`datetime64[ns]`; registration/instrument/group/type/SEO IDs are strings. NAVs,
amounts, weights, returns and dividend months parse numeric strings. Dividend
months no longer mix numbers and '-'; zero stays numeric zero. Missing weights
and optional asset values no longer become invented zeros. The provider's
RankLastUpdate timestamps preserve supplied offsets (mixed semantics may require
object dtype); no timezone is invented.

Rayan (including aggregate histories), Noavaran and Nika no longer multiply
per-unit NAV by unit counts. TotalNAV retains the provider's separate aggregate
value. Mabna totals explicitly state subscription/redemption valuation basis.
No cross-provider aggregate valuation equivalence is asserted. Unknown asset
labels and legacy Common NAV subtype are preserved without guessed translations.
Malformed TSETMC fund JSON now includes provider context with either supported
JSON backend; invalid JSON/records are still errors.

NAV evidence includes live Rayan per-share keys, Noavaran
[report](https://sepordeh.ebidar.com/), Nika's [unit-price display](https://atiyeh.mofidfund.com/)
and API, and Mabna [fund reports](https://kianfunds10.ir/). Certificate failures
and redirect/error pages at other fund sites remain provider/environment limits.
