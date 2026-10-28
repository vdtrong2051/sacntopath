"""07.9B design boundaries without requiring Qt on headless build hosts."""
from pathlib import Path


def _root():
    return Path(__file__).resolve().parents[3]


def test_native_docks_are_explicitly_outlined_without_wash():
    qss = (_root() / 'src/scantopath/ui/theme/hmi_panel.qss').read_text(encoding='utf-8')
    assert 'QDockWidget#explorerDock, QDockWidget#inspectorDock, QDockWidget#taskDock' in qss
    assert 'border: 1px solid #C7D6E7;' in qss
    assert 'QWidget#desktopRoot' in qss
    assert 'QFrame#workspacePanel' in qss
    assert 'border: 1px solid #C9D8EA' in qss
    assert 'QTabWidget::pane { border: 1px solid #C9D9EB' in qss
    assert '#1463D7' in qss  # preserve approved accent


def test_compact_docks_and_existing_unmeasured_contract_remain():
    mw = (_root() / 'src/scantopath/ui/shell/main_window.py').read_text(encoding='utf-8')
    pages = (_root() / 'src/scantopath/ui/workspaces/pages.py').read_text(encoding='utf-8')
    assert 'self.explorer_dock.setMinimumWidth(205)' in mw
    assert 'self.inspector_dock.setMinimumWidth(215)' in mw
    assert 'self.workspace_toolbar' in mw
    assert 'QSizePolicy.Ignored' in mw
    assert 'Chưa chạy phép đo' in pages
    assert 'state.setWordWrap(True)' in pages
    assert 'planned.setWordWrap(True)' in pages
    assert 'message.setWordWrap(True)' in pages


def test_hmi_keeps_long_labels_accessible_without_forcing_wide_panels():
    root = _root() / 'src/scantopath/ui/components'
    explorer = (root / 'project_explorer.py').read_text(encoding='utf-8')
    inspector = (root / 'property_inspector.py').read_text(encoding='utf-8')
    tasks = (root / 'task_event_panel.py').read_text(encoding='utf-8')
    assert 'item.setToolTip(0, node.label)' in explorer
    assert 'self.tree.setTextElideMode(Qt.ElideMiddle)' in explorer
    assert 'item.setToolTip(1, value)' in inspector
    assert 'self.details.setTextElideMode(Qt.ElideMiddle)' in inspector
    assert 'QBoxLayout.TopToBottom if self.width() < 460' in tasks
