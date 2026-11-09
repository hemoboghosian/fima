"""Deterministic regressions for complete official IME option histories."""
from types import SimpleNamespace

import pandas as pd
import pytest
import requests

import fima
import fima.IME as ime


def option_row(identifier=188033, code="NQOR06P3000", date="1405/08/17"):
    # Source-shaped fields captured from the official historical consumer.
    return dict(id=identifier, ContractID=1002531 + identifier - 188033,
                ContractCode=code, ContractDescription="Option contract", IsActive=True,
                TradesVolume=333, TradesValue=4930980064.0, MaxPrice=16099999.0,
                MinPrice=14500000.0, LastPrice=15999999.0, FirstPrice=15100001.0,
                OpenInterest=416507, ChangeOpenInterest=-106, ActiveCustomers=93,
                ActiveBrokers=28, C_Buy=7, C_Sell=5, Vol_Hoghooghi_Buy=22,
                Val_Hoghooghi_Buy=338749968.0, Vol_Hoghooghi_Sell=0,
                Val_Hoghooghi_Sell=0.0, Vol_Haghighi_Buy=311,
                Val_Haghighi_Buy=4592230096.0, Vol_Haghighi_Sell=333,
                Val_Haghighi_Sell=4930980064.0, LastSettlementPrice=15839899.0,
                TodaySettlementPrice=14807748.0, SettlementPricePercent=-6.52,
                DT=date, DT_en="2026-11-08T00:00:00", DeliveryDate="1406/02/20",
                CreateDateTime="2026-11-09T06:03:43.533")


def serve(monkeypatch, responses):
    calls = []
    iterator = iter(responses)

    def get(url, **kwargs):
        calls.append((url, kwargs))
        item = next(iterator)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(json=lambda: item, raise_for_status=lambda: None)

    monkeypatch.setattr(ime.requests, "get", get)
    return calls


def history(**kwargs):
    return ime.get_all_ime_option_trades(start_date="1405-08-17", end_date="1405-08-17", **kwargs)


def test_follows_reported_total_even_when_server_caps_pages(monkeypatch):
    calls = serve(monkeypatch, [dict(total=2, rows=[option_row()]),
                               dict(total=2, rows=[option_row(188032, "GBAB05C1800")])])
    result = history(contract_code="GBAB05C1800")
    assert result.ContractCode.tolist() == ["GBAB05C1800"]
    assert [c[1]["params"]["offset"] for c in calls] == [0, 1]
    assert all(c[1]["params"]["limit"] == 1000 for c in calls)
    assert all(c[1]["timeout"] == (10, 45) for c in calls)
    assert all("verify" not in c[1] for c in calls)
    assert result.iloc[0].TradeVolume == 333
    assert result.iloc[0].TradeValue == 4930980064
    assert result.iloc[0].OpenInterestChange == -106
    assert result.iloc[0].SettlementPricePercent == -6.52
    assert result.iloc[0].ID == "188032"
    assert result.iloc[0].ContractID == "1002530"
    assert result.iloc[0].JalaliDate == "1405-08-17"
    assert result.iloc[0].GregorianDate == pd.Timestamp("2026-11-08")
    assert result.iloc[0].CreateDateTime == pd.Timestamp("2026-11-09T06:03:43.533")
    assert fima.get_all_ime_option_trades is ime.get_all_ime_option_trades


@pytest.mark.parametrize("error", [requests.Timeout("read timeout"), requests.exceptions.SSLError("TLS"),
                                  requests.HTTPError("503"), ValueError("not JSON")])
def test_failed_window_is_never_returned_as_empty_or_partial(monkeypatch, error):
    serve(monkeypatch, [dict(total=0, rows=[]), error])
    with pytest.raises(RuntimeError, match="1405/08/17"):
        ime.get_all_ime_option_trades(start_date="1405-08-16", end_date="1405-08-17", _chunk_size=0)


@pytest.mark.parametrize("bad", [{}, {"total": 0}, {"total": True, "rows": []},
    {"total": -1, "rows": []}, {"total": 1, "rows": {}}, {"total": 1, "rows": []},
    {"total": 0, "rows": [option_row()]}, {"total": 1, "rows": [None]},
    {"total": 1, "rows": [{"id": 1}]}])
def test_invalid_envelope_is_not_empty_success(monkeypatch, bad):
    serve(monkeypatch, [bad])
    with pytest.raises(RuntimeError):
        history()


@pytest.mark.parametrize("next_page", [dict(total=3, rows=[option_row(188032)]),
    dict(total=2, rows=[]), dict(total=2, rows=[option_row()])])
def test_changed_total_missing_or_repeated_page_fails(monkeypatch, next_page):
    serve(monkeypatch, [dict(total=2, rows=[option_row()]), next_page])
    with pytest.raises(RuntimeError):
        history()


@pytest.mark.parametrize("changes", [dict(id=None), dict(ContractID=None), dict(ContractCode=""),
    dict(DT="1405/08/16"), dict(DT="1405/13/01"), dict(DT_en="2026-11-07")])
def test_missing_identity_or_wrong_date_fails(monkeypatch, changes):
    row = option_row()
    row.update(changes)
    serve(monkeypatch, [dict(total=1, rows=[row])])
    with pytest.raises(RuntimeError):
        history()


def test_valid_empty_and_absent_exact_contract_have_same_schema(monkeypatch):
    serve(monkeypatch, [dict(total=0, rows=[]), dict(total=1, rows=[option_row()])])
    empty = history()
    filtered = history(contract_code="UNKNOWN")
    assert empty.empty and filtered.empty
    assert empty.columns.tolist() == filtered.columns.tolist()
    assert str(empty.GregorianDate.dtype) == "datetime64[ns]"
    assert str(empty.ID.dtype) == "string"


@pytest.mark.parametrize("kwargs", [dict(option_type="Calls"), dict(only_active="yes"),
    dict(contract_code=""), dict(contract_code=123), dict(_chunk_size=-1)])
def test_invalid_selection_fails_before_http(monkeypatch, kwargs):
    calls = serve(monkeypatch, [])
    with pytest.raises(ValueError):
        history(**kwargs)
    assert calls == []


def test_filter_cannot_hide_failure_in_later_page(monkeypatch):
    serve(monkeypatch, [dict(total=2, rows=[option_row()]), requests.Timeout("page two")])
    with pytest.raises(RuntimeError):
        history(contract_code="NQOR06P3000")


def test_filter_cannot_hide_malformed_financial_values(monkeypatch):
    row = option_row(188032, "OTHER")
    row['TradesValue'] = 'broken'
    serve(monkeypatch, [dict(total=2, rows=[option_row(), row])])
    with pytest.raises(RuntimeError):
        history(contract_code="NQOR06P3000")


def test_duplicate_identity_with_different_date_separators_fails(monkeypatch):
    first, second = option_row(), option_row()
    second.update(id=188034, DT='1405-08-17')
    serve(monkeypatch, [dict(total=2, rows=[first, second])])
    with pytest.raises(RuntimeError, match='duplicate'):
        history()


def test_duplicate_normalized_observation_id_fails(monkeypatch):
    first, second = option_row(), option_row(188032, 'OTHER')
    second['id'] = '188033'
    serve(monkeypatch, [dict(total=2, rows=[first, second])])
    with pytest.raises(RuntimeError, match='duplicate'):
        history()


@pytest.mark.parametrize("option_type, ot", [("All", 0), ("Call", 1), ("Put", 2)])
def test_source_filters_and_exact_case_sensitive_selection(monkeypatch, option_type, ot):
    calls = serve(monkeypatch, [dict(total=1, rows=[option_row()])])
    assert history(option_type=option_type, only_active=True, contract_code="nqor06p3000").empty
    assert calls[0][1]['params']['c'] == -1
    assert calls[0][1]['params']['ot'] == ot


def test_inactive_source_record_is_rejected_for_active_request(monkeypatch):
    row = option_row()
    row['IsActive'] = False
    serve(monkeypatch, [dict(total=1, rows=[row])])
    with pytest.raises(RuntimeError, match='inactive'):
        history(only_active=True)


def test_defaults_and_legacy_reversed_range(monkeypatch):
    calls = serve(monkeypatch, [dict(total=0, rows=[])])
    ime.get_all_ime_option_trades(_chunk_size=100000)
    assert calls[0][1]['params']['f'] == '1395/01/01'
    assert calls[0][1]['params']['t'] == str(ime.jd.date.today() - ime.jd.timedelta(days=1)).replace('-', '/')
    assert ime.get_all_ime_option_trades(start_date='1405-08-18', end_date='1405-08-17') is None


def test_no_import_time_requests():
    import subprocess
    import sys

    subprocess.run([sys.executable, '-c',
        "import requests; "
        "requests.sessions.Session.request=lambda *a,**k: (_ for _ in ()).throw(AssertionError('HTTP at import')); "
        "import fima; assert callable(fima.get_all_ime_option_trades)"], check=True)


@pytest.mark.integration
def test_live_option_history_matches_complete_official_report():
    """Explicit opt-in: compare all records and financial fields, not just nonemptiness."""
    params = dict(f="1405/08/10", t="1405/08/17", c=-1, ot=0, lang=8, order="asc")
    response = requests.get("https://www.ime.co.ir/subsystems/ime/option/optionboarddata.ashx",
                            params=params, timeout=(10, 45))
    response.raise_for_status()
    raw = response.json()
    assert len(raw["rows"]) == raw["total"] > 0
    assert raw['total'] > 1000  # Requires multiple real pages in the implementation.
    result = ime.get_all_ime_option_trades(only_active=True, start_date="1405-08-10", end_date="1405-08-17")
    assert len(result) == raw["total"]
    source = {str(row["id"]): row for row in raw["rows"]}
    assert set(result.ID) == set(source)
    for row in result.itertuples():
        original = source[row.ID]
        assert row.ContractCode == original["ContractCode"]
        assert row.TradeVolume == original["TradesVolume"]
        assert row.TradeValue == original["TradesValue"]
        assert row.LastPrice == original["LastPrice"]
        assert row.OpenInterest == original["OpenInterest"]
        assert row.TodaySettlementPrice == original["TodaySettlementPrice"]
