"""UXH-01.7-B source boundary: toolbar/canvas only, no device/RAW/renderer changes."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VIEW = ROOT / 'src/scantopath/modules/viewer3d/presentation/view.py'
INTERACTIVE = ROOT / 'src/scantopath/modules/viewer3d/presentation/interactive_controller.py'
TOOLS = ROOT / 'src/scantopath/modules/viewer3d/presentation/live_tools.py'


def test_stable_entrypoints_and_no_native_import_in_toolbar():
    tools = TOOLS.read_text(encoding='utf-8')
    tree = ast.parse(tools)
    live = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LiveViewerTools')
    methods = {node.name for node in live.body if isinstance(node, ast.FunctionDef)}
    assert {'_grid_menu', '_select_grid_plane', 'set_grid', 'set_layer',
            'reset_layer', 'set_mode'} <= methods
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.startswith(('vtk', 'scantopath.acquisition', 'sqlite3')) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or '').startswith(('vtk', 'scantopath.acquisition', 'sqlite3'))
    assert 'viewer3dToolAdvanced' in tools
    assert 'viewer3dToolGrid' in tools
    assert 'viewer3dToolLayer' in tools


def test_canvas_entrypoint_and_named_layout_dependency():
    view = ast.parse(VIEW.read_text(encoding='utf-8'))
    page = next(n for n in view.body if isinstance(n, ast.ClassDef) and n.name == 'Viewer3DPage')
    names = {n.name for n in page.body if isinstance(n, ast.FunctionDef)}
    assert {'enable_canvas_priority', 'mount_source_info', 'mount_measurement'} <= names
    source = INTERACTIVE.read_text(encoding='utf-8')
    assert 'self.page.enable_canvas_priority()' in source
    assert source.count('self.page.navigation_layout') == 2
    assert 'self.page.layout().itemAt(1).layout()' not in source
