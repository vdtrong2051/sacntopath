# R7 — Quy tắc tài liệu, chứng cứ và lịch sử (R7.1–R7.4)

## Phân tầng tài liệu

1. `docs/INDEX.md` làm điểm vào. `docs/architecture`, `docs/modules`, `docs/development`, `docs/decisions`, `docs/acceptance` là lớp **tra cứu hiện hành**.
2. `docs/gd1/**`, `docs/PRE_*`, `docs/roadmap/ROADMAP_V1_ARCHIVED.md` là **hồ sơ tại thời điểm lập**, không viết lại quyết định/số đo lịch sử.
3. `docs/history/` chứa timeline, attempts, incidents và mức độ chứng cứ. Raw console, image, telemetry đặt ngoài repo `_setup/.../evidence`; chỉ commit tóm tắt và đường dẫn tương đối/quy ước vị trí.

## Nhãn trạng thái bắt buộc

| Nhãn | Tiêu chuẩn |
|---|---|
| VERIFIED | Có source/commit và kết quả cụ thể đã kiểm tra; phạm vi tương ứng được nêu |
| OPERATOR_REPORTED | Log hoặc nhận xét do người vận hành cung cấp; không coi là mở được artifact trên Windows từ xa |
| PARTIAL_EVIDENCE | Mới chứng minh một phần điều kiện; không gán PASS tổng thể |
| NOT_TESTED | Không có phép thử phù hợp hoặc kết quả chưa được cung cấp |
| HISTORY_INCOMPLETE | Chưa xác định được số attempts hoặc root cause đầy đủ |
| WAIVED | Có người duyệt, giới hạn và lý do rõ; không biến WAIVED thành PASS |

## Ghi chú lỗi

ID sự cố ổn định `INC-GD1-...` hoặc `INC-GD0-...`. Lưu *symptom*, *confirmed root cause* (hoặc `UNCONFIRMED`), *attempt evidence*, *fix*, *regression*, *prevention*. Khi một nhận định cũ sai, thêm correction với ngày/nguồn mới thay vì sửa lén lịch sử.

## Cổng R7.4

`python scripts/r7_docs_gate.py --project-root . --out-dir <evidence>` kiểm tra path/link Markdown ở bộ tài liệu chuẩn, schema nhật ký, dấu conflict, hai docstring module không làm thay đổi AST code và tham chiếu mốc R6. Gate chỉ chứng minh **tính nhất quán tĩnh**, không chứng minh tài liệu khoa học chính xác hoặc HMI đã nghiệm thu.

**Lưu ý:** `README.md`/`docs/ARCHITECTURE.md` cũ được giữ để tránh phá lịch sử; README được thêm chỉ dẫn đến tài liệu GĐ1 hiện hành. R8 mới cân nhắc đổi cấu trúc tests, không làm trong R7.
