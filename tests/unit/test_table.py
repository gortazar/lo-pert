import pytest

from lopert.table import (
    Activity,
    TableValidationError,
    looks_like_header,
    parse_table,
    split_predecessors,
)


def test_parses_a_minimal_table():
    activities = parse_table([["A", "3", ""], ["B", "2", "A"]])

    assert activities == [
        Activity("A", 3.0, (), 1),
        Activity("B", 2.0, ("A",), 2),
    ]


def test_skips_a_header_row():
    activities = parse_table(
        [["Activity", "Duration", "Predecessors"], ["A", "3", "-"]]
    )

    assert [a.id for a in activities] == ["A"]
    # Row numbers count the header, because that is what Calc shows.
    assert activities[0].row == 2


def test_keeps_a_first_row_that_is_an_activity():
    activities = parse_table([["A", "3", ""], ["B", "1", "A"]])

    assert activities[0].id == "A"


def test_skips_blank_rows():
    activities = parse_table([["A", "3", ""], ["", "", ""], ["B", "1", "A"]])

    assert [a.id for a in activities] == ["A", "B"]
    assert activities[1].row == 3


def test_accepts_numeric_cells_from_calc():
    activities = parse_table([["A", 3.0, ""], [2.0, 1.5, "A"]])

    assert activities[0].duration == 3.0
    # An id typed as a number comes back from Calc as a float; "2.0" would be wrong.
    assert activities[1].id == "2"
    assert activities[1].duration == 1.5


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", ()),
        ("-", ()),
        ("none", ()),
        ("A", ("A",)),
        ("A,B", ("A", "B")),
        ("A, B", ("A", "B")),
        ("A B", ("A", "B")),
        ("A; B|C/D", ("A", "B", "C", "D")),
    ],
)
def test_split_predecessors(text, expected):
    assert split_predecessors(text) == expected


def test_comma_decimal_separator_is_a_duration():
    activities = parse_table([["A", "3,5", ""]])

    assert activities[0].duration == 3.5


def test_looks_like_header():
    assert looks_like_header(["Activity", "Duration", "Predecessors"])
    assert not looks_like_header(["A", "3", ""])
    assert not looks_like_header(["A"])


def _errors(rows):
    with pytest.raises(TableValidationError) as raised:
        parse_table(rows)
    return [str(error) for error in raised.value.errors]


def test_rejects_an_empty_table():
    assert _errors([]) == ["the precedence table is empty"]
    assert _errors([["", "", ""]]) == ["the precedence table is empty"]


def test_rejects_a_duplicate_activity_naming_both_rows():
    errors = _errors([["A", "3", ""], ["A", "2", ""]])

    assert errors == ["row 2: activity 'A' is already defined on row 1"]


def test_rejects_an_unknown_predecessor():
    errors = _errors([["A", "3", ""], ["B", "2", "Z"]])

    assert errors == ["row 2: activity 'B' lists unknown predecessor 'Z'"]


def test_rejects_a_non_numeric_duration():
    errors = _errors([["A", "three", ""]])

    assert errors == ["row 1: duration 'three' of activity 'A' is not a number"]


def test_rejects_a_negative_duration():
    errors = _errors([["A", "-1", ""]])

    assert errors == ["row 1: duration of activity 'A' is negative"]


def test_rejects_a_missing_duration():
    errors = _errors([["A", "", ""]])

    assert errors == ["row 1: activity 'A' has no duration"]


def test_rejects_a_missing_identifier():
    errors = _errors([["", "3", ""]])

    assert errors == ["row 1: activity has no identifier"]


def test_reports_every_problem_at_once():
    errors = _errors([["A", "x", ""], ["B", "-2", ""], ["C", "1", "Z"]])

    assert len(errors) == 3


def test_rejects_a_self_predecessor():
    errors = _errors([["A", "3", "A"]])

    assert errors == ["row 1: activity 'A' is its own predecessor"]


def test_rejects_a_cycle_naming_the_chain():
    errors = _errors([["A", "1", "C"], ["B", "1", "A"], ["C", "1", "B"]])

    assert errors == ["row 1: circular precedence: A -> B -> C -> A"]


def test_unknown_predecessor_does_not_also_report_a_bogus_cycle():
    errors = _errors([["A", "1", "Z"]])

    assert errors == ["row 1: activity 'A' lists unknown predecessor 'Z'"]
