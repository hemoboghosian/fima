"""Official IFB fixed-income observations; no calculations or import-time I/O."""
from collections import Counter
from datetime import date
import math
import re
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup
import jdatetime as jd
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ._data import jalali_date, number_series, text_or_na


_URL = 'https://ifb.ir/YTM.aspx'
_P = 'ctl00$ContentPlaceHolder1$'
_TIMEOUT = (10, 30)
_GRID_HEADER = ['ردیف', 'نماد', 'تاریخ آخرین روز معاملاتی', 'تاریخ انتشار',
                'تاریخ سررسید', 'قبمت پایانی', 'حجم', 'YTM']
_EXPORT_HEADER = ['نام نماد', 'تاریخ آخرین معامله', 'تاریخ انتشار', 'تاریخ سررسید',
                  'قیمت پایانی', 'حجم', 'YTM']
_DATE_COLUMNS = ['LastTradeJalaliDate', 'IssueJalaliDate', 'MaturityJalaliDate']
_RAW_COLUMNS = ['Ticker', *_DATE_COLUMNS, 'ClosingPrice', 'TradeVolume', 'YTM']


def _text(value):
    return re.sub(r'\s+', ' ', str(value)).strip()


def _session():
    session = requests.Session()
    retry = Retry(total=1, connect=1, read=0, status=1, backoff_factor=.25,
                  status_forcelist=(502, 503, 504), allowed_methods=('GET', 'POST'),
                  respect_retry_after_header=False, raise_on_status=False)
    session.mount('https://', HTTPAdapter(max_retries=retry))
    return session


def _date(value, *, required=False):
    text = text_or_na(value)
    if text is pd.NA:
        if required:
            raise ValueError('IFB missing required history date.')
        return pd.NA
    if not re.fullmatch(r'\d{4}[-/]\d{2}[-/]\d{2}', text):
        raise ValueError(f'IFB invalid history date: {value!r}')
    try:
        return jalali_date(text)
    except ValueError as error:
        raise ValueError(f'IFB invalid history date: {value!r}') from error


def _bounds(start, end, jalali):
    if not isinstance(jalali, bool):
        raise ValueError('IFB jalali must be True or False.')
    result = []
    for value in (start, end):
        if not isinstance(value, str):
            raise ValueError('IFB both date bounds must be YYYY-MM-DD strings.')
        if jalali:
            result.append(_date(value, required=True))
        else:
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                    raise ValueError('Expected YYYY-MM-DD')
                result.append(jd.date.fromgregorian(date=date.fromisoformat(value)).isoformat())
            except ValueError as error:
                raise ValueError(f'IFB invalid Gregorian history bound: {value!r}') from error
    if result[0] > result[1]:
        raise ValueError('IFB start_date must not exceed end_date.')
    return result


def _form(soup):
    data = {x['name']: x.get('value', '') for x in soup.select('input[name]')
            if x.get('type', 'text').lower() in ('hidden', 'text')}
    if not data.get('__VIEWSTATE'):
        raise ValueError('IFB YTM WebForms state missing.')
    for select in soup.select('select[name]'):
        options = select.select('option[selected]') or select.select('option')[:1]
        if options:
            data[select['name']] = options[0].get('value', '')
    return data


def _identity(soup, ticker, instrument_id):
    select = soup.find('select', attrs={'name': _P+'SymbolComboboxYTMHistory'})
    if select is None:
        raise ValueError('IFB history instrument selector missing.')
    options = [(o.get('value', ''), _text(o.get_text())) for o in select.select('option')
               if o.get('value', '') != '-1']
    if not options or any(not i.isascii() or not i.isdigit() for i, _ in options):
        raise ValueError('IFB history instrument IDs malformed.')
    matches = [(i, n) for i, n in options if (instrument_id is None or i == instrument_id)
               and (ticker is None or n == _text(ticker))]
    if len(matches) != 1:
        raise ValueError('IFB instrument missing or ambiguous; use an exact published instrument_id.')
    return matches[0]


def _frame(rows, instrument_id, ticker, start, end):
    frame = pd.DataFrame(rows, columns=_RAW_COLUMNS)
    frame.insert(0, 'InstrumentID', pd.Series([instrument_id] * len(frame), dtype='string'))
    if not frame.Ticker.eq(ticker).all():
        raise ValueError('IFB export contains another instrument ticker.')
    for column in _DATE_COLUMNS:
        frame[column] = frame[column].map(lambda v: _date(v, required=column == 'LastTradeJalaliDate'))
        gregorian = column.replace('Jalali', 'Gregorian')
        frame[gregorian] = pd.to_datetime(frame[column].map(
            lambda v: jd.date(*map(int, v.split('-'))).togregorian() if pd.notna(v) else None))
    if not frame.LastTradeJalaliDate.between(start, end).all():
        raise ValueError('IFB history export ignored the requested date bounds.')
    try:
        frame['ClosingPrice'] = number_series(frame.ClosingPrice.map(lambda v: v.replace('/', '.')))
        quantities = []
        for value in frame.TradeVolume:
            text = text_or_na(value)
            if text is pd.NA:
                quantities.append(pd.NA)
            else:
                text = text.replace(',', '').replace('٬', '')
                if not text.isdigit() or int(text) > 2**63-1:
                    raise ValueError('Invalid security volume')
                quantities.append(int(text))
        frame['TradeVolume'] = pd.array(quantities, dtype='Int64')
        for value in frame.YTM:
            if text_or_na(value) is not pd.NA and not value.endswith(('%', '٪')):
                raise ValueError('YTM percentage marker missing')
        frame['YTM'] = number_series(frame.YTM.map(lambda v: v.replace('/', '.')))
        if any(not values.dropna().map(math.isfinite).all() for values in (frame.ClosingPrice, frame.YTM)):
            raise ValueError('Nonfinite financial value')
    except (ValueError, TypeError) as error:
        raise ValueError(f'IFB malformed history financial value: {error}') from error
    return frame


_CURVE_METHODS = {'treasury': 'GetITBtNelsonIndex',
                  'government': 'GetGovermentNelsonIndex',
                  'nongovernment': 'GetNonGovermentNelsonIndex'}
_CURVE_COLUMNS = ['CurveCategory', 'ComparisonLabel', 'ComparisonEnglishLabel', 'TenorDays', 'YTM']


def get_ifb_yield_curve(category='treasury') -> pd.DataFrame:
    """Return official fitted YTM comparison nodes from IFB's Nelson page.

    category is treasury, government or nongovernment. TenorDays is remaining
    maturity in days; YTM is effective annual percentage points, without rounding.
    Published Persian/English comparison labels are preserved verbatim. These are
    relative comparison snapshots, without verified calibration dates, not daily
    history, spot or forward rates. No interpolation or fitting is performed.

    A valid empty envelope returns the typed schema. Invalid input, changed or
    incomplete provider data raises ValueError; HTTP/request errors propagate.
    See docs/ifb.md for fields, sources and financial limitations.
    """
    if not isinstance(category, str) or category not in _CURVE_METHODS:
        raise ValueError('IFB curve category must be treasury, government or nongovernment.')
    url = 'https://ifb.ir/HistoricalInstrumentData.asmx/' + _CURVE_METHODS[category]
    with _session() as session:
        response = session.post(url, headers={'Content-Type': 'application/json; charset=utf-8'},
                                timeout=_TIMEOUT)
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as error:
            raise ValueError('IFB fitted curve response is not JSON.') from error
    if not isinstance(payload, dict) or not isinstance(payload.get('d'), list):
        raise ValueError('IFB fitted curve envelope changed.')
    series = payload['d']
    if series and len(series) != 3:
        raise ValueError('IFB fitted curve comparison series incomplete/changed.')
    rows, labels = [], set()
    for points in series:
        if not isinstance(points, list) or not points:
            raise ValueError('IFB fitted curve comparison series missing.')
        label, tenors = None, set()
        for point in points:
            if not isinstance(point, dict) or set(point) != {'Date', 'EnDate', 'DayNum', 'Value'}:
                raise ValueError('IFB fitted curve node schema changed.')
            current = (point['Date'], point['EnDate'])
            if any(not isinstance(v, str) or not v.strip() for v in current):
                raise ValueError('IFB fitted curve comparison labels missing.')
            if label is not None and current != label:
                raise ValueError('IFB fitted curve comparison labels inconsistent.')
            label = current
            tenor = point['DayNum']
            if (isinstance(tenor, bool) or not isinstance(tenor, (int, float))
                    or not math.isfinite(tenor) or tenor <= 0 or tenor != int(tenor)
                    or tenor > 2**63-1 or tenor in tenors):
                raise ValueError('IFB fitted curve tenor invalid or duplicated.')
            tenors.add(tenor)
            value = point['Value']
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                      or not math.isfinite(value)):
                raise ValueError('IFB fitted curve YTM must be finite numeric or null.')
            rows.append([category, *current, int(tenor), value])
        if label in labels:
            raise ValueError('IFB fitted curve comparison series duplicated.')
        labels.add(label)
    frame = pd.DataFrame(rows, columns=_CURVE_COLUMNS)
    frame['TenorDays'] = pd.array(frame.TenorDays, dtype='Int64')
    frame['YTM'] = pd.to_numeric(frame.YTM)
    frame.attrs = {'SourceURL': url, 'SourcePageURL': 'https://ifb.ir/NelsonIndex.aspx',
                   'Snapshot': True, 'TenorUnit': 'Days', 'YieldUnit': 'PercentagePoints'}
    return frame


def _signatures(frame):
    # Missing observations compare equal, without coercing integer volumes to float.
    return Counter(tuple(None if pd.isna(v) else v for v in row)
                   for row in frame[_RAW_COLUMNS].itertuples(index=False, name=None))


def _grid(soup, instrument_id, ticker, start, end):
    error = soup.select_one('#ContentPlaceHolder1_lblerror')
    if error is not None and error.get_text(strip=True):
        raise ValueError(f'IFB history filter rejected: {_text(error.get_text())}')
    table = soup.select_one('#ContentPlaceHolder1_ytmHistoryGride')
    if table is None:
        raise ValueError('IFB history grid missing; not a valid empty response.')
    text = _text(table.get_text(' ', strip=True))
    if text in ('.داده ای یافت نشد', 'داده ای یافت نشد.'):
        return _frame([], instrument_id, ticker, start, end), False
    rows = table.find_all('tr', recursive=False)
    if not rows and table.tbody:
        rows = table.tbody.find_all('tr', recursive=False)
    if not rows or [_text(c.get_text()) for c in rows[0].find_all(['th', 'td'])] != _GRID_HEADER:
        raise ValueError('IFB historical grid header changed.')
    data, more = [], False
    for row in rows[1:]:
        if 'pgr' in row.get('class', []):
            more = bool(row.select('a[href*="Page$"]'))
            continue
        cells = row.find_all('td', recursive=False)
        if len(cells) != 8:
            raise ValueError('IFB historical grid row changed/truncated.')
        link = cells[1].find('a', href=True)
        ids = parse_qs(urlparse(link['href']).query).get('id', []) if link else []
        if (not link or ids != [instrument_id] or link.get('symbolid_fk') != instrument_id
                or _text(cells[0].get_text()) != str(len(data)+1)):
            raise ValueError('IFB historical grid instrument identity/order changed.')
        data.append([_text(c.get_text(' ', strip=True)) for c in cells[1:]])
    if not data:
        raise ValueError('IFB unexplained empty history grid.')
    return _frame(data, instrument_id, ticker, start, end), more


def get_ifb_bond_yield_history(start_date, end_date, ticker=None, *, instrument_id=None,
                             jalali=True, on_conflict='raise') -> pd.DataFrame:
    """Download a verified instrument's complete official filtered YTM export.

    Both inclusive YYYY-MM-DD bounds are required; jalali=False selects Gregorian
    inputs. Supply an exact ticker or a string IFB instrument_id (ambiguous names
    require the ID). Returns instrument identity, last-trade/issue/maturity dates
    in both calendars, ClosingPrice in rials, TradeVolume in securities, YTM in
    effective annual percentage points and HasConflictingObservation.

    Identical repeats are normalized with provenance in attrs. Conflicting
    dates raise ValueError unless on_conflict='preserve', which retains and flags
    each distinct source observation. Valid empty filters return the typed schema.
    HTTP/request errors propagate; malformed/incomplete responses raise ValueError.
    This is provider archive coverage, not guaranteed continuous market history.
    Existing bond snapshots/risk-free calculations are not used or modified.
    See docs/ifb.md for the full schema, sources and financial limitations.
    """
    start, end = _bounds(start_date, end_date, jalali)
    if on_conflict not in ('raise', 'preserve'):
        raise ValueError("IFB on_conflict must be 'raise' or 'preserve'.")
    if ticker is None and instrument_id is None:
        raise ValueError('IFB an exact ticker or instrument_id is required.')
    for value in (ticker, instrument_id):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError('IFB instrument selectors must be nonempty strings.')
    with _session() as session:
        response = session.get(_URL, timeout=_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        selected_id, selected_ticker = _identity(soup, ticker, instrument_id)
        data = _form(soup)
        data.update({_P+'SymbolComboboxYTMHistory': selected_id, _P+'TxtDateFrom': start.replace('-', '/'),
                     _P+'TxtDateTo': end.replace('-', '/'), _P+'Button1': 'فیلتر'})
        response = session.post(_URL, data=data, timeout=_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        data = _form(soup)
        if (data.get(_P+'SymbolComboboxYTMHistory') != selected_id
                or _date(data.get(_P+'TxtDateFrom'), required=True) != start
                or _date(data.get(_P+'TxtDateTo'), required=True) != end):
            raise ValueError('IFB history filter state was not preserved.')
        visible, more = _grid(soup, selected_id, selected_ticker, start, end)
        frame = visible
        if not visible.empty:
            data[_P+'btnYTMHistoryExport'] = 'خروجی اکسل'
            response = session.post(_URL, data=data, timeout=_TIMEOUT)
            response.raise_for_status()
            try:
                body = response.content.decode('utf-8-sig', errors='strict')
            except UnicodeError as error:
                raise ValueError('IFB historical export is not valid UTF-8.') from error
            if ('application/vnd.ms-excel' not in response.headers.get('Content-Type', '').lower()
                    or not body.rstrip().lower().endswith('</table>')):
                raise ValueError('IFB history export is not a complete HTML-table Excel download.')
            tables = BeautifulSoup(body, 'html.parser').find_all('table')
            if len(tables) != 1:
                raise ValueError('IFB history export table structure changed.')
            rows = [[_text(c.get_text(' ', strip=True)) for c in row.find_all('td', recursive=False)]
                    for row in tables[0].find_all('tr')]
            if not rows or rows[0] != _EXPORT_HEADER or any(len(r) != 7 for r in rows[1:]):
                raise ValueError('IFB history export columns changed/truncated.')
            frame = _frame(rows[1:], selected_id, selected_ticker, start, end)
            if (_signatures(visible) - _signatures(frame)) or (more and len(frame) <= len(visible)):
                raise ValueError('IFB history export incomplete: missing visible records or later pages.')
    count = len(frame)
    frame = frame.drop_duplicates().copy()
    conflicts = frame.LastTradeJalaliDate.duplicated(keep=False)
    conflict_dates = sorted(frame.loc[conflicts, 'LastTradeJalaliDate'].unique().tolist())
    if conflict_dates and on_conflict == 'raise':
        raise ValueError(f'IFB conflicting historical observations on {conflict_dates}; '
                         "use on_conflict='preserve' to inspect flagged source records.")
    frame['HasConflictingObservation'] = conflicts.astype(bool)
    frame = frame.sort_values('LastTradeJalaliDate', kind='stable').reset_index(drop=True)
    frame.attrs = {'SourceURL': _URL, 'Snapshot': False, 'PriceUnit': 'IRR',
                   'YieldUnit': 'PercentagePoints', 'VolumeUnit': 'Securities',
                   'ExportRowCount': count, 'DuplicateRowCount': count-len(frame),
                   'ConflictingDates': conflict_dates}
    return frame
