import pandas as pd
import pytest
import jdatetime as jd

import fima.Funds as Funds


def test_jalali_str_to_date_helper():
    assert Funds._jalali_str_to_date("1405/04/09") == jd.date(1405, 4, 9)
    assert Funds._jalali_str_to_date("1405-04-09") == jd.date(1405, 4, 9)
    assert Funds._jalali_str_to_date("14050409") == jd.date(1405, 4, 9)


def test_normalize_website_host_helper():
    assert Funds._normalize_website_host(
        "https://emacofund.ir/api/data/NAV/1"
    ) == "emacofund.ir"

    assert Funds._normalize_website_host("emacofund.ir") == "emacofund.ir"
    assert Funds._normalize_website_host(
        "aghighfund.com/home/index"
    ) == "aghighfund.com"

    assert Funds._normalize_website_host(None) is None


def test_build_base_urls_helper():
    urls = Funds._build_base_urls("emacofund.ir")

    assert "https://emacofund.ir" in urls
    assert "http://emacofund.ir" in urls


def test_get_fund_row_success():
    all_funds = pd.DataFrame(
        [
            {
                "Name": "Fund A",
                "WebsiteAddress": "funda.ir",
                "FundType": "Test Type",
            },
            {
                "Name": "Fund B",
                "WebsiteAddress": "fundb.ir",
                "FundType": "Test Type",
            },
        ]
    )

    row = Funds._get_fund_row("Fund A", all_funds)

    assert row["Name"] == "Fund A"
    assert row["WebsiteAddress"] == "funda.ir"


def test_get_fund_row_invalid_name_raises():
    all_funds = pd.DataFrame(
        [
            {
                "Name": "Fund A",
                "WebsiteAddress": "funda.ir",
                "FundType": "Test Type",
            }
        ]
    )

    with pytest.raises(ValueError):
        Funds._get_fund_row("__INVALID_FUND_NAME__", all_funds)


def test_get_daily_navs_invalid_fund_name_raises(monkeypatch):
    fake_funds = pd.DataFrame(
        [
            {
                "Name": "Fund A",
                "WebsiteAddress": "funda.ir",
                "FundType": "Test Type",
            }
        ]
    )

    monkeypatch.setattr(
        Funds,
        "get_all_funds",
        lambda _set_website_developers=False: fake_funds,
    )

    with pytest.raises(ValueError):
        Funds.get_daily_navs("__INVALID_FUND_NAME__")


def test_get_daily_asset_allocation_invalid_fund_name_raises(monkeypatch):
    fake_funds = pd.DataFrame(
        [
            {
                "Name": "Fund A",
                "WebsiteAddress": "funda.ir",
                "FundType": "Test Type",
            }
        ]
    )

    monkeypatch.setattr(
        Funds,
        "get_all_funds",
        lambda _set_website_developers=False: fake_funds,
    )

    with pytest.raises(ValueError):
        Funds.get_daily_asset_allocation("__INVALID_FUND_NAME__")
    