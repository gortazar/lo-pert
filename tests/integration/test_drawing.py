"""The commands that put shapes on a page, driven through the installed extension.

These read the resulting page back — group structure, connector endpoints, the text
in each region — because "the command ran without raising" says nothing about whether
a diagram appeared.
"""

import pytest

WORKED_EXAMPLE = [
    ["Activity", "Duration", "Predecessors"],
    ["A", 3.0, ""],
    ["B", 4.0, ""],
    ["C", 2.0, "A"],
    ["D", 5.0, "A"],
    ["E", 4.0, "C, D"],
    ["F", 3.0, "B"],
]


def shapes_on(page):
    return [page.getByIndex(index) for index in range(page.getCount())]


def named(page, prefix):
    return [shape for shape in shapes_on(page) if shape.Name.startswith(prefix)]


def texts_of(group):
    """The strings inside a state group, in the order they were added."""
    return [
        group.getByIndex(index).getString()
        for index in range(group.getCount())
        if group.getByIndex(index).getString()
    ]


@pytest.fixture
def calc_with_table(office):
    """A Calc document holding the worked example, with the table selected."""
    document = office.new_document("scalc")
    sheet = document.getSheets().getByIndex(0)
    for row, cells in enumerate(WORKED_EXAMPLE):
        for column, value in enumerate(cells):
            cell = sheet.getCellByPosition(column, row)
            if isinstance(value, float):
                cell.setValue(value)
            else:
                cell.setString(value)
    cell_range = sheet.getCellRangeByPosition(0, 0, 2, len(WORKED_EXAMPLE) - 1)
    document.getCurrentController().select(cell_range)
    office.clear_dialogs()
    try:
        yield document
    finally:
        document.close(False)


def test_insert_state_draws_a_grouped_three_region_circle(office, draw_document):
    page = draw_document.getDrawPages().getByIndex(0)

    office.dispatch(draw_document, "InsertState")

    groups = named(page, "lopert.event.")
    assert len(groups) == 1
    group = groups[0]
    assert group.getShapeType() == "com.sun.star.drawing.GroupShape"
    # Ellipse, two dividers, three texts.
    assert group.getCount() == 6
    assert texts_of(group) == ["0", "0", "1"]


def test_a_second_state_gets_the_next_number(office, draw_document):
    page = draw_document.getDrawPages().getByIndex(0)

    office.dispatch(draw_document, "InsertState")
    office.dispatch(draw_document, "InsertState")

    numbers = sorted(texts_of(group)[-1] for group in named(page, "lopert.event."))
    assert numbers == ["1", "2"]


def test_insert_action_needs_two_selected_states(office, draw_document):
    office.dispatch(draw_document, "InsertAction")

    kinds = [dialog[0] for dialog in office.dialogs()]
    assert kinds == ["errorbox"]


def test_insert_action_glues_an_arrow_to_both_states(office, draw_document):
    page = draw_document.getDrawPages().getByIndex(0)
    office.dispatch(draw_document, "InsertState")
    office.dispatch(draw_document, "InsertState")
    groups = named(page, "lopert.event.")
    # Put them side by side so the command has a left and a right one to join.
    from com.sun.star.awt import Point

    groups[0].setPosition(Point(3000, 5000))
    groups[1].setPosition(Point(12000, 5000))
    controller = draw_document.getCurrentController()
    collection = office.ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.drawing.ShapeCollection", office.ctx
    )
    collection.add(groups[0])
    collection.add(groups[1])
    controller.select(collection)

    office.dispatch(draw_document, "InsertAction")

    connectors = [
        shape
        for shape in shapes_on(page)
        if shape.getShapeType() == "com.sun.star.drawing.ConnectorShape"
    ]
    assert len(connectors) == 1
    connector = connectors[0]
    assert connector.getPropertyValue("StartShape") is not None
    assert connector.getPropertyValue("EndShape") is not None
    assert connector.getString() == "A(1)"


def test_generate_draws_the_whole_network_from_a_calc_selection(
    office, calc_with_table
):
    office.dispatch(calc_with_table, "GenerateDiagram")

    assert office.dialogs() == []
    drawings = [
        document
        for document in office.desktop.getComponents().createEnumeration()
        if document.supportsService("com.sun.star.drawing.DrawingDocument")
    ]
    assert drawings, "no Draw document was created for the diagram"
    page = drawings[0].getDrawPages().getByIndex(0)

    states = named(page, "lopert.event.")
    activities = named(page, "lopert.activity.")
    dummies = named(page, "lopert.dummy.")
    # Six activities, each drawn once, plus whatever dummies precedence required.
    assert len(activities) == 6
    assert {shape.getString()[0] for shape in activities} == set("ABCDEF")
    assert len(states) >= 4
    assert all(shape.getString() == "" for shape in dummies)

    # The finish event carries the project duration in both halves: 12 days.
    finish = max(states, key=lambda shape: int(shape.Name.rsplit(".", 1)[1]))
    early, late, number = texts_of(finish)
    assert (early, late) == ("12", "12")
    assert number == finish.Name.rsplit(".", 1)[1]

    for shape in activities + dummies:
        assert shape.getPropertyValue("StartShape") is not None
        assert shape.getPropertyValue("EndShape") is not None

    drawings[0].close(False)


def test_generate_reports_a_bad_table_and_draws_nothing(office):
    document = office.new_document("scalc")
    sheet = document.getSheets().getByIndex(0)
    for row, cells in enumerate([["A", 1.0, "Z"], ["B", -2.0, ""]]):
        sheet.getCellByPosition(0, row).setString(cells[0])
        sheet.getCellByPosition(1, row).setValue(cells[1])
        sheet.getCellByPosition(2, row).setString(cells[2])
    document.getCurrentController().select(
        sheet.getCellRangeByPosition(0, 0, 2, 1)
    )
    office.clear_dialogs()
    before = office.desktop.getComponents().createEnumeration()
    open_before = sum(1 for _ in before)

    office.dispatch(document, "GenerateDiagram")

    dialogs = office.dialogs()
    assert len(dialogs) == 1
    kind, title, message = dialogs[0]
    assert kind == "errorbox"
    assert "unknown predecessor 'Z'" in message
    assert "negative" in message
    open_after = sum(1 for _ in office.desktop.getComponents().createEnumeration())
    assert open_after == open_before, "a document was created for a rejected table"

    document.close(False)


def test_generate_without_a_spreadsheet_says_so(office, draw_document):
    office.dispatch(draw_document, "GenerateDiagram")

    dialogs = office.dialogs()
    assert len(dialogs) == 1
    assert dialogs[0][0] == "errorbox"
    assert "Calc" in dialogs[0][2]


def test_generate_draws_into_an_open_impress_document(office, calc_with_table):
    # Impress is a supported target, not just Draw: same drawing API, and the menu
    # is contributed to both. With a presentation open, the diagram belongs on its
    # slide rather than in a Draw document nobody asked for.
    presentation = office.new_document("simpress")
    try:
        office.dispatch(calc_with_table, "GenerateDiagram")

        assert office.dialogs() == []
        pages = presentation.getDrawPages()
        drawn = [
            pages.getByIndex(index)
            for index in range(pages.getCount())
            if named(pages.getByIndex(index), "lopert.event.")
        ]
        assert len(drawn) == 1, "the diagram did not land on a slide"
        page = drawn[0]
        assert len(named(page, "lopert.activity.")) == 6
        # The slide keeps its own size; the diagram is scaled to fit it.
        for shape in named(page, "lopert.event."):
            position = shape.getPosition()
            assert 0 <= position.X <= page.Width
            assert 0 <= position.Y <= page.Height
    finally:
        presentation.close(False)
