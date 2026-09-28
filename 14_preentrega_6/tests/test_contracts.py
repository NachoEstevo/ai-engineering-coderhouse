import pytest
from pydantic import ValidationError

from state import AnalysisRequest, SampleGroup
from tools.statistics_tool import compute_statistics


@pytest.mark.parametrize(
    "values",
    [
        [],
        [1],
        [True, 2],
        ["1", 2],
        [float("nan"), 2],
        [float("inf"), 2],
        [10**1000, 2],
        [1e13, 2],
    ],
)
def test_invalid_values(values):
    with pytest.raises(ValidationError):
        SampleGroup(name="A", unit="ms", values=values)


def test_statistics_known_values():
    groups = [SampleGroup(name="A", unit="ms", values=[100, 110, 90, 100, 100])]
    result = compute_statistics(groups)
    assert result[0].mean == 100
    assert result[0].median == 100
    assert result[0].stdev == pytest.approx(50**0.5)


def test_units_and_duplicate_names():
    a = SampleGroup(name="A", unit="ms", values=[1, 2])
    for b in [SampleGroup(name="B", unit="s", values=[1, 2]), a]:
        with pytest.raises(ValidationError):
            AnalysisRequest(query="compare", groups=[a, b])


def test_missing_groups_are_valid_request():
    assert AnalysisRequest(query=" compare ", groups=[]).query == "compare"


@pytest.mark.parametrize("name,unit", [("", "ms"), (" ", "ms"), ("A", ""), ("A", " ")])
def test_group_requires_name_and_explicit_unit(name, unit):
    with pytest.raises(ValidationError):
        SampleGroup(name=name, unit=unit, values=[1, 2])


def test_group_size_query_and_group_count_limits():
    with pytest.raises(ValidationError):
        SampleGroup(name="A", unit="ms", values=[1] * 1001)
    with pytest.raises(ValidationError):
        AnalysisRequest(query="x" * 8001, groups=[])
    with pytest.raises(ValidationError):
        AnalysisRequest(
            query="compare",
            groups=[
                SampleGroup(name=str(i), unit="ms", values=[1, 2]) for i in range(3)
            ],
        )
