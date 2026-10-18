"""Public regressions characterized against the pre-audit implementation."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import fima.TSETMC as tse
import fima.Options as opt


def response(data):
    return SimpleNamespace(json=lambda: data, raise_for_status=lambda: None)


def daily():
    return dict(priceChange=2, priceMin="۹۰", priceMax="۱۲۰", priceYesterday=98,
                priceFirst=95, last=False, id=0, insCode="000123", dEven=20261017,
                hEven=122959, pClosing=100, iClose=False, yClose=True, pDrCotVal=110,
                zTotTran="7", qTotTran5J="1,234", qTotCap="123,400")


def test_daily_semantics_and_types(monkeypatch):
    monkeypatch.setattr(tse.requests, "get", lambda *a, **k: response({"closingPriceDaily": [daily()]}))
    result = tse.get_ticker_historical_data(ticker_instrument_code="000123")
    assert result.index.name == "JalaliDate"
    assert result.index.tolist() == ["1405-07-25"]
    assert result.iloc[0][["OpeningPrice", "LowPrice", "HighPrice", "ClosingPrice", "LastPrice",
                          "TransactionCount", "TradeVolume", "TradeValue"]].tolist() == [95, 90, 120, 100, 110, 7, 1234, 123400]
    assert all(pd.api.types.is_numeric_dtype(result[c]) for c in result)


def test_index_extrema_not_reversed(monkeypatch):
    record = dict(insCode="0001", hEven=90503, xDrNivJIdx004=105, xPhNivJIdx004=120,
                  xPbNivJIdx004=90, xVarIdxJRfV=2, indexChange=3, lVal30="Index",
                  dEven=0, c1=0, c2=0, c3=0, c4=0, last=False)
    monkeypatch.setattr(tse.requests, "get", lambda *a, **k: response({"indexB1": [record]}))
    result = tse.get_indexes_status()
    assert result.iloc[0]["HighIndexValue"] == 120
    assert result.iloc[0]["LowIndexValue"] == 90
    assert result.iloc[0]["InstrumentCode"] == "0001"
    assert result.iloc[0]["Time"] == "09:05:03"


def test_option_history_maps_keys_not_positions(monkeypatch):
    row = dict(reversed(list(daily().items())))

    def get(url, **kwargs):
        return response({"instrumentInfo": {"lVal30": "اختیارخ BASE-100-1405/09/18"}} if "GetInstrumentInfo" in url
                        else {"closingPriceDaily": [row]})

    monkeypatch.setattr(opt, "_find_instrument_code", lambda **kwargs: "000123")
    monkeypatch.setattr(opt.requests, "get", get)
    option, underlying = opt.download_historical_data("TEST")
    for result in [option, underlying]:
        assert result.JalaliDate.tolist() == ["1405-07-25"]
        assert result.iloc[0]["TransactionCount"] == 7
        assert result.iloc[0]["TradeVolume"] == 1234
        assert result.iloc[0]["ClosingPrice"] == 100
        assert result.iloc[0]["LastPrice"] == 110


def test_volatility_uses_latest_window_in_chronological_order():
    data = pd.DataFrame({"JalaliDate": ["1405-07-%02d" % i for i in range(1, 9)],
                         "ClosingPrice": [1, 1000, 10, 80, 100, 95, 110, 105]})
    expected = np.log(data.ClosingPrice.tail(5)).diff().std() * np.sqrt(252)
    assert opt._calculate_volatility(data.iloc[::-1], 4) == pytest.approx(expected)


def test_implied_volatility_passes_percent_rate_to_mibian(monkeypatch):
    captured = []

    def bs(args, **kwargs):
        captured.append(args)
        return SimpleNamespace(impliedVolatility=25)

    monkeypatch.setattr(opt, "BS", bs)
    info = pd.DataFrame([dict(DaysToMaturity=90, StrikePrice=100, Type="Call", LastPrice=8,
                              **{"LastPrice-UA": 105})])
    history = pd.DataFrame({"ClosingPrice": np.linspace(90, 110, 50)})
    assert opt.get_implied_volatility("TEST", _ticker_info_df=info, r_f=.05,
                                      _ua_historical_data=history) == .25
    assert captured[0][2] == 5


@pytest.mark.parametrize("kind,expected", [("Call", 20), ("Put", 0)])
def test_expiry_price_is_intrinsic(kind, expected):
    assert opt.calculate_black_scholes_merton(120, 100, 0, .2, .05, kind) == expected


def test_client_categories_match_official_individual_and_legal_labels(monkeypatch):
    monkeypatch.setattr(tse, "_find_instrument_code", lambda ticker: "000123")
    monkeypatch.setattr(tse, "get_ticker_historical_data", lambda **k: pd.DataFrame(
        index=pd.Index(["1405-07-25"], name="JalaliDate")))
    raw = {"recDate": 20261017, "insCode": "000123"}
    for side in ("buy", "sell"):
        for n, field in enumerate(("Volume", "Value", "Count"), 1):
            raw[f"{side}_I_{field}"] = n
            raw[f"{side}_N_{field}"] = n * 10
    monkeypatch.setattr(tse.requests, "get", lambda *a, **k: response({"clientType": raw}))
    result = tse.get_ticker_historical_trades_client_type("TEST", _max_workers=1)
    assert result.index.tolist() == ["1405-07-25"]
    for side in ("Buy", "Sell"):
        for n, field in enumerate(("Volume", "Value", "Count"), 1):
            assert result.iloc[0][f"Retail{side}{field}"] == n
            assert result.iloc[0][f"Institutional{side}{field}"] == n * 10


def option_record():
    raw = dict(insCode_P="00001", insCode_C="00002", contractSize=1000, uaInsCode="00003",
               lval30_UA="BASE", beginDate="20261001", endDate="20261209", strikePrice=100,
               remainedDay=52, pClosing_UA=105, pDrCotVal_UA=110, priceYesterday_UA=102)
    for side in ("P", "C"):
        for key, value in dict(lVal18AFC=side, lVal30="Option", zTotTran=7, qTotTran5J=1234,
                               qTotCap=9876, notionalValue=123400000, pClosing=6, priceYesterday=5,
                               oP=22, pDrCotVal=8, pMeDem=7, qTitMeDem=9, pMeOf=10,
                               qTitMeOf=11, yesterdayOP=20).items():
            raw[f"{key}_{side}"] = value
    return dict(reversed(list(raw.items())))


@pytest.mark.parametrize("stack", ["Horizontal", "Vertical"])
@pytest.mark.parametrize("j_date", [True, False])
def test_option_watch_named_mapping_dates_and_identifiers(monkeypatch, stack, j_date):
    monkeypatch.setattr(opt.requests, "get", lambda *a, **k: response({"instrumentOptMarketWatch": [option_record()]}))
    result = opt.download_market_watch(stack=stack, j_date=j_date)
    assert result is not None
    prefix = "Call" if stack == "Horizontal" else ""
    assert result.iloc[0][prefix + "TransactionCount"] == 7
    assert result.iloc[0][prefix + "TradeVolume"] == 1234
    assert result.iloc[0][prefix + "TradeValue"] == 9876
    assert result.iloc[0][prefix + "InstrumentCode"] == "00002"
    assert result.iloc[0][prefix + "ClosingPrice"] == 6
    assert result.iloc[0][prefix + "LastPrice"] == 8
    assert result.iloc[0][prefix + "BidPrice"] == 7
    assert result.iloc[0][prefix + "AskPrice"] == 10
    assert result.iloc[0]["UnderlyingInstrumentCode"] == "00003"
    if j_date:
        assert result.iloc[0].BeginJalaliDate == "1405-07-09"
    else:
        assert str(result.BeginGregorianDate.dtype) == "datetime64[ns]"
    assert all(__import__("re").fullmatch(r"[A-Z][A-Za-z0-9]*", column) for column in result)


def test_implied_volatility_matches_known_premium():
    from mibian import BS
    premium = BS([105, 100, 5, 90], volatility=25).callPrice
    info = pd.DataFrame([dict(DaysToMaturity=90, StrikePrice=100, OptionType="Call", LastPrice=premium,
                              UnderlyingLastPrice=105)])
    history = pd.DataFrame({"ClosingPrice": np.linspace(90, 110, 50)})
    assert opt.get_implied_volatility("TEST", _ticker_info_df=info, r_f=.05,
                                      _ua_historical_data=history) == pytest.approx(.25, abs=.001)


@pytest.mark.parametrize("function", ["download_market_watch", "download_chain_contracts"])
def test_option_analytics_pipeline_with_public_history(monkeypatch, function):
    monkeypatch.setattr(opt.requests, "get", lambda *a, **k: response({"instrumentOptMarketWatch": [option_record()]}))
    history = pd.DataFrame({"ClosingPrice": np.linspace(90, 110, 80)},
                           index=pd.Index([str(__import__("jdatetime").date(1405, 1, 1) + __import__("jdatetime").timedelta(days=i)) for i in range(80)], name="JalaliDate"))
    monkeypatch.setattr(opt, "get_ticker_historical_data", lambda **k: history)
    monkeypatch.setattr(opt, "get_risk_free_rate", lambda: .05)
    kwargs = {"underlying_ticker": "BASE"} if function == "download_chain_contracts" else {}
    result = getattr(opt, function)(**kwargs, bsm=True, greeks=True, implied_volatility=True)
    assert result is not None
    assert result.iloc[0].RiskFreeRate == 5
    assert result.iloc[0].CallBSMPrice >= 0
    assert pd.notna(result.iloc[0].PutDelta)
    assert result.iloc[0].CallVolatility > 0
    assert not any("HistoricalData" in column for column in result)


def test_shared_parsers_preserve_missing_zero_and_identifier_digits():
    from fima._data import number_series, identifier_series, jalali_date, gregorian_series
    values = number_series(pd.Series(["\u06f1\u066c\u06f2\u06f3\u06f4", "\u06f0", "2.7%", "N/A", None, "-"]))
    assert values.iloc[:3].tolist() == [1234, 0, 2.7]
    assert values.iloc[3:].isna().all()
    assert identifier_series(pd.Series(["00012", 123.0, None])).iloc[:2].tolist() == ["00012", "123"]
    assert jalali_date("\u06f1\u06f4\u06f0\u06f5/\u06f7/\u06f2\u06f5") == "1405-07-25"
    dates = gregorian_series(pd.Series(["2026-10-17", "", None]))
    assert str(dates.dtype) == "datetime64[ns]"
    assert dates.iloc[1:].isna().all()
    with pytest.raises(ValueError):
        number_series(pd.Series(["not-a-number"]))


def test_at_the_money_expiry_and_zero_volatility_limit():
    assert opt.calculate_black_scholes_merton(100, 100, 0, .2, .05, "Call") == 0
    assert opt.calculate_black_scholes_merton(100, 100, 1, 0, .05, "Call") == pytest.approx(100 - 100 * np.exp(-.05))


def test_market_cap_uses_official_close_and_share_count(monkeypatch):
    monkeypatch.setattr(tse, "_find_instrument_code", lambda _: "123")
    monkeypatch.setattr(tse, "get_ticker_historical_data", lambda **k: pd.DataFrame(
        {"ClosingPrice": [100], "LastPrice": [110]}, index=pd.Index(["1405-07-25"], name="JalaliDate")))
    monkeypatch.setattr(tse, "_fetch_shares_no_for_date", lambda args: (args[0], 10))
    result = tse.get_ticker_historical_market_caps("TEST", _max_workers=1)
    assert result.iloc[0].NumberOfShares == 10
    assert result.iloc[0].MarketCap == 1000


@pytest.mark.parametrize("kind,benchmark", [("Call", 10.450583572185565), ("Put", 5.573526022256971)])
def test_model_price_benchmark_and_greek_finite_differences(kind, benchmark):
    s, k, t, sigma, rate = 100, 100, 1, .2, .05
    price = lambda s=s, t=t, sigma=sigma, rate=rate: opt.calculate_black_scholes_merton(s, k, t, sigma, rate, kind)
    assert price() == pytest.approx(benchmark)
    epsilon = .001
    delta = (price(s=s + epsilon) - price(s=s - epsilon)) / (2 * epsilon)
    gamma = (price(s=s + epsilon) - 2 * price() + price(s=s - epsilon)) / epsilon ** 2
    vega = (price(sigma=sigma + epsilon) - price(sigma=sigma - epsilon)) / (2 * epsilon)
    rho = (price(rate=rate + epsilon) - price(rate=rate - epsilon)) / (2 * epsilon)
    theta = -(price(t=t + epsilon) - price(t=t - epsilon)) / (2 * epsilon)
    assert opt.calculate_delta(s, k, t, rate, sigma, kind) == pytest.approx(delta, rel=1e-5)
    assert opt.calculate_gamma(s, k, t, rate, sigma) == pytest.approx(gamma, rel=1e-5)
    assert opt.calculate_vega(s, k, t, rate, sigma) == pytest.approx(vega, rel=1e-5)
    assert opt.calculate_rho(s, k, t, rate, sigma, kind) == pytest.approx(rho, rel=1e-5)
    assert opt.calculate_theta(s, k, t, rate, sigma, kind) == pytest.approx(theta, rel=1e-5)
