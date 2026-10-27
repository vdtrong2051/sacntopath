# R7-C — Phạm vi chuẩn hóa nhật ký và chú thích mã nguồn

**Mốc đầu vào:** `feat/gd1-desktop-ui@f923d1e4852f8f36c6b0c7c2c20ecee4dbcf91d1` (R7-B). **Mục tiêu:** nhật ký tiếng Việt dễ truy vết và giải thích rõ các điểm rủi ro của mã nguồn, không phát triển chức năng.

## Tài liệu được chuẩn hóa

- `docs/history/README.md` và `QUY_UOC_GHI_NHAT_KY.md`: trang bắt đầu và chuẩn ghi bằng chứng (mới).
- `DEVELOPMENT_MASTER_LOG.md`: nhật ký tổng; thêm R7-A/R7-B và tách kết quả Git với log Windows.
- `GD0/GD0_EXECUTION_JOURNAL.md`: các PRE-01–06, hạn chế đo lường/hardware.
- `GD1/GD1_EXECUTION_JOURNAL.md`: các lượt thử R5.3, R6, R7; giữ FAIL trước PASS.
- `GD1/INCIDENT_REGISTER.md`: 7 sự cố đã có, giữ nguyên ID; phân biệt lỗi harness với ứng dụng.

## Những tệp Python được ưu tiên chuẩn hóa

| Tệp | Trách nhiệm cần giải nghĩa bằng tiếng Việt |
|---|---|
| `acquisition/native.py` | Nạp SDK DLL riêng trên Windows; không mở camera khi import |
| `storage/session_store.py` | Quy tắc RAW bất biến, thư mục `.partial`/`COMMITTED` và giới hạn mất điện |
| `metadata/store.py` | SQLite schema và nguyên tắc không tự migrate database không rõ nguồn |
| `modules/project_workspace/application/service.py` | Điều phối lệnh/truy vấn Project, không tự mở kho khi import |
| `modules/viewer3d/infrastructure/resident_poc/protocol.py` | Kiểm tra lệnh IPC, giới hạn kích thước/trạng thái |
| `modules/viewer3d/infrastructure/resident_poc/client.py` | Sở hữu tiến trình Render Host và 2 ô shared memory RGB |
| `modules/viewer3d/infrastructure/resident_poc/async_session.py` | Worker riêng, coalescing và copy/ACK trước khi phát frame |
| `ui/shell/viewer_bootstrap.py` | Chọn live/fallback; alias tương thích R5.2/R5.3 |

Các module còn lại vẫn được **kiểm kê**, không đánh dấu đã Việt hóa hoặc được sửa. Đây không phải tuyên bố 100% comment trong 131 tệp Python đã chuẩn hóa.

## Cổng nghiệm thu R7-C

1. Đúng commit đầu vào, working tree sạch trước khi áp dụng; chỉ thay đổi các tệp trong manifest.
2. Trước/sau nguồn Python chỉ thay comment/docstring; **AST bỏ docstring** phải hoàn toàn giống. Đối chiếu SHA gốc, không sửa API/logic/test/SQL/RAW.
3. Bốn nhật ký hiện hành có tiêu đề và nội dung chính tiếng Việt; giữ `INC-GD1-R6-RUNNER-001`, `INC-GD1-R6-RUNNER-002` và mọi FAIL lịch sử.
4. Kiểm tra liên kết nội bộ trong **tài liệu thay đổi**, không tự claim toàn bộ archive không có link hỏng.
5. Kiểm kê đầy đủ `src/scantopath/**/*.py`, xuất JSON/CSV với số module docstring, comment, tệp chưa có docstring và ước lượng ngôn ngữ.
6. `tests/test_gd1_r7_docs.py`, Architecture/Quality Gate, full pytest, CTest Release PASS trên Windows trước khi commit.

**Ngoại lệ giữ nguyên:** `R6_AUTOMATED_PASS / R6_OVERALL_PENDING`; HMI/native bận thực, GPU/VRAM, pointer-to-present chưa kiểm chứng.
