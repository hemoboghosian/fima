import pytest
from fima.TSEInstitutions import get_all_institutions


def test_get_all_institutions():
    all_institutions = get_all_institutions()
    assert all_institutions is not None
    assert not all_institutions.empty
    for column in ['InstituteType', 'InstituteKind', 'SEORegisterNo', 'Website', 'Name', 'NationalId', 'CEO',
                   'CEOMobileNo', 'State', 'AminName', 'Status']:
        assert column in all_institutions.columns

