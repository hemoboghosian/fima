"""Small extraction fixtures preserve provider selector behavior."""
from bs4 import BeautifulSoup
import pytest

from fima._ifb_market_values import _container
from fima._html import _descendants, _find_descendant


@pytest.mark.parametrize('parts', [
    ('div.sizeselector', "select[name*='grdFinancialData']"),
    ('.panelheader', 'label'),
    ("table[id$='grdPBs']", 'tr.pgr'),
    ("table[id$='grdFinancialData']", 'tr.pgr'),
    ('#ContentPlaceHolder1_tblContainer', 'table.tblGrp'),
    ('thead', 'th'), ('tbody', 'tr'),
    ('tfoot', '.pager', "a[title='Next page']"),
    ('[data-testid="trend-table"]', 'table'),
])
def test_provider_chains_preserve_css_scope_order_and_uniqueness(parts):
    # Nested matching containers, wrappers, unrelated lookalikes, and attributes
    # containing spaces must retain exactly the original selector semantics.
    html = '''<section><div id="root">
    <select name="grdFinancialData" id="unrelated"></select>
    <div class="sizeselector"><div class="sizeselector"><span>
      <select name="ctl00$grdFinancialData$size"></select></span></div></div>
    <div class="panelheader"><span><label>section</label></span></div>
    <div id="ContentPlaceHolder1_tblContainer"><div><table class="tblGrp">
      <thead><tr><th>price</th><th>date</th></tr></thead>
      <tbody><tr><td>9007199254740993</td></tr></tbody>
      <tfoot><tr><td class="pager"><div class="pager"><a title="Next page">next</a>
      </div></td></tr></tfoot></table></div><table class="tblGrp"></table></div>
    <table id="ctl00_grdPBs"><tr class="pgr"></tr></table>
    <table id="ctl00_grdFinancialData"><tr class="pgr"></tr></table>
    <div data-testid="trend-table"><div data-testid="trend-table">
      <table><tbody><tr><td>1</td></tr></tbody></table></div><table></table></div>
    </div></section>'''
    soup = BeautifulSoup(html, 'html.parser')
    for root in (soup, soup.find(id='root')):
        expected = root.select(' '.join(parts))
        assert [id(tag) for tag in _descendants(root, *parts)] == [id(tag) for tag in expected]
        assert _find_descendant(root, *parts) is (expected[0] if expected else None)


def test_root_and_external_ancestors_match_but_are_never_returned():
    soup = BeautifulSoup('<section><div id="root"><a/><p><a/></p></div><a/></section>', 'html.parser')
    root = soup.find(id='root')
    for parts in [('section', 'a'), ('div', 'a'), ('section', 'div', 'a')]:
        assert [id(t) for t in _descendants(root, *parts)] == [id(t) for t in root.select(' '.join(parts))]


def test_nested_pagers_do_not_duplicate_the_next_link():
    soup = BeautifulSoup('<div class="pager"><span><div class="pager">'
                         '<a title="Next page">next</a></div></span></div>', 'html.parser')
    assert list(_descendants(soup, '.pager', '.pager', "a[title='Next page']")) == [soup.a]
    assert list(_descendants(soup, 'tfoot', '.pager', 'a')) == []


def test_nested_financial_rows_preserve_exact_values_and_order():
    soup = BeautifulSoup('<table><thead><tr><th>Date</th><th>MarketValue</th></tr></thead>'
                         '<tbody><tr><td>1405/08/17</td><td>9007199254740993</td></tr>'
                         '<tr><td>1405/08/16</td><td>0</td></tr></tbody></table>', 'html.parser')
    headers = [tag.get_text() for tag in _descendants(soup, 'thead', 'th')]
    rows = [[td.get_text() for td in tr.find_all('td', recursive=False)]
            for tr in _descendants(soup, 'tbody', 'tr')]
    assert headers == ['Date', 'MarketValue']
    assert rows == [['1405/08/17', '9007199254740993'], ['1405/08/16', '0']]
    assert rows == [[td.get_text() for td in tr.find_all('td', recursive=False)]
                    for tr in soup.select('tbody tr')]


@pytest.mark.parametrize('html', ['', '<div><table class="other"></div>', '<table class="tblGrp"></table>'])
def test_missing_or_malformed_container_keeps_explicit_failure(html):
    with pytest.raises(ValueError, match='table missing'):
        _container(BeautifulSoup(html, 'html.parser'))


def test_ifb_multiple_tables_keep_first_matching_table_not_unrelated_table():
    soup = BeautifulSoup('<table class="tblGrp" id="outside"></table>'
                         '<div id="ContentPlaceHolder1_tblContainer">'
                         '<span><table class="tblGrp" id="first"></table></span>'
                         '<table class="tblGrp" id="second"></table></div>', 'html.parser')
    assert _container(soup)['id'] == 'first'
