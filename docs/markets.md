# مثال‌های بازارهای دیگر

[User guide](../README.md) | [Public API reference](api.md)

این مثال‌ها از توابع عمومی ماژول‌ها استفاده می‌کنند. داده‌های آنلاین به دسترسی ارائه‌دهنده وابسته‌اند؛ برای مشاهدهٔ خروجی‌های بزرگ از چند ردیف نخست استفاده کنید.

### اختیار معامله

برای دریافت زنجیرهٔ فعلی قراردادهای یک دارایی پایه:

```python
from fima import download_chain_contracts

chain = download_chain_contracts(underlying_ticker="اهرم")
print(chain.head())
```

در مثال‌های بعدی، نام قرارداد و بازهٔ تاریخی نمونه‌اند. برای قراردادهای فعلی، نام نماد را از زنجیرهٔ روز انتخاب کنید؛ ممکن است قرارداد نمونه منقضی شده باشد.

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

### نهادهای مالی

```python
from fima.TSEInstitutions import get_all_institutions

institutions = get_all_institutions()
```
