"""UXH-01.6: Qt boundary behavior without native VTK or camera."""
from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
from scantopath.ui.shell.geometry_preview import GeometryPreviewBridge
from scantopath.application.preview_scratch_leases import PreviewScratchLeases

class Scratch:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True)
        path.write_bytes(b'fixture')
        self.cleaned = 0
    def cleanup(self):
        self.cleaned += 1
        self.path.unlink()
        self.path.parent.rmdir()

class Viewer:
    def __init__(self, accept=True):
        self.accept = accept
        self._current_source = self._pending_source = self._last_requested_source = None
        self._teardown = None
        self.shutdown_pending = False
    def load_ply(self, path):
        if not self.accept:
            return False
        self._pending_source = self._last_requested_source = Path(path)
        return True

class Measurement:
    def __init__(self): self.unbound = 0
    def unbind(self): self.unbound += 1

def test_protects_current_pending_retry_and_renderer_teardown(tmp_path):
    paths = [tmp_path / n / 'preview.ply' for n in ('a','b')]
    scratches = [Scratch(p) for p in paths]
    pool = PreviewScratchLeases()
    for p, s in zip(paths, scratches): pool.retain(p,s)
    viewer = Viewer()
    viewer._pending_source = paths[0]
    viewer._last_requested_source = paths[0]
    measurement = Measurement()
    bridge = SimpleNamespace(_closing=False,host=SimpleNamespace(viewer3d=viewer),
         _scratch=pool,_receipt=SimpleNamespace(path=paths[0]),
         _measurement_ui=measurement,_sensor_view_token=object())
    viewer._teardown = SimpleNamespace(is_alive=lambda: True)
    GeometryPreviewBridge._reap_retired_scratch(bridge)
    assert len(pool) == 2 and scratches[1].cleaned == 0
    viewer._teardown = None
    GeometryPreviewBridge._reap_retired_scratch(bridge)
    assert len(pool) == 1 and scratches[1].cleaned == 1
    assert bridge._receipt is not None and measurement.unbound == 0
    viewer._pending_source = viewer._last_requested_source = None
    GeometryPreviewBridge._reap_retired_scratch(bridge)
    assert len(pool) == 0 and scratches[0].cleaned == 1
    assert bridge._receipt is None and measurement.unbound == 1

def test_shutdown_defers_release_to_dispose(tmp_path):
    path=tmp_path/'running'/'preview.ply'
    scratch=Scratch(path)
    pool=PreviewScratchLeases();pool.retain(path,scratch)
    bridge=SimpleNamespace(_closing=True,host=SimpleNamespace(viewer3d=None),
        _scratch=pool,_receipt=SimpleNamespace(path=path),_measurement_ui=None)
    GeometryPreviewBridge._reap_retired_scratch(bridge)
    assert scratch.cleaned == 0 and path.exists()
    assert pool.release_all()==0 and not path.exists()

def test_failed_open_cleans_and_successful_open_retains(tmp_path):
    for accept in (False,True):
        path=tmp_path/str(accept)/'preview.ply'
        scratch=Scratch(path)
        ctx=SimpleNamespace(store_root='store',capture_id='c1')
        host=SimpleNamespace(capture_preview=SimpleNamespace(context=ctx),
            project_explorer=SimpleNamespace(store_root='store'),
            workflow_context=None,_navigate=lambda *_:None,viewer3d=Viewer(accept))
        pool=PreviewScratchLeases()
        bridge=SimpleNamespace(host=host,_closing=False,
            _workflow_revision_at_request=None,_receipt=None,_sensor_view_token=None,
            _scratch=pool,_measurement_ui=None,_viewer_label=SimpleNamespace(setText=lambda *_:None),
            _ensure_viewer_label=lambda *_:None,_update_viewer_label=lambda *_:None)
        GeometryPreviewBridge._ready(bridge,SimpleNamespace(path=path),scratch,ctx,object())
        assert (scratch.cleaned==0)==accept
        assert pool.contains(path)==accept
        assert (bridge._receipt is not None)==accept
        assert pool.release_all()==0
