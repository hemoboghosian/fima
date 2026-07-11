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

پارامترهایی که با `_` شروع می‌شوند برای کنترل داخلی و آزمون هستند و بخشی از API پایدار عمومی محسوب نمی‌شوند.

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

بخش قابل‌توجهی از آزمون‌ها به سرویس‌های آنلاین متصل می‌شوند. خطای شبکه یا تغییر API منبع داده باید از خطای منطقی کتابخانه تفکیک شود، اما انتشار نسخه در صورت شکست هر آزمون متوقف می‌شود.

## پیوندها

- GitHub: https://github.com/hemoboghosian/fima
- PyPI: https://pypi.org/project/fima/

## مجوز

این پروژه تحت مجوز MIT منتشر می‌شود. متن کامل در فایل `LICENSE` قرار دارد.

## تماس

- HemoBoghosian@gmail.com
