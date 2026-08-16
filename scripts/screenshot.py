"""Render the worked example to screenshots/, using the extension itself.

    ./scripts/with-soffice.sh python3 scripts/screenshot.py

Drives a headless office over the UNO bridge exactly as the integration tests do:
fills a Calc sheet with the README's example, dispatches the generate command, and
exports the resulting page as PNG. The pictures in the README are therefore produced
by the shipped code, not drawn by hand.
"""

import os
import pathlib
import sys

import uno
from com.sun.star.beans import PropertyValue

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHOTS = ROOT / "screenshots"

EXAMPLE = [
    ["Activity", "Duration", "Predecessors"],
    ["A", 3.0, ""],
    ["B", 4.0, ""],
    ["C", 2.0, "A"],
    ["D", 5.0, "A"],
    ["E", 4.0, "C, D"],
    ["F", 3.0, "B"],
]


def connect(port):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local
    )
    return resolver.resolve(
        f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext"
    )


def properties(**values):
    result = []
    for name, value in values.items():
        item = PropertyValue()
        item.Name = name
        item.Value = value
        result.append(item)
    return tuple(result)


def main():
    ctx = connect(os.environ.get("LO_PERT_PORT", "2002"))
    desktop = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", ctx
    )
    SHOTS.mkdir(exist_ok=True)

    calc = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, ())
    sheet = calc.getSheets().getByIndex(0)
    for row, cells in enumerate(EXAMPLE):
        for column, value in enumerate(cells):
            cell = sheet.getCellByPosition(column, row)
            if isinstance(value, float):
                cell.setValue(value)
            else:
                cell.setString(value)
    selection = sheet.getCellRangeByPosition(0, 0, 2, len(EXAMPLE) - 1)
    calc.getCurrentController().select(selection)

    # A registration problem shows up as a diagram that silently never appears, so
    # check the handler is there before blaming the drawing code.
    from com.sun.star.util import URL

    transformer = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.util.URLTransformer", ctx
    )
    url = URL()
    url.Complete = "vnd.gortazar.lopert:GenerateDiagram"
    _, url = transformer.parseStrict(url)
    frame = calc.getCurrentController().getFrame()
    print("handler registered:", frame.queryDispatch(url, "", 0) is not None)

    helper = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.DispatchHelper", ctx
    )
    helper.executeDispatch(
        calc.getCurrentController().getFrame(),
        "vnd.gortazar.lopert:GenerateDiagram",
        "",
        0,
        (),
    )

    drawing = None
    enumeration = desktop.getComponents().createEnumeration()
    while enumeration.hasMoreElements():
        candidate = enumeration.nextElement()
        if candidate.supportsService("com.sun.star.drawing.DrawingDocument"):
            drawing = candidate
            break
    if drawing is None:
        print("no diagram was drawn", file=sys.stderr)
        return 1

    page = drawing.getDrawPages().getByIndex(0)
    print("shapes drawn:", page.getCount())

    target = SHOTS / "worked-example.png"
    drawing.getCurrentController().select(page)
    drawing.storeToURL(
        f"file://{target}",
        properties(
            FilterName="draw_png_Export",
            FilterData=properties(PixelWidth=1600, PixelHeight=1130),
        ),
    )
    print("wrote", target)

    calc.storeToURL(f"file://{SHOTS / 'precedence-table.png'}", properties(
        FilterName="calc_png_Export",
    ))

    drawing.close(False)
    calc.close(False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
