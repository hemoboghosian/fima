# TSETMC reference-price adjustment

[User guide](../README.md) | [TSETMC guide](tsetmc.md)

## تعدیل اختیاری گذشته‌نگر بر پایهٔ قیمت مرجع

```python
from fima.TSETMC import get_ticker_historical_data, adjust_historical_prices

history = get_ticker_historical_data(
    ticker_instrument_code="35425587644337450", adjust_prices=True,
)
prices = history[["ClosingPrice", "LastPrice", "AdjustmentFactor",
                  "AdjustedClosingPrice", "AdjustedLastPrice"]]

# برای انتخاب تاریخ مبنای قدیمی‌تر، ابتدا دادهٔ خام را فیلتر کنید.
import jdatetime as jd

raw = get_ticker_historical_data(ticker="فملی")
as_of = adjust_historical_prices(raw.loc[raw.index <= jd.date(1403, 12, 29)])
```

گزینهٔ `adjust_prices` فقط به‌صورت آرگومان نام‌دار پذیرفته می‌شود و مقدار پیش‌فرض آن
`False` است؛ آرگومان‌های موقعیتی موجود، ستون‌های خام و نمایهٔ تاریخ شمسی سازگار
می‌مانند. `ClosingPrice` قیمت پایانی رسمی (`pClosing`) و `LastPrice` قیمت آخرین
معامله (`pDrCotVal`) است. `YesterdayPrice` (`priceYesterday`) قیمت مرجع بورس
است و ممکن است با قیمت پایانی مشاهدهٔ قبلی تفاوت داشته باشد.

محاسبات در ترتیب صعودی تاریخ واقعی انجام می‌شود و نسبت هر ردیف برابر است با:

```text
q[t] = YesterdayPrice[t] / ClosingPrice[t-1]
```

مقدار `AdjustmentFactor[t]` حاصل‌ضرب نسبت‌های ردیف‌های بعدی تا آخرین تاریخ
دادهٔ ورودی است؛ مقدار آن در آخرین ردیف زمانی عمداً برابر با ۱ است. ستون‌های
`AdjustedClosingPrice`، `AdjustedLastPrice`، `AdjustedOpeningPrice`،
`AdjustedLowPrice` و `AdjustedHighPrice` از ضرب قیمت خام در این ضریب ساخته می‌شوند.
همهٔ ستون‌های خام، ردیف‌ها، برچسب‌های نمایه و ترتیب خروجی، از جمله روزهای بدون
معامله، حفظ می‌شوند. حجم و ارزش معاملات، تعداد معاملات، تعداد سهام و ارزش بازار
تغییر نمی‌کنند. مقادیر با دقت `float64` و بدون گردکردن محاسبه می‌شوند؛ برای
نمایش قیمت‌های تعدیل‌شده به ریال صحیح، پس از محاسبه روی ستون‌های دلخواه
`.round(0)` اعمال کنید.

تابع `adjust_historical_prices` درخواست شبکه‌ای ندارد. در هر فراخوانی دادهٔ
یک ابزار را با شش ستون قیمت و قیمت مرجع و یکی از این تاریخ‌ها وارد کنید:
ستون میلادی `GregorianDate`، ستون شمسی `JalaliDate`، نمایهٔ `DatetimeIndex` یا نمایهٔ
`JalaliDate` خروجی fima. تاریخ‌ها باید مشخص و یکتا باشند و ستون شناسه، در صورت وجود،
باید یک ابزار مشخص را معرفی کند. ستون ناقص، تاریخ تکراری، ترکیب ابزارهای مختلف،
محاسبات نامتناهی و قیمت نامعتبر با `ValueError` گزارش می‌شود. قیمت پایانی و
قیمت مرجعِ استفاده‌شده در نسبت‌ها باید مثبت و متناهی باشند؛ قیمت مرجع قدیمی‌ترین
ردیف در محاسبه استفاده نمی‌شود. مقدار مثبت ۱۰۰۰ برای قیمت مرجع معتبر است.

منبع گاهی ستون `OpeningPrice` را حتی در روز دارای معامله صفر برمی‌گرداند. این مقدار
در ستون خام و `AdjustedOpeningPrice` به همان صورت صفر حفظ می‌شود؛ نباید آن را
قیمت واقعی معامله دانست و قیمت دیگری به‌طور حدسی جایگزین آن نمی‌شود. مقدار
منفی یا نامتناهی و دادهٔ ناموجود در این ستون همچنان خطاست. صفر در ستون‌های
`LastPrice`، `LowPrice` و `HighPrice` فقط در ردیف دارای `TransactionCount == 0`
پذیرفته می‌شود. ورودی خالی با ستون‌های لازم، ستون‌های افزودهٔ خالی برمی‌گرداند؛
ضریب ورودی تک‌ردیفی برابر با ۱ است.

تاریخ مبنای دریافت تاریخچه، آخرین مشاهدهٔ برگشتی است و فیلتر تاریخی اعمال
نمی‌شود. برای حذف اثر تغییرات پس از یک تاریخ مشخص، ابتدا دادهٔ **خام** را
فیلتر کنید و سپس تابع تعدیل را فراخوانی کنید. فیلترکردن خروجیِ ازقبل تعدیل‌شده،
مبنای اولیهٔ آن را تغییر نمی‌دهد. تغییرات بعدی قیمت مرجع می‌توانند سطح قیمت‌های
تعدیل‌شدهٔ گذشته را تغییر دهند. تمام مشاهدات ورودی، حتی در فاصله‌های زمانی،
توقف‌ها و بازگشایی‌ها، به هم متصل می‌شوند. تاریخچهٔ ناقص یا فیلترشده نمی‌تواند
کامل‌بودن جلسات معاملاتی یا علت اختلاف قیمت مرجع را اثبات کند. این خروجی،
تاریخچهٔ قیمت با تعدیل گذشته‌نگر بر پایهٔ قیمت مرجع TSETMC است؛ صحت آن به‌عنوان
سری بازده کل سرمایه‌گذار یا نحوهٔ دقیق برخورد با حق‌تقدم و آوردهٔ نقدی تأیید نشده است.

شواهد بررسی منابع و مقایسه‌ها در بخش‌های بعدی همین راهنما آمده است.

The calculation is implemented independently in fima, without importing either
comparison package or making additional requests for adjustment events.

## Source inspection

Pinned sources inspected from the published wheels:

- [finpy-tse 1.2.10](https://pypi.org/project/finpy-tse/1.2.10/),
  `finpy_tse.Get_Price_History`;
  [source repository](https://github.com/ARahimiQuant/finpy-tse).
- [pytse-client 0.19.1](https://pypi.org/project/pytse-client/0.19.1/),
  `pytse_client.download.adjust_price` and history field mappings;
  [source repository](https://github.com/Glyphack/pytse-client).

Finpy's `Final` and pytse's unadjusted `adjClose` correspond to fima's official
`ClosingPrice`. Finpy's `Close` and pytse's `close` correspond to `LastPrice`.
Column names alone do not establish adjustment status. Both implementations
use successive exchange-reference/previous-official-close ratios. Finpy
truncates adjusted values to integers; pytse rounds them to whole rials.
Fima retains floating-point precision.

Finpy substitutes previous closes for references of 0 or 1000 specifically
when stitching different market-history segments. This does not establish
that 1000 is invalid for a single instrument. Fima does not stitch instruments
or substitute missing references. It rejects instrument mixing and invalid
ratio inputs; a positive reference of 1000 is accepted.

## Bounded live comparison

Observed on 2026-10-13 for **فملی**, InsCode **35425587644337450**, with a shared
adjustment endpoint of **2026-10-12**. Requests were cached locally, used
10-second connection and 20-second read timeouts, one-second spacing and TLS
verification. Cached data and downloaded third-party sources are not committed.

The official
[daily endpoint](https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/35425587644337450/0)
returned HTTP 200 JSON without redirects: **4,673** observations from
2007-02-04 through 2026-10-12, with **367** zero-trade rows and no duplicate
dates. All closing/reference prices were positive. Zero-trade rows can have
zero first/minimum/maximum prices while their official close/reference carries
a valid level. Some reference changes occurred during zero-trade periods,
including consecutive changes on 2013-06-09 and 2013-06-10. Retaining these
rows in the chronological chain matched the independent traded-date results.
This is evidence for the sampled chain, not proof of session completeness
or economic classification for every instrument.

Both pinned packages' legacy endpoints returned 200 after HTTP-to-HTTPS 303
redirects. Their histories had **4,306** rows, omitting the **367** official
zero-trade rows. Comparisons used only matching instrument/date observations,
with the latest date aligned. The exact pinned functions were executed against
cached responses; finpy's identifier lookup was restricted to this one instrument.

| Comparison on 4,306 matching dates | Maximum official-close difference |
| --- | --- |
| Fima floating output vs finpy adjusted `Final` | < 1 rial |
| Fima truncated for comparison vs finpy | 0 |
| Fima floating output vs pytse adjusted `adjClose` | < 0.5 rial |
| Fima rounded for comparison vs pytse | 0 |
| Fima raw vs official unadjusted chart | 0 |
| Fima rounded vs official adjusted chart | 0 |

Both official charts returned HTTP 200 without redirects and contained 4,306
traded rows at the same endpoint:
[unadjusted](https://members.tsetmc.com/tsev2/chart/data/Financial.aspx?i=35425587644337450&t=ph&a=0),
[adjusted](https://members.tsetmc.com/tsev2/chart/data/Financial.aspx?i=35425587644337450&t=ph&a=1).
The chart's fifth field is last trade and its seventh field is official close;
the raw chart was checked against both corresponding daily fields before
comparing adjusted closes. These are snapshot comparisons, not permanent
availability or exact-match guarantees.

## Supporting events and limitations

### Zero opening fields on traded observations

During the 2026-10-13 investigation of Issue #36, the official daily history
for Shasta, InsCode 2400322364771558, returned a 2023-10-09 record with
`priceFirst=0`, 5,605 transactions, closing price 1,267, last trade 1,273,
minimum 1,244 and maximum 1,285. The legacy official history for the same
instrument/date supplied opening price 1,244; a subsequent daily response also
supplied 1,244. Responses varied in row coverage as well. These observations
show that a zero opening field is not evidence of zero trades or a genuine
zero execution price. The exact cause of the source discrepancy is unverified.

Fima preserves the supplied zero in both `OpeningPrice` and `AdjustedOpeningPrice`
without fetching or inferring a replacement. It does not use the opening price
in adjustment ratios, so this source value must not reject the entire chain.
Negative, missing and nonfinite opening values still fail validation. Closing
and used reference prices remain finite and positive; zero last/minimum/maximum
prices still require an explicit zero transaction count. The captured Shasta
record is covered by a mocked deterministic regression. Foolad's reported error
was reproduced in a ticker call, but subsequent responses passed; the offending
Foolad record was not captured, so its exact date is not established.

The official
[event endpoint](https://cdn.tsetmc.com/api/ClosingPrice/GetPriceAdjustList/35425587644337450)
returned 24 entries with null `corporateTypeCode`. Its two separate entries on
2011-07-05 describe before/after prices **15241 → 12991** and **12991 → 4911**.
Both were retained in the investigation, without deduplication or reliance on
response ordering. Their combined ratio agrees with that date's reference
discontinuity. The daily chain had 31 non-unit ratios, so the archive must not
be assumed complete or one-to-one with observations.

Reference gaps can reflect source corrections or other market behavior.
The helper cannot infer dividends, splits, rights or cash subscriptions from
those gaps, and does not certify investor total returns. Gaps in supplied dates
are linked as observations; callers remain responsible for data coverage.
Synthetic tests establish arithmetic and validation, not corporate-action
economics. Additional securities, market transitions and event-based economic
validation deserve separate work.
