import pytest
import pandas as pd
import jdatetime as jd
from fima.IME import get_all_ime_physical_trades


@pytest.mark.parametrize(["start_date", "end_date"], [('1400-01-01', '1401-12-29'),
                                                      ('1400-01-01', str(jd.date.today() + jd.timedelta(days=10))),
                                                      (None, None)])
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
