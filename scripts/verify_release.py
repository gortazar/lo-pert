"""Drive an office that has the released extension installed. See verify-release.sh."""

import os
import sys

import uno

TABLE = [
    ("A", 3.0, ""),
    ("B", 4.0, ""),
    ("C", 2.0, "A"),
    ("D", 5.0, "A"),
    ("E", 4.0, "C, D"),
    ("F", 3.0, "B"),
]


def main():
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local
    )
    port = os.environ.get("LO_PERT_PORT", "2002")
    ctx = resolver.resolve(
        f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext"
    )
    desktop = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", ctx
    )

    calc = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, ())
    sheet = calc.getSheets().getByIndex(0)
    for row, (identifier, duration, predecessors) in enumerate(TABLE):
        sheet.getCellByPosition(0, row).setString(identifier)
        sheet.getCellByPosition(1, row).setValue(duration)
        sheet.getCellByPosition(2, row).setString(predecessors)
    calc.getCurrentController().select(
        sheet.getCellRangeByPosition(0, 0, 2, len(TABLE) - 1)
    )

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

    enumeration = desktop.getComponents().createEnumeration()
    while enumeration.hasMoreElements():
        candidate = enumeration.nextElement()
        if candidate.supportsService("com.sun.star.drawing.DrawingDocument"):
            page = candidate.getDrawPages().getByIndex(0)
            names = [page.getByIndex(i).Name for i in range(page.getCount())]
            states = [name for name in names if name.startswith("lopert.event.")]
            activities = [name for name in names if name.startswith("lopert.activity.")]
            print(f"drawn: {len(states)} states, {len(activities)} activities")
            if len(activities) != len(TABLE):
                print("wrong number of activities drawn", file=sys.stderr)
                return 1
            return 0

    print("the installed extension drew nothing", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
