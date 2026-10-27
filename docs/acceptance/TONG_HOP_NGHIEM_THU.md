# Tổng hợp trạng thái nghiệm thu ScanToPath

| Giai đoạn | Bằng chứng có | Quyết định hiện hành |
|---|---|---|
| GĐ0 | PRE-06, Gemini 2 có một lần thu nhận thật; RAW v2/SQLite; PR #3 merge | Có bằng chứng GĐ0 trong hồ sơ; không có chứng chỉ độ chính xác metric |
| GĐ1 R1–R5 | Giao diện và Viewer R5.3 đã tích hợp, phát hành trên nhánh | Chỉ các chức năng ở phạm vi đó được xem là đã triển khai |
| R6 tự động | 14/14 cổng PASS, 618 Python PASS / 3 SKIP, CTest 2/2 | **AUTOMATED_PASS** theo log operator |
| R6 tổng thể | Thiếu bảng HMI hoàn chỉnh, DPI matrix, native C++ busy/crash, FPS thực và VRAM | **PENDING**; không biến thành PASS |
| R7-B | Chuyển cấu trúc tài liệu | Chỉ chốt sau verify và người vận hành duyệt |
| R8 và 08.06.6 | Chưa thực hiện ở mốc kiểm kê R7-A | **NOT_STARTED**, chưa đóng băng GĐ1 |

Chi tiết: [GĐ0](GD0.md) · [GĐ1](GD1.md) · [Bảng R6 gốc](GD1_R6_ACCEPTANCE_STATUS.md). Tất cả bằng chứng hệ thống gốc trên Windows nằm ngoài repo tại `_setup/.../evidence`.
