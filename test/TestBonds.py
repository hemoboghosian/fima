import pytest
from fima.Bonds import get_risk_free_rate, get_all_bonds_without_coupons, get_all_bonds_with_coupons


def test_get_risk_free_rate_range():
    risk_free_rate = get_risk_free_rate()
    assert isinstance(risk_free_rate, float)
    assert 0.25 <= risk_free_rate <= 0.5  # Typical YTM for Iranian T-bills


@pytest.mark.parametrize("deprecated", [True, False])
def test_get_all_bonds_without_coupons(deprecated):
    all_bonds_without_coupons = get_all_bonds_without_coupons(deprecated=deprecated)
    assert all_bonds_without_coupons is not None
    assert not all_bonds_without_coupons.empty
    for column in ['Ticker', 'LastTradedPrice', 'LastTradedDate', 'MaturityDate', 'YTM', 'SimpleReturn']:
        assert column in all_bonds_without_coupons.columns


@pytest.mark.parametrize("deprecated", [True, False])
def test_get_all_bonds_with_coupons(deprecated):
    all_bonds_with_coupons = get_all_bonds_with_coupons(deprecated=deprecated)
    assert all_bonds_with_coupons is not None
    assert not all_bonds_with_coupons.empty
    for column in ['Ticker', 'LastTradedPrice', 'LastTradedDate', 'MaturityDate', 'YTM']:
        assert column in all_bonds_with_coupons.columns
