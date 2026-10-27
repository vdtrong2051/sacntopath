# Nghiệm thu GĐ0 — Phạm vi nền tảng

GĐ0 cung cấp RAW RGB-D của Orbbec Gemini 2, lưu/đọc v2, SQLite Project/Specimen/ScanSession/Capture/ProcessingRun. Hồ sơ PRE-06 mô tả các kiểm thử offline, native, một lần chụp thật, đọc lại SHA-256 và các trường hợp từ chối dữ liệu hỏng.

Bằng chứng lịch sử: PR #3 merge vào `main`; PRE-06 Windows có các bước pytest (mốc 80 pass, 1 skip), CTest 2/2 và native self-test. **Một lần đọc cảm biến thật không chứng minh đồng bộ exposure, pose, chuẩn đo mét, hiệu chuẩn sai số hay tự động điều khiển cơ cấu**.

- Nguồn chi tiết: [PRE-06 lịch sử](../archive/GD0/PRE/PRE_06_GD0_ACCEPTANCE.md).
- Metadata: [Quản lý dự án](../modules/QUAN_LY_DU_AN.md).
- RAW: [Lưu trữ](../modules/LUU_TRU_RAW.md).

Không thay đổi hoặc chạy lại capture vật lý trong R7-B.
