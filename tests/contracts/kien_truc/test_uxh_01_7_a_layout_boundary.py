"""UXH-01.7-A source-only tests: Qt-free, no SDK, renderer or project store."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VIEW = ROOT / 'src/scantopath/modules/viewer3d/presentation/view.py'
INTERACTIVE = ROOT / 'src/scantopath/modules/viewer3d/presentation/interactive_controller.py'
PREVIEW = ROOT / 'src/scantopath/modules/capture/presentation/preview_widget.py'
GEOM = ROOT / 'src/scantopath/ui/shell/geometry_preview.py'
MEASURE = ROOT / 'src/scantopath/ui/shell/geometry_measurement.py'


def test_named_slots_exposed_by_actual_widget_owners():
    v = VIEW.read_text(encoding='utf-8')
    p = PREVIEW.read_text(encoding='utf-8')
    for token in ('self.source_info_slot', 'self.measurement_slot',
                  'self.navigation_layout', 'def mount_source_info(',
                  'def mount_measurement('):
        assert token in v, token
    for token in ('self.replay_action_slot', 'def mount_replay_action('):
        assert token in p, token


def test_consumers_only_use_named_integration_contracts():
    c = INTERACTIVE.read_text(encoding='utf-8')
    g = GEOM.read_text(encoding='utf-8')
    m = MEASURE.read_text(encoding='utf-8')
    assert c.count('nav = self.page.navigation_layout') == 2
    assert 'self.page.layout().itemAt(1)' not in c
    assert 'panel.mount_replay_action(self.button)' in g
    assert 'viewer.page.mount_source_info(label)' in g
    assert 'viewer.page.mount_measurement(self.panel)' in m
    assert 'header.insertWidget(' not in g
    assert 'viewer.page.layout().insertWidget(' not in (g + m)


def test_presentation_remains_native_free():
    for path in (VIEW, INTERACTIVE, PREVIEW, GEOM, MEASURE):
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                imports = [node.module or '']
            else:
                continue
            assert not any(x == 'vtk' or x.startswith('vtkmodules') for x in imports), path


def test_replay_and_measurement_are_still_in_place():
    v = VIEW.read_text(encoding='utf-8')
    p = PREVIEW.read_text(encoding='utf-8')
    m = MEASURE.read_text(encoding='utf-8')
    assert v.index('outer.addLayout(self.source_info_slot)') < v.index('outer.addLayout(self.measurement_slot)')
    assert v.index('outer.addLayout(self.measurement_slot)') < v.index('outer.addLayout(nav_row)')
    assert p.index('header.addLayout(self.replay_action_slot)') < p.index('header.addWidget(self.replay_button)')
    assert 'uxhDepthTwoPointButton' in m
    assert 'gd2GeometryMeasurementPanel' in m
