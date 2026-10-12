import json

import pandas as pd
import pytest
import requests

import fima.Funds as Funds


def _row(name, reg_no, fund_type=6, group_id=0):
    return {
        "regNo": reg_no, "groupId": group_id, "name": name,
        "fundType": fund_type, "typeOfInvest": "Negotiable",
        "fundSize": 100, "initiationDate": "2020-01-01",
        "date": "2026-10-12", "websiteAddress": ["fund.example"],
    }


def _mock_provider(monkeypatch, rows):
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        items = rows if url.endswith("fundcompare") else [
            {"fundType": value, "name": name, "isActive": True}
            for value, name in [(6, "Equity"), (11, "Marketmaker"),
                                (21, "Sector"), (4, "Fixed income"), (5, "Commodity")]
        ]
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response._content = json.dumps({"status": 200, "items": items}).encode()
        return response

    monkeypatch.setattr(Funds, "_request", request)
    return calls


def test_catalog_excludes_instruments_but_preserves_funds_and_compartments(monkeypatch):
    # Instrument rows deliberately precede their parent: deduplication is unsafe.
    rows = [
        _row("Sukuk instrument", "MM-A", 11, 13),
        _row("Stock instrument", "MM-B", 11, 7),
        _row("CD instrument", "MM-A", 11, 2),
        _row("Marketmaker A", "MM-A", 11, 0),
        _row("Marketmaker B", "MM-B", 11, 1),
        _row("Equity fund", "E", 6, 2),
        _row("Sector compartment", "S", 21, 2),
        _row("Sector fund", "S", 21, 1),
        _row("Bond fund", "B", 4),
        _row("Commodity CD fund", "C", 5),
    ]
    calls = _mock_provider(monkeypatch, rows)
    result = Funds.get_all_funds(_set_website_developers=False)
    assert result["Name"].tolist() == [row["name"] for row in rows[3:]]
    assert result["RegNo"].tolist() == [row["regNo"] for row in rows[3:]]
    assert result["TotalNAV"].tolist() == [100] * 7
    assert result["WebsiteAddress"].tolist() == ["fund.example"] * 7
    assert result.index.equals(pd.RangeIndex(7))
    assert calls[0][2]["json"] == {"regNos": [], "showMarketMakers": True}


@pytest.mark.parametrize("group_id", [None, "instrument", 0.5, -1, True])
def test_catalog_rejects_invalid_marketmaker_group(monkeypatch, group_id):
    _mock_provider(monkeypatch, [_row("Marketmaker", "MM", 11, group_id)])
    with pytest.raises(ValueError, match="Fipiran.*groupId"):
        Funds.get_all_funds()


@pytest.mark.parametrize("include_ordinary_fund", [False, True])
def test_catalog_requires_marketmaker_group_identifiers(monkeypatch, include_ordinary_fund):
    marketmaker = _row("Marketmaker", "MM", 11)
    del marketmaker["groupId"]
    rows = [marketmaker]
    if include_ordinary_fund:
        rows.append(_row("Equity fund", "E"))
    _mock_provider(monkeypatch, rows)
    with pytest.raises(ValueError, match="Fipiran.*groupId"):
        Funds.get_all_funds()


def test_catalog_without_fund_level_rows_is_an_error(monkeypatch):
    _mock_provider(monkeypatch, [_row("Sukuk instrument", "MM", 11, 3)])
    with pytest.raises(ValueError, match="Fipiran.*fund-level"):
        Funds.get_all_funds()


def test_catalog_without_marketmakers_does_not_require_group_id(monkeypatch):
    row = _row("Equity fund", "E")
    del row["groupId"]
    _mock_provider(monkeypatch, [row])
    assert Funds.get_all_funds()["Name"].tolist() == ["Equity fund"]


def test_optional_website_discovery_only_receives_funds(monkeypatch):
    _mock_provider(monkeypatch, [
        _row("Sukuk instrument", "MM", 11, 3),
        _row("Marketmaker", "MM", 11, 0),
    ])
    names = []

    def discover(frame):
        names.extend(frame["Name"])
        return frame.assign(WebsiteDeveloper="Known")

    monkeypatch.setattr(Funds, "_autoset_website_developers", discover)
    result = Funds.get_all_funds(_set_website_developers=True)
    assert names == ["Marketmaker"]
    assert result["WebsiteDeveloper"].tolist() == ["Known"]
