"""What each menu entry does. Called from lopert_handler.LoPertHandler.dispatch."""

from lopert import dialogs

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
    raise CommandError("lo-pert", "not implemented yet")


def insert_state(ctx, frame):
    raise CommandError("lo-pert", "not implemented yet")


def insert_action(ctx, frame):
    raise CommandError("lo-pert", "not implemented yet")


COMMANDS = {
    "About": about,
    "GenerateDiagram": generate_diagram,
    "InsertState": insert_state,
    "InsertAction": insert_action,
}
