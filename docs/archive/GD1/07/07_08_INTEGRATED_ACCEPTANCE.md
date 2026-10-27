# GĐ1 — 07.8: Tổng nghiệm thu Project Workspace & SQLite

**Baseline (đã push):** `feat/gd1-desktop-ui` @ `03f6448a291c2d20d1d0e0af98e5e2c8e5739d21` (07.7).

**Phạm vi:** chỉ bổ sung kiểm thử/biên bản. **Không sửa mã ứng dụng, schema SQLite, dữ liệu RAW, camera, thuật toán xử lý 3D, giao diện HMI hay template QSS.** Không chạy migration trên dữ liệu người dùng. Mọi tác động dữ liệu được kiểm thử trong `tmp_path` do pytest tạo mới.

## Điều kiện nghiệm thu

| Mã | Hợp đồng tích hợp | Bằng chứng tự động |
|---|---|---|
| AC-01 | Khởi động không tự tạo database, không mở camera | `test_gui_starts_empty_*` và hồi quy 06 |
| AC-02 | SQLite v1 đọc được nhưng không ghi/cấp mã tự động | `test_v1_can_be_opened_*`, `test_gui_v1_is_readonly_*` |
| AC-03 | v1→v2 chỉ qua lệnh migration rõ ràng; có backup | `_seed_numbered`, `test_full_legacy_roundtrip_*` |
| AC-04 | Project/Specimen/Session CRUD v2, đóng phiên và bền vững sau mở lại | `test_explicit_v2_*`, `test_gui_writer_*` |
| AC-05 | Cây P/S/T/C/R và Inspector không làm sai ID nội bộ | `test_capture_run_audit_*`, `test_gui_numbered_*` |
| AC-06 | Capture RAW v1 kiểm tra cấu trúc, RAW v2 kiểm tra SHA-256, báo thiếu/hỏng; không nhận là kiểm chứng hình học | `test_missing_raw_*`, `test_numbered_raw_v2_*`, `test_gui_numbered_*` |
| AC-07 | ProcessingRun là lịch sử metadata và output chỉ là tham chiếu | `test_capture_run_audit_*`, hồi quy 07.6 |
| AC-08 | Audit từ SQLite, thao tác xem/verify RAW không sinh audit mới | `test_capture_run_audit_*` |
| AC-09 | 07.7 dry-run không ghi; copy nguyên byte; backup; đổi con trỏ; rollback | `test_full_legacy_roundtrip_*` |
| AC-10 | Sau rollback giữ bản sao C0001, không tự xóa/ghi đè | `test_dry_run_after_rollback_*` |
| AC-11 | SQLite integrity và foreign key đúng sau lưu và migration | `test_explicit_v2_*`, `test_full_legacy_roundtrip_*` |
| AC-12 | Không nhiễm fixture/capture/run khi kho trống | `test_empty_v2_store_*` |
| AC-13 | Hồi quy GĐ0–GĐ1, Qt trên Windows, CTest và native self-test không dùng camera | `verify.ps1` |

## Giới hạn kỹ thuật phải giữ nguyên

- **Mã public code có scope riêng:** P đánh theo kho, S theo Project, T theo Specimen; không giả định tăng liên tục toàn cục.
- **`state=verified` cho RAW v1** chỉ có nghĩa vượt kiểm tra *cấu trúc*; RAW v1 không có bằng chứng SHA-256 giống v2. Với RAW v2, kiểm tra manifest/hash không suy ra chất lượng hiệu chuẩn, độ chính xác metric, pose hay tính đầy đủ của mô hình.
- **Rollback 07.7** chuyển con trỏ SQLite về legacy, còn bản sao RAW đánh số vẫn tồn tại. Do đó `dry-run` sau rollback **có thể trả `FileExistsError`**; đây là chặn ghi đè có chủ đích, không phải rollback thất bại. Không dùng `Remove-Item` tự động để làm cho dry-run "qua".
- `audit_events` ghi migration schema ngay cả trong kho v2 không có Project. Không coi đó là đối tượng dự án giả.
- Nghiệm thu 07.8 không chứng minh trải nghiệm tải lượng hàng nghìn Capture, dữ liệu camera thật, độ chính xác 3D hay quy trình trên dữ liệu sản xuất.

## Thực thi nghiệm thu tự động (Windows)

1. Xác minh nhánh `feat/gd1-desktop-ui`, HEAD `03f6448...`, working tree sạch. Giải nén PATCH riêng vào `_setup\ScanToPath_GD1_07_8`.
2. Chạy `apply.ps1`, chỉ thêm 3 tệp kiểm thử/tài liệu.
3. Chạy `verify.ps1`: cần PySide6; chạy đủ 14 case 07.8 (9 headless + 5 Qt), full pytest (bao gồm GĐ0), CTest và native `--self-test` **không truy cập camera**; tạo `acceptance/07_08_RESULT.md` và `07_08_RECEIPT.json` trong **thư mục gói vá**, không trong repository.
4. Kiểm tra HMI trực quan theo mục dưới, rồi `publish.ps1 -ManualUiAccepted` mới commit/push đúng 3 tệp. Không merge vào `main`.

## Kiểm tra HMI trực quan (bắt buộc, trên bản sao/kho test)

- [ ] Mở ứng dụng khi chưa chọn kho: không có cây hay DB được tự sinh; bốn workspace và ba dock còn hoạt động.
- [ ] Chọn kho v1 test: cây đọc được, thêm/sửa/đóng phiên bị khóa.
- [ ] Chọn kho v2 test: cây đúng Project→Specimen→Session→Capture/Run; Inspector và mã public đúng; không đổi ID.
- [ ] Tạo/Sửa/Đóng Session trên **kho v2 test riêng**, đóng rồi mở lại: dữ liệu đúng, không sinh capture giả.
- [ ] Chọn Capture synthetic: kiểm tra RAW chỉ khi nhấn nút, kết quả đúng; Run/Audit hiển thị metadata thật.
- [ ] Thao tác Thu gọn / Mở dock trên laptop 14 inch; không chồng lấp, các nút vẫn dùng được.
- [ ] Đóng cửa sổ trong khi worker đang chạy: GUI không crash; tự đóng sau khi worker kết thúc.
- [ ] Không chụp camera, không xử lý 3D, không migration dữ liệu thật trong buổi nghiệm thu.

**Tiêu chí khóa GĐ1-07:** `verify.ps1` kết thúc thành công, có biên bản tự động và checklist trực quan đạt, working tree chỉ gồm 3 tệp đã kiểm tra, commit/push trên nhánh tính năng thành công. Lúc đó mới chuyển sang **phiên 08: VTK/PLY Viewer**.
