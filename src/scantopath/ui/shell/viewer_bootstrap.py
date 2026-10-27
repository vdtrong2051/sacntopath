"""Khởi tạo Viewer theo nhu cầu, không chạy VTK native trong tiến trình Qt.

Khi Qt offscreen/minimal, sử dụng bộ xem trước PNG tương thích; trên giao diện
Windows thật, dùng Render Host cô lập với bộ điều khiển tương tác R5.3.
"""
from __future__ import annotations


def create_viewer_controller(parent):
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.platformName().lower() in ('offscreen', 'minimal'):
        from scantopath.modules.viewer3d.presentation.controller import Viewer3DController
        return Viewer3DController(parent)
    # Bộ điều khiển R5.3 kế thừa lớp live R5.2; tên alias giữ hợp đồng khởi tạo
    # mà bài kiểm thử tương thích R5.2 vẫn yêu cầu, không đổi loại đối tượng thật.
    from scantopath.modules.viewer3d.presentation.interactive_controller import (
        InteractiveViewer3DController as LiveViewer3DController,
    )
    from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import CoalescingRenderSession
    from .viewer_inspector_bridge import SceneInspectorBridge
    controller = LiveViewer3DController(
        parent, session_factory=lambda: CoalescingRenderSession(640, 480, timeout=45))
    controller._inspector_bridge = SceneInspectorBridge(parent.property_inspector, controller)
    return controller
