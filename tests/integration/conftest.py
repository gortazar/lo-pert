"""A headless LibreOffice with the built extension installed.

Everything the office needs is set up here rather than in a wrapper script, so
`pytest tests/integration` from the dev shell is all it takes.

Two things are easy to get wrong and expensive to debug:

- soffice must NOT inherit URE_BOOTSTRAP. The client python needs it to bootstrap
  pyuno; the office bootstraps itself, and inheriting the client's value makes it
  abort during startup. The office is therefore spawned with a cleaned environment.
- unopkg has to run *before* the office starts, against the same user profile, or
  the extension is not registered in the session under test.
"""

import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _program_dir():
    soffice = shutil.which("soffice")
    if soffice is None:
        pytest.skip("no soffice on PATH — run inside 'nix develop'")
    program = pathlib.Path(os.path.realpath(soffice)).parent
    if not (program / "uno.py").exists():
        pytest.skip(f"no PyUNO next to {soffice}")
    return program


def _import_uno():
    """Make `import uno` work in this process, using the office's own PyUNO."""
    program = _program_dir()
    if str(program) not in sys.path:
        sys.path.insert(0, str(program))
    os.environ.setdefault(
        "URE_BOOTSTRAP", f"vnd.sun.star.pathname:{program}/fundamentalrc"
    )
    import uno  # noqa: PLC0415 - the path has to be set up first

    return uno


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _office_environment(extra):
    """The environment soffice is started with: ours, minus the PyUNO client bits."""
    env = dict(os.environ)
    for name in ("URE_BOOTSTRAP", "PYTHONPATH", "LD_LIBRARY_PATH", "PYTHONHOME"):
        env.pop(name, None)
    env.update(extra)
    return env


@pytest.fixture(scope="session")
def oxt(tmp_path_factory):
    """The extension, built from the working tree."""
    out = tmp_path_factory.mktemp("dist")
    result = subprocess.run(
        [str(ROOT / "build.sh"), str(out)],
        check=True,
        capture_output=True,
        text=True,
    )
    return pathlib.Path(result.stdout.strip())


class Office:
    """A running headless office with the extension installed."""

    def __init__(self, ctx, dialog_log):
        self.ctx = ctx
        self.dialog_log = dialog_log
        self.desktop = ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", ctx
        )

    def new_document(self, kind="sdraw"):
        return self.desktop.loadComponentFromURL(
            f"private:factory/{kind}", "_blank", 0, ()
        )

    def dispatch(self, document, command, arguments=()):
        """Invoke a menu command exactly as the menu entry does."""
        helper = self.ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.DispatchHelper", self.ctx
        )
        frame = document.getCurrentController().getFrame()
        helper.executeDispatch(
            frame, f"vnd.gortazar.lopert:{command}", "", 0, tuple(arguments)
        )

    def dialogs(self):
        """Every message the extension has shown, as (kind, title, message)."""
        if not self.dialog_log.exists():
            return []
        lines = self.dialog_log.read_text(encoding="utf-8").splitlines()
        dialogs = []
        for line in lines:
            if not line:
                continue
            kind, title, message = line.split("\t", 2)
            dialogs.append(
                (kind, title, message.replace("\\n", "\n").replace("\\\\", "\\"))
            )
        return dialogs

    def clear_dialogs(self):
        self.dialog_log.write_text("", encoding="utf-8")


@pytest.fixture(scope="session")
def office(oxt, tmp_path_factory):
    uno = _import_uno()

    profile = tmp_path_factory.mktemp("profile")
    dialog_log = tmp_path_factory.mktemp("logs") / "dialogs.tsv"
    dialog_log.write_text("", encoding="utf-8")
    env = _office_environment({"LO_PERT_DIALOG_LOG": str(dialog_log)})
    user_installation = f"-env:UserInstallation=file://{profile}"

    install = subprocess.run(
        ["unopkg", "add", "--force", user_installation, str(oxt)],
        env=env,
        capture_output=True,
        text=True,
    )
    if install.returncode != 0:
        pytest.fail(f"unopkg add failed:\n{install.stdout}\n{install.stderr}")

    port = _free_port()
    office_process = subprocess.Popen(
        [
            "soffice",
            "--headless",
            "--norestore",
            "--nologo",
            user_installation,
            f"--accept=socket,host=127.0.0.1,port={port};urp;StarOffice.ServiceManager",
        ],
        env=env,
    )

    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local
    )
    url = f"uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext"

    ctx = None
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if office_process.poll() is not None:
            pytest.fail(f"soffice exited with {office_process.returncode}")
        try:
            ctx = resolver.resolve(url)
            break
        except Exception:  # noqa: BLE001 - the office is simply not up yet
            time.sleep(0.5)
    if ctx is None:
        office_process.terminate()
        pytest.fail("soffice never accepted a UNO connection")

    running = Office(ctx, dialog_log)
    try:
        yield running
    finally:
        try:
            running.desktop.terminate()
        except Exception:  # noqa: BLE001 - the bridge dies with the office
            pass
        try:
            office_process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            office_process.kill()


@pytest.fixture
def draw_document(office):
    """A fresh empty Draw document, closed again afterwards."""
    document = office.new_document("sdraw")
    office.clear_dialogs()
    try:
        yield document
    finally:
        document.close(False)
