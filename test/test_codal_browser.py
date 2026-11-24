"""Deterministic coverage of the optional browser's lifecycle and handoff."""

from contextlib import contextmanager
import sys
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from fima import _codal_browser as browser, codal


class FakePlaywrightError(Exception):
    pass


class Response:
    def __init__(self, url, status=200, headers=None):
        self.url = url
        self.status = status
        self.headers = headers or {"content-type": "text/html"}
        self.request = SimpleNamespace(url=url, redirected_from=None)
        self.disposed = False

    def dispose(self):
        self.disposed = True

    def body(self):
        return b"\xef\xbb\xbf<html>server response</html>\r\n"


class Page:
    def __init__(self):
        self.actions = []
        self.visible = True
        self.closed = False
        self.after_wait = None
        self.search_outcome = None
        self.status = 200

    def goto(self, url, *, wait_until, timeout):
        assert wait_until == "domcontentloaded"
        assert 0 < timeout <= 25_000
        self.url = url
        self.actions.append(("goto", url))
        return Response(url, self.status)

    def locator(self, selector):
        self.actions.append(("locator", selector))
        return SimpleNamespace(first=SimpleNamespace(is_visible=lambda: self.visible))

    def is_closed(self):
        return self.closed

    def evaluate(self, script, args=None):
        self.actions.append(("evaluate", script, args))
        if script == browser._WATCH_SEARCH:
            return True
        if script == browser._SEARCH_REQUEST:
            return {"status": 200, "type": "application/json", "retryAfter": None, "text": '{"IsAttacker":false}'}
        assert script == "() => window.fimaCodalVerification"
        return self.search_outcome

    def wait_for_timeout(self, delay):
        assert 0 < delay <= 200
        self.after_wait()


@pytest.fixture
def chromium(monkeypatch, tmp_path):
    executable = tmp_path / "chromium"
    executable.touch()
    actions = []
    tick = [10]
    callbacks = {}
    report_calls = []

    def new_page():
        page = Page()
        page.after_wait = lambda: tick.__setitem__(0, tick[0] + 250)
        return page

    def get(url, **kwargs):
        response = Response(url)
        report_calls.append((response, kwargs))
        return response

    def launch(**kwargs):
        actions.append(("launch", kwargs))
        return runtime

    def new_context(**kwargs):
        actions.append(("context", kwargs))
        return context

    @contextmanager
    def sync_playwright():
        actions.append("start")
        try:
            yield SimpleNamespace(chromium=SimpleNamespace(launch=launch, executable_path=str(executable)))
        finally:
            actions.append("stop")

    context = SimpleNamespace(
        new_page=new_page, on=callbacks.__setitem__, request=SimpleNamespace(get=get),
        close=lambda: actions.append("context close"),
    )
    runtime = SimpleNamespace(new_context=new_context, close=lambda: actions.append("browser close"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api",
                        SimpleNamespace(Error=FakePlaywrightError, sync_playwright=sync_playwright))
    monkeypatch.setattr(browser, "monotonic", lambda: tick[0])
    monkeypatch.setattr(codal, "monotonic", lambda: tick[0])
    monkeypatch.setattr(codal, "_rate_limit", None)
    return SimpleNamespace(actions=actions, context=context, callbacks=callbacks,
                           new_page=new_page, executable=executable, report_calls=report_calls)


_REPORT_URL = "https://www.codal.ir/Reports/Decision.aspx?LetterSerial=a"


def test_search_verification_keeps_the_original_page_and_context(chromium, monkeypatch, capsys):
    search_page = chromium.new_page()
    monkeypatch.setattr(chromium.context, "new_page", lambda: search_page)
    search_page.after_wait = lambda: setattr(search_page, "search_outcome", "solved")
    query = {"Symbol": "فولاد", "PageNumber": 2, "Category": 3, "LetterType": 58}

    with browser.open_browser() as session:
        session.verify(codal._SEARCH, search=True, params=query)
        assert session.get(codal._SEARCH, query, False).json() == {"IsAttacker": False}
        assert session.get(_REPORT_URL, None, True).content == Response(_REPORT_URL).body()

    assert chromium.actions == [
        "start", ("launch", {"headless": False, "timeout": browser._NAVIGATION_MS}),
        ("context", {"accept_downloads": False}), "context close", "browser close", "stop",
    ]
    entry_url = urlsplit(search_page.actions[0][1])
    assert entry_url.netloc == "www.codal.ir" and entry_url.path == "/ReportList.aspx"
    expected_query = {key: [str(value)] for key, value in query.items()}
    assert parse_qs(entry_url.query) == {**expected_query, "search": ["true"]}
    assert search_page.actions[1][1] == browser._SEARCH_INPUT
    assert parse_qs(urlsplit(search_page.actions[-1][2]["url"]).query) == expected_query
    assert "کدال" in capsys.readouterr().err
    response, options = chromium.report_calls[0]
    assert response.disposed and response.url == _REPORT_URL
    assert options == {
        "headers": {"Accept": "text/html"}, "max_redirects": 0, "timeout": browser._NAVIGATION_MS,
    }


def test_report_verification_reuses_browser_context_and_response_bytes(chromium, monkeypatch):
    page = chromium.new_page()
    monkeypatch.setattr(chromium.context, "new_page", lambda: page)
    page.status = 403

    def human_finishes():
        page.visible = False

    page.after_wait = human_finishes
    with browser.open_browser() as session:
        session.verify(_REPORT_URL, search=False, params=None)
        result = session.get(_REPORT_URL, None, True)

    assert result.url == _REPORT_URL
    assert result.content == Response(_REPORT_URL).body()
    assert [action[0] for action in page.actions] == ["goto", "locator"]
    assert chromium.report_calls[0][0].disposed


@pytest.mark.parametrize(("outcome", "message"), [
    ("missing", "did not present a usable human verification form"),
    ("timeout", "verification timed out"),
    ("closed", "was closed"),
    ("interrupt", "was cancelled"),
    ("expired", "verification expired"),
    ("rate-limit", "HTTP 429.*Retry-After: 60"),
])
def test_verification_failure_closes_resources(chromium, monkeypatch, outcome, message):
    page = chromium.new_page()
    monkeypatch.setattr(chromium.context, "new_page", lambda: page)
    if outcome == "missing":
        page.visible = False
    elif outcome == "closed":
        page.after_wait = lambda: setattr(page, "closed", True)
    elif outcome == "interrupt":
        def interrupt():
            raise KeyboardInterrupt
        page.after_wait = interrupt
    elif outcome == "expired":
        page.after_wait = lambda: setattr(page, "search_outcome", "expired")
    elif outcome == "rate-limit":
        page.after_wait = lambda: chromium.callbacks["response"](
            Response(codal._SEARCH, 429, {"retry-after": "60"}),
        )

    with pytest.raises(codal.CodalRequestError, match=message):
        with browser.open_browser() as session:
            session.verify(codal._SEARCH, search=True, params={"PageNumber": 1})

    assert chromium.actions[-3:] == ["context close", "browser close", "stop"]
    assert [action[0] for action in page.actions].count("goto") == 1
    if outcome == "rate-limit":
        with pytest.raises(codal.CodalRequestError, match="Retry-After"):
            codal._check_rate_limit()


def test_installed_chrome_is_used_when_bundled_chromium_is_missing(chromium):
    chromium.executable.unlink()
    with browser.open_browser():
        pass
    assert chromium.actions[1] == (
        "launch", {"headless": False, "timeout": browser._NAVIGATION_MS, "channel": "chrome"},
    )


def test_missing_playwright_has_install_instructions(monkeypatch):
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    with pytest.raises(codal.CodalRequestError, match="fima\\[codal-browser\\].*playwright install chromium"):
        with browser.open_browser():
            pytest.fail("Browser unexpectedly opened")


def test_failed_chromium_launch_has_install_instructions(monkeypatch, tmp_path):
    def launch(**kwargs):
        raise FakePlaywrightError("missing executable")

    @contextmanager
    def sync_playwright():
        chromium = SimpleNamespace(launch=launch, executable_path=str(tmp_path / "missing"))
        yield SimpleNamespace(chromium=chromium)

    monkeypatch.setitem(sys.modules, "playwright.sync_api",
                        SimpleNamespace(Error=FakePlaywrightError, sync_playwright=sync_playwright))
    with pytest.raises(codal.CodalRequestError, match="Could not open.*playwright install chromium"):
        with browser.open_browser():
            pytest.fail("Browser unexpectedly opened")


def test_report_redirects_stay_on_codal_hosts(chromium, monkeypatch):
    codal_url = _REPORT_URL.replace("www.codal.ir", "codal.ir")
    blocked_url = "https://example.org/report"
    chain = [
        Response(_REPORT_URL, 302, {"location": codal_url}),
        Response(codal_url, 302, {"location": blocked_url}),
    ]
    responses = iter(chain)
    requested = []

    def get(url, **kwargs):
        requested.append(url)
        return next(responses)

    monkeypatch.setattr(chromium.context.request, "get", get)
    with pytest.raises(codal.CodalRequestError, match="outside the expected HTTPS hosts"):
        with browser.open_browser() as session:
            session.get(_REPORT_URL, None, True)

    assert requested == [_REPORT_URL, codal_url]
    assert all(response.disposed for response in chain)
