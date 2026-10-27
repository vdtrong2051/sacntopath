"""R5.2 Windows native GUI integration test; never edits real user geometry."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--evidence-dir', required=True, type=Path)
    p.add_argument('--manual', action='store_true')
    args = p.parse_args()
    if os.environ.get('QT_QPA_PLATFORM', '').lower() in ('offscreen', 'minimal'):
        raise RuntimeError('NATIVE_WINDOWS_QT_PLATFORM_REQUIRED')
    folder = args.evidence_dir.resolve()
    if folder.is_symlink():
        raise ValueError('UNSAFE_EVIDENCE_DIR')
    folder.mkdir(parents=True, exist_ok=True)
    stamp = str(int(time.time() * 1000))
    fixture = folder / ('R52_POINTS_' + stamp + '.ply')
    obj = folder / ('R52_MESH_' + stamp + '.obj')
    fixture.write_bytes((
        b'ply\nformat ascii 1.0\nelement vertex 4\nproperty float x\n'
        b'property float y\nproperty float z\nend_header\n'
        b'0 0 0\n1 0 0\n0 1 0\n0 0 1\n'
    ))
    obj.write_bytes(b'v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\n')
    source_checksums = {str(f.name): hashlib.sha256(f.read_bytes()).hexdigest()
                        for f in (fixture, obj)}

    from PySide6.QtCore import Qt, QPointF, QCoreApplication, QEvent
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    from scantopath.ui.shell.main_window import ScanToPathMainWindow
    from scantopath.application.contracts import WorkspaceId
    from scantopath.modules.viewer3d.presentation.live_controller import LiveViewer3DController

    app = QApplication.instance() or QApplication([])
    if app.platformName().lower() in ('offscreen', 'minimal'):
        raise RuntimeError('NATIVE_DISPLAY_REQUIRED')
    window = ScanToPathMainWindow()
    report = {'schema': 'r5.2-native-gui-v1', 'status': 'INCOMPLETE',
              'platform': app.platformName(), 'native_busy_close_proven': False,
              'real_display_present_latency': 'NOT_MEASURED',
              'picking': 'DEFERRED_R5_3'}

    def until(predicate, seconds=60.0):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate():
                return True
            time.sleep(.015)
        return False

    try:
        window.show()
        window._navigate(WorkspaceId.INSPECT3D)
        viewer = window.viewer3d
        assert isinstance(viewer, LiveViewer3DController), 'PRODUCTION_COMPOSITION_NOT_LIVE'
        assert viewer.page.preview.objectName() == 'viewer3dPreview'
        assert viewer.load_ply(fixture)
        assert until(lambda: viewer.live_phase == 'ready' and viewer.frames_presented_to_qt >= 1), 'POINT_OPEN_TIMEOUT'
        original_session = viewer._live_session
        original_pid = original_session.pid
        original_frames = viewer.frames_presented_to_qt
        widget = viewer.page.preview
        widget.resize(640, 480)
        app.processEvents()

        def send(kind, x, y, button, buttons):
            pos = QPointF(float(x), float(y))
            ev = QMouseEvent(kind, pos, button, buttons, Qt.NoModifier)
            QCoreApplication.sendEvent(widget, ev)
            app.processEvents()

        send(QEvent.MouseButtonPress, 180, 150, Qt.LeftButton, Qt.LeftButton)
        for i in range(10):
            send(QEvent.MouseMove, 185 + i * 5, 153 + i * 2, Qt.NoButton, Qt.LeftButton)
            until(lambda: viewer.frames_presented_to_qt > original_frames, seconds=5)
        before_release = viewer.frames_presented_to_qt
        assert before_release > original_frames, 'NO_LIVE_FRAME_DURING_DRAG'
        send(QEvent.MouseButtonRelease, 230, 171, Qt.LeftButton, Qt.NoButton)
        assert viewer._live_session.pid == original_pid
        report['drag_frames_before_release'] = before_release - original_frames
        report['resident_pid_reused_during_drag'] = True
        assert viewer.load_ply(obj)
        assert until(lambda: viewer.live_phase == 'ready' and viewer._descriptor is not None
                     and viewer._descriptor.geometry_kind == 'mesh'), 'OBJ_SWITCH_TIMEOUT'
        report['obj_mesh_faces'] = viewer._descriptor.face_count
        assert viewer._descriptor.face_count == 1
        assert viewer._live_session is not original_session, 'SOURCE_SWITCH_DID_NOT_REPLACE_SESSION'
        assert original_session.pid is None, 'OLD_RENDER_HOST_NOT_REAPED'
        # Controlled host termination: do not confuse with native C++ segfault.
        child = viewer._live_session._client._proc
        assert child is not None
        child.kill()
        child.wait(timeout=10)
        assert until(lambda: viewer.retry_button.isEnabled(), seconds=25), 'HOST_LOSS_NOT_HANDLED'
        viewer.retry()
        assert until(lambda: viewer.live_phase == 'ready' and viewer._descriptor.geometry_kind == 'mesh',
                     seconds=90), 'HOST_RETRY_FAILED'
        report['controlled_host_loss_recovered'] = True
        if args.manual:
            print('R5.2 HMI: perform orbit/pan/zoom, then close the window.', flush=True)
            until(lambda: not window.isVisible(), seconds=1800)
        window.close()
        assert until(lambda: not window.isVisible(), seconds=40), 'WINDOW_CLOSE_ORPHAN_GATE_FAILED'
        report['window_close_accepted'] = True
        report['source_unchanged'] = all(
            hashlib.sha256(f.read_bytes()).hexdigest() == source_checksums[f.name]
            for f in (fixture, obj))
        assert report['source_unchanged']
        report['status'] = 'NATIVE_SMOKE_PASS'
    finally:
        # Do not turn a lifecycle failure into success. Keep the process alive until
        # the guarded close can reap the child; on failure, log and exit nonzero.
        if window.isVisible():
            window.close()
            until(lambda: not window.isVisible(), seconds=20)
        report['completed_at_utc'] = __import__('datetime').datetime.now(
            __import__('datetime').timezone.utc).isoformat()
        output = folder / ('R5_2_NATIVE_' + stamp + '.json')
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        (folder / 'R5_2_NATIVE_LATEST.json').write_text(json.dumps(
            {'report': output.name, 'status': report['status']}, indent=2) + '\n', encoding='ascii')
        print('R5.2 native report:', output, report['status'], flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('R5.2 NATIVE FAILED: ' + repr(exc), file=sys.stderr, flush=True)
        raise SystemExit(2)
