# GĐ0 — Nhật ký hồi cứu PRE-01 đến PRE-06

**Nguồn:** [PRE-06 Acceptance](../../archive/GD0/PRE/PRE_06_GD0_ACCEPTANCE.md), [PRE-04 Gemini2](../../archive/GD0/PRE/PRE_04_GEMINI2_STORAGE_INTEGRATION.md), Git merge PR #3. Đây là **hồi cứu**, không diễn lại test phần cứng ở R7.

| Nhóm | Thực hiện/quan sát | Giới hạn |
|---|---|---|
| PRE-01, baseline | Thiết lập Python 3.12 + C++20 + Gemini 2/SDK | Tài liệu là mốc điều kiện chạy, không xác nhận mọi kết hợp thiết bị |
| PRE-02 RAW contract | MJPEG màu, Y16 sâu, intrinsics, scale, timestamps, camera pose unknown | Chưa RGB↔depth alignment hay metric validation |
| PRE-03 RAW storage | SHA-256, marker COMMITTED, giữ bytes v1/v2 | Không bảo đảm atomic transaction xuyên filesystem+SQLite |
| PRE-04 Gemini 2 | Một shot thiết bị thật, ghi/đọc RAW độc lập | Không suy ra pose, world frame hoặc error tolerance |
| PRE-05 metadata | Project/Specimen/Session/Capture/ProcessingRun audit SQLite | Run status metadata không chứng minh thuật toán 3D đã chạy |
| PRE-06 nghiệm thu | 80 Python PASS/1 symlink SKIP, CTest 2/2, native self-test 0 (theo hồ sơ) | HMI/physical evidence ở operator log |
| Merge `main` | PR #3; commit `8bf33591389dcdff82f0fbd5bf5932a22547c984` | Git evidence tách với kết quả thử thiết bị |

**Root-cause attempts:** `HISTORY_INCOMPLETE`: hồ sơ không đủ cho số lần patch/attempt của tất cả PRE; không tự đặt số đếm.

**Risk carry-over:** Symlink privilege ở Windows, không khẳng định pose/world geometry, không tự khởi động camera. Thực nghiệm phá lỗi RAW trong PRE-06 chỉ trên **bản sao**, không tái thực thi trên kho của người dùng ở R7.
