"""R2.2.3A final HMI behavior, real PySide6, no synthetic worker/SQLite access."""
from __future__ import annotations
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QToolButton
from scantopath.ui.shell import ScanToPathMainWindow

@pytest.fixture(scope='module')
def app():
    yield QApplication.instance() or QApplication([])

@pytest.fixture
def window(app):
    win=ScanToPathMainWindow()
    win.show();app.processEvents()
    yield win
    win.close();app.processEvents()

def test_exactly_three_independent_title_actions(window,app):
    bar=window.task_dock_chrome
    minus=window.task_event_panel.expand_button
    square=bar.maximize_button
    close=bar.close_button
    assert bar.height()==44
    assert window.task_dock.titleBarWidget() is bar
    assert not hasattr(bar,'float_button')
    assert len(bar.findChildren(QToolButton))==2
    assert all(b.isVisible() for b in (minus,square,close))
    assert minus.parentWidget() is bar
    assert len({id(b) for b in (minus,square,close)})==3
    assert all(not b.icon().isNull() and b.toolTip() for b in (minus,square,close))
    assert minus.geometry().right() < square.geometry().left()
    assert square.geometry().right() < close.geometry().left()

def test_minus_square_x_have_distinct_behaviors(window,app):
    bar=window.task_dock_chrome
    panel=window.task_event_panel
    assert not panel.expanded
    # Minus toggles content only, square maximizes within QMainWindow (not floating).
    panel.expand_button.click();app.processEvents()
    assert panel.expanded and panel.tabs.isVisible()
    panel.expand_button.click();app.processEvents()
    assert not panel.expanded and panel.tabs.isHidden()
    bar.maximize_button.click();app.processEvents()
    assert panel.expanded and bar._maximized
    assert not window.task_dock.isFloating()
    assert 'Khôi phục' in bar.maximize_button.toolTip()
    bar.maximize_button.click();app.processEvents()
    assert not bar._maximized and not panel.expanded
    assert not window.task_dock.isFloating()
    bar.close_button.click();app.processEvents()
    assert not window.task_dock.isVisible()
    window.task_dock.toggleViewAction().trigger();app.processEvents()
    assert window.task_dock.isVisible()

def test_clear_visual_hierarchy_and_no_fixed_explanation_rows(window,app):
    qss=window.styleSheet()
    assert '/* R2.2.3A-FINAL:' in qss
    assert 'border-bottom: 1px solid #B8CAE0;' in qss
    assert 'border-top: 1px solid #C9D9EA;' in qss
    p=window.task_event_panel
    p.set_expanded(True)
    p.tabs.setCurrentIndex(1);app.processEvents()
    assert p.event_hint.isHidden() and p.event_empty.isVisible()
    assert p.event_blank_spacer.isVisible()
    p.add_ui_event('R2.2.3A event')
    app.processEvents()
    assert p.event_empty.isHidden() and p.event_blank_spacer.isHidden()
    assert p.events.isVisible()
    p.tabs.setCurrentIndex(2);app.processEvents()
    assert p.audit_hint.isHidden()
    assert p.audit_table.isVisible()
    assert p.audit_table.columnWidth(0)>=235
    assert p.audit_table.height()>=max(1,p.tabs.currentWidget().height()-4)

def test_task_empty_is_top_anchored_and_list_still_fills(window,app):
    from scantopath.application.contracts import TaskSnapshot,TaskState
    p=window.task_event_panel
    p.set_expanded(True)
    p.tabs.setCurrentIndex(0);app.processEvents()
    assert p.task_empty.text()=='Chưa có tác vụ.'
    assert p.task_blank_spacer.isVisible()
    assert p.task_empty.geometry().top() < p.tabs.currentWidget().height()//2
    p.set_tasks((TaskSnapshot(task_id='job-1',title='Job',state=TaskState.RUNNING,can_cancel=True),))
    app.processEvents()
    assert p.tasks.isVisible() and p.task_blank_spacer.isHidden()
    assert p.tasks.topLevelItemCount()==1
    p.set_tasks(())
