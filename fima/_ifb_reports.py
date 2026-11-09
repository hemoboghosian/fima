"""Bounded discovery of IFB's public statistical-report catalog, not its contents."""
from datetime import date
import re
import time
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup
import jdatetime as jd
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ._data import jalali_date


_URL = 'https://ifb.ir/datareporter/periodicalreport.aspx'
_P = 'ctl00$ContentPlaceHolder1$'
_TIMEOUT = (30, 30)
_TYPES = {'trading': ('1', 'آمار معاملات'), 'descriptive': ('2', 'گزارش آماری توصیفی'),
          'ranking': ('5', 'رتبه‌بندی')}
_PERIODS = {'daily': ('10', 'روزانه'), 'weekly': ('20', 'هفتگی'),
            'monthly': ('30', 'ماهانه'), 'annual': ('40', 'سالانه')}
_BREAKDOWNS = {'market': 'بازار', 'industry': 'صنعت', 'symbol': 'نماد',
               'investor_type': 'حقیقی و حقوقی', 'trade_side': 'خرید و فروش',
               'channel': 'برخط و ایستگاه', 'broker': 'کارگزاری'}
_HEADER = ['ردیف', 'نوع گزارش', 'دوره گزارش', 'منتهی به', 'به تفکیک',
           'تاریخ بارگزاری', 'توضیحات', 'فایل']
_COLUMNS = ['ReportID', 'Title', 'ReportType', 'ReportingPeriod', 'PeriodEndJalaliDate',
            'PeriodEndGregorianDate', 'Breakdown', 'UploadJalaliDate', 'UploadGregorianDate',
            'ExcelURL', 'PDFURL']


def _text(value):
    return re.sub(r'\s+', ' ', str(value)).strip()


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}[-/][0-9]{2}[-/][0-9]{2}', value.strip()):
        raise ValueError('IFB report date must be YYYY-MM-DD.')
    try:
        return jalali_date(value.strip())
    except ValueError as error:
        raise ValueError('IFB invalid report date.') from error


def _session():
    session = requests.Session()
    retry = Retry(total=1, connect=1, read=0, status=1, backoff_factor=.25,
                  status_forcelist=(502, 503, 504), allowed_methods=('GET', 'POST'),
                  respect_retry_after_header=False, raise_on_status=False)
    session.mount('https://', HTTPAdapter(max_retries=retry))
    return session


def _form(soup):
    data = {tag['name']: tag.get('value', '') for tag in soup.select('input[name]')
            if tag.get('type', 'text') in ('hidden', 'text')
            or (tag.get('type') == 'checkbox' and tag.has_attr('checked'))}
    for select in soup.select('select[name]'):
        option = select.select_one('option[selected]') or select.select_one('option')
        if option is None:
            raise ValueError('IFB report form selector is empty.')
        data[select['name']] = option.get('value', '')
    if not data.get('__VIEWSTATE') or any(_P+name not in data for name in
                                         ('FromDT', 'ToDT', 'txtTitle', 'comboReportType', 'comboReportPeriod')):
        raise ValueError('IFB report WebForms state/controls missing.')
    for name, mapping in (('comboReportType', _TYPES), ('comboReportPeriod', _PERIODS)):
        select = soup.find('select', attrs={'name': _P+name})
        if select is None:
            raise ValueError('IFB report filter selector missing.')
        options = {o.get('value'): _text(o.get_text()) for o in select.select('option')}
        if options != {'0': 'همه', **{v: label for v, label in mapping.values()}}:
            raise ValueError('IFB report filter categories changed.')
    checks = soup.select(f'input[name^="{_P}TafkikCheckboxlist$"]')
    if len(checks) != len(_BREAKDOWNS):
        raise ValueError('IFB report breakdown controls changed.')
    for i, (check, label) in enumerate(zip(checks, _BREAKDOWNS.values())):
        caption = soup.find('label', attrs={'for': check.get('id')})
        if (check.get('name') != _P+f'TafkikCheckboxlist${i}' or check.get('value') != str(2**i)
                or caption is None or _text(caption.get_text()) != label):
            raise ValueError('IFB report breakdown meanings changed.')
    return data


def _files(cell):
    rid, urls = None, {}
    for link in cell.select('a[href]'):
        if any(tag.has_attr('hidden') or re.search(r'display\s*:\s*none', tag.get('style', ''), re.I)
               for tag in [link, *link.parents] if getattr(tag, 'attrs', None) is not None):
            continue
        url = urljoin(_URL, link['href'])
        parsed = urlparse(url)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if (parsed.scheme != 'https' or parsed.netloc != 'ifb.ir' or parsed.fragment
                or parsed.path != '/GetFiles/GetPeriodicalFile.aspx' or set(query) != {'id', 'type', 'EnData'}
                or any(len(v) != 1 for v in query.values()) or query['EnData'] != ['False']
                or query['type'][0] not in ('Excel', 'PDF') or not re.fullmatch(r'[0-9]+', query['id'][0])):
            raise ValueError('IFB report file URL/format/identity changed.')
        current, fmt = query['id'][0], query['type'][0]
        if (rid is not None and rid != current) or fmt in urls:
            raise ValueError('IFB report file IDs conflict or formats repeat.')
        rid, urls[fmt] = current, url
    if rid is None:
        raise ValueError('IFB report has no verified visible Excel/PDF identity.')
    return rid, urls.get('Excel'), urls.get('PDF')


def _page(soup, current, expected):
    data = _form(soup)
    if any(data.get(k) != v for k, v in expected.items()) or any(
            'TafkikCheckboxlist$' in k and k not in expected for k in data):
        raise ValueError('IFB report filters were not preserved.')
    error = soup.select_one('#ContentPlaceHolder1_Label3')
    if error is None or error.get_text(strip=True):
        raise ValueError('IFB report filter error/validation label changed.')
    table = soup.select_one('#ContentPlaceHolder1_grdPRs')
    if table is None:
        raise ValueError('IFB report grid missing; not a valid empty search.')
    rows = table.find_all('tr', recursive=False)
    if not rows and table.tbody:
        rows = table.tbody.find_all('tr', recursive=False)
    if _text(table.get_text(' ', strip=True)) == '.داده ای یافت نشد':
        if current != 1:
            raise ValueError('IFB report later page unexpectedly empty.')
        return [], (0, (), 0)
    if not rows or [_text(c.get_text()) for c in rows[0].find_all(['td', 'th'])] != _HEADER:
        raise ValueError('IFB report header changed.')
    records, pager = [], None
    for row in rows[1:]:
        if 'pgr' in row.get('class', []):
            if pager is not None:
                raise ValueError('IFB report pager duplicated.')
            pager = row
            continue
        cells = row.find_all('td', recursive=False)
        if len(cells) != 8 or _text(cells[0].get_text()) != str((current-1)*50+len(records)+1):
            raise ValueError('IFB report row/order incomplete or repeated.')
        kind, period, end, breakdown, upload, title = [_text(c.get_text(' ', strip=True)) for c in cells[1:7]]
        if (kind not in {v[1] for v in _TYPES.values()} or period not in {v[1] for v in _PERIODS.values()}
                or not title or not breakdown):
            raise ValueError('IFB report metadata missing/changed.')
        end, upload = _date(end), _date(upload)
        if not expected[_P+'FromDT'].replace('/', '-') <= end <= expected[_P+'ToDT'].replace('/', '-'):
            raise ValueError('IFB report period-end date filter ignored.')
        for control, label, mapping in (('comboReportType', kind, _TYPES), ('comboReportPeriod', period, _PERIODS)):
            selected = expected[_P+control]
            if selected != '0' and (selected, label) not in mapping.values():
                raise ValueError('IFB report category filter ignored.')
        selected = [label for i, label in enumerate(_BREAKDOWNS.values()) if _P+f'TafkikCheckboxlist${i}' in expected]
        if selected and selected[0] not in breakdown.split('، '):
            raise ValueError('IFB report breakdown filter ignored.')
        rid, excel, pdf = _files(cells[-1])
        records.append([rid, title, kind, period, end, breakdown, upload, excel, pdf])
    nav = pager.find('table') if pager else None
    size = pager.select_one('select[name]') if pager else None
    if nav is None or size is None or data.get(size['name']) != '50' or not 1 <= len(records) <= 50:
        raise ValueError('IFB report pager/page size/count changed.')
    numbers, active, last = [], [], None
    for cell in nav.find_all('td'):
        link, span = cell.find('a', href=True), cell.find('span')
        if link:
            match = re.fullmatch(r"javascript:__doPostBack\('"+re.escape(_P)+r"grdPRs','Page\$(\d+)'\)", link['href'])
            if not match or _text(link.get_text()) not in (match[1], '...'):
                raise ValueError('IFB report pager link changed.')
            numbers.append(int(match[1]))
        elif span and span.get_text(strip=True).isascii() and span.get_text(strip=True).isdigit():
            numbers.append(int(span.get_text(strip=True)))
            active.append(numbers[-1])
        else:
            raise ValueError('IFB report pager structure changed.')
    if active != [current] or numbers != sorted(set(numbers)) or not numbers or numbers[0] < 1:
        raise ValueError('IFB report pager current page/count changed.')
    if _text(nav.find_all('td')[-1].get_text()) != '...':
        last = numbers[-1]
    if numbers[-1] > current and current+1 not in numbers:
        raise ValueError('IFB report next page missing.')
    if last != current and len(records) != 50:
        raise ValueError('IFB report nonterminal page incomplete.')
    return records, (current, tuple(numbers), last)


def get_ifb_periodical_reports(start_date, end_date, *, report_type=None, reporting_period=None,
                               title=None, breakdown=None, jalali=True, max_pages=20) -> pd.DataFrame:
    """Discover all official reports in an inclusive reporting-period-end window.

    Both YYYY-MM-DD bounds are required, Jalali by default or Gregorian with
    jalali=False. Optional source filters: report_type trading/descriptive/ranking;
    reporting_period daily/weekly/monthly/annual; title (1..40 characters); one
    breakdown market/industry/symbol/investor_type/trade_side/channel/broker.
    max_pages is 1..100 (default 20), 50 records per page, per validation pass.

    Returns typed report IDs, source titles/categories/breakdowns, period-end and
    upload dates in both calendars, and visible official Excel/PDF URLs. Two
    complete traversals must match. Missing dates/financial observations are not
    invented; report titles are not deduplicated. This retrieves metadata only.
    Valid empty searches retain the schema. Invalid input, schema/filter changes,
    incomplete/changed catalogs or page limits raise ValueError. HTTP/network
    errors propagate. See docs/ifb.md for the full contract and limitations.
    """
    if not isinstance(jalali, bool) or type(max_pages) is not int or not 1 <= max_pages <= 100:
        raise ValueError('IFB jalali must be boolean and max_pages must be an integer in 1..100.')
    bounds = []
    for value in (start_date, end_date):
        if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
            raise ValueError('IFB both report date bounds must be YYYY-MM-DD strings.')
        try:
            bounds.append(_date(value) if jalali else jd.date.fromgregorian(date=date.fromisoformat(value)).isoformat())
        except ValueError as error:
            raise ValueError('IFB invalid report date bound.') from error
    if bounds[0] > bounds[1]:
        raise ValueError('IFB start_date must not exceed end_date.')
    for value, mapping in ((report_type, _TYPES), (reporting_period, _PERIODS), (breakdown, _BREAKDOWNS)):
        if value is not None and (not isinstance(value, str) or value not in mapping):
            raise ValueError(f'IFB report selector must be one of {list(mapping)} or None.')
    if title is not None and (not isinstance(title, str) or not title.strip() or len(title) > 40):
        raise ValueError('IFB report title must contain 1..40 characters or be None.')
    expected = {_P+'FromDT': bounds[0].replace('-', '/'), _P+'ToDT': bounds[1].replace('-', '/'),
                _P+'comboReportType': _TYPES[report_type][0] if report_type else '0',
                _P+'comboReportPeriod': _PERIODS[reporting_period][0] if reporting_period else '0',
                _P+'txtTitle': title or ''}
    if breakdown:
        i = list(_BREAKDOWNS).index(breakdown)
        expected[_P+f'TafkikCheckboxlist${i}'] = str(2**i)
    passes = []
    with _session() as session:
        response = session.get(_URL, timeout=_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for _ in range(2):
            records, topology, seen, known_last = [], [], set(), None
            for current in range(1, max_pages+1):
                data = _form(soup)
                if current == 1:
                    data = {k: v for k, v in data.items() if 'TafkikCheckboxlist$' not in k}
                    data.update(expected)
                    for key in data:
                        if key.startswith(_P+'grdPRs$'):
                            data[key] = '50'
                    data.update({'__EVENTTARGET': '', '__EVENTARGUMENT': '', _P+'BtnSearch': 'جستجو'})
                else:
                    data.update({'__EVENTTARGET': _P+'grdPRs', '__EVENTARGUMENT': f'Page${current}'})
                time.sleep(.25)
                response = session.post(_URL, data=data, timeout=_TIMEOUT)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                rows, info = _page(soup, current, expected)
                _, numbers, last = info
                if numbers and max(numbers) > max_pages:
                    raise ValueError('IFB report page limit exceeded; narrow the date window or increase max_pages.')
                if known_last is not None and last != known_last:
                    raise ValueError('IFB report page count changed during retrieval.')
                if last is not None:
                    known_last = last
                for row in rows:
                    if row[0] in seen:
                        raise ValueError('IFB report duplicate ID/repeated page; retrieval incomplete.')
                    seen.add(row[0])
                records.extend(rows)
                topology.append(info)
                if not rows or last == current:
                    break
            else:
                raise ValueError('IFB report page limit reached without a verified last page.')
            passes.append((records, topology))
        if passes[0] != passes[1]:
            raise ValueError('IFB report catalog changed between validation passes; retry a narrower window.')
    frame = pd.DataFrame(passes[0][0], columns=['ReportID', 'Title', 'ReportType', 'ReportingPeriod',
                                               'PeriodEndJalaliDate', 'Breakdown', 'UploadJalaliDate', 'ExcelURL', 'PDFURL'])
    for name in frame:
        frame[name] = frame[name].astype('string')
    for prefix in ('PeriodEnd', 'Upload'):
        frame[prefix+'GregorianDate'] = pd.to_datetime(frame[prefix+'JalaliDate'].map(
            lambda value: jd.date(*map(int, value.split('-'))).togregorian()))
    frame = frame[_COLUMNS]
    frame.attrs = {'SourceURL': _URL, 'Snapshot': True, 'RecordCount': len(frame),
                   'PageCount': len(passes[0][1]) if len(frame) else 0, 'ValidationPasses': 2,
                   'FilterDateField': 'PeriodEndJalaliDate',
                   'Filters': {'StartJalaliDate': bounds[0], 'EndJalaliDate': bounds[1],
                               'ReportType': report_type, 'ReportingPeriod': reporting_period,
                               'Title': title, 'Breakdown': breakdown}}
    return frame
