"""The full collection behind IFB's metric-selected market-map table."""
from decimal import Decimal
import json
import math

from bs4 import BeautifulSoup
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


_URL = "https://ifb.ir/DataReporter/MarketMap.aspx"
_TIMEOUT = (10, 30)
_METRICS = {"trade_volume": (1, "InstrumentUnits"), "trade_value": (2, "IRR"),
            "transaction_count": (3, "Transactions"), "market_value": (4, "IRR")}
_FIELDS = {"title", "id", "value", "label", "data", "close", "market", "eps", "ptoe"}
_COLUMNS = ["InstrumentID", "Ticker", "InstrumentName", "Market", "MetricValue",
            "ClosingPrice", "ClosingPercentageChange", "EPS", "PE", "DetailURL"]


def _session():
    session = requests.Session()
    retry = Retry(total=1, connect=1, read=0, status=1, backoff_factor=.25,
                  status_forcelist=(502, 503, 504), allowed_methods=("GET", "POST"),
                  respect_retry_after_header=False, raise_on_status=False)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.max_redirects = 5
    return session


def _bootstrap(response):
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    for code, label in enumerate(("حجم", "ارزش", "تعداد", "ارزش بازار"), 1):
        control = soup.find("input", id=f"rbtn_{code}")
        caption = soup.find("label", attrs={"for": f"rbtn_{code}"})
        if (control is None or control.get("value") != str(code) or caption is None
                or " ".join(caption.get_text().split()) != label):
            raise ValueError("IFB market-map page or metric definitions missing/changed.")
    if not any("/DataReporter/MarketMap.aspx/getData" in s.get_text() for s in soup.find_all("script")):
        raise ValueError("IFB market-map AJAX endpoint missing/changed.")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("IFB market-map JSON contains duplicate keys.")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"IFB market-map nonfinite JSON number: {value}")


def _number(value, *, integer=False, signed=False):
    if value is None:
        return pd.NA
    if type(value) not in (int, Decimal) or (isinstance(value, Decimal) and not value.is_finite()):
        raise ValueError("IFB market-map invalid numeric value.")
    if not signed and value < 0:
        raise ValueError("IFB market-map negative price, volume, count or value.")
    if integer:
        if not -(2**63) <= value <= 2**63 - 1 or value != int(value):
            raise ValueError("IFB market-map nonintegral/overflow integer value.")
        return int(value)
    return Decimal(value)


def _ratio(value):
    value = _number(value, signed=True)
    if value is pd.NA:
        return value
    number = float(value)
    if not math.isfinite(number) or (number == 0 and value != 0):
        raise ValueError("IFB market-map ratio outside finite float range.")
    return number


def _frame(response, metric):
    response.raise_for_status()
    if response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise ValueError("IFB market-map expected a JSON WebMethod response.")
    payload = json.loads(response.content, parse_float=Decimal,
                         parse_constant=_invalid_constant, object_pairs_hook=_unique_object)
    if not isinstance(payload, dict) or set(payload) != {"d"} or not isinstance(payload["d"], list):
        raise ValueError("IFB market-map response envelope missing/changed/incomplete.")
    code, unit = _METRICS[metric]
    records, ids = [], set()
    for row in payload["d"]:
        if not isinstance(row, dict) or set(row) != _FIELDS:
            raise ValueError("IFB market-map record fields missing/changed.")
        iid = row["id"]
        if type(iid) is not int or iid <= 0 or iid in ids:
            raise ValueError("IFB market-map instrument identity missing/invalid/duplicated.")
        ids.add(iid)
        names = []
        for key in ("label", "title", "market"):
            value = row[key]
            if not isinstance(value, str) or not value.strip():
                raise ValueError("IFB market-map identity/classification text missing/invalid.")
            names.append(value.strip())
        pe = _ratio(row["ptoe"])
        records.append([str(iid), *names, _number(row["value"], integer=code in (1, 3)),
                        _number(row["close"], integer=True), _ratio(row["data"]),
                        _number(row["eps"], integer=True, signed=True),
                        pd.NA if pe is not pd.NA and pe == 0 else pe,
                        f"https://ifb.ir/Instruments.aspx?id={iid}"])
    # Build each column directly, before pandas can turn large/missing integers
    # into binary floats. Monetary decimals retain only the serialized precision.
    frame = pd.DataFrame({column: pd.Series([r[i] for r in records], dtype=(
        ("Int64" if code in (1, 3) else "object") if column == "MetricValue" else
        "Int64" if column in ("ClosingPrice", "EPS") else
        "Float64" if column in ("ClosingPercentageChange", "PE") else "string"))
        for i, column in enumerate(_COLUMNS)})
    frame.attrs = {"SourceURL": _URL, "EndpointURL": _URL + "/getData", "Snapshot": True,
                   "Metric": metric, "MetricCode": code, "MetricUnit": unit,
                   "PriceUnit": "IRR", "EPSUnit": "IRRPerInstrumentUnit",
                   "SourceRowCount": len(records), "Coverage": "SelectedMetricResponse",
                   "MonetaryPrecision": "SerializedJSONNumbers"}
    return frame


def get_ifb_market_map(metric="market_value", ticker=None, market=None) -> pd.DataFrame:
    """Return all records from IFB's selected market-map snapshot response.

    metric: trade_volume (native instrument units), trade_value (rials),
    transaction_count, or market_value (rials; includes debt and funds).
    ticker/market: optional nonempty exact source strings, combined with AND;
    filters run locally after validating the complete selected collection.

    Columns: InstrumentID (IFB string ID, not TSETMC insCode), Ticker,
    InstrumentName, Market, MetricValue, ClosingPrice (rials),
    ClosingPercentageChange (percentage points), EPS (provider rials per unit),
    PE (ratio; source zero displayed as unavailable), DetailURL. Monetary
    MetricValue uses Decimal preserving JSON-token precision, not a guarantee
    of exact underlying rials. Counts, volume, closing price and EPS are nullable
    Int64; change/PE nullable Float64. Missing source numbers remain missing.

    Coverage is the full selected response, without the chart's 100-row limit;
    IFB supplies no independent total count, all-IFB coverage guarantee or
    observation timestamp. Metric selection can change identities and tickers.
    This is not history or an atomic multi-metric quote. EPS earnings basis is
    unverified. See docs/ifb.md for complete provenance and financial caveats.

    Invalid arguments, changed/incomplete schemas and malformed financial data
    raise ValueError. Request/HTTP errors propagate. A valid d=[] or unmatched
    filter returns a typed empty table. No network requests occur at import.
    """
    if not isinstance(metric, str) or metric not in _METRICS:
        raise ValueError("metric must be trade_volume, trade_value, transaction_count or market_value.")
    for value in (ticker, market):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError("ticker and market must be nonempty exact strings or None.")
    with _session() as session:
        _bootstrap(session.get(_URL, timeout=_TIMEOUT))
        response = session.post(_URL + "/getData", data="{type:" + str(_METRICS[metric][0]) + "}",
                                headers={"Content-Type": "application/json; charset=utf-8"}, timeout=_TIMEOUT)
        frame = _frame(response, metric)
    if ticker is not None:
        frame = frame.loc[frame.Ticker.eq(ticker)]
    if market is not None:
        frame = frame.loc[frame.Market.eq(market)]
    return frame.reset_index(drop=True)
