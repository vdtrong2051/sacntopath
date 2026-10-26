"""Bốn trang UI 06.3. Chưa đọc SQLite, RAW, SDK hoặc tải dữ liệu 3D.

Chỉ hiển thị thông tin định hướng rõ ràng rằng các chức năng bên trong
chưa được tích hợp; KHÔNG sinh ra dữ liệu dự án/thiết bị/độ chính xác giả.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from scantopath.application.contracts import UiDataState, WorkspaceId


@dataclass(frozen=True, slots=True)
class WorkspacePresentation:
    title: str
    subtitle: str
    next_title: str
    next_description: str
    planned_session: str
    state: UiDataState = UiDataState.NOT_IMPLEMENTED


WORKSPACE_PRESENTATION: dict[WorkspaceId, WorkspacePresentation] = {
    WorkspaceId.PROJECTS: WorkspacePresentation(
        title="Dự án",
        subtitle="Tổ chức dự án, vật mẫu, phiên quét và dữ liệu đã thu nhận.",
        next_title="Quản lý dữ liệu dự án",
        next_description=(
            "Đã có thể mở kho SQLite từ Cây dự án, tạo/sửa metadata ở bảng Thuộc tính "
            "và xem lịch sử bản thu trong Nhật ký SQLite. Khu vực này là tổng quan; "
            "dữ liệu chi tiết nằm trong các panel."
        ),
        planned_session="Phiên 07",
    ),
    WorkspaceId.CAPTURE: WorkspacePresentation(
        title="Thu nhận và phát lại",
        subtitle="Xem dữ liệu ảnh màu và độ sâu theo từng lần thu nhận.",
        next_title="Làm việc với dữ liệu RGB-D",
        next_description=(
            "GĐ0 đã lưu được RAW Gemini 2. Chức năng xem lại ảnh màu và chiều sâu "
            "sẽ triển khai ở phiên 09. Mở giao diện này không mở camera."
        ),
        planned_session="Phiên 09",
    ),
    WorkspaceId.INSPECT3D: WorkspacePresentation(
        title="Kiểm tra 3D",
        subtitle="Quan sát và tương tác với dữ liệu đám mây điểm.",
        next_title="Trình xem 3D",
        next_description=(
            "Trình xem VTK, nhập tệp PLY và điều khiển góc nhìn sẽ có ở phiên 08. "
            "Hiện tại chưa hiển thị mô hình hoặc tọa độ đo."
        ),
        planned_session="Phiên 08",
    ),
    WorkspaceId.PROCESSING: WorkspacePresentation(
        title="Xử lý và kết quả",
        subtitle="Theo dõi tác vụ, lịch sử xử lý và kết quả phân tích.",
        next_title="Theo dõi tiến trình",
        next_description=(
            "Xem ProcessingRun trong Cây dự án và xem sự kiện đã lưu tại tab Nhật ký SQLite "
            "trong Tác vụ và thông báo. Thuật toán xử lý 3D chưa chạy trong workspace này."
        ),
        planned_session="Phiên 07",
    ),
}


def create_workspace_page(workspace: WorkspaceId) -> QWidget:
    """Tạo trang placeholder rõ nhãn, không tạo phiên làm việc giả."""
    key = WorkspaceId(workspace)
    info = WORKSPACE_PRESENTATION[key]
    if info.state is not UiDataState.NOT_IMPLEMENTED:
        raise ValueError("06.3 may only create not-implemented placeholder pages")

    page = QWidget()
    page.setObjectName(f"workspace_{key.value}")
    page.setAccessibleName(info.title)

    # Native Qt ScrollArea scales correctly at 125/150% display settings.
    frame = QVBoxLayout(page)
    frame.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea(page)
    scroll.setObjectName(f"workspaceScroll_{key.value}")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    content = QWidget()
    content.setObjectName("workspaceScrollContent")
    outer = QVBoxLayout(content)
    outer.setContentsMargins(24, 10, 24, 16)
    outer.setSpacing(6)
    frame.addWidget(scroll)
    scroll.setWidget(content)

    eyebrow = QLabel("KHÔNG GIAN LÀM VIỆC")
    eyebrow.setObjectName("workspaceEyebrow")
    eyebrow.setVisible(False)
    outer.addWidget(eyebrow)
    # R3.2.1: compact header; preserve widget positions for R3.1/R3.2 presenters.

    heading = QLabel(info.title)
    heading.setObjectName("workspaceHeading")
    heading.setWordWrap(True)
    heading.setTextInteractionFlags(Qt.TextSelectableByMouse)
    outer.addWidget(heading)

    description = QLabel(info.subtitle)
    description.setObjectName("workspaceSubtitle")
    description.setWordWrap(True)
    outer.addWidget(description)
    outer.addSpacing(4)

    panel = QFrame(content)
    panel.setObjectName("workspacePanel")
    panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    body = QVBoxLayout(panel)
    body.setContentsMargins(25, 24, 25, 25)
    body.setSpacing(12)

    state_row = QHBoxLayout()
    state_row.setSpacing(10)
    state = QLabel("CÓ THỂ SỬ DỤNG QUA PANEL" if key in (WorkspaceId.PROJECTS, WorkspaceId.PROCESSING)
                   else "CHƯA TRIỂN KHAI")
    state.setObjectName("workspaceState")
    state.setWordWrap(True)
    state.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    state.setAccessibleName("Trạng thái: " + state.text())
    state_row.addWidget(state, alignment=Qt.AlignLeft)
    planned = QLabel("Đã kết nối ở phiên 07" if key in (WorkspaceId.PROJECTS, WorkspaceId.PROCESSING)
                     else f"Dự kiến: {info.planned_session}")
    planned.setObjectName("workspacePlanned")
    planned.setWordWrap(True)
    planned.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
    state_row.addWidget(planned, alignment=Qt.AlignVCenter)
    state_row.addStretch(1)
    body.addLayout(state_row)
    body.addSpacing(7)

    feature_title = QLabel(info.next_title)
    feature_title.setObjectName("workspaceFeatureTitle")
    feature_title.setWordWrap(True)
    body.addWidget(feature_title)

    details = QLabel(info.next_description)
    details.setObjectName("workspaceDescription")
    details.setWordWrap(True)
    details.setTextInteractionFlags(Qt.TextSelectableByMouse)
    body.addWidget(details)

    actions = QHBoxLayout()
    actions.setSpacing(12)
    if key in (WorkspaceId.PROJECTS, WorkspaceId.PROCESSING):
        primary = QPushButton("Mở kho dữ liệu" if key is WorkspaceId.PROJECTS
                              else "Xem nhật ký SQLite")
        primary.setObjectName("workspacePrimaryAction")
        primary.setMinimumHeight(37)
        primary.setCursor(Qt.PointingHandCursor)
        actions.addWidget(primary, alignment=Qt.AlignLeft)
    else:
        message = QLabel("Tính năng này sẽ được tích hợp theo lộ trình.")
        message.setObjectName("workspaceActionHint")
        message.setWordWrap(True)
        actions.addWidget(message, alignment=Qt.AlignLeft)
    actions.addStretch(1)
    body.addLayout(actions)

    note = QLabel("Mở kho theo yêu cầu · Chưa chạy phép đo · Không khởi động thiết bị"
                  if key in (WorkspaceId.PROJECTS, WorkspaceId.PROCESSING)
                  else "Chưa tải dữ liệu · Chưa chạy phép đo · Chưa khởi động thiết bị")
    note.setObjectName("workspaceFootnote")
    note.setWordWrap(True)
    body.addWidget(note)

    # Cap the welcome content: it is a focused empty state, not the actual
    # storage/capture/processing workspace. All data remains in real docks.
    outer.addWidget(panel)
    outer.addStretch(1)
    return page
