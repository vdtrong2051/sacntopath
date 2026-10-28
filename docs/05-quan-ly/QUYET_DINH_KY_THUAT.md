# Quyết định kỹ thuật — Chỉ mục áp dụng hiện hành, không sửa ADR gốc

> `owner: PROJECT_COORDINATOR` · `as_of_commit: 81da5d2050324b1dc4a65ffbca9a38ed1ebba10a` · `verified_at: 2026-10-28`  
> `scope: hiệu lực hiện tại của các ADR và quyết định GĐ1` · `source-of-truth: ADR gốc bất biến + source Git để xét mức áp dụng` · `evidence_level: SOURCE_REVIEWED / MANUAL_APPROVAL_NOT_INFERRED`

## 1. Quy ước status và bảo toàn lịch sử

`ACTIVE`: quyết định đang định hướng source hiện tại; `PARTIALLY_APPLIED`: có phần đã triển khai nhưng thiếu cổng; `SUPERSEDED`: có ADR mới thay thế được ghi tên/SHA; `PENDING_VERIFICATION`: chưa đủ bằng chứng đánh giá tính áp dụng hoặc tính vật lý. Đây là **trạng thái áp dụng hiện nay**, không chỉnh phát biểu lịch sử tại ngày ký. Trang `docs/decisions/` và archive **giữ nguyên** đến DOC-05; khi đổi quyết định phải có ADR mới và index ghi rõ ref.

## 2. Decision index

| adr_id / decision | original_path (nguồn bất biến) | current_applicability | evidence / trade-off / còn mở | superseding_adr | reviewed_at |
|---|---|---|---|---|---|
| `ADR-001` UI-first vertical slices | [ADR-001](../99-lich-su/ADR/ADR_001_UI_FIRST.md) | `ACTIVE` — Qt shell + feature modules hiện có | Cấu trúc [`ui/`, `modules/`](../02-kien-truc/KIEN_TRUC_HE_THONG.md), R5.3; status nguyên thủy có điều kiện merge, **không sửa** | none | 2026-10-28 |
| `ADR-002` numbered storage v2 | [ADR-002](../99-lich-su/ADR/ADR_002_NUMBERED_STORAGE_LAYOUT.md) | `PARTIALLY_APPLIED` — code registry v2/migration opt-in có trong Git; bảo đảm end-to-end vẫn theo gate | [`numbered.py`](../../src/scantopath/storage/numbered.py), [`legacy_migration.py`](../../src/scantopath/storage/legacy_migration.py), [RAW](../03-modules/RAW_STORAGE.md). ADR ngày 19/10 còn ghi `implementation pending`, không là trạng thái code ngày 28/10 | none | 2026-10-28 |
| `DEC-R4.5` cô lập VTK Render Host | [R4.5 decision](../99-lich-su/ARCHIVE/GD1/R1-R5/R4_05_RENDERER_ARCHITECTURE_DECISION.md) | `ACTIVE_WITH_CONDITIONS` (diễn giải = `PARTIALLY_APPLIED` tới khi manual gates xong) | IPC/shared-memory/ACK đã có; không chứng nhận native C++ fault/VRAM/physical present; [Viewer](../03-modules/VIEWER_3D.md) | none | 2026-10-28 |
| `DEC-R5.3` interaction/picking | [R5.3 source](../99-lich-su/ARCHIVE/GD1/R1-R5/R5_03_INTERACTION_INSPECTOR_UX.md) | `PARTIALLY_APPLIED` — code đã có; nghiệm thu manual đang mở | scene/frame revision, Inspector, operator-reported R6 automated | none | 2026-10-28 |
| `DEC-08.06.5` operator HMI waiver | [Waiver record](../99-lich-su/ARCHIVE/GD1/08/08_06_5_DEFECT_DISPOSITION_AND_HMI_WAIVER.md) | `PARTIALLY_APPLIED` — phạm vi **riêng phiên A/TC11/TC12** | TC11/12 không chạy; `NOT_RUN_WAIVED_BY_OPERATOR`, residual risk AR-03; **không miễn** toàn bộ R6/08.06.6 | none | 2026-10-28 |
| `DEC-HW-CURRENT` rig/camera vật lý hiện hành | [DOC-02 open issue](../standardization/DOC02_QUYET_DINH_20.csv) | `PENDING_VERIFICATION` | `DOC01-07` = `OPEN_REQUIRED_SOURCE_DECISION`; lịch sử handheld khác thiết kế cơ cấu mới, cần ADR/ảnh/sơ đồ/owner/phê duyệt | none | 2026-10-28 |

`ACTIVE_WITH_CONDITIONS` ở dòng R4.5 chỉ là diễn giải con người cho `PARTIALLY_APPLIED`, **không phải giá trị thứ năm** của state ledger. Nếu cần máy đọc, sử dụng `PARTIALLY_APPLIED` như canonical.

## 3. Vì sao không sửa ADR-002 thành “implemented”?

ADR là biên bản tại **2026-10-19** khi 07.2/07.7 còn pending. Từ code `NumberedStorageRegistry`, CLI migration và regression thấy **cấu trúc đã được triển khai theo lát cắt** nhưng phép đo filesystem+SQLite, di trú dữ liệu người dùng và symlink Windows vẫn cần điều kiện riêng. Sửa nội dung ADR cũ sẽ làm giả trình tự quyết định. Chỉ mục này giải quyết mâu thuẫn DOC01-04 mà không thay chứng cứ gốc.

## 4. Quy trình ra quyết định mới

Đề xuất phải gồm `adr_id`, ngày, vấn đề, scope, phương án A/B, quyết định, tác động, mốc áp dụng, test/receipt, rollback và người ký; nếu có phá tương thích, nêu migration plan. Đối với cấu hình vật lý `DEC-HW-CURRENT`, bắt buộc phân biệt `CURRENT_PHYSICAL`, `TARGET_DESIGN`, `HISTORICAL_VARIANT`, nêu model/firmware, camera cố định hay cầm tay, các trục/tín hiệu có thật, ảnh/scan/diagram có ngày. Không thể xác nhận bằng từ ngữ trong roadmap hay note.

## 5. Giới hạn đã biết

Không có quyết định mới nào được ký trong DOC-04. Chỉ mục là đối chiếu tại commit, không làm thay đổi cổng HMI của 08.06.6; mọi waiver mới phải do owner phê duyệt có receipt, tuyệt đối không xem một test skip là ngoại lệ đã được duyệt.
