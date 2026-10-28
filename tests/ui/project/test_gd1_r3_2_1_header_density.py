"""R3.2.1 – real Qt workspace header density without repositioning feature panels."""
import os
import pytest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PySide6')
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QFrame
from scantopath.application.contracts import WorkspaceId
from scantopath.ui.shell import ScanToPathMainWindow

@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app):
    win=ScanToPathMainWindow()
    win.resize(1440,900)
    win.show()
    app.processEvents()
    yield win
    win.close()
    app.processEvents()

@pytest.mark.parametrize('workspace', list(WorkspaceId))
def test_compact_header_keeps_original_structure(window, workspace, app):
    page=window.page_for(workspace)
    page_content=page.findChild(QWidget,'workspaceScrollContent')
    outer=page_content.layout()
    margins=outer.contentsMargins()
    assert (margins.left(),margins.top(),margins.right(),margins.bottom())==(24,10,24,16)
    assert outer.spacing()==6
    eyebrow=page.findChild(QLabel,'workspaceEyebrow')
    assert eyebrow is not None and eyebrow.isHidden()
    heading=page.findChild(QLabel,'workspaceHeading')
    description=page.findChild(QLabel,'workspaceSubtitle')
    assert heading.text()
    assert description.text()
    # Preserve layout positions: R3.1 inserts at 3, R3.2 inserts at 4.
    assert outer.itemAt(0).widget() is eyebrow
    assert outer.itemAt(1).widget() is heading
    assert outer.itemAt(2).widget() is description


def test_project_header_keeps_r31_and_r32_panels_in_order(window,app):
    page=window.page_for(WorkspaceId.PROJECTS)
    content=page.findChild(QWidget,'workspaceScrollContent')
    layout=content.layout()
    store=window.project_workspace.recent_stores.panel
    dash=window.project_workspace.project_dashboard.panel
    assert layout.itemAt(3).widget() is store
    assert layout.itemAt(4).widget() is dash
    assert store.isVisible()
    assert not dash.isVisible()
    eyebrow=page.findChild(QLabel,'workspaceEyebrow')
    assert eyebrow.isHidden()
    heading=page.findChild(QLabel,'workspaceHeading')
    description=page.findChild(QLabel,'workspaceSubtitle')
    head_y=heading.mapTo(content,QPoint(0,0)).y()
    desc_bottom=description.mapTo(content,QPoint(0,description.height())).y()
    store_top=store.mapTo(content,QPoint(0,0)).y()
    assert 0 <= head_y <= 20, head_y
    assert 0 <= store_top-desc_bottom <= 25, (desc_bottom,store_top)
    # No auto-opening a user database on launch.
    assert window.project_explorer.store_root is None
