# Nhật ký phát triển ScanToPath — Hướng dẫn tra cứu

**Phạm vi:** lịch sử triển khai phần mềm; khác với nhật ký quét, ghi nhận RAW hoặc `ProcessingRun` trong SQLite. Tài liệu hiện hành sử dụng tiếng Việt; định danh mã nguồn, mã sự cố, mã commit và tên trạng thái tự động được giữ nguyên.

| Khi cần biết | Tài liệu | Vai trò |
|---|---|---|
| Dự án phát triển qua các mốc nào? | [Nhật ký tổng](DEVELOPMENT_MASTER_LOG.md) | Mốc, thay đổi, commit và giới hạn chứng cứ |
| GĐ0 đã nghiệm thu những gì? | [Nhật ký GĐ0](GD0/GD0_EXECUTION_JOURNAL.md) | RAW, Gemini 2, SQLite và nghiệm thu PRE-01–06 |
| GĐ1 đã làm những gì, thử những lần nào? | [Nhật ký GĐ1](GD1/GD1_EXECUTION_JOURNAL.md) | Các phiên 06–08, R1–R7; giữ các lần FAIL |
| Sự cố nào đã xảy ra? | [Sổ sự cố GĐ1](GD1/INCIDENT_REGISTER.md) | Triệu chứng, nguyên nhân, cách sửa, kiểm thử, giới hạn |
| Viết bản ghi mới thế nào? | [Quy tắc ghi nhật ký](QUY_UOC_GHI_NHAT_KY.md) | Phân loại chứng cứ, cách dẫn nguồn, mẫu bản ghi |
| R7-C đã thay đổi chú thích nào? | [Bảng đối chiếu R7-C](../standardization/R7C_PHAM_VI_VA_DOI_CHIEU.md) | Phạm vi, mã nguồn, tiêu chí kiểm tra |

## Ranh giới và độ tin cậy

- **Mã commit và tệp theo phiên** xác nhận phần nào đã được đưa vào Git; không tự chứng minh thử nghiệm trên Windows hoặc camera.
- **Nhật ký PowerShell người vận hành** là bằng chứng do người vận hành báo cáo, không phải một phiên chạy mới của công cụ R7-C.
- **Tệp `_setup/.../evidence`** nằm ngoài repo. Không sao chép kết quả giả hoặc thêm tệp nhạy cảm vào Git.
- Không chuyển một bài kiểm thử tự động PASS thành nghiệm thu HMI/nội suy đo lường; [R6 tổng thể còn mở](../acceptance/GD1.md).
- Những bước mà không có ngày, số lần thử hay bản sửa xác định được dùng **CHƯA ĐỦ LỊCH SỬ**, thay vì ước đoán.
