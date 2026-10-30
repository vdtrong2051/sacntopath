"""R3.1 — optional local store bookmarks and an explicit-open Project UI.

No SQLite, RAW or camera import. Selection requests reuse 07.4's guarded
ProjectLoadController. QSettings stores paths only after successful reads.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from scantopath.application.contracts import WorkspaceId


def _normalized_root(root: str) -> str:
    if not isinstance(root, str) or not root.strip():
        raise ValueError("Store root must be a non-empty string")
    # Pure path normalization. Does not open SQLite, follow RAW paths or create dirs.
    return os.path.abspath(os.path.expanduser(root.strip()))


class RecentStorePreferences:
    """Bookmarked locations, never an authority to open/modify data on startup."""

    KEY = "project_workspace/recent_store_roots"
    LIMIT = 8

    def __init__(self, settings: QSettings | None = None) -> None:
        if settings is not None:
            self._settings = settings
        elif os.environ.get("QT_QPA_PLATFORM", "").lower() in ("offscreen", "minimal"):
            # Qt regression opens temporary SQLite fixtures: never pollute the
            # operator's real Recent Stores preferences with test directories.
            temporary = Path(tempfile.gettempdir()) / f"scantopath-qt-r31-{os.getpid()}.ini"
            self._settings = QSettings(str(temporary), QSettings.IniFormat)
        else:
            self._settings = QSettings("ScanToPath", "ScanToPath")

    def paths(self) -> tuple[str, ...]:
        raw = self._settings.value(self.KEY, [])
        candidates = [raw] if isinstance(raw, str) else raw
        if not isinstance(candidates, (list, tuple)):
            return ()
        clean: list[str] = []
        seen: set[str] = set()
        for value in candidates:
            try:
                path = _normalized_root(value)
            except (TypeError, ValueError, OSError):
                continue
            key = os.path.normcase(path)
            if key not in seen:
                seen.add(key)
                clean.append(path)
            if len(clean) >= self.LIMIT:
                break
        return tuple(clean)

    def remember(self, root: str) -> None:
        path = _normalized_root(root)
        existing = [p for p in self.paths() if os.path.normcase(p) != os.path.normcase(path)]
        self._settings.setValue(self.KEY, [path, *existing][:self.LIMIT])
        self._settings.sync()

    def forget(self, root: str) -> None:
        path = _normalized_root(root)
        self._settings.setValue(self.KEY, [p for p in self.paths()
                                             if os.path.normcase(p) != os.path.normcase(path)])
        self._settings.sync()


class RecentStorePanel(QFrame):
    """Central Project store panel; source of truth remains the existing loader."""

    browse_requested = Signal()
    init_default_requested = Signal()
    open_requested = Signal(str)
    forget_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("recentStorePanel")
        self.setAccessibleName("Quản lý kho dữ liệu")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 13, 16, 14)
        layout.setSpacing(9)

        title_row = QHBoxLayout()
        heading = QLabel("KHO DỮ LIỆU", self)
        heading.setObjectName("recentStoreHeading")
        title_row.addWidget(heading)
        title_row.addStretch(1)
        self.browse_button = QPushButton("Mở kho khác…", self)
        self.browse_button.setObjectName("recentStoreBrowse")
        self.browse_button.clicked.connect(self.browse_requested.emit)
        title_row.addWidget(self.browse_button)
        self.init_button = QPushButton("Khởi tạo scantopath-data", self)
        self.init_button.setObjectName("recentStoreInitializeDefault")
        self.init_button.setToolTip("Chỉ khởi tạo kho SQLite v2 khi bạn xác nhận; không ghi đè kho đã có.")
        self.init_button.clicked.connect(self.init_default_requested.emit)
        title_row.addWidget(self.init_button)
        layout.addLayout(title_row)
        top_separator = QFrame(self)
        top_separator.setObjectName("recentStoreTopSeparator")
        top_separator.setFixedHeight(1)
        layout.addWidget(top_separator)

        self.name_label = QLabel("Chưa mở kho dữ liệu", self)
        self.name_label.setObjectName("recentStoreName")
        layout.addWidget(self.name_label)
        self.path_label = QLabel("Hãy chọn một kho có metadata.sqlite3.", self)
        self.path_label.setObjectName("recentStorePath")
        self.path_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.path_label)
        self.state_label = QLabel("Trạng thái: Chưa tải · Không tự mở SQLite", self)
        self.state_label.setObjectName("recentStoreState")
        layout.addWidget(self.state_label)

        separator = QFrame(self)
        separator.setObjectName("recentStoreListSeparator")
        separator.setFixedHeight(1)
        layout.addWidget(separator)
        recent_heading = QLabel("KHO ĐÃ MỞ GẦN ĐÂY", self)
        recent_heading.setObjectName("recentStoreListHeading")
        layout.addWidget(recent_heading)
        self.empty_label = QLabel("Chưa có kho gần đây.", self)
        self.empty_label.setObjectName("recentStoreEmpty")
        layout.addWidget(self.empty_label)
        self.recent_list = QListWidget(self)
        self.recent_list.setObjectName("recentStoreList")
        self.recent_list.setMaximumHeight(130)
        self.recent_list.itemDoubleClicked.connect(self._open_item)
        self.recent_list.itemSelectionChanged.connect(self._update_buttons)
        layout.addWidget(self.recent_list)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.open_button = QPushButton("Mở kho đã chọn", self)
        self.open_button.setObjectName("recentStoreOpenSelected")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_selected)
        actions.addWidget(self.open_button)
        self.forget_button = QPushButton("Bỏ khỏi danh sách", self)
        self.forget_button.setObjectName("recentStoreForget")
        self.forget_button.setEnabled(False)
        self.forget_button.clicked.connect(self._forget_selected)
        actions.addWidget(self.forget_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        self._root_path = ""
        self._busy = False

    def _selected_path(self) -> str | None:
        item = self.recent_list.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def _update_buttons(self) -> None:
        selected = self._selected_path() is not None
        self.open_button.setEnabled(selected and not self._busy)
        self.forget_button.setEnabled(selected and not self._busy)

    def _open_item(self, item: QListWidgetItem) -> None:
        if not self._busy:
            self.open_requested.emit(item.data(Qt.UserRole))

    def _open_selected(self) -> None:
        root = self._selected_path()
        if root and not self._busy:
            self.open_requested.emit(root)

    def _forget_selected(self) -> None:
        root = self._selected_path()
        if root and not self._busy:
            self.forget_requested.emit(root)

    def display_recent(self, paths: tuple[str, ...]) -> None:
        prior = self._selected_path()
        self.recent_list.clear()
        for root in paths:
            folder = Path(root)
            available = folder.is_dir()  # Folder hint only; loader validates SQLite.
            label = folder.name or root
            if not available:
                label += "  ·  Không còn tại đường dẫn cũ"
            item = QListWidgetItem(label, self.recent_list)
            item.setData(Qt.UserRole, root)
            item.setToolTip(root)
            if root == prior:
                self.recent_list.setCurrentItem(item)
        self.empty_label.setVisible(not paths)
        self.recent_list.setVisible(bool(paths))
        self._update_buttons()

    def show_store(self, root: str, schema: int) -> None:
        self._root_path = root
        self.name_label.setText(Path(root).name or root)
        self.path_label.setToolTip(root)
        self.state_label.setText(f"Đã mở · SQLite v{schema} · Chỉ tải theo yêu cầu")
        self._elide_path()

    def show_error(self, message: str) -> None:
        self._root_path = ""
        self.name_label.setText("Không có kho đang mở")
        self.path_label.setToolTip("")
        self.path_label.setText("Chọn kho gần đây hoặc mở thư mục khác.")
        self.state_label.setText(message)

    def set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        self.browse_button.setEnabled(not busy)
        self.init_button.setEnabled(not busy)
        self.recent_list.setEnabled(not busy)
        if busy:
            self.state_label.setText("Đang kiểm tra và tải kho dữ liệu…")
        self._update_buttons()

    def _elide_path(self) -> None:
        if self._root_path:
            width = max(160, self.width() - 38)
            self.path_label.setText(self.path_label.fontMetrics().elidedText(
                self._root_path, Qt.ElideMiddle, width))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._elide_path()


class RecentStorePresenter:
    """Feature-local composition; no imports of SQLite or backend in Qt widgets."""

    def __init__(self, view: QWidget, loader, controller,
                 preferences: RecentStorePreferences | None = None) -> None:
        self._prefs = preferences if preferences is not None else RecentStorePreferences()
        self.panel = RecentStorePanel()
        scroll = view._pages[WorkspaceId.PROJECTS].findChild(QScrollArea, "workspaceScroll_projects")
        if scroll is None or scroll.widget() is None:
            raise RuntimeError("Missing Project workspace host")
        content = scroll.widget()
        content.layout().insertWidget(3, self.panel)
        # Keep older objectName/test command contract, not its duplicate welcome card.
        legacy = content.findChild(QFrame, "workspacePanel")
        if legacy is not None:
            legacy.hide()
        self.panel.display_recent(self._prefs.paths())
        self.panel.browse_requested.connect(view._choose_project_store)
        self.panel.init_default_requested.connect(controller._initialize_default_store)
        self.panel.open_requested.connect(controller._begin_project_load)
        self.panel.forget_requested.connect(self._forget)
        loader.loaded.connect(self._on_loaded)
        loader.failed.connect(self._on_failed)
        loader.busy_changed.connect(self.panel.set_busy)

    def _on_loaded(self, bundle) -> None:
        # Only a valid, fully loaded existing store becomes a recent bookmark.
        self._prefs.remember(bundle.info.root)
        self.panel.show_store(bundle.info.root, bundle.info.schema_version)
        self.panel.display_recent(self._prefs.paths())

    def _on_failed(self, message: str) -> None:
        self.panel.show_error(message)
        self.panel.display_recent(self._prefs.paths())

    def _forget(self, root: str) -> None:
        self._prefs.forget(root)
        self.panel.display_recent(self._prefs.paths())
