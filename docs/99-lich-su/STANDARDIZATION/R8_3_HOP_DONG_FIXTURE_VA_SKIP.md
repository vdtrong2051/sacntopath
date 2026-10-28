# R8.3 — Hợp đồng fixture và chính sách SKIP có định danh

**Baseline:** `feat/gd1-desktop-ui@c4bbf11145626b07e27950b4c720bd6fffcfadb2` (R8.2). **Phạm vi:** chỉ công cụ kiểm thử, test và tài liệu; không sửa mã thực thi, dữ liệu RAW hay SQLite của người dùng.

## 1. Fixture dùng chung

- `tests/support/raw_fixture.py::raw`: gói RGB-D **tổng hợp**, MJPEG/Y16 có kích thước độc lập, `measured=False`, tỷ lệ sâu 0,001 m/unit; không mở camera và không tuyên bố độ chính xác đo lường.
- `tests/support/project_seed.py::_seed_v1`: tạo cơ sở dữ liệu và dữ liệu mẫu **trong thư mục tạm do pytest cung cấp**, không thay đổi kho người vận hành.
- `tests/support/project_seed.py::_seed_numbered`: sau khi tạo v1, thực hiện **di trú tường minh trên kho tạm**, lưu bản backup, cấp mã. Không chạy ở thư mục dữ liệu người dùng.
- R8.3 thêm kiểm thử bất biến fixture. **Không đổi thân 3 hàm** đã được R8.2 bảo vệ bằng đối chiếu AST với mốc `997536b`.
- Những fixture Qt khác chưa được hợp nhất trong R8.3; chuyển tiếp sang R8.4 khi đã có runner và kiểm tra vòng đời GUI.

## 2. Danh sách cho phép SKIP — Windows

Chỉ được SKIP khi **đúng ID bài test**, lý do mô tả **symlink và quyền Windows**, hệ điều hành đang chạy là Windows; các bài kiểm tra bắt buộc 07.12 không được SKIP. SKIP chưa được thay bằng PASS, không phải bằng chứng bảo vệ symlink trên Windows đã chạy.

| Tệp R8.2 | Tên test | Lý do chấp nhận |
|---|---|---|
| `tests/integration/storage/test_gd1_07_2_numbered_storage.py` | `test_path_rejects_escape_alias_and_symlinks` | Windows không cấp quyền tạo symlink |
| `tests/native/renderer/test_gd1_r4_3_transport_lifecycle.py` | `test_r43_source_symlink_is_not_followed` | Windows không cấp quyền tạo symlink |
| `tests/unit/raw/test_raw_storage.py` | `test_extra_file_or_symlink_is_rejected` | Windows không cấp quyền tạo symlink |

`check_qt_acceptance_xml.py` chấp nhận cả tên class JUnit trước R8.2 khi đọc hồ sơ cũ. **Các SKIP khác đều FAIL**, kể cả khi có cùng từ khóa *symlink*. Những ca đã được chạy thay vì SKIP cũng hợp lệ.

## 3. Hợp đồng R5.2 thay cho chuỗi nguồn

Bài `test_r52_composition_root_contains_bounded_close_gate` đổi từ tìm **đúng chuỗi văn bản** sang đọc cây cú pháp Python (AST) và xác minh các ranh giới: khởi tạo Viewer có hai chế độ (offscreen, isolated), Render Host có factory, `closeEvent` có `begin_shutdown` và yêu cầu đóng bất đồng bộ. Các bài kiểm tra hành vi live/fake-session R5.2 được giữ nguyên. Việc này giảm lỗi khi sửa khoảng trắng/chú thích, nhưng AST vẫn chỉ chứng minh **cấu trúc**, không chứng nhận HMI/native.

## 4. Tiêu chí nghiệm thu R8.3

1. Baseline R8.2 sạch; chỉ sửa các file trong manifest; không chạm `src/`, `cpp/`, `.venv/`, `build-orbbec/`.
2. Parser JUnit chạy 10 ca kiểm tra bao gồm đúng 3 SKIP và những tình huống từ chối, không tự tăng ngưỡng SKIP.
3. Hợp đồng RAW/SQLite dùng thư mục pytest và có các test kiểm tra nguồn dữ liệu giả, không mở thiết bị thật.
4. R8.2 Structure Gate và R8.1 Inventory giữ nguyên PASS; **tên các test cũ không đổi**.
5. Full pytest không FAIL, CTest Release 2/2 PASS, Architecture/Quality Gate PASS trên máy Windows.
6. Không tự gắn `R6_OVERALL_PASS` hay nghiệm thu HMI/nhiễu GPU: R6 vẫn `R6_AUTOMATED_PASS / R6_OVERALL_PENDING`.

## 5. Tiếp nối

R8.4 xây dựng lệnh kiểm thử thống nhất `Quick / Full / Acceptance`, thống nhất JUnit/JSON và đường dẫn bằng chứng ngoài repo. R8.5 đánh giá trùng lặp/rác có chứng cứ trước khi xóa.
