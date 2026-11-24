# راهنمای توابع عمومی

[شروع کار](../README.md) | [قرارداد داده‌ها](data-conventions.md)

تمام ۹۱ تابع زیر از `fima` و ماژول عمومی مربوط قابل واردسازی‌اند. امضاها ترتیب، آرگومان‌های الزامی، پیش‌فرض‌ها و مرز `*` برای آرگومان‌های صرفاً نام‌دار را نشان می‌دهند؛ نوع‌ها و توضیحات کامل در `help(fima.function)` و راهنمای هر منبع آمده‌اند. از import صریح استفاده کنید.

برای انتخاب شناسه، ابتدا ابزار کشف همان منبع را بخوانید. شناسه‌های پویا `Literal` نیستند؛ انتخاب‌های کوچکِ واقعاً محدود در annotation مشخص شده‌اند. این نوع‌ها کنترل جدیدی در زمان اجرا اعمال نمی‌کنند. نمایش پیشنهادها به ویرایشگر و تنظیمات آن وابسته است.

| کار | مسیر کشف |
| --- | --- |
| سهام / شاخص | `get_tickers` → `Ticker`/`InstrumentCode`؛ `get_indexes_status().index` → نام شاخص |
| صندوق | `get_all_funds` → `FundName`؛ برای TSETMC: انواع → گروه → نام/شماره ثبت |
| اختیار | `download_all_underlying_assets` → `Ticker` → زنجیره → `CallTicker`/`PutTicker` |
| TGJU | گروه‌ها → `get_tgju_instruments` → `Symbol` → مشخصات/تاریخچه |
| IME | گزارش کوتاه → `ProducerName`، `ContractCode` یا `Symbol`/`Code`؛ مشخصات قرارداد برای واحد |
| IFB | پاسخ بدون فیلتر برای طبقه‌بندی‌ها؛ انتخابگر رسمی YTM برای شناسهٔ اوراق |
| CBI | نرخ‌های آخرین گزارش → `CurrencyCode`/`CurrencyName`؛ انتخابگر رسمی برای ارزهای تاریخی |
| KILID | `get_kilid_areas` → `Area`؛ نام نمایشی شناسه نیست |
| IMF | شاخص‌ها → `Indicator`؛ جغرافیاها → `Country`، با حفظ نوع کشور/منطقه/گروه |

## `fima.TSETMC`

[پارامترها، خروجی، واحدها و محدودیت‌ها](tsetmc.md)

| امضای تابع | کاربرد |
| --- | --- |
| `get_ticker_historical_trades_client_type(ticker, _max_workers=10)` | Return a ticker's daily retail/institutional trading breakdown. |
| `get_index_companies(index, thirty_days_history=False)` | Return index-constituent quotes and optional recent closing history. |
| `get_ticker_historical_shareholders(ticker, _max_workers=10)` | Return published shareholders across a ticker's available trading dates. |
| `get_ticker_historical_market_caps(ticker, _max_workers=10)` | Calculate daily official closing price times historical shares. |
| `get_tickers(tse, ifb, details=False)` | Discover TSE/IFB tickers from the selected index-constituent sources. |
| `get_ticker_historical_data(ticker=None, ticker_instrument_code=None, *, adjust_prices=False)` | Download official TSETMC daily history with a Jalali date index. |
| `get_index_historical_data(index)` | Return daily levels for an index selected by its exact published name. |
| `get_indexes_status()` | Discover selected TSE/IFB index names and latest published levels. |
| `get_supervision_lists()` | Return reasons from TSETMC's selected supervision lists. |
| `get_ticker_intraday_trades(ticker)` | Return the source's last-session individual trades for a ticker. |
| `get_share_changes()` | Return recent TSE/IFB share-count changes published by TSETMC. |
| `get_price_adjustments()` | Return TSETMC's published TSE/IFB price-adjustment event records. |
| `get_index_last_intraday_data(index)` | Return the last available day's intraday observations for an index. |
| `adjust_historical_prices(data)` | Return a copy with TSETMC reference-price-based backward-adjusted prices. |

## `fima.TSEInstitutions`

[پارامترها، خروجی، واحدها و محدودیت‌ها](markets.md#financial-institution-directory)

| امضای تابع | کاربرد |
| --- | --- |
| `get_all_institutions()` | Return the published financial-institution directory. |

## `fima.Funds`

[پارامترها، خروجی، واحدها و محدودیت‌ها](funds.md)

| امضای تابع | کاربرد |
| --- | --- |
| `get_all_funds(_set_website_developers=False)` | Return available investment-fund information from Fipiran. |
| `get_daily_navs(fund_name)` | Return daily NAV data for a fund. |
| `get_daily_asset_allocation(fund_name)` | Return daily asset-allocation data for a fund. |
| `get_tsetmc_funds(fund_type)` | Return a normalized TSETMC fund-group snapshot. |
| `get_tsetmc_fund_details(fund_name=None, *, fund_type=None, reg_no=None)` | Return a normalized TSETMC fund dict selected by name or registration. |
| `get_tsetmc_fund_types()` | List supported Persian/English group names and TSETMC numeric selectors. |

## `fima.Options`

[پارامترها، خروجی، واحدها و محدودیت‌ها](options.md)

| امضای تابع | کاربرد |
| --- | --- |
| `download_chain_contracts(underlying_ticker, j_date=True, bsm=False, greeks=False, implied_volatility=False)` | Return the current option chain for an exact underlying ticker. |
| `get_greeks(ticker, _ticker_info_df=None, volatility_window_size=None, r_f=None, minimum_required_history=30, _ua_historical_data=None)` | Estimate an option's Greeks using historical underlying volatility. |
| `get_implied_volatility(ticker, _ticker_info_df=None, volatility_window_size=None, r_f=None, minimum_required_history=30, _ua_historical_data=None)` | Estimate decimal implied volatility from the option's observed premium. |
| `black_scholes_merton(ticker, _ticker_info_df=None, volatility_window_size=None, r_f=None, minimum_required_history=30, _ua_historical_data=None)` | Estimate an option price using historical underlying volatility. |
| `download_market_watch(market='All', stack='Horizontal', j_date=True, bsm=False, greeks=False, implied_volatility=False)` | Return TSETMC options for ``All``, ``TSE`` or ``IFB``. |
| `calculate_contract_metrics(watch, *, price='Ask', underlying_price='Last')` | مقایسهٔ مظنه‌ها، ارزش ذاتی/زمانی، سربه‌سر و مبلغ پریمیوم هر قرارداد، بدون شبکه. |
| `calculate_expiration_payoff(underlying_prices, strike_price, premium, option_type, *, contract_size, contracts=1, position='Long')` | سناریوی ارزش و سود/زیان ناخالص در سررسید، با اندازهٔ قرارداد صریح و بدون شبکه. |
| `download_all_underlying_assets(_all_options_market_watch=None, market='All')` | Discover underlying assets from an options market watch. |
| `download_historical_data(ticker, start_date=None, end_date=None)` | Option and underlying raw daily history, filtered by optional Jalali bounds. |
| `ticker_info(ticker, j_date=True)` | Return option metadata and last prices for an exact option ticker. |
| `calculate_delta(s, k, t, r_f, sigma, option_type)` | Calculate delta for the no-dividend European option model. |
| `calculate_vega(s, k, t, r_f, sigma)` | Calculate vega for the no-dividend European option model. |
| `calculate_theta(s, k, t, r_f, sigma, option_type)` | Calculate theta for the no-dividend European option model. |
| `calculate_gamma(s, k, t, r_f, sigma)` | Calculate gamma for the no-dividend European option model. |
| `calculate_rho(s, k, t, r_f, sigma, option_type)` | Calculate rho for the no-dividend European option model. |
| `calculate_black_scholes_merton(s, k, t, sigma, r_f, option_type)` | Calculate a no-dividend European option price without network requests. |
| `get_risk_free_rate()` | Return a decimal annual treasury-yield proxy from the IFB snapshot. |
| `get_ticker_historical_data(ticker=None, ticker_instrument_code=None, *, adjust_prices=False)` | Download official TSETMC daily history with a Jalali date index. |

## `fima.IFB`

[پارامترها، خروجی، واحدها و محدودیت‌ها](ifb.md)

| امضای تابع | کاربرد |
| --- | --- |
| `get_ifb_market_map(metric='market_value', ticker=None, market=None)` | Return all records from IFB's selected market-map snapshot response. |
| `get_ifb_periodical_reports(start_date, end_date, *, report_type=None, reporting_period=None, title=None, breakdown=None, jalali=True, max_pages=20)` | Discover all official reports in an inclusive reporting-period-end window. |
| `get_ifb_bond_yield_history(start_date, end_date, ticker=None, *, instrument_id=None, jalali=True, on_conflict='raise')` | Download a verified instrument's complete official filtered YTM export. |
| `get_ifb_yield_curve(category='treasury')` | Return official fitted YTM comparison nodes from IFB's Nelson page. |
| `get_ifb_market_values(group_by='industry')` | Return IFB's aggregate market-value snapshot by ``industry`` or ``market``. |
| `get_ifb_symbol_market_values(ticker=None, market=None, industry=None)` | Return all industry-page constituents, optionally exact-filtered locally. |
| `get_ifb_market_value_history(start_date=None, end_date=None, *, jalali=True)` | Return all three official market-value CSV histories, filtered inclusively. |
| `get_risk_free_rate()` | Return a decimal annual treasury-yield proxy from the IFB snapshot. |
| `get_all_bonds_without_coupons(deprecated=True)` | Return IFB's published discount-bond yield snapshot. |
| `get_all_bonds_with_coupons(deprecated=True)` | Return IFB's published coupon-bond yield snapshot. |
| `get_ifb_equally_weighted_total_index_historical_data()` | Return the source's available IFB equal-weight total index history. |
| `get_ifb_equally_weighted_price_index_historical_data()` | Return the source's available IFB equal-weight price index history. |
| `get_ifb_price_index_historical_data()` | Return the source's available IFB price index history. |
| `get_ifb_total_index_historical_data()` | Return the source's available IFB total index history. |
| `get_ifb_total_sukuk_index_historical_data()` | Return the source's available IFB total sukuk index history. |
| `get_sukuk_daily_trades_based_on_bs()` | Return dated IFB sukuk trades grouped by buyer/seller sector. |
| `get_sukuk_daily_trades_based_on_ct()` | Return dated IFB sukuk trades grouped by source transaction category. |
| `get_all_standard_financing_instruments()` | Discover published IFB standard financing instruments. |
| `get_all_special_financing_instruments()` | Discover published IFB special financing instruments. |
| `get_all_crowdfunding_plans(include_descriptions=True, _max_workers=8)` | Return published crowdfunding plans and optional descriptions. |
| `get_all_crowdfunding_platforms()` | Return the source's crowdfunding-platform licensing directory. |
| `get_ticker_info(ticker)` | Return IFB financing-instrument display metadata and payment history. |

## `fima.IME`

[پارامترها، خروجی، واحدها و محدودیت‌ها](ime.md)

| امضای تابع | کاربرد |
| --- | --- |
| `get_all_ime_physical_trades(start_date=None, end_date=None, _chunk_size=30, _max_workers=2, _timeout=(20, 120), _max_retries=3, _strict=True, _verbose=False, _rescue_chunk_size=7)` | Return IME physical trades for an inclusive Jalali interval. |
| `get_all_ime_futures_trades(only_active=False, start_date=None, end_date=None, _chunk_size=100, _offset=0, _timeout=(10, 45))` | Return complete official futures reports, or raise RuntimeError on failure. |
| `get_all_ime_option_trades(option_type='All', only_active=False, start_date=None, end_date=None, _chunk_size=100, _offset=0, _timeout=(10, 45), *, contract_code=None)` | Return complete official daily option statistics for inclusive Jalali dates. |
| `get_all_physical_producer_products(start_date=None, end_date=None, all_ime_physical_trades=None)` | Group physical trade goods by their exact published producer names. |
| `get_producer_physical_trades(producer, start_date=None, end_date=None, all_ime_physical_trades=None)` | Select physical trades for an exact producer and optional Jalali bounds. |
| `get_all_ime_export_trades(start_date=None, end_date=None, _chunk_size=100, _offset=40, _timeout=(10, 45))` | Return complete official export reports, preserving source Currency/Unit. |
| `get_all_ime_cd_trades(start_date=None, end_date=None, _chunk_size=100, _offset=30, _timeout=(10, 45), *, ticker=None, instrument_code=None)` | Return complete daily certificate statistics for inclusive Jalali dates. |
| `get_all_export_producer_products()` | Group export goods by producer after downloading default export history. |
| `get_producer_export_trades(producer, start_date=None, end_date=None)` | Return export trades matching an exact producer name. |
| `get_all_ime_salaf_trades(start_date=None, end_date=None, _chunk_size=100, _offset=30, _timeout=(10, 45), *, ticker=None, instrument_code=None)` | Return complete daily standard parallel salaf statistics for inclusive Jalali dates. |
| `get_gold_and_silver_cd_trades(contract_type, start_date=None, end_date=None, _timeout=(10, 45))` | Request legacy gold/silver CDC history using existing configured filters. |

## `fima.TGJU`

[پارامترها، خروجی، واحدها و محدودیت‌ها](tgju.md)

| امضای تابع | کاربرد |
| --- | --- |
| `get_tgju_categories()` | گروه‌های پشتیبانی‌شده را از پیکربندی عمومی سایت کشف می‌کند. |
| `get_tgju_instruments(category=None, *, search=None, page=1)` | یک صفحه از فهرست عمومی نمادها را با نام فارسی یا انگلیسی دریافت می‌کند. |
| `get_tgju_market(category=None, *, search=None, page=1)` | آخرین داده‌های یک صفحه نماد را از منبع عمومی ویجت می‌گیرد. |
| `get_tgju_history(instrument, category=None, *, start_date=None, end_date=None, jalali=False)` | تاریخچه روزانه نماد را به ترتیب صعودی تاریخ در DataFrame برمی‌گرداند. |
| `get_tgju_instrument_details(instrument, category=None)` | مشخصات نماد منتخب با نام فارسی، انگلیسی یا Symbol را برمی‌گرداند. |

## `fima.CBI`

[پارامترها، خروجی، واحدها و محدودیت‌ها](cbi.md)

| امضای تابع | کاربرد |
| --- | --- |
| `get_cbi_policy_rates()` | Return complete policy-rate history advertised by the CBI year selector. |
| `get_cbi_inflation_rates(frequency='monthly')` | Return CBI's complete monthly or annual inflation table. |
| `get_cbi_exchange_rates(currency=None, start_date=None, end_date=None, *, jalali=False)` | Return the normal CBI exchange dataset, separately from ETS buy/sell quotes. |
| `get_cbi_ets_rates(currency=None, transaction_type='all', start_date=None, end_date=None, *, jalali=False)` | Return ETS cash/transfer buy and sell quotes in one wide DataFrame. |

## `fima.KILID`

[پارامترها، خروجی، واحدها و محدودیت‌ها](kilid.md)

| امضای تابع | کاربرد |
| --- | --- |
| `get_kilid_areas(area=None)` | Discover one page's published areas, without recursively crawling. |
| `get_kilid_house_price_history(area, period='1y', denomination='toman')` | Return KILID's complete published monthly listing-price table per m². |
| `get_kilid_house_price_snapshot(area)` | Return latest published sale/rental listing statistics in long format. |
| `get_kilid_area_comparison(area)` | Return all published related-area comparison rows for a source slug. |

## `fima.IMF`

[پارامترها، خروجی، واحدها و محدودیت‌ها](imf.md)

| امضای تابع | کاربرد |
| --- | --- |
| `get_imf_datasets()` | Discover the supported DataMapper subset (currently annual WEO only). |
| `get_imf_indicators(dataset=None, search=None)` | Discover supported annual WEO indicators, definitions and native units. |
| `get_imf_countries(include_aggregates=False)` | Discover exact source geographic IDs; they are not all ISO country codes. |
| `get_imf_series(indicator, countries, start_year, end_year)` | Retrieve one WEO annual indicator for explicit geographies and years. |

## `fima.codal`

[راهنمای دریافت خودکار گزارش با نام فارسی](codal.md)

| API | کاربرد |
| --- | --- |
| `get_codal_data(symbol, report_type, period=None, *, statement=None, audited=None, duration_months=None, raw=False, max_pages=100, interactive=False)` | دریافت یک گزارش کدال با نام فارسی و بازگرداندن DataFrame. |
| `search_codal_filings(symbol, report_type, period=None, *, max_pages=100, interactive=False)` | جست‌وجوی گزارش‌های ناشر و نسخه‌های اصلاح‌شده. |
| `fetch_codal_report(filing, *, statement=None, interactive=False)` | دریافت HTML ساخت‌یافته و برگهٔ صورت مالی برای یک ردیف جست‌وجو. |
| `list_codal_report_types()` | فهرست نام‌ها و شناسه‌های دسته و نوع گزارش ناشران از کدال. |

## `fima.codal_reports`

[شیوهٔ ذخیره، ساختار خروجی و محدودیت‌ها](codal.md)

| امضای تابع | کاربرد |
| --- | --- |
| `get_codal_report(path, sheet_id=None)` | Read structured CODAL HTML and preserve filing metadata, original bytes and sheet coverage. |
| `get_codal_tables(report)` | Return source-ordered tables with cell DataFrames, source units and provenance. |
| `get_codal_monthly_activity(report)` | Normalize the verified manufacturing production and sales grid from a saved filing. |
| `get_codal_financial_statements(report)` | Normalize verified separate annual and six-month industrial statement grids from a saved filing. |

### واردسازی و سازگاری

پارامترهای قدیمی با پیشوند `_` برای سازگاری در امضا باقی مانده‌اند؛ راهنمای هر تابع نقش آن‌ها را توضیح می‌دهد. در `Funds` فقط شش تابع عمومی در `dir()` و import با `*` نمایش داده می‌شوند، ولی دسترسی صریح به کمک‌تابع‌ها همچنان ممکن است. نام‌های `PIKAD_URL_PREFIXES` و `NIKA_MANUAL_CONFIGS` قرارداد تنظیمات عمومی نیستند.

`ticker_info` مربوط به اختیار و `get_ticker_info` مربوط به ابزار تأمین مالی IFB است. دیکشنری جزئیات صندوق TSETMC، tuple تاریخچهٔ اختیار، Series مربوط به Greeks و خروجی scalar تحلیل عمداً شکل یکسانی ندارند. نام‌ها و معنی کلیدهای ساختاریافته در [قرارداد داده‌ها](data-conventions.md) و [مهاجرت](data-migration.md) آمده است.
