"""Lazy R5.2 Viewer composition; native VTK never runs in the Qt process.

The desktop composition layer owns the choice between the accepted legacy PNG
controller for Qt offscreen tests and the isolated resident renderer on Windows.
"""
from __future__ import annotations


def create_viewer_controller(parent):
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.platformName().lower() in ('offscreen', 'minimal'):
        from scantopath.modules.viewer3d.presentation.controller import Viewer3DController
        return Viewer3DController(parent)
    from scantopath.modules.viewer3d.presentation.live_controller import LiveViewer3DController
    from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import CoalescingRenderSession
    return LiveViewer3DController(
        parent, session_factory=lambda: CoalescingRenderSession(640, 480, timeout=45))
