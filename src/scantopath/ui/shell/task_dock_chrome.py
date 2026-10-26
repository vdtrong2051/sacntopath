"""R2.2.1 — small task-dock chrome. UI-only: no database, worker or VTK."""
from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QSize, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QDockWidget, QFrame, QHBoxLayout, QLabel, QToolButton, QWidget


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
    elif kind == "maximize":
        painter.drawRect(QRectF(3.5, 3.5, 9.0, 9.0))
    elif kind == "restore":
        painter.drawRect(QRectF(3.0, 5.5, 8.0, 7.5))
        painter.drawLine(QPointF(5.0, 3.0), QPointF(12.5, 3.0))
        painter.drawLine(QPointF(12.5, 3.0), QPointF(12.5, 10.5))
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
        row.setContentsMargins(14, 4, 12, 4)
        row.setSpacing(14)
        self.setFixedHeight(44)
        self._maximized = False
        self._restore_expanded = False
        title = QLabel("Tác vụ và thông báo", self)
        title.setObjectName("taskDockTitle")
        row.addWidget(title)
        self.summary = QLabel(panel.compact_summary.text(), self)
        self.summary.setObjectName("taskDockTitleSummary")
        self.summary.setToolTip("Tác vụ UI hiện tại; không phải ProcessingRun trong SQLite")
        row.addWidget(self.summary)
        row.addStretch(1)

        # Reuse the existing button and signal: 06–08 and R2.2 test hooks stay valid.
        panel.compact_header.removeWidget(panel.expand_button)
        panel.compact_header.removeWidget(panel.compact_summary)
        panel.layout().removeItem(panel.compact_header)
        panel.compact_summary.hide()
        panel.expand_button.setParent(self)
        panel.expand_button.setFixedSize(28, 26)
        panel.expand_button.setIconSize(QSize(16, 16))
        row.addWidget(panel.expand_button)

        # Distinct square action: maximize the dock within the main window,
        # then restore its previous height. This is NOT the unreliable float action.
        self.maximize_button = QToolButton(self)
        self.maximize_button.setObjectName("taskDockMaximizeButton")
        self.maximize_button.setText("")
        self.maximize_button.setIconSize(QSize(16, 16))
        self.maximize_button.setFixedSize(28, 26)
        self.maximize_button.clicked.connect(self._toggle_maximize)
        row.addWidget(self.maximize_button)

        self.close_button = QToolButton(self)
        self.close_button.setObjectName("taskDockCloseButton")
        self.close_button.setText("")
        self.close_button.setIcon(_dock_chrome_icon("close"))
        self.close_button.setIconSize(QSize(16, 16))
        self.close_button.setToolTip("Ẩn bảng tác vụ (mở lại qua Hiển thị)")
        self.close_button.setAccessibleName("Ẩn bảng tác vụ")
        self.close_button.setFixedSize(28, 26)
        self.close_button.clicked.connect(dock.hide)
        row.addWidget(self.close_button)

        dock.setTitleBarWidget(self)
        panel.summary_changed.connect(self.summary.setText)
        panel.expanded_changed.connect(self._sync_expand_icon)
        self._sync_expand_icon(panel.expanded)
        self._sync_maximize_icon()

        # Remove the duplicate padded summary row from the *shell* panel only.
        # Standalone TaskAndEventPanel retains its legacy layout for old tests.
        panel.layout().setContentsMargins(0, 0, 0, 0)
        panel.layout().setSpacing(0)
        # R2.2.3C-REPAIR: physical separator with reserved layout space.
        # Do not paint a line over the tab bar using TaskDockChrome.paintEvent.
        self._header_separator = QFrame(panel)
        self._header_separator.setObjectName("taskDockHeaderSeparator")
        self._header_separator.setFixedHeight(1)
        panel.layout().insertWidget(0, self._header_separator)
        panel.expanded_changed.connect(self._sync_header_gutter)
        self._sync_header_gutter(panel.expanded)

    def _sync_header_gutter(self, expanded: bool) -> None:
        """Keep title and tabs in independent vertical bands."""
        self._header_separator.setVisible(expanded)
        self._panel.layout().setContentsMargins(6, 16 if expanded else 0, 6, 4)
        if expanded:
            QTimer.singleShot(0, self._ensure_tab_clearance)

    def _ensure_tab_clearance(self) -> None:
        """Correct the actual Qt geometry; never draw across navigation labels."""
        if not self._panel.expanded or not self._panel.tabs.isVisible() or not self.isVisible():
            return
        header_bottom = self.mapTo(self._dock, QPoint(0, self.height())).y()
        tab_top = self._panel.tabs.tabBar().mapTo(self._dock, QPoint(0, 0)).y()
        missing = header_bottom + 3 - tab_top
        if missing > 0:
            layout = self._panel.layout()
            left, top, right, bottom = layout.getContentsMargins()
            layout.setContentsMargins(left, min(40, top + missing), right, bottom)
            layout.invalidate()

    def _sync_expand_icon(self, expanded: bool) -> None:
        button = self._panel.expand_button
        button.setText("")
        # Preserve the dedicated minus glyph in both states; never combine
        # expand/collapse with the independent maximize-square control.
        button.setIcon(_dock_chrome_icon("collapse"))
        button.setToolTip("Thu gọn bảng tác vụ" if expanded else "Mở rộng bảng tác vụ")
        button.setAccessibleName(button.toolTip())
        if not expanded and self._maximized:
            self._maximized = False
            self._sync_maximize_icon()

    def _sync_maximize_icon(self) -> None:
        button = self.maximize_button
        button.setIcon(_dock_chrome_icon("restore" if self._maximized else "maximize"))
        caption = "Khôi phục kích thước bảng tác vụ" if self._maximized else "Phóng lớn bảng tác vụ"
        button.setToolTip(caption)
        button.setAccessibleName(caption)

    def _toggle_maximize(self) -> None:
        main = self._dock.parentWidget()
        if not self._maximized:
            self._restore_expanded = self._panel.expanded
            self._panel.set_expanded(True)
            self._maximized = True
            self.resize_to(main.height())
        else:
            self._maximized = False
            self._panel.set_expanded(self._restore_expanded)
            # Reapply the REAL geometry cap when leaving maximized mode.
            self.resize_to(main.height())
        self._sync_maximize_icon()

    def resize_to(self, window_height: int) -> None:
        """R2.2.3B REAL DOCK GEOMETRY FIX.

        resizeDocks() alone is a relative weight, NOT a pixel cap. Apply the
        dock's maximumHeight before resizing, so the workspace retains space.
        The square action deliberately permits a larger (still bounded) dock.
        """
        if not self._dock.isVisible() or self._dock.isFloating():
            return
        window_height = max(1, int(window_height))
        if self._maximized:
            # Intentionally larger view; still leave most of the window above.
            target = min(310, max(235, int(window_height * 0.34)))
        elif self._panel.expanded:
            target = min(190, max(150, int(window_height * 0.22)))
        else:
            target = 52  # 44px title + native dock frame room
        # Critical: prevent Qt's dock-area layout from growing beyond target.
        self._dock.setMaximumHeight(target)
        self._dock.parentWidget().resizeDocks([self._dock], [target], Qt.Vertical)
        if self._panel.expanded:
            QTimer.singleShot(0, self._ensure_tab_clearance)

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
