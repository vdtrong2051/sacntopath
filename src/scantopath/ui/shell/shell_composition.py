"""Qt shell/dock composition moved from main_window in 09.09.4 regression repair.

Pure UI setup. The host QMainWindow owns all widgets and controllers. No
persistence, SDK, RAW, or process state is created during module import.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget, QFrame, QLabel, QPushButton, QSizePolicy, QStackedWidget,
    QStatusBar, QToolBar, QVBoxLayout, QWidget,
)
from scantopath.application.contracts import WorkspaceId
from scantopath.ui.components import ProjectExplorer, PropertyInspector, TaskAndEventPanel
from scantopath.ui.workspaces import WORKSPACE_PRESENTATION, create_workspace_page


class ShellCompositionMixin:
    """Retain the original QMainWindow methods as inherited behavior."""

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
        self.status_message.setObjectName("statusMessage")
        status.addWidget(self.status_message, 1)
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
        self.task_dock.setMinimumHeight(0)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.task_dock)
        from .task_dock_chrome import TaskDockChrome
        self.task_dock_chrome = TaskDockChrome(self.task_dock, self.task_event_panel)
        self.task_event_panel.expanded_changed.connect(self._resize_task_panel)
        self.task_event_panel.set_demo_tools_visible(False)
        self.task_event_panel.set_expanded(False)
