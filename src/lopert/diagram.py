"""The whole pure pipeline: cells in, a laid-out diagram out.

    rows -> activities -> network -> layout -> renumbered events -> times

This is everything the UNO layer needs to know about. It hands drawing.py a Diagram
and gets shapes back; nothing above this line imports UNO, and nothing below it knows
what a precedence table is.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from lopert.layout import Layout, Style, layout, renumber_by_layout
from lopert.network import Arc, Network, build_network
from lopert.table import Activity, Cell, parse_table
from lopert.times import Times, compute_times


@dataclass(frozen=True)
class Diagram:
    activities: tuple[Activity, ...]
    network: Network
    times: Times
    placement: Layout

    @property
    def width(self) -> int:
        return self.placement.width

    @property
    def height(self) -> int:
        return self.placement.height

    def state_text(self, event: int) -> tuple[str, str, str]:
        """The three regions of an event circle: early, late, number.

        Upper-left is the early time, upper-right the late time, and the lower half
        the event number.
        """
        return (
            _number(self.times.early[event]),
            _number(self.times.late[event]),
            str(event),
        )

    def is_critical_arc(self, arc: Arc) -> bool:
        return arc in self.times.critical_arcs

    def summary(self) -> str:
        critical = " -> ".join(self.times.critical_activities)
        return (
            f"{len(self.activities)} activities, "
            f"{len(self.network.events)} events, "
            f"{sum(1 for arc in self.network.arcs if arc.dummy)} dummy activities.\n"
            f"Project duration: {_number(self.times.duration)}.\n"
            f"Critical path: {critical}"
        )


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(round(value, 4))


def build_diagram(
    activities: Sequence[Activity], style: Style | None = None
) -> Diagram:
    """Network, layout, event numbering and times for a validated table."""

    network = build_network(activities)
    placement = layout(network, style)
    network, placement = renumber_by_layout(network, placement)
    return Diagram(
        activities=tuple(activities),
        network=network,
        times=compute_times(network),
        placement=placement,
    )


def diagram_from_rows(
    rows: Iterable[Sequence[Cell]], style: Style | None = None
) -> Diagram:
    """The whole pipeline, raising TableValidationError on bad input."""
    return build_diagram(parse_table(rows), style)
