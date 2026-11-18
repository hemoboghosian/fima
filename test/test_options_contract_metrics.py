"""Independent financial examples and existing-provider schema for offline metrics."""
import numpy as np
import pandas as pd
import pytest
import requests

import fima
import fima.Options as options


METRICS = [
    'QuoteStatus', 'MidPrice', 'Spread', 'SpreadPercent', 'ReferencePrice',
    'UnderlyingReferencePrice', 'SpotStrikeRatio', 'IntrinsicValue', 'TimeValue',
    'BreakevenPrice', 'PremiumPerContract', 'VolumeOpenPositionsRatio',
]


@pytest.fixture(autouse=True)
def no_http(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Offline option metrics must not request HTTP')
    monkeypatch.setattr(requests.Session, 'request', forbidden)


@pytest.fixture
def watch():
    return pd.DataFrame({
        'Ticker': ['SYNTHETIC-C', 'SYNTHETIC-P'],
        'InstrumentCode': ['0001', '0002'], 'UnderlyingInstrumentCode': ['0003', '0003'],
        'OptionType': ['Call', 'Put'], 'StrikePrice': [100., 120.],
        'ContractSize': [1000., 1254.], 'UnderlyingLastPrice': [110., 110.],
        'UnderlyingClosingPrice': [105., 105.], 'BidPrice': [8., 12.],
        'AskPrice': [12., 16.], 'BidVolume': [2., 3.], 'AskVolume': [4., 5.],
        'LastPrice': [11., 15.], 'ClosingPrice': [10., 14.],
        'TradeVolume': [20., 0.], 'OpenPositions': [100., 0.],
        'Status': ['ITM', 'ITM'], 'EndJalaliDate': ['1405-09-01', '1405-10-01'],
    }, index=pd.Index([7, 7], name='Selection'))


def test_default_formulas_identity_order_and_immutability(watch):
    watch.attrs['SourceURL'] = 'https://example.invalid/fixture'
    before = watch.copy(deep=True)
    result = options.calculate_contract_metrics(watch)
    pd.testing.assert_frame_equal(watch, before)
    pd.testing.assert_frame_equal(result[watch.columns], before)
    assert result.attrs == watch.attrs
    assert list(result) == list(watch) + METRICS
    assert result.QuoteStatus.tolist() == ['TwoSided', 'TwoSided']
    assert str(result.QuoteStatus.dtype) == 'string'
    assert all(str(result[c].dtype) == 'float64' for c in METRICS[1:])
    assert result.MidPrice.tolist() == [10., 14.]
    assert result.Spread.tolist() == [4., 4.]
    assert result.SpreadPercent.tolist() == pytest.approx([40., 100 * 4 / 14])
    assert result.ReferencePrice.tolist() == [12., 16.]
    assert result.IntrinsicValue.tolist() == [10., 10.]
    assert result.TimeValue.tolist() == [2., 6.]
    assert result.BreakevenPrice.tolist() == [112., 104.]
    assert result.PremiumPerContract.tolist() == [12000., 20064.]
    assert result.SpotStrikeRatio.tolist() == pytest.approx([1.1, 110 / 120])
    assert result.VolumeOpenPositionsRatio.iloc[0] == .2
    assert pd.isna(result.VolumeOpenPositionsRatio.iloc[1])


@pytest.mark.parametrize('price,expected', [
    ('Ask', [12., 16.]), ('Bid', [8., 12.]), ('Mid', [10., 14.]),
    ('Last', [11., 15.]), ('Closing', [10., 14.]),
])
def test_explicit_price_choices(watch, price, expected):
    result = options.calculate_contract_metrics(watch, price=price, underlying_price='Closing')
    assert result.ReferencePrice.tolist() == expected
    assert result.UnderlyingReferencePrice.tolist() == [105., 105.]
    assert result.IntrinsicValue.tolist() == [5., 15.]
    assert result.Status.tolist() == ['ITM', 'ITM']


@pytest.mark.parametrize('bid,bv,ask,av,status,mid', [
    (10, 1, 12, 2, 'TwoSided', 11), (10, 1, 10, 2, 'Locked', 10),
    (12, 1, 10, 2, 'Crossed', None), (10, 1, 0, 0, 'BidOnly', None),
    (0, 0, 10, 2, 'AskOnly', None), (0, 0, 0, 0, 'NoQuote', None),
    (10, 0, 12, 0, 'NoQuote', None), (None, 1, 10, 2, 'Incomplete', None),
    (10, 1, np.nan, 2, 'Incomplete', None), (10, -1, 12, 2, 'Incomplete', None),
    (np.inf, 1, 12, 2, 'Incomplete', None),
])
def test_quote_states(watch, bid, bv, ask, av, status, mid):
    watch = watch.iloc[:1].copy()
    watch[['BidPrice', 'BidVolume', 'AskPrice', 'AskVolume']] = [bid, bv, ask, av]
    row = options.calculate_contract_metrics(watch, price='Mid').iloc[0]
    assert row.QuoteStatus == status
    if mid is None:
        assert pd.isna(row.MidPrice) and pd.isna(row.Spread) and pd.isna(row.ReferencePrice)
    else:
        assert row.MidPrice == mid
        assert row.Spread == ask - bid


def test_no_substitution_and_crossed_reference_rules(watch):
    watch['AskPrice'] = 0.
    assert options.calculate_contract_metrics(watch).ReferencePrice.isna().all()
    assert options.calculate_contract_metrics(watch, price='Bid').ReferencePrice.tolist() == [8., 12.]
    watch['AskPrice'] = 1.
    for price in ('Ask', 'Bid', 'Mid'):
        assert options.calculate_contract_metrics(watch, price=price).ReferencePrice.isna().all()
    assert options.calculate_contract_metrics(watch, price='Last').ReferencePrice.tolist() == [11., 15.]
    watch['LastPrice'] = 0.
    assert options.calculate_contract_metrics(watch, price='Last').ReferencePrice.isna().all()


def test_known_side_survives_unknown_opposite_side(watch):
    watch['BidPrice'] = np.nan
    result = options.calculate_contract_metrics(watch)
    assert result.QuoteStatus.tolist() == ['Incomplete', 'Incomplete']
    assert result.ReferencePrice.tolist() == [12., 16.]


def test_negative_time_value_and_unreachable_put_breakeven(watch):
    watch['LastPrice'] = [1., 121.]
    result = options.calculate_contract_metrics(watch, price='Last')
    assert result.TimeValue.tolist() == [-9., 111.]
    assert pd.isna(result.BreakevenPrice.iloc[1])
    watch['LastPrice'] = [1., 120.]
    assert options.calculate_contract_metrics(watch, price='Last').BreakevenPrice.iloc[1] == 0.


@pytest.mark.parametrize('column,value,missing', [
    ('UnderlyingLastPrice', pd.NA, ['UnderlyingReferencePrice', 'IntrinsicValue', 'TimeValue', 'SpotStrikeRatio']),
    ('UnderlyingLastPrice', 0, ['IntrinsicValue', 'SpotStrikeRatio']),
    ('StrikePrice', -1, ['IntrinsicValue', 'TimeValue', 'SpotStrikeRatio', 'BreakevenPrice']),
    ('ContractSize', np.nan, ['PremiumPerContract']),
    ('ContractSize', 0, ['PremiumPerContract']),
    ('OpenPositions', 0, ['VolumeOpenPositionsRatio']),
    ('TradeVolume', -1, ['VolumeOpenPositionsRatio']),
])
def test_missing_or_invalid_observations_only_mask_dependent_results(watch, column, value, missing):
    watch[column] = value
    result = options.calculate_contract_metrics(watch)
    assert result[missing].isna().all().all()
    assert result.ReferencePrice.notna().all()


def test_missing_spot_does_not_invalidate_premium_or_breakeven(watch):
    watch['UnderlyingLastPrice'] = np.nan
    result = options.calculate_contract_metrics(watch)
    assert result.IntrinsicValue.isna().all()
    assert result.BreakevenPrice.tolist() == [112., 104.]
    assert result.PremiumPerContract.tolist() == [12000., 20064.]


@pytest.mark.parametrize('kwargs', [{'price': 'ask'}, {'underlying_price': 'Mid'}])
def test_invalid_choices(watch, kwargs):
    with pytest.raises(ValueError):
        options.calculate_contract_metrics(watch, **kwargs)


def test_invalid_schema_and_values(watch):
    for bad in (None, pd.DataFrame({'CallTicker': ['C']}), watch.drop(columns='BidVolume'),
                pd.concat([watch, watch[['Ticker']]], axis=1)):
        with pytest.raises(ValueError):
            options.calculate_contract_metrics(bad)
    watch['OptionType'] = 'call'
    with pytest.raises(ValueError, match='OptionType'):
        options.calculate_contract_metrics(watch)
    watch['OptionType'] = 'Call'
    watch['BidPrice'] = 'invalid'
    with pytest.raises(ValueError, match='BidPrice'):
        options.calculate_contract_metrics(watch)


@pytest.mark.parametrize('value', [True, 1 + 2j, np.complex64(1j), pd.Timestamp('2026-11-18')])
def test_nonnumeric_financial_types_are_rejected(watch, value):
    watch['BidPrice'] = value
    with pytest.raises(ValueError, match='BidPrice'):
        options.calculate_contract_metrics(watch)


def test_repeated_analysis_does_not_overwrite_existing_columns(watch):
    enriched = options.calculate_contract_metrics(watch)
    with pytest.raises(ValueError, match='original'):
        options.calculate_contract_metrics(enriched)


def test_nullable_numbers_and_zero_volume_ratio(watch):
    watch['OpenPositions'] = pd.array([100, pd.NA], dtype='Int64')
    watch['TradeVolume'] = pd.array([0, pd.NA], dtype='Int64')
    result = options.calculate_contract_metrics(watch)
    assert result.VolumeOpenPositionsRatio.iloc[0] == 0
    assert pd.isna(result.VolumeOpenPositionsRatio.iloc[1])


def test_overflowing_derived_values_are_missing(watch):
    watch['LastPrice'] = 1e308
    watch['StrikePrice'] = 1e308
    result = options.calculate_contract_metrics(watch, price='Last')
    assert result.PremiumPerContract.isna().all()
    assert pd.isna(result.BreakevenPrice.iloc[0])
    assert not np.isinf(result[METRICS[1:]].to_numpy()).any()


def test_empty_has_stable_schema_and_no_mutation(watch):
    empty = watch.iloc[:0].copy()
    result = options.calculate_contract_metrics(empty)
    assert result.empty and list(result) == list(empty) + METRICS
    assert str(result.QuoteStatus.dtype) == 'string'
    assert all(str(result[c].dtype) == 'float64' for c in METRICS[1:])
    assert list(empty) == list(watch)
    assert fima.calculate_contract_metrics is options.calculate_contract_metrics


def test_existing_provider_fixture_round_trip(monkeypatch):
    from types import SimpleNamespace
    from test.test_tsetmc_options_contracts import option_record
    monkeypatch.setattr(options.requests, 'get', lambda *a, **k: SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {'instrumentOptMarketWatch': [option_record()]}))
    frame = options.download_market_watch(stack='Vertical')
    result = options.calculate_contract_metrics(frame)
    assert result.InstrumentCode.tolist() == ['00002', '00001']
    assert result.UnderlyingInstrumentCode.tolist() == ['00003', '00003']
    assert result.IntrinsicValue.tolist() == [10., 0.]
    assert result.PremiumPerContract.tolist() == [10000., 10000.]
