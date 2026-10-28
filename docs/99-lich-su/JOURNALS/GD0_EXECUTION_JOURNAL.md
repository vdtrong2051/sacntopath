# GĐ0 — Nhật ký phát triển PRE-01 đến PRE-06

**Tính chất:** tổng hợp hồi cứu từ Git và tài liệu nghiệm thu GĐ0; không tái chạy camera, không thay đổi dữ liệu đo.

| Phiên | Mốc kỹ thuật | Kết quả được ghi nhận | Chưa được chứng minh |
|---|---|---|---|
| PRE-01 | Gemini 2, OrbbecSDK v2.10.6, C++20 và pybind11; máy Windows đã có smoke test | Theo hồ sơ đầu nối camera và test native | Chất lượng kích thước/độ đồng bộ đo lường |
| PRE-02 | Hợp đồng RAW v2 | Color MJPEG và Depth Y16 **hai lưới độc lập**, intrinsics, distortion, D2C, timestamp/scale | Không auto-align, không suy ra camera pose |
| PRE-03 | Lưu trữ RAW | Lưu byte không đổi, manifest SHA-256, `COMMITTED`, v1/v2 đọc được | Rename không chứng nhận độ bền khi mất điện; RAW và SQLite không có giao dịch nguyên tử chung |
| PRE-04 | Gemini 2 thu nhận thực | Người vận hành xác nhận một shot và khả năng lưu/đọc RAW | Không biến `measured` thành `metric_validated` |
| PRE-05 | SQLite metadata | Project → Specimen → Session → Capture → ProcessingRun; lịch sử/audit | `ProcessingRun` là bản ghi trạng thái, không tự thực hiện xử lý hình học |
| PRE-06 | Nghiệm thu GĐ0 | Theo hồ sơ Windows: Python 80 PASS, 1 SKIP; CTest 2/2; native self-test mã 0; thu/đọc RAW thật | Quyền symlink Windows chưa kiểm tra; không chứng minh pose hoặc hiệu chuẩn |
| Đóng mốc GĐ0 | PR #3 merge `main` | Commit merge `8bf33591389dcdff82f0fbd5bf5932a22547c984` đã được đối chiếu trên GitHub | Merge code không thay thế kết quả kiểm thử trên từng phần cứng |

## Điểm có thể truy xuất lại

- [PRE-02 — hợp đồng RAW](../ARCHIVE/GD0/PRE/PRE_02_RAW_RGBD_CONTRACT.md), [PRE-03 — lưu RAW](https://github.com/vdtrong2051/sacntopath/blob/08ef856a04d61f20db1e26b2ceeb399065db902f/docs/archive/GD0/PRE/PRE_03_RAW_STORAGE.md), [PRE-04 — thu nhận Gemini 2](https://github.com/vdtrong2051/sacntopath/blob/08ef856a04d61f20db1e26b2ceeb399065db902f/docs/archive/GD0/PRE/PRE_04_GEMINI2_STORAGE_INTEGRATION.md).
- [PRE-05 — metadata](https://github.com/vdtrong2051/sacntopath/blob/08ef856a04d61f20db1e26b2ceeb399065db902f/docs/archive/GD0/PRE/PRE_05_GD0_METADATA_PERSISTENCE.md), [PRE-06 — nghiệm thu](../ARCHIVE/GD0/PRE/PRE_06_GD0_ACCEPTANCE.md).
- [Bài học chung](../../04-phat-trien/TIEU_CHUAN_KY_THUAT.md): nếu không có số lần thử hoặc ngày riêng, đánh dấu **CHƯA ĐỦ LỊCH SỬ**, không tự bổ sung.

## Rủi ro chuyển sang GĐ1

- Luồng thu nhận Gemini 2 **không tự mở camera khi import**, không có bảo đảm world pose hay đồng bộ khung đo tuyệt đối.
- Tác động phá lỗi trong PRE-06 được thực hiện trên **bản sao**; R7-C không đụng thư mục RAW thực tế.
- Có thể tồn tại hồ sơ phần cứng của những phương án thiết kế khác theo thời điểm. Không dùng một tài liệu cũ để tự tuyên bố cơ cấu hiện hành mà chưa đối chiếu phần cứng.
