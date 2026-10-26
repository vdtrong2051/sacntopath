"""Immutable, Qt-free Project DTO to Explorer/Inspector projection.

No database I/O, code assignment, implicit RAW verification or fake geometry.
"""
from __future__ import annotations

from dataclasses import dataclass

from scantopath.application.contracts import SelectionRef
from scantopath.modules.project_workspace.application.models import AuditEventSummary, ProjectTree, StoreInfo


@dataclass(frozen=True, slots=True)
class ProjectLoadBundle:
    info: StoreInfo
    trees: tuple[ProjectTree, ...]
    audit_events: tuple[AuditEventSummary, ...] = ()


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


def _storage_fields(storage) -> tuple[tuple[str, str], ...]:
    # A numbered logical path must NOT be represented as existing filesystem data.
    return (("Đường dẫn", storage.relative_path or "Chưa có"),
            ("Lưu trữ", _state(storage.state)))


def project_rows(trees: tuple[ProjectTree, ...]) -> tuple[ProjectRow, ...]:
    """Preserve SQLite hierarchy, truthful metadata and immutable entity identity."""
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
                            ("Kiểu bản thu", cap.kind),
                            ("RAW", _state(cap.storage.state)),
                            ("RAW schema", str(cap.schema_version)),
                            ("Phiên quét ID", cap.session_id),
                            ("Đăng ký lúc", cap.registered_at)) + _storage_fields(cap.storage),
                ) for index, cap in enumerate(session.captures, start=1))
                runs = tuple(ProjectRow(
                    title=f"{_code(run.storage.public_code)} · Xử lý {run.stage}",
                    selection=SelectionRef("processing_run", run.run_id),
                    fields=(("Mã", _code(run.storage.public_code)),
                            ("Công đoạn", run.stage),
                            ("Thuật toán", run.algorithm),
                            ("Phiên bản", run.version),
                            ("Trạng thái", run.state),
                            ("Phiên quét ID", run.session_id),
                            ("Đầu vào", ", ".join(run.input_capture_ids) or "Chưa có"),
                            ("Đầu ra (tham chiếu)", ", ".join(run.output_files) or "Chưa có"),
                            ("Tham số JSON", run.parameters_json),
                            ("Lỗi", run.error_message or "Không có"),
                            ("Tạo lúc", run.created_at),
                            ("Bắt đầu", run.started_at or "Chưa có"),
                            ("Kết thúc", run.finished_at or "Chưa có")) + _storage_fields(run.storage),
                ) for run in session.processing_runs)
                sessions.append(ProjectRow(
                    title=f"{_code(session.storage.public_code)} · {session.label}",
                    selection=SelectionRef("scan_session", session.session_id),
                    fields=(("Mã", _code(session.storage.public_code)),
                            ("Tên phiên quét", session.label),
                            ("Trạng thái", "Đang mở" if session.state == "open" else "Đã đóng"),
                            ("Vật mẫu ID", session.specimen_id),
                            ("Tạo lúc", session.created_at),
                            ("Đóng lúc", session.closed_at or "Chưa đóng")) + _storage_fields(session.storage),
                    children=captures + runs,
                ))
            specimens.append(ProjectRow(
                title=f"{_code(specimen.storage.public_code)} · {specimen.label}",
                selection=SelectionRef("specimen", specimen.specimen_id),
                fields=(("Mã", _code(specimen.storage.public_code)),
                        ("Tên vật mẫu", specimen.label),
                        ("Mô tả", specimen.description or "Không có"),
                        ("Dự án ID", specimen.project_id),
                        ("Tạo lúc", specimen.created_at),
                        ("Cập nhật", specimen.updated_at)) + _storage_fields(specimen.storage),
                children=tuple(sessions),
            ))
        projects.append(ProjectRow(
            title=f"{_code(p.storage.public_code)} · {p.name}",
            selection=SelectionRef("project", p.project_id),
            fields=(("Mã", _code(p.storage.public_code)),
                    ("Tên dự án", p.name),
                    ("Mô tả", p.description or "Không có"),
                    ("Tạo lúc", p.created_at),
                    ("Cập nhật", p.updated_at)) + _storage_fields(p.storage),
            children=tuple(specimens),
        ))
    return tuple(projects)
