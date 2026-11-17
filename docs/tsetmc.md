# راهنمای سهام و شاخص‌ها

[User guide](../README.md)

برای دریافت فهرست نمادهای بورس و فرابورس یا تاریخچهٔ روزانه، از توابع زیر استفاده کنید:

```python
from fima.TSETMC import get_ticker_historical_data, get_tickers

tickers = get_tickers(tse=True, ifb=True, details=False)
history = get_ticker_historical_data(ticker="فملی")
print(history[["ClosingPrice", "TradeVolume"]].head())
```

برای انتخاب بازارها، هر دو آرگومان `tse` و `ifb` را مشخص کنید. گزینهٔ `details=True` جزئیات بیشتری به فهرست نمادها اضافه می‌کند.

در تاریخچه، نام نماد با آرگومان `ticker` انتخاب می‌شود. اگر کد ابزار را می‌دانید، می‌توانید به‌جای نام از آرگومان `ticker_instrument_code` استفاده کنید. خروجی یک جدول پانداس با نمایهٔ تاریخ شمسی است؛ تاریخچه در این تابع فیلتر تاریخی ندارد. ستون‌های قیمت، تعداد و حجم معاملات از منبع دریافت می‌شوند و ترتیب برگشتی حفظ می‌شود.

ستون `ClosingPrice` قیمت پایانی رسمی، ستون `LastPrice` آخرین قیمت معامله و ستون `YesterdayPrice` قیمت مرجع بورس است. قیمت مرجع الزاماً با قیمت پایانی ردیف قبلی برابر نیست.

برای دریافت قیمت تعدیل‌شده، از گزینهٔ `adjust_prices=True` استفاده کنید. روش محاسبه، انتخاب تاریخ مبنا، ستون‌های افزوده و محدودیت‌ها در [راهنمای تعدیل قیمت](tsetmc-adjustment.md) آمده است.

دریافت داده به دسترسی منبع وابسته است و خطاهای شبکه منتشر می‌شوند. اگر نام نماد پیدا نشود، رفتار فعلی تابع تاریخچه چاپ پیام و برگرداندن `None` است؛ پیش از استفاده از خروجی یک نام نامطمئن، نتیجه را بررسی کنید.

برای کشف توابع شاخص‌ها، معاملات درون‌روزی و سهامداران، [فهرست توابع عمومی](api.md) را ببینید.

## کشف و انتخاب ابزار

```python
from fima import get_tickers, get_ticker_historical_data

tickers = get_tickers(tse=True, ifb=True)
selected = tickers.loc[tickers["Ticker"].eq("فملی")]
if len(selected) == 1:
    history = get_ticker_historical_data(ticker_instrument_code=selected.iloc[0]["InstrumentCode"])
    print(history.sort_index()[["ClosingPrice", "TradeVolume"]].tail())
```

`ticker_instrument_code` بر `ticker` مقدم است؛ این تنها تابع تاریخچهٔ این بخش با انتخاب مستقیم کد است. توابع نام‌محور، نام دقیق را در جستجوی منبع حل می‌کنند و رفتار قدیمی انتخاب نخستین تطابق را دارند. یک نام مشترک را هویت قطعی ندانید. فهرست `get_tickers` از شرکت‌های شاخص‌های منتخب دریافت می‌شود؛ فهرست جامع ابزارهای منقضی یا مشتقه نیست.

`details=False` ستون `Ticker` را نگه می‌دارد؛ `details=True` آن را به نمایه می‌برد و برای هر نماد اطلاعات کدال می‌گیرد. نبودن اطلاعات تکمیلی پیام چاپ می‌کند و مقدار را خالی می‌گذارد. هر دو پرچم بازار `False` نیز پیام و جدول خالی می‌دهد.

## شاخص‌ها و اجزا

```python
from fima import get_indexes_status, get_index_historical_data, get_index_companies

indexes = get_indexes_status()
print(indexes)
if not indexes.empty:
    index_name = indexes.index[0]  # نمونه: اولین شاخص فهرست، نه توصیهٔ سرمایه‌گذاری
    levels = get_index_historical_data(index_name)
    quotes, recent_closes = get_index_companies(index_name, thirty_days_history=True)
    print(levels.sort_index().tail())
```

نام دقیق شاخص از نمایه می‌آید، نه ستون `InstrumentCode`. تاریخچه فقط `IndexValue` و نمایهٔ شمسی دارد؛ معنی شاخص قیمت/کل تابع انتخاب شماست. `get_index_last_intraday_data(index)` آخرین روز موجود را با تاریخ و ساعت می‌دهد، بدون انتخاب روز تاریخی. `get_index_companies` همیشه دو جدول می‌دهد؛ با پیش‌فرض `thirty_days_history=False` جدول دوم خالی است. این داده عضویت تاریخی شاخص را بازسازی نمی‌کند.

## سایر خروجی‌ها و خطاهای قدیمی

| تابع | ورودی و خروجی مهم | محدودیت |
| --- | --- | --- |
| `get_share_changes()` | تغییر تعداد سهام قدیم/جدید، نماد و تاریخ شمسی | پنجرهٔ اخیر منبع؛ آرشیو کامل اقدامات شرکتی نیست |
| `get_price_adjustments()` | رویداد/قیمت مرجع، `ClosingPrice` و `UnadjustedClosingPrice` | با سری پیوستهٔ تعدیل‌شده تفاوت دارد |
| `get_supervision_lists()` | کد ابزار، نام و یک ردیف به‌ازای هر دلیل | فهرست‌های منتخب منبع، نه تاریخچهٔ جامع وضعیت |
| `get_ticker_historical_shareholders(ticker)` | نام سهامدار، تعداد سهم، درصد و تاریخ | فقط دارندگان منتشرشده؛ درخواست‌های ناموفق روزانه حذف می‌شوند |
| `get_ticker_historical_trades_client_type(ticker)` | خرید/فروش حقیقی و حقوقی؛ حجم، ارزش و تعداد مجزا | تاریخ‌های ناموفق حذف می‌شوند؛ نمایهٔ شمسی |
| `get_ticker_historical_market_caps(ticker)` | `ClosingPrice * NumberOfShares` به ریال | تعداد سهام ناموفق خالی می‌ماند؛ با ارزش بازار رسمی IFB یکی نیست |
| `get_ticker_intraday_trades(ticker)` | توالی معامله، ساعت، حجم، قیمت ریالی و `Canceled` | آخرین جلسهٔ منبع؛ معاملهٔ لغوشده حفظ می‌شود و ستون تاریخ ندارد |

توابع سهامداران/نوع مشتری در صورت شکست همهٔ روزها هم می‌توانند جدول خالی بدهند؛ خروجی موفق به‌تنهایی کامل‌بودن تاریخچه را ثابت نمی‌کند. `_max_workers=10` کنترل هم‌زمانی قدیمی این سه تابع است. خطاهای اولیهٔ جستجو/قیمت و خطاهای ساختار در سایر مسیرها می‌توانند منتشر شوند. ترتیب منبع را پیش از محاسبهٔ بازده مرتب کنید؛ روز مفقود با صفر یا روز بدون معامله یکسان نیست. ستون‌های ارزش و قیمت سهام ریالی‌اند و تعداد، حجم و درصد هرکدام معنی مستقل دارند.
