"""Turning a laid-out Diagram into shapes on a draw page.

This is the only module that touches the drawing API. It knows nothing about
precedence tables: it is handed a Diagram (events with positions and times, arcs with
labels) and puts shapes on a page.

A state is a *group*: an ellipse, a horizontal diameter, a vertical divider across the
upper half, and three text shapes — early time upper-left, late time upper-right,
event number below. Grouping makes it move and scale as one object while leaving each
number separately editable, and connectors glue to the group as a whole.
"""

from __future__ import annotations

import uno
from com.sun.star.awt import Point, Size

# Names let the shapes be found again — by a user in the Navigator, and by the
# integration tests reading a generated page back.
EVENT_PREFIX = "lopert.event."
ACTIVITY_PREFIX = "lopert.activity."
DUMMY_PREFIX = "lopert.dummy."

BLACK = 0x000000
WHITE = 0xFFFFFF
CRITICAL = 0xC9211E  # the red LibreOffice itself uses for "brick"


def _create(document, service):
    return document.createInstance(f"com.sun.star.drawing.{service}")


def _place(shape, x, y, width, height):
    shape.setPosition(Point(int(x), int(y)))
    shape.setSize(Size(int(width), int(height)))


def _set(shape, **properties):
    for name, value in properties.items():
        shape.setPropertyValue(name, value)


def _text_shape(document, page, text, x, y, width, height, size, colour=BLACK):
    shape = _create(document, "TextShape")
    page.add(shape)
    _place(shape, x, y, width, height)
    shape.setString(text)
    _set(
        shape,
        TextAutoGrowHeight=False,
        TextAutoGrowWidth=False,
        TextLeftDistance=0,
        TextRightDistance=0,
        TextUpperDistance=0,
        TextLowerDistance=0,
        CharHeight=float(size),
        CharColor=colour,
        FillStyle=uno.Enum("com.sun.star.drawing.FillStyle", "NONE"),
        LineStyle=uno.Enum("com.sun.star.drawing.LineStyle", "NONE"),
        TextHorizontalAdjust=uno.Enum(
            "com.sun.star.drawing.TextHorizontalAdjust", "CENTER"
        ),
        TextVerticalAdjust=uno.Enum(
            "com.sun.star.drawing.TextVerticalAdjust", "CENTER"
        ),
    )
    return shape


def _line(document, page, x1, y1, x2, y2, colour=BLACK):
    shape = _create(document, "LineShape")
    page.add(shape)
    # A LineShape's geometry is its bounding box, so a line is drawn from the
    # top-left corner to the bottom-right one.
    _place(shape, x1, y1, x2 - x1, y2 - y1)
    _set(
        shape,
        LineStyle=uno.Enum("com.sun.star.drawing.LineStyle", "SOLID"),
        LineColor=colour,
        LineWidth=0,
    )
    return shape


def draw_state(
    ctx, document, page, centre, texts, diameter=2000, critical=False, number=None
):
    """Draw one three-region event circle and return the grouped shape."""

    x, y = centre
    left = int(x - diameter / 2)
    top = int(y - diameter / 2)
    early, late, event_number = texts
    colour = CRITICAL if critical else BLACK

    collection = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.drawing.ShapeCollection", ctx
    )

    circle = _create(document, "EllipseShape")
    page.add(circle)
    _place(circle, left, top, diameter, diameter)
    _set(
        circle,
        FillStyle=uno.Enum("com.sun.star.drawing.FillStyle", "SOLID"),
        FillColor=WHITE,
        LineStyle=uno.Enum("com.sun.star.drawing.LineStyle", "SOLID"),
        LineColor=colour,
        LineWidth=60 if critical else 0,
    )
    collection.add(circle)

    # The horizontal diameter, and the vertical divider across the upper half only.
    collection.add(_line(document, page, left, y, left + diameter, y, colour))
    collection.add(_line(document, page, x, top, x, y, colour))

    half = diameter // 2
    font = diameter / 250.0  # ~8pt in a 20mm circle, and it scales with the circle
    collection.add(
        _text_shape(document, page, early, left, top, half, half, font)
    )
    collection.add(
        _text_shape(document, page, late, x, top, half, half, font)
    )
    collection.add(
        _text_shape(document, page, event_number, left, y, diameter, half, font)
    )

    group = page.group(collection)
    if number is not None:
        group.Name = f"{EVENT_PREFIX}{number}"
    return group


def draw_action(
    ctx,
    document,
    page,
    start_shape,
    end_shape,
    label="",
    dummy=False,
    critical=False,
    name=None,
):
    """Draw one arrow between two state groups, glued to both."""

    connector = _create(document, "ConnectorShape")
    page.add(connector)
    connector.setPropertyValue("StartShape", start_shape)
    connector.setPropertyValue("EndShape", end_shape)
    # Straight lines: a PERT arrow is a straight arrow, not a routed cable.
    _set(
        connector,
        EdgeKind=uno.Enum("com.sun.star.drawing.ConnectorType", "LINE"),
        LineColor=CRITICAL if critical else BLACK,
        LineWidth=60 if critical else 0,
        LineStyle=uno.Enum(
            "com.sun.star.drawing.LineStyle", "DASH" if dummy else "SOLID"
        ),
    )
    if dummy:
        _set(connector, LineDash=_dash())
    _set(connector, LineEnd=_arrow_head(), LineEndWidth=250, LineEndCenter=False)

    if label:
        connector.setString(label)
        _set(
            connector,
            CharHeight=10.0,
            CharColor=CRITICAL if critical else BLACK,
            CharWeight=150.0 if critical else 100.0,
        )
    if name:
        connector.Name = name
    return connector


def _arrow_head():
    """A filled triangle, defined inline rather than looked up by name.

    The document's marker table names are localised, so asking for "Arrow" works in
    an English UI and quietly does nothing in a Spanish one.
    """
    from com.sun.star.drawing import PolyPolygonBezierCoords
    from com.sun.star.drawing.PolygonFlags import NORMAL

    head = PolyPolygonBezierCoords()
    head.Coordinates = ((Point(0, 0), Point(100, 300), Point(-100, 300)),)
    head.Flags = ((NORMAL, NORMAL, NORMAL),)
    return head


def _dash():
    from com.sun.star.drawing import LineDash
    from com.sun.star.drawing.DashStyle import RECT

    dash = LineDash()
    dash.Style = RECT
    dash.Dots = 0
    dash.Dashes = 1
    dash.DashLen = 200
    dash.Distance = 150
    return dash


def draw_diagram(ctx, document, page, diagram, scale=1.0, offset=(0, 0)):
    """Draw every event and arc of a diagram on `page`.

    `scale` shrinks the whole thing to fit the page (see layout.fit_scale) and
    `offset` moves it; both apply to positions and to the circles alike, so the
    proportions of the drawing never change.

    Returns the state groups by event number, so callers (and tests) can find them.
    """

    style = diagram.placement.style
    critical_events = {
        event
        for event in diagram.network.events
        if diagram.times.is_critical_event(event)
    }

    states = {}
    for event in diagram.network.events:
        x, y = diagram.placement.centre(event)
        states[event] = draw_state(
            ctx,
            document,
            page,
            (x * scale + offset[0], y * scale + offset[1]),
            diagram.state_text(event),
            diameter=max(int(style.circle_diameter * scale), 200),
            critical=event in critical_events,
            number=event,
        )

    dummy_index = 0
    for arc in diagram.network.arcs:
        if arc.dummy:
            dummy_index += 1
            name = f"{DUMMY_PREFIX}{dummy_index}"
        else:
            name = f"{ACTIVITY_PREFIX}{arc.activity}"
        draw_action(
            ctx,
            document,
            page,
            states[arc.tail],
            states[arc.head],
            label=arc.label(),
            dummy=arc.dummy,
            critical=diagram.is_critical_arc(arc),
            name=name,
        )

    return states
