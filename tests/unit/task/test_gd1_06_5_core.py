"""06.5 headless contract tests: no Qt/hardware/SQLite required."""
from __future__ import annotations

import threading
import time

import pytest

from scantopath.application.contracts import TaskState
from scantopath.application.tasks import TaskManager, TaskQueueFull, TaskManagerClosed


def wait_until(check, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(.005)
    raise AssertionError("Timed out")


def test_success_progress_and_terminal_snapshot():
    manager = TaskManager()
    try:
        task = manager.submit("Kiểm thử", lambda ctx: ctx.report_progress(100))
        wait_until(lambda: manager.snapshot(task).state == TaskState.SUCCEEDED)
        snap = manager.snapshot(task)
        assert snap.progress == 100
        assert not snap.can_cancel
        assert not manager.cancel(task)
    finally:
        assert manager.shutdown(1)


def test_failure_is_sanitized_and_terminal():
    manager = TaskManager()
    secret = "password=should-not-appear"
    def crash(_ctx):
        raise ValueError(secret)
    task = manager.submit("Thử lỗi", crash)
    wait_until(lambda: manager.snapshot(task).state == TaskState.FAILED)
    assert "ValueError" in manager.snapshot(task).error
    assert secret not in manager.snapshot(task).error
    assert manager.shutdown(1)


def test_running_cancel_is_request_until_acknowledged():
    manager = TaskManager()
    started = threading.Event()
    proceed = threading.Event()
    def job(ctx):
        started.set()
        proceed.wait(1)
        ctx.check_cancelled()
    task = manager.submit("Thử hủy", job)
    try:
        assert started.wait(1)
        assert manager.cancel(task)
        snap = manager.snapshot(task)
        assert snap.state == TaskState.RUNNING
        assert not snap.can_cancel
        assert not manager.cancel(task)
        proceed.set()
        wait_until(lambda: manager.snapshot(task).state == TaskState.CANCELLED)
    finally:
        proceed.set()
        assert manager.shutdown(1)


def test_queued_cancel_does_not_execute():
    manager = TaskManager(max_pending=2)
    started, release, executed = threading.Event(), threading.Event(), threading.Event()
    def block(ctx):
        started.set()
        release.wait(1)
        ctx.check_cancelled()
    try:
        manager.submit("Đang chạy", block)
        assert started.wait(1)
        second = manager.submit("Đang chờ", lambda ctx: executed.set())
        assert manager.cancel(second)
        assert manager.snapshot(second).state == TaskState.CANCELLED
        release.set()
        assert manager.shutdown(1)
        assert not executed.is_set()
    finally:
        release.set()
        manager.shutdown(1)


def test_queue_is_bounded_and_rejects_extra_pending():
    manager = TaskManager(max_pending=1)
    started, release = threading.Event(), threading.Event()
    def block(ctx):
        started.set()
        release.wait(1)
    try:
        manager.submit("One", block)
        assert started.wait(1)
        manager.submit("Two", lambda _: None)
        with pytest.raises(TaskQueueFull):
            manager.submit("Three", lambda _: None)
        assert len(manager.snapshots()) == 2
    finally:
        release.set()
        assert manager.shutdown(1)


def test_nonblocking_shutdown_refuses_new_work():
    manager = TaskManager()
    started, release = threading.Event(), threading.Event()
    def block(ctx):
        started.set()
        release.wait(1)
        ctx.check_cancelled()
    manager.submit("Đợi", block)
    try:
        assert started.wait(1)
        assert not manager.shutdown(0)
        with pytest.raises(TaskManagerClosed):
            manager.submit("New", lambda _: None)
    finally:
        release.set()
        assert manager.shutdown(1)


@pytest.mark.parametrize("value", [-1, 101, True, "80", float("nan")])
def test_invalid_progress_is_task_failure(value):
    manager = TaskManager()
    try:
        task = manager.submit("Bad progress", lambda ctx: ctx.report_progress(value))
        wait_until(lambda: manager.snapshot(task).state == TaskState.FAILED)
    finally:
        assert manager.shutdown(1)


def test_unknown_progress_is_not_fake_percent():
    manager = TaskManager()
    try:
        task = manager.submit("Unknown", lambda ctx: ctx.report_progress(None))
        wait_until(lambda: manager.snapshot(task).state == TaskState.SUCCEEDED)
        assert manager.snapshot(task).progress is None
    finally:
        assert manager.shutdown(1)


def test_undisturbed_import_does_not_spawn_thread():
    manager = TaskManager()
    assert not manager.worker_alive
    assert not manager.shutting_down
    assert manager.snapshots() == ()
    assert manager.shutdown(0)


def test_repeated_shutdown_and_cancel_safe():
    manager = TaskManager()
    assert manager.shutdown(0)
    assert manager.shutdown(0)
    assert not manager.cancel("does-not-exist")


def test_history_is_bounded():
    manager = TaskManager(max_history=2)
    try:
        for i in range(4):
            task = manager.submit(f"Job {i}", lambda _: None)
            wait_until(lambda: manager.snapshot(task).state == TaskState.SUCCEEDED)
        assert len(manager.snapshots()) <= 2
    finally:
        assert manager.shutdown(1)


def test_invalid_submit_validation():
    manager = TaskManager()
    with pytest.raises(ValueError):
        manager.submit(" ", lambda _: None)
    with pytest.raises(TypeError):
        manager.submit("Name", None)
    assert manager.shutdown(0)


def test_progress_callbacks_use_worker_thread_not_caller():
    manager = TaskManager()
    caller = threading.get_ident()
    ids = []
    try:
        task = manager.submit("Worker", lambda ctx: ids.append(threading.get_ident()))
        wait_until(lambda: manager.snapshot(task).state == TaskState.SUCCEEDED)
        assert ids and ids[0] != caller
    finally:
        assert manager.shutdown(1)
