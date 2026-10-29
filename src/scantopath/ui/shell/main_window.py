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


class ScanToPathMainWindow(QMainWindow):
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

        self._install_task_controller()
        self._connect_workspace_actions()
        self._apply_style()
        self._show_workspace(self.navigation.workspace)
        QTimer.singleShot(0, self._initialize_dock_layout)

    @property
    def active_workspace(self) -> WorkspaceId:
        return self.navigation.workspace

    def page_for(self, workspace: WorkspaceId) -> QWidget:
        return self._pages[WorkspaceId(workspace)]

    def _create_shell(self) -> None:
        """One global navigation strip above docks; no redundant side rail.

        This is deliberately native QMainWindow/QToolBar. Existing dock state,
        screen sizing, shortcuts and UI controller contracts remain unchanged.
        """
        from PySide6.QtWidgets import QSizePolicy

        self.workspace_toolbar = QToolBar("Điều hướng workspace", self)
        self.workspace_toolbar.setObjectName("workspaceToolbar")
        self.workspace_toolbar.setMovable(False)
        self.workspace_toolbar.setFloatable(False)
        self.workspace_toolbar.setContextMenuPolicy(Qt.PreventContextMenu)
        self.workspace_toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)

        brand = QLabel("ScanToPath", self.workspace_toolbar)
        brand.setObjectName("toolbarBrand")
        # Native QLabel uses its compact natural text width; never reserves 126 px.
        brand.setMinimumWidth(0)
        self.workspace_toolbar.addWidget(brand)

        divider = QFrame(self.workspace_toolbar)
        divider.setObjectName("toolbarDivider")
        divider.setFixedSize(1, 20)
        self.workspace_toolbar.addWidget(divider)

        short_labels = {
            WorkspaceId.PROJECTS: "Dự án",
            WorkspaceId.CAPTURE: "Thu nhận RGB-D",
            WorkspaceId.INSPECT3D: "Kiểm tra 3D",
            WorkspaceId.PROCESSING: "Xử lý",
        }
        for workspace in WorkspaceId:
            label = WORKSPACE_PRESENTATION[workspace].title
            button = QPushButton(short_labels[workspace], self.workspace_toolbar)
            button.setObjectName(f"nav_{workspace.value}")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setMinimumHeight(28)
            button.setToolTip(label)
            button.setAccessibleName(f"Mở không gian: {label}")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, key=workspace: self._navigate(key))
            self.nav_buttons[workspace] = button
            self.workspace_toolbar.addWidget(button)

        spacer = QWidget(self.workspace_toolbar)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.workspace_toolbar.addWidget(spacer)
        self.toolbar_context = QLabel("GĐ1 · Desktop", self.workspace_toolbar)
        self.toolbar_context.setObjectName("toolbarContext")
        self.toolbar_context.hide()
        self.addToolBar(Qt.TopToolBarArea, self.workspace_toolbar)

        root = QWidget(self)
        root.setObjectName("desktopRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.workspace_stack = QStackedWidget(root)
        self.workspace_stack.setObjectName("workspaceStack")
        for key in WorkspaceId:
            page = create_workspace_page(key)
            self._pages[key] = page
            self.workspace_stack.addWidget(page)
        layout.addWidget(self.workspace_stack, stretch=1)
        self.setCentralWidget(root)

        status = QStatusBar(self)
        status.setObjectName("applicationStatus")
        status.setSizeGripEnabled(True)
        status.setMaximumHeight(28)
        self.status_message = QLabel("Sẵn sàng")
        self.status_message.setMinimumWidth(0)
        self.status_message.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.status_message.setObjectName("statusMessage")
        status.addWidget(self.status_message, 1)
        self.data_status = QLabel("Dữ liệu: Chưa tải")
        self.data_status.setObjectName("dataStatus")
        status.addPermanentWidget(self.data_status)
        self.setStatusBar(status)

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

    def _open_audit_panel(self) -> None:
        self.task_dock_chrome.open_audit()

    def _create_docks(self) -> None:
        """06.4: các bảng chung không tự khởi tạo SQLite hay thiết bị."""
        self.setDockNestingEnabled(True)
        self.project_explorer = ProjectExplorer(self)
        self.property_inspector = PropertyInspector(self)
        self.task_event_panel = TaskAndEventPanel(self)
        self.project_explorer.selection_changed.connect(self._on_explorer_selection)

        self.explorer_dock = QDockWidget("Cây dự án", self)
        self.explorer_dock.setObjectName("explorerDock")
        self.explorer_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.explorer_dock.setWidget(self.project_explorer)
        self.explorer_dock.setMinimumWidth(205)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.explorer_dock)

        self.inspector_dock = QDockWidget("Thuộc tính", self)
        self.inspector_dock.setObjectName("inspectorDock")
        self.inspector_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.inspector_dock.setWidget(self.property_inspector)
        self.inspector_dock.setMinimumWidth(215)
        self.addDockWidget(Qt.RightDockWidgetArea, self.inspector_dock)

        self.task_dock = QDockWidget("Tác vụ và thông báo", self)
        self.task_dock.setObjectName("taskDock")
        self.task_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.task_dock.setWidget(self.task_event_panel)
        self.task_dock.setMinimumHeight(0)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.task_dock)
        from .task_dock_chrome import TaskDockChrome
        self.task_dock_chrome = TaskDockChrome(self.task_dock, self.task_event_panel)
        self.task_event_panel.expanded_changed.connect(self._resize_task_panel)
        self.task_event_panel.set_demo_tools_visible(False)
        self.task_event_panel.set_expanded(False)

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
        capture_stopped = self.capture_preview.begin_shutdown()
        live_stopped = self.capture_live.begin_shutdown()
        if (
            tasks_stopped
            and project_stopped
            and write_stopped
            and check_stopped
            and viewer_stopped
            and capture_stopped
            and live_stopped
        ):
            if self.viewer3d is not None:
                self.viewer3d.dispose()
            return super().closeEvent(event)
        event.ignore()
        if not viewer_stopped and getattr(self.viewer3d, 'shutdown_pending', False):
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

            if going_to_capture:
                self.capture_preview.begin_navigation_handoff()

            try:
                # Preserve GĐ1 behavior: Explorer selection is always cleared.
                self.project_explorer.clear_selection()
            finally:
                if going_to_capture:
                    self.capture_preview.end_navigation_handoff()

            self.property_inspector.set_selection(None)
            self.task_event_panel.add_ui_event(
                f"Đã chuyển đến: {WORKSPACE_PRESENTATION[self.navigation.workspace].title}"
            )

        self._show_workspace(self.navigation.workspace)

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
