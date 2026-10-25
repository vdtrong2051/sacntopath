"""R2.2.1 — small task-dock chrome. UI-only: no database, worker or VTK."""
from __future__ import annotations

from PySide6.QtCore import Qt, QPointF, QRectF, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QDockWidget, QHBoxLayout, QLabel, QToolButton, QWidget


def _dock_chrome_icon(kind: str) -> QIcon:
    """Draw editor-like monochrome dock glyphs without OS fonts or icon files."""
    image = QPixmap(32, 32)
    image.setDevicePixelRatio(2.0)  # 16 logical px; sharp on 100/200% DPI
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#526984"))
    pen.setWidthF(1.35)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    if kind == "collapse":
        painter.drawLine(QPointF(3.5, 10.5), QPointF(12.5, 10.5))
    elif kind == "expand":
        painter.drawRect(QRectF(3.5, 4.0, 9.0, 8.5))
        painter.drawLine(QPointF(3.5, 6.5), QPointF(12.5, 6.5))
    elif kind == "float":
        painter.drawRect(QRectF(5.0, 3.5, 7.5, 7.5))
        painter.drawLine(QPointF(3.0, 6.5), QPointF(3.0, 12.5))
        painter.drawLine(QPointF(3.0, 12.5), QPointF(9.0, 12.5))
    elif kind == "close":
        painter.drawLine(QPointF(4.0, 4.0), QPointF(12.0, 12.0))
        painter.drawLine(QPointF(12.0, 4.0), QPointF(4.0, 12.0))
    else:
        painter.end()
        raise ValueError(f"Unknown dock icon: {kind}")
    painter.end()
    return QIcon(image)


class TaskDockChrome(QWidget):
    """Own the dock title controls; shell owns only composition and delegation."""

    def __init__(self, dock: QDockWidget, panel: QWidget) -> None:
        super().__init__(dock)
        self._dock = dock
        self._panel = panel
        self.setObjectName("taskDockTitleBar")
        self.setAccessibleName("Thanh tiêu đề bảng tác vụ")
        row = QHBoxLayout(self)
        row.setContentsMargins(9, 1, 6, 1)
        row.setSpacing(5)
        title = QLabel("Tác vụ và thông báo", self)
        title.setObjectName("taskDockTitle")
        row.addWidget(title)
        self.summary = QLabel(panel.compact_summary.text(), self)
        self.summary.setObjectName("taskDockTitleSummary")
        self.summary.setToolTip("Tác vụ UI hiện tại; không phải ProcessingRun trong SQLite")
        row.addWidget(self.summary, stretch=1)

        # Reuse the existing button and signal: 06–08 and R2.2 test hooks stay valid.
        panel.compact_header.removeWidget(panel.expand_button)
        panel.compact_header.removeWidget(panel.compact_summary)
        panel.layout().removeItem(panel.compact_header)
        panel.compact_summary.hide()
        panel.expand_button.setParent(self)
        panel.expand_button.setFixedSize(26, 24)
        panel.expand_button.setIconSize(QSize(16, 16))
        row.addWidget(panel.expand_button)

        self.float_button = QToolButton(self)
        self.float_button.setObjectName("taskDockFloatButton")
        self.float_button.setText("")
        self.float_button.setIcon(_dock_chrome_icon("float"))
        self.float_button.setIconSize(QSize(16, 16))
        self.float_button.setToolTip("Tách/ghép bảng tác vụ")
        self.float_button.setAccessibleName("Tách hoặc ghép bảng tác vụ")
        self.float_button.setFixedSize(25, 24)
        self.float_button.clicked.connect(self._toggle_floating)
        row.addWidget(self.float_button)

        self.close_button = QToolButton(self)
        self.close_button.setObjectName("taskDockCloseButton")
        self.close_button.setText("")
        self.close_button.setIcon(_dock_chrome_icon("close"))
        self.close_button.setIconSize(QSize(16, 16))
        self.close_button.setToolTip("Ẩn bảng tác vụ (mở lại qua Hiển thị)")
        self.close_button.setAccessibleName("Ẩn bảng tác vụ")
        self.close_button.setFixedSize(25, 24)
        self.close_button.clicked.connect(dock.hide)
        row.addWidget(self.close_button)

        dock.setTitleBarWidget(self)
        panel.summary_changed.connect(self.summary.setText)
        panel.expanded_changed.connect(self._sync_expand_icon)
        self._sync_expand_icon(panel.expanded)

        # Remove the duplicate padded summary row from the *shell* panel only.
        # Standalone TaskAndEventPanel retains its legacy layout for old tests.
        panel.layout().setContentsMargins(6, 0, 6, 4)
        panel.layout().setSpacing(0)

    def _sync_expand_icon(self, expanded: bool) -> None:
        button = self._panel.expand_button
        button.setText("")
        button.setIcon(_dock_chrome_icon("collapse" if expanded else "expand"))
        button.setToolTip("Thu gọn bảng tác vụ" if expanded else "Mở rộng bảng tác vụ")
        button.setAccessibleName(button.toolTip())

    def _toggle_floating(self) -> None:
        self._dock.setFloating(not self._dock.isFloating())

    def resize_to(self, window_height: int) -> None:
        if self._dock.isVisible() and not self._dock.isFloating():
            height = (176 if window_height >= 690 else 160) if self._panel.expanded else 40
            self._dock.parentWidget().resizeDocks([self._dock], [height], Qt.Vertical)

    def open_audit(self) -> None:
        self._panel.set_expanded(True)
        self._dock.show()
        self._dock.raise_()
        self._panel.tabs.setCurrentIndex(2)
        self.resize_to(self._dock.parentWidget().height())

    def install_developer_tools(self, help_menu) -> None:
        from PySide6.QtGui import QAction
        action = QAction("Công cụ kiểm thử UI (chế độ phát triển)", self)
        action.setObjectName("actionTaskDemoTools")
        action.setCheckable(True)
        action.toggled.connect(self._set_dev_mode)
        help_menu.addAction(action)

    def _set_dev_mode(self, enabled: bool) -> None:
        self._panel.set_demo_tools_visible(enabled)
        if enabled:
            self._panel.set_expanded(True)
            self._dock.show()
            self.resize_to(self._dock.parentWidget().height())
