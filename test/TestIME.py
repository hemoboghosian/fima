import pytest
import pandas as pd
import jdatetime as jd
from fima.IME import (get_all_ime_physical_trades, get_all_ime_futures_trades, get_all_ime_option_trades,
                      get_all_physical_producer_products, get_producer_physical_trades, get_all_ime_export_trades,
                      get_all_ime_cd_trades, get_all_export_producer_products, get_producer_export_trades,
                      get_all_ime_salaf_trades, get_gold_and_silver_cd_trades)


@pytest.mark.parametrize(["start_date", "end_date"], [('1400-01-01', '1400-12-29'),
                                                      ('1404-01-01', str(jd.date.today() + jd.timedelta(days=10))),
                                                      (None, None), (None, '1400-12-29'), ('1403-12-29', None)])
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

    if start_date is not None:
        start_jd = jd.date(int(start_date[:4]), int(start_date[5:7]), int(start_date[8:]))
    else:
        start_jd = jd.date(1385, 1, 1)

    if end_date is not None:
        end_jd = jd.date(int(end_date[:4]), int(end_date[5:7]), int(end_date[8:]))
    else:
        end_jd = jd.date.today()
    assert all(start_jd <= date_column <= end_jd for date_column in all_ime_physical_trades['Date'] if pd.notna(date_column))



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
    if not only_active:
        assert not all_ime_futures_trades.empty
    if only_active and all_ime_futures_trades.empty:
        return
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

    if start_date is not None:
        start_jd = jd.date(int(start_date[:4]), int(start_date[5:7]), int(start_date[8:]))
    else:
        start_jd = jd.date(1387, 1, 1)

    if end_date is not None:
        end_jd = jd.date(int(end_date[:4]), int(end_date[5:7]), int(end_date[8:]))
    else:
        end_jd = jd.date.today()
    assert all(start_jd <= date_column <= end_jd for date_column in all_ime_futures_trades['Date'] if pd.notna(date_column))



@pytest.mark.parametrize(["option_type", "only_active", "start_date", "end_date"],
                         [
                             ("All", True, str(jd.date.today() - jd.timedelta(days=10)), str(jd.date.today())),
                             ("All", True, str(jd.date.today() - jd.timedelta(days=10)),
                              str(jd.date.today() + jd.timedelta(days=10))),
                             ("All", True, None, None),
                             ("All", False, str(jd.date.today() - jd.timedelta(days=10)), str(jd.date.today())),
                             ("All", False, '1404-01-01', '1404-02-01'),
                             ("All", False, '1404-01-01', str(jd.date.today() + jd.timedelta(days=10))),
                             ("All", False, None, None),
                             ("All", False, None, '1400-01-01'),
                             ("All", False, '1403-01-01', None),
                             ("Call", True, str(jd.date.today() - jd.timedelta(days=10)), str(jd.date.today())),
                             ("Call", True, str(jd.date.today() - jd.timedelta(days=10)),
                              str(jd.date.today() + jd.timedelta(days=10))),
                             ("Call", True, None, None),
                             ("Call", False, str(jd.date.today() - jd.timedelta(days=10)), str(jd.date.today())),
                             ("Call", False, '1404-01-01', '1404-02-01'),
                             ("Call", False, '1404-01-01', str(jd.date.today() + jd.timedelta(days=10))),
                             ("Call", False, None, None),
                             ("Call", False, None, '1400-01-01'),
                             ("Call", False, '1403-01-01', None),
                             ("Put", True, str(jd.date.today() - jd.timedelta(days=10)), str(jd.date.today())),
                             ("Put", True, str(jd.date.today() - jd.timedelta(days=10)),
                              str(jd.date.today() + jd.timedelta(days=10))),
                             ("Put", True, None, None),
                             ("Put", False, str(jd.date.today() - jd.timedelta(days=10)), str(jd.date.today())),
                             ("Put", False, '1404-01-01', '1404-02-01'),
                             ("Put", False, '1404-01-01', str(jd.date.today() + jd.timedelta(days=10))),
                             ("Put", False, None, None),
                             ("Put", False, None, '1400-01-01'),
                             ("Put", False, '1403-01-01', None),
                         ])
def test_get_all_ime_option_trades(option_type, only_active, start_date, end_date):
    all_ime_option_trades = get_all_ime_option_trades(option_type, only_active, start_date, end_date)
    assert isinstance(all_ime_option_trades, pd.DataFrame)
    assert all_ime_option_trades is not None
    assert not all_ime_option_trades.empty
    assert all(column in all_ime_option_trades.columns for column in
               ['ID', 'ContractID', 'ContractCode', 'ContractDescription', 'IsActive', 'TradesVolume', 'TradesValue',
                'MaxPrice', 'MinPrice', 'LastPrice', 'FirstPrice', 'OpenInterest', 'ChangeOpenInterest',
                'ActiveCustomers', 'ActiveBrokers', 'CBuy', 'CSell', 'InstitutionalBuyVolume', 'InstitutionalBuyValue',
                'InstitutionalSellVolume', 'InstitutionalSellValue', 'RetailBuyVolume', 'RetailBuyValue',
                'RetailSellVolume', 'RetailSellValue', 'LastSettlementPrice', 'TodaySettlementPrice',
                'SettlementPricePercent', 'Date', 'GDate', 'DeliveryDate', 'CreateDateTime'])

    if start_date is not None:
        start_jd = jd.date(int(start_date[:4]), int(start_date[5:7]), int(start_date[8:]))
    else:
        start_jd = jd.date(1395, 1, 1)

    if end_date is not None:
        end_jd = jd.date(int(end_date[:4]), int(end_date[5:7]), int(end_date[8:]))
    else:
        end_jd = jd.date.today()

    assert all(start_jd <= date_column <= end_jd for date_column in all_ime_option_trades['Date'] if pd.notna(date_column))



def test_get_all_physical_producer_products():
    all_producer_products = get_all_physical_producer_products()
    assert isinstance(all_producer_products, pd.DataFrame)
    assert all_producer_products is not None
    assert not all_producer_products.empty
    assert all(column in all_producer_products.columns for column in ['Producer', 'Products'])



@pytest.mark.parametrize(["producer", "start_date", "end_date"],
                         [('ذوب آهن اصفهان', '1402-01-01', '1403-01-01'),
                          ('ذوب آهن اصفهان', None, None),
                          ('ذوب آهن اصفهان', '1403-01-01', None),
                          ('ذوب آهن اصفهان', None, '1403-01-01')])
def test_get_producer_physical_trades(producer, start_date, end_date):
    producer_physical_trades = get_producer_physical_trades(producer, start_date, end_date)
    assert isinstance(producer_physical_trades, pd.DataFrame)
    assert producer_physical_trades is not None
    assert not producer_physical_trades.empty
    assert all(column in producer_physical_trades.columns for column in
               ['GoodsName', 'Symbol', 'ProducerName', 'ContractType', 'MinPrice', 'ClosePrice', 'MaxPrice',
                'SupplyVolume', 'SupplyBasePrice', 'SupplyMinPrice', 'Demand', 'DemandMaxPrice', 'ContractSize',
                'TransactionValue', 'Date', 'DeliveryDate', 'Warehouse', 'Supplier', 'SettlementDate', 'Broker',
                'SupplyType', 'BuyType', 'Currency', 'Unit', 'ExchangeHall', 'PacketType', 'Settlement'])

    if start_date is not None:
        start_jd = jd.date(int(start_date[:4]), int(start_date[5:7]), int(start_date[8:]))
    else:
        start_jd = jd.date(1300, 1, 1)
    if end_date is not None:
        end_jd = jd.date(int(end_date[:4]), int(end_date[5:7]), int(end_date[8:]))
    else:
        end_jd = jd.date.today()
    assert all(start_jd <= date_column <= end_jd for date_column in producer_physical_trades['Date'] if pd.notna(date_column))



@pytest.mark.parametrize(["start_date", "end_date"], [('1400-01-01', '1400-12-29'),
                                                      ('1404-01-01', str(jd.date.today() + jd.timedelta(days=10))),
                                                      (None, None), (None, '1400-12-29'), ('1400-12-29', None)])
def test_get_all_ime_export_trades(start_date, end_date):
    all_ime_export_trades = get_all_ime_export_trades(start_date, end_date)
    assert all_ime_export_trades is not None
    assert not all_ime_export_trades.empty
    assert isinstance(all_ime_export_trades, pd.DataFrame)
    assert all(column in all_ime_export_trades.columns for column in
               ['BrokerName', 'ID', 'GoodsName', 'Symbol', 'ProducerName', 'ContractType', 'DeliveryDate', 'MinPrice',
                'Price', 'MaxPrice', 'Supply', 'BasePrice', 'SupplyMinPrice', 'Demand', 'DemandMaxPrice', 'Quantity',
                'TotalPrice', 'BasketDetail', 'GroupName', 'SubGroupName', 'Warehouse', 'Date', 'MainGroupName',
                'SupplyBasePrice', 'Supplier', 'RingName', 'SupplyType', 'BuyType', 'FXRate', 'Currency', 'Unit',
                'ExchangeHall'])

    if start_date is not None:
        start_jd = jd.date(int(start_date[:4]), int(start_date[5:7]), int(start_date[8:]))
    else:
        start_jd = jd.date(1387, 12, 1)

    if end_date is not None:
        end_jd = jd.date(int(end_date[:4]), int(end_date[5:7]), int(end_date[8:]))
    else:
        end_jd = jd.date.today()
    assert all(start_jd <= date_column <= end_jd for date_column in all_ime_export_trades['Date'] if pd.notna(date_column))



@pytest.mark.parametrize(["start_date", "end_date"], [('1400-01-01', '1400-12-29'),
                                                      ('1404-01-01', str(jd.date.today() + jd.timedelta(days=10))),
                                                      (None, None), (None, '1400-12-29'), ('1400-12-29', None)])
def test_get_all_ime_cd_trades(start_date, end_date):
    all_ime_cd_trades = get_all_ime_cd_trades(start_date, end_date)
    assert all_ime_cd_trades is not None
    assert not all_ime_cd_trades.empty
    assert isinstance(all_ime_cd_trades, pd.DataFrame)
    assert all(column in all_ime_cd_trades.columns for column in
               ['ID', 'Code', 'Symbol', 'Date', 'Description', 'ClosePrice', 'LastPrice', 'TotalTransitions', 'Volume',
                'Value', 'MinPrice', 'MaxPrice', 'YesterdayPrice', 'LastPriceChange', 'LastPricePercentageChange',
                'ClosePriceChangePrice', 'ClosePricePercentageChange', 'GDate'])

    if start_date is not None:
        start_jd = jd.date(int(start_date[:4]), int(start_date[5:7]), int(start_date[8:]))
    else:
        start_jd = jd.date(1394, 3, 1)

    if end_date is not None:
        end_jd = jd.date(int(end_date[:4]), int(end_date[5:7]), int(end_date[8:]))
    else:
        end_jd = jd.date.today()
    assert all(start_jd <= date_column <= end_jd for date_column in all_ime_cd_trades['Date'] if pd.notna(date_column))



def test_get_all_export_producer_products():
    all_producer_products = get_all_export_producer_products()
    assert isinstance(all_producer_products, pd.DataFrame)
    assert all_producer_products is not None
    assert not all_producer_products.empty
    assert all(column in all_producer_products.columns for column in ['Producer', 'Products'])



@pytest.mark.parametrize(["producer", "start_date", "end_date"],
                         [('ملی صنایع مس ایران', '1402-01-01', '1403-01-01'),
                          ('ملی صنایع مس ایران', None, None),
                          ('ملی صنایع مس ایران', '1403-01-01', None),
                          ('ملی صنایع مس ایران', None, '1403-01-01')])
def test_get_producer_export_trades(producer, start_date, end_date):
    producer_export_trades = get_producer_export_trades(producer, start_date, end_date)
    assert isinstance(producer_export_trades, pd.DataFrame)
    assert producer_export_trades is not None
    assert not producer_export_trades.empty
    assert all(column in producer_export_trades.columns for column in
               ['BrokerName', 'ID', 'GoodsName', 'Symbol', 'ProducerName', 'ContractType', 'DeliveryDate', 'MinPrice',
                'Price', 'MaxPrice', 'Supply', 'BasePrice', 'SupplyMinPrice', 'Demand', 'DemandMaxPrice', 'Quantity',
                'TotalPrice', 'BasketDetail', 'GroupName', 'SubGroupName', 'Warehouse', 'Date', 'MainGroupName',
                'SupplyBasePrice', 'Supplier', 'RingName', 'SupplyType', 'BuyType', 'FXRate', 'Currency', 'Unit',
                'ExchangeHall'])

    if start_date is not None:
        start_jd = jd.date(int(start_date[:4]), int(start_date[5:7]), int(start_date[8:]))
    else:
        start_jd = jd.date(1300, 1, 1)

    if end_date is not None:
        end_jd = jd.date(int(end_date[:4]), int(end_date[5:7]), int(end_date[8:]))
    else:
        end_jd = jd.date.today()
    assert all(start_jd <= date_column <= end_jd for date_column in producer_export_trades['Date'] if pd.notna(date_column))



@pytest.mark.parametrize(["start_date", "end_date"], [('1400-01-01', '1400-12-29'),
                                                      ('1404-01-01', str(jd.date.today() + jd.timedelta(days=10))),
                                                      (None, None), (None, '1400-12-29'), ('1400-12-29', None)])
def test_get_all_ime_salaf_trades(start_date, end_date):
    all_ime_salaf_trades = get_all_ime_salaf_trades(start_date, end_date)
    assert all_ime_salaf_trades is not None
    assert not all_ime_salaf_trades.empty
    assert isinstance(all_ime_salaf_trades, pd.DataFrame)
    assert all(column in all_ime_salaf_trades.columns for column in
               ['ID', 'Code', 'Symbol', 'Date', 'Description', 'ClosePrice', 'LastPrice', 'TotalTransitions', 'Volume',
                'Value', 'MinPrice', 'MaxPrice', 'YesterdayPrice', 'LastPriceChange', 'LastPricePercentageChange',
                'ClosePriceChangePrice', 'ClosePricePercentageChange', 'GDate'])

    if start_date is not None:
        start_jd = jd.date(int(start_date[:4]), int(start_date[5:7]), int(start_date[8:]))
    else:
        start_jd = jd.date(1393, 5, 1)

    if end_date is not None:
        end_jd = jd.date(int(end_date[:4]), int(end_date[5:7]), int(end_date[8:]))
    else:
        end_jd = jd.date.today()
    assert all(start_jd <= date_column <= end_jd for date_column in all_ime_salaf_trades['Date'] if pd.notna(date_column))



@pytest.mark.parametrize(["contract_type", "start_date", "end_date"],
                         [('gold_bar_cd', '1403-01-01', '1403-12-29'),
                          ('silver_bar_cd', '1403-01-01', '1403-12-29'),
                          ('gold_coin_cd', '1403-01-01', '1403-12-29'),
                          ('gold_bar_cd', None, '1403-12-29'),
                          ('silver_bar_cd', None, '1403-12-29'),
                          ('gold_coin_cd', None, '1403-12-29'),
                          ('gold_bar_cd', '1403-01-01', None),
                          ('silver_bar_cd', '1403-01-01', None),
                          ('gold_coin_cd', '1403-01-01', None),
                          ('gold_bar_cd', None, None),
                          ('silver_bar_cd', None, None),
                          ('gold_coin_cd', None, None)])
def test_get_gold_and_silver_cd_trades(contract_type, start_date, end_date):
    gold_and_silver_cd_trades = get_gold_and_silver_cd_trades(contract_type, start_date, end_date)
    assert gold_and_silver_cd_trades is not None
    assert not gold_and_silver_cd_trades.empty
    assert isinstance(gold_and_silver_cd_trades, pd.DataFrame)
    assert all(column in gold_and_silver_cd_trades.columns for column in
               ['ContractID', 'ContractCode', 'ContractDescription', 'TradesVolume', 'TradesValue', 'MaxPrice',
                'MinPrice', 'LastPrice', 'FirstPrice', 'OpenInterest', 'OpenInterestChange', 'ActiveCustomers',
                'ActiveBrokers', 'CBuy', 'CSell', 'InstitutionalBuyVolume', 'InstitutionalBuyValue',
                'InstitutionalSellVolume', 'InstitutionalSellValue', 'RetailBuyVolume', 'RetailBuyValue',
                'RetailSellVolume', 'RetailSellValue', 'LastSettlementPrice', 'TodaySettlementPrice',
                'SettlementPricePercent', 'GDate', 'JDate', 'DeliveryGDate', 'DeliveryJDate'])

    if start_date is not None:
        start_jd = jd.date(int(start_date[:4]), int(start_date[5:7]), int(start_date[8:]))
    else:
        start_jd = jd.date(1401, 12, 1)

    if end_date is not None:
        end_jd = jd.date(int(end_date[:4]), int(end_date[5:7]), int(end_date[8:]))
    else:
        end_jd = jd.date.today()
    assert all(start_jd <= date_column <= end_jd for date_column in gold_and_silver_cd_trades['JDate'] if pd.notna(date_column))
