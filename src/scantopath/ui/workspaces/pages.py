"""Bốn trang UI 06.3. Chưa đọc SQLite, RAW, SDK hoặc tải dữ liệu 3D.

Chỉ hiển thị thông tin định hướng rõ ràng rằng các chức năng bên trong
chưa được tích hợp; KHÔNG sinh ra dữ liệu dự án/thiết bị/độ chính xác giả.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
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
            "Thông tin dự án, vật mẫu, phiên quét và bản thu đã có trong GĐ0. "
            "Giao diện quản lý và truy vấn SQLite sẽ được kết nối ở phiên 07."
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
            "Bảng tác vụ và thông báo lỗi sẽ được bổ sung ở các bước 06.4–06.5. "
            "Lịch sử các lần xử lý trong SQLite sẽ được trình bày ở phiên 07."
        ),
        planned_session="Bước 06.4–06.5 / Phiên 07",
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

    outer = QVBoxLayout(page)
    outer.setContentsMargins(42, 40, 42, 36)
    outer.setSpacing(18)

    heading = QLabel(info.title)
    heading.setObjectName("workspaceHeading")
    heading.setWordWrap(True)
    heading.setTextInteractionFlags(Qt.TextSelectableByMouse)
    outer.addWidget(heading)

    description = QLabel(info.subtitle)
    description.setObjectName("workspaceSubtitle")
    description.setWordWrap(True)
    outer.addWidget(description)

    state_row = QHBoxLayout()
    state_row.setSpacing(12)
    state = QLabel("CHƯA TRIỂN KHAI")
    state.setObjectName("workspaceState")
    state.setAccessibleName("Trạng thái: Chưa triển khai")
    state_row.addWidget(state, alignment=Qt.AlignLeft)
    planned = QLabel(f"Dự kiến: {info.planned_session}")
    planned.setObjectName("workspacePlanned")
    planned.setWordWrap(True)
    state_row.addWidget(planned, stretch=1)
    outer.addLayout(state_row)

    panel = QFrame()
    panel.setObjectName("workspacePanel")
    panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    panel_layout = QVBoxLayout(panel)
    panel_layout.setContentsMargins(26, 26, 26, 28)
    panel_layout.setSpacing(12)

    label = QLabel("KHÔNG GIAN LÀM VIỆC")
    label.setObjectName("workspaceKicker")
    panel_layout.addWidget(label)

    feature_title = QLabel(info.next_title)
    feature_title.setObjectName("workspaceFeatureTitle")
    feature_title.setWordWrap(True)
    panel_layout.addWidget(feature_title)

    details = QLabel(info.next_description)
    details.setObjectName("workspaceDescription")
    details.setWordWrap(True)
    details.setTextInteractionFlags(Qt.TextSelectableByMouse)
    panel_layout.addWidget(details)

    note = QLabel("Chưa tải dữ liệu • Chưa chạy phép đo • Chưa khởi động thiết bị")
    note.setObjectName("workspaceFootnote")
    note.setWordWrap(True)
    panel_layout.addSpacing(8)
    panel_layout.addWidget(note)

    outer.addWidget(panel)
    outer.addStretch(1)
    return page
