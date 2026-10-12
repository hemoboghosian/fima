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

    market_makers = all_funds[all_funds["FundType"] == "اختصاصی بازارگردانی"]
    if not market_makers.empty:
        assert "GroupId" in market_makers.columns
        assert market_makers["GroupId"].isin([0, 1]).all()


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


def test_pikad_nav_parser_live(monkeypatch):
    # Resolve the known fund locally so Fipiran downtime does not mask this API check.
    monkeypatch.setattr(Funds, "_get_fund_website_address", lambda _: "servatfund.ir")
    df = Funds._get_daily_navs_pikad("ثروت آفرین تمدن")
    _assert_nav_dataframe(df)


@pytest.fixture
def current_rayan_fund(monkeypatch):
    # This identity was verified in Fipiran; provider HTTP responses remain live.
    name = "مشترک عقیق"
    metadata = pd.DataFrame([{"Name": name, "WebsiteAddress": "aghighfund.com", "FundType": "در سهام"}])
    monkeypatch.setattr(Funds, "get_all_funds", lambda **kwargs: metadata.copy())
    return name


def test_get_daily_navs_current_rayan_live(current_rayan_fund):
    _assert_nav_dataframe(Funds.get_daily_navs(current_rayan_fund))


def test_get_daily_asset_allocation_current_rayan_live(current_rayan_fund):
    df = Funds.get_daily_asset_allocation(current_rayan_fund)
    _assert_asset_allocation_dataframe(df)
    assert {"Stocks", "Upper5%Stocks", "Bonds", "Cash", "Bank", "FundUnits", "CCDs", "OtherAssets"}.issubset(df.columns)
