"""R5.3 native Qt/VTK probe. Do not run with offscreen/minimal Qt platform."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time


def _run(path: Path, report: Path) -> int:
    from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from scantopath.modules.viewer3d.presentation.interactive_controller import InteractiveViewer3DController
    from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import CoalescingRenderSession
    from scantopath.ui.components.property_inspector import PropertyInspector
    from scantopath.ui.shell.viewer_inspector_bridge import SceneInspectorBridge

    app = QApplication.instance() or QApplication([])
    if app.platformName().lower() in ('offscreen','minimal'):
        raise RuntimeError('NATIVE_QT_PLATFORM_REQUIRED')
    root = QWidget()
    root.setWindowTitle('ScanToPath - Kiem thu 3D R5.3')
    layout = QHBoxLayout(root)
    inspector = PropertyInspector(root)
    controller = InteractiveViewer3DController(
        root, session_factory=lambda: CoalescingRenderSession(640,480,timeout=45))
    bridge = SceneInspectorBridge(inspector, controller)
    layout.addWidget(controller.page, 4)
    layout.addWidget(inspector, 1)
    root.resize(1100,720)
    root.show()
    original = hashlib.sha256(path.read_bytes()).hexdigest()

    def until(predicate, seconds: float = 60.0):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate(): return
            time.sleep(.015)
        raise TimeoutError('NATIVE_VIEWER_PROBE_TIMEOUT')

    pid = None
    try:
        assert controller.load_ply(path.resolve())
        until(lambda: controller.live_phase == 'ready' and controller._last_frame_revision >= 1, 90)
        pid = controller._live_session.pid
        initial_frame = controller._last_frame_revision
        assert controller._descriptor is not None
        assert controller._descriptor.source_sha256 == original
        assert bridge._owned and inspector.properties_frame.isVisible()
        assert controller.page.preview.pixmap() is not None
        select = controller.tools.findChild(QWidget, 'viewer3dToolSelect')
        assert not select.icon().isNull(), 'SVG_ICON_REQUIRED'
        assert controller.tools.findChild(QWidget, 'viewer3dToolGrid') is not None
        select.click()
        center = QPoint(controller.page.preview.width() // 2, controller.page.preview.height() // 2)
        QTest.mouseClick(controller.page.preview, Qt.LeftButton, Qt.NoModifier, center)
        until(lambda: controller._selected is not None, 30)
        selected = controller._selected
        assert selected.kind == 'face' and selected.source_sha256 == original
        assert selected.scene_revision == controller._expected_scene_revision
        assert inspector.kind_label.text() == 'LỰA CHỌN HÌNH HỌC'
        assert bridge.copy_button.isVisible()
        bridge.copy_button.click()
        assert QApplication.clipboard().text() == ', '.join(repr(x) for x in selected.xyz)
        controller.tools.grid_button.setChecked(False)
        until(lambda: controller._grid_future is None and not controller._grid_enabled, 30)
        frame_after_grid = controller._last_frame_revision
        controller.tools.grid_button.setChecked(True)
        until(lambda: controller._grid_future is None and controller._last_frame_revision > frame_after_grid, 30)
        controller.tools.layer_button.setChecked(False)
        until(lambda: controller._layer_future is None and controller._last_frame_revision > initial_frame, 30)
        hidden_frame = controller._last_frame_revision
        controller.tools.layer_button.setChecked(True)
        until(lambda: controller._layer_future is None and controller._last_frame_revision > hidden_frame, 30)
        assert controller._live_session.pid == pid
        assert hashlib.sha256(path.read_bytes()).hexdigest() == original
        result = {
            'schema':'r5.3-native-probe-v1','status':'PASS','qt_platform':app.platformName(),
            'source_sha256':original,'geometry_kind':'mesh',
            'picked_kind':selected.kind,'picked_element_id':selected.element_id,
            'frame_revision_end':controller._last_frame_revision,
            'host_pid':pid,'host_reused':True,'source_unchanged':True,
            'svg_icons':True,'xy_grid_toggled':True,'copy_xyz':True,
            'not_tested':['true_display_present_latency','native_cpp_fault_injection',
                          'genuinely_native_busy_close','high_dpi_driver_matrix'],
        }
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n',encoding='utf-8')
        print('R5.3 NATIVE PROBE PASS',flush=True)
        return 0
    finally:
        controller._closing = True
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if controller.begin_shutdown():
                controller.dispose()
                break
            app.processEvents()
            time.sleep(.025)
        else:
            raise RuntimeError('RENDER_HOST_TEARDOWN_INCOMPLETE')
        root.close()
        app.processEvents()


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--report', required=True, type=Path)
    opt = args.parse_args()
    with tempfile.TemporaryDirectory(prefix='scantopath-r53-') as folder:
        source = Path(folder) / 'r5_3_square_mesh.ply'
        source.write_text('ply\nformat ascii 1.0\nelement vertex 4\nproperty float x\n'
                          'property float y\nproperty float z\nelement face 1\n'
                          'property list uchar int vertex_indices\nend_header\n'
                          '-1 -1 0\n1 -1 0\n1 1 0\n-1 1 0\n4 0 1 2 3\n',encoding='ascii')
        return _run(source, opt.report)

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('R5.3 NATIVE PROBE FAILED: '+repr(exc),file=sys.stderr,flush=True)
        raise
