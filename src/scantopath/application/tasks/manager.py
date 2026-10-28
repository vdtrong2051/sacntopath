"""GĐ1-06.5: bounded, cooperative, headless task executor.

One non-daemon worker; no Qt, SQLite, OrbbecSDK, camera or data writes.
Cancellation is a REQUEST until the worker acknowledges it. Snapshot status is
for the UI only; it is NOT a persisted ProcessingRun.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Condition, Event, Thread
from typing import Callable
from uuid import uuid4

from scantopath.application.contracts import TaskSnapshot, TaskState


class TaskCancelled(Exception):
    """Cooperative cancellation acknowledged by a worker."""


class TaskQueueFull(Exception):
    """All pending slots are occupied."""


class TaskManagerClosed(Exception):
    """The executor has entered shutdown and will accept no more work."""


class TaskContext:
    """Pass into a worker; never exposes Qt objects or a mutable TaskSnapshot."""

    def __init__(self, cancel_event: Event, progress: Callable[[float | None], None]) -> None:
        self._cancel = cancel_event
        self._progress = progress

    @property
    def cancellation_requested(self) -> bool:
        return self._cancel.is_set()

    def check_cancelled(self) -> None:
        if self._cancel.is_set():
            raise TaskCancelled()

    def report_progress(self, progress: float | None) -> None:
        self.check_cancelled()
        if progress is not None:
            if isinstance(progress, bool) or not isinstance(progress, (float, int)) or not (0 <= progress <= 100):
                raise ValueError("progress must be 0..100 or None")
        self._progress(None if progress is None else float(progress))


@dataclass(slots=True)
class _Job:
    task_id: str
    title: str
    function: Callable[[TaskContext], object]
    cancel: Event
    snapshot: TaskSnapshot
    cancel_requested: bool = False


class TaskManager:
    """Finite pending queue and one worker; snapshots are safe to poll from GUI.

    Non-daemon thread and refusal-to-close until acknowledgement avoid use-after-
    shutdown of Python/Qt objects. Native/blocking tasks MUST explicitly support
    cooperative cancellation before they can be scheduled by this executor.
    """

    def __init__(self, *, max_pending: int = 2, max_history: int = 64) -> None:
        if max_pending < 1 or max_history < 1:
            raise ValueError("queue/history limits must be positive")
        self._cv = Condition()
        self._max_pending = max_pending
        self._max_history = max_history
        self._jobs: dict[str, _Job] = {}
        self._queue: deque[str] = deque()
        self._running: str | None = None
        self._worker: Thread | None = None
        self._stopping = False
        self._revision = 0

    @property
    def revision(self) -> int:
        with self._cv:
            return self._revision

    @property
    def shutting_down(self) -> bool:
        with self._cv:
            return self._stopping

    @property
    def worker_alive(self) -> bool:
        with self._cv:
            return self._worker is not None and self._worker.is_alive()

    def submit(self, title: str, function: Callable[[TaskContext], object]) -> str:
        if not isinstance(title, str) or not title.strip() or len(title) > 256:
            raise ValueError("title must be 1..256 characters")
        if not callable(function):
            raise TypeError("function must be callable")
        with self._cv:
            if self._stopping:
                raise TaskManagerClosed("Task manager is shutting down")
            if len(self._queue) >= self._max_pending:
                raise TaskQueueFull("Pending task queue is full")
            task_id = uuid4().hex
            job = _Job(task_id, title, function, Event(), TaskSnapshot(
                task_id=task_id, title=title, state=TaskState.QUEUED, can_cancel=True,
            ))
            self._jobs[task_id] = job
            self._queue.append(task_id)
            self._revision += 1
            if self._worker is None:
                self._worker = Thread(target=self._run, name="scantopath-task-06-5", daemon=False)
                self._worker.start()
            self._cv.notify_all()
            return task_id

    def snapshots(self) -> tuple[TaskSnapshot, ...]:
        with self._cv:
            return tuple(job.snapshot for job in self._jobs.values())

    def snapshot(self, task_id: str) -> TaskSnapshot | None:
        with self._cv:
            job = self._jobs.get(task_id)
            return job.snapshot if job is not None else None

    def cancel(self, task_id: str) -> bool:
        with self._cv:
            job = self._jobs.get(task_id)
            if job is None or job.snapshot.state in (TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED):
                return False
            if job.cancel_requested:
                return False
            job.cancel_requested = True
            job.cancel.set()
            if job.snapshot.state == TaskState.QUEUED:
                self._queue.remove(task_id)
                self._finish(job, TaskState.CANCELLED)
            else:
                # A running task has not yet acknowledged cancellation.
                job.snapshot = TaskSnapshot(task_id=job.task_id, title=job.title,
                                            state=TaskState.RUNNING, progress=job.snapshot.progress,
                                            can_cancel=False)
                self._revision += 1
            self._cv.notify_all()
            return True

    def shutdown(self, timeout: float = 0.0) -> bool:
        """Cancel pending/running tasks. Nonblocking by default; False means wait.

        Calling from GUI closeEvent with timeout=0 avoids blocking its event loop.
        If False, the GUI must remain alive and continue polling; do not forcibly
        terminate a native/Python thread.
        """
        if timeout < 0:
            raise ValueError("timeout must be >= 0")
        with self._cv:
            self._stopping = True
            outstanding = [job.task_id for job in self._jobs.values() if job.snapshot.state in (TaskState.QUEUED, TaskState.RUNNING) and not job.cancel_requested]
        for task_id in outstanding:
            self.cancel(task_id)
        with self._cv:
            self._cv.notify_all()
            worker = self._worker
        if worker is None:
            return True
        worker.join(timeout)
        return not worker.is_alive()

    def _finish(self, job: _Job, state: TaskState, error: str | None = None) -> None:
        # Caller holds _cv. All terminal transitions happen exactly once.
        if job.snapshot.state in (TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED):
            return
        job.snapshot = TaskSnapshot(task_id=job.task_id, title=job.title,
                                    state=state, progress=job.snapshot.progress,
                                    can_cancel=False, error=error)
        self._revision += 1
        self._trim_history()

    def _trim_history(self) -> None:
        done = [key for key, job in self._jobs.items()
                if job.snapshot.state in (TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED)]
        for key in done[:-self._max_history]:
            self._jobs.pop(key, None)

    def _run(self) -> None:
        while True:
            with self._cv:
                self._cv.wait_for(lambda: bool(self._queue) or self._stopping)
                if not self._queue and self._stopping:
                    return
                task_id = self._queue.popleft()
                job = self._jobs[task_id]
                self._running = task_id
                job.snapshot = TaskSnapshot(task_id=task_id, title=job.title,
                                            state=TaskState.RUNNING, can_cancel=not job.cancel_requested)
                self._revision += 1

            def report(progress: float | None, current_job: _Job = job) -> None:
                with self._cv:
                    if current_job.snapshot.state == TaskState.RUNNING and current_job.snapshot.progress != progress:
                        current_job.snapshot = TaskSnapshot(task_id=current_job.task_id, title=current_job.title,
                                                    state=TaskState.RUNNING, progress=progress,
                                                    can_cancel=not current_job.cancel_requested)
                        self._revision += 1

            ctx = TaskContext(job.cancel, report)
            try:
                ctx.check_cancelled()
                job.function(ctx)
                ctx.check_cancelled()
            except TaskCancelled:
                state, error = TaskState.CANCELLED, None
            except Exception as exc:
                # Do not expose arbitrary exception text containing paths/secrets.
                state, error = TaskState.FAILED, f"Lỗi tác vụ ({type(exc).__name__})"
            else:
                state, error = TaskState.SUCCEEDED, None
            with self._cv:
                if job.cancel.is_set():
                    state, error = TaskState.CANCELLED, None
                self._finish(job, state, error)
                self._running = None
                self._cv.notify_all()
