"""Olist scope checks that used to fail silently as empty charts (no CSVs needed)."""
from types import SimpleNamespace

import pytest
from jsonschema import ValidationError

from backend.data import SOURCE_SCHEMA, STATES, OlistData, normalize_source

CATALOG = SimpleNamespace(_catalog={"categories": ["bed_bath_table", "health_beauty", "watches_gifts"],
                                    "date_range": {"start": "2016-09-04", "end": "2018-10-18"}})


def check(**source):
    OlistData.check_scope(CATALOG, normalize_source(source))


def test_region_is_a_state_code_with_spoken_names_in_the_description():
    assert len(STATES) == 27 and None in SOURCE_SCHEMA["properties"]["region"]["enum"]
    assert "Minas Gerais = MG" in SOURCE_SCHEMA["properties"]["region"]["description"]
    for spoken in ("Minas Gerais", "mg", "Rio"):
        with pytest.raises(ValidationError):
            normalize_source({"region": spoken})
    assert normalize_source({"region": None})["region"] is None


def test_unknown_category_ids_are_rejected_with_the_closest_id():
    check(categories=["health_beauty"], top_n=None)
    with pytest.raises(ValueError, match=r"health and beauty \(closest: health_beauty\)"):
        check(categories=["health and beauty"], top_n=None)


@pytest.mark.parametrize("start,end", [("2019-01-01", "2020-01-01"), ("2015-01-01", "2016-01-01")])
def test_periods_without_any_olist_purchase_are_rejected(start, end):
    with pytest.raises(ValueError, match="the data covers 2016-09-04 to 2018-10-18"):
        check(start=start, end=end)
    check(start="2018-01-01", end="2019-01-01")
