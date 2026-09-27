import pandas as pd
import pytest
import jdatetime as jd

import fima.Funds as Funds


pytestmark = pytest.mark.integration


NAV_COLUMNS = [
    "JDate",
    "Subscription",
    "Redemption",
    "Statistical",
    "TotalNAV",
]


@pytest.fixture(scope="session")
def all_funds():
    df = Funds.get_all_funds(_set_website_developers=False)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    return df


def _find_fund_name_by_website(
    all_funds: pd.DataFrame,
    website_fragment: str,
) -> str:
    matches = all_funds[
        all_funds["WebsiteAddress"]
        .astype(str)
        .str.contains(website_fragment, regex=False, na=False)
    ]

    if matches.empty:
        pytest.skip(
            f"No fund found with website containing: {website_fragment}"
        )

    return matches.iloc[0]["Name"]


def _assert_nav_dataframe(df: pd.DataFrame):
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert list(df.columns) == NAV_COLUMNS

    assert df["JDate"].map(
        lambda value: isinstance(value, jd.date)
    ).all()


def _assert_asset_allocation_dataframe(df: pd.DataFrame):
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "Date" in df.columns

    assert df["Date"].map(
        lambda value: isinstance(value, jd.date)
    ).all()


def test_get_all_funds_live(all_funds):
    required_columns = [
        "Name",
        "WebsiteAddress",
        "FundType",
        "InvestmentType",
        "TotalNAV",
        "UpdateDate",
    ]

    for column in required_columns:
        assert column in all_funds.columns


def test_rayan_nav_records_live():
    records = Funds._get_rayan_hamafza_nav_records(
        "emacofund.ir"
    )

    assert isinstance(records, list)
    assert len(records) > 0


def test_get_daily_navs_rayan_live(all_funds):
    fund_name = _find_fund_name_by_website(
        all_funds,
        "emacofund.ir",
    )

    df = Funds.get_daily_navs(fund_name)

    _assert_nav_dataframe(df)


def test_noavaran_nav_records_live():
    records = Funds._get_noavaran_nav_records(
        "sepordeh.ebidar.com"
    )

    assert isinstance(records, list)
    assert len(records) > 0


def test_get_daily_navs_noavaran_live(all_funds):
    fund_name = _find_fund_name_by_website(
        all_funds,
        "sepordeh.ebidar.com",
    )

    df = Funds.get_daily_navs(fund_name)

    _assert_nav_dataframe(df)


def test_get_daily_asset_allocation_noavaran_live(all_funds):
    fund_name = _find_fund_name_by_website(
        all_funds,
        "sepordeh.ebidar.com",
    )

    df = Funds.get_daily_asset_allocation(fund_name)

    _assert_asset_allocation_dataframe(df)

    expected_columns = [
        "Date",
        "Stocks",
        "Upper5%Stocks",
        "Bonds",
        "CDs",
        "PhysicalCDs",
        "Bank",
        "FundUnits",
        "OtherAssets",
    ]

    for column in expected_columns:
        assert column in df.columns