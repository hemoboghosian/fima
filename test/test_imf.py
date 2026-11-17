"""Synthetic, source-shaped IMF v2 contracts; no live data or network required."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest
import requests

import fima
import fima.IMF as imf


API = {"version": "2", "output-method": "json"}


def metadata(label="Synthetic GDP growth", unit="Annual percent change", **changes):
    result = {"label": label, "description": "Synthetic test definition", "source": "Synthetic WEO edition",
              "unit": unit, "dataset": "WEO", "projection-year": 2026,
              "last-modified": "2026-10-08 14:43:32"}
    result.update(changes)
    return result


def payloads():
    return {
        "indicators": {"api": API, "indicators": {
            "NGDP_RPCH": metadata(),
            "NGDPD": metadata("Nominal GDP", "Billions of U.S. dollars"),
            "PCPIPCH": metadata("Average inflation", "Annual percent change"),
            "GGXWDG_NGDP": metadata("General government gross debt", "Percent of GDP"),
            "other": {"dataset": "FPP", "unit": None},
        }},
        "countries": {"api": API, "countries": {
            "IRN": {"label": "Iran"}, "USA": {"label": "United States"},
            "ABW": {"label": "Aruba"}, "KOS": {"label": "Synthetic source code"}}},
        "regions": {"api": API, "regions": {"APQ": {"label": "Asia and Pacific"}}},
        "groups": {"api": API, "groups": {"WEOWORLD": {"label": "World"}}},
        "NGDP_RPCH": {"api": API, "indicators": {"NGDP_RPCH": metadata()}, "values": {
            "NGDP_RPCH": {"IRN": {"2024": None, "2025": 0, "2026": -1.5, "2027": 2.25},
                          "USA": {"2025": 3.25, "2026": 4.5},
                          "WEOWORLD": {"2025": 1.25}, "APQ": {"2025": 2.5}}, "": None}},
    }


class Response:
    def __init__(self, url, payload=None, status=200, mime="application/json", raw=None, headers=None):
        self.url, self.status_code = url, status
        self.content = json.dumps(payload).encode() if raw is None else raw
        self.headers = {"Content-Type": mime, **(headers or {})}
        self.closed = False

    def iter_content(self, chunk_size):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i:i+chunk_size]

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def close(self):
        self.closed = True


@pytest.fixture
def source(monkeypatch):
    data, calls, responses, sleeps = payloads(), [], [], []
    options = {}

    def get(url, **kwargs):
        calls.append((url, kwargs))
        path = url.removeprefix(imf._BASE).split("/")[0]
        option = options.get(path, {})
        if isinstance(option, list):
            option = option.pop(0)
        if isinstance(option, Exception):
            raise option
        response = Response(url, data.get(path), **option)
        responses.append(response)
        return response

    monkeypatch.setattr(imf._requests, "get", get)
    monkeypatch.setattr(imf._time, "sleep", sleeps.append)
    return data, calls, options, responses, sleeps


def series():
    return imf.get_imf_series("NGDP_RPCH", ["IRN", "USA"], 2024, 2026)


def test_public_signatures_and_exports():
    expected = {
        "get_imf_datasets": "()",
        "get_imf_indicators": "(dataset=None, search=None)",
        "get_imf_countries": "(include_aggregates=False)",
        "get_imf_series": "(indicator, countries, start_year, end_year)",
    }
    assert set(imf.__all__) == set(expected)
    for name, signature in expected.items():
        fn = getattr(imf, name)
        assert getattr(fima, name) is fn
        sig = inspect.signature(fn)
        structural = sig.replace(parameters=[p.replace(annotation=inspect.Parameter.empty)
                                            for p in sig.parameters.values()],
                                 return_annotation=inspect.Signature.empty)
        assert str(structural) == signature
        assert sig.return_annotation is pd.DataFrame


def test_catalog_discovery_and_literal_search(source):
    data, calls, *_ = source
    frame = imf.get_imf_indicators(search="debt")
    assert frame.Indicator.tolist() == ["GGXWDG_NGDP"]
    assert frame.Unit.tolist() == ["Percent of GDP"]
    assert str(frame.SourceProjectionYear.dtype) == "Int64"
    assert len(calls) == 1
    assert imf.get_imf_indicators(search="[invalid regex").empty
    assert len(imf.get_imf_indicators(dataset="WEO")) == 4
    datasets = imf.get_imf_datasets()
    assert datasets.iloc[0].Dataset == "WEO" and datasets.iloc[0].IndicatorCount == 4
    data["indicators"]["indicators"]["NEW"] = metadata("New source indicator")
    assert "NEW" in imf.get_imf_indicators().Indicator.tolist()


def test_geographies_preserve_source_ids_and_distinguish_aggregates(source):
    countries = imf.get_imf_countries()
    assert set(countries.GeographyType) == {"Country"}
    assert "KOS" in set(countries.Country)  # No assumption that every ID is ISO3.
    frame = imf.get_imf_countries(True).set_index("Country")
    assert frame.loc["APQ", "GeographyType"] == "Region"
    assert frame.loc["WEOWORLD", "GeographyType"] == "Group"


def test_multicountry_native_values_missing_zero_filtering_and_coverage(source):
    _, calls, _, responses, _ = source
    frame = series()
    assert list(frame.columns) == imf._SERIES
    assert frame.Country.tolist() == ["IRN"] * 3 + ["USA"] * 2
    assert frame.Period.tolist() == ["2024", "2025", "2026", "2025", "2026"]
    assert pd.isna(frame.Value.iloc[0]) and frame.Value.iloc[1] == 0
    assert frame.Value.iloc[2:].tolist() == [-1.5, 3.25, 4.5]
    assert str(frame.Value.dtype) == "float64"
    assert set(frame.Unit) == {"Annual percent change"}
    assert frame.attrs["Filtering"] == "ClientSide"
    assert frame.attrs["ObservationStatus"] == "Unknown"
    assert frame.attrs["IndicatorMetadata"]["SourceProjectionYear"] == 2026
    assert frame.attrs["Coverage"][1]["MissingPeriods"] == ["2024"]
    assert calls[-1][1]["params"] == {"periods": "2024,2025,2026"}
    assert all(r.closed for r in responses)
    assert all(c[1]["timeout"] == (10, 30) and "verify" not in c[1] for c in calls)


@pytest.mark.parametrize("code,unit", [("NGDPD", "Billions of U.S. dollars"),
                                      ("PCPIPCH", "Annual percent change"),
                                      ("GGXWDG_NGDP", "Percent of GDP")])
def test_economic_units_are_never_rescaled(source, code, unit):
    data = source[0]
    data[code] = {"api": API, "indicators": {code: deepcopy(data["indicators"]["indicators"][code])},
                  "values": {code: {"IRN": {"2025": 123.45}}}}
    frame = imf.get_imf_series(code, "IRN", 2025, 2025)
    assert frame.Value.tolist() == [123.45] and frame.Unit.tolist() == [unit]


@pytest.mark.parametrize("code,kind", [("WEOWORLD", "Group"), ("APQ", "Region")])
def test_aggregate_series(source, code, kind):
    frame = imf.get_imf_series("NGDP_RPCH", code, 2025, 2025)
    assert frame.GeographyType.tolist() == [kind] and frame.Country.tolist() == [code]


def test_empty_interval_and_absent_geography_are_explicit(source):
    empty = imf.get_imf_series("NGDP_RPCH", "IRN", 1900, 1901)
    assert empty.empty and list(empty.columns) == imf._SERIES
    assert str(empty.Value.dtype) == "float64"
    assert empty.attrs["Coverage"][0]["SourceSeriesPresent"] is True
    with pytest.warns(RuntimeWarning, match="no series for ABW"):
        mixed = imf.get_imf_series("NGDP_RPCH", ["IRN", "ABW"], 2025, 2025)
    assert mixed.Country.tolist() == ["IRN"]
    assert mixed.attrs["Coverage"][1] == {"Country": "ABW", "SourceSeriesPresent": False,
                                            "ReturnedPeriods": [], "MissingPeriods": ["2025"]}


@pytest.mark.parametrize("kwargs", [{"dataset": "FM"}, {"dataset": []}, {"search": ""}, {"search": 3}])
def test_invalid_discovery_inputs_do_not_request(source, kwargs):
    with pytest.raises(ValueError):
        imf.get_imf_indicators(**kwargs)
    assert not source[1]


@pytest.mark.parametrize("value", [None, 1, "yes", []])
def test_invalid_aggregate_flag(source, value):
    with pytest.raises(ValueError):
        imf.get_imf_countries(value)
    assert not source[1]


@pytest.mark.parametrize("args", [
    ("../x", "IRN", 2025, 2025), ("x?y", "IRN", 2025, 2025),
    ("NGDP_RPCH", [], 2025, 2025), ("NGDP_RPCH", ["IRN", "IRN"], 2025, 2025),
    ("NGDP_RPCH", ["USA"] * 21, 2025, 2025), ("NGDP_RPCH", "IRN/USA", 2025, 2025),
    ("NGDP_RPCH", {"IRN"}, 2025, 2025), ("NGDP_RPCH", "IRN", True, 2025),
    ("NGDP_RPCH", "IRN", 2025.0, 2025), ("NGDP_RPCH", "IRN", "2025", 2025),
    ("NGDP_RPCH", "IRN", 999, 2025), ("NGDP_RPCH", "IRN", 2026, 2025),
    ("NGDP_RPCH", "IRN", 1800, 2000),
])
def test_invalid_series_inputs_do_not_request(source, args):
    with pytest.raises(ValueError):
        imf.get_imf_series(*args)
    assert not source[1]


@pytest.mark.parametrize("indicator,country", [("UNKNOWN", "IRN"), ("NGDP_RPCH", "UNKNOWN")])
def test_unknown_id_is_not_sent_to_series_endpoint(source, indicator, country):
    with pytest.raises(ValueError):
        imf.get_imf_series(indicator, country, 2025, 2025)
    assert all("periods" not in (kwargs.get("params") or {}) for _, kwargs in source[1])


@pytest.mark.parametrize("change", [
    lambda p: p.pop("values"),
    lambda p: p.update(values={"WRONG": {}}),
    lambda p: p["values"].update(extra={}),
    lambda p: p["values"].update({"": {}}),
    lambda p: p["values"]["NGDP_RPCH"].update(IRN=None),
    lambda p: p["indicators"].update(WRONG=metadata()),
    lambda p: p.update(indicators={}),
    lambda p: p.update(errors=["incomplete source"]),
    lambda p: p.update(api={"version": "1", "output-method": "json"}),
])
def test_invalid_response_contract(source, change):
    change(source[0]["NGDP_RPCH"])
    with pytest.raises(RuntimeError, match="IMF"):
        series()


@pytest.mark.parametrize("period", ["2025-Q1", "2025-01", "25", "2025.0", "0200"])
def test_nonannual_periods_rejected_even_outside_filter(source, period):
    source[0]["NGDP_RPCH"]["values"]["NGDP_RPCH"]["IRN"][period] = 1
    with pytest.raises(RuntimeError, match="annual"):
        series()


@pytest.mark.parametrize("value", [True, "2.5", "", "..", "NaN", [], {}, float("inf"), float("nan")])
def test_malformed_observation_is_not_missing_or_zero(source, value):
    source[0]["NGDP_RPCH"]["values"]["NGDP_RPCH"]["IRN"]["1900"] = value
    with pytest.raises(RuntimeError, match="IMF"):
        series()


@pytest.mark.parametrize("key,value", [("unit", "Percent of GDP"), ("source", "Revised edition"),
                                      ("last-modified", "changed"), ("projection-year", 2027),
                                      ("description", "redefined"), ("label", "redefined")])
def test_metadata_revision_midcall_fails(source, key, value):
    source[0]["NGDP_RPCH"]["indicators"]["NGDP_RPCH"][key] = value
    with pytest.raises(RuntimeError, match="metadata changed"):
        series()


@pytest.mark.parametrize("changes", [{"unit": None}, {"source": ""}, {"frequency": "M"},
                                    {"scale": 9}, {"UNIT_MULT": 6}, {"projection-year": True},
                                    {"projection-year": "2026"}])
def test_invalid_metadata_frequency_and_scale(source, changes):
    source[0]["indicators"]["indicators"]["NGDP_RPCH"].update(changes)
    with pytest.raises(RuntimeError, match="IMF"):
        imf.get_imf_indicators()


def test_absent_projection_metadata_remains_nullable_unknown(source):
    source[0]["indicators"]["indicators"]["NGDP_RPCH"].pop("projection-year")
    source[0]["NGDP_RPCH"]["indicators"]["NGDP_RPCH"].pop("projection-year")
    assert pd.isna(imf.get_imf_indicators().set_index("Indicator").loc["NGDP_RPCH", "SourceProjectionYear"])
    frame = series()
    assert frame.attrs["IndicatorMetadata"]["SourceProjectionYear"] is None
    assert frame.attrs["ObservationStatus"] == "Unknown"


def test_projection_metadata_appearing_midcall_is_a_revision(source):
    source[0]["indicators"]["indicators"]["NGDP_RPCH"].pop("projection-year")
    with pytest.raises(RuntimeError, match="metadata changed"):
        series()


def test_unrepresentable_json_integer_is_rejected(source):
    source[0]["NGDP_RPCH"]["values"]["NGDP_RPCH"]["IRN"]["2025"] = 10 ** 500
    with pytest.raises(RuntimeError, match="nonfinite"):
        series()


@pytest.mark.parametrize("path,key,bad", [("indicators", "indicators", []),
                                        ("countries", "countries", {}),
                                        ("countries", "countries", {"IRN": {}})])
def test_malformed_catalogs(source, path, key, bad):
    source[0][path][key] = bad
    with pytest.raises(RuntimeError, match="IMF"):
        imf.get_imf_indicators() if path == "indicators" else imf.get_imf_countries()


def test_duplicate_geographic_identity(source):
    source[0]["groups"]["groups"]["IRN"] = {"label": "Wrong group"}
    with pytest.raises(RuntimeError, match="duplicate"):
        imf.get_imf_countries(True)


def test_source_null_geographic_names_are_preserved(source):
    # Live catalog contains null labels for ATI and ATL; source IDs remain valid.
    source[0]["countries"]["countries"]["ATI"] = {"label": None}
    frame = imf.get_imf_countries().set_index("Country")
    assert pd.isna(frame.loc["ATI", "CountryName"])


@pytest.mark.parametrize("raw", [b'{"api":', b'<html>denied</html>',
                                 b'{"api":{},"values":{"IRN":{"2025":1,"2025":2}}}', b'[]'])
def test_malformed_truncated_or_duplicate_json(source, raw):
    source[2]["NGDP_RPCH"] = {"raw": raw}
    with pytest.raises(RuntimeError, match="IMF"):
        series()
    assert all(r.closed for r in source[3])


@pytest.mark.parametrize("mime", ["text/html", "text/plain", "application/xml", ""])
def test_wrong_mime(source, mime):
    source[2]["NGDP_RPCH"] = {"mime": mime}
    with pytest.raises(RuntimeError, match="MIME"):
        series()


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 502, 503, 504])
def test_http_failures_and_bounded_retries(source, status):
    source[2]["NGDP_RPCH"] = {"status": status}
    with pytest.raises(RuntimeError, match=f"HTTP {status}"):
        series()
    count = sum("NGDP_RPCH/" in url for url, _ in source[1])
    assert count == (3 if status in (429, 500, 502, 503, 504) else 1)
    assert all(r.closed for r in source[3])


def test_retry_after_success_and_long_delay_failure(source):
    source[2]["NGDP_RPCH"] = [{"status": 429, "headers": {"Retry-After": "7"}}, {}]
    assert not series().empty
    assert source[4] == [7]
    source[2]["NGDP_RPCH"] = {"status": 429, "headers": {"Retry-After": "120"}}
    with pytest.raises(RuntimeError, match="retry.*later"):
        series()
    assert source[4] == [7]


def test_retry_after_http_date_and_invalid_header(source):
    date = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=10), usegmt=True)
    source[2]["NGDP_RPCH"] = [{"status": 503, "headers": {"Retry-After": date}}, {}]
    series()
    assert 0 < source[4][0] <= 10
    source[2]["NGDP_RPCH"] = {"status": 503, "headers": {"Retry-After": "nonsense"}}
    with pytest.raises(RuntimeError, match="Retry-After"):
        series()


@pytest.mark.parametrize("error", [requests.Timeout("timed out"), requests.exceptions.SSLError("TLS"),
                                   requests.ConnectionError("network"), requests.exceptions.ChunkedEncodingError("truncated")])
def test_network_failure_keeps_cause(source, error):
    source[2]["NGDP_RPCH"] = error
    with pytest.raises(RuntimeError) as caught:
        series()
    assert caught.value.__cause__ is error


def test_body_limit_prevents_partial_success(source, monkeypatch):
    monkeypatch.setattr(imf, "_MAX_BYTES", 100)
    with pytest.raises(RuntimeError, match="limit"):
        imf.get_imf_indicators()
    assert all(r.closed for r in source[3])


def test_imports_do_not_make_http():
    code = """
import requests
def forbidden(*args, **kwargs):
    raise AssertionError('import-time HTTP')
requests.sessions.Session.request = forbidden
import fima
from fima import get_imf_series, get_cbi_policy_rates, get_kilid_areas, get_tickers
from fima.IMF import get_imf_series as direct
assert get_imf_series is direct
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
