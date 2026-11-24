# fima

با این کتابخانهٔ پایتون می‌توانید داده‌های بازارهای مالی ایران را برای تحلیل و پژوهش دریافت کنید؛ از تاریخچهٔ سهام و اطلاعات صندوق‌ها تا قیمت طلا و ارز، اختیار معامله، بورس کالا، سری‌های بانک مرکزی، مسکن و شاخص‌های اقتصادی IMF.

## نصب

به پایتون نسخهٔ ۳٫۱۰ یا جدیدتر نیاز دارید:

```shell
pip install fima
```

## شروع سریع

برای دریافت تاریخچهٔ خام قیمت سهام، نام نماد را وارد کنید:

```python
from fima import get_ticker_historical_data

history = get_ticker_historical_data(ticker="فملی")
if history is not None:
    print(history[["ClosingPrice", "TradeVolume"]].head())
```

خروجی جدول پانداس با نمایهٔ `JalaliDate` است؛ تاریخ شمسی به‌شکل رشتهٔ `YYYY-MM-DD` برمی‌گردد. `ClosingPrice` قیمت پایانی رسمی به ریال و `TradeVolume` حجم معاملات است. ترتیب منبع حفظ می‌شود؛ پیش از محاسبهٔ بازده، تاریخ‌ها را مرتب کنید.

برای افزودن ستون‌های قیمت تعدیل‌شده، `adjust_prices=True` را وارد کنید. قیمت خام حفظ می‌شود و مبنا آخرین مشاهدهٔ برگشتی است. این تعدیل بر پایهٔ قیمت مرجع بورس است و سری بازده کل تأییدشده نیست؛ [روش و مثال انتخاب تاریخ مبنا](https://github.com/hemoboghosian/fima/blob/master/docs/tsetmc-adjustment.md).

### گزارش‌های کدال با نام فارسی

نماد، نام گزارش و ماه پایان دوره را وارد کنید. خروجی گزارش کدال یک
DataFrame پانداس است.

```python
from fima import get_codal_data

df = get_codal_data(
    symbol="فولاد",
    report_type="گزارش عملکرد ماهانه",
    period="1405/06",
    interactive=True,
)
print(df[["ProductName", "PeriodBasis", "Metric", "Value", "Unit", "Scale"]].head())
```

با نصب عادی fima، وابستگی Playwright هم نصب می‌شود. اگر کدال تأیید انسانی
بخواهد، `interactive=True` صفحهٔ کدال را در Google Chrome نصب‌شده باز می‌کند.
اگر Chrome ندارید، یک‌بار `python -m playwright install chromium` را اجرا کنید.
خطای HTTP 429 به‌معنی محدودیت موقت دسترسی از طرف کدال است. درخواست را بلافاصله
تکرار نکنید و اگر `Retry-After` اعلام شد، تا پایان مهلت صبر کنید.

[راهنمای صورت‌های مالی، نام گزارش‌ها و پوشش کدال](https://github.com/hemoboghosian/fima/blob/master/docs/codal.md)

## چه داده‌هایی در دسترس است؟

| منبع | کاربرد و راهنما |
| --- | --- |
| TSETMC | [نمادها، قیمت سهام، شاخص‌ها، معاملات و سهامداران](https://github.com/hemoboghosian/fima/blob/master/docs/tsetmc.md) |
| Funds | [فهرست فیپیران و تاریخچهٔ NAV و ترکیب دارایی از وب‌سایت صندوق](https://github.com/hemoboghosian/fima/blob/master/docs/funds.md)؛ [فهرست و جزئیات مستقل صندوق‌های TSETMC](https://github.com/hemoboghosian/fima/blob/master/docs/tsetmc-funds.md) |
| TGJU | [کشف نماد و قیمت‌های طلا، ارز و بازارهای جهانی](https://github.com/hemoboghosian/fima/blob/master/docs/tgju.md) |
| Options | [زنجیره، قراردادها، تاریخچه، قیمت‌گذاری و Greeks](https://github.com/hemoboghosian/fima/blob/master/docs/options.md) |
| IFB | [اوراق بدهی، بازده، شاخص‌ها، تأمین مالی و ارزش بازار فرابورس](https://github.com/hemoboghosian/fima/blob/master/docs/ifb.md) |
| IME | [معاملات فیزیکی، صادراتی، آتی، اختیار، گواهی سپرده و سلف](https://github.com/hemoboghosian/fima/blob/master/docs/ime.md) |
| CBI | [نرخ‌های سیاستی، تورم و دو مجموعهٔ مستقل نرخ ارز](https://github.com/hemoboghosian/fima/blob/master/docs/cbi.md) |
| KILID | [محدوده‌ها و میانهٔ قیمت پیشنهادی آگهی آپارتمان](https://github.com/hemoboghosian/fima/blob/master/docs/kilid.md)؛ قیمت آگهی با معاملهٔ قطعی تفاوت دارد |
| کدال | [دریافت گزارش و صورت‌های مالی با نام فارسی](https://github.com/hemoboghosian/fima/blob/master/docs/codal.md) |
| IMF | [کشف شاخص و دریافت سری‌های سالانهٔ منتخب WEO](https://github.com/hemoboghosian/fima/blob/master/docs/imf.md)؛ شامل برآورد و پیش‌بینی نیز می‌شود |
| TSEInstitutions | [فهرست نهادهای مالی](https://github.com/hemoboghosian/fima/blob/master/docs/markets.md#financial-institution-directory) |

## نام یا شناسهٔ معتبر را چطور پیدا کنم؟

ابتدا فهرست همان منبع را دریافت کنید و مقدار ستون معرفی‌شده در راهنما را به تابع بعدی بدهید. نام نمایشی، کد ابزار، شماره ثبت صندوق و شناسهٔ وب‌سایت فرابورس یکسان نیستند.

برای سهام، `get_tickers(tse=True, ifb=True)` ستون‌های `Ticker` و `InstrumentCode` را می‌دهد. برای شاخص‌ها، نام را از نمایهٔ `get_indexes_status()` انتخاب کنید. [فهرست کامل توابع](https://github.com/hemoboghosian/fima/blob/master/docs/api.md) امضا و راهنمای هر بخش را دارد.

### کشف نماد TGJU و دریافت تاریخچه

```python
from fima import get_tgju_categories, get_tgju_instruments, get_tgju_history

print(get_tgju_categories())
matches = get_tgju_instruments("ارز", search="دلار")
print(matches[["Symbol", "InstrumentName", "Category", "Currency"]])
selected = matches.loc[matches["InstrumentName"].eq("دلار")]
if len(selected) == 1:
    symbol = selected.iloc[0]["Symbol"]
    usd = get_tgju_history(symbol, "ارز", start_date="2026-10-01", end_date="2026-10-15")
    print(usd[["GregorianDate", "ClosingPrice"]].tail())
    print(usd.attrs)
```

نماد را از ستون `Symbol` ردیف مطلوب بردارید؛ نام فارسی و انگلیسی هم پذیرفته می‌شود، اما نام مبهم خطا می‌دهد. `category` خانوادهٔ کشف‌شده است؛ ستون `Category` فهرست می‌تواند زیرگروه متفاوتی باشد. اگر نتیجهٔ دلخواه در صفحه نیست، با توجه به `attrs["HasMore"]` صفحهٔ بعد را بررسی کنید. تاریخ‌های این مثال میلادی‌اند؛ واحد و منشأ تاریخچه در `attrs` قرار دارد.

### انتخاب صندوق

```python
from fima import get_all_funds, get_daily_navs

funds = get_all_funds()
print(funds[["FundName", "FundTypeName", "WebsiteAddress"]].head())
selected = funds.loc[funds["FundName"].eq("ثروت آفرین تمدن")]
if len(selected) == 1:
    navs = get_daily_navs(selected.iloc[0]["FundName"])
    print(navs.head())
```

فهرست فیپیران وجود تاریخچه در وب‌سایت صندوق را تضمین نمی‌کند. NAV هر واحد، ارزش کل دارایی‌ها و واحدهای عادی/ممتاز را جدا نگه دارید. برای اطلاعات منبع TSETMC، ابتدا `get_tsetmc_fund_types()`، سپس `get_tsetmc_funds(fund_type)` و `get_tsetmc_fund_details(...)` را به‌کار ببرید؛ شناسه‌های نوع صندوق در این دو منبع قابل جایگزینی نیستند.

### مقایسهٔ شاخص اقتصادی دو کشور

```python
from fima import get_imf_indicators, get_imf_countries, get_imf_series

print(get_imf_indicators(search="GDP"))
print(get_imf_countries())
growth = get_imf_series("NGDP_RPCH", ["IRN", "USA"], 2020, 2027)
print(growth[["Country", "Period", "Value", "Unit"]])
print(growth.attrs["IndicatorMetadata"])
print(growth.attrs["Coverage"])
```

کد شاخص را از `Indicator` و شناسهٔ کشور یا گروه را از `Country` بردارید. واحد منبع، نسخهٔ داده و پوشش را پیش از مقایسه بررسی کنید؛ همهٔ مشاهدات دادهٔ قطعی نیستند. برای KILID نیز `get_kilid_areas()` مسیر کشف شناسهٔ `Area` است؛ انتخاب‌های تاریخچه `6m`، `1y` و `3y` و واحدها `toman`، `usd` و `gold` هستند.

### مقایسهٔ قراردادهای اختیار

```python
from fima import download_market_watch, calculate_contract_metrics

watch = download_market_watch(stack="Vertical")
print(watch[["UnderlyingTicker", "Ticker", "InstrumentCode", "EndJalaliDate", "StrikePrice"]])
code = input("کد ابزار قرارداد موردنظر را از جدول وارد کنید: ").strip()
selected = watch.loc[watch["InstrumentCode"].eq(code)]
if len(selected) != 1:
    raise ValueError("یک قرارداد مشخص از جدول انتخاب کنید.")
comparison = calculate_contract_metrics(selected, price="Ask")
print(comparison[["Ticker", "QuoteStatus", "TimeValue", "PremiumPerContract"]])
```

محاسبه روی جدول دریافت‌شده انجام می‌شود و درخواست شبکهٔ دیگری ندارد. پیش از انتخاب، دارایی پایه، سررسید، نوع اختیار و قیمت اعمال را بررسی کنید. قیمت‌ها ریال به‌ازای هر سهم یا واحد پایه‌اند؛ `PremiumPerContract` با اندازهٔ همان قرارداد، مبلغ ریالی یک قرارداد را نشان می‌دهد. مظنهٔ فروش تضمین اجرای خرید نیست و قیمت مفقود با قیمت دیگری جایگزین نمی‌شود. [راهنمای مقایسه و سناریوی سود/زیان سررسید](https://github.com/hemoboghosian/fima/blob/master/docs/options.md#contract-comparison) تفاوت ارزش ذاتی/زمانی، مبلغ پریمیوم و فرض‌های اعمال را توضیح می‌دهد.

## قرارداد داده‌ها و محدودیت‌ها

- نام ستون‌ها و کلیدهای پردازش‌شده انگلیسی و `PascalCase` است؛ نام تابع و پارامتر پایتون `snake_case` باقی می‌ماند.
- تاریخ روزانهٔ شمسی رشتهٔ لاتین `YYYY-MM-DD` و تاریخ میلادی در جای مناسب datetime پانداس است. دادهٔ ماهانه و سالانه تاریخ روزانهٔ ساختگی ندارد.
- درصدهای جدول‌ها واحد درصد هستند: `2.5` یعنی `2.5%`. ورودی نرخ و نوسان توابع تحلیلی اعشاری است؛ واحد Greeks و فرض نرخ در [راهنمای اختیار](https://github.com/hemoboghosian/fima/blob/master/docs/options.md#analytics) آمده است.
- واحد پول و مقدار فیزیکی منبع بدون تبدیل حفظ می‌شود. ریال، تومان، مقدار هر گواهی و تعداد قرارداد را با هم یکی نگیرید.
- دادهٔ مفقود صفر نیست. داده‌ها به دسترسی و پوشش منبع وابسته‌اند و می‌توانند قدیمی باشند. رفتار خطا، خروجی خالی یا `None` در توابع قدیمی یکسان نیست؛ راهنمای همان تابع را بخوانید.

[قرارداد کامل داده‌ها](https://github.com/hemoboghosian/fima/blob/master/docs/data-conventions.md)، [مثال‌های بازارها](https://github.com/hemoboghosian/fima/blob/master/docs/markets.md) و [راهنمای مهاجرت نسخه‌های قدیمی](https://github.com/hemoboghosian/fima/blob/master/docs/data-migration.md) جزئیات بیشتری دارند. این کتابخانه مستقل از ارائه‌دهندگان داده است؛ شرایط استفاده و محدودیت‌های هر منبع را رعایت کنید.

## مشارکت و گزارش مشکل

برای [گزارش مشکل](https://github.com/hemoboghosian/fima/issues)، نسخهٔ نصب‌شده، نام تابع، نمونهٔ کوتاه کد و متن خطا را بنویسید. روش نصب توسعه و آزمون‌های قطعی/زنده در [راهنمای مشارکت](https://github.com/hemoboghosian/fima/blob/master/docs/development.md) آمده است.

پروژه با [مجوز ام‌آی‌تی](https://github.com/hemoboghosian/fima/blob/master/LICENSE) منتشر می‌شود. نسخهٔ قابل نصب در [پای‌پی‌آی](https://pypi.org/project/fima/) و راه تماس در [اطلاعات پروژه](https://github.com/hemoboghosian/fima/blob/master/pyproject.toml) قرار دارد.
