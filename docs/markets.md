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

### بانک مرکزی ایران

```python
from fima import get_cbi_policy_rates, get_cbi_inflation_rates, get_cbi_exchange_rates, get_cbi_ets_rates

rates = get_cbi_policy_rates()
print(rates.tail())
inflation = get_cbi_inflation_rates()
usd = get_cbi_exchange_rates("USD")
ets = get_cbi_ets_rates("USD", transaction_type="all")
```

سال‌های نرخ سیاستی و تورم به‌صورت خودکار دریافت می‌شوند. توابع ارز و ETS به‌طور
پیش‌فرض آخرین گزارش را می‌دهند؛ برای تاریخچه، هر دو تاریخ ابتدا و انتها را وارد
کنید. معنی ستون‌ها، واحدها و محدودیت دسترسی منبع در [راهنمای CBI](cbi.md) آمده است.

Public table schemas and analytical model units follow [data conventions](data-conventions.md); see [0.9.0 migration notes](data-migration.md) before upgrading.


The IFB tables expose YTM/SimpleReturn/CouponPercent in percentage points;
get_risk_free_rate() retains a decimal annual rate for model inputs. IFB index
histories share IndexValue/GregorianDate/JalaliDate, while each function still
selects its own index. Event dates explicitly name the Jalali calendar. The
get_ticker_info Section/Label/Value table intentionally keeps heterogeneous
provider display values as text; payment amounts remain numeric.

IME physical fields are mapped by source key: Quantity is TradeVolume, TotalPrice
is TradeValue, Price is the provider's weighted ClosingPrice. Other IME prices,
trade quantities, counts, date calendars and identifiers follow the shared
conventions. CreateDateTime preserves the supplied timestamp, including time.
Provider currency/quantity units remain unchanged; the physical report can display
trade value in thousand rial and quantity/price bases can differ. Never assume
that TradeValue equals price*quantity in unconverted unit systems. Export currency
and unit metadata are retained. A successful empty gold/silver CDC response is an
empty typed table, not a KeyError; empty data is not evidence that historical
coverage or configured provider filters were independently verified.

Institutions use InstitutionName, string NationalID/SEORegisterNo/CEOMobileNo and
the provider's existing boolean Status. Other contact/metadata fields stay as
provided. TLS verification remains enabled; the package's existing truststore
integration can succeed where a standalone requests probe lacks the same roots.
