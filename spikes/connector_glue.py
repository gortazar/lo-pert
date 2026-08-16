"""M0 spike: does a ConnectorShape stay glued to a *grouped* shape?

The state shape is a group (ellipse + dividers + three text shapes), and the whole
design of the action shape rests on a real ConnectorShape binding two of those groups
so the arrow follows when either is dragged. If groups cannot be connector endpoints,
the state shape has to become a single custom shape instead — better to find out now
than in M4.

Run with scripts/with-soffice.sh (which starts a headless soffice and exports the
bootstrap variables):

    ./scripts/with-soffice.sh python3 spikes/connector_glue.py
"""

import sys

import uno
from com.sun.star.awt import Point, Size


def connect(port=2002):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local
    )
    return resolver.resolve(
        f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext"
    )


def make_shape(doc, service):
    return doc.createInstance(f"com.sun.star.drawing.{service}")


def state_group(ctx, doc, page, x, y, size=2500):
    """A three-region event circle, grouped."""
    # ShapeCollection comes from the service manager, not the document.
    shapes = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.drawing.ShapeCollection", ctx
    )

    circle = make_shape(doc, "EllipseShape")
    circle.setPosition(Point(x, y))
    circle.setSize(Size(size, size))
    page.add(circle)
    shapes.add(circle)

    # Horizontal diameter, then a vertical divider through the upper half only.
    across = make_shape(doc, "LineShape")
    page.add(across)
    across.setPosition(Point(x, y + size // 2))
    across.setSize(Size(size, 0))
    shapes.add(across)

    down = make_shape(doc, "LineShape")
    page.add(down)
    down.setPosition(Point(x + size // 2, y))
    down.setSize(Size(0, size // 2))
    shapes.add(down)

    for text, px, py, w, h in (
        ("0", x, y, size // 2, size // 2),
        ("0", x + size // 2, y, size // 2, size // 2),
        ("1", x, y + size // 2, size, size // 2),
    ):
        label = make_shape(doc, "TextShape")
        page.add(label)
        label.setPosition(Point(px, py))
        label.setSize(Size(w, h))
        label.setString(text)
        shapes.add(label)

    return page.group(shapes)


def main():
    ctx = connect()
    desktop = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", ctx
    )
    doc = desktop.loadComponentFromURL(
        "private:factory/sdraw", "_blank", 0, ()
    )
    page = doc.getDrawPages().getByIndex(0)

    a = state_group(ctx, doc, page, 2000, 5000)
    b = state_group(ctx, doc, page, 12000, 5000)
    print("groups:", a.getShapeType(), b.getShapeType())

    connector = make_shape(doc, "ConnectorShape")
    page.add(connector)
    connector.setPropertyValue("StartShape", a)
    connector.setPropertyValue("StartGluePointIndex", 2)  # right edge
    connector.setPropertyValue("EndShape", b)
    connector.setPropertyValue("EndGluePointIndex", 0)  # left edge
    connector.setString("A(3)")

    print("StartShape reads back:", connector.getPropertyValue("StartShape") is not None)
    before = (connector.getPropertyValue("StartPosition"), connector.getPropertyValue("EndPosition"))
    print("endpoints before:", before[0].X, before[0].Y, "->", before[1].X, before[1].Y)

    # The whole question: move the group, does the connector follow?
    b.setPosition(Point(12000, 12000))
    after = (connector.getPropertyValue("StartPosition"), connector.getPropertyValue("EndPosition"))
    print("endpoints after: ", after[0].X, after[0].Y, "->", after[1].X, after[1].Y)

    glued = after[1].Y != before[1].Y
    print("GLUED TO GROUP:", glued)

    # Does a group survive round-tripping through .odg, connector included?
    doc.storeToURL("file:///tmp/lopert-spike.odg", ())
    doc.close(False)

    reopened = desktop.loadComponentFromURL("file:///tmp/lopert-spike.odg", "_blank", 0, ())
    page = reopened.getDrawPages().getByIndex(0)
    print("shapes on reopened page:", page.getCount())
    for i in range(page.getCount()):
        shape = page.getByIndex(i)
        print("  ", shape.getShapeType(), getattr(shape, "getCount", lambda: "")())
    reopened.close(False)

    return 0 if glued else 1


if __name__ == "__main__":
    sys.exit(main())
