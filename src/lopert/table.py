"""Precedence table: the input side of the core.

A precedence table is one row per activity — identifier, duration, immediate
predecessors — which is what a user types into a Calc sheet. Everything here works
on plain strings and numbers so it can be unit-tested without LibreOffice.

Validation collects *every* problem it can find rather than stopping at the first,
because the dialog that reports them should name all the offending rows at once.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

# Cells are handed over as strings (Calc's getString()) or numbers (getValue()).
Cell = object


@dataclass(frozen=True)
class Activity:
    """One row of the table, after parsing."""

    id: str
    duration: float
    predecessors: tuple[str, ...]
    # 1-based index of the source row, used verbatim in error messages so the user
    # can find the cell to fix.
    row: int


@dataclass(frozen=True)
class TableError:
    """One problem with the input. `row` is None for whole-table problems."""

    message: str
    row: int | None = None

    def __str__(self) -> str:
        if self.row is None:
            return self.message
        return f"row {self.row}: {self.message}"


class TableValidationError(Exception):
    """Raised when the table cannot be turned into a network.

    Carries every problem found, not just the first, so callers can show them all.
    """

    def __init__(self, errors: Sequence[TableError]):
        self.errors: tuple[TableError, ...] = tuple(errors)
        super().__init__("\n".join(str(e) for e in self.errors))


# Anything a user might reasonably put between predecessor ids in one cell.
_PREDECESSOR_SEPARATORS = ",;/|"

# Cell values meaning "no predecessors". Spanish and English, since the diagram is
# taught under both names.
_NO_PREDECESSORS = {"", "-", "--", "—", "none", "ninguna", "ninguno", "na", "n/a"}

_HEADER_WORDS = {
    "id",
    "activity",
    "activities",
    "actividad",
    "actividades",
    "tarea",
    "tareas",
    "task",
    "name",
    "nombre",
}

_DURATION_HEADER_WORDS = {
    "duration",
    "duracion",
    "duración",
    "time",
    "tiempo",
    "days",
    "dias",
    "días",
    "weeks",
    "semanas",
    "length",
}

_PREDECESSOR_HEADER_WORDS = {
    "predecessor",
    "predecessors",
    "predecesor",
    "predecesores",
    "precedent",
    "precedents",
    "precedentes",
    "precede",
    "previous",
    "previas",
    "anteriores",
    "depends",
    "dependencies",
}


def _cell_text(cell: Cell) -> str:
    if cell is None:
        return ""
    if isinstance(cell, float) and cell.is_integer():
        # Calc hands back 3.0 for a cell showing "3"; an id of "3.0" would be a
        # surprise nobody asked for.
        return str(int(cell))
    return str(cell).strip()


def split_predecessors(text: str) -> tuple[str, ...]:
    """Split one predecessors cell into ids.

    Accepts commas, semicolons, slashes, pipes or plain whitespace as separators, so
    "A,B", "A B" and "A; B" all mean the same thing.
    """

    text = _cell_text(text)
    if text.lower() in _NO_PREDECESSORS:
        return ()
    for sep in _PREDECESSOR_SEPARATORS:
        text = text.replace(sep, " ")
    return tuple(part for part in text.split() if part)


def looks_like_header(row: Sequence[Cell]) -> bool:
    """True when a row is a header rather than an activity.

    A non-numeric duration is necessary but not sufficient: ["A", "x", ""] is an
    activity with a broken duration, and silently swallowing it as a header would
    turn a reportable error into a missing activity. So one of the three cells also
    has to read like a column title.
    """

    if len(row) < 2:
        return False
    duration = _cell_text(row[1])
    if duration == "":
        return False
    if _parse_duration(duration) is not None:
        return False
    return (
        _cell_text(row[0]).lower() in _HEADER_WORDS
        or duration.lower() in _DURATION_HEADER_WORDS
        or (
            len(row) > 2
            and _cell_text(row[2]).lower() in _PREDECESSOR_HEADER_WORDS
        )
    )


def _parse_duration(text: str) -> float | None:
    # A comma decimal separator is what a Spanish locale produces, and rejecting it
    # would be a locale bug rather than a validation.
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def parse_table(rows: Iterable[Sequence[Cell]]) -> list[Activity]:
    """Turn raw cells into activities, or raise TableValidationError.

    Rows are 1-based for error reporting, counting the header if there is one, so the
    numbers match what the user sees in Calc. Entirely blank rows are skipped: a
    selected range usually has a few.
    """

    errors: list[TableError] = []
    activities: list[Activity] = []
    seen: dict[str, int] = {}

    materialised = [list(row) for row in rows]
    for index, row in enumerate(materialised, start=1):
        if index == 1 and looks_like_header(row):
            continue
        cells = [_cell_text(cell) for cell in row]
        if not any(cells):
            continue

        identifier = cells[0] if cells else ""
        duration_text = cells[1] if len(cells) > 1 else ""
        predecessors = split_predecessors(cells[2]) if len(cells) > 2 else ()

        if identifier == "":
            errors.append(TableError("activity has no identifier", index))
            continue
        if identifier in seen:
            errors.append(
                TableError(
                    f"activity {identifier!r} is already defined on row {seen[identifier]}",
                    index,
                )
            )
            continue

        if duration_text == "":
            errors.append(TableError(f"activity {identifier!r} has no duration", index))
            duration = 0.0
        else:
            parsed = _parse_duration(duration_text)
            if parsed is None:
                errors.append(
                    TableError(
                        f"duration {duration_text!r} of activity {identifier!r} is not a number",
                        index,
                    )
                )
                duration = 0.0
            elif parsed < 0:
                errors.append(
                    TableError(
                        f"duration of activity {identifier!r} is negative", index
                    )
                )
                duration = 0.0
            else:
                duration = parsed

        seen[identifier] = index
        activities.append(Activity(identifier, duration, predecessors, index))

    if not activities and not errors:
        errors.append(TableError("the precedence table is empty"))

    known = {activity.id for activity in activities}
    for activity in activities:
        for predecessor in activity.predecessors:
            if predecessor == activity.id:
                errors.append(
                    TableError(
                        f"activity {activity.id!r} is its own predecessor", activity.row
                    )
                )
            elif predecessor not in known:
                errors.append(
                    TableError(
                        f"activity {activity.id!r} lists unknown predecessor "
                        f"{predecessor!r}",
                        activity.row,
                    )
                )

    if not errors:
        errors.extend(_cycle_errors(activities))

    if errors:
        raise TableValidationError(errors)
    return activities


def _cycle_errors(activities: Sequence[Activity]) -> list[TableError]:
    """Report one error per activity on a cycle, naming the cycle itself.

    Only run once ids are known to resolve, so the walk cannot fall off the graph.
    """

    by_id = {activity.id: activity for activity in activities}
    # 0 = unvisited, 1 = on the current path, 2 = done.
    state: dict[str, int] = {activity.id: 0 for activity in activities}
    path: list[str] = []
    cycles: list[list[str]] = []

    def visit(identifier: str) -> None:
        state[identifier] = 1
        path.append(identifier)
        for predecessor in by_id[identifier].predecessors:
            if state[predecessor] == 0:
                visit(predecessor)
            elif state[predecessor] == 1:
                start = path.index(predecessor)
                cycles.append(path[start:] + [predecessor])
        path.pop()
        state[identifier] = 2

    import sys

    # Deep chains are legitimate input; the default limit is reached around a
    # thousand activities, which a real table can have.
    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(previous_limit, 10 * len(activities) + 1000))
    try:
        for activity in activities:
            if state[activity.id] == 0:
                visit(activity.id)
    finally:
        sys.setrecursionlimit(previous_limit)

    errors: list[TableError] = []
    reported: set[str] = set()
    for cycle in cycles:
        # The cycle reads in precedence order — A depends on B depends on A — which
        # is the direction the user wrote the table in.
        chain = " -> ".join(reversed(cycle))
        head = cycle[0]
        if head in reported:
            continue
        reported.add(head)
        errors.append(
            TableError(f"circular precedence: {chain}", by_id[head].row)
        )
    return errors
