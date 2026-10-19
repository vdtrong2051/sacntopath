"""06.5 Qt tests (required on operator Windows with PySide6 installed)."""
from __future__ import annotations

import os
import threading
import time

import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import QApplication
from scantopath.application.contracts import TaskState
from scantopath.application.tasks import TaskManager
from scantopath.ui.tasks import QtTaskController
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def wait_qt(app, predicate, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            return
        time.sleep(.008)
    raise AssertionError("Qt condition timed out")


@pytest.fixture
def window(qapp):
    window = ScanToPathMainWindow()
    window.show()
    qapp.processEvents()
    yield window
    window.close()
    wait_qt(qapp, lambda: not window.task_controller.manager.worker_alive)


def test_worker_is_idle_on_launch(window):
    assert not window.task_controller.manager.worker_alive
    assert window.task_event_panel.tasks.topLevelItemCount() == 0


def test_vietnamese_buttons_visible_and_no_fake_processingrun(window):
    assert window.task_event_panel.demo_button.text() == "Chạy tác vụ KIỂM THỬ"
    assert window.task_event_panel.cancel_button.text() == "Yêu cầu hủy tác vụ"
    assert "KIỂM THỬ" in window.task_event_panel.task_hint.text() or "06.5" in window.task_event_panel.task_hint.text()


def test_start_fixture_shows_task_and_completes(window, qapp):
    window.task_event_panel.demo_button.click()
    wait_qt(qapp, lambda: window.task_event_panel.tasks.topLevelItemCount() >= 1)
    wait_qt(qapp, lambda: window.task_controller.manager.snapshots()[0].state == TaskState.SUCCEEDED)
    wait_qt(qapp, lambda: window.task_event_panel.tasks.topLevelItem(0).text(1) == "Hoàn thành")
    assert window.task_event_panel.tasks.topLevelItem(0).text(2) == "100%"


def test_cancel_selected_running_task(window, qapp):
    window.task_event_panel.demo_button.click()
    wait_qt(qapp, lambda: window.task_event_panel.tasks.topLevelItemCount() == 1)
    item = window.task_event_panel.tasks.topLevelItem(0)
    window.task_event_panel.tasks.setCurrentItem(item)
    wait_qt(qapp, lambda: window.task_event_panel.cancel_button.isEnabled())
    window.task_event_panel.cancel_button.click()
    wait_qt(qapp, lambda: window.task_controller.manager.snapshots()[0].state == TaskState.CANCELLED)
    assert any("yêu cầu hủy" in window.task_event_panel.events.item(i).text().lower()
               for i in range(window.task_event_panel.events.count()))


def test_queued_task_cancellation(window, qapp):
    window.task_event_panel.demo_button.click()
    wait_qt(qapp, lambda: window.task_controller.manager.snapshots()[0].state == TaskState.RUNNING)
    window.task_event_panel.demo_button.click()
    wait_qt(qapp, lambda: window.task_event_panel.tasks.topLevelItemCount() == 2)
    item = window.task_event_panel.tasks.topLevelItem(1)
    window.task_event_panel.tasks.setCurrentItem(item)
    assert window.task_event_panel.cancel_button.isEnabled()
    window.task_event_panel.cancel_button.click()
    wait_qt(qapp, lambda: window.task_controller.manager.snapshots()[1].state == TaskState.CANCELLED)


def test_queue_overflow_is_reported(window, qapp):
    window.task_event_panel.demo_button.click()
    wait_qt(qapp, lambda: window.task_controller.manager.snapshots()[0].state == TaskState.RUNNING)
    for _ in range(3):
        window.task_event_panel.demo_button.click()
    assert any("Hàng đợi đã đầy" in window.task_event_panel.events.item(i).text()
               for i in range(window.task_event_panel.events.count()))


def test_gui_thread_can_process_while_running(window, qapp):
    window.task_event_panel.demo_button.click()
    wait_qt(qapp, lambda: window.task_controller.manager.snapshots()[0].state == TaskState.RUNNING)
    window.nav_buttons[next(k for k in window.nav_buttons if k.value == 'inspect3d')].click()
    qapp.processEvents()
    assert window.navigation.workspace.value == 'inspect3d'


def test_gui_signal_emitted_on_main_thread(qapp):
    controller = QtTaskController()
    threads = []
    try:
        controller.snapshots_changed.connect(lambda _: threads.append(QThread.currentThread()))
        controller.start_fixture()
        wait_qt(qapp, lambda: bool(threads))
        assert all(t == qapp.thread() for t in threads)
    finally:
        assert not controller.begin_shutdown() or True
        wait_qt(qapp, lambda: not controller.manager.worker_alive)
        controller.timer.stop()


def test_close_during_active_task_is_nonblocking(window, qapp):
    window.task_event_panel.demo_button.click()
    wait_qt(qapp, lambda: window.task_controller.manager.snapshots()[0].state == TaskState.RUNNING)
    before = time.monotonic()
    window.close()
    assert time.monotonic() - before < .2
    wait_qt(qapp, lambda: not window.isVisible(), timeout=3)
    assert not window.task_controller.manager.worker_alive


def test_error_surface_without_leaking_exception(qapp):
    mgr = TaskManager()
    controller = QtTaskController(manager=mgr)
    received = []
    controller.snapshots_changed.connect(lambda snapshots: received.append(snapshots))
    try:
        def fail(_ctx):
            raise RuntimeError('sensitive-path-secret')
        task = mgr.submit('Lỗi thử', fail)
        wait_qt(qapp, lambda: mgr.snapshot(task).state == TaskState.FAILED)
        wait_qt(qapp, lambda: received and received[-1][0].state == TaskState.FAILED)
        assert "sensitive-path-secret" not in received[-1][0].error
    finally:
        controller.begin_shutdown()
        wait_qt(qapp, lambda: not mgr.worker_alive)
        controller.timer.stop()
