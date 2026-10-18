# توسعه و آزمون

[User guide](../README.md)

## نصب برای توسعه

نمونهٔ زیر برای پاورشل در ویندوز است. در لینوکس و مک، محیط را با دستور `source .venv/bin/activate` فعال کنید.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --editable ".[test]"
python -m pytest -m "not integration"
python -m pytest
```

نخستین دستور آزمون، آزمون‌های قطعی و بدون شبکه را اجرا می‌کند. دستور دوم کل مجموعه، شامل آزمون‌های اتصال به منابع زنده، را اجرا می‌کند.

بخش قابل‌توجهی از آزمون‌ها به سرویس‌های آنلاین متصل می‌شوند. تمام آزمون‌های قطعی و بدون شبکه شرط انتشار هستند. آزمون‌های زنده جداگانه اجرا می‌شوند و خطای شبکه یا تغییر API منبع داده باید از خطای منطقی کتابخانه تفکیک، بررسی و پیش از انتشار گزارش شود.

## به‌روزرسانی و بررسی نسخه

```shell
python -m pip install --upgrade fima
python -c "from importlib.metadata import version; print(version('fima'))"
```
