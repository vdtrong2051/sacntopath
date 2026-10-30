"""GD2-09.09.3 — compact Capture workspace composition, with NO data or camera I/O.

Keep Live/ROI and RAW Replay controllers unchanged. Both widgets remain alive;
only their visual layout changes. The global shell still has four workspaces.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)

from scantopath.application.contracts import WorkspaceId


class CaptureWorkspaceLayout:
    """A presentation-only layout adapter for the existing Live and Replay panels.

    Tabs avoid stacking two large 16:9 RGB-D viewers inside a small central
    viewport. Selecting a Capture opens the Replay tab, while selecting an
    active Session returns to Live controls. No SDK, RAW or SQLite access.
    """

    def __init__(self, view) -> None:
        self.view = view
        page = view.page_for(WorkspaceId.CAPTURE)
        host = page.findChild(QWidget, "workspaceScrollContent")
        if host is None or host.layout() is None:
            raise RuntimeError("Capture workspace host missing")

        outer = host.layout()
        live = view.capture_live.panel
        replay = view.capture_preview.panel
        if outer.indexOf(live) < 0 or outer.indexOf(replay) < 0:
            raise RuntimeError("Capture panels must be attached before layout")

        # The real controls and native data are in these panels; hide only the
        # obsolete 06.3 placeholder heading/subtitle, NOT any actual controls.
        for name in ("workspaceHeading", "workspaceSubtitle", "workspaceEyebrow"):
            heading = host.findChild(QLabel, name, Qt.FindDirectChildrenOnly)
            if heading is not None:
                heading.hide()

        outer.setContentsMargins(24, 10, 24, 16)
        outer.setSpacing(6)

        self.workflow_bar = QFrame(host)
        self.workflow_bar.setObjectName("captureWorkflowBar")
        workflow = QHBoxLayout(self.workflow_bar)
        workflow.setContentsMargins(10, 6, 10, 6)
        workflow.setSpacing(12)
        label = QLabel("THU NHẬN RGB-D", self.workflow_bar)
        label.setObjectName("captureWorkflowHeading")
        workflow.addWidget(label)
        hint = QLabel("Session → Kết nối → Chụp và lưu → Capture → Phát lại", self.workflow_bar)
        hint.setObjectName("captureWorkflowHint")
        hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        hint.setWordWrap(True)
        hint.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        workflow.addWidget(hint, 1)

        # Capture the location BEFORE reparenting: QTabWidget.addTab() moves
        # widgets out of their previous QLayout automatically.
        insertion_index = min(outer.indexOf(live), outer.indexOf(replay))
        outer.removeWidget(live)
        outer.removeWidget(replay)

        self.tabs = QTabWidget(host)
        self.tabs.setObjectName("captureWorkspaceTabs")
        self.tabs.setDocumentMode(False)
        self.tabs.setUsesScrollButtons(False)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tabs.setMinimumHeight(390)
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.addTab(live, "01  Thu nhận trực tiếp")
        self.tabs.addTab(replay, "02  RAW đã lưu · Phát lại")
        self.tabs.setTabToolTip(0, "Gemini 2 Live, ROI, chọn Session và Chụp và lưu")
        self.tabs.setTabToolTip(1, "Chọn Capture từ Cây dự án để phát lại RGB/Depth")
        self.tabs.setCurrentWidget(live)

        # Insert both blocks ahead of the hidden 06.3 placeholder, preserving
        # other global workspace widgets and QScrollArea ownership.
        outer.insertWidget(insertion_index, self.workflow_bar)
        outer.insertWidget(insertion_index + 1, self.tabs, 1)

        # Local, limited style: never override the global QSS or widget names.
        self.workflow_bar.setStyleSheet(
            "QFrame#captureWorkflowBar { background: #e7eef9; "
            "border: 1px solid #cddbf0; border-radius: 5px; } "
            "QLabel#captureWorkflowHeading { font-weight: 650; color: #16345b; } "
            "QLabel#captureWorkflowHint { color: #425f82; }"
        )
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #d4deec; "
            "border-radius: 4px; background: #ffffff; } "
            "QTabBar::tab { padding: 7px 14px; min-width: 120px; }"
        )

        # Selection authority remains the existing global Project Explorer.
        view.project_explorer.selection_changed.connect(self._on_selection)

    def _on_selection(self, selection: object) -> None:
        if self.view.active_workspace is not WorkspaceId.CAPTURE:
            return
        kind = getattr(selection, "entity_type", None)
        if kind == "capture":
            self.tabs.setCurrentWidget(self.view.capture_preview.panel)
        elif kind == "scan_session":
            self.tabs.setCurrentWidget(self.view.capture_live.panel)
