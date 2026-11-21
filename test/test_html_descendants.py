"""Bounded regression for the real IFB lookup, without timing assertions."""
from bs4 import BeautifulSoup
import pytest
from soupsieve.css_match import CSSMatch

from fima._ifb_market_values import _container
from fima._html import _descendants, _find_descendant


def test_ifb_missing_container_does_not_recheck_every_ancestor(monkeypatch):
    depth = 160
    soup = BeautifulSoup('<table class="tblGrp">' * depth + '</table>' * depth, 'html.parser')
    calls = 0
    original = CSSMatch.match_selectors

    def counted(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(CSSMatch, 'match_selectors', counted)
    with pytest.raises(ValueError, match='table missing'):
        _container(soup)
    assert calls <= depth * 12  # A constant amount of selector work per tag.


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


def test_deep_markup_is_iterative_and_does_not_duplicate_results():
    depth = 1200
    soup = BeautifulSoup('<div class="pager">' * depth + '<a title="Next page">next</a>'
                         + '</div>' * depth, 'html.parser')
    assert list(_descendants(soup, '.pager', '.pager', "a[title='Next page']")) == [soup.a]
    assert list(_descendants(soup, 'tfoot', '.pager', 'a')) == []


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
