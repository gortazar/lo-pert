"""Where each event goes on the page.

Layered layout, left to right: an event's column is its level — the longest path in
arcs from the start event — which guarantees every arrow points rightwards. Within a
column the vertical order comes from a few barycentre sweeps, the standard cheap way
to cut crossings: put each event next to the average position of the events it is
joined to.

Coordinates are in 1/100 mm, the unit the drawing API uses, and are the *centres* of
the state circles. Still no UNO: this module only produces numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from lopert.network import Arc, Network


@dataclass(frozen=True)
class Style:
    """Sizes in 1/100 mm. A4 landscape is 29700 x 21000."""

    circle_diameter: int = 2000
    column_spacing: int = 5000
    row_spacing: int = 3000
    margin: int = 1500
    # Sweeps of the barycentre heuristic. Four is plenty: it converges fast and the
    # result has to be deterministic, not optimal.
    sweeps: int = 4


@dataclass(frozen=True)
class Layout:
    positions: dict[int, tuple[int, int]]
    level: dict[int, int]
    style: Style
    width: int
    height: int

    def centre(self, event: int) -> tuple[int, int]:
        return self.positions[event]


def levels(network: Network) -> dict[int, int]:
    """Longest path in arcs from the start event, per event."""
    level = {event: 0 for event in network.events}
    # Event numbers are a topological order, so one pass in order is enough.
    for event in sorted(network.events):
        for arc in network.arcs_out_of(event):
            level[arc.head] = max(level[arc.head], level[event] + 1)
    return level


def _columns(network: Network, level: dict[int, int]) -> dict[int, list[int]]:
    columns: dict[int, list[int]] = {}
    for event in sorted(network.events):
        columns.setdefault(level[event], []).append(event)
    return columns


def _barycentre(
    columns: dict[int, list[int]], neighbours: dict[int, list[int]]
) -> None:
    """Reorder one column by the average position of each event's neighbours."""
    for depth in sorted(columns):
        column = columns[depth]
        index_of = {
            event: position
            for other_depth, other in columns.items()
            if other_depth != depth
            for position, event in enumerate(other)
        }
        keyed = []
        for position, event in enumerate(column):
            related = [index_of[n] for n in neighbours.get(event, ()) if n in index_of]
            # An event with no neighbour in another column keeps its place, so the
            # sort stays stable and the result deterministic.
            keyed.append(
                (sum(related) / len(related) if related else position, position, event)
            )
        keyed.sort()
        columns[depth] = [event for _key, _position, event in keyed]


def layout(network: Network, style: Style | None = None) -> Layout:
    """Place every event, left to right by level."""

    style = style or Style()
    level = levels(network)
    columns = _columns(network, level)

    predecessors: dict[int, list[int]] = {}
    successors: dict[int, list[int]] = {}
    for arc in network.arcs:
        predecessors.setdefault(arc.head, []).append(arc.tail)
        successors.setdefault(arc.tail, []).append(arc.head)

    for sweep in range(style.sweeps):
        _barycentre(columns, predecessors if sweep % 2 == 0 else successors)

    tallest = max(len(column) for column in columns.values())
    positions: dict[int, tuple[int, int]] = {}
    for depth, column in columns.items():
        x = style.margin + style.circle_diameter // 2 + depth * style.column_spacing
        # Columns are centred against the tallest one, which keeps the diagram
        # looking like a network rather than a staircase.
        top = (tallest - len(column)) * style.row_spacing / 2
        for position, event in enumerate(column):
            y = int(
                style.margin
                + style.circle_diameter // 2
                + top
                + position * style.row_spacing
            )
            positions[event] = (x, y)

    width = (
        style.margin * 2 + style.circle_diameter + max(columns) * style.column_spacing
    )
    height = (
        style.margin * 2 + style.circle_diameter + (tallest - 1) * style.row_spacing
    )
    return Layout(
        positions=positions, level=level, style=style, width=width, height=height
    )


def renumber_by_layout(
    network: Network, placement: Layout
) -> tuple[Network, Layout]:
    """Renumber events so they read left to right, then top to bottom.

    Still a topological order — level increases along every arc — but one that
    matches how the drawing is read, which is the point of numbering events at all.
    """

    ordering = sorted(
        network.events,
        key=lambda event: (
            placement.level[event],
            placement.positions[event][1],
            event,
        ),
    )
    # The finish event keeps the last number: it is the end of the project, wherever
    # the layout happened to put it.
    ordering = [event for event in ordering if event != network.finish]
    ordering.append(network.finish)
    mapping = {event: number for number, event in enumerate(ordering, start=1)}

    arcs = tuple(
        sorted(
            (
                Arc(mapping[arc.tail], mapping[arc.head], arc.duration, arc.activity)
                for arc in network.arcs
            ),
            key=lambda arc: (arc.tail, arc.head, arc.activity or ""),
        )
    )
    renumbered = Network(
        events=tuple(sorted(mapping.values())),
        arcs=arcs,
        start=mapping[network.start],
        finish=mapping[network.finish],
    )
    moved = replace(
        placement,
        positions={
            mapping[event]: position
            for event, position in placement.positions.items()
        },
        level={mapping[event]: depth for event, depth in placement.level.items()},
    )
    return renumbered, moved
