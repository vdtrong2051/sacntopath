"""C2 UI smoke: signal routing, disabled actions until verified output exists."""
import pytest
from PySide6.QtWidgets import QApplication
from scantopath.modules.reconstruction.presentation.reconstruction_workflow import ReconstructionPanel


@pytest.fixture
def qt():
    return QApplication.instance() or QApplication([])


def test_c2_actions_enable_only_with_c1_or_c2(qt):
    panel=ReconstructionPanel()
    panel.set_ready(False,False)
    assert panel.c2_open.isEnabled()
    assert not panel.c2_button.isEnabled()
    assert not panel.c2_mesh.isEnabled()
    panel.set_c2_available(True,False)
    panel.set_ready(True,False)
    assert panel.c2_button.isEnabled()
    assert not panel.c2_contour.isEnabled()
    panel.set_c2_available(True,True)
    panel.set_ready(True,False)
    assert all(b.isEnabled() for b in (panel.c2_mesh,panel.c2_contour,panel.c2_zigzag))
    panel.set_ready(True,True)
    assert not panel.c2_button.isEnabled()
    assert not panel.c2_open.isEnabled()
    panel.close()


def test_c2_buttons_emit_correct_mode(qt):
    panel=ReconstructionPanel()
    operations=[]
    panel.c2_view_requested.connect(operations.append)
    panel.set_c2_available(True,True)
    panel.set_ready(True,False)
    panel.c2_mesh.click()
    panel.c2_zigzag.click()
    panel.c2_contour.click()
    assert operations==['mesh','zigzag','contour']
    panel.close()
