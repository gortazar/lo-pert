"""The extension installs, registers its protocol handler, and answers a command.

A wrong manifest or Addons.xcu produces an extension that installs happily and then
does nothing at all, so "unopkg add succeeded" is not the assertion worth making.
"""


def test_the_protocol_handler_is_registered(office, draw_document):
    frame = draw_document.getCurrentController().getFrame()
    url = office.ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.util.URLTransformer", office.ctx
    )
    from com.sun.star.util import URL

    transformed = URL()
    transformed.Complete = "vnd.gortazar.lopert:About"
    _, transformed = url.parseStrict(transformed)

    assert frame.queryDispatch(transformed, "", 0) is not None


def test_about_reports_the_version(office, draw_document):
    office.dispatch(draw_document, "About")

    dialogs = office.dialogs()
    assert len(dialogs) == 1
    kind, title, message = dialogs[0]
    assert kind == "infobox"
    assert title == "lo-pert"
    assert "lo-pert 0.1" in message


def test_an_unimplemented_command_says_so_rather_than_failing_silently(
    office, draw_document
):
    office.dispatch(draw_document, "InsertState")

    kinds = [dialog[0] for dialog in office.dialogs()]
    assert kinds == ["errorbox"]
