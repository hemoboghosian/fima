import pandas as pd
import requests


def get_indexes_status() -> pd.DataFrame:
    tse_url = "https://cdn.tsetmc.com/api/Index/GetIndexB1LastAll/SelectedIndexes/1"
    tse_idnexes_info = requests.get(tse_url).json()['indexB1']

    ifb_url = "https://cdn.tsetmc.com/api/Index/GetIndexB1LastAll/SelectedIndexes/2"
    ifb_indexes_info = requests.get(ifb_url).json()['indexB1']

    indexes_info = tse_idnexes_info + ifb_indexes_info
    indexes_info = pd.DataFrame(indexes_info)
    indexes_info.rename(columns={'insCode': 'InstrumentCode', 'hEven': 'HourMinute', 'xDrNivJIdx004': 'Value',
                                 'xPhNivJIdx004': 'MinValue', 'xPbNivJIdx004': 'MaxValue', 'xVarIdxJRfV': 'PercentageChange',
                                 'indexChange': 'Change', 'lVal30': 'Index'}, inplace=True)
    indexes_info.drop(['dEven', 'c1', 'c2', 'c3', 'c4', 'last'], inplace=True, axis=1)
    return indexes_info


IndexesStatus = get_indexes_status()
