# fima
## معرفی و هدف


این کتابخانه جهت دسترسی آسان و سریع به داده‌های بازارهای مالی ایران با زبان برنامه‌نویسی پایتون پیاده‌سازی شده است. هدف نهایی این پروژه، ساخت کتابخانه‌ای جامع جهت استخراج، ساختاردهی و تحلیل داده‌های مالی از منابع مختلف موجود است.

**توجه: این کتابخانه هنوز در حال توسعه و تکامل است و ممکن است در برخی قسمت‌ها اشتباهاتی داشته باشد. لطفاً اگر خطا یا نقصی دیدید اطلاع دهید.**

## اطلاعات تماس
* ایمیل: HemoBoghosian@gmail.com
* تلگرام: @HemoBoghosian

## نصب کتابخانه
```
pip install fima
```

## ۱. توابع مربوط به اختیارهای معامله
###### نسخه ۰.۱.۱
### فراخوانی تمام توابع

```python
from fima.Options import *
```

### ۱.۱. دریافت سابقه قیمت اختیار معامله و دارایی پایه آن

```python
from fima.Options import download_historical_data

option_historical_data, ua_historical_data = download_historical_data(ticker='ضهرم4018', start_date='1404-01-01',
                                                                      end_date='1404-01-31')
```
#### ورودی
* ticker: نماد اختیار معامله
* start_date: تاریخ شروع داده‌ها
* end_date: تاریخ پایان داده‌ها

#### خروجی
* option_historical_data: سابقه قیمت اختیار معامله
* ua_historical_data: سابقه قیمت دارایی پایه نماد وارد شده

##### توجه: در صورت وارد نکردن تاریخ شروع و پایان، خروجی تابع تمام سابقه قیمت اختیار معامله و دارایی پایه آن خواهد بود.

### ۲.۱. دریافت اطلاعات لحظه‌ای یک نماد اختیار معامله

```python
from fima.Options import ticker_info

ticker_info_data = ticker_info(ticker='ضهرم4018', j_date=True)
```

#### ورود
* ticker: نماد اختیار معامله مد نظرم
* j_date: تاریخ شمسی

#### خروجی
* ticker_info_data: اطلاعات لحظه‌ای مربوط به نماد مد نظر

### ۳.۱. دریافت زنجیره قراردادهای یک دارایی پایه

```python
from fima.Options import download_chain_contracts

chain_contracts = download_chain_contracts(underlying_ticker='اهرم', j_date=True, bsm=False, greeks=False,
                                           implied_volatility=False)
```
#### ورودی
* underlying_ticker: نماد دارایی پایه
* j_date: تاریخ شمسی
* bsm: محاسبه ارزش اختیار معامله با مدل بلک، شولز و مرتون 
* greeks: محاسبه دلتا، تتا، گاما، رو و وگا
* implied_volatility: محاسبه نوسانات ضمنی

#### خروجی
* chain_contracts: اطلاعات تمامی زنجیره قراردادهای مربوط به دارایی پایه مد نظر

##### توجه: برای محاسبات مربوط به مدل بلک، شولز و مرتون از میانگین نرخ بازده تا سررسید اسناد خزانه در آخرین تاریخ (دریافت‌شده از سایت فرابورس ایران) به عنوان نرخ بازده بدون ریسک استفاده می‌شود.

### ۴.۱. دریافت دیده‌بان بازار

```python
from fima.Options import download_market_watch

market_watch = download_market_watch(market='All', stack='Vertical', j_date=True, bsm=False, greeks=False,
                                     implied_volatility=False)
```
#### ورودی
* market: بازار معامله اختیار معامله
  * 'TSE': بورس اوراق بهادار تهران
  * 'IFB': فرابورس ایران
  * 'All': تمامی اختیارهای معامله
* stack: نحوه چینش داده‌ها
  * 'Vertical': چینش عمودی داده‌ها
  * 'Horizontal': چینش افقی داده‌ها
* j_date: تاریخ شمسی
* bsm: محاسبه ارزش اختیار معامله با مدل بلک، شولز و مرتون 
* greeks: محاسبه دلتا، تتا، گاما، رو و وگا
* implied_volatility: محاسبه نوسانات ضمنی

#### خروجی
* market_watch: اطلاعات تمامی اختیارهای معامله بازار مد نظر

##### توجه: برای محاسبات مربوط به مدل بلک، شولز و مرتون از میانگین نرخ بازده تا سررسید اسناد خزانه در آخرین تاریخ (دریافت‌شده از سایت فرابورس ایران) به عنوان نرخ بازده بدون ریسک استفاده می‌شود.

### ۵.۱. دریافت ارزش محاسبه‌شده توسط مدل بلک، شولز و مرتون برای یک نماد

```python
from fima.Options import black_scholes_merton

volatility, bsm_price = black_scholes_merton(ticker='ضهرم4018')
```
#### ورودی
* ticker: نماد اختیار معامله مد نظر

#### خروجی
* volatility: نوسانات دارایی پایه محاسبه‌شده در مدل
* bsm_price: ارزش محاسبه‌شده اختیار معامله مد نظر با مدل بلک، شولز و مرتون

##### توجه
* توجه: در صورت عدم وارد کردن متغیر مربوط به نرخ بازده بدون ریسک، برای محاسبات مربوط به مدل بلک، شولز و مرتون از میانگین نرخ بازده تا سررسید اسناد خزانه در آخرین تاریخ (دریافت‌شده از سایت فرابورس ایران) به عنوان نرخ بازده بدون ریسک استفاده می‌شود.
* در صورتی که روزهای باقی‌مانده تا سررسید اختیار معامله کمتر از ۱۰ روز باشند، به دلیل احتمال خطا، مدل بلک، شولز و مرتون اعمال نخواهد شد.

### ۶.۱. دریافت گریکز برای یک نماد

```python
from fima.Options import get_greeks

ticker_greeks = get_greeks(ticker='ضهرم4018')
```
#### ورودی
* ticker: نماد اختیار معامله مد نظر
* r_f: نرخ بازده بدون ریسک
* minimum_required_history: کمینه دیتای مورد نیاز برای دارایی پایهجهت محاسبه نوسانات که به صورت پیش‌فرض ۳۰ روز در نظر گرفته شده است.

#### خروجی
* ticker_greeks: دلتا، تتا، گاما، وگا و رو برای نماد مد نظر 

##### توجه 
* در صورت عدم وارد کردن متغیر مربوط به نرخ بازده بدون ریسک، برای محاسبات مربوط به مدل بلک، شولز و مرتون از میانگین نرخ بازده تا سررسید اسناد خزانه در آخرین تاریخ (دریافت‌شده از سایت فرابورس ایران) به عنوان نرخ بازده بدون ریسک استفاده می‌شود.
* در صورتی که روزهای باقی‌مانده تا سررسید اختیار معامله کمتر از ۱۰ روز باشند، به دلیل احتمال خطا، مدل بلک، شولز و مرتون اعمال نخواهد شد.

### ۷.۱. دریافت نوسانات ضمنی برای یک نماد

```python
from fima.Options import get_implied_volatility

ticker_implied_volatility = get_implied_volatility(ticker='ضهرم4018')
```
#### ورودی
* ticker: نماد اختیار معامله مد نظر
* r_f: نرخ بازده بدون ریسک
* minimum_required_history: کمینه دیتای مورد نیاز برای دارایی پایهجهت محاسبه نوسانات که به صورت پیش‌فرض ۳۰ روز در نظر گرفته شده است.

#### خروجی
* ticker_implied_volatility: نوسانات ضمنی برای نماد مد نظر 

##### توجه 
* در صورت عدم وارد کردن متغیر مربوط به نرخ بازده بدون ریسک، برای محاسبات مربوط به مدل بلک، شولز و مرتون از میانگین نرخ بازده تا سررسید اسناد خزانه در آخرین تاریخ (دریافت‌شده از سایت فرابورس ایران) به عنوان نرخ بازده بدون ریسک استفاده می‌شود.
* در صورتی که روزهای باقی‌مانده تا سررسید اختیار معامله کمتر از ۱۰ روز باشند، به دلیل احتمال خطا، مدل بلک، شولز و مرتون اعمال نخواهد شد.

### ۸.۱. دریافت تمامی نمادهای دارای اختیار معامله

```python
from fima.Options import download_all_underlying_assets

all_underlying_assets = download_all_underlying_assets(market='All')
```
#### ورودی
* market: بازار معامله اختیار معامله
  * 'TSE': بورس اوراق بهادار تهران
  * 'IFB': فرابورس ایران
  * 'All': تمامی اختیارهای معامله (حالت پیش‌فرض)

#### خروجی
* all_underlying_assets: اطلاعات مربوط به نمادهای دارای اختیار معامله

#### توجه: در صورت عدم وارد کردن market، تمامی اختیارهای معامله دریافت خواهد شد. 

### ۹.۱. توابع مربوط به محاسبات

```python
from fima.Options import (calculate_black_scholes_merton, calculate_delta, calculate_vega,
                          calculate_theta, calculate_gamma, calculate_rho)

bsm_price = calculate_black_scholes_merton(s=550, k=28000, option_type='Call', t=71, sigma=0.9588, r_f=0.3372)
delta = calculate_delta(s=550, k=28000, option_type='Call', t=71, sigma=0.9588, r_f=0.3372)
theta = calculate_theta(s=550, k=28000, option_type='Call', t=71, sigma=0.9588, r_f=0.3372)
gamma = calculate_gamma(s=550, k=28000, t=71, sigma=0.9588, r_f=0.3372)
rho = calculate_rho(s=550, k=28000, option_type='Call', t=71, sigma=0.9588, r_f=0.3372)
vega = calculate_vega(s=550, k=28000, t=71, sigma=0.9588, r_f=0.3372)
```

## ۲. توابع مربوط به اوراق درآمد ثابت
###### نسخه ۰.۱.۱
### فراخوانی تمام توابع

```python
from fima.Bonds import *
```

### ۱.۲. دریافت سابقه قیمت اختیار معامله و دارایی پایه آن

```python
from fima.Bonds import get_risk_free_rate

risk_free_rate = get_risk_free_rate()
```

#### خروجی
* risk_free_rate: میانگین نرخ بازده تا سررسید اسناد خزانه در آخرین تاریخ (دریافت‌شده از سایت فرابورس ایران)

### ۲.۲. دریافت اوراق درآمد ثابت بدون کوپن

```python
from fima.Bonds import get_all_bonds_without_coupons

all_bonds_without_coupons = get_all_bonds_without_coupons(deprecated=True)
```

#### ورودی
* deprecated:
  * True: اوراق سررسید شده نیز در خروجی بیاید
  * False: اوراق سررسید شده در خروجی نیاید
#### خروجی
* all_bonds_without_coupons: اطلاعات مربوط به اوراق درآمد ثابت بدون کوپن (دریاقت‌شده از سایت فرابورس ایران)

### ۳.۲. دریافت اوراق درآمد ثابت با کوپن

```python
from fima.Bonds import get_all_bonds_with_coupons

all_bonds_with_coupons = get_all_bonds_with_coupons(deprecated=True)
```

#### ورودی
* deprecated:
  * True: اوراق سررسید شده نیز در خروجی بیاید
  * False: اوراق سررسید شده در خروجی نیاید
#### خروجی
* all_bonds_without_coupons: اطلاعات مربوط به اوراق درآمد ثابت با کوپن (دریاقت‌شده از سایت فرابورس ایران)


##  ۳. توابع مربوط به بورس کالا
######  نسخه ۰.۲.۰
### فراخوانی تمام توابع

```python
from fima.IME import *
```

### ۱.۳. دریافت آمار تمامی معاملات فیزیکی بورس کالا

```python
from fima.IME import get_all_ime_physical_trades

all_ime_physical_trades = get_all_ime_physical_trades(start_date='1400-01-01', end_date='1400-12-29')
```
#### ورودی
* start_date: تاریخ شروع داده‌ها
* end_date: تاریخ پایان داده‌ها
#### خروجی
* all_ime_physical_trades: آمار معاملات فیزیکی بورس کالا در بازه زمانی وارد شده

#### توجه: در صورت وارد نکردن تاریخ شروع و پایان داده‌ها، خروجی شامل تمامی معاملات خواهد بود.

### ۲.۳. دریافت آمار معاملات فیزیکی یک تولیدکننده در بورس کالا

```python
from fima.IME import get_producer_physical_trades

producer_physical_trades = get_producer_physical_trades(producer='ذوب آهن اصفهان', start_date='1402-01-01', end_date='1403-01-01')
```
#### ورودی
* producer: نام تولیدکننده مورد نظر
* start_date: تاریخ شروع داده‌ها
* end_date: تاریخ پایان داده‌ها
#### خروجی
* producer_physical_trades: آمار معاملات فیزیکی تولیدکننده مورد نظر در بورس کالا در بازه زمانی وارد شده

#### توجه: در صورت وارد نکردن تاریخ شروع و پایان داده‌ها، خروجی شامل تمامی معاملات تولیدکننده مورد نظر خواهد بود.

### ۳.۳. دریافت محصولات تمامی تولیدکنندگان فیزیکی در بورس کالا

```python
from fima.IME import get_all_physical_producer_products

all_physical_producer_products = get_all_physical_producer_products()
```

#### خروجی
* all_physical_producer_products: محصولات تمامی تولیدکنندگان فیزیکی در بورس کالا

### ۴.۳. دریافت آمار تمامی معاملات بازار مشتقه در بورس کالا

```python
from fima.IME import get_all_ime_futures_trades

all_ime_futures_trades = get_all_ime_futures_trades(only_active=False, start_date='1404-01-01', end_date='1404-02-01')
```
#### ورودی
* only_active:
  * True: فقط قراردادهای فعال
  * False: تمامی قراردادها
* start_date: تاریخ شروع داده‌ها
* end_date: تاریخ پایان داده‌ها
#### خروجی
* all_ime_futures_trades: آمار معاملات بازار مشتقه در بورس کالا در بازه زمانی وارد شده


### ۵.۳. دریافت آمار تمامی معاملات اختیار معامله در بورس کالا

```python
from fima.IME import get_all_ime_option_trades

all_ime_option_trades = get_all_ime_option_trades(option_type='All', only_active=False, start_date='1404-01-01', end_date='1404-02-01')
```
#### ورودی
* option_type:
  * 'All': تمامی اختیارهای معامله
  * 'Call': فقط اختیار خرید
  * 'Put': فقط اختیار فروش
* only_active: 
  * True: فقط قراردادهای فعال
  * False: تمامی قراردادها
* start_date: تاریخ شروع داده‌ها
* end_date: تاریخ پایان داده‌ها
#### خروجی
* all_ime_option_trades: آمار معاملات اختیار معامله در بورس کالا در بازه زمانی وارد شده

### ۶.۳. دریافت آمار تمامی معاملات صادراتی در بورس کالا

```python
from fima.IME import get_all_ime_export_trades

all_ime_export_trades = get_all_ime_export_trades(start_date='1404-01-01', end_date='1404-02-01')
```
#### ورودی
* start_date: تاریخ شروع داده‌ها
* end_date: تاریخ پایان داده‌ها
#### خروجی
* all_ime_export_trades: آمار معاملات صادراتی در بورس کالا در بازه زمانی وارد شده

#### توجه: در صورت وارد نکردن تاریخ شروع و پایان داده‌ها، خروجی شامل تمامی معاملات خواهد بود.

### ۷.۳. دریافت آمار تمامی معاملات صادراتی یک تولیدکننده در بورس کالا

```python
from fima.IME import get_producer_export_trades

producer_export_trades = get_producer_export_trades(producer='ملی صنایع مس ایران', start_date='1402-01-01', end_date='1403-01-01')
```
#### ورودی
* producer: نام تولیدکننده مورد نظر
* start_date: تاریخ شروع داده‌ها
* end_date: تاریخ پایان داده‌ها
#### خروجی
* producer_export_trades: آمار معاملات صادراتی تولیدکننده مورد نظر در بورس کالا در بازه زمانی وارد شده

#### توجه: در صورت وارد نکردن تاریخ شروع و پایان داده‌ها، خروجی شامل تمامی معاملات خواهد بود.

### ۸.۳. دریافت محصولات تمامی تولیدکنندگان صادراتی در بورس کالا

```python
from fima.IME import get_all_export_producer_products

all_export_producer_products = get_all_export_producer_products()
```

#### خروجی
* all_export_producer_products: محصولات تمامی تولیدکنندگان صادراتی در بورس کالا

### ۹.۳. دریافت آمار تمامی معاملات گواهی سپرده در بورس کالا

```python
from fima.IME import get_all_ime_cd_trades

all_ime_cd_trades = get_all_ime_cd_trades(start_date='1401-01-01', end_date='1401-12-29')
```
#### ورودی
* start_date: تاریخ شروع داده‌ها
* end_date: تاریخ پایان داده‌ها
#### خروجی
* all_ime_cd_trades: آمار معاملات گواهی سپرده در بورس کالا در بازه زمانی وارد شده

#### توجه: در صورت وارد نکردن تاریخ شروع و پایان داده‌ها، خروجی شامل تمامی معاملات خواهد بود.

### ۱۰.۳. دریافت آمار تمامی معاملات سلف استاندارد در بورس کالا

```python
from fima.IME import get_all_ime_salaf_trades

all_ime_salaf_trades = get_all_ime_salaf_trades(start_date='1401-01-01', end_date='1401-12-29')
```
#### ورودی
* start_date: تاریخ شروع داده‌ها
* end_date: تاریخ پایان داده‌ها
#### خروجی
* all_ime_salaf_trades: آمار معاملات سلف استاندارد در بورس کالا در بازه زمانی وارد شده

#### توجه: در صورت وارد نکردن تاریخ شروع و پایان داده‌ها، خروجی شامل تمامی معاملات خواهد بود.

### ۱۱.۳. دریافت آمار معاملات گواهی سپرده‌های شمش طلا و نقره و سکه طلا در بورس کالا

```python
from fima.IME import get_gold_and_silver_cd_trades

cd_trades = get_gold_and_silver_cd_trades(contract_type='gold_bar_cd', start_date='1403-01-01', end_date='1403-12-29')
```
#### ورودی
* contract_type: نوع قرارداد
  * 'gold_bar_cd': گواهی سپرده پیوسته شمش طلای +995
  * 'gold_coin_cd': گواهی سپرده پیوسته تمام سکه بهار آزادی طرح جدید
  * 'silver_bar_cd': گواهی سپرده پیوسته شمش نقره 999.9
* start_date: تاریخ شروع داده‌ها
* end_date: تاریخ پایان داده‌ها
#### خروجی
* cd_trades: آمار معاملات گواهی سپرده‌های شمش طلا و نقره و سکه طلا در بورس کالا در بازه زمانی وارد شده

#### توجه: در صورت وارد نکردن تاریخ شروع و پایان داده‌ها، خروجی شامل تمامی معاملات خواهد بود.

## نقشه راه
1. [ ] عیب‌یابی و بهبود توابع پیاده‌سازی‌شده
2. [ ] دریافت اطلاعات از سایت tgju
3. [ ] دریافت اطلاعات از سایت tsetmc
4. [ ] دریافت و پاکسازی اطلاعات سایت codal
5. [ ] دریافت اطلاعات از سایت TradingView