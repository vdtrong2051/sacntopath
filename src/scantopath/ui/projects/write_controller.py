"""07.5: explicit SQLite metadata writes on QThread, never on QWidget thread."""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from scantopath.modules.project_workspace.application.ports import ProjectWritePort
from .forms_contract import ProjectEditCommand, ProjectEditResult


def _make_write_service(root: str) -> "ProjectWritePort":
    # Preserve 06.3 import isolation: persistence imported only after user action.
    from scantopath.application.projects import ProjectWorkspaceService
    return ProjectWorkspaceService(root)


def _execute(service, command: ProjectEditCommand) -> ProjectEditResult:
    """Only Application Services may mutate metadata; no direct ORM/SQL in Qt."""
    a = command.action
    if a == "project.create":
        result = service.create_project(command.name, command.description)
        kind, identity = "project", result.project_id
    elif a == "project.update":
        result = service.update_project(command.target_id, name=command.name,
                                        description=command.description)
        kind, identity = "project", result.project_id
    elif a == "specimen.create":
        result = service.create_specimen(command.parent_id, command.name, command.description)
        kind, identity = "specimen", result.specimen_id
    elif a == "specimen.update":
        result = service.update_specimen(command.project_id, command.target_id,
                                         label=command.name, description=command.description)
        kind, identity = "specimen", result.specimen_id
    elif a == "session.create":
        result = service.create_session(command.parent_id, command.name)
        kind, identity = "scan_session", result.session_id
    elif a == "session.update":
        result = service.update_session(command.parent_id, command.target_id, label=command.name)
        kind, identity = "scan_session", result.session_id
    elif a == "session.close":
        result = service.close_session(command.parent_id, command.target_id)
        kind, identity = "scan_session", result.session_id
    else:
        raise ValueError("Unsupported command")
    return ProjectEditResult(a, kind, identity, result.storage.public_code)


class _WriteThread(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, root: str, command: ProjectEditCommand, parent: QObject | None = None):
        super().__init__(parent)
        self.root = root
        self.command = command

    def run(self) -> None:
        try:
            service = _make_write_service(self.root)
            if not service.info.writable_with_codes:
                self.failed.emit("Kho SQLite v1 chỉ cho phép xem. Hãy sao lưu và nâng schema bằng công cụ 07.2 trước.")
                return
            result = _execute(service, self.command)
            self.completed.emit(result)
        except Exception as exc:
            # A create may COMMIT its internal ID before code allocation fails.
            # Return the ID so recovery is possible, never suggest creating twice.
            if type(exc).__name__ == "NumberingPendingError":
                kind = exc.entity_type
                selection_kind = "scan_session" if kind == "session" else kind
                self.completed.emit(ProjectEditResult(self.command.action, selection_kind,
                                                      exc.internal_id, None, True))
            elif isinstance(exc, (ValueError, LookupError)):
                self.failed.emit("Thông tin không hợp lệ hoặc đối tượng đã thay đổi. Tải lại cây dự án rồi thử lại.")
            elif type(exc).__name__ in ("OperationalError", "IntegrityError", "DatabaseError", "PermissionError"):
                self.failed.emit("Không thể ghi SQLite. Kiểm tra quyền truy cập hoặc trạng thái khóa cơ sở dữ liệu.")
            elif type(exc).__name__ == "NumberedSchemaRequiredError":
                self.failed.emit("Kho chưa hỗ trợ ghi theo mã đánh số. Cần nâng schema thủ công ở 07.2.")
            else:
                # Do not surface exception text containing absolute path / user data.
                self.failed.emit("Không hoàn thành thao tác. Dữ liệu chưa được xác nhận; tải lại để kiểm tra.")


class ProjectWriteController(QObject):
    completed = Signal(object)
    failed = Signal(str)
    busy_changed = Signal(bool)
    stopped = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: _WriteThread | None = None
        self._closing = False

    @property
    def busy(self) -> bool:
        return self._thread is not None

    def submit(self, root: str, command: ProjectEditCommand) -> bool:
        if not isinstance(command, ProjectEditCommand):
            raise TypeError("Expected validated ProjectEditCommand")
        if not isinstance(root, str) or not root.strip():
            raise ValueError("An existing store must be selected")
        if self._closing or self.busy:
            return False
        thread = _WriteThread(root, command, self)
        self._thread = thread
        thread.completed.connect(self._on_completed)
        thread.failed.connect(self._on_failed)
        thread.finished.connect(self._on_finished)
        thread.finished.connect(thread.deleteLater)
        self.busy_changed.emit(True)
        thread.start()
        return True

    @Slot(object)
    def _on_completed(self, result: ProjectEditResult) -> None:
        if not self._closing:
            self.completed.emit(result)

    @Slot(str)
    def _on_failed(self, reason: str) -> None:
        if not self._closing:
            self.failed.emit(reason)

    @Slot()
    def _on_finished(self) -> None:
        self._thread = None
        self.busy_changed.emit(False)
        if self._closing:
            self.stopped.emit()

    def begin_shutdown(self) -> bool:
        self._closing = True
        return not self.busy
