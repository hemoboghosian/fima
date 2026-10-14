import inspect

import fima
import fima.Funds as Funds


PUBLIC_NAMES = {"get_all_funds", "get_daily_navs", "get_daily_asset_allocation",
                "get_tsetmc_funds", "get_tsetmc_fund_details"}


def test_wildcard_imports_only_public_funds_functions():
    namespace = {}
    exec("from fima.Funds import *", namespace)
    assert set(namespace) - {"__builtins__"} == PUBLIC_NAMES


def test_module_discovery_only_lists_public_funds_functions():
    assert dir(Funds) == sorted(PUBLIC_NAMES)


def test_explicit_public_imports_remain_compatible():
    for name in PUBLIC_NAMES:
        assert getattr(fima, name) is getattr(Funds, name)
        assert callable(getattr(Funds, name))


def test_internal_helpers_remain_accessible_explicitly():
    from fima.Funds import _normalize_website_host

    assert _normalize_website_host("https://fund.example/path") == "fund.example"


def test_legacy_internal_parameter_keeps_its_real_signature():
    signature = inspect.signature(Funds.get_all_funds)
    assert list(signature.parameters) == ["_set_website_developers"]
    assert signature.parameters["_set_website_developers"].default is False
    assert signature.parameters["_set_website_developers"].annotation is bool
