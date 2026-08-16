from lopert.network import build_network
from lopert.table import parse_table
from lopert.times import compute_times

# The example worked by hand in the README: critical path A -> D -> E, 12 days.
WORKED_EXAMPLE = [
    ["A", "3", ""],
    ["B", "4", ""],
    ["C", "2", "A"],
    ["D", "5", "A"],
    ["E", "4", "C D"],
    ["F", "3", "B"],
]


def times_for(rows):
    network = build_network(parse_table(rows))
    return network, compute_times(network)


def test_a_chain_adds_up():
    network, times = times_for([["A", "2", ""], ["B", "3", "A"], ["C", "4", "B"]])

    assert times.early[network.start] == 0
    assert times.duration == 9
    assert times.early[network.finish] == 9
    assert times.late[network.finish] == 9


def test_the_late_time_of_the_start_event_is_zero():
    network, times = times_for(WORKED_EXAMPLE)

    assert times.late[network.start] == 0


def test_parallel_branches_take_the_longer_one():
    network, times = times_for([["A", "2", ""], ["B", "5", ""]])

    assert times.duration == 5


def test_the_worked_example_has_the_expected_duration_and_critical_path():
    _network, times = times_for(WORKED_EXAMPLE)

    assert times.duration == 12
    assert set(times.critical_activities) == {"A", "D", "E"}


def test_floats_of_the_worked_example():
    _network, times = times_for(WORKED_EXAMPLE)

    assert times.total_float["A"] == 0
    assert times.total_float["D"] == 0
    assert times.total_float["E"] == 0
    # C can slip three days: A ends at 3, E starts at 8, and C takes 2.
    assert times.total_float["C"] == 3
    # B and F have five days of slack between them.
    assert times.total_float["B"] == 5
    assert times.total_float["F"] == 5


def test_early_never_exceeds_late():
    network, times = times_for(WORKED_EXAMPLE)

    for event in network.events:
        assert times.early[event] <= times.late[event]


def test_events_on_the_critical_path_have_no_slack():
    network, times = times_for(WORKED_EXAMPLE)

    assert times.is_critical_event(network.start)
    assert times.is_critical_event(network.finish)
    assert times.slack(network.finish) == 0


def test_a_dummy_can_be_critical():
    # B waits for A; C waits for A and B. The dummy joining A's end to C's start
    # carries the critical path.
    network, times = times_for(
        [["A", "3", ""], ["B", "2", ""], ["C", "4", "A B"], ["D", "1", "A"]]
    )

    assert times.duration == 7
    assert set(times.critical_activities) == {"A", "C"}
    assert any(arc.dummy for arc in times.critical_arcs)


def test_a_zero_duration_activity_is_allowed():
    _network, times = times_for([["A", "0", ""], ["B", "2", "A"]])

    assert times.duration == 2
    assert times.total_float["A"] == 0


def test_fractional_durations():
    _network, times = times_for([["A", "1.5", ""], ["B", "2.25", "A"]])

    assert times.duration == 3.75


def test_the_critical_path_is_the_longest_path():
    rows = [
        ["A", "2", ""],
        ["B", "3", ""],
        ["C", "1", "A"],
        ["D", "4", "A B"],
        ["E", "2", "C D"],
        ["F", "3", "B"],
    ]
    _network, times = times_for(rows)

    # Longest path over the original activities, computed independently.
    durations = {row[0]: float(row[1]) for row in rows}
    predecessors = {row[0]: row[2].split() for row in rows}
    finish = {}
    for identifier in ("A", "B", "C", "D", "E", "F"):
        start = max(
            (finish[p] for p in predecessors[identifier]), default=0.0
        )
        finish[identifier] = start + durations[identifier]

    assert times.duration == max(finish.values())
