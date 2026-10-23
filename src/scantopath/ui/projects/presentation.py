"""07.4: immutable, Qt-free transformation from real Project DTOs to tree rows.

No database I/O, code assignment, implicit verification, or fake captures.
"""
from __future__ import annotations

from dataclasses import dataclass

from scantopath.application.contracts import SelectionRef
from scantopath.application.projects.models import ProjectTree, StoreInfo


@dataclass(frozen=True, slots=True)
class ProjectLoadBundle:
    info: StoreInfo
    trees: tuple[ProjectTree, ...]


@dataclass(frozen=True, slots=True)
class ProjectRow:
    title: str
    selection: SelectionRef
    fields: tuple[tuple[str, str], ...]
    children: tuple["ProjectRow", ...] = ()


def _code(code: str | None) -> str:
    return code if code is not None else "Chưa cấp mã"


def _state(raw: str) -> str:
    return {
        "legacy_unmapped": "RAW cũ · chưa cấp mã",
        "unmapped": "Chưa cấp mã",
        "not_materialized": "Chưa có thư mục vật lý",
        "not_checked": "Chưa kiểm tra RAW",
        "missing": "Thiếu tệp dữ liệu",
        "verified": "Đã kiểm tra tính toàn vẹn RAW",
    }.get(raw, "Chưa xác định")


def project_rows(trees: tuple[ProjectTree, ...]) -> tuple[ProjectRow, ...]:
    """Preserve database hierarchy, never turn missing codes into invented ones."""
    if not isinstance(trees, tuple) or any(not isinstance(t, ProjectTree) for t in trees):
        raise TypeError("Expected tuple[ProjectTree, ...]")
    projects = []
    for tree in trees:
        p = tree.project
        specimens = []
        for spec_node in tree.specimens:
            specimen = spec_node.specimen
            sessions = []
            for session in spec_node.sessions:
                captures = tuple(ProjectRow(
                    title=f"{_code(cap.storage.public_code)} · Bản thu {index:02d}",
                    selection=SelectionRef("capture", cap.capture_id),
                    fields=(("Mã", _code(cap.storage.public_code)),
                            ("Loại dữ liệu", "Từ cảm biến" if cap.data_state.value == "measured" else "Dữ liệu thử"),
                            ("RAW", _state(cap.storage.state)),
                            ("Đường dẫn", cap.storage.relative_path or "Chưa có")),
                ) for index, cap in enumerate(session.captures, start=1))
                sessions.append(ProjectRow(
                    title=f"{_code(session.storage.public_code)} · {session.label}",
                    selection=SelectionRef("scan_session", session.session_id),
                    fields=(("Mã", _code(session.storage.public_code)),
                            ("Tên phiên quét", session.label),
                            ("Trạng thái", "Đang mở" if session.state == "open" else "Đã đóng")),
                    children=captures,
                ))
            specimens.append(ProjectRow(
                title=f"{_code(specimen.storage.public_code)} · {specimen.label}",
                selection=SelectionRef("specimen", specimen.specimen_id),
                fields=(("Mã", _code(specimen.storage.public_code)), ("Tên vật mẫu", specimen.label)),
                children=tuple(sessions),
            ))
        projects.append(ProjectRow(
            title=f"{_code(p.storage.public_code)} · {p.name}",
            selection=SelectionRef("project", p.project_id),
            fields=(("Mã", _code(p.storage.public_code)), ("Tên dự án", p.name),
                    ("Mô tả", p.description or "Không có")),
            children=tuple(specimens),
        ))
    return tuple(projects)
