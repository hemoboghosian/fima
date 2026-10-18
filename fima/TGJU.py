"""داده‌های عمومی TGJU؛ بدون توکن، وابستگی سازمانی یا درخواست هنگام import."""
import datetime as _dt
import json as _json
import math as _math
import re as _re
import threading as _threading
import time as _time
from urllib.parse import parse_qs as _parse_qs, urlparse as _urlparse

from bs4 import BeautifulSoup as _Soup
import jdatetime as _jd
import pandas as _pd
import requests as _requests
from ._data import gregorian_series as _gregorian_series, jalali_date as _jalali_date, time_string as _time_string

__all__ = [
    'get_tgju_categories', 'get_tgju_instruments', 'get_tgju_market',
    'get_tgju_history', 'get_tgju_instrument_details',
]

_API = 'https://api.tgju.org/v1/'
_SITE = 'https://www.tgju.org/'
_TIMEOUT = (10, 30)
_HISTORY_PAGE_SIZE = 100
_MAX_PAGES = 200
_request_lock = _threading.Lock()
_last_request = 0.0
_categories_cache = None
_digits = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩يك', '01234567890123456789یک')
# These are website data families, not an instrument list or numeric identifiers.
_families = {
    'internal_gold': ('gold', ('طلا',)),
    'internal_coin': ('coin', ('coins', 'سکه')),
    'internal_currency': ('currency', ('fx', 'currencies', 'ارز')),
    'crypto': ('crypto', ('cryptocurrency', 'ارز دیجیتال', 'رمزارز')),
    'global_precious_metals': ('precious_metals', ('فلزات گرانبها',)),
    'global_base_metals': ('base_metals', ('فلزات پایه',)),
    'global_energy': ('energy', ('انرژی', 'نفت', 'نفت و انرژی')),
    'global_commodity': ('commodity', ('commodities', 'کالا', 'کالایی')),
    'global_currencies': ('forex', ('بازارهای ارزی',)),
    'indices_bourse_countries': ('indices', ('index', 'شاخص', 'شاخص‌ها', 'شاخص های جهانی')),
}
_INSTRUMENT_COLUMNS = ['Symbol', 'Name', 'EnglishName', 'Category', 'Group', 'Market', 'Currency']
_MARKET_COLUMNS = _INSTRUMENT_COLUMNS + [
    'Price', 'Open', 'High', 'Low', 'Change', 'ChangePercent', 'ChangeDirection',
    'UpdateTime', 'UpdatedAt', 'Unit', 'HasSnapshot',
]
_HISTORY_COLUMNS = ['Date', 'JDate', 'Open', 'Low', 'High', 'Close', 'Change', 'ChangePercent', 'ChangeDirection']


def _text(value):
    return str(value).translate(_digits).replace('\\u200c', ' ').replace('\u200c', ' ').strip()


def _norm(value):
    return _re.sub(r'\s+', '', _text(value)).casefold()


def _number(value):
    if value is None:
        return None
    text = _text(value).replace('٬', ',').replace('٫', '.').replace('−', '-')
    if text in ('', '-', '—'):
        return None
    text = text.removesuffix('%').removesuffix('٪').strip()
    if not _re.fullmatch(r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][+-]?\d+)?', text):
        raise ValueError(f'TGJU invalid numeric value: {value!r}')
    text = text.replace(',', '')
    if _re.fullmatch(r'[+-]?\d+', text):
        return int(text)
    number = float(text)
    if not _math.isfinite(number):
        raise ValueError(f'TGJU non-finite numeric value: {value!r}')
    return int(number) if number.is_integer() else number


def _signed(value, direction):
    value = _number(value)
    if value is None or not value or direction not in ('high', 'low'):
        return value
    return abs(value) * (-1 if direction == 'low' else 1)


def _date(value, jalali=False):
    if value is None or value == '':
        return None
    if isinstance(value, _dt.datetime):
        value = value.date()
    if isinstance(value, _dt.date) and not jalali:
        return value
    if isinstance(value, _jd.date) and jalali:
        return value
    try:
        year, month, day = map(int, _text(value).replace('/', '-').split('-'))
        return (_jd.date if jalali else _dt.date)(year, month, day)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'TGJU invalid {"Jalali" if jalali else "Gregorian"} date: {value!r}') from exc


def _html_number(value):
    if value is None:
        return None, ''
    soup = _Soup(str(value), 'html.parser')
    classes = {cls for node in soup.select('[class]') for cls in node.get('class', [])}
    if {'high', 'low'} <= classes:
        raise ValueError('TGJU conflicting change directions')
    direction = 'low' if 'low' in classes else 'high' if 'high' in classes else ''
    return _signed(soup.get_text(' ', strip=True), direction), direction


class _Client:
    def __enter__(self):
        self.session = _requests.Session()
        return self

    def __exit__(self, *args):
        self.session.close()

    def get(self, url, params=None, *, json_data=True):
        global _last_request
        for attempt in range(2):
            with _request_lock:
                _time.sleep(max(0, .5 - (_time.monotonic() - _last_request)))
                try:
                    response = self.session.get(url, params=params, timeout=_TIMEOUT)
                except _requests.Timeout as exc:
                    raise _requests.Timeout(f'TGJU request timed out: {url}') from exc
                finally:
                    _last_request = _time.monotonic()
            # Do not retry authentication failures, deliberate blocks or rate limits.
            if response.status_code in (500, 502, 503, 504) and attempt == 0:
                response.close()
                _time.sleep(1)
                continue
            response.raise_for_status()
            if not json_data:
                return response
            try:
                return response.json()
            except ValueError as exc:
                raise ValueError(f'TGJU invalid JSON response: {url}') from exc


def _categories(client):
    global _categories_cache
    if _categories_cache and _time.monotonic() - _categories_cache[0] < 600:
        return [dict(row) for row in _categories_cache[1]]
    response = client.get(_SITE, json_data=False)
    soup = _Soup(response.text, 'html.parser')
    pattern = r'title:\s*("(?:[^"\\]|\\.)*")\s*,\s*source:\s*"(https://api\.tgju\.org/v1/newsearch\?[^"\s]+)"'
    rows = {}
    for script in soup.find_all('script'):
        for label, url in _re.findall(pattern, script.get_text()):
            query = _parse_qs(_urlparse(url).query)
            batch = query.get('batch', [''])[0]
            module = query.get('module', [''])[0]
            if batch in _families and module in ('markets.internal', 'markets.global'):
                rows.setdefault(batch, dict(Category=_json.loads(label),
                    Market='بازار داخلی' if module == 'markets.internal' else 'بازار جهانی',
                    EnglishName=_families[batch][0], _batch=batch, _module=module))
    if not rows:
        raise ValueError('TGJU category configuration is missing or malformed')
    _categories_cache = (_time.monotonic(), list(rows.values()))
    return [dict(row) for row in rows.values()]


def _sources(client, category):
    if category is None:
        return [{'module': 'markets.internal'}, {'module': 'markets.global'}]
    if not isinstance(category, str) or not category.strip():
        raise ValueError('category must be a name from get_tgju_categories()')
    categories = _categories(client)
    matches = [row for row in categories if _norm(category) in {
        _norm(x) for x in (row['Category'], row['EnglishName'], *_families[row['_batch']][1])}]
    if len(matches) != 1:
        raise ValueError('Unknown or ambiguous TGJU category; use get_tgju_categories()')
    return [{'module': matches[0]['_module'], 'batch': matches[0]['_batch']}]


def _catalog_page(client, source, search, page):
    params = dict(source, page=page)
    if search is not None:
        params['q'] = _text(search)
    data = client.get(_API + 'newsearch', params)
    if not isinstance(data, dict) or not isinstance(data.get('list'), list) or not isinstance(data.get('last'), bool):
        raise ValueError('TGJU malformed instrument catalog response')
    rows = []
    for raw in data['list']:
        if (not isinstance(raw, dict) or not isinstance(raw.get('title'), str)
                or not raw['title'].strip() or not raw.get('n1')
                or not isinstance(raw.get('type'), str)):
            raise ValueError('TGJU malformed catalog instrument')
        if raw.get('batch') not in _families:
            continue
        symbol = raw.get('s3') or raw.get('s1') or raw.get('grade')
        if not isinstance(symbol, str) or not symbol.strip() or any(x in symbol for x in '/?#'):
            raise ValueError('TGJU malformed instrument symbol')
        rows.append(dict(Symbol=symbol.strip(), Name=raw['title'].strip(), EnglishName=raw.get('title_en'),
            Category=raw.get('category'), Group=_families[raw['batch']][0],
            Market='بازار داخلی' if raw['type'].startswith('markets.internal') else 'بازار جهانی',
            Currency=(raw.get('s2') or '').upper() or None, _id=str(raw['n1']), _raw=raw))
    return rows, not data['last'], len(data['list'])


def _page(client, category, search, page):
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ValueError('page must be a positive integer')
    if search is not None and (not isinstance(search, str) or not search.strip()):
        raise ValueError('search must be a nonempty string')
    rows, has_more = [], False
    for source in _sources(client, category):
        found, more, _ = _catalog_page(client, source, search, page)
        rows.extend(found)
        has_more |= more
    return rows, {'page': page, 'has_more': has_more, 'SourceURL': _API + 'newsearch'}


def _table(rows, columns, attrs=None):
    frame = _pd.DataFrame(rows, columns=columns)
    frame.attrs.update(attrs or {})
    return frame


def _public_table(frame):
    names = {'Name': 'InstrumentName', 'Date': 'GregorianDate', 'JDate': 'JalaliDate',
             'Open': 'OpeningPrice', 'High': 'HighPrice', 'Low': 'LowPrice', 'Close': 'ClosingPrice',
             'Change': 'PriceChange', 'ChangePercent': 'PercentageChange'}
    result = frame.rename(columns=names).copy()
    for column in ('Price', 'OpeningPrice', 'HighPrice', 'LowPrice', 'ClosingPrice', 'PriceChange', 'PercentageChange'):
        if column in result:
            result[column] = _pd.to_numeric(result[column], errors='raise')
    if 'GregorianDate' in result:
        result['GregorianDate'] = _gregorian_series(result['GregorianDate'])
    if 'JalaliDate' in result:
        result['JalaliDate'] = result['JalaliDate'].map(_jalali_date)
    if 'UpdateTime' in result:
        result.insert(result.columns.get_loc('UpdateTime'), 'UpdateLabel', result['UpdateTime'])
        result['UpdateTime'] = result['UpdateTime'].map(
            lambda value: _time_string(value) if isinstance(value, str)
            and _re.fullmatch(r'[0-9]{1,2}:[0-9]{2}:[0-9]{2}', value) else _pd.NA)
    if 'UpdatedAt' in result:
        result['UpdatedAt'] = _pd.to_datetime(result['UpdatedAt'])
    if 'HasSnapshot' in result:
        result['HasSnapshot'] = result['HasSnapshot'].astype(bool)
    if 'Name' in result.attrs:
        result.attrs['InstrumentName'] = result.attrs.pop('Name')
    return result


def _resolve(client, instrument, category):
    if not isinstance(instrument, str) or not instrument.strip():
        raise ValueError('instrument must be a nonempty name or symbol from get_tgju_instruments()')
    sources = _sources(client, category)
    queries = [instrument]
    words = _re.sub(r'[_-]+', ' ', instrument)
    if words != instrument:
        queries.append(words)
    # Some new catalog symbols are not indexed verbatim by TGJU search.
    # Retry ordinary word search, but still select against the original name/symbol.
    for query in queries:
        candidates = {}
        for source in sources:
            seen = set()
            for page in range(1, _MAX_PAGES + 1):
                rows, more, count = _catalog_page(client, source, query, page)
                fingerprint = tuple(row['_id'] for row in rows)
                if count and fingerprint and fingerprint in seen:
                    raise ValueError('TGJU catalog pagination repeated; narrow the category or search')
                seen.add(fingerprint)
                for row in rows:
                    candidates[row['_id']] = row
                if not more or not count:
                    break
            else:
                raise ValueError('TGJU catalog pagination limit reached; narrow the category or search')
        needle = _norm(instrument)
        exact = [row for row in candidates.values() if needle in {
            _norm(row['Name']), _norm(row['Symbol']), _norm(row['EnglishName'] or ''), _norm(row['_raw'].get('grade') or '')}]
        matches = exact or [row for row in candidates.values() if any(needle in _norm(row[k] or '') for k in ('Name', 'EnglishName', 'Symbol'))]
        if matches:
            break
    if not matches:
        raise ValueError(f'Unknown TGJU instrument {instrument!r}; use get_tgju_instruments()')
    if len(matches) != 1:
        choices = '; '.join(f"{r['Name']} ({r['Category']}; {r['Symbol']})" for r in matches[:20])
        raise ValueError(f'Ambiguous TGJU instrument {instrument!r}: {choices}. Select a symbol from get_tgju_instruments().')
    return matches[0]


def _metadata(client, row):
    response = client.get(_SITE + 'profile/' + row['Symbol'], json_data=False)
    soup = _Soup(response.text, 'html.parser')
    title = soup.select_one('h1.title')
    if title is None:
        raise ValueError('TGJU malformed instrument profile (missing title)')
    fields = {}
    for line in soup.select('h3.line'):
        label, value = line.select_one('.label'), line.select_one('.value')
        if label is not None and value is not None:
            for link in value.select('a'):
                link.decompose()
            fields[label.get_text(' ', strip=True).rstrip(':').strip()] = value.get_text(' ', strip=True)
    if not fields:
        raise ValueError('TGJU malformed instrument profile (missing metadata)')
    details = {key: row[key] for key in _INSTRUMENT_COLUMNS}
    details.update(ProfileName=title.get_text(' ', strip=True), CurrencyName=fields.get('واحد پولی') or None,
        Unit=fields.get('واحد حجمی') or None, Country=fields.get('کشور') or None, ProfileURL=response.url,
        ProviderMetadata=fields, ProviderInstrument=dict(row['_raw']))
    return details


def get_tgju_categories():
    """گروه‌های پشتیبانی‌شده را از پیکربندی عمومی سایت کشف می‌کند.

    خروجی DataFrame با ستون‌های Category، Market و EnglishName است.
    پیکربندی ده دقیقه در حافظه می‌ماند. خطاهای شبکه از خانواده requests و
    پاسخ نامعتبر با ValueError گزارش می‌شوند. پارامتری ندارد.
    """
    with _Client() as client:
        return _public_table(_table(_categories(client), ['Category', 'Market', 'EnglishName']))


def get_tgju_instruments(category=None, *, search=None, page=1):
    """یک صفحه از فهرست عمومی نمادها را با نام فارسی یا انگلیسی دریافت می‌کند.

    category نام گروه یا None برای هر دو بازار است؛ search جستجوی اختیاری
    و page شماره صفحه از یک است. خروجی DataFrame است و attrs['has_more']
    ادامه داشتن فهرست را نشان می‌دهد؛ خروجی به معنی فهرست کامل نیست.
    پارامتر یا پاسخ نامعتبر ValueError و خطاهای شبکه استثنای requests دارند.
    """
    with _Client() as client:
        rows, attrs = _page(client, category, search, page)
        return _public_table(_table(rows, _INSTRUMENT_COLUMNS, attrs))


def get_tgju_market(category=None, *, search=None, page=1):
    """آخرین داده‌های یک صفحه نماد را از منبع عمومی ویجت می‌گیرد.

    category، search و page مانند get_tgju_instruments هستند. خروجی
    DataFrame دارای قیمت، بازگشایی، سقف، کف، تغییر و زمان اعلامی منبع است.
    HasSnapshot نبود داده را مشخص می‌کند؛ Unit در این منبع اعلام نشده است.
    زمان بدون فرض منطقه زمانی و واحد پول بدون تبدیل حفظ می‌شود.
    پاسخ/پارامتر نامعتبر ValueError و خطای شبکه استثنای requests دارد.
    """
    with _Client() as client:
        rows, attrs = _page(client, category, search, page)
        snapshots = {}
        for offset in range(0, len(rows), 20):
            ids = {r['_id'] for r in rows[offset:offset + 20]}
            data = client.get(_API + 'widget/tmp', {'keys': ','.join(sorted(ids))})
            if not isinstance(data, dict) or not isinstance(data.get('response'), dict) or not isinstance(data['response'].get('indicators'), list):
                raise ValueError('TGJU malformed market snapshot response')
            for raw in data['response']['indicators']:
                if not isinstance(raw, dict) or str(raw.get('item_id')) not in ids:
                    raise ValueError('TGJU unexpected snapshot instrument')
                if str(raw['item_id']) in snapshots and snapshots[str(raw['item_id'])] != raw:
                    raise ValueError('TGJU conflicting duplicate snapshot instrument')
                snapshots[str(raw['item_id'])] = raw
        result = []
        for row in rows:
            raw = snapshots.get(row['_id'], {})
            direction = raw.get('dt', '')
            if direction not in ('', 'high', 'low'):
                raise ValueError('TGJU invalid snapshot change direction')
            try:
                timestamp = _dt.datetime.fromisoformat(_text(raw['updated_at'])) if raw.get('updated_at') else None
            except ValueError as exc:
                raise ValueError('TGJU invalid snapshot timestamp') from exc
            result.append(dict(row, Price=_number(raw.get('p')), Open=_number(raw.get('o')),
                High=_number(raw.get('h')), Low=_number(raw.get('l')),
                Change=_signed(raw.get('d'), direction), ChangePercent=_signed(raw.get('dp'), direction),
                ChangeDirection=direction, UpdateTime=_text(raw['t']) if raw.get('t') else None,
                UpdatedAt=timestamp, Unit=None, HasSnapshot=bool(raw)))
        attrs['SourceURL'] = _API + 'widget/tmp'
        return _public_table(_table(result, _MARKET_COLUMNS, attrs))


def get_tgju_instrument_details(instrument, category=None):
    """مشخصات نماد منتخب با نام فارسی، انگلیسی یا Symbol را برمی‌گرداند.

    category گروه اختیاری برای محدود کردن جستجو است. خروجی dict شامل
    فراداده فهرست، واحد، نام پول، کشور، نشانی پروفایل و داده خام منبع است.
    نام ناشناخته/مبهم یا پاسخ نامعتبر ValueError و خطای شبکه استثنای
    requests دارد. واحدها تبدیل نمی‌شوند؛ اطلاعات اعلام‌نشده None است.
    """
    with _Client() as client:
        details = _metadata(client, _resolve(client, instrument, category))
        details["InstrumentName"] = details.pop("Name")
        return details


def get_tgju_history(instrument, category=None, *, start_date=None, end_date=None, jalali=False):
    """تاریخچه روزانه نماد را به ترتیب صعودی تاریخ در DataFrame برمی‌گرداند.

    instrument نام فارسی/انگلیسی یا Symbol، category گروه اختیاری،
    start_date و end_date حدود شامل ابتدا/انتها به صورت YYYY-MM-DD یا
    YYYY/MM/DD هستند. jalali=True تاریخ ورودی را شمسی تفسیر می‌کند؛
    پیش‌فرض میلادی است. هر دو Date و JDate در خروجی موجودند. واحد و
    منشأ در attrs حفظ می‌شوند. تکرار کاملاً یکسان حذف و ردیف متناقض حفظ
    می‌شود. نام مبهم/ناشناخته، ورودی یا پاسخ نامعتبر ValueError و خطای
    شبکه استثنای requests دارد. هیچ قیمت یا تاریخ مفقودی ساخته نمی‌شود.
    """
    if not isinstance(jalali, bool):
        raise ValueError('jalali must be a boolean')
    start, end = _date(start_date, jalali), _date(end_date, jalali)
    if start is not None and end is not None and start > end:
        raise ValueError('start_date must not be later than end_date')
    start_g = start.togregorian() if start is not None and jalali else start
    end_g = end.togregorian() if end is not None and jalali else end
    with _Client() as client:
        row = _resolve(client, instrument, category)
        details = _metadata(client, row)
        url = _API + 'market/indicator/summary-table-data/' + row['Symbol']
        params = dict(lang='fa', order_col='timestamp', order_dir='desc', length=_HISTORY_PAGE_SIZE, convert_to_ad=1)
        for key, value in [('from', start_g), ('to', end_g)]:
            if value is not None:
                params[key] = _jd.date.fromgregorian(date=value).strftime('%Y/%m/%d')
        rows, seen_pages, offset, total = [], set(), 0, None
        for _ in range(_MAX_PAGES):
            data = client.get(url, dict(params, start=offset))
            if not isinstance(data, dict) or not isinstance(data.get('data'), list):
                raise ValueError('TGJU malformed history response')
            count = data.get('recordsFiltered')
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError('TGJU invalid history record count')
            if total is not None and count != total:
                raise ValueError('TGJU history pagination changed during retrieval; retry later')
            total = count
            batch = data['data']
            if offset + len(batch) > total:
                raise ValueError('TGJU history pagination exceeds the reported record count')
            fingerprint = _json.dumps(batch, ensure_ascii=False)
            if (batch and fingerprint in seen_pages) or (not batch and offset < total):
                raise ValueError('TGJU history pagination repeated or ended prematurely')
            seen_pages.add(fingerprint)
            for values in batch:
                if not isinstance(values, list) or len(values) != 8:
                    raise ValueError('TGJU malformed daily history row')
                change, direction = _html_number(values[4])
                percent, _ = _html_number(values[5])
                rows.append(dict(Date=_date(values[6]), JDate=_date(values[7], True),
                    Open=_number(values[0]), Low=_number(values[1]), High=_number(values[2]),
                    Close=_number(values[3]), Change=change, ChangePercent=percent, ChangeDirection=direction))
            offset += len(batch)
            if offset >= total:
                break
        else:
            raise ValueError('TGJU history pagination limit reached; use a smaller date range')
        table = _table(rows, _HISTORY_COLUMNS).drop_duplicates().sort_values('Date', kind='stable').reset_index(drop=True)
        if start_g is not None or end_g is not None:
            if table.Date.isna().any():
                raise ValueError('TGJU history contains an undated observation inside a date-filtered result')
            if not table.empty:
                keep = [(start_g is None or d >= start_g) and (end_g is None or d <= end_g)
                        for d in table.Date]
                table = table.loc[keep].reset_index(drop=True)
        table.attrs.update({key: details[key] for key in ('Symbol', 'Name', 'Currency', 'CurrencyName', 'Unit', 'ProfileURL')})
        table.attrs['SourceURL'] = url
        return _public_table(table)
