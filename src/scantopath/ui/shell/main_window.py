"""GĐ1-06.5: giao diện tiếng Việt, task queue và shutdown an toàn.

Không dùng SQLite, camera, SDK hay VTK. Worker thử nghiệm không thao tác QWidget.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QCloseEvent
from PySide6.QtWidgets import (
    QDockWidget, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu,
    QPushButton, QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

from scantopath.application.contracts import CommandStatus, WorkspaceId
from scantopath.ui.components import ProjectExplorer, PropertyInspector, TaskAndEventPanel
from scantopath.ui.viewmodels.navigation import NavigationViewModel
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
        self.resize(1260, 790)
        self.setMinimumSize(860, 590)

        self._pages: dict[WorkspaceId, QWidget] = {}
        self.nav_buttons: dict[WorkspaceId, QPushButton] = {}
        self.workspace_actions: dict[WorkspaceId, QAction] = {}
        self._create_shell()
        self._create_docks()
        self._create_menus()
        self._install_task_controller()
        self._apply_style()
        self._show_workspace(self.navigation.workspace)

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
        sidebar.setFixedWidth(244)
        nav_layout = QVBoxLayout(sidebar)
        nav_layout.setContentsMargins(16, 24, 16, 22)
        nav_layout.setSpacing(9)

        brand = QLabel("ScanToPath")
        brand.setObjectName("appBrand")
        nav_layout.addWidget(brand)

        brand_caption = QLabel("KHÔNG GIAN KỸ THUẬT 3D")
        brand_caption.setObjectName("appBrandCaption")
        nav_layout.addWidget(brand_caption)
        nav_layout.addSpacing(28)

        navigation_title = QLabel("ĐIỀU HƯỚNG")
        navigation_title.setObjectName("navTitle")
        nav_layout.addWidget(navigation_title)
        nav_layout.addSpacing(5)

        for workspace in WorkspaceId:
            label = WORKSPACE_PRESENTATION[workspace].title
            button = QPushButton(label)
            button.setObjectName(f"nav_{workspace.value}")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setMinimumHeight(45)
            button.setCursor(Qt.PointingHandCursor)
            button.setAccessibleName(f"Mở không gian: {label}")
            button.clicked.connect(lambda checked=False, key=workspace: self._navigate(key))
            self.nav_buttons[workspace] = button
            nav_layout.addWidget(button)

        nav_layout.addStretch(1)
        stage = QLabel("GĐ1 · BƯỚC 06.5")
        stage.setObjectName("stageLabel")
        nav_layout.addWidget(stage)
        sidebar_note = QLabel("Bảng điều khiển · Chưa kết nối dữ liệu")
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
        topbar_layout.setContentsMargins(28, 12, 28, 12)
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
        self.addDockWidget(Qt.LeftDockWidgetArea, self.explorer_dock)

        self.inspector_dock = QDockWidget("Thuộc tính", self)
        self.inspector_dock.setObjectName("inspectorDock")
        self.inspector_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.inspector_dock.setWidget(self.property_inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, self.inspector_dock)

        self.task_dock = QDockWidget("Tác vụ và thông báo", self)
        self.task_dock.setObjectName("taskDock")
        self.task_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.task_dock.setWidget(self.task_event_panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.task_dock)

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
        if self.task_controller.begin_shutdown(grace_seconds=3.0):
            super().closeEvent(event)
        else:
            event.ignore()

    def _on_explorer_selection(self, selection: object) -> None:
        """SelectionRef là tham chiếu, không phải phép đo hoặc metadata đã nạp."""
        self.navigation.select_entity(selection)
        self.property_inspector.set_selection(selection)
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
        stage = QAction("Trạng thái phát triển: GĐ1 — 06.5", self)
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

    def _apply_style(self) -> None:
        # Chỉ QSS nhẹ, không kéo thêm thư viện giao diện cho GĐ1.
        self.setStyleSheet("""
            QMainWindow, #desktopRoot, #workspaceArea, #workspaceStack {
                background: #f4f7fa; color: #182b39;
            }
            QMenuBar { background: #ffffff; border-bottom: 1px solid #e5ebf0; padding: 3px; }
            QMenuBar::item:selected, QMenu::item:selected { background: #e7f4f1; }
            QMenu { background: #ffffff; color: #182b39; }
            #navigationSidebar { background: #152936; border: none; }
            #appBrand { color: #ffffff; font-size: 24px; font-weight: 700; }
            #appBrandCaption { color: #a3b9c2; font-size: 10px; letter-spacing: 1px; }
            #navTitle { color: #95acb5; font-size: 11px; font-weight: 650; }
            QPushButton[checkable="true"] { background: transparent; color: #e7eff2;
                text-align: left; padding: 9px 14px; border-radius: 7px; font-size: 13px; }
            QPushButton[checkable="true"]:hover { background: #2b4553; }
            QPushButton[checkable="true"]:checked { background: #146f66;
                color: #ffffff; font-weight: 700; }
            #stageLabel { color: #93d9cb; font-weight: 700; font-size: 11px; }
            #sidebarNote { color: #abc0c7; font-size: 11px; }
            #workspaceTopbar { background: #ffffff; border-bottom: 1px solid #e5ebf0; }
            #workspaceTopbarTitle { color: #536b77; font-size: 11px; font-weight: 700; }
            #baselineMarker { color: #146f66; background: #eaf6f2;
                border-radius: 5px; padding: 6px 9px; font-size: 10px; font-weight: 650; }
            #workspaceHeading { font-size: 31px; font-weight: 700; color: #172d3b; }
            #workspaceSubtitle { color: #607787; font-size: 13px; }
            #workspaceState { border-radius: 6px; background: #fff3e2; color: #845314;
                font-size: 10px; font-weight: 700; padding: 7px 11px; }
            #workspacePlanned { color: #536b77; font-size: 11px; }
            #workspacePanel { background: #ffffff; border: 1px solid #e1e9ef;
                border-radius: 10px; }
            #workspaceKicker { font-size: 11px; color: #146f66; font-weight: 700; }
            #workspaceFeatureTitle { font-size: 21px; font-weight: 700; color: #172d3b; }
            #workspaceDescription { color: #435e6c; font-size: 13px; }
            #workspaceFootnote { color: #8599a4; font-size: 11px; }
            QStatusBar { background: #ffffff; color: #405965;
                border-top: 1px solid #e1e9ef; padding: 3px 10px; }
        """)
