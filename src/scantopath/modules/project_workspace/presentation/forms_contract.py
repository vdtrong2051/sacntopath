"""07.5 form commands: immutable Qt-free metadata input, no implicit I/O."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Action = Literal[
    "project.create", "project.update", "specimen.create", "specimen.update",
    "session.create", "session.update", "session.close",
    "project.delete", "specimen.delete", "session.delete",
]
_ACTIONS = frozenset({
    "project.create", "project.update", "specimen.create", "specimen.update",
    "session.create", "session.update", "session.close",
    "project.delete", "specimen.delete", "session.delete",
})


def validate_label(value: str) -> str:
    """Match MetadataStore._label without accepting silent truncation."""
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError("Tên cần có 1–256 ký tự.")
    return value.strip()


def validate_description(value: str) -> str:
    if not isinstance(value, str) or len(value) > 4096 or "\x00" in value:
        raise ValueError("Mô tả không hợp lệ (tối đa 4096 ký tự).")
    return value.strip()


def _id(value: str | None, field: str) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 128
            or not value.isascii() or not all(c.isalnum() or c in "_-" for c in value)):
        raise ValueError(f"Mã định danh {field} không hợp lệ.")
    return value


@dataclass(frozen=True, slots=True)
class ProjectEditCommand:
    action: Action
    name: str = ""
    description: str = ""
    target_id: str | None = None
    parent_id: str | None = None
    project_id: str | None = None

    def __post_init__(self) -> None:
        if self.action not in _ACTIONS:
            raise ValueError("Thao tác quản lý không được hỗ trợ.")
        entity = self.action.split(".")[0]
        operation = self.action.split(".")[1]
        if operation not in ("close", "delete"):
            object.__setattr__(self, "name", validate_label(self.name))
        elif self.name or self.description:
            raise ValueError("Thao tác đóng/xóa không nhận tên hoặc mô tả.")
        if entity == "session" and self.description:
            raise ValueError("Phiên quét không có trường mô tả.")
        object.__setattr__(self, "description", validate_description(self.description))
        if operation in ("update", "close", "delete"):
            _id(self.target_id, "đối tượng")
        elif self.target_id is not None:
            raise ValueError("Thao tác tạo mới không nhận ID định sẵn.")
        if entity != "project":
            _id(self.parent_id, "cha")
        elif self.parent_id is not None:
            raise ValueError("Project không có đối tượng cha.")
        if entity == "specimen" and operation == "update":
            _id(self.project_id, "dự án")
        elif self.project_id is not None:
            raise ValueError("Tham số dự án chỉ áp dụng khi sửa vật mẫu.")


@dataclass(frozen=True, slots=True)
class ProjectEditResult:
    action: str
    entity_type: str  # same SelectionRef type for GUI
    entity_id: str
    public_code: str | None
    numbering_pending: bool = False
