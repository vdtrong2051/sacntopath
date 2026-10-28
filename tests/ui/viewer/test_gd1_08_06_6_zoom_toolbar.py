"""GĐ1 08.06.6: regression for live Viewer zoom toolbar."""

from PySide6.QtWidgets import QApplication, QWidget

from scantopath.modules.viewer3d.application.navigation import CameraView
from scantopath.modules.viewer3d.presentation.interactive_controller import (
    InteractiveViewer3DController,
)


def test_r53_toolbar_zoom_maps_to_camera_intents(monkeypatch):
    app = QApplication.instance() or QApplication([])

    root = QWidget()
    controller = InteractiveViewer3DController(
        root,
        session_factory=lambda: None,
    )

    try:
        root.show()
        controller.page.show()
        app.processEvents()

        calls = []

        def record(self, action, dx=0.0, dy=0.0):
            CameraView().update(action, dx, dy)
            calls.append((action, dx, dy))
            return True

        monkeypatch.setattr(
            type(controller),
            "navigate",
            record,
        )

        controller._live_phase = "ready"
        controller._last_frame_revision = 1
        controller._ready_tools()

        for button in (
            "viewer3dToolZoomIn",
            "viewer3dToolZoomOut",
            "viewer3dToolFit",
            "viewer3dToolAxes",
        ):
            controller.tools.buttons[button].click()

        assert calls == [
            ("zoom", 1.0, 0.0),
            ("zoom", -1.0, 0.0),
            ("reset", 0.0, 0.0),
            ("axes", 0.0, 0.0),
        ]

    finally:
        controller._poll_timer.stop()
        controller.page.close()
        root.close()