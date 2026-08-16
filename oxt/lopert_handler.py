"""The extension's UNO entry point: a protocol handler for vnd.gortazar.lopert: URLs.

Every menu entry in Addons.xcu dispatches one of those URLs; this component turns it
into a call into the `lopert` package, which LibreOffice's python loader makes
importable by putting the extension's pythonpath/ directory on sys.path.

Deliberately thin. Anything worth testing lives in lopert.* — this file only routes,
and reports failures as a dialog instead of a traceback nobody sees.
"""

import traceback

import unohelper
from com.sun.star.frame import XDispatch, XDispatchProvider
from com.sun.star.lang import XInitialization, XServiceInfo

IMPLEMENTATION_NAME = "com.github.gortazar.lopert.ProtocolHandler"
PROTOCOL = "vnd.gortazar.lopert:"


class LoPertHandler(
    unohelper.Base, XServiceInfo, XDispatchProvider, XDispatch, XInitialization
):
    def __init__(self, ctx):
        self.ctx = ctx
        self.frame = None

    # XInitialization — the frame the menu was invoked from.
    def initialize(self, args):
        if args:
            self.frame = args[0]

    # XServiceInfo
    def getImplementationName(self):
        return IMPLEMENTATION_NAME

    def supportsService(self, name):
        return name == "com.sun.star.frame.ProtocolHandler"

    def getSupportedServiceNames(self):
        return ("com.sun.star.frame.ProtocolHandler",)

    # XDispatchProvider
    def queryDispatch(self, url, target_frame_name, search_flags):
        if url.Protocol == PROTOCOL:
            return self
        return None

    def queryDispatches(self, requests):
        return tuple(
            self.queryDispatch(r.FeatureURL, r.FrameName, r.SearchFlags)
            for r in requests
        )

    # XDispatch
    def dispatch(self, url, arguments):
        from lopert import commands

        try:
            commands.run(self.ctx, self.frame, url.Path)
        except Exception:  # noqa: BLE001 - a traceback in the console helps nobody
            commands.report_error(
                self.ctx,
                self.frame,
                "lo-pert failed",
                traceback.format_exc(),
            )

    def addStatusListener(self, listener, url):
        pass

    def removeStatusListener(self, listener, url):
        pass


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    LoPertHandler, IMPLEMENTATION_NAME, ("com.sun.star.frame.ProtocolHandler",)
)
