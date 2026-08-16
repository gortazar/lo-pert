"""The core must stay importable without LibreOffice.

If a UNO import creeps into one of these modules, every unit test starts needing an
office to run, which is exactly the trade the plan refuses to make.
"""

import ast
import pathlib

CORE = ["table.py", "network.py", "times.py", "layout.py", "diagram.py"]
SOURCE = pathlib.Path(__file__).resolve().parents[2] / "src" / "lopert"


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_the_core_imports_no_uno():
    for name in CORE:
        for module in imported_modules(SOURCE / name):
            root = module.split(".")[0]
            assert root not in {"uno", "unohelper", "com"}, f"{name} imports {module}"


def test_the_core_modules_all_exist():
    for name in CORE:
        assert (SOURCE / name).exists()
