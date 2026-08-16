"""What each menu entry does. Called from lopert_handler.LoPertHandler.dispatch."""

from lopert import dialogs, documents, drawing
from lopert.diagram import diagram_from_rows
from lopert.layout import fit_scale
from lopert.table import TableValidationError

VERSION = "0.1"

ABOUT_TEXT = (
    "lo-pert {version}\n\n"
    "PERT (activity-on-arrow) diagrams for LibreOffice Draw and Impress.\n"
    "States are three-region circles: early time, late time, event number.\n"
    "Actions are labelled connectors between them.\n\n"
    "https://github.com/gortazar/lo-pert"
).format(version=VERSION)


class CommandError(Exception):
    """A failure worth showing the user as a plain message, not a traceback."""

    def __init__(self, title, message):
        self.title = title
        self.message = message
        super().__init__(f"{title}: {message}")


def run(ctx, frame, command):
    """Dispatch one vnd.gortazar.lopert: URL path."""

    handler = COMMANDS.get(command)
    if handler is None:
        raise CommandError("lo-pert", f"unknown command {command!r}")
    try:
        handler(ctx, frame)
    except CommandError as error:
        dialogs.show_error(ctx, frame, error.title, error.message)


def report_error(ctx, frame, title, message):
    dialogs.show_error(ctx, frame, title, message)


def about(ctx, frame):
    dialogs.show_message(ctx, frame, "lo-pert", ABOUT_TEXT)


def generate_diagram(ctx, frame):
    """Read the selected precedence table and draw its network."""

    try:
        spreadsheet = documents.find_spreadsheet(ctx, frame)
        rows = documents.selected_cells(spreadsheet)
    except documents.NoTableError as error:
        raise CommandError("lo-pert — no precedence table", str(error)) from error

    try:
        diagram = diagram_from_rows(rows)
    except TableValidationError as error:
        raise CommandError(
            "lo-pert — the precedence table has errors",
            "Nothing was drawn. Fix these and run the command again:\n\n"
            + "\n".join(str(problem) for problem in error.errors),
        ) from error

    document, created = documents.drawing_document(ctx, frame)
    page = documents.target_page(document)
    if created:
        # Our own new document: give it a page the diagram fits on at full size,
        # rather than shrinking a wide network onto a portrait A4.
        width, height = documents.resize_page(
            page,
            diagram.width + 2 * diagram.placement.style.margin,
            diagram.height + 2 * diagram.placement.style.margin,
        )
    else:
        width, height = documents.page_size(page)
    scale = fit_scale(diagram.width, diagram.height, width, height)
    offset = (
        (width - diagram.width * scale) / 2,
        (height - diagram.height * scale) / 2,
    )

    drawing.draw_diagram(ctx, document, page, diagram, scale=scale, offset=offset)
    _bring_to_front(document, page)


def _bring_to_front(document, page):
    """Show the page that was just drawn on, if its window is around."""
    try:
        controller = document.getCurrentController()
        controller.setCurrentPage(page)
        controller.getFrame().getContainerWindow().toFront()
    except Exception:  # noqa: BLE001 - headless, or no window: nothing to raise about
        pass


def _drawing_target(ctx, frame):
    document = documents.current_document(ctx, frame)
    if not (
        document.supportsService(documents.DRAW)
        or document.supportsService(documents.IMPRESS)
    ):
        raise CommandError(
            "lo-pert",
            "This command draws on a page, so run it from a Draw or Impress "
            "document.",
        )
    page = document.getCurrentController().getCurrentPage()
    return document, page


def _next_event_number(page):
    numbers = [0]
    for index in range(page.getCount()):
        name = page.getByIndex(index).Name
        if name.startswith(drawing.EVENT_PREFIX):
            suffix = name[len(drawing.EVENT_PREFIX) :]
            if suffix.isdigit():
                numbers.append(int(suffix))
    return max(numbers) + 1


def insert_state(ctx, frame):
    """Insert one state circle in the middle of the page, ready to be edited."""

    document, page = _drawing_target(ctx, frame)
    number = _next_event_number(page)
    drawing.draw_state(
        ctx,
        document,
        page,
        (page.Width / 2, page.Height / 2),
        ("0", "0", str(number)),
        number=number,
    )


def insert_action(ctx, frame):
    """Join the two selected states with a labelled arrow."""

    document, page = _drawing_target(ctx, frame)
    selection = document.getCurrentController().getSelection()
    shapes = (
        [selection.getByIndex(index) for index in range(selection.getCount())]
        if selection is not None and hasattr(selection, "getCount")
        else []
    )
    states = [shape for shape in shapes if shape.Name.startswith(drawing.EVENT_PREFIX)]
    if len(states) != 2:
        raise CommandError(
            "lo-pert",
            "Select exactly two states — the one the action starts at and the one "
            "it ends at — then run this command.",
        )

    # The arrow runs left to right, whichever order they were selected in.
    states.sort(key=lambda shape: shape.getPosition().X)
    start, end = states
    drawing.draw_action(
        ctx,
        document,
        page,
        start,
        end,
        label="A(1)",
        name=f"{drawing.ACTIVITY_PREFIX}{start.Name}-{end.Name}",
    )


COMMANDS = {
    "About": about,
    "GenerateDiagram": generate_diagram,
    "InsertState": insert_state,
    "InsertAction": insert_action,
}
