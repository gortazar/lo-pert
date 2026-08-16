"""Message boxes — the one part of the UI that has to talk to the toolkit.

Headless LibreOffice has no one to click OK, so a dialog there would hang the
integration tests forever. When LO_PERT_DIALOG_LOG names a file, dialogs are appended
to it instead of shown; that is exactly what the tests read back to assert on the
error a bad table produces.
"""

import os

MESSAGE_LOG_VARIABLE = "LO_PERT_DIALOG_LOG"


def _log_target():
    return os.environ.get(MESSAGE_LOG_VARIABLE)


def show_message(ctx, frame, title, message, kind="infobox"):
    """Show a message box, or log it when dialogs are suppressed."""

    target = _log_target()
    if target:
        # One dialog per line, so a multi-line message has to be escaped: most of
        # them are multi-line, and a reader splitting on newlines would otherwise
        # see one dialog as several.
        escaped = message.replace("\\", "\\\\").replace("\n", "\\n")
        with open(target, "a", encoding="utf-8") as log:
            log.write(f"{kind}\t{title}\t{escaped}\n")
        return

    # Imported lazily so the module can be imported (and its logging path tested)
    # without a UNO bridge.
    from com.sun.star.awt.MessageBoxButtons import BUTTONS_OK
    from com.sun.star.awt.MessageBoxType import ERRORBOX, INFOBOX

    toolkit = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.awt.Toolkit", ctx
    )
    parent = frame.getContainerWindow() if frame is not None else None
    box = toolkit.createMessageBox(
        parent,
        ERRORBOX if kind == "errorbox" else INFOBOX,
        BUTTONS_OK,
        title,
        message,
    )
    try:
        box.execute()
    finally:
        box.dispose()


def show_error(ctx, frame, title, message):
    show_message(ctx, frame, title, message, kind="errorbox")
