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
- `fima.TGJU`: کشف نمادها، نمای آخرین قیمت‌ها، تاریخچهٔ روزانه و مشخصات بازارهای عمومی TGJU

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

#### تعدیل اختیاری گذشته‌نگر بر پایهٔ قیمت مرجع

```python
from fima.TSETMC import get_ticker_historical_data, adjust_historical_prices

history = get_ticker_historical_data(
    ticker_instrument_code="35425587644337450", adjust_prices=True,
)
prices = history[["ClosePrice", "LastPrice", "AdjustmentFactor",
                  "AdjustedClosePrice", "AdjustedLastPrice"]]

# برای انتخاب تاریخ مبنای قدیمی‌تر، ابتدا دادهٔ خام را فیلتر کنید.
import jdatetime as jd

raw = get_ticker_historical_data(ticker="فملی")
as_of = adjust_historical_prices(raw.loc[raw.index <= jd.date(1403, 12, 29)])
```

`adjust_prices` فقط به‌صورت آرگومان نام‌دار پذیرفته می‌شود و مقدار پیش‌فرض آن
`False` است؛ آرگومان‌های موقعیتی موجود، ستون‌های خام و نمایهٔ تاریخ شمسی سازگار
می‌مانند. `ClosePrice` قیمت پایانی رسمی (`pClosing`) و `LastPrice` قیمت آخرین
معامله (`pDrCotVal`) است. `YesterdayPrice` (`priceYesterday`) قیمت مرجع بورس
است و ممکن است با قیمت پایانی مشاهدهٔ قبلی تفاوت داشته باشد.

محاسبات در ترتیب صعودی تاریخ واقعی انجام می‌شود و نسبت هر ردیف برابر است با:
`q[t] = YesterdayPrice[t] / ClosePrice[t-1]`.
مقدار `AdjustmentFactor[t]` حاصل‌ضرب نسبت‌های ردیف‌های بعدی تا آخرین تاریخ
دادهٔ ورودی است؛ مقدار آن در آخرین ردیف زمانی عمداً برابر با ۱ است. ستون‌های
`AdjustedClosePrice`، `AdjustedLastPrice`، `AdjustedFirstPrice`،
`AdjustedMinPrice` و `AdjustedMaxPrice` از ضرب قیمت خام در این ضریب ساخته می‌شوند.
همهٔ ستون‌های خام، ردیف‌ها، برچسب‌های نمایه و ترتیب خروجی، از جمله روزهای بدون
معامله، حفظ می‌شوند. حجم و ارزش معاملات، تعداد معاملات، تعداد سهام و ارزش بازار
تغییر نمی‌کنند. مقادیر با دقت `float64` و بدون گردکردن محاسبه می‌شوند؛ برای
نمایش قیمت‌های تعدیل‌شده به ریال صحیح، پس از محاسبه روی ستون‌های دلخواه
`.round(0)` اعمال کنید.

تابع `adjust_historical_prices` درخواست شبکه‌ای ندارد. در هر فراخوانی دادهٔ
یک ابزار را با شش ستون قیمت و قیمت مرجع و یکی از این تاریخ‌ها وارد کنید:
ستون میلادی `GDate`، ستون شمسی `JDate`، نمایهٔ `DatetimeIndex` یا نمایهٔ
`JDate` خروجی fima. تاریخ‌ها باید مشخص و یکتا باشند و ستون شناسه، در صورت وجود،
باید یک ابزار مشخص را معرفی کند. ستون ناقص، تاریخ تکراری، ترکیب ابزارهای مختلف،
محاسبات نامتناهی و قیمت نامعتبر با `ValueError` گزارش می‌شود. قیمت پایانی و
قیمت مرجعِ استفاده‌شده در نسبت‌ها باید مثبت و متناهی باشند؛ قیمت مرجع قدیمی‌ترین
ردیف در محاسبه استفاده نمی‌شود. مقدار مثبت ۱۰۰۰ برای قیمت مرجع معتبر است.

TSETMC گاهی `FirstPrice` را حتی در روز دارای معامله صفر برمی‌گرداند. این مقدار
در ستون خام و `AdjustedFirstPrice` به همان صورت صفر حفظ می‌شود؛ نباید آن را
قیمت واقعی معامله دانست و قیمت دیگری به‌طور حدسی جایگزین آن نمی‌شود. مقدار
منفی یا نامتناهی و دادهٔ ناموجود در این ستون همچنان خطاست. صفر در ستون‌های
`LastPrice`، `MinPrice` و `MaxPrice` فقط در ردیف دارای `TransactionNo == 0`
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

شواهد بررسی منابع و مقایسه‌ها: [یادداشت‌های تعدیل TSETMC](https://github.com/hemoboghosian/fima/blob/master/docs/tsetmc-adjustment.md).

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

برای بخش‌های صندوق تدبیر پرداز، شناسه سبد از تطابق نام یا نماد صندوق با انتخابگر خود سایت تعیین می‌شود؛ `GroupId` فیپیران به‌طور حدسی به شناسه سبد تبدیل نمی‌شود. نبودن تطابق یا مبهم بودن آن خطا ایجاد می‌کند. بنابراین نام صندوق مادر در فیپیران، وقتی سایت فقط نام بخش‌ها را دارد، الزاماً تاریخچه مستقلی ندارد. در سایت‌های چندصندوقی رایان و مبنا نیز شناسه از فهرست عمومی ارائه‌دهنده و نام یا نماد صندوق تعیین می‌شود.

قالب جدید NAV اهرمی تدبیر پرداز شامل `Subscription`، `Redemption` و `Statistical` برای واحدهای عادی و `SpecialSubscription`، `SpecialRedemption` و `SpecialStatistical` برای واحدهای ممتاز است. ستون `Common` در قالب قدیمی، وقتی منبع آن را ارائه کند، حفظ می‌شود. قالب‌های NAV اهرمی با NAV صندوق‌های عادی یکسان نیستند؛ ستون‌ها و واحد مقادیر را پیش از مقایسه بررسی کنید.

ترکیب دارایی مبنا از گزارش عمومی جدید `/api/v2/public/reports/daily-assets` دریافت می‌شود و در صورت نبودن آن، مسیر قدیمی بررسی می‌شود. صفحه‌بندی اعلام‌شده توسط منبع تکمیل می‌شود؛ تکرار صفحه یا تغییر تعداد رکوردها خطا ایجاد می‌کند. دارایی‌های اضافی گزارش مبنا با ستون مقدار و ستون `Weight` حفظ می‌شوند. در گزارش تدبیر پرداز نیز ستون‌های موجود برای گواهی سپرده کالایی (`CCDs`)، اختیار معامله (`Options`)، پروژه در جریان ساخت (`ConstructionProjects`) و دارایی ثابت (`FixedAssets`) همراه با وزنشان حفظ می‌شوند. هر دانلود فقط یک بار فهرست فیپیران را حل می‌کند و اطلاعات صندوق و اتصال HTTP همان فراخوانی را تا پایان آن نگه می‌دارد؛ نشست‌ها بین فراخوانی‌ها مشترک نیستند.

این پشتیبانی تضمین دانلود همه صندوق‌ها نیست: گواهی نامعتبر، سایت غیرقابل دسترس، نبودن داده عمومی، نام‌های متفاوت یا ارائه‌دهنده پشتیبانی‌نشده همچنان می‌توانند مانع دریافت شوند. بررسی HTTPS برای رفع این محدودیت‌ها غیرفعال نمی‌شود.

#### اطلاعات صندوق‌ها از TSETMC

```python
import pandas as pd
from fima import get_tsetmc_fund_types, get_tsetmc_funds, get_tsetmc_fund_details

fund_types = get_tsetmc_fund_types()
stock_funds = get_tsetmc_funds("سهامی")
mixed_funds = get_tsetmc_funds("مختلط")
fund_names = mixed_funds["mfName"].tolist()

details = get_tsetmc_fund_details("آرمان سپهر آتی")
nav_history = pd.DataFrame(details.get("stats") or [])

# تعیین گروه، جست‌وجوی نام را به همان گروه محدود می‌کند.
selected_details = get_tsetmc_fund_details(
    fund_name="آرمان سپهر آتی", fund_type="مختلط"
)
```

`get_tsetmc_fund_types()` بدون درخواست شبکه، جدولی از نام فارسی گروه‌ها، نام انگلیسی قابل استفاده و شناسهٔ TSETMC می‌دهد. برای استفادهٔ معمول کافی است نام گروه را به `get_tsetmc_funds(fund_type)` بدهید؛ خروجی آن فهرست صندوق‌های همان گروه در قالب `DataFrame` است. نام‌های فارسی شامل «سهامی»، «مختلط»، «درآمد ثابت»، «بازارگردانی»، «جسورانه»، «زمین و ساختمان»، «پروژه»، «کالایی»، «خصوصی» و «صندوق» هستند. نام‌های انگلیسی جدول نیز پذیرفته می‌شوند؛ برای نمونه `equity` یا `stock` برای سهامی و `mixed` برای مختلط. «در سهام» و «سهام» نیز معادل «سهامی» پذیرفته می‌شوند. تفاوت حروف عربی و فارسی، فاصله و نیم‌فاصله و بزرگی حروف انگلیسی در انتخاب نام نادیده گرفته می‌شود.

برای سازگاری، فراخوانی‌های عددی مانند `get_tsetmc_funds(6)` و `get_tsetmc_funds(7)` همچنان معتبرند. شناسهٔ عددی هر گروه در جدول `fund_types` قابل مشاهده است و نباید با شناسهٔ فیپیران یکسان فرض شود. گزینهٔ عددی `0` برای نمایش همه در سایت استفاده می‌شود، اما هنگام بررسی پاسخ `500` داشت؛ در فهرست نام‌های پیشنهادی قرار ندارد و دریافت موفق آن تضمین نمی‌شود. جدول نام گروه‌ها به معنی تضمین دسترسی فعلی سرویس نیست.

نام ستون‌ها و ترتیب ردیف‌ها از منبع حفظ می‌شود؛ تاریخ‌ها رشته‌های میلادیِ خام هستند و مقادیر نوع دادهٔ معمول pandas را می‌گیرند. نام صندوق در `mfName`، شمارهٔ ثبت در `regNo` و گروه نمایشی در `fixIncome` است؛ ستون `fundType` الزاماً گروه انتخاب‌شده نیست. فیلدهای اضافی و تو‌در‌تو حذف یا بازنام‌گذاری نمی‌شوند. آرایهٔ معتبر و خالی `funds` یک جدول خالی بدون ستون برمی‌گرداند؛ پاسخ نامعتبر یا فاقد این آرایه خطا ایجاد می‌کند. حتی یک شناسهٔ گروه ناشناخته ممکن است از طرف منبع به‌صورت آرایهٔ خالی پاسخ داده شود.

`get_tsetmc_fund_details(fund_name)` اطلاعات کامل صندوق انتخاب‌شده با نام را در قالب `dict` برمی‌گرداند. نام کامل را از ستون `mfName` فهرست صندوق‌ها انتخاب کنید؛ برای دانستن شمارهٔ ثبت نیازی به بررسی نشانی سایت ندارید. اگر `fund_type` مشخص نشود، هر ده گروه شناخته‌شده جداگانه بررسی می‌شوند؛ این کار درخواست‌های بیشتری دارد و به دسترسی همهٔ آن گروه‌ها وابسته است. تعیین گروه با نام، مانند `fund_type="مختلط"`، جست‌وجو را به یک گروه محدود می‌کند. نام پس از یکسان‌سازی حروف عربی و فارسی، فاصله‌ها و بزرگی حروف انگلیسی باید دقیقاً مطابق باشد؛ نام ناقص یا شبیه‌ترین نام به‌طور حدسی انتخاب نمی‌شود. چند ردیف با یک شمارهٔ ثبت یک صندوق محسوب می‌شوند، اما تطابق با چند شمارهٔ ثبت، `ValueError` ایجاد می‌کند؛ گروه را مشخص کنید یا از شمارهٔ ثبت فهرست استفاده کنید. شکست دریافت یک گروه در جست‌وجوی کامل مخفی نمی‌شود.

فراخوانی‌های قبلی `get_tsetmc_fund_details(11172)` و `get_tsetmc_fund_details(reg_no=11172)` همچنان معتبرند و مستقیماً جزئیات را می‌گیرند. `reg_no` شمارهٔ ثبت است، نه کد معاملاتی ابزار؛ آن را با نام یا گروه در یک فراخوانی ترکیب نکنید. فیلدهای `stats` و `fundProfits`، در صورت ارائه توسط منبع، با ساختار و ترتیب اصلی حفظ می‌شوند. تاریخچه مرتب، تکمیل یا به تاریخ شمسی تبدیل نمی‌شود؛ جدول `nav_history` در مثال بالا فقط دادهٔ `stats` را به جدول تبدیل می‌کند. تاریخ و پوشش اطلاعات جزئیات ممکن است با فهرست صندوق‌ها متفاوت باشد؛ جدیدترین بودن و کامل بودن تاریخچه تضمین نمی‌شود.

در استفادهٔ عددی، شناسهٔ گروه باید عدد صحیح نامنفی و شمارهٔ ثبت باید عدد صحیح مثبت باشد. رشتهٔ ارقام لاتین و مقدار عددیِ بدون بخش اعشاری، مانند `11172.0` موجود در پاسخ منبع، نیز پذیرفته می‌شود؛ مقدار بولی یا مسیر به‌جای شناسه پذیرفته نمی‌شود. نام یا ورودی نامعتبر، ترکیب متعارض انتخاب‌ها، JSON یا ساختار پاسخ نامعتبر و عدم تطابق شمارهٔ ثبت جزئیات، `ValueError` ایجاد می‌کنند. خطاهای اتصال، مهلت، گواهی و HTTP به‌صورت زیرکلاس‌های `requests.RequestException` منتشر می‌شوند؛ منبع ممکن است برای شمارهٔ ثبت ناموجود نیز `500` برگرداند. درخواست‌ها بررسی گواهی HTTPS، مهلت محدود و سیاست تلاش مجدد محدود بخش `Funds` را دارند. این توابع از فیپیران یا وب‌سایت مستقل صندوق داده‌ای دریافت نمی‌کنند و رفتار توابع قبلی تغییر نمی‌کند.

شواهد بررسی منبع و محدودیت‌ها: [یادداشت‌های دادهٔ صندوق‌های TSETMC](https://github.com/hemoboghosian/fima/blob/master/docs/tsetmc-funds.md).

### داده‌های عمومی طلا، ارز و بازارهای جهانی TGJU

```python
from fima import (
    get_tgju_categories,
    get_tgju_instruments,
    get_tgju_market,
    get_tgju_history,
    get_tgju_instrument_details,
)

categories = get_tgju_categories()
instruments = get_tgju_instruments("ارز", search="دلار")
fx = get_tgju_market("ارز")
gold = get_tgju_market("طلا")
usd = get_tgju_history("دلار", "ارز", start_date="2026-10-01")
gold18 = get_tgju_history(
    "طلای 18 عیار / 750", "طلا",
    start_date="1405/07/01", end_date="1405/07/23", jalali=True,
)
details = get_tgju_instrument_details("بیت کوین", "ارز دیجیتال")
```

نام فارسی، نام انگلیسی و `Symbol` فهرست قابل استفاده‌اند و نیازی به شناسهٔ عددی TGJU نیست. نام مبهم با `ValueError` و گزینه‌های قابل انتخاب گزارش می‌شود؛ مثلاً «طلای ۱۸ عیار» می‌تواند به دو عیار مختلف اشاره کند، پس نام کامل را از فهرست انتخاب کنید.

فهرست نمادها و نمای بازار **صفحه‌بندی دارند**؛ `attrs["has_more"]` ادامه داشتن داده را مشخص می‌کند. برای صفحهٔ بعد از `get_tgju_instruments("ارز", page=2)` یا `get_tgju_market("ارز", page=2)` استفاده کنید. خروجی یک فراخوانی، فهرست کامل همهٔ ابزارها نیست. تاریخچه، همهٔ صفحات بازهٔ درخواستی را دریافت و صعودی مرتب می‌کند؛ واحد و منشأ آن در `usd.attrs` قرار دارد.

منبع این قابلیت، نقاط دسترسی عمومی و بدون احراز هویت TGJU است و توکن اشتراک نیاز ندارد. `fima` وابسته به TGJU نیست و ادعای تأیید یا مجوز رسمی از آن ندارد. دسترسی و رفتار منبع ممکن است تغییر کند؛ مسئولیت رعایت شرایط و محدودیت‌های ارائه‌دهنده بر عهدهٔ کاربر است. ریال و تومان تبدیل نمی‌شوند؛ فیلد اعلام‌نشده خالی می‌ماند. [راهنمای فارسی، ستون‌ها و محدودیت‌ها](https://github.com/hemoboghosian/fima/blob/master/docs/tgju.md).

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
- `adjust_historical_prices`
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
- `get_tsetmc_funds`
- `get_tsetmc_fund_details`
- `get_tsetmc_fund_types`

### `fima.TGJU`

- `get_tgju_categories`
- `get_tgju_instruments`
- `get_tgju_market`
- `get_tgju_history`
- `get_tgju_instrument_details`

همین پنج تابع از `fima` نیز قابل واردسازی هستند. واردسازی با `*` از `fima.TGJU` فقط همین نام‌ها را صادر می‌کند؛ هنگام واردسازی ماژول، درخواست شبکه انجام نمی‌شود.

پارامترهایی که با `_` شروع می‌شوند برای کنترل داخلی و آزمون هستند و بخشی از API پایدار عمومی محسوب نمی‌شوند.

در `fima.Funds`، واردسازی با `*` و فراخوانی `dir()` فقط شش تابع عمومی بالا را نمایش می‌دهند. توابع کمکی و وابستگی‌های داخلی در این فهرست‌ها ظاهر نمی‌شوند، ولی دسترسی صریح به آن‌ها همچنان ممکن است؛ پایتون آن‌ها را خصوصی و غیرقابل دسترسی نمی‌کند. نمایش تکمیل خودکار در ویرایشگرها ممکن است متفاوت باشد. پارامتر `_set_website_developers` برای سازگاری حفظ شده و همچنان در امضای واقعی `get_all_funds` دیده می‌شود؛ برای دریافت فهرست صندوق‌ها کافی است `get_all_funds()` را فراخوانی کنید.

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
