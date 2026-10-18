# فهرست توابع عمومی

[User guide](../README.md)

برای استفاده، نام تابع را به‌صورت صریح از `fima` یا ماژول مربوط وارد کنید. برای جلوگیری از واردشدن نام‌های کمکی، از `import *` استفاده نکنید. مثال‌های کوتاه در [راهنمای اصلی](../README.md)، [راهنمای سهام](tsetmc.md)، [راهنمای صندوق‌ها](funds.md)، [راهنمای طلا و ارز](tgju.md) و [مثال‌های بازارهای دیگر](markets.md) قرار دارند.

## `fima.Options`

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

## `fima.IFB`

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

## `fima.IME`

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

## `fima.TSETMC`

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

## `fima.TSEInstitutions`

- `get_all_institutions`

## `fima.Funds`

- `get_all_funds`
- `get_daily_navs`
- `get_daily_asset_allocation`
- `get_tsetmc_funds`
- `get_tsetmc_fund_details`
- `get_tsetmc_fund_types`

## `fima.TGJU`

- `get_tgju_categories`
- `get_tgju_instruments`
- `get_tgju_market`
- `get_tgju_history`
- `get_tgju_instrument_details`

همین پنج تابع از `fima` نیز قابل واردسازی هستند. واردسازی با `*` از `fima.TGJU` فقط همین نام‌ها را صادر می‌کند؛ هنگام واردسازی ماژول، درخواست شبکه انجام نمی‌شود.

پارامترهایی که با `_` شروع می‌شوند برای کنترل داخلی و آزمون هستند و بخشی از API پایدار عمومی محسوب نمی‌شوند.

در `fima.Funds`، واردسازی با `*` و فراخوانی `dir()` فقط شش تابع عمومی بالا را نمایش می‌دهند. توابع کمکی و وابستگی‌های داخلی در این فهرست‌ها ظاهر نمی‌شوند، ولی دسترسی صریح به آن‌ها همچنان ممکن است؛ پایتون آن‌ها را خصوصی و غیرقابل دسترسی نمی‌کند. نمایش تکمیل خودکار در ویرایشگرها ممکن است متفاوت باشد. پارامتر `_set_website_developers` برای سازگاری حفظ شده و همچنان در امضای واقعی `get_all_funds` دیده می‌شود؛ برای دریافت فهرست صندوق‌ها کافی است `get_all_funds()` را فراخوانی کنید.

Parsed public data contracts: [conventions](data-conventions.md) and [unreleased migration](data-migration.md).
