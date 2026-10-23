"""GĐ1 — HMI QSS tối giản, UI tiếng Việt, worker không chạm QWidget.

Không dùng SQLite, camera, SDK hay VTK. Worker thử nghiệm không thao tác QWidget.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QCloseEvent
from PySide6.QtWidgets import (
    QApplication, QDockWidget, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMenu, QPushButton, QSizePolicy, QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

from scantopath.application.contracts import CommandStatus, WorkspaceId
from scantopath.ui.components import ExplorerNode, ProjectExplorer, PropertyInspector, TaskAndEventPanel
from scantopath.ui.projects.controller import ProjectLoadController
from scantopath.ui.viewmodels.navigation import NavigationViewModel
from scantopath.ui.theme import load_hmi_qss
from scantopath.ui.tasks import QtTaskController
from scantopath.ui.workspaces import WORKSPACE_PRESENTATION, create_workspace_page


class ScanToPathMainWindow(QMainWindow):
    """Một cửa sổ, bốn workspace; command xử lý ở lớp 06.2."""

    WINDOW_TITLE = "ScanToPath — Không gian làm việc kỹ thuật 3D"

    def __init__(self, navigation: NavigationViewModel | None = None, parent=None) -> None:
        super().__init__(parent)
        self.navigation = navigation if navigation is not None else NavigationViewModel()
        self.setObjectName("ScanToPathMainWindow")
        self.setWindowTitle(self.WINDOW_TITLE)
        # Kích thước dựa trên vùng màn hình thực dùng được (đã trừ taskbar,
        # Windows DPI scaling); không giả định laptop 14 inch là một độ phân giải.
        self._fit_initial_screen()

        self._pages: dict[WorkspaceId, QWidget] = {}
        self.nav_buttons: dict[WorkspaceId, QPushButton] = {}
        self.workspace_actions: dict[WorkspaceId, QAction] = {}
        self._create_shell()
        self._create_docks()
        self._create_menus()
        self._install_project_loader()
        self._install_task_controller()
        self._apply_style()
        self._show_workspace(self.navigation.workspace)
        # Đợi Qt bố trí dock lần đầu rồi mới cân lại kích thước.
        QTimer.singleShot(0, self._initialize_dock_layout)

    @property
    def active_workspace(self) -> WorkspaceId:
        return self.navigation.workspace

    def page_for(self, workspace: WorkspaceId) -> QWidget:
        return self._pages[WorkspaceId(workspace)]

    def _create_shell(self) -> None:
        root = QWidget(self)
        root.setObjectName("desktopRoot")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame(root)
        sidebar.setObjectName("navigationSidebar")
        self.navigation_sidebar = sidebar
        sidebar.setFixedWidth(184)
        sidebar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        nav_layout = QVBoxLayout(sidebar)
        nav_layout.setContentsMargins(11, 16, 11, 12)
        nav_layout.setSpacing(5)

        brand = QLabel("ScanToPath")
        brand.setObjectName("appBrand")
        nav_layout.addWidget(brand)

        brand_caption = QLabel("KHÔNG GIAN KỸ THUẬT 3D")
        brand_caption.setObjectName("appBrandCaption")
        nav_layout.addWidget(brand_caption)
        nav_layout.addSpacing(14)

        navigation_title = QLabel("ĐIỀU HƯỚNG")
        navigation_title.setObjectName("navTitle")
        nav_layout.addWidget(navigation_title)
        nav_layout.addSpacing(3)

        for workspace in WorkspaceId:
            label = WORKSPACE_PRESENTATION[workspace].title
            button = QPushButton(label)
            button.setObjectName(f"nav_{workspace.value}")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setMinimumHeight(35)
            button.setCursor(Qt.PointingHandCursor)
            button.setAccessibleName(f"Mở không gian: {label}")
            button.clicked.connect(lambda checked=False, key=workspace: self._navigate(key))
            self.nav_buttons[workspace] = button
            nav_layout.addWidget(button)

        nav_layout.addStretch(1)
        stage = QLabel("GĐ1 · HMI")
        stage.setObjectName("stageLabel")
        nav_layout.addWidget(stage)
        sidebar_note = QLabel("Dữ liệu dự án · Mở kho từ Cây dự án")
        sidebar_note.setObjectName("sidebarNote")
        sidebar_note.setWordWrap(True)
        nav_layout.addWidget(sidebar_note)

        layout.addWidget(sidebar)

        content = QFrame(root)
        content.setObjectName("workspaceArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        topbar = QFrame(content)
        topbar.setObjectName("workspaceTopbar")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(16, 7, 16, 7)
        title = QLabel("ỨNG DỤNG MÁY TÍNH")
        title.setObjectName("workspaceTopbarTitle")
        topbar_layout.addWidget(title)
        topbar_layout.addStretch(1)
        marker = QLabel("NỀN TẢNG GĐ0 ĐÃ NGHIỆM THU")
        marker.setObjectName("baselineMarker")
        marker.setToolTip("Các chức năng giao diện được triển khai tuần tự từ GĐ1.")
        topbar_layout.addWidget(marker)
        content_layout.addWidget(topbar)

        self.workspace_stack = QStackedWidget(content)
        self.workspace_stack.setObjectName("workspaceStack")
        for key in WorkspaceId:
            page = create_workspace_page(key)
            self._pages[key] = page
            self.workspace_stack.addWidget(page)
        content_layout.addWidget(self.workspace_stack, stretch=1)
        layout.addWidget(content, stretch=1)
        self.setCentralWidget(root)

        status = QStatusBar(self)
        status.setObjectName("applicationStatus")
        status.setSizeGripEnabled(True)
        status.setMaximumHeight(28)
        self.status_message = QLabel("Sẵn sàng")
        self.status_message.setObjectName("statusMessage")
        status.addWidget(self.status_message)
        self.data_status = QLabel("Dữ liệu: Chưa tải")
        self.data_status.setObjectName("dataStatus")
        status.addPermanentWidget(self.data_status)
        self.setStatusBar(status)

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
        self.explorer_dock.setMinimumWidth(155)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.explorer_dock)

        self.inspector_dock = QDockWidget("Thuộc tính", self)
        self.inspector_dock.setObjectName("inspectorDock")
        self.inspector_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.inspector_dock.setWidget(self.property_inspector)
        self.inspector_dock.setMinimumWidth(155)
        self.addDockWidget(Qt.RightDockWidgetArea, self.inspector_dock)

        self.task_dock = QDockWidget("Tác vụ và thông báo", self)
        self.task_dock.setObjectName("taskDock")
        self.task_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.task_dock.setWidget(self.task_event_panel)
        self.task_dock.setMinimumHeight(115)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.task_dock)

    def _install_project_loader(self) -> None:
        """Qt-main-thread bridge for explicitly chosen, existing SQLite stores."""
        self.project_loader = ProjectLoadController(self)
        self._project_root: str | None = None
        self._project_fields: dict[object, tuple[tuple[str, str], ...]] = {}
        self.project_explorer.open_requested.connect(self._choose_project_store)
        self.project_explorer.refresh_requested.connect(self._reload_project_store)
        self.project_loader.loaded.connect(self._on_project_loaded)
        self.project_loader.failed.connect(self._on_project_failed)
        self.project_loader.busy_changed.connect(self._on_project_busy)
        self.project_loader.stopped.connect(self.close)

    def _choose_project_store(self) -> None:
        if self.project_loader.busy:
            return
        root = QFileDialog.getExistingDirectory(self, "Chọn thư mục kho ScanToPath", self._project_root or "")
        if root:
            self._begin_project_load(root)

    def _reload_project_store(self) -> None:
        if self._project_root is not None:
            self._begin_project_load(self._project_root)

    def _begin_project_load(self, root: str) -> None:
        if self.project_loader.busy:
            return
        # Do not display stale objects from a previously selected data root.
        self.project_explorer.set_nodes(())
        self._project_fields.clear()
        self.property_inspector.set_selection(None)
        self._project_root = None
        self.project_explorer.show_store(None)
        self.data_status.setText("Dữ liệu: Đang tải")
        if not self.project_loader.load(root):
            self._on_project_failed("Đang có thao tác tải kho dữ liệu khác.")

    def _on_project_busy(self, busy: bool) -> None:
        self.project_explorer.set_busy(busy)

    def _on_project_loaded(self, bundle: object) -> None:
        """Called in GUI thread; the worker only passes immutable DTO records."""
        # Lazy import: startup/import UI must not load metadata/SQLite modules.
        from scantopath.ui.projects.presentation import project_rows
        self._project_root = bundle.info.root
        rows = project_rows(bundle.trees)
        self._project_fields.clear()

        def convert(row) -> ExplorerNode:
            self._project_fields[row.selection] = row.fields
            return ExplorerNode(row.title, row.selection, tuple(convert(c) for c in row.children))

        self.project_explorer.set_nodes(tuple(convert(r) for r in rows))
        for index in range(self.project_explorer.tree.topLevelItemCount()):
            self.project_explorer.tree.topLevelItem(index).setExpanded(True)
        self.project_explorer.show_store(bundle.info.root, schema_version=bundle.info.schema_version)
        if not rows:
            self.project_explorer.show_message("Kho SQLite hợp lệ nhưng chưa có dự án.")
        self.data_status.setText(f"Dữ liệu: {len(rows)} dự án · SQLite v{bundle.info.schema_version}")
        self._set_status(f"Đã tải {len(rows)} dự án từ kho SQLite đã chọn.")
        self.task_event_panel.add_ui_event("Đã tải cây dự án từ kho SQLite được chọn.")

    def _on_project_failed(self, message: str) -> None:
        self._project_root = None
        self._project_fields.clear()
        self.project_explorer.set_nodes(())
        self.project_explorer.show_store(None)
        self.project_explorer.show_message(message)
        self.property_inspector.set_selection(None)
        self.data_status.setText("Dữ liệu: Chưa tải")
        self._set_status(message)

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
        # Evaluate both independently so a running loader cannot be orphaned
        # when the pre-existing task worker has already stopped.
        tasks_stopped = self.task_controller.begin_shutdown(grace_seconds=3.0)
        project_stopped = self.project_loader.begin_shutdown()
        if tasks_stopped and project_stopped:
            super().closeEvent(event)
        else:
            event.ignore()

    def _on_explorer_selection(self, selection: object) -> None:
        """SelectionRef là tham chiếu, không phải phép đo hoặc metadata đã nạp."""
        self.navigation.select_entity(selection)
        self.property_inspector.set_selection(selection)
        if selection is not None and selection in self._project_fields:
            self.property_inspector.set_store_fields(self._project_fields[selection])
        if selection is not None:
            self._set_status(f"Đã chọn đối tượng: {selection.entity_id}")

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
        stage = QAction("GĐ1 · Project Explorer 07.4 (chỉ đọc)", self)
        stage.setEnabled(False)
        help_menu.addAction(stage)

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
            self.project_explorer.clear_selection()
            self.property_inspector.set_selection(None)
            self.task_event_panel.add_ui_event(
                f"Đã chuyển đến: {WORKSPACE_PRESENTATION[self.navigation.workspace].title}"
            )
        self._show_workspace(self.navigation.workspace)

    def _show_workspace(self, workspace: WorkspaceId) -> None:
        key = WorkspaceId(workspace)
        self.workspace_stack.setCurrentWidget(self._pages[key])
        for item, button in self.nav_buttons.items():
            button.setChecked(item == key)
        for item, action in self.workspace_actions.items():
            action.setChecked(item == key)
        self._set_status(f"Không gian hiện tại: {WORKSPACE_PRESENTATION[key].title}")

    def _set_status(self, message: str) -> None:
        self.status_message.setText(message)
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
        self.navigation_sidebar.setFixedWidth(172 if width < 1180 else 194)
        # Automated Qt offscreen tests have a synthetic screen; don't hide docks
        # implicitly there. The compact behavior is exercised in dedicated tests.
        app = QApplication.instance()
        offscreen = app is not None and app.platformName().lower() in ("offscreen", "minimal")
        if not offscreen:
            if width < 970:
                self.inspector_dock.hide()
            if height < 535:
                self.task_dock.hide()
        if self.explorer_dock.isVisible() and self.inspector_dock.isVisible():
            self.resizeDocks(
                [self.explorer_dock, self.inspector_dock],
                [185 if width < 1180 else 205, 185 if width < 1180 else 215],
                Qt.Horizontal,
            )
        elif self.explorer_dock.isVisible():
            self.resizeDocks([self.explorer_dock], [185], Qt.Horizontal)
        if self.task_dock.isVisible():
            self.resizeDocks([self.task_dock], [145 if height < 690 else 172], Qt.Vertical)

    def _apply_style(self) -> None:
        """Isolate HMI appearance from UI behavior and all worker contracts."""
        self.setStyleSheet(load_hmi_qss())
