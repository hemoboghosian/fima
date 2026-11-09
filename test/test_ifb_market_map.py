"""Small synthetic WebMethod fixtures; financial values never pass through float."""
from copy import deepcopy
from decimal import Decimal
import inspect
import json
import subprocess
import sys

import pandas as pd
import pytest
import requests

import fima
import fima.IFB as ifb
import fima._ifb_market_map as source


PAGE = '''<html><script>url: "/DataReporter/MarketMap.aspx/getData"</script>
<input id="rbtn_1" value="1"><label for="rbtn_1">حجم</label>
<input id="rbtn_2" value="2"><label for="rbtn_2">ارزش</label>
<input id="rbtn_3" value="3"><label for="rbtn_3">تعداد</label>
<input id="rbtn_4" value="4"><label for="rbtn_4">ارزش بازار</label></html>'''
ROW = dict(title="بیمه پاسارگاد", id=18620, value=1421055000000000,
           label="بپاس1", data=-2.5, close=13730, market="بازار دوم", eps=1221,
           ptoe=11.244881244881245)
COLUMNS = ["InstrumentID", "Ticker", "InstrumentName", "Market", "MetricValue",
           "ClosingPrice", "ClosingPercentageChange", "EPS", "PE", "DetailURL"]
METRICS = ["trade_volume", "trade_value", "transaction_count", "market_value"]


class Response:
    def __init__(self, content, kind="application/json; charset=utf-8", error=None):
        self.content = content.encode("utf-8")
        self.headers = {"Content-Type": kind}
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error


class Session:
    def __init__(self, rows=None, payload=None, page=PAGE, error=None, kind=None):
        self.rows = [deepcopy(ROW)] if rows is None else rows
        self.payload, self.page, self.error, self.kind = payload, page, error, kind
        self.calls, self.closed = [], False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return Response(self.page, "text/html; charset=utf-8")

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if isinstance(self.error, requests.Timeout):
            raise self.error
        return Response(self.payload if self.payload is not None else json.dumps({"d": self.rows}),
                        self.kind or "application/json; charset=utf-8", self.error)


@pytest.fixture
def install(monkeypatch):
    def factory(**kwargs):
        session = Session(**kwargs)
        monkeypatch.setattr(source, "_session", lambda: session)
        return session
    return factory


def test_public_contract():
    assert fima.get_ifb_market_map is ifb.get_ifb_market_map
    signature = inspect.signature(ifb.get_ifb_market_map)
    assert str(signature.replace(return_annotation=inspect.Signature.empty)) == \
        "(metric='market_value', ticker=None, market=None)"
    assert signature.return_annotation is pd.DataFrame


@pytest.mark.parametrize("metric,code", list(zip(METRICS, range(1, 5))))
def test_published_request_and_metric_mapping(install, metric, code):
    session = install()
    frame = ifb.get_ifb_market_map(metric)
    assert [c[:2] for c in session.calls] == [
        ("GET", source._URL), ("POST", source._URL + "/getData")]
    assert session.calls[1][2]["data"] == "{type:" + str(code) + "}"
    assert session.calls[1][2]["headers"] == {"Content-Type": "application/json; charset=utf-8"}
    assert all(c[2]["timeout"] == (10, 30) for c in session.calls)
    assert session.closed
    assert list(frame) == COLUMNS
    assert frame.attrs == {
        "SourceURL": source._URL, "EndpointURL": source._URL + "/getData",
        "Snapshot": True, "Metric": metric, "MetricCode": code,
        "MetricUnit": {1: "InstrumentUnits", 2: "IRR", 3: "Transactions", 4: "IRR"}[code],
        "PriceUnit": "IRR", "EPSUnit": "IRRPerInstrumentUnit", "SourceRowCount": 1,
        "Coverage": "SelectedMetricResponse", "MonetaryPrecision": "SerializedJSONNumbers",
    }
    assert frame.InstrumentID.tolist() == ["18620"]
    assert frame.DetailURL[0] == "https://ifb.ir/Instruments.aspx?id=18620"
    assert frame.ClosingPrice[0] == 13730 and frame.EPS[0] == 1221
    assert frame.ClosingPercentageChange[0] == -2.5
    assert frame.PE[0] == pytest.approx(13730 / 1221)
    assert str(frame.ClosingPrice.dtype) == str(frame.EPS.dtype) == "Int64"
    assert str(frame.ClosingPercentageChange.dtype) == str(frame.PE.dtype) == "Float64"
    assert str(frame.InstrumentID.dtype) == "string"
    if code in (2, 4):
        assert isinstance(frame.MetricValue[0], Decimal)
    else:
        assert str(frame.MetricValue.dtype) == "Int64"


@pytest.mark.parametrize("metric", ["trade_value", "market_value"])
def test_monetary_wire_precision_scientific_and_fractional(install, metric):
    payload = json.dumps({"d": [ROW]}).replace(str(ROW["value"]), "9.007199254740993125E+15")
    install(payload=payload)
    frame = ifb.get_ifb_market_map(metric)
    assert frame.MetricValue[0] == Decimal("9007199254740993.125")
    assert frame.MetricValue.dtype == object


def test_all_rows_and_duplicate_tickers_distinct_identities(install):
    install(rows=[{**ROW, "id": i + 1} for i in range(143)])
    frame = ifb.get_ifb_market_map()
    assert len(frame) == frame.attrs["SourceRowCount"] == 143
    assert frame.InstrumentID.is_unique and frame.Ticker.nunique() == 1


@pytest.mark.parametrize("metric", METRICS)
def test_missing_zero_and_negative_eps(install, metric):
    install(rows=[{**ROW, "value": None, "close": None, "eps": None, "data": None, "ptoe": None},
                  {**ROW, "id": 2, "value": 0, "close": 0, "eps": 0, "data": 0, "ptoe": 0},
                  {**ROW, "id": 3, "eps": -805, "ptoe": -3.3490683229813665, "data": -85.01827040194884}])
    frame = ifb.get_ifb_market_map(metric)
    assert frame.loc[0, ["MetricValue", "ClosingPrice", "EPS", "ClosingPercentageChange", "PE"]].isna().all()
    assert frame.loc[1, ["MetricValue", "ClosingPrice", "EPS", "ClosingPercentageChange"]].eq(0).all()
    assert pd.isna(frame.PE[1])
    assert frame.EPS[2] == -805 and frame.PE[2] < 0
    assert frame.ClosingPercentageChange[2] < -85


@pytest.mark.parametrize("metric", METRICS)
def test_valid_empty_source_is_typed(install, metric):
    install(rows=[])
    frame = ifb.get_ifb_market_map(metric)
    assert frame.empty and list(frame) == COLUMNS
    assert frame.attrs["SourceRowCount"] == 0
    assert str(frame.ClosingPrice.dtype) == "Int64"
    assert str(frame.Ticker.dtype) == "string"


def test_exact_filters_and_source_count(install):
    install(rows=[ROW, {**ROW, "id": 2, "market": "ETF"}, {**ROW, "id": 3, "label": "بپاس"}])
    frame = ifb.get_ifb_market_map(ticker="بپاس1", market="بازار دوم")
    assert frame.InstrumentID.tolist() == ["18620"] and frame.attrs["SourceRowCount"] == 3
    assert list(frame.index) == [0]
    assert ifb.get_ifb_market_map(ticker="بپا").empty


def test_filters_cannot_hide_bad_unselected_rows(install):
    install(rows=[ROW, {**ROW, "id": 2, "label": "other", "close": -1}])
    with pytest.raises(ValueError):
        ifb.get_ifb_market_map(ticker=ROW["label"])


@pytest.mark.parametrize("kwargs", [{"metric": x} for x in [None, 1, "volume", "MarketValue", [], True]] +
                         [{"ticker": x} for x in [3, "", "  ", []]] + [{"market": 1}],
                         ids=["metric-null", "metric-code", "metric-alias", "metric-case", "metric-list", "metric-bool",
                              "ticker-int", "ticker-empty", "ticker-blank", "ticker-list", "market-int"])
def test_invalid_arguments_before_http(monkeypatch, kwargs):
    monkeypatch.setattr(source, "_session", lambda: pytest.fail("HTTP must not run"))
    with pytest.raises(ValueError):
        ifb.get_ifb_market_map(**kwargs)


@pytest.mark.parametrize("payload", ['{}', '{"d":null}', '{"d":{}}', '{"d":"[]"}', '[]',
                         '{"d":[],"HasMore":true}', '{"d":[', '{"d":[],"d":[]}'],
                         ids=["missing", "null", "object", "encoded", "list", "partial-envelope", "truncated", "duplicate-key"])
def test_invalid_envelopes(install, payload):
    install(payload=payload)
    with pytest.raises(ValueError):
        ifb.get_ifb_market_map()


@pytest.mark.parametrize("field,value", [("id", None), ("id", True), ("id", 0), ("id", 1.5),
    ("label", ""), ("market", None), ("title", []), ("value", -1), ("value", "12"),
    ("value", True), ("close", -1), ("close", 1.5), ("eps", "--"), ("eps", 2**63),
    ("data", "2%"), ("data", float("nan")), ("ptoe", float("inf"))],
    ids=["missing-id", "bool-id", "zero-id", "fraction-id", "blank-ticker", "missing-market", "bad-title",
         "negative-value", "string-value", "bool-value", "negative-price", "fraction-price", "text-eps",
         "overflow-eps", "text-percent", "nan-percent", "inf-pe"])
def test_malformed_financial_rows(install, field, value):
    install(rows=[{**ROW, field: value}])
    with pytest.raises(ValueError):
        ifb.get_ifb_market_map()


@pytest.mark.parametrize("rows", [[ROW, ROW], [None], [dict(ROW, extra=1)],
                         [{k: v for k, v in ROW.items() if k != "eps"}]],
                         ids=["duplicate-id", "null-row", "extra-column", "missing-column"])
def test_schema_and_identity_failures(install, rows):
    install(rows=rows)
    with pytest.raises(ValueError):
        ifb.get_ifb_market_map()


@pytest.mark.parametrize("metric", ["trade_volume", "transaction_count"])
@pytest.mark.parametrize("value", [1.5, 2**63])
def test_invalid_integer_metric(install, metric, value):
    install(rows=[{**ROW, "value": value}])
    with pytest.raises(ValueError):
        ifb.get_ifb_market_map(metric)


@pytest.mark.parametrize("page", ["<html>Access denied</html>", PAGE.replace('value="2"', 'value="7"'),
                         PAGE.replace("ارزش بازار", "حجم"), PAGE.replace("/getData", "/other")],
                         ids=["denied", "changed-metric-code", "changed-metric-meaning", "changed-endpoint"])
def test_bootstrap_guard(install, page):
    session = install(page=page)
    with pytest.raises(ValueError):
        ifb.get_ifb_market_map()
    assert len(session.calls) == 1 and session.closed


@pytest.mark.parametrize("error", [requests.Timeout("timed out"), requests.HTTPError("403"), requests.HTTPError("500")],
                         ids=["timeout", "forbidden", "server-error"])
def test_http_errors_propagate_and_cleanup(install, error):
    session = install(error=error)
    with pytest.raises(type(error), match=str(error)):
        ifb.get_ifb_market_map()
    assert session.closed


def test_html_in_place_of_json(install):
    install(payload="<html>blocked</html>", kind="text/html")
    with pytest.raises(ValueError):
        ifb.get_ifb_market_map()


def test_transport_limits():
    with source._session() as session:
        retry = session.get_adapter(source._URL).max_retries
        assert retry.total == 1 and retry.read == 0
        assert set(retry.status_forcelist) == {502, 503, 504}
        assert set(retry.allowed_methods) == {"GET", "POST"}
        assert not retry.respect_retry_after_header
        assert session.verify is True and session.max_redirects <= 5


def test_no_import_time_requests():
    subprocess.run([sys.executable, "-c", """
import requests
def forbidden(*args, **kwargs):
    raise AssertionError('import attempted HTTP')
requests.sessions.Session.request = forbidden
import fima
import fima.IFB
assert fima.get_ifb_market_map is fima.IFB.get_ifb_market_map
"""], check=True, timeout=30)


@pytest.mark.parametrize("payload", [
    '{"d":[' + json.dumps(ROW).replace('"eps": 1221', '"eps": 1, "eps": 2') + ']}',
    json.dumps({"d": [ROW]}).replace('"data": -2.5', '"data": 1E+500'),
    json.dumps({"d": [ROW]}).replace('"data": -2.5', '"data": 1E-500'),
], ids=["duplicate-row-key", "ratio-overflow", "ratio-underflow"])
def test_unrepresentable_or_ambiguous_numbers(install, payload):
    install(payload=payload)
    with pytest.raises(ValueError):
        ifb.get_ifb_market_map()


def test_bootstrap_http_failure_closes_session(install, monkeypatch):
    session = install()
    monkeypatch.setattr(session, "get", lambda *args, **kwargs: Response(
        PAGE, error=requests.HTTPError("503")))
    with pytest.raises(requests.HTTPError, match="503"):
        ifb.get_ifb_market_map()
    assert session.closed and not session.calls
