"""Finding the table to read and the page to draw on.

The precedence table lives in Calc and the diagram belongs in Draw or Impress, so the
generate command nearly always spans two documents. The rules, in order:

    the table   — the current document if it is a spreadsheet, otherwise the first
                  open spreadsheet
    the page    — the current page if the current document draws, otherwise the first
                  open Draw or Impress document, otherwise a new Draw document; and
                  if that page already has shapes on it, a new page after it

Predictable, and never silently on top of someone's work.
"""

from __future__ import annotations

CALC = "com.sun.star.sheet.SpreadsheetDocument"
DRAW = "com.sun.star.drawing.DrawingDocument"
IMPRESS = "com.sun.star.presentation.PresentationDocument"


class NoTableError(Exception):
    """No spreadsheet to read a precedence table from."""


def desktop(ctx):
    return ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.frame.Desktop", ctx
    )


def _supports(document, service):
    try:
        return document.supportsService(service)
    except AttributeError:
        return False


def open_documents(ctx):
    enumeration = desktop(ctx).getComponents().createEnumeration()
    while enumeration.hasMoreElements():
        yield enumeration.nextElement()


def current_document(ctx, frame):
    if frame is not None:
        controller = frame.getController()
        if controller is not None:
            return controller.getModel()
    return desktop(ctx).getCurrentComponent()


def find_spreadsheet(ctx, frame):
    """The document holding the precedence table."""
    document = current_document(ctx, frame)
    if _supports(document, CALC):
        return document
    for candidate in open_documents(ctx):
        if _supports(candidate, CALC):
            return candidate
    raise NoTableError(
        "lo-pert reads the precedence table from a Calc sheet, and no spreadsheet "
        "is open.\n\nPut the activities in three columns — identifier, duration, "
        "immediate predecessors — select them, and run the command again."
    )


def selected_cells(spreadsheet):
    """The selected range as rows of cell values.

    A selection of one cell means "the block I am standing in": Calc's own current
    region, which is what a user who clicked once into their table expects.
    """
    selection = spreadsheet.getCurrentSelection()
    if selection is None:
        raise NoTableError("nothing is selected in the spreadsheet")

    if _supports(selection, "com.sun.star.sheet.SheetCellRanges"):
        if selection.getCount() == 0:
            raise NoTableError("nothing is selected in the spreadsheet")
        selection = selection.getByIndex(0)

    if _supports(selection, "com.sun.star.sheet.SheetCell"):
        sheet = selection.getSpreadsheet()
        cursor = sheet.createCursorByRange(selection)
        cursor.collapseToCurrentRegion()
        selection = cursor
    elif not _supports(selection, "com.sun.star.sheet.SheetCellRange"):
        raise NoTableError(
            "select the cells holding the precedence table before running the command"
        )

    return [list(row) for row in selection.getDataArray()]


def drawing_document(ctx, frame):
    """The document to draw in, creating a Draw document if there is none."""
    document = current_document(ctx, frame)
    if _supports(document, DRAW) or _supports(document, IMPRESS):
        return document
    for candidate in open_documents(ctx):
        if _supports(candidate, DRAW) or _supports(candidate, IMPRESS):
            return candidate
    return desktop(ctx).loadComponentFromURL(
        "private:factory/sdraw", "_blank", 0, ()
    )


def _current_page(document):
    try:
        return document.getCurrentController().getCurrentPage()
    except AttributeError:
        return None


def target_page(document):
    """An empty page to draw on: the current one if it is empty, else a new one."""
    pages = document.getDrawPages()
    page = _current_page(document)
    if page is None:
        page = pages.getByIndex(0)
    if page.getCount() == 0:
        return page

    index = 0
    for position in range(pages.getCount()):
        if pages.getByIndex(position) == page:
            index = position
            break
    pages.insertNewByIndex(index + 1)
    fresh = pages.getByIndex(index + 1)
    try:
        document.getCurrentController().setCurrentPage(fresh)
    except AttributeError:
        pass
    return fresh


def page_size(page):
    return page.Width, page.Height
