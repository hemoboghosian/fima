# fima

`fima` یک کتابخانه پایتون برای دریافت، ساختاردهی و تحلیل داده‌های بازارهای مالی ایران است. این پروژه در حال توسعه است و داده‌ها را از سرویس‌های آنلاین عمومی دریافت می‌کند؛ بنابراین تغییر یا قطعی منبع داده می‌تواند بر خروجی توابع اثر بگذارد.

## نیازمندی‌ها

- Python 3.10 یا جدیدتر
- دسترسی اینترنت برای توابعی که داده زنده یا تاریخی دریافت می‌کنند

## نصب

```powershell
py -m pip install fima
```

به‌روزرسانی به آخرین نسخه:

```powershell
py -m pip install --upgrade fima
```

نمایش نسخه نصب‌شده:

```powershell
py -c "from importlib.metadata import version; print(version('fima'))"
```

## ماژول‌های عمومی

نسخه عمومی بسته شامل این ماژول‌ها است:

- `fima.Options`: داده‌ها و محاسبات اختیار معامله
- `fima.IFB`: داده‌های فرابورس ایران و ابزارهای تأمین مالی
- `fima.IME`: داده‌های بورس کالای ایران
- `fima.TSETMC`: داده‌های نمادها، شاخص‌ها، معاملات و سهامداران
- `fima.TSEInstitutions`: فهرست نهادهای مالی
- `fima.Funds`: اطلاعات صندوق‌های سرمایه‌گذاری، NAV روزانه و ترکیب روزانه دارایی‌ها

برای جلوگیری از واردشدن نام‌های کمکی، از import صریح استفاده کنید و از `import *` استفاده نکنید.

## نمونه استفاده

### اختیار معامله

```python
from fima.Options import download_chain_contracts, ticker_info

option_info = ticker_info(ticker="ضهرم4018")
chain = download_chain_contracts(
    underlying_ticker="اهرم",
    j_date=True,
    bsm=False,
    greeks=False,
    implied_volatility=False,
)
```

دریافت سابقه نماد اختیار و دارایی پایه:

```python
from fima.Options import download_historical_data

option_history, underlying_history = download_historical_data(
    ticker="ضهرم4018",
    start_date="1404-01-01",
    end_date="1404-01-31",
)
```

محاسبات مستقل بلک–شولز–مرتون و Greeks:

```python
from fima.Options import (
    calculate_black_scholes_merton,
    calculate_delta,
    calculate_gamma,
    calculate_rho,
    calculate_theta,
    calculate_vega,
)

price = calculate_black_scholes_merton(
    s=550,
    k=28000,
    t=71 / 365,
    sigma=0.9588,
    r_f=0.3372,
    option_type="Call",
)
```

### فرابورس ایران

```python
from fima.IFB import get_all_bonds_without_coupons, get_risk_free_rate

risk_free_rate = get_risk_free_rate()
bonds = get_all_bonds_without_coupons(deprecated=False)
```

### بورس کالای ایران

```python
from fima.IME import get_all_ime_physical_trades

physical_trades = get_all_ime_physical_trades(
    start_date="1403-01-01",
    end_date="1403-12-29",
)
```

### TSETMC

```python
from fima.TSETMC import get_ticker_historical_data, get_tickers

tickers = get_tickers(tse=True, ifb=True, details=False)
history = get_ticker_historical_data(ticker="فملی")
```

### نهادهای مالی

```python
from fima.TSEInstitutions import get_all_institutions

institutions = get_all_institutions()
```

### صندوق‌های سرمایه‌گذاری

```python
from fima import get_all_funds, get_daily_navs, get_daily_asset_allocation

all_funds = get_all_funds()

navs = get_daily_navs("نام صندوق")
asset_allocation = get_daily_asset_allocation("نام صندوق")
```

توابع این ماژول به منابع آنلاین اطلاعات صندوق‌ها وابسته هستند. نام صندوق باید با نام موجود در خروجی `get_all_funds()` مطابقت داشته باشد. درخواست نامعتبر یا درخواست داده‌ای که برای صندوق در دسترس نیست می‌تواند `ValueError` ایجاد کند و ارائه‌دهنده‌ای که هنوز پشتیبانی نمی‌شود می‌تواند `NotImplementedError` ایجاد کند.

خطای اتصال، پایان مهلت درخواست، گواهی نامعتبر HTTPS یا خطای HTTP با یکی از زیرکلاس‌های `requests.RequestException` گزارش می‌شود. پاسخ خالی یا نامعتبر منبع داده می‌تواند `ValueError` ایجاد کند؛ این خطاها به خروجی خالی تبدیل نمی‌شوند. گواهی HTTPS بررسی می‌شود و تغییر وب‌سایت صندوق یا مشکل گواهی آن ممکن است دریافت داده را متوقف کند.

ارائه‌دهندگان قابل تشخیص شامل تدبیر پرداز، رایان هم‌افزا، مبنا، پیکاد، راهکار، نیکا و نوآوران هستند؛ ترکیب دارایی‌های نیکا هنوز پشتیبانی نمی‌شود. پشتیبانی از یک ارائه‌دهنده به معنای در دسترس بودن همه وب‌سایت‌های آن نیست. خروجی `get_all_funds()` شامل صندوق‌های بازارگردانی نیز می‌شود. در صورت وجود چند نشانی، نخستین نشانی موجود انتخاب می‌شود و `WebsiteAddress` فقط نام میزبان را نگه می‌دارد.

این فهرست خود صندوق‌های بازارگردانی را برمی‌گرداند، نه تک‌تک سهام، صکوک یا گواهی‌های سپرده‌ای که آن‌ها بازارگردانی می‌کنند. بخش‌های مستقل صندوق‌های غیر بازارگردانی در فهرست حفظ می‌شوند؛ بنابراین ممکن است چند نام صندوق یا بخش صندوق شماره ثبت یکسانی داشته باشند.

داده‌های نمودار تدبیر پرداز بر اساس تاریخ به هم متصل می‌شوند و فقط تاریخ‌های مشترک سری‌های موردنیاز برگردانده می‌شوند. تکرار نقطه با تاریخ و مقدار کاملاً یکسان حذف می‌شود؛ مقادیر متفاوت برای تاریخ یکسان، سری تکراری و تکرار صفحه گزارش ترکیب دارایی‌ها با `ValueError` گزارش می‌شود.

تاریخچه NAV مبنا تا زمان فعلی درخواست می‌شود و به تاریخ ثابت گذشته محدود نیست؛ داده‌های موجود همچنان به پاسخ ارائه‌دهنده وابسته‌اند.

ترکیب روزانه دارایی‌های رایان هم‌افزا از هر دو قالب جدید و قدیمی پشتیبانی می‌کند. اگر مسیر جدید موجود نباشد یا قالب پاسخ آن متفاوت باشد، مسیر قدیمی بررسی می‌شود؛ خطای شبکه یا محدودیت نرخ درخواست پنهان نمی‌شود.

دریافت تاریخچه صندوق‌های بازارگردانی نیز امتحان می‌شود. در سایت‌های چندسبدی رایان، NAV خود صندوق از تاریخچه تجمیعی دریافت می‌شود؛ NAV سبد شماره ۱ جایگزین NAV صندوق نیست. اگر سایت فقط ترکیب دارایی سبدهای زیرمجموعه را ارائه کند و داده صندوق اصلی در دسترس نباشد، `NotImplementedError` گزارش می‌شود.

برای بخش‌های صندوق تدبیر پرداز، شناسه سبد از نام بخش در انتخابگر خود سایت تعیین می‌شود؛ `GroupId` فیپیران به‌طور حدسی به شناسه سبد تبدیل نمی‌شود. نبودن نام یا مبهم بودن آن خطا ایجاد می‌کند. بنابراین نام صندوق مادر در فیپیران، وقتی سایت فقط نام بخش‌ها را دارد، الزاماً تاریخچه مستقلی ندارد. در سایت‌های چندصندوقی رایان و مبنا نیز شناسه از فهرست عمومی ارائه‌دهنده و نام یا نماد صندوق تعیین می‌شود.

قالب جدید NAV اهرمی تدبیر پرداز شامل `Subscription`، `Redemption` و `Statistical` برای واحدهای عادی و `SpecialSubscription`، `SpecialRedemption` و `SpecialStatistical` برای واحدهای ممتاز است. ستون `Common` در قالب قدیمی، وقتی منبع آن را ارائه کند، حفظ می‌شود. قالب‌های NAV اهرمی با NAV صندوق‌های عادی یکسان نیستند؛ ستون‌ها و واحد مقادیر را پیش از مقایسه بررسی کنید.

ترکیب دارایی مبنا از گزارش عمومی جدید `/api/v2/public/reports/daily-assets` دریافت می‌شود و در صورت نبودن آن، مسیر قدیمی بررسی می‌شود. صفحه‌بندی اعلام‌شده توسط منبع تکمیل می‌شود؛ تکرار صفحه یا تغییر تعداد رکوردها خطا ایجاد می‌کند. دارایی‌های اضافی گزارش مبنا با ستون مقدار و ستون `Weight` حفظ می‌شوند. در گزارش تدبیر پرداز نیز ستون‌های موجود برای گواهی سپرده کالایی (`CCDs`)، اختیار معامله (`Options`)، پروژه در جریان ساخت (`ConstructionProjects`) و دارایی ثابت (`FixedAssets`) همراه با وزنشان حفظ می‌شوند. هر دانلود فقط یک بار فهرست فیپیران را حل می‌کند و اطلاعات صندوق و اتصال HTTP همان فراخوانی را تا پایان آن نگه می‌دارد؛ نشست‌ها بین فراخوانی‌ها مشترک نیستند.

این پشتیبانی تضمین دانلود همه صندوق‌ها نیست: گواهی نامعتبر، سایت غیرقابل دسترس، نبودن داده عمومی، نام‌های متفاوت یا ارائه‌دهنده پشتیبانی‌نشده همچنان می‌توانند مانع دریافت شوند. بررسی HTTPS برای رفع این محدودیت‌ها غیرفعال نمی‌شود.

## API عمومی

### `fima.Options`

- `ticker_info`
- `download_historical_data`
- `download_chain_contracts`
- `download_market_watch`
- `download_all_underlying_assets`
- `black_scholes_merton`
- `get_greeks`
- `get_implied_volatility`
- `calculate_black_scholes_merton`
- `calculate_delta`
- `calculate_gamma`
- `calculate_theta`
- `calculate_vega`
- `calculate_rho`

### `fima.IFB`

- `get_risk_free_rate`
- `get_all_bonds_without_coupons`
- `get_all_bonds_with_coupons`
- `get_ifb_equally_weighted_total_index_historical_data`
- `get_ifb_equally_weighted_price_index_historical_data`
- `get_ifb_price_index_historical_data`
- `get_ifb_total_index_historical_data`
- `get_ifb_total_sukuk_index_historical_data`
- `get_sukuk_daily_trades_based_on_bs`
- `get_sukuk_daily_trades_based_on_ct`
- `get_all_crowdfunding_plans`
- `get_all_crowdfunding_platforms`
- `get_all_standard_financing_instruments`
- `get_all_special_financing_instruments`
- `get_ticker_info`

### `fima.IME`

- `get_all_ime_physical_trades`
- `get_all_ime_futures_trades`
- `get_all_ime_option_trades`
- `get_all_physical_producer_products`
- `get_producer_physical_trades`
- `get_all_ime_export_trades`
- `get_all_ime_cd_trades`
- `get_all_export_producer_products`
- `get_producer_export_trades`
- `get_all_ime_salaf_trades`
- `get_gold_and_silver_cd_trades`

### `fima.TSETMC`

- `get_share_changes`
- `get_price_adjustments`
- `get_supervision_lists`
- `get_ticker_historical_shareholders`
- `get_ticker_historical_trades_client_type`
- `get_ticker_historical_market_caps`
- `get_ticker_historical_data`
- `get_ticker_intraday_trades`
- `get_indexes_status`
- `get_index_historical_data`
- `get_index_last_intraday_data`
- `get_index_companies`
- `get_tickers`

### `fima.TSEInstitutions`

- `get_all_institutions`

### `fima.Funds`

- `get_all_funds`
- `get_daily_navs`
- `get_daily_asset_allocation`

پارامترهایی که با `_` شروع می‌شوند برای کنترل داخلی و آزمون هستند و بخشی از API پایدار عمومی محسوب نمی‌شوند.

در `fima.Funds`، واردسازی با `*` و فراخوانی `dir()` فقط سه تابع عمومی بالا را نمایش می‌دهند. توابع کمکی و وابستگی‌های داخلی در این فهرست‌ها ظاهر نمی‌شوند، ولی دسترسی صریح به آن‌ها همچنان ممکن است؛ پایتون آن‌ها را خصوصی و غیرقابل دسترسی نمی‌کند. نمایش تکمیل خودکار در ویرایشگرها ممکن است متفاوت باشد. پارامتر `_set_website_developers` برای سازگاری حفظ شده و همچنان در امضای واقعی `get_all_funds` دیده می‌شود؛ برای دریافت فهرست صندوق‌ها کافی است `get_all_funds()` را فراخوانی کنید.

## توسعه و آزمون

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --editable ".[test]"
python -m pytest -m "not integration"
python -m pytest
```

دستور اول آزمون‌های قطعی و بدون شبکه را اجرا می‌کند. دستور دوم کل مجموعه، شامل آزمون‌های اتصال به منابع زنده، را اجرا می‌کند.

بخش قابل‌توجهی از آزمون‌ها به سرویس‌های آنلاین متصل می‌شوند. تمام آزمون‌های قطعی و بدون شبکه شرط انتشار هستند. آزمون‌های زنده جداگانه اجرا می‌شوند و خطای شبکه یا تغییر API منبع داده باید از خطای منطقی کتابخانه تفکیک، بررسی و پیش از انتشار گزارش شود.

## پیوندها

- GitHub: https://github.com/hemoboghosian/fima
- PyPI: https://pypi.org/project/fima/

## مجوز

این پروژه تحت مجوز MIT منتشر می‌شود. متن کامل در فایل `LICENSE` قرار دارد.

## تماس

- HemoBoghosian@gmail.com
