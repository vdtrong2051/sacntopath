"""Windows Qt offscreen regression: no disconnect warning, no callback accumulation."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from scantopath.modules.project_workspace.presentation.ft07_project_hub import ProjectHub


def test_project_hub_reuses_one_signal_connection(qtbot=None):
    app=QApplication.instance() or QApplication([])
    hub=ProjectHub()
    calls=[]
    hub._reset_button(hub.primary,'First',lambda: calls.append('first'))
    hub.primary.click()
    hub._reset_button(hub.primary,'Second',lambda: calls.append('second'))
    hub.primary.click()
    hub._reset_button(hub.primary,'',None)
    assert calls == ['first','second']
    assert hub.primary.isHidden()
    hub.deleteLater()
