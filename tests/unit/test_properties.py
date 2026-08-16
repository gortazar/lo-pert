"""Invariants over randomly generated acyclic precedence tables.

Fixed examples check the cases someone thought of; these check the ones nobody did.
The properties are the contract in the plan: a topological numbering, E <= L
everywhere, the project duration equal to the longest path through the original
activities, and — the one that keeps dummies honest — the network implying exactly
the transitive closure of the stated precedences, no more and no less.
"""

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from lopert.network import build_network
from lopert.table import Activity
from lopert.times import compute_times

IDS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@st.composite
def precedence_tables(draw, max_activities=8):
    """Acyclic tables: activity i may only depend on activities before it."""
    count = draw(st.integers(min_value=1, max_value=max_activities))
    activities = []
    for index in range(count):
        predecessors = draw(
            st.lists(
                st.sampled_from(IDS[:index] or "-"),
                max_size=index,
                unique=True,
            )
            if index
            else st.just([])
        )
        duration = draw(
            st.one_of(
                st.integers(min_value=0, max_value=20).map(float),
                st.floats(min_value=0, max_value=20, allow_nan=False, allow_infinity=False),
            )
        )
        activities.append(
            Activity(IDS[index], duration, tuple(predecessors), index + 1)
        )
    return activities


def transitive_closure(activities):
    """identifier -> every activity that must finish before it starts."""
    closure = {}
    for activity in activities:
        needed = set()
        for predecessor in activity.predecessors:
            needed.add(predecessor)
            needed |= closure[predecessor]
        closure[activity.id] = needed
    return closure


def reachable_from(network, start):
    seen = {start}
    frontier = [start]
    while frontier:
        event = frontier.pop()
        for arc in network.arcs_out_of(event):
            if arc.head not in seen:
                seen.add(arc.head)
                frontier.append(arc.head)
    return seen


def longest_path(activities):
    finish = {}
    for activity in activities:
        start = max((finish[p] for p in activity.predecessors), default=0.0)
        finish[activity.id] = start + activity.duration
    return max(finish.values(), default=0.0)


SETTINGS = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


@given(precedence_tables())
@SETTINGS
def test_every_arc_runs_low_to_high(activities):
    network = build_network(activities)

    assert all(arc.tail < arc.head for arc in network.arcs)
    assert network.start == min(network.events)
    assert network.finish == max(network.events)


@given(precedence_tables())
@SETTINGS
def test_early_never_exceeds_late(activities):
    network = build_network(activities)
    times = compute_times(network)

    for event in network.events:
        assert times.early[event] <= times.late[event] + 1e-9


@given(precedence_tables())
@SETTINGS
def test_project_duration_is_the_longest_path(activities):
    network = build_network(activities)
    times = compute_times(network)

    # Both sides add the same durations in a different order, so compare with a
    # tolerance rather than making CI depend on float associativity.
    assert times.duration == pytest.approx(longest_path(activities))


@given(precedence_tables())
@SETTINGS
def test_the_network_implies_exactly_the_stated_precedences(activities):
    network = build_network(activities)
    closure = transitive_closure(activities)
    downstream = {
        activity.id: reachable_from(network, network.activity_arc(activity.id).head)
        for activity in activities
    }

    for activity in activities:
        tail = network.activity_arc(activity.id).tail
        implied = {
            other.id
            for other in activities
            if other.id != activity.id and tail in downstream[other.id]
        }
        assert closure[activity.id] <= implied, "a stated precedence was lost"
        assert implied <= closure[activity.id], "a precedence was invented"


@given(precedence_tables())
@SETTINGS
def test_construction_is_deterministic(activities):
    assert build_network(activities) == build_network(activities)


@given(precedence_tables())
@SETTINGS
def test_dummies_have_no_duration(activities):
    network = build_network(activities)

    assert all(arc.duration == 0.0 for arc in network.arcs if arc.dummy)


@given(precedence_tables())
@SETTINGS
def test_every_activity_appears_exactly_once(activities):
    network = build_network(activities)

    drawn = [arc.activity for arc in network.arcs if not arc.dummy]
    assert sorted(drawn) == sorted(activity.id for activity in activities)


@given(precedence_tables())
@SETTINGS
def test_every_event_lies_between_start_and_finish(activities):
    network = build_network(activities)
    reachable = reachable_from(network, network.start)

    assert set(network.events) == reachable
    for event in network.events:
        assert network.finish in reachable_from(network, event)
