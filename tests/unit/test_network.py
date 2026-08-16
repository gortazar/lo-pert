import pytest

from lopert.network import build_network
from lopert.table import parse_table


def network_for(rows):
    return build_network(parse_table(rows))


def reachable(network, start):
    """Every event reachable from `start` by following arcs."""
    seen = {start}
    frontier = [start]
    while frontier:
        event = frontier.pop()
        for arc in network.arcs_out_of(event):
            if arc.head not in seen:
                seen.add(arc.head)
                frontier.append(arc.head)
    return seen


def precedes(network, first, second):
    """Does the network force `first` to finish before `second` starts?"""
    first_arc = network.activity_arc(first)
    second_arc = network.activity_arc(second)
    return second_arc.tail in reachable(network, first_arc.head)


def test_a_single_activity_is_one_arc_from_start_to_finish():
    network = network_for([["A", "3", ""]])

    assert network.events == (1, 2)
    assert len(network.arcs) == 1
    arc = network.arcs[0]
    assert (arc.tail, arc.head) == (network.start, network.finish)
    assert arc.activity == "A"
    assert arc.duration == 3.0


def test_a_chain_needs_no_dummies():
    network = network_for([["A", "1", ""], ["B", "2", "A"], ["C", "3", "B"]])

    assert [arc.activity for arc in network.arcs] == ["A", "B", "C"]
    assert network.events == (1, 2, 3, 4)


def test_activities_sharing_predecessors_share_a_start_event():
    network = network_for(
        [
            ["A", "1", ""],
            ["B", "2", "A"],
            ["C", "3", "A"],
            ["D", "1", "B"],
            ["E", "1", "C"],
        ]
    )

    assert network.activity_arc("B").tail == network.activity_arc("C").tail
    assert not any(arc.dummy for arc in network.arcs)


def test_parallel_openers_share_the_start_event():
    network = network_for([["A", "1", ""], ["B", "2", ""], ["C", "3", "A B"]])

    assert network.activity_arc("A").tail == network.start
    assert network.activity_arc("B").tail == network.start


def test_a_diamond_closes_on_the_finish_event():
    network = network_for(
        [["A", "1", ""], ["B", "2", "A"], ["C", "3", "A"], ["D", "4", "B C"]]
    )

    assert network.activity_arc("D").head == network.finish
    assert precedes(network, "B", "D")
    assert precedes(network, "C", "D")
    assert not precedes(network, "B", "C")


def test_overlapping_predecessor_sets_get_a_dummy():
    # C needs A and B, D needs only A: the classic case where sharing an event would
    # invent a precedence B -> D that the table does not state.
    network = network_for(
        [["A", "1", ""], ["B", "1", ""], ["C", "1", "A B"], ["D", "1", "A"]]
    )

    assert any(arc.dummy for arc in network.arcs)
    assert precedes(network, "A", "C")
    assert precedes(network, "B", "C")
    assert precedes(network, "A", "D")
    assert not precedes(network, "B", "D")


def test_every_stated_precedence_holds():
    rows = [
        ["A", "2", ""],
        ["B", "3", ""],
        ["C", "1", "A"],
        ["D", "4", "A B"],
        ["E", "2", "C D"],
        ["F", "3", "B"],
    ]
    network = network_for(rows)

    for identifier, duration, predecessors in rows:
        for predecessor in predecessors.split():
            assert precedes(network, predecessor, identifier), (
                f"{predecessor} -> {identifier} lost"
            )


def test_no_precedence_is_invented():
    network = network_for(
        [["A", "1", ""], ["B", "1", ""], ["C", "1", "A"], ["D", "1", "B"]]
    )

    assert not precedes(network, "A", "D")
    assert not precedes(network, "B", "C")


def test_dummies_carry_no_duration_and_no_label():
    network = network_for(
        [["A", "1", ""], ["B", "1", ""], ["C", "1", "A B"], ["D", "1", "A"]]
    )

    for arc in network.arcs:
        if arc.dummy:
            assert arc.duration == 0.0
            assert arc.label() == ""


def test_labels_show_identifier_and_duration():
    network = network_for([["A", "3", ""], ["B", "2.5", "A"]])

    assert network.activity_arc("A").label() == "A(3)"
    assert network.activity_arc("B").label() == "B(2.5)"


def test_every_arc_runs_from_a_lower_to_a_higher_event():
    network = network_for(
        [
            ["A", "2", ""],
            ["B", "3", ""],
            ["C", "1", "A"],
            ["D", "4", "A B"],
            ["E", "2", "C D"],
        ]
    )

    for arc in network.arcs:
        assert arc.tail < arc.head


def test_the_finish_event_has_the_highest_number():
    network = network_for(
        [["A", "1", ""], ["B", "1", ""], ["C", "1", "A"], ["D", "1", "A B"]]
    )

    assert network.finish == max(network.events)
    assert network.start == min(network.events)


def test_parallel_activities_are_split_by_a_dummy():
    # A and B have the same predecessors and no successors, so both would run from
    # the start event to the finish event and be drawn on top of each other.
    network = network_for([["A", "1", ""], ["B", "2", ""]])

    pairs = [(arc.tail, arc.head) for arc in network.arcs if not arc.dummy]
    assert len(set(pairs)) == len(pairs)
    assert sum(1 for arc in network.arcs if arc.dummy) == 1


def test_disconnected_fragments_still_share_start_and_finish():
    network = network_for(
        [["A", "1", ""], ["B", "1", "A"], ["C", "1", ""], ["D", "1", "C"]]
    )

    assert network.activity_arc("A").tail == network.start
    assert network.activity_arc("C").tail == network.start
    assert network.activity_arc("B").head == network.finish
    assert network.activity_arc("D").head == network.finish


def test_the_same_table_always_gives_the_same_network():
    rows = [
        ["A", "2", ""],
        ["B", "3", ""],
        ["C", "1", "A"],
        ["D", "4", "A B"],
        ["E", "2", "C D"],
    ]

    first = network_for(rows)
    second = network_for(rows)

    assert first == second


def test_rejects_an_empty_activity_list():
    with pytest.raises(ValueError):
        build_network([])
