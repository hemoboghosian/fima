"""Run a supported CODAL challenge and continue in its Chromium session."""

from contextlib import ExitStack, contextmanager, suppress
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from time import monotonic
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

from .codal import (
    CodalRequestError,
    _CAPTCHA_CONTROLS,
    _REPORT_HOSTS,
    _REPORT_ROOT,
    _SEARCH_HOST,
    _check_rate_limit,
    _check_status,
    _codal_host,
    _rate_limit_error,
    _remember_rate_limit,
)

_SEARCH_PAGE = "/ReportList.aspx"
_SEARCH_INPUT = '.modal[ng-show="showCaptchaModal"] input[ng-model="captchaInput"]'
_NAVIGATION_MS = 25_000
_CHALLENGE_SECONDS = 12
_VERIFICATION_SECONDS = 240
_INSTALL = "Install Google Chrome or run python -m playwright install chromium."
_PROMPT = (
    "کد امنیتی را در صفحهٔ کدال وارد و تأیید کنید. "
    "پس از تأیید کدال، دریافت گزارش ادامه می‌یابد. برای لغو، پنجرهٔ مرورگر را ببندید."
)

# Observe only the provider's outcome events. The provider's application owns
# the verification UI, its submission, and the browser session state.
_WATCH_SEARCH = """
() => {
    const app = document.querySelector("[ng-app], [data-ng-app]");
    const injector = app && window.angular?.element(app).injector();
    if (!injector) return false;
    const scope = injector.get("$rootScope");
    window.fimaCodalVerification = null;
    scope.$on("captcha:solved", () => { window.fimaCodalVerification = "solved"; });
    scope.$on("captcha:expired", () => { window.fimaCodalVerification = "expired"; });
    return true;
}
"""

# Keep search requests in the official page's HTTP service so any state
# maintained by that application stays in the page.
_SEARCH_REQUEST = """
async ({url, timeout}) => {
    const app = document.querySelector("[ng-app], [data-ng-app]");
    const injector = app && window.angular?.element(app).injector();
    if (!injector) return null;
    const http = injector.get("$http");
    let response;
    try {
        response = await http.get(url, {
            timeout, transformResponse: [], headers: {Accept: "application/json"}
        });
    } catch (error) {
        response = error;
    }
    if (typeof response?.status !== "number") return null;
    return {
        status: response.status,
        type: response.headers?.("Content-Type"),
        retryAfter: response.headers?.("Retry-After"),
        text: typeof response.data === "string" ? response.data : ""
    };
}
"""


@dataclass
class _Response:
    url: str
    status_code: int
    headers: dict
    content: bytes

    def json(self):
        return json.loads(self.content)


def _close(close, error):
    with suppress(error):
        close()


@contextmanager
def open_browser():
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError as exc:
        raise CodalRequestError(
            "CODAL browser support is unavailable. Run python -m pip install --upgrade fima "
            "in the Python environment you are using."
        ) from exc

    with ExitStack() as resources:
        try:
            playwright = resources.enter_context(sync_playwright())
            chromium = playwright.chromium
            try:
                browser = chromium.launch(channel="chrome", headless=False, timeout=_NAVIGATION_MS)
            except Error:
                if not Path(chromium.executable_path).is_file():
                    raise
                browser = chromium.launch(headless=False, timeout=_NAVIGATION_MS)
            resources.callback(_close, browser.close, Error)
            context = browser.new_context(accept_downloads=False)
            resources.callback(_close, context.close, Error)
        except Error as exc:
            raise CodalRequestError(f"Could not open the CODAL browser. {_INSTALL}") from exc
        session = _CodalBrowser(context)
        try:
            yield session
        except KeyboardInterrupt as exc:
            raise CodalRequestError("CODAL browser verification was cancelled") from exc
        except Error as exc:
            session.check_access()
            if session.page_closed():
                raise CodalRequestError("CODAL browser was closed. Retrieval cancelled.") from exc
            raise CodalRequestError(f"CODAL browser request failed: {exc}") from exc


class _CodalBrowser:
    def __init__(self, context):
        self.context = context
        self.search_page = None
        self.report_page = None
        self.rate_limited = None
        context.on("response", self._observe_response)

    def _observe_response(self, response):
        parts = urlsplit(response.url)
        if (response.status == 429 and parts.scheme == "https"
                and parts.netloc.lower() in _REPORT_HOSTS | {_SEARCH_HOST}):
            retry_after = response.headers.get("retry-after")
            _remember_rate_limit(retry_after)
            self.rate_limited = _rate_limit_error(retry_after)

    def page_closed(self):
        return any(page is not None and page.is_closed() for page in (self.search_page, self.report_page))

    def check_access(self):
        if self.rate_limited is not None:
            raise self.rate_limited
        _check_rate_limit()

    def _navigate(self, page, url, hosts):
        self.check_access()
        _codal_host(url, hosts)
        response = page.goto(url, wait_until="domcontentloaded", timeout=_NAVIGATION_MS)
        self.check_access()
        if response is None:
            raise CodalRequestError("CODAL browser returned no document response")
        request = response.request
        for _ in range(5):
            _codal_host(request.url, hosts)
            request = request.redirected_from
            if request is None:
                return response
        raise CodalRequestError("CODAL exceeded the redirect limit")

    def _wait(self, page, condition, seconds, message):
        deadline = monotonic() + seconds
        while True:
            self.check_access()
            if page.is_closed():
                raise CodalRequestError("CODAL browser was closed. Retrieval cancelled.")
            outcome = condition()
            if outcome:
                return outcome
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise CodalRequestError(message)
            page.wait_for_timeout(min(200, remaining * 1000))

    def verify(self, url, *, search, params):
        absent = "CODAL did not present a usable human verification form in the browser"
        timeout = "CODAL human verification timed out"
        if search:
            self.search_page = page = self.context.new_page()
            _codal_host(url, {_SEARCH_HOST})
            query = {**dict(parse_qsl(urlsplit(url).query)), **(params or {})}
            entry = f"{_REPORT_ROOT}{_SEARCH_PAGE}?{urlencode({**query, 'search': 'true'})}"
            response = self._navigate(page, entry, _REPORT_HOSTS)
            _check_status(response.status, response.headers.get("retry-after"), urlsplit(response.url).netloc)
            self._check_search_page()
            controls = page.locator(_SEARCH_INPUT).first
        else:
            self.report_page = page = self.context.new_page()
            response = self._navigate(page, url, _REPORT_HOSTS)
            if response.status != 403:
                _check_status(response.status, response.headers.get("retry-after"), urlsplit(response.url).netloc)
            controls = page.locator(f":is({_CAPTCHA_CONTROLS}):visible").first

        self._wait(page, controls.is_visible, _CHALLENGE_SECONDS, absent)
        if search and not page.evaluate(_WATCH_SEARCH):
            raise CodalRequestError(absent)
        print(_PROMPT, file=sys.stderr, flush=True)
        if search:
            def search_outcome():
                self._check_search_page()
                return page.evaluate("() => window.fimaCodalVerification")

            result = self._wait(page, search_outcome, _VERIFICATION_SECONDS, timeout)
            if result != "solved":
                raise CodalRequestError("CODAL human verification expired")
        else:
            self._wait(page, lambda: not controls.is_visible(), _VERIFICATION_SECONDS, timeout)
            _codal_host(page.url, _REPORT_HOSTS)

    def _check_search_page(self):
        _codal_host(self.search_page.url, _REPORT_HOSTS)
        if urlsplit(self.search_page.url).path.lower() != _SEARCH_PAGE.lower():
            raise CodalRequestError("CODAL's verified search page is unavailable")

    def _get_report(self, url):
        # The context owns the request and browser session. Its binary body
        # API preserves bytes that Chromium can normalize on page navigation.
        for _ in range(5):
            self.check_access()
            _codal_host(url, _REPORT_HOSTS)
            response = self.context.request.get(
                url, headers={"Accept": "text/html"}, timeout=_NAVIGATION_MS, max_redirects=0,
            )
            try:
                headers = response.headers
                location = headers.get("location")
                if location and response.status in (301, 302, 303, 307, 308):
                    url = urljoin(response.url, location)
                    continue
                content = response.body() if response.status in (200, 403) else b""
                return _Response(response.url, response.status, {
                    "Content-Type": headers.get("content-type", ""),
                    "Retry-After": headers.get("retry-after"),
                }, content)
            finally:
                response.dispose()
        raise CodalRequestError("CODAL exceeded the redirect limit")

    def get(self, url, params, report):
        if report:
            return self._get_report(url)

        self.check_access()
        _codal_host(url, {_SEARCH_HOST})
        self._check_search_page()
        if params:
            url += ("&" if urlsplit(url).query else "?") + urlencode(params)
        result = self.search_page.evaluate(_SEARCH_REQUEST, {"url": url, "timeout": _NAVIGATION_MS})
        self.check_access()
        if result is None or not isinstance(result["status"], int) or result["status"] <= 0:
            raise CodalRequestError("CODAL search in the verified browser session failed")
        return _Response(
            url, result["status"],
            {"Content-Type": result["type"] or "", "Retry-After": result["retryAfter"]},
            result["text"].encode("utf-8"),
        )
