"""Qt offscreen UI contracts for 07.6, operator Windows/PySide6 required."""
from __future__ import annotations
import os
import time

import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from scantopath.ui.shell import ScanToPathMainWindow
from scantopath.metadata.store import MetadataStore
from scantopath.storage.session_store import SessionStore
from scantopath.acquisition.sources import SyntheticSource


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    w = ScanToPathMainWindow()
    w.show()
    qapp.processEvents()
    yield w
    w.close()
    wait(qapp, lambda: not w.project_loader.busy and not w.project_writer.busy and not w.capture_checker.busy)
    wait(qapp, lambda: not w.task_controller.manager.worker_alive)


def wait(app, check, timeout=8):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        app.processEvents()
        if check():
            app.processEvents()
            return
        time.sleep(.01)
    raise AssertionError("Qt operation timed out")


def prepare(root):
    with MetadataStore(root) as store:
        store.create_project("p", "Thử nghiệm")
        store.create_specimen("s", "p", "Vật mẫu")
        store.create_scan_session("t", "s", "Lần 1")
    cap = SessionStore(root).commit(SyntheticSource().capture(), "t", "s")
    with MetadataStore(root) as store:
        row = store.register_capture(cap)
        store.create_processing_run(run_id="run1", session_id="t", stage="metadata-check",
                                    algorithm="fixture", version="1", input_capture_ids=[row["capture_id"]])
    return row


def load(w, app, root):
    w._begin_project_load(str(root))
    wait(app, lambda: not w.project_loader.busy)


def test_no_auto_sqlite_or_verification_on_start(window, tmp_path):
    assert window.project_explorer.store_root is None
    assert window.task_event_panel.audit_table.topLevelItemCount() == 0
    assert not window.property_inspector.verify_button.isEnabled()
    assert not (tmp_path / "metadata.sqlite3").exists()


def test_history_run_audit_and_capture_validation(window, qapp, tmp_path):
    row = prepare(tmp_path)
    load(window, qapp, tmp_path)
    sess = window.project_explorer.tree.topLevelItem(0).child(0).child(0)
    assert sess.childCount() == 2
    capture, run = sess.child(0), sess.child(1)
    assert run.data(0, 0x0100).entity_type == "processing_run"
    assert window.task_event_panel.audit_table.topLevelItemCount() >= 4
    window.project_explorer.tree.setCurrentItem(run)
    assert not window.property_inspector.verify_button.isEnabled()
    window.project_explorer.tree.setCurrentItem(capture)
    assert window.property_inspector.verify_button.isEnabled()
    window.property_inspector.verify_button.click()
    wait(qapp, lambda: not window.capture_checker.busy)
    assert "RAW v1" in window.property_inspector.note.text()
    assert "Không" not in window.data_status.text()  # metadata loaded
    assert window.project_explorer.store_root == str(tmp_path.resolve())


def test_failed_raw_integrity_and_selection_isolation(window, qapp, tmp_path):
    row = prepare(tmp_path)
    load(window, qapp, tmp_path)
    capture = window.project_explorer.tree.topLevelItem(0).child(0).child(0).child(0)
    (tmp_path / row["relative_path"] / "depth.npy").write_bytes(b"tampered")
    window.project_explorer.tree.setCurrentItem(capture)
    window.property_inspector.verify_button.click()
    wait(qapp, lambda: not window.capture_checker.busy)
    # A corrupt capture must be represented by its state in the properties
    # table, while the note provides an explanation rather than the state label.
    raw_states = [
        window.property_inspector.details.topLevelItem(i).text(1)
        for i in range(window.property_inspector.details.topLevelItemCount())
        if window.property_inspector.details.topLevelItem(i).text(0) == "RAW"
    ]
    assert raw_states == ["RAW không hợp lệ"]
    assert "không đạt kiểm tra" in window.property_inspector.note.text().lower()
    window.project_explorer.tree.setCurrentItem(window.project_explorer.tree.topLevelItem(0))
    assert not window.property_inspector.verify_button.isEnabled()
    assert not window.capture_checker.busy


def test_switch_store_clears_old_audit(window, qapp, tmp_path):
    prepare(tmp_path)
    load(window, qapp, tmp_path)
    assert window.task_event_panel.audit_table.topLevelItemCount() > 0
    empty = tmp_path / "invalid"
    empty.mkdir()
    load(window, qapp, empty)
    assert window.task_event_panel.audit_table.topLevelItemCount() == 0
    assert window.project_explorer.store_root is None


def test_close_during_capture_check_preserves_worker(window, qapp, tmp_path, monkeypatch):
    row = prepare(tmp_path)
    load(window, qapp, tmp_path)
    capture = window.project_explorer.tree.topLevelItem(0).child(0).child(0).child(0)
    window.project_explorer.tree.setCurrentItem(capture)
    from scantopath.ui.projects import inspection_controller as control
    import scantopath.application.projects as projects
    original = projects.ProjectWorkspaceService

    class SlowService:
        def __init__(self, root):
            self.inner = original(root)
        def inspect_capture(self, id):
            time.sleep(.2)
            return self.inner.inspect_capture(id)

    monkeypatch.setattr(projects, "ProjectWorkspaceService", SlowService)
    window.property_inspector.verify_button.click()
    assert window.capture_checker.busy
    window.close()
    assert window.isVisible()
    wait(qapp, lambda: not window.capture_checker.busy)
    wait(qapp, lambda: not window.isVisible())
