"""UXH-01.1: SQL and snapshot responsibilities cannot drift into Qt Shell."""
from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]


def _scan(root):
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from check_architecture_boundaries import scan
        return scan(root)
    finally:
        sys.path.remove(str(ROOT / "scripts"))


def test_shell_rejects_sqlite_imports_including_nested_and_from(tmp_path):
    location = tmp_path / "src" / "scantopath" / "ui" / "shell"
    location.mkdir(parents=True)
    (location / "bad.py").write_text(
        "import sqlite3\ndef sneak():\n    from sqlite3 import connect\n",
        encoding="utf-8",
    )
    found = _scan(tmp_path)
    assert ("ui/shell/bad.py", 1, "sqlite3") in found
    assert ("ui/shell/bad.py", 3, "sqlite3") in found


def test_feature_presentation_rejects_sqlite(tmp_path):
    location = tmp_path / "src" / "scantopath" / "modules" / "fake" / "presentation"
    location.mkdir(parents=True)
    (location / "bad.py").write_text("import sqlite3\n", encoding="utf-8")
    assert ("modules/fake/presentation/bad.py", 1, "sqlite3") in _scan(tmp_path)


def test_geometry_shell_has_no_snapshot_writer_or_file_io():
    p = ROOT / "src/scantopath/ui/shell/geometry_preview.py"
    tree = ast.parse(p.read_text(encoding="utf-8"))
    forbidden_functions = {"snapshot_capture", "write_preview_ply"}
    assert not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and
                   n.name in forbidden_functions for n in ast.walk(tree))
    # Qt Signal.connect(slot) is valid presentation work; SQLite imports are
    # prohibited by the AST architecture scanner and negative tests above.
    forbidden_calls = {"backup", "read_bytes", "write_bytes", "open", "mkdir"}
    calls = [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and
             isinstance(n.func, ast.Attribute)]
    assert not forbidden_calls.intersection(calls)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.Import) for n in n.names}
    assert "sqlite3" not in names


def test_existing_repo_import_gate_stays_clean():
    assert _scan(ROOT) == []
