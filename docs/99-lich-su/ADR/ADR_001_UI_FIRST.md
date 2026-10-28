# ADR-001 — Dựng UI/workflow trước, tích hợp geometry theo lát cắt

- **Ngày:** 2026-10-18
- **Trạng thái:** Adopted khi PR tài liệu này được merge vào `main`; trước đó: pending review.
- **Phạm vi:** GĐ1 trở đi; không sửa GĐ0 hoặc sơ đồ phần cứng.
- **Nguồn:** `docs/ROADMAP.md`, `docs/roadmap/SESSION_CROSSWALK.md`, nghiên cứu `01_PHAM_VI_VA_BAN_DO_NGHIEN_CUU`.

## Vấn đề

Cách triển khai 3D Core hoàn chỉnh trước mới tích hợp UI khiến một nhóm nhỏ khó quan sát, debug, nghiệm thu tác vụ người dùng và quản lý tương tác với dữ liệu gốc. Ngược lại, dựng một giao diện khổng lồ toàn mock rồi mới làm core cũng tạo nợ kỹ thuật và dễ gây nhầm dữ liệu giả với phép đo thực.

## Quyết định

1. **UI-first tại từng phiên**, không phải «làm hết UI rồi mới code core». GĐ1 bắt đầu 06 UI foundation → 07 Projects → 08 VTK; GĐ2 09 Replay → 10 cloud → 11/12 tương tác/filter → 13 export.
2. **Modular monolith**: Qt Widgets + PySide6, UI/ViewModel/commands, Python Application Services, adapters cho SQLite/RAW/VTK/Camera/Geometry; C++20+pybind11 cho công việc nặng khi cần. Không dùng Electron/QML/microservices thứ hai chỉ vì có ví dụ tốt hơn về UI.
3. UI xem `ProcessingRun`/task status qua service; không query/commit SQLite trực tiếp trong widgets, không chạy frame capture hay cloud calculation trên Qt GUI thread.
4. **Một nguồn sự thật:** RAW/meta từ GĐ0 là immutable. Dữ liệu dẫn xuất và các kết quả đo phải giữ source IDs, units, frames, transformation validity và loại provenance.
5. **Mock rõ ràng:** trạng thái `not_implemented`, `fixture`, `measured`, `estimated`, `validated`, `insufficient_evidence`; UI không được gắn số đo thật khi không có confidence/calibration gate.
6. Tích hợp VTK sớm để kiểm tra memory/render/interaction; không kéo AI hoặc PCL vào critical path của 06–13. AI qua worker/sandbox riêng.

## Phương án đã cân nhắc

- **Core-first tuyệt đối:** dễ unit-test toán nhưng feedback UI muộn, khó kiểm soát product flow. Không chọn cho lịch trình hiện tại.
- **Full mock UI trước rồi tích hợp một lần:** demo nhanh nhưng chi phí viết lại adapter/service rất cao. Không chọn.
- **UI-first + vertical slices:** thấy giá trị sớm, có lỗi/gates rõ, quay lại sửa phạm vi nhỏ; được chọn.

## Hệ quả

- Trọng tâm nghiên cứu metric/trust/feature/replica giữ nguyên; thứ tự/nhãn các phiên thay đổi **có chủ đích**, được lưu crosswalk.
- Worker + error/cancel/progress có thể phải làm sớm hơn một số tính năng hình học; đây là **ngoại lệ ưu tiên độ khó sớm để tránh nợ kiến trúc**.
- Pose camera cầm tay vẫn unknown đến khi được ước lượng; UI quỹ đạo hướng dẫn không được thay thế actual pose.
- Tiêu chí Done gồm UI không block, test dữ liệu thật/fixture, traceability và hồi quy module cũ; không chỉ là ảnh chụp UI.

## Gate nghiệm thu ADR

PR tài liệu phải thay 3 tài liệu cấp cao `README.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`; lưu nguyên văn roadmap cũ theo SHA; tạo crosswalk; không sửa `src/`, `cpp/`, `tests/`, hoặc các hồ sơ PRE-01…06. Sau khi merge mới bắt đầu implementation session 06.
