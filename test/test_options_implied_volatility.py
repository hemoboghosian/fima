"""Model bounds and independent repricing regressions for issue #162."""
from math import erf, exp, log, sqrt
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import requests

import fima.Options as options


def price(kind, s=100., k=100., rate=.05, days=90., sigma=.25):
    """Independent scalar formula, using math.erf rather than fima/Mibian."""
    t = days / 365
    discount = k * exp(-rate * t)
    if sigma == 0:
        return max(s - discount, 0) if kind == 'Call' else max(discount - s, 0)
    d1 = (log(s / k) + (rate + sigma * sigma / 2) * t) / (sigma * sqrt(t))
    d2 = d1 - sigma * sqrt(t)
    cdf = lambda x: (1 + erf(x / sqrt(2))) / 2
    return s * cdf(d1) - discount * cdf(d2) if kind == 'Call' else discount * cdf(-d2) - s * cdf(-d1)


@pytest.fixture(autouse=True)
def no_http(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('IV correctness tests must not use HTTP')
    monkeypatch.setattr(requests.Session, 'request', forbidden)


@pytest.fixture
def inputs():
    info = pd.DataFrame([dict(UnderlyingTicker='BASE', UnderlyingLastPrice=100.,
                              StrikePrice=100., DaysToMaturity=90., OptionType='Call', LastPrice=150.)])
    history = pd.DataFrame({'ClosingPrice': np.linspace(90, 110, 60)})
    return info, history


def iv(inputs, *, kind='Call', premium=None, rate=.05, **fields):
    info, history = inputs
    info = info.assign(**dict({'OptionType': kind}, **fields))
    if premium is not None:
        info['LastPrice'] = premium
    return options.get_implied_volatility('SYNTHETIC', _ticker_info_df=info,
                                          r_f=rate, _ua_historical_data=history)


def test_reproduced_impossible_call_is_missing(inputs):
    assert iv(inputs) is None  # Previously 5.0 decimal IV for a 150 premium on 100 spot.


@pytest.mark.parametrize('kind,s,k,rate,premium', [
    ('Call', 100, 100, .05, 100.01), ('Put', 100, 100, .05, 100.),
    ('Call', 120, 100, .05, 19.), ('Put', 80, 100, .05, 17.),
    ('Put', 100, 100, -.05, 102.), ('Call', 100, 100, .05, -1.),
])
def test_outside_model_bounds(inputs, kind, s, k, rate, premium):
    assert iv(inputs, kind=kind, premium=premium, rate=rate,
              UnderlyingLastPrice=s, StrikePrice=k) is None


@pytest.mark.parametrize('kind', ['Call', 'Put'])
@pytest.mark.parametrize('sigma', [.05, .25, 2., 4.99, 5.])
def test_valid_iv_and_independent_residual(inputs, kind, sigma):
    premium = price(kind, sigma=sigma)
    result = iv(inputs, kind=kind, premium=premium)
    assert result == pytest.approx(sigma, abs=2e-6)
    assert price(kind, sigma=result) == pytest.approx(premium, abs=1e-8 * max(1, premium) + 2e-12)


@pytest.mark.parametrize('kind', ['Call', 'Put'])
def test_valid_integer_premium_is_refined_instead_of_discarded(inputs, kind):
    result = iv(inputs, kind=kind, premium=5.)
    assert result is not None
    assert price(kind, sigma=result) == pytest.approx(5., abs=5e-8)


@pytest.mark.parametrize('kind,s,k,rate', [
    ('Call', 120., 100., .05), ('Put', 80., 100., .05),
    ('Call', 80., 100., .05), ('Put', 120., 100., .05),
    ('Call', 120., 100., -.05), ('Put', 80., 100., -.05),
])
def test_zero_volatility_boundary(inputs, kind, s, k, rate):
    premium = price(kind, s=s, k=k, rate=rate, sigma=0)
    assert iv(inputs, kind=kind, premium=premium, rate=rate,
              UnderlyingLastPrice=s, StrikePrice=k) == 0.


@pytest.mark.parametrize('kind', ['Call', 'Put'])
def test_upper_bound_requires_infinite_iv(inputs, kind):
    upper = 100. if kind == 'Call' else 100. * exp(-.05 * 90 / 365)
    assert iv(inputs, kind=kind, premium=upper) is None


def test_lower_boundary_roundoff_and_small_positive_time_value(inputs):
    lower = price('Call', s=120, sigma=0)
    assert iv(inputs, premium=np.nextafter(lower, -np.inf), UnderlyingLastPrice=120) == 0.
    assert iv(inputs, premium=lower - 1e-6, UnderlyingLastPrice=120) is None
    result = iv(inputs, premium=lower + 1e-5, UnderlyingLastPrice=120)
    assert result is not None and result > 0
    assert price('Call', s=120, sigma=result) == pytest.approx(lower + 1e-5, abs=3e-7)


@pytest.mark.parametrize('kind', ['Call', 'Put'])
def test_valid_premium_beyond_mibian_range_is_not_capped(inputs, kind):
    result = iv(inputs, kind=kind, premium=price(kind, sigma=6.))
    assert result == pytest.approx(6., abs=2e-6)


def test_low_volatility_survives_mibian_premium_rounding(inputs):
    premium = price('Call', rate=0., sigma=1e-8)
    assert 0 < premium < .5e-6
    result = iv(inputs, premium=premium, rate=0.)
    assert result is not None and result > 0
    assert price('Call', rate=0., sigma=result) == pytest.approx(premium, abs=2e-12)


@pytest.mark.parametrize('candidate', [None, np.nan, np.inf, -1.])
def test_invalid_solver_candidate_is_missing(monkeypatch, inputs, candidate):
    monkeypatch.setattr(options, 'BS', lambda *a, **k: SimpleNamespace(impliedVolatility=candidate))
    def unavailable(*args, **kwargs):
        raise RuntimeError('No independently verified root')
    monkeypatch.setattr(options, '_brentq', unavailable)
    assert iv(inputs, premium=price('Call')) is None


def test_bad_residual_is_never_forwarded(monkeypatch, inputs):
    monkeypatch.setattr(options, 'BS', lambda *a, **k: SimpleNamespace(impliedVolatility=5.))
    result = iv(inputs, premium=price('Call'))
    assert result != .05
    if result is not None:
        assert price('Call', sigma=result) == pytest.approx(price('Call'), abs=1e-7)


@pytest.mark.parametrize('outcome', ['raises', 'bad_residual', 'nonfinite'])
def test_unverified_refinement_is_missing(monkeypatch, inputs, outcome):
    monkeypatch.setattr(options, 'BS', lambda *a, **k: SimpleNamespace(impliedVolatility=5.))
    def refine(*args, **kwargs):
        if outcome == 'raises':
            raise RuntimeError('No convergence')
        if outcome == 'nonfinite':
            return np.nan
        return .1
    monkeypatch.setattr(options, '_brentq', refine)
    assert iv(inputs, premium=price('Call')) is None


def test_unbracketed_search_has_a_finite_budget(monkeypatch, inputs):
    evaluations = []
    def unresolved(s, k, t, sigma, rate, kind):
        evaluations.append(sigma)
        return 0.
    monkeypatch.setattr(options, 'calculate_black_scholes_merton', unresolved)
    assert iv(inputs, premium=5.) is None
    assert len(evaluations) < 30


@pytest.mark.parametrize('kind', ['Call', 'Put'])
@pytest.mark.parametrize('days', [10., 30.])
def test_short_eligible_maturities_keep_integer_history_windows(inputs, kind, days):
    result = iv(inputs, kind=kind, premium=price(kind, days=days), DaysToMaturity=days)
    assert result == pytest.approx(.25, abs=2e-6)


@pytest.mark.parametrize('scale', [.1, 1000.])
def test_unit_scaling_and_negative_rates(inputs, scale):
    premium = price('Put', rate=-.05) * scale
    result = iv(inputs, kind='Put', premium=premium, rate=-.05,
                UnderlyingLastPrice=100 * scale, StrikePrice=100 * scale)
    assert result == pytest.approx(.25, abs=2e-6)


@pytest.mark.parametrize('field,value', [
    ('UnderlyingLastPrice', None), ('UnderlyingLastPrice', 0), ('UnderlyingLastPrice', np.inf),
    ('StrikePrice', np.nan), ('StrikePrice', -1), ('StrikePrice', 'bad'),
    ('DaysToMaturity', pd.NA), ('DaysToMaturity', np.inf), ('DaysToMaturity', 'bad'),
    ('LastPrice', np.nan), ('LastPrice', np.inf), ('LastPrice', 'bad'),
    ('LastPrice', True), ('LastPrice', np.complex128(1j)),
    ('OptionType', None),
])
def test_invalid_inputs_are_missing(inputs, field, value):
    assert iv(inputs, **{field: value}) is None


@pytest.mark.parametrize('rate', [np.nan, np.inf, 'bad', -10000., 10000.])
def test_invalid_rate_is_missing(inputs, rate):
    assert iv(inputs, premium=5., rate=rate) is None


def test_history_and_expiry_eligibility_are_preserved(inputs):
    assert iv(inputs, premium=0., DaysToMaturity=0) is None
    assert iv(inputs, premium=0., DaysToMaturity=9) is None
    info, history = inputs
    assert options.get_implied_volatility('SYNTHETIC', _ticker_info_df=info, r_f=.05,
                                          _ua_historical_data=history.iloc[:2]) is None


@pytest.mark.parametrize('layout', ['Horizontal', 'Vertical', 'chain'])
def test_missing_iv_propagates_through_watch_and_chain(monkeypatch, layout):
    from test.test_tsetmc_options_contracts import option_record
    record = option_record()
    record.update(pDrCotVal_UA=100, strikePrice=100, pDrCotVal_C=150, pDrCotVal_P=150,
                  remainedDay=90)
    monkeypatch.setattr(options.requests, 'get', lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {'instrumentOptMarketWatch': [record]}))
    history = pd.DataFrame({'ClosingPrice': np.linspace(90, 110, 60)},
                           index=pd.Index(pd.date_range('2026-01-01', periods=60), name='JalaliDate'))
    monkeypatch.setattr(options, 'get_ticker_historical_data', lambda **k: history)
    monkeypatch.setattr(options, 'get_risk_free_rate', lambda: .05)
    result = (options.download_chain_contracts('BASE', implied_volatility=True) if layout == 'chain'
              else options.download_market_watch(stack=layout, implied_volatility=True))
    columns = ['ImpliedVolatility'] if layout == 'Vertical' else ['CallImpliedVolatility', 'PutImpliedVolatility']
    assert result[columns].isna().all().all()
    assert result.RiskFreeRate.eq(5).all()
