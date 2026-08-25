import pandas as pd
import pytest

import fima.Funds as Funds


pytestmark = pytest.mark.integration


def test_get_all_funds_live():
    df = Funds.get_all_funds(_set_website_developers=False)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    required_columns = [
        "Name",
        "WebsiteAddress",
        "FundType",
        "InvestmentType",
        "TotalNAV",
        "UpdateDate",
    ]

    for column in required_columns:
        assert column in df.columns