"""Early and late times, floats and the critical path.

Forward pass: E(start) = 0, E(j) = max over arcs i->j of E(i) + d.
Backward pass: L(finish) = E(finish), L(i) = min over arcs i->j of L(j) - d.

An activity's total float is L(head) - E(tail) - d; the critical path is the arcs
with no float, which is also the longest path from start to finish.

No UNO here either: this is arithmetic over the Network built in network.py.
"""

from __future__ import annotations

from dataclasses import dataclass

from lopert.network import Arc, Network

# Durations are floats, so "zero float" has to mean "zero to within rounding".
TOLERANCE = 1e-9


@dataclass(frozen=True)
class Times:
    early: dict[int, float]
    late: dict[int, float]
    # Activity identifier -> total float. Dummies are not in here; they are not work.
    total_float: dict[str, float]
    critical_activities: tuple[str, ...]
    # Every arc with no float, dummies included: the critical path as drawn.
    critical_arcs: tuple[Arc, ...]

    @property
    def duration(self) -> float:
        """How long the project takes: the early time of the finish event."""
        return max(self.early.values()) if self.early else 0.0

    def slack(self, event: int) -> float:
        """An event's slack — how long it can be delayed without delaying the end."""
        return self.late[event] - self.early[event]

    def is_critical_event(self, event: int) -> bool:
        return abs(self.slack(event)) <= TOLERANCE


def compute_times(network: Network) -> Times:
    """Run both passes over a network whose events are in topological order."""

    early = {event: 0.0 for event in network.events}
    for event in sorted(network.events):
        for arc in network.arcs_into(event):
            early[event] = max(early[event], early[arc.tail] + arc.duration)

    finish_time = early[network.finish]
    late = {event: finish_time for event in network.events}
    for event in sorted(network.events, reverse=True):
        outgoing = network.arcs_out_of(event)
        if outgoing:
            late[event] = min(late[arc.head] - arc.duration for arc in outgoing)

    total_float: dict[str, float] = {}
    critical_arcs = []
    for arc in network.arcs:
        float_ = late[arc.head] - early[arc.tail] - arc.duration
        if arc.activity is not None:
            total_float[arc.activity] = float_
        # A critical arc has no float *and* joins two critical events: an arc with
        # slack at either end is not on the longest path even if its own float is
        # zero.
        if (
            abs(float_) <= TOLERANCE
            and abs(late[arc.tail] - early[arc.tail]) <= TOLERANCE
            and abs(late[arc.head] - early[arc.head]) <= TOLERANCE
        ):
            critical_arcs.append(arc)

    critical_activities = tuple(
        arc.activity for arc in critical_arcs if arc.activity is not None
    )

    return Times(
        early=early,
        late=late,
        total_float=total_float,
        critical_activities=critical_activities,
        critical_arcs=tuple(critical_arcs),
    )
