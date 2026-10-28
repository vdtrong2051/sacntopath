# ScanToPath — Kho lịch sử tài liệu (DOC-05)

> `owner: HISTORY_CUSTODIAN` · `as_of_commit: 8bf5e1e1603a0acf735ffc55f0b3d11ef9d96286` · `verified_at: 2026-10-28`  
> `scope: bản sao lịch sử và đường dẫn kiểm chứng` · `source-of-truth: docs/standardization/DOC05_MIGRATION_PLAN.json` · `evidence_level: GIT_SOURCE_REVIEWED / WINDOWS_FULL_PENDING`

## 1. Đọc tài liệu ở đâu?

Nhóm **đang thay đổi** có một nguồn chuẩn: [trạng thái](../05-quan-ly/TRANG_THAI_DU_AN.md), [task](../05-quan-ly/TASK_REGISTER.md), [quyết định áp dụng hiện hành](../05-quan-ly/QUYET_DINH_KY_THUAT.md), [nghiệm thu GĐ1](../07-nghiem-thu/GD1_ACCEPTANCE.md). Kho này giữ **ảnh chụp lịch sử**, không được thay status dự án hiện tại. Không sử dụng hồ sơ 08.06.5 để tự xác nhận HMI 08.06.6.

DOC-05 đã lưu bản sao có truy vết; DOC-06 loại bỏ bản cũ trùng lặp sau khi chuyển liên kết và gate. Mỗi hồ sơ được đối chiếu Git blob nguồn và chỉ chỉnh đường dẫn Markdown tương đối ở bản xem trong thư mục mới; tệp gốc giữ nguyên byte để truy xuất. Vì các gate R7/R8 và permalink còn gọi đường cũ, các alias cũ đã được hợp nhất vào tuyến v2. Một phần liên kết nguồn lịch sử vốn đã cũ hoặc hỏng; nên dùng bản gốc của hồ sơ để đối chiếu nội dung nếu liên kết không còn hiệu lực. Đó không phải phép xác nhận dữ liệu đo.

## 2. ADR và quyết định lịch sử

- [ADR-001 — UI-first](ADR/ADR_001_UI_FIRST.md).
- [ADR-002 — Numbered Storage](ADR/ADR_002_NUMBERED_STORAGE_LAYOUT.md).
- [Trạng thái áp dụng hiện hành](../05-quan-ly/QUYET_DINH_KY_THUAT.md). ADR có mốc thời gian, không chỉnh hồi tố thành đã đạt.

## 3. Nhật ký và hồ sơ gốc

- [DOC-039 — DEVELOPMENT_MASTER_LOG](JOURNALS/DEVELOPMENT_MASTER_LOG.md).
- [DOC-040 — GD0_EXECUTION_JOURNAL](JOURNALS/GD0_EXECUTION_JOURNAL.md).
- [DOC-041 — GD1_EXECUTION_JOURNAL](JOURNALS/GD1_EXECUTION_JOURNAL.md).
- [Biên bản sự cố R6 gốc](JOURNALS/GD1_INCIDENT_REGISTER.md).
- [DOC-043 — HO_SO_CU_VA_TRUY_VET](HO_SO_CU_VA_TRUY_VET.md).

- [Biên bản R6 gốc (không phải nghiệm thu tổng thể)](ACCEPTANCE/GD1_R6_ACCEPTANCE_STATUS_ORIGINAL.md).

## 4. Archive PRE/GĐ1 — 12 hồ sơ

- [DOC-014 — PRE_02_RAW_RGBD_CONTRACT](ARCHIVE/GD0/PRE/PRE_02_RAW_RGBD_CONTRACT.md).
- [DOC-015 — PRE_06_GD0_ACCEPTANCE](ARCHIVE/GD0/PRE/PRE_06_GD0_ACCEPTANCE.md).
- [DOC-016 — 07_01_STORAGE_LAYOUT_V2_CONTRACT](ARCHIVE/GD1/07/07_01_STORAGE_LAYOUT_V2_CONTRACT.md).
- [DOC-017 — 07_12_CONSOLIDATION_RISK_REGISTER](ARCHIVE/GD1/07/07_12_CONSOLIDATION_RISK_REGISTER.md).
- [DOC-018 — 08_06_4_WINDOWS_HMI_ACCEPTANCE](ARCHIVE/GD1/08/08_06_4_WINDOWS_HMI_ACCEPTANCE.md).
- [DOC-019 — 08_06_5_DEFECT_DISPOSITION_AND_HMI_WAIVER](ARCHIVE/GD1/08/08_06_5_DEFECT_DISPOSITION_AND_HMI_WAIVER.md).
- [DOC-020 — R4_03_FRAME_TRANSPORT_AND_LIFECYCLE](ARCHIVE/GD1/R1-R5/R4_03_FRAME_TRANSPORT_AND_LIFECYCLE.md).
- [DOC-021 — R4_05_R5_HANDOVER_GATES](ARCHIVE/GD1/R1-R5/R4_05_R5_HANDOVER_GATES.md).
- [DOC-022 — R4_05_RENDERER_ARCHITECTURE_DECISION](ARCHIVE/GD1/R1-R5/R4_05_RENDERER_ARCHITECTURE_DECISION.md).
- [DOC-023 — R5_01_SCENE_GEOMETRY_CONTRACTS](ARCHIVE/GD1/R1-R5/R5_01_SCENE_GEOMETRY_CONTRACTS.md).
- [DOC-024 — R5_03_INTERACTION_INSPECTOR_UX](ARCHIVE/GD1/R1-R5/R5_03_INTERACTION_INSPECTOR_UX.md).
- [DOC-026 — ROADMAP_V1_ARCHIVED](ARCHIVE/ROADMAP_CU/ROADMAP_V1_ARCHIVED.md).

## 5. R7/R8 và nguồn chuẩn hóa

- [Chỉ mục hồ sơ R7/R8](STANDARDIZATION/README.md).
- [Kế hoạch 28 bản sao kèm Git blob](../standardization/DOC05_MIGRATION_PLAN.json) · [Hồ sơ DOC-05](../standardization/DOC05_TRUY_VET_VA_BAN_GIAO.md).
- [DOC-02](../standardization/DOC02_KIEN_TRUC_TAI_LIEU.md) là bản đặc tả tại ngày chốt, không phải kết quả thực thi.

## 6. Giới hạn đã biết

Bản sao lịch sử không thay thế evidence từ máy Windows, không khẳng định SHA file RAW, hiệu chuẩn metric, cấu hình phần cứng đang dùng, GPU/VRAM hoặc FPS thực. Kiểm thử Full và việc đọc/đối chiếu bản sao do người vận hành thực hiện; `GD1_OVERALL_PENDING` vẫn còn đến khi 08.06.6 được quyết định hợp lệ. Các alias không xóa trong DOC-05 vì thiếu bằng chứng an toàn của liên kết ngoài repository.
