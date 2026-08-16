import pytest

from lopert.diagram import build_diagram, diagram_from_rows
from lopert.layout import Style, layout, levels, renumber_by_layout
from lopert.network import build_network
from lopert.table import parse_table

WORKED_EXAMPLE = [
    ["A", "3", ""],
    ["B", "4", ""],
    ["C", "2", "A"],
    ["D", "5", "A"],
    ["E", "4", "C D"],
    ["F", "3", "B"],
]


def placed(rows):
    network = build_network(parse_table(rows))
    return network, layout(network)


def test_the_start_event_is_leftmost_and_the_finish_event_rightmost():
    network, placement = placed(WORKED_EXAMPLE)

    xs = {event: placement.centre(event)[0] for event in network.events}
    assert xs[network.start] == min(xs.values())
    assert xs[network.finish] == max(xs.values())


def test_every_arrow_points_rightwards():
    network, placement = placed(WORKED_EXAMPLE)

    for arc in network.arcs:
        assert placement.centre(arc.tail)[0] < placement.centre(arc.head)[0]


def test_events_never_share_a_position():
    network, placement = placed(WORKED_EXAMPLE)

    positions = [placement.centre(event) for event in network.events]
    assert len(set(positions)) == len(positions)


def test_events_in_a_column_are_spaced_by_the_row_spacing():
    style = Style()
    network = build_network(parse_table(WORKED_EXAMPLE))
    placement = layout(network, style)

    columns = {}
    for event in network.events:
        x, y = placement.centre(event)
        columns.setdefault(x, []).append(y)
    for ys in columns.values():
        ys.sort()
        for first, second in zip(ys, ys[1:]):
            assert second - first == style.row_spacing


def test_the_level_of_an_event_is_its_longest_path_in_arcs():
    network = build_network(parse_table(WORKED_EXAMPLE))

    level = levels(network)
    assert level[network.start] == 0
    for arc in network.arcs:
        assert level[arc.head] >= level[arc.tail] + 1


def test_layout_is_deterministic():
    _network, first = placed(WORKED_EXAMPLE)
    _network, second = placed(WORKED_EXAMPLE)

    assert first.positions == second.positions


def test_the_diagram_fits_the_reported_size():
    diagram = diagram_from_rows(WORKED_EXAMPLE)

    for event in diagram.network.events:
        x, y = diagram.placement.centre(event)
        assert 0 < x < diagram.width
        assert 0 < y < diagram.height


def test_renumbering_keeps_the_topological_order():
    network = build_network(parse_table(WORKED_EXAMPLE))
    placement = layout(network)

    renumbered, moved = renumber_by_layout(network, placement)

    assert set(renumbered.events) == set(range(1, len(network.events) + 1))
    for arc in renumbered.arcs:
        assert arc.tail < arc.head
    assert renumbered.finish == max(renumbered.events)
    assert set(moved.positions) == set(renumbered.events)


def test_renumbering_reads_left_to_right_then_top_to_bottom():
    diagram = diagram_from_rows(WORKED_EXAMPLE)

    ordered = sorted(
        diagram.network.events, key=lambda event: diagram.placement.centre(event)
    )
    # Excluding the finish event, which is deliberately numbered last.
    ordered = [event for event in ordered if event != diagram.network.finish]
    assert ordered == sorted(ordered)


def test_the_state_circle_reads_early_late_number():
    diagram = diagram_from_rows(WORKED_EXAMPLE)

    early, late, number = diagram.state_text(diagram.network.start)
    assert (early, late, number) == ("0", "0", str(diagram.network.start))

    early, late, number = diagram.state_text(diagram.network.finish)
    assert early == late == "12"
    assert number == str(diagram.network.finish)


def test_the_summary_names_the_critical_path():
    diagram = diagram_from_rows(WORKED_EXAMPLE)

    summary = diagram.summary()
    assert "Project duration: 12" in summary
    assert "A -> D -> E" in summary


def test_a_wider_style_produces_a_wider_diagram():
    narrow = build_diagram(parse_table(WORKED_EXAMPLE), Style(column_spacing=4000))
    wide = build_diagram(parse_table(WORKED_EXAMPLE), Style(column_spacing=8000))

    assert wide.width > narrow.width


def test_barycentre_ordering_beats_the_naive_one_on_a_crossing_table():
    # Two independent strands: A -> C and B -> D. Numbered order would interleave
    # the middle column and cross the strands; the barycentre sweep should not.
    rows = [
        ["A", "1", ""],
        ["B", "1", ""],
        ["C", "1", "A"],
        ["D", "1", "B"],
        ["E", "1", "C"],
        ["F", "1", "D"],
    ]
    diagram = diagram_from_rows(rows)

    assert _crossings(diagram) == 0


def _crossings(diagram):
    """Count pairs of arcs between the same two columns whose ends interleave."""
    count = 0
    arcs = diagram.network.arcs
    centre = diagram.placement.centre
    for index, first in enumerate(arcs):
        for second in arcs[index + 1 :]:
            first_tail, first_head = centre(first.tail), centre(first.head)
            second_tail, second_head = centre(second.tail), centre(second.head)
            if first_tail[0] != second_tail[0] or first_head[0] != second_head[0]:
                continue
            if (first_tail[1] - second_tail[1]) * (
                first_head[1] - second_head[1]
            ) < 0:
                count += 1
    return count


def test_a_single_activity_lays_out_in_two_columns():
    diagram = diagram_from_rows([["A", "3", ""]])

    assert len(diagram.network.events) == 2
    left, right = (diagram.placement.centre(e) for e in diagram.network.events)
    assert left[0] < right[0]
    assert left[1] == right[1]


def test_diagram_from_rows_rejects_a_bad_table():
    from lopert.table import TableValidationError

    with pytest.raises(TableValidationError):
        diagram_from_rows([["A", "1", "Z"]])


def test_fit_scale_shrinks_a_diagram_that_is_too_wide():
    from lopert.layout import fit_scale

    assert fit_scale(60000, 10000, 29700, 21000, margin=1000) < 1.0


def test_fit_scale_never_enlarges_a_small_diagram():
    from lopert.layout import fit_scale

    assert fit_scale(5000, 5000, 29700, 21000) == 1.0
