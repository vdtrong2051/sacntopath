"""C1 smoke: only reuses existing FT11 ReconstructionPanel, no camera/VTK started."""
import pytest
from PySide6.QtWidgets import QApplication
from scantopath.modules.reconstruction.presentation.reconstruction_workflow import ReconstructionPanel


@pytest.fixture
def qt():
    return QApplication.instance() or QApplication([])


def test_c1_controls_are_contextual_and_do_not_open_camera(qt):
    panel=ReconstructionPanel()
    assert panel.c1_button.objectName()=='c1RunGeometry'
    assert not panel.c1_button.isEnabled()
    assert not panel.metric_button.isEnabled()
    panel.set_ready(True,False)
    assert panel.c1_button.isEnabled() and panel.metric_button.isEnabled()
    panel.set_ready(True,True)
    assert not panel.c1_button.isEnabled() and not panel.metric_button.isEnabled()
    panel.close()


def test_c1_signal_emitted_once(qt):
    panel=ReconstructionPanel()
    calls=[]
    panel.c1_requested.connect(lambda: calls.append(1))
    panel.set_ready(True,False)
    panel.c1_button.click()
    assert calls==[1]
    panel.close()
