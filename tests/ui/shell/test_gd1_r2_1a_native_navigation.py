"""R2.1A native QToolBar regression; requires real PySide6, not a signal mock."""
import os
import pytest

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QToolBar, QPushButton
from scantopath.application.contracts import WorkspaceId
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture(scope='module')
def app():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    w = ScanToPathMainWindow()
    w.show(); app.processEvents()
    yield w
    w.close();app.processEvents()


def test_native_qtoolbar_with_four_ordinary_buttons(win):
    assert type(win.workspace_toolbar) is QToolBar
    assert len(win.nav_buttons) == 4
    assert all(type(b) is QPushButton for b in win.nav_buttons.values())
    assert not hasattr(win, 'responsive_toolbar')
    assert not hasattr(win.workspace_toolbar, 'reflow_for_width')
    assert all(b.isEnabled() for b in win.nav_buttons.values())


def test_navigation_context_hidden_without_losing_brand(win):
    assert not win.toolbar_context.isVisible()
    assert win.workspace_toolbar.isVisible()
    assert win.nav_buttons[WorkspaceId.CAPTURE].text() == 'Thu nhận RGB-D'
    assert win.nav_buttons[WorkspaceId.INSPECT3D].text() == 'Kiểm tra 3D'


@pytest.mark.parametrize('width', [720, 850, 900, 1024, 1366])
def test_real_window_resize_preserves_full_label_geometry_and_commands(win, app, width):
    win.resize(width, 650)
    app.processEvents()
    assert win.width() >= 720
    seen = 0
    for workspace, button in win.nav_buttons.items():
        assert button.isEnabled(), f'{workspace} must stay callable regardless of viewport width'
        if button.isVisible():
            needed = button.fontMetrics().horizontalAdvance(button.text()) + 20
            assert button.width() >= needed, (width, workspace, button.width(), needed)
            seen += 1
    assert seen >= 3, f'Unexpected native Qt toolbar overflow at width {width}'
    for idx,workspace in enumerate(WorkspaceId,1):
        assert win.workspace_actions[workspace].shortcut().toString() == f'Ctrl+{idx}'
        win.workspace_actions[workspace].trigger()
        assert win.active_workspace is workspace
        assert win.nav_buttons[workspace].isChecked()


def test_click_works_and_remains_enabled_at_compact_width(win, app):
    win.resize(850,560);app.processEvents()
    for workspace,button in win.nav_buttons.items():
        assert button.isEnabled()
        button.click()
        assert win.active_workspace is workspace
        assert button.isChecked()
