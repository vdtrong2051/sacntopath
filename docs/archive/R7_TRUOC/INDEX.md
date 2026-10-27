# ScanToPath — Cổng tài liệu kỹ thuật hiện hành (R7)

**Nhánh kiểm kê:** `feat/gd1-desktop-ui` · **mốc kiểm kê:** `ff45ccf87ce770e25eedf6e12df6bb5aaa958734` (R5.3) · **tình trạng:** R7 tài liệu đã soạn; chỉ có hiệu lực sau apply, verify và commit. Ngày lập: 27/10/2026.

Đây là **điểm vào chuẩn** để hiểu hệ thống ở mốc R5/R6. Những tài liệu được tạo từ phiên 06–08 và R1–R5 vẫn là hồ sơ lịch sử, không bị xóa/viết lại. Trạng thái dự kiến của roadmap không đồng nghĩa đã triển khai.

| Nhu cầu | Tài liệu chuẩn | Nguồn bằng chứng/tham chiếu |
|---|---|---|
| Kiến trúc thực tế | [Kiến trúc GĐ1](architecture/CURRENT_GD1_ARCHITECTURE.md) | [Kiến trúc mục tiêu GĐ0](../GD0/ARCHITECTURE.md) |
| Mô-đun Project/SQLite/RAW | [Project Workspace](modules/PROJECT_WORKSPACE.md) | [ADR-002](../../decisions/ADR_002_NUMBERED_STORAGE_LAYOUT.md) |
| Mô-đun Viewer/VTK | [Viewer 3D](modules/VIEWER3D.md) | [R4.5 handover](../GD1/R1-R5/R4_05_R5_HANDOVER_GATES.md) |
| Quy ước code và docstring | [Chuẩn bảo trì](development/ENGINEERING_STANDARDS.md) | [Lộ trình](../../ROADMAP.md) |
| Chuẩn ghi chú và bằng chứng | [Documentation & evidence](development/R7_DOCUMENTATION_POLICY.md) | [Đối chiếu phiên](../../roadmap/SESSION_CROSSWALK.md) |
| Quyết định thiết kế | [Chỉ mục ADR](../../decisions/DECISION_INDEX.md) | [ADR-001](../../decisions/ADR_001_UI_FIRST.md) |
| Nghiệm thu R6 | [Ma trận R6](../../acceptance/GD1_R6_ACCEPTANCE_STATUS.md) | [Hợp đồng R4–R5](../GD1/R1-R5/R4_05_R5_HANDOVER_GATES.md) |
| Nhật ký toàn dự án | [Master log](../../history/DEVELOPMENT_MASTER_LOG.md) | [GĐ0](../../history/GD0/GD0_EXECUTION_JOURNAL.md) · [GĐ1](../../history/GD1/GD1_EXECUTION_JOURNAL.md) |
| Sự cố và bài học | [Incident register](../../history/GD1/INCIDENT_REGISTER.md) | [GĐ1 Journal](../../history/GD1/GD1_EXECUTION_JOURNAL.md) |

**Quy tắc độ tin cậy:** `VERIFIED` = quan sát bằng Git/file/log/receipt; `OPERATOR_REPORTED` = người vận hành cung cấp log, chưa đọc trực tiếp artifact Windows; `PARTIAL_EVIDENCE` = có chứng cứ một phần; `NOT_TESTED` = chưa có bằng chứng kiểm thử; `HISTORY_INCOMPLETE` = không đủ để suy ra thứ tự/số lần sửa.

**Mốc hiện hành:** R6 tự động **14/14 PASS theo log operator**, trong đó Python 618 PASS, 3 Windows symlink SKIP, CTest 2/2. R6 tổng thể **PENDING** vì HMI 100/125/150%, thử native thật sự bận, GPU/VRAM và display-present còn thiếu/chưa kết luận. R7 không thay đổi trạng thái này. Sau R7 thực hiện R8; chỉ **08.06.6** mới xét GĐ1 Final Freeze.
