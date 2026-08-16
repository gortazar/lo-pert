"""Precedence table -> activity-on-arrow network.

In an AOA network the *events* (states) are nodes and the *activities* (actions) are
arcs. Turning a precedence table into one is not a relabelling: activities that share
some but not all of their predecessors cannot share an event, so the network needs
*dummy* activities — zero-duration arcs that carry a precedence without implying work.

The construction here is the standard one, and deliberately not the minimal one:
minimising dummies is NP-hard, so the goal is a network that is correct (every
precedence in the table holds, and no precedence that is not in the table is implied)
and deterministic (the same table always gives the same network).

    * activities sharing the same set of immediate predecessors share a start event
    * every activity gets its own end event, which then feeds dummies into the start
      events of the activities that need it
    * two merges keep the obvious cases dummy-free: an activity that is the *only*
      predecessor of some group ends directly at that group's start event, and an
      activity nobody depends on ends directly at the finish event
    * activities with no predecessors leave the single start event; activities with
      no successors arrive at the single finish event

Everything in this module is plain data — no UNO, no LibreOffice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from lopert.table import Activity

START_KEY = "start"
FINISH_KEY = "finish"


@dataclass(frozen=True)
class Arc:
    """One arrow: a real activity, or a dummy carrying precedence only."""

    tail: int
    head: int
    duration: float
    activity: str | None = None

    @property
    def dummy(self) -> bool:
        return self.activity is None

    def label(self) -> str:
        """What the arrow shows: identifier and duration; dummies show nothing."""
        if self.dummy:
            return ""
        return f"{self.activity}({_number(self.duration)})"


@dataclass(frozen=True)
class Network:
    """Numbered events and the arcs between them.

    Event numbers are a topological order: every arc runs from a lower to a higher
    number, which is the convention the diagram is read with.
    """

    events: tuple[int, ...]
    arcs: tuple[Arc, ...]
    start: int
    finish: int

    def arcs_into(self, event: int) -> tuple[Arc, ...]:
        return tuple(arc for arc in self.arcs if arc.head == event)

    def arcs_out_of(self, event: int) -> tuple[Arc, ...]:
        return tuple(arc for arc in self.arcs if arc.tail == event)

    def activity_arc(self, identifier: str) -> Arc:
        for arc in self.arcs:
            if arc.activity == identifier:
                return arc
        raise KeyError(identifier)


def _number(value: float) -> str:
    """3.0 -> "3", 2.5 -> "2.5" — durations read as the user typed them."""
    return str(int(value)) if float(value).is_integer() else str(value)


class _Merges:
    """Union-find over node keys, keeping the first key seen as the name."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def find(self, key: str) -> str:
        self._parent.setdefault(key, key)
        root = key
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[key] != root:
            self._parent[key], key = root, self._parent[key]
        return root

    def union(self, keep: str, drop: str) -> None:
        self._parent[self.find(drop)] = self.find(keep)


def _predecessor_key(predecessors: Iterable[str]) -> str:
    ordered = sorted(predecessors)
    if not ordered:
        return START_KEY
    return "after:" + ",".join(ordered)


def build_network(activities: Sequence[Activity]) -> Network:
    """Build the AOA network for a validated precedence table."""

    if not activities:
        raise ValueError("cannot build a network from an empty table")

    order = [activity.id for activity in activities]
    by_id = {activity.id: activity for activity in activities}

    successors: dict[str, list[str]] = {identifier: [] for identifier in order}
    for activity in activities:
        for predecessor in activity.predecessors:
            successors[predecessor].append(activity.id)

    # Distinct predecessor sets, in first-appearance order so the result does not
    # depend on set iteration order.
    groups: dict[str, list[str]] = {}
    group_members: dict[str, tuple[str, ...]] = {}
    for activity in activities:
        key = _predecessor_key(activity.predecessors)
        groups.setdefault(key, []).append(activity.id)
        group_members[key] = tuple(sorted(activity.predecessors))

    merges = _Merges()
    for identifier in order:
        end_key = f"end:{identifier}"
        if not successors[identifier]:
            # Nobody waits for it, so its end event *is* the project's finish event.
            merges.union(FINISH_KEY, end_key)
    for key, members in group_members.items():
        if len(members) == 1:
            # The group waits for exactly one activity, so that activity can end
            # right where the group starts — the dummy would carry nothing.
            merges.union(key, f"end:{members[0]}")

    arcs: list[tuple[str, str, float, str | None]] = []
    for identifier in order:
        activity = by_id[identifier]
        tail = merges.find(_predecessor_key(activity.predecessors))
        head = merges.find(f"end:{identifier}")
        arcs.append((tail, head, activity.duration, identifier))

    seen_dummies: set[tuple[str, str]] = set()
    for key, members in group_members.items():
        head = merges.find(key)
        for member in members:
            tail = merges.find(f"end:{member}")
            if tail == head or (tail, head) in seen_dummies:
                continue
            seen_dummies.add((tail, head))
            arcs.append((tail, head, 0.0, None))

    arcs = _split_parallel_activities(arcs)
    numbers = _number_events(arcs, merges)

    numbered = tuple(
        Arc(numbers[tail], numbers[head], duration, activity)
        for tail, head, duration, activity in arcs
    )
    numbered = tuple(sorted(numbered, key=lambda arc: (arc.tail, arc.head, arc.activity or "")))

    return Network(
        events=tuple(sorted(numbers.values())),
        arcs=numbered,
        start=numbers[merges.find(START_KEY)],
        finish=numbers[merges.find(FINISH_KEY)],
    )


def _split_parallel_activities(
    arcs: list[tuple[str, str, float, str | None]],
) -> list[tuple[str, str, float, str | None]]:
    """Give parallel real activities their own arcs to run along.

    Two activities between the same pair of events are ambiguous in the notation and
    would be drawn as two arrows on top of each other. The textbook fix is a dummy:
    the second activity ends at a new event, which a dummy then joins to the original
    one. Correctness is unaffected — the dummy adds no precedence the pair did not
    already have.
    """

    result: list[tuple[str, str, float, str | None]] = []
    taken: set[tuple[str, str]] = set()
    extra = 0
    for tail, head, duration, activity in arcs:
        if activity is not None and (tail, head) in taken:
            extra += 1
            split = f"split:{activity}:{extra}"
            result.append((tail, split, duration, activity))
            result.append((split, head, 0.0, None))
            continue
        if activity is not None:
            taken.add((tail, head))
        result.append((tail, head, duration, activity))
    return result


def _number_events(
    arcs: Sequence[tuple[str, str, float, str | None]], merges: _Merges
) -> dict[str, int]:
    """Number events so that every arc runs from a lower number to a higher one.

    Events are ordered by level — the longest path in arcs from the start event —
    and ties are broken by key, so the numbering is a fixed function of the table.
    """

    keys = {merges.find(START_KEY), merges.find(FINISH_KEY)}
    outgoing: dict[str, list[str]] = {}
    incoming_count: dict[str, int] = {}
    for tail, head, _duration, _activity in arcs:
        keys.add(tail)
        keys.add(head)
        outgoing.setdefault(tail, []).append(head)
        incoming_count[head] = incoming_count.get(head, 0) + 1

    level = {key: 0 for key in keys}
    remaining = {key: incoming_count.get(key, 0) for key in keys}
    ready = sorted(key for key in keys if remaining[key] == 0)
    ordered: list[str] = []
    while ready:
        key = ready.pop(0)
        ordered.append(key)
        for head in outgoing.get(key, ()):
            level[head] = max(level[head], level[key] + 1)
            remaining[head] -= 1
            if remaining[head] == 0:
                ready.append(head)
                ready.sort()
    if len(ordered) != len(keys):
        # The table is validated for cycles before it gets here, so this would be a
        # bug in the construction rather than bad input.
        raise AssertionError("the constructed network is cyclic")

    # The finish event is always last: it is where the project ends, and a reader
    # expects the highest number there even if some branch is longer in arcs.
    finish = merges.find(FINISH_KEY)
    ordering = sorted(
        keys, key=lambda key: (key == finish, level[key], key)
    )
    return {key: number for number, key in enumerate(ordering, start=1)}


def activity_ids(network: Network) -> tuple[str, ...]:
    return tuple(arc.activity for arc in network.arcs if arc.activity is not None)
