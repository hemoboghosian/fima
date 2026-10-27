"""Options failures must be distinguishable from valid empty provider data."""
from types import SimpleNamespace

import pandas as pd
import pytest
import requests

import fima.Options as options
from test.test_tsetmc_options_contracts import option_record


@pytest.fixture(params=["watch", "chain"])
def download(request):
    if request.param == "watch":
        return options.download_market_watch
    return lambda **kwargs: options.download_chain_contracts("BASE", **kwargs)


@pytest.mark.parametrize("error", [requests.Timeout("provider timed out"),
                                  requests.ConnectionError("provider unavailable")])
def test_network_errors_propagate(monkeypatch, download, error):
    def get(*args, **kwargs):
        assert kwargs["timeout"] == 30
        raise error
    monkeypatch.setattr(options.requests, "get", get)
    with pytest.raises(type(error), match=str(error)):
        download()


def test_http_errors_propagate_before_json(monkeypatch, download):
    def failed_status():
        raise requests.HTTPError("503 Service Unavailable")
    monkeypatch.setattr(options.requests, "get", lambda *a, **k: SimpleNamespace(
        raise_for_status=failed_status))
    with pytest.raises(requests.HTTPError, match="503"):
        download()


def test_invalid_json_propagates(monkeypatch, download):
    def invalid_json():
        raise requests.exceptions.JSONDecodeError("Invalid JSON", "<html>", 0)
    monkeypatch.setattr(options.requests, "get", lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=invalid_json))
    with pytest.raises(requests.exceptions.JSONDecodeError):
        download()


@pytest.mark.parametrize("payload,exception", [({}, KeyError),
                                              ({"instrumentOptMarketWatch": [{"insCode_C": "1"}]}, ValueError)])
def test_malformed_provider_schema_propagates(monkeypatch, download, payload, exception):
    monkeypatch.setattr(options.requests, "get", lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: payload))
    with pytest.raises(exception):
        download()


def test_analytics_failure_is_not_hidden(monkeypatch, download):
    monkeypatch.setattr(options.requests, "get", lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"instrumentOptMarketWatch": [option_record()]}))
    def history(**kwargs):
        raise requests.HTTPError("history unavailable")
    monkeypatch.setattr(options, "get_ticker_historical_data", history)
    with pytest.raises(requests.HTTPError, match="history unavailable"):
        download(bsm=True)


@pytest.mark.parametrize("stack", ["Horizontal", "Vertical"])
@pytest.mark.parametrize("j_date", [True, False])
def test_valid_empty_watch_has_the_same_public_schema(monkeypatch, stack, j_date):
    payload = {"instrumentOptMarketWatch": [option_record()]}
    monkeypatch.setattr(options.requests, "get", lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: payload))
    expected = options.download_market_watch(stack=stack, j_date=j_date)
    payload["instrumentOptMarketWatch"] = []
    result = options.download_market_watch(stack=stack, j_date=j_date)
    assert isinstance(result, pd.DataFrame)
    assert result.empty
    assert list(result) == list(expected)
    code = "CallInstrumentCode" if stack == "Horizontal" else "InstrumentCode"
    assert str(result[code].dtype) == "string"
    if not j_date:
        assert str(result.BeginGregorianDate.dtype) == "datetime64[ns]"


def test_valid_empty_chain_has_the_same_public_schema(monkeypatch):
    payload = {"instrumentOptMarketWatch": [option_record()]}
    monkeypatch.setattr(options.requests, "get", lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: payload))
    expected = options.download_chain_contracts("BASE")
    payload["instrumentOptMarketWatch"] = []
    result = options.download_chain_contracts("BASE")
    assert isinstance(result, pd.DataFrame)
    assert result.empty
    assert list(result) == list(expected)


@pytest.mark.parametrize("layout", ["Horizontal", "Vertical", "chain"])
@pytest.mark.parametrize("flags", [{"bsm": True}, {"greeks": True},
                                   {"implied_volatility": True},
                                   {"bsm": True, "greeks": True, "implied_volatility": True}])
def test_empty_analytics_do_not_fetch_unneeded_inputs(monkeypatch, layout, flags):
    monkeypatch.setattr(options.requests, "get", lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {"instrumentOptMarketWatch": []}))
    def unexpected(*args, **kwargs):
        pytest.fail("Empty option data must not fetch history or rates")
    monkeypatch.setattr(options, "get_ticker_historical_data", unexpected)
    monkeypatch.setattr(options, "get_risk_free_rate", unexpected)
    result = (options.download_chain_contracts("BASE", **flags) if layout == "chain"
              else options.download_market_watch(stack=layout, **flags))
    assert result.empty
    prefix = "" if layout == "Vertical" else "Call"
    if flags.get("bsm"):
        assert prefix + "BSMPrice" in result
        assert prefix + "Volatility" in result
    if flags.get("greeks"):
        assert prefix + "Delta" in result
    if flags.get("implied_volatility"):
        assert prefix + "ImpliedVolatility" in result
    assert "RiskFreeRate" in result
