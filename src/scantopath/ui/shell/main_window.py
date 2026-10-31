"""Qt desktop composition root for workspaces and their feature controllers.

Project persistence opens by explicit user action, not at startup. The 3D feature starts its resident VTK renderer in a separate child process;
this Qt shell never imports the VTK runtime or activates the camera.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QCloseEvent
from PySide6.QtWidgets import (
    QApplication, QDialog, QDockWidget, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QMenu, QMessageBox, QPushButton, QSizePolicy, QStackedWidget,
    QStatusBar, QToolBar, QVBoxLayout, QWidget,
)

from scantopath.application.contracts import CommandStatus, WorkspaceId
from scantopath.modules.project_workspace.presentation.controller import ProjectWorkspaceController
from scantopath.modules.capture.presentation.preview_controller import (
    CapturePreviewController,
)
from scantopath.modules.capture.presentation.live_ui_controller import LiveCaptureUiController
from scantopath.ui.components import ExplorerNode, ProjectExplorer, PropertyInspector, TaskAndEventPanel
from scantopath.ui.viewmodels.navigation import NavigationViewModel
from scantopath.ui.theme import load_hmi_qss
from scantopath.ui.tasks import QtTaskController
from scantopath.ui.workspaces import WORKSPACE_PRESENTATION, create_workspace_page
from .shell_composition import ShellCompositionMixin
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .task_dock_chrome import TaskDockChrome


def _create_capture_replay_services():
    """GD2-09.04 composition root for offline RAW Replay.

    Called inside ReplayThread.run(), never during MainWindow startup.
    Only this boundary wires application services to infrastructure adapters.
    """
    from scantopath.modules.capture.application.replay import RawReplayService
    from scantopath.modules.capture.application.decoding import RgbdDecoder

    from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter
    from scantopath.modules.capture.infrastructure.jpeg_codec import PillowMjpegDecoder

    replay_service = RawReplayService(
        RawReaderAdapter()
    )

    decoder = RgbdDecoder(
        PillowMjpegDecoder()
    )

    return replay_service, decoder

def _capture_storage_adapter():
    """Explicit worker-thread factory; no SQLite opened during UI construction."""
    from scantopath.modules.capture.infrastructure.capture_writer import NumberedCapturePersistenceAdapter
    return NumberedCapturePersistenceAdapter()


def _create_live_camera_worker():
    """GD2-09.07.2: worker construction; lazy native SDK acquisition."""
    from scantopath.modules.capture.presentation.live_worker import LiveStreamWorker

    def make_service():
        # Called inside QThread.run(), never when the UI is instantiated.
        from scantopath.modules.capture.application.live_stream import LiveCaptureService
        from scantopath.modules.capture.infrastructure.process_camera import ProcessIsolatedCameraAdapter
        from scantopath.modules.capture.infrastructure.jpeg_codec import PillowMjpegDecoder
        return LiveCaptureService(ProcessIsolatedCameraAdapter(), PillowMjpegDecoder())

    return LiveStreamWorker(service_factory=make_service)


class ScanToPathMainWindow(ShellCompositionMixin, QMainWindow):
    """Một cửa sổ, bốn workspace; command xử lý ở lớp 06.2."""

    WINDOW_TITLE = "ScanToPath — Không gian làm việc kỹ thuật 3D"

    def __init__(self, navigation: NavigationViewModel | None = None, parent=None) -> None:
        super().__init__(parent)
        self.navigation = navigation if navigation is not None else NavigationViewModel()
        self.setObjectName("ScanToPathMainWindow")
        self.setWindowTitle(self.WINDOW_TITLE)

        self._fit_initial_screen()

        self._pages: dict[WorkspaceId, QWidget] = {}
        self.viewer3d = None  # Lazy feature controller; no VTK import at startup.
        self.nav_buttons: dict[WorkspaceId, QPushButton] = {}
        self.workspace_actions: dict[WorkspaceId, QAction] = {}
        self._create_shell()
        self._create_docks()
        self.task_dock_chrome: TaskDockChrome  # Instantiated by ShellCompositionMixin.
        self._apply_shell_constraints()
        self._create_menus()

        self.project_workspace = ProjectWorkspaceController(self)
        self.project_loader = self.project_workspace.project_loader
        self.project_writer = self.project_workspace.project_writer
        self.capture_checker = self.project_workspace.capture_checker

        # GD2-09.04: wire Replay only after GĐ1 controller aliases exist.
        self.capture_preview = CapturePreviewController(
            self,
            service_factory=_create_capture_replay_services,
        )
        # 09.07.2: dedicated live panel, independent from immutable RAW Replay.
        self.capture_live = LiveCaptureUiController(
            self,
            worker_factory=_create_live_camera_worker,
        )
        from scantopath.modules.capture.presentation.capture_action import CaptureActionCoordinator
        self.capture_action = CaptureActionCoordinator(self, store_factory=_capture_storage_adapter)
        self.capture_action.stopped.connect(self.close)
        # 09.09.3: place existing Live and Replay panels in a compact UI.
        # The layout owns neither camera nor SQLite/RAW lifecycle.
        from scantopath.modules.capture.presentation.workspace_layout import CaptureWorkspaceLayout
        self.capture_workspace_layout = CaptureWorkspaceLayout(self)
        # 09.09.4: controller signals -> real operational timeline.
        from scantopath.ui.tasks.operation_bridge import OperationActivityBridge
        self.operation_activity = OperationActivityBridge(self)
        # UXH-01.3: single validated workflow identity for all workspaces.
        from .workflow_context_controller import WorkflowContextController
        self.workflow_context = WorkflowContextController(self)
        # GD2-10.08.1: opt-in RAW XYZRGB preview; never opens camera at startup.
        from .geometry_preview import GeometryPreviewBridge
        self.geometry_preview = GeometryPreviewBridge(self)
        # UXH-01.4-R02: one action route, no extra toolbar/viewport.
        self.project_explorer.capture_open_requested.connect(self._open_capture_from_click)
        self.project_workspace.project_dashboard.panel.capture_open_requested.connect(
            self._open_capture_from_click)

        self._install_task_controller()
        self._connect_workspace_actions()
        self._apply_style()
        self._show_workspace(self.navigation.workspace)
        QTimer.singleShot(0, self._initialize_dock_layout)

    def _apply_shell_constraints(self) -> None:
        """Qt shell layout constraints owned by the host MainWindow.

        The inherited mixin constructs the widgets. This is the single
        place applying their app-level width and sizing contracts.
        """
        self.explorer_dock.setMinimumWidth(205)
        self.inspector_dock.setMinimumWidth(215)
        self.workspace_toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.status_message.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    @property
    def active_workspace(self) -> WorkspaceId:
        return self.navigation.workspace

    def page_for(self, workspace: WorkspaceId) -> QWidget:
        return self._pages[WorkspaceId(workspace)]


    def _connect_workspace_actions(self) -> None:
        """Thin UI wiring: actionable central empty states reuse 07 controllers."""
        projects = self._pages[WorkspaceId.PROJECTS].findChild(
            QPushButton, "workspacePrimaryAction")
        if projects is not None:
            projects.clicked.connect(self._choose_project_store)
        processing = self._pages[WorkspaceId.PROCESSING].findChild(
            QPushButton, "workspacePrimaryAction")
        if processing is not None:
            processing.clicked.connect(self._open_audit_panel)

    def _open_capture_from_click(self, ref) -> None:
        """UXH-01.4-R02: click Capture -> existing saved RAW tab + Replay.

        Never invoked from selection_changed / SQLite reload.
        """
        from scantopath.application.contracts import SelectionRef
        from scantopath.application.contracts.workflow_context import WorkflowStatus
        if not isinstance(ref, SelectionRef) or ref.entity_type != "capture":
            return
        if (self.project_loader.busy or self.project_writer.busy or
                self.capture_checker.busy):
            self._set_status("Kho đang bận; chưa thể mở bản thu.")
            return
        # Dashboard emits its selected signal synchronously, but explicitly
        # resolve the current Explorer identity if signal order changes.
        if self.project_explorer.selection != ref:
            if not self.project_explorer.select_ref(ref):
                self._set_status("Bản thu không còn trong kho đang mở.")
                return
        wf = self.workflow_context.current
        preview = self.capture_preview
        ctx = preview.context
        if (wf.status is not WorkflowStatus.READY or
                wf.selection != ref or wf.actionable_capture_id != ref.entity_id or
                wf.store_root != self.project_explorer.store_root or
                ctx is None or ctx.store_root != wf.store_root or
                ctx.capture_id != ref.entity_id or
                ctx.project_id != wf.project_id or
                ctx.specimen_id != wf.specimen_id or
                ctx.session_id != wf.session_id):
            self._set_status("Ngữ cảnh bản thu chưa hợp lệ; hãy tải lại kho.")
            return
        # Never leave a live camera stream running invisibly on a RAW view.
        live_state = getattr(self.capture_live.state, "value", "")
        if str(live_state).lower() not in ("idle", "closed", "failed"):
            self._set_status("Hãy dừng camera trực tiếp trước khi mở bản thu đã lưu.")
            return
        # Set the destination tab before exposing the Capture workspace.
        self.capture_workspace_layout.tabs.setCurrentWidget(preview.panel)
        if self.active_workspace is not WorkspaceId.CAPTURE:
            self._navigate(WorkspaceId.CAPTURE)
        if self.active_workspace is not WorkspaceId.CAPTURE:
            return
        if not preview.request_explicit_replay():
            self._set_status("Không thể phát lại RAW tại thời điểm này.")

    def _open_audit_panel(self) -> None:
        self.task_dock_chrome.open_audit()


    # 07.10 compatibility delegates for pre-existing test/UI calls.
    # All project state and workflow logic live in ProjectWorkspaceController.
    def _verify_selected_capture(self, *args, **kwargs):
        return self.project_workspace._verify_selected_capture(*args, **kwargs)

    def _on_capture_checked(self, *args, **kwargs):
        return self.project_workspace._on_capture_checked(*args, **kwargs)

    def _on_capture_check_failed(self, *args, **kwargs):
        return self.project_workspace._on_capture_check_failed(*args, **kwargs)

    def _on_capture_busy(self, *args, **kwargs):
        return self.project_workspace._on_capture_busy(*args, **kwargs)

    def _can_write_project(self, *args, **kwargs):
        return self.project_workspace._can_write_project(*args, **kwargs)

    def _update_project_actions(self, *args, **kwargs):
        return self.project_workspace._update_project_actions(*args, **kwargs)

    def _dialog_command(self, *args, **kwargs):
        return self.project_workspace._dialog_command(*args, **kwargs)

    def _create_project(self, *args, **kwargs):
        return self.project_workspace._create_project(*args, **kwargs)

    def _create_specimen(self, *args, **kwargs):
        return self.project_workspace._create_specimen(*args, **kwargs)

    def _create_session(self, *args, **kwargs):
        return self.project_workspace._create_session(*args, **kwargs)

    def _edit_selected_metadata(self, *args, **kwargs):
        return self.project_workspace._edit_selected_metadata(*args, **kwargs)

    def _close_selected_session(self, *args, **kwargs):
        return self.project_workspace._close_selected_session(*args, **kwargs)

    def _submit_project_write(self, *args, **kwargs):
        return self.project_workspace._submit_project_write(*args, **kwargs)

    def _on_project_written(self, *args, **kwargs):
        return self.project_workspace._on_project_written(*args, **kwargs)

    def _on_project_write_failed(self, *args, **kwargs):
        return self.project_workspace._on_project_write_failed(*args, **kwargs)

    def _on_project_write_busy(self, *args, **kwargs):
        return self.project_workspace._on_project_write_busy(*args, **kwargs)

    def _choose_project_store(self, *args, **kwargs):
        return self.project_workspace._choose_project_store(*args, **kwargs)

    def _reload_project_store(self, *args, **kwargs):
        return self.project_workspace._reload_project_store(*args, **kwargs)

    def _begin_project_load(self, *args, **kwargs):
        return self.project_workspace._begin_project_load(*args, **kwargs)

    def _on_project_busy(self, *args, **kwargs):
        return self.project_workspace._on_project_busy(*args, **kwargs)

    def _on_project_loaded(self, *args, **kwargs):
        return self.project_workspace._on_project_loaded(*args, **kwargs)

    def _on_project_failed(self, *args, **kwargs):
        return self.project_workspace._on_project_failed(*args, **kwargs)

    def _on_explorer_selection(self, *args, **kwargs):
        return self.project_workspace._on_explorer_selection(*args, **kwargs)

    @property
    def _project_root(self):
        return self.project_workspace._project_root

    @property
    def _project_fields(self):
        return self.project_workspace._project_fields

    @property
    def _project_entities(self):
        return self.project_workspace._project_entities

    @property
    def _project_owners(self):
        return self.project_workspace._project_owners

    @property
    def _project_schema(self):
        return self.project_workspace._project_schema

    @property
    def _pending_selection(self):
        return self.project_workspace._pending_selection

    @property
    def _write_refresh_pending(self):
        return self.project_workspace._write_refresh_pending

    @property
    def _project_closing(self):
        return self.project_workspace._project_closing

    @_project_closing.setter
    def _project_closing(self, value):
        self.project_workspace._project_closing = bool(value)

    def _select_project_store(self, last_root):
        return QFileDialog.getExistingDirectory(
            self, "Chọn thư mục kho ScanToPath", last_root or "")

    def _install_task_controller(self) -> None:
        """Only the GUI timer updates Qt widgets; jobs run off the GUI thread."""
        self.task_controller = QtTaskController(self)
        self.task_controller.snapshots_changed.connect(self.task_event_panel.set_tasks)
        self.task_controller.notice.connect(self._task_notice)
        self.task_controller.stopped.connect(self.close)
        self.task_event_panel.demo_requested.connect(self.task_controller.start_fixture)
        self.task_event_panel.cancel_requested.connect(self.task_controller.request_cancel)

    def _task_notice(self, message: str) -> None:
        self.task_event_panel.add_ui_event(message)
        self._set_status(message)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Never exit while a non-daemon task is executing.

        Cancellation is cooperative; if the task cannot stop promptly, keep
        the window alive rather than freezing Qt or terminating the thread.
        """
        self._project_closing = True
        tasks_stopped = self.task_controller.begin_shutdown(grace_seconds=3.0)
        project_stopped = self.project_loader.begin_shutdown()
        write_stopped = self.project_writer.begin_shutdown()
        check_stopped = self.capture_checker.begin_shutdown()
        viewer_stopped = self.viewer3d is None or getattr(self.viewer3d, 'begin_shutdown', lambda: True)()
        geometry_preview_stopped = self.geometry_preview.begin_shutdown()
        capture_stopped = self.capture_preview.begin_shutdown()
        live_stopped = self.capture_live.begin_shutdown()
        store_init_stopped = self.project_workspace.store_initializer.begin_shutdown()
        capture_action_stopped = self.capture_action.begin_shutdown()
        if (
            tasks_stopped
            and project_stopped
            and write_stopped
            and check_stopped
            and viewer_stopped
            and geometry_preview_stopped
            and capture_stopped
            and live_stopped
            and store_init_stopped
            and capture_action_stopped
        ):
            if self.viewer3d is not None:
                self.viewer3d.dispose()
            self.geometry_preview.dispose()
            return super().closeEvent(event)
        event.ignore()
        if not viewer_stopped and getattr(self.viewer3d, 'shutdown_pending', False):
            QTimer.singleShot(120, self.close)
        if not geometry_preview_stopped:
            QTimer.singleShot(120, self.close)

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&Tệp")
        exit_action = QAction("&Thoát", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.setStatusTip("Đóng ứng dụng ScanToPath")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        workspace_menu: QMenu = self.menuBar().addMenu("&Không gian làm việc")
        for index, workspace in enumerate(WorkspaceId, start=1):
            action = QAction(WORKSPACE_PRESENTATION[workspace].title, self)
            action.setObjectName(f"action_{workspace.value}")
            action.setShortcut(QKeySequence(f"Ctrl+{index}"))
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, key=workspace: self._navigate(key))
            workspace_menu.addAction(action)
            self.workspace_actions[workspace] = action

        view_menu = self.menuBar().addMenu("&Hiển thị")
        for dock, title in (
            (self.explorer_dock, "Cây dự án"),
            (self.inspector_dock, "Thuộc tính"),
            (self.task_dock, "Tác vụ và thông báo"),
        ):
            toggle = dock.toggleViewAction()
            toggle.setText(title)
            view_menu.addAction(toggle)

        help_menu = self.menuBar().addMenu("T&rợ giúp")
        stage = QAction("GĐ1 · Workspace & SQLite 07.8 · HMI 07.9", self)
        stage.setEnabled(False)
        help_menu.addAction(stage)
        self.task_dock_chrome.install_developer_tools(help_menu)

    def _resize_task_panel(self, *_args) -> None:
        self.task_dock_chrome.resize_to(self.height())

    def _navigate(self, workspace: WorkspaceId) -> None:
        """Không cập nhật UI nếu CommandOutcome báo thất bại."""
        previous = self.navigation.workspace
        try:
            result = self.navigation.select_workspace(workspace)
        except (TypeError, ValueError) as exc:
            self._show_workspace(self.navigation.workspace)
            self._set_status(f"Không thể chuyển không gian: {exc}")
            return
        if result.status != CommandStatus.SUCCEEDED:
            self._show_workspace(self.navigation.workspace)
            message = ("Không gian làm việc không hợp lệ"
                       if result.error_code == "INVALID_ARGUMENT"
                       else (result.message or "Không thể chuyển không gian làm việc"))
            self._set_status(message)
            return
        if previous != self.navigation.workspace:
            going_to_capture = self.navigation.workspace is WorkspaceId.CAPTURE

            if previous is WorkspaceId.CAPTURE and not going_to_capture:
                self.capture_live.begin_navigation_away()

            # Workspace navigation is display-only: never clear Explorer or context.
            self.task_event_panel.add_ui_event(
                f"Đã chuyển đến: {WORKSPACE_PRESENTATION[self.navigation.workspace].title}"
            )

        self._show_workspace(self.navigation.workspace)
        if previous is WorkspaceId.INSPECT3D and self.navigation.workspace is not WorkspaceId.INSPECT3D:
            # The scene inspector is display state, not the active Project selection.
            # Restore metadata *after* the Viewer hide event clears its scene fields.
            selected = self.project_explorer.selection
            current_workspace = self.navigation.workspace
            QTimer.singleShot(0, lambda: self._restore_project_inspector(selected, current_workspace))

    def _restore_project_inspector(self, selected, destination) -> None:
        if (self.navigation.workspace == destination and destination is not WorkspaceId.INSPECT3D
                and self.project_explorer.selection == selected):
            self.project_workspace._on_explorer_selection(selected)

    def _ensure_viewer3d(self) -> None:
        """Composition only: create a process-isolated VTK preview on first visit."""
        if self.viewer3d is not None:
            return
        from scantopath.ui.shell.viewer_bootstrap import create_viewer_controller
        controller = create_viewer_controller(self)
        old = self._pages[WorkspaceId.INSPECT3D]
        index = self.workspace_stack.indexOf(old)
        if index < 0:
            raise RuntimeError("Missing Inspect 3D workspace")
        self.workspace_stack.removeWidget(old)
        self.workspace_stack.insertWidget(index, controller.page)
        self._pages[WorkspaceId.INSPECT3D] = controller.page
        self.viewer3d = controller
        old.setParent(None)
        old.deleteLater()

    def _show_workspace(self, workspace: WorkspaceId) -> None:
        key = WorkspaceId(workspace)
        if key is WorkspaceId.INSPECT3D:
            self._ensure_viewer3d()
        self.workspace_stack.setCurrentWidget(self._pages[key])
        if key is WorkspaceId.INSPECT3D:
            self.viewer3d.activate()
        for item, button in self.nav_buttons.items():
            button.setChecked(item == key)
        for item, action in self.workspace_actions.items():
            action.setChecked(item == key)
        self._set_status(f"Không gian hiện tại: {WORKSPACE_PRESENTATION[key].title}")

    def _set_status(self, message: str) -> None:
        self.status_message.setText(message)
        self.status_message.setToolTip(message)  # Full string when narrow status bar clips.
        self.statusBar().showMessage(message, 3500)

    def _fit_initial_screen(self) -> None:
        """Fit to physical screen's *logical* available area, including DPI scaling.

        Qt / QScreen.availableGeometry excludes the OS taskbar where supported.
        We never lock a hard-coded 14-inch resolution or maximize by default.
        """
        app = QApplication.instance()
        screen = app.primaryScreen() if app is not None else None
        if screen is None:
            self.setMinimumSize(720, 440)
            self.resize(1100, 700)
            return
        bounds = screen.availableGeometry()
        width = max(1, bounds.width())
        height = max(1, bounds.height())
        self.setMinimumSize(min(720, width), min(440, height))
        # Chừa khoảng thở quanh cửa sổ để dễ kéo và tránh taskbar/dock.
        target_w = min(1240, max(1, width - 32))
        target_h = min(780, max(1, height - 40))
        self.resize(target_w, target_h)
        self.move(bounds.x() + max(0, (width - self.width()) // 2),
                  bounds.y() + max(0, (height - self.height()) // 2))

    def _initialize_dock_layout(self) -> None:
        """Compact preset for small logical viewports, without fixed card geometry.

        The user can always restore hidden docks via the Hiển thị menu.
        Respect manually toggled docks after startup (no repeated auto-hiding).
        """
        width = self.width()
        height = self.height()
        app = QApplication.instance()
        offscreen = app is not None and app.platformName().lower() in ("offscreen", "minimal")
        if not offscreen:
            if width < 900:
                self.inspector_dock.hide()
            if height < 535:
                self.task_dock.hide()
        if self.explorer_dock.isVisible() and self.inspector_dock.isVisible():
            self.resizeDocks(
                [self.explorer_dock, self.inspector_dock],
                [215 if width < 1180 else 240, 225 if width < 1180 else 255],
                Qt.Horizontal,
            )
        elif self.explorer_dock.isVisible():
            self.resizeDocks([self.explorer_dock], [215 if width < 1180 else 240], Qt.Horizontal)
        if self.task_dock.isVisible():
            self._resize_task_panel()

    def _apply_style(self) -> None:
        """Isolate HMI appearance from UI behavior and all worker contracts."""
        self.setStyleSheet(load_hmi_qss())
        for button in self.nav_buttons.values():
            button.ensurePolished()
            text_width = button.fontMetrics().horizontalAdvance(button.text())
            button.setMinimumWidth(max(button.sizeHint().width(), text_width + 22))
