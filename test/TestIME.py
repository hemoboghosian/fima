import pytest
import pandas as pd
import jdatetime as jd
from fima.IME import get_all_ime_physical_trades, get_all_ime_futures_trades


@pytest.mark.parametrize(["start_date", "end_date"], [('1400-01-01', '1400-12-29'),
                                                      ('1404-01-01', str(jd.date.today() + jd.timedelta(days=10))),
                                                      (None, None), (None, '1400-12-29'), ('1400-12-29', None)])
def test_get_all_ime_physical_trades(start_date, end_date):
    all_ime_physical_trades = get_all_ime_physical_trades(start_date, end_date)
    assert all_ime_physical_trades is not None
    assert not all_ime_physical_trades.empty
    assert isinstance(all_ime_physical_trades, pd.DataFrame)
    assert all(column in all_ime_physical_trades.columns for column in
               ['GoodsName', 'Symbol', 'ProducerName', 'ContractType', 'MinPrice','ClosePrice', 'MaxPrice',
                'SupplyVolume', 'SupplyBasePrice', 'SupplyMinPrice', 'Demand', 'DemandMaxPrice', 'ContractSize',
                'TransactionValue', 'Date', 'DeliveryDate', 'Warehouse', 'Supplier', 'SettlementDate', 'Broker',
                'SupplyType', 'BuyType', 'Currency', 'Unit', 'ExchangeHall', 'PacketType', 'Settlement'])


@pytest.mark.parametrize(["only_active", "start_date", "end_date"],
                         [(True, str(jd.date.today() - jd.timedelta(days=10)), str(jd.date.today())),
                          (True, str(jd.date.today()), str(jd.date.today() + jd.timedelta(days=10))),
                          (True, str(jd.date.today()), str(jd.date.today())),
                          (True, str(jd.date.today() - jd.timedelta(days=10)), str(jd.date.today() + jd.timedelta(days=10))),
                          (True, None, None),
                          (False, str(jd.date.today() - jd.timedelta(days=10)), str(jd.date.today())),
                          (False, '1404-01-01', '1404-02-01'),
                          (False, '1404-01-01', str(jd.date.today() + jd.timedelta(days=10))),
                          (False, None, None), (False, None, '1400-01-01'), (False, '1403-01-01', None)])
def test_get_all_ime_futures_trades(only_active, start_date, end_date):
    all_ime_futures_trades = get_all_ime_futures_trades(only_active, start_date, end_date)
    assert isinstance(all_ime_futures_trades, pd.DataFrame)
    assert all_ime_futures_trades is not None
    assert not all_ime_futures_trades.empty
    assert all(column in all_ime_futures_trades.columns for column in
               ['ContractDay', 'ContractCode', 'ContractDescription', 'TradesVolume',
                'TradesValue', 'MaxPrice', 'MinPrice', 'LastPrice', 'FirstPrice',
                'OpenInterest', 'ChangeOpenInterest', 'ActiveCustomers',
                'ActiveBrokers', 'CBuy', 'CSell', 'RetailBuyVolume', 'RetailBuyValue',
                'RetailSellVolume', 'RetailSellValue', 'LastSettlementPrice',
                'TodaySettlementPrice', 'SettlementPricePercent', 'Date',
                'DeliveryDate', 'WeeklyOpenInterests', 'WeeklyOpenInterestsPercent',
                'MonthlyOpenInterests', 'WeeklySettlementPrice',
                'WeeklySettlementPricePercent', 'MonthlySettlementPrice',
                'InstitutionalBuyVolume', 'InstitutionalBuyValue',
                'MonthlyOpenInterestsPercent', 'MonthlySettlementPricePercent',
                'InstitutionalSellVolume', 'InstitutionalSellValue'])
