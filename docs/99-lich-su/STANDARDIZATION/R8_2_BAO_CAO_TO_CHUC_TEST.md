# R8.2 — Tổ chức lại kiểm thử theo chức năng

**Baseline Git bắt buộc:** `997536b8f14b95e64642be1028f8318c51efecc5` (R8.1). **Trạng thái:** thay đổi chỉ có hiệu lực sau khi người vận hành chạy `apply`/`verify` trên Windows và commit.

## Quyết định được áp dụng

- Di chuyển **76 tệp test** gồm 75 tệp R8.1 đã kiểm kê và 1 tệp nghiệm thu R8.1; giữ nguyên tên hàm kiểm thử, không bỏ ca nào.
- Tổ chức vào `tests/unit/`, `tests/integration/`, `tests/contracts/`, `tests/ui/`, `tests/native/`, `tests/performance/`, mỗi nhóm chia tiếp theo chủ đề. Bản đồ cũ → mới: [CSV](../../standardization/R8_2_BAN_DO_TEST.csv).
- Thêm `tests/support/raw_fixture.py`, `tests/support/project_seed.py`: chuyển đúng phần thân `raw`, `_seed_v1`, `_seed_numbered` từ các bài test gốc, không sinh số đo hoặc dữ liệu camera thật. Loại bỏ import test–test cho hai nhóm helper này.
- Sửa chỉ số `Path(__file__).resolve().parents[N]` theo độ sâu mới, **giữ cùng repository root**. Cập nhật 9 đường dẫn trong script nghiệm thu R3.5.
- Cho phép công cụ kiểm kê R8.1 đọc path mới thông qua CSV, vẫn gắn mã Git và đường dẫn lịch sử của 97 mục ban đầu.
- Bổ sung kiểm tra AST nhằm phát hiện mất tên bài test, test import test, thay đổi nội dung helper đã tách và test còn nằm sai vị trí.

## Không thực hiện trong R8.2

- **Không xóa test** chỉ do cùng module/fixture; các dấu hiệu trùng lặp phải xác nhận phạm vi hợp đồng trước khi gỡ ở R8.3/R8.5.
- **Không sửa** mã nguồn ứng dụng `src/`, C++, schema SQLite, dữ liệu RAW, Qt/VTK, camera hoặc hợp đồng lỗi.
- **Không thay** quy định `SKIP`, không đổi assert dạng text/source trong R8.2. Những vấn đề đó được theo dõi để sửa ở R8.3.
- **Không công bố** R6 Overall PASS hoặc hoàn tất HMI/native thực địa.

## Điều kiện nghiệm thu

1. Baseline đúng `997536b8`; working tree sạch trước khi áp dụng.
2. Có đúng 76 đường dẫn mới từ 76 đường dẫn gốc, không còn file test phẳng ở `tests/`.
3. AST của tất cả tên hàm test ở mỗi tệp giữ nguyên; `raw`, `_seed_v1`, `_seed_numbered` có phần thân AST y nguyên bản gốc.
4. `tests/support/` không import Qt hoặc mở camera thật; dữ liệu chỉ ở `tmp_path` của test.
5. R8.1 inventory vẫn kiểm kê đủ 97 tệp lịch sử; R3.5 focused runner trỏ đúng vị trí hiện hành.
6. `pytest -q tests`, Architecture Guard, Quality Gate và `ctest -C Release` **PASS trên Windows** trước khi commit. Không biến SKIP có điều kiện thành PASS.
7. Xuất bằng chứng ra `_setup` ngoài repository; không thêm file evidence vào Git.

**R8.3 tiếp theo:** sửa kiểm thử giòn, hợp nhất fixture có kiểm soát và kiểm soát SKIP theo nodeid. **08.06.6** sau R8 mới xét nghiệm thu GĐ1 toàn diện.
