# GĐ1 — Sổ sự cố kỹ thuật

**Bản R7-C:** giữ nguyên mã sự cố đã tồn tại; phân biệt lỗi chương trình với lỗi công cụ kiểm thử. Nguyên nhân chưa chứng minh thì ghi **CHƯA XÁC NHẬN**, không chuyển thành kết luận.

## 1. Danh mục

| Mã sự cố | Triệu chứng | Phân loại | Kết quả đã ghi nhận | Rủi ro còn lại |
|---|---|---|---|---|
| `INC-GD1-07-ARCH` | Lỗi quoting PowerShell/Qt QObject/import trong đợt 07.11–07.12 | Công cụ và ranh giới kiến trúc | Có Architecture Guard 07.11, Quality Gate 07.12; R6 đều PASS | Không chứng minh tất cả tương tác bất đồng bộ |
| `INC-GD1-08-VTK` | Qt/VTK cùng tiến trình không ổn định | Vòng đời native/Qt | R4.5 chọn Render Host riêng, có điều kiện | Chưa thực hiện crash-injection C++ thật |
| `INC-GD1-R5-003` | File Qt shell vượt giới hạn 500 dòng; cảnh báo Qt image API | Hồi quy cấu trúc | Tách bootstrap, sửa gọi API và hồi quy theo log R5.2 | Cần giữ giới hạn khi bổ sung UI |
| `INC-GD1-R5-001` | R5.3 chọn hình học báo FAIL khi fixture chưa có frame hợp lệ | Bài kiểm thử và UX | Sửa fixture, giữ chốt từ chối khi chưa có frame; 16 focused PASS | Cần HMI thật cho thao tác người dùng |
| `INC-GD1-R5-002` | Full R5.3 617 PASS, 1 FAIL do test dò chuỗi `LiveViewer3DController(` | Bài kiểm thử phụ thuộc mã nguồn | Dùng alias tương thích lớp tương tác; R6 full pytest 618 PASS | R8 nên kiểm tra hợp đồng thực thay vì chuỗi |
| `INC-GD1-R6-RUNNER-001` | Mọi chương trình R6 không khởi chạy, `ArgumentList` rỗng | **Lỗi runner**, không phải app | Sửa tham số `$args` xung đột biến tự động của PowerShell | Cần test runner trong PowerShell 5.1 |
| `INC-GD1-R6-RUNNER-002` | Chương trình in PASS nhưng runner ghi FAIL; CTest thiếu cấu hình | **Lỗi runner**, không phải app | Lấy mã thoát trực tiếp và dùng `ctest -C Release`; 14/14 cổng tự động PASS | Luôn kiểm tra exit code/receipt |

## 2. Chuỗi bằng chứng và cách phòng ngừa

### `INC-GD1-07-ARCH`

Hồ sơ [07.12 — rủi ro hợp nhất](../../archive/GD1/07/07_12_CONSOLIDATION_RISK_REGISTER.md) ghi nhận tình huống quote trong `python -c` trên Windows và ranh giới import, QObject. Nguyên nhân chi tiết của *mọi* attempt **CHƯA ĐỦ LỊCH SỬ**. Phòng ngừa: dùng script `.py` cho lệnh dài, kiểm tra import/lifecycle bằng test Windows thật.

### `INC-GD1-08-VTK`

Xem [08.02 — sửa crash](https://github.com/vdtrong2051/sacntopath/blob/08ef856a04d61f20db1e26b2ceeb399065db902f/docs/archive/GD1/08/08_02_CRASH_REPAIR.md) và [R4.5 — quyết định kiến trúc](../../archive/GD1/R1-R5/R4_05_RENDERER_ARCHITECTURE_DECISION.md). Tách renderer khỏi GUI làm giảm khả năng một lỗi renderer giết trực tiếp Qt; **không chứng minh** mọi crash native thực đều đã được xử lý. Cần phép thử có kiểm soát ngoài tiến trình Qt.

### `INC-GD1-R5-003`

Log R5.2 ghi nhận `main_window.py` vượt giới hạn dòng và cảnh báo API ảnh Qt; đã tách phần khởi tạo Viewer ra khỏi shell, giữ khả năng tương thích. Phòng ngừa: giữ composition root gọn, mỗi module một trách nhiệm. Số lần sửa trước PASS chưa có thống kê đầy đủ.

### `INC-GD1-R5-001`

Test `test_r53_live_click_emits_uv_only_in_select_mode` chưa cấp frame đã xác nhận nên `_ready_tools()` từ chối chọn là **đúng chốt an toàn**. Sửa test fixture chứ không tháo chốt. Cùng đợt cải tiến toolbar SVG, lưới và Inspector; log người vận hành báo các focused test PASS.

### `INC-GD1-R5-002`

Test R5.2 dò chữ trong `viewer_bootstrap.py`, trong khi R5.3 khởi tạo lớp kế thừa. Bản vá dùng alias thật trỏ tới `InteractiveViewer3DController`; không đánh lừa bằng chuỗi comment. Sự cố đã được hồi quy xác nhận qua R6, nhưng test kiểm chuỗi vẫn là khoản nợ cần đánh giá ở R8.

### `INC-GD1-R6-RUNNER-001`

Tham số tên `$args` va chạm biến tự động PowerShell; mọi lệnh con dừng trước pytest/CTest, kéo theo thiếu receipt. Sau sửa, các lệnh thực thi đã chạy. **Không** ghi các FAIL giả ban đầu thành lỗi module Python/C++.

### `INC-GD1-R6-RUNNER-002`

Bản runner tiếp theo không lấy được exit code (trống), và CTest không dùng `-C Release` cho build multi-config. Sau sửa, đối chiếu `Process.ExitCode` của tiến trình; log R6 báo 14/14 PASS, 618 Python PASS/3 SKIP, CTest 2/2; vẫn chưa phải PASS tổng thể HMI.

## 3. Những điều không được liệt kê là sự cố đã phát sinh

| Rủi ro | Trạng thái đúng |
|---|---|
| Đóng cửa sổ khi native C++ **thực sự bận** | `NOT_TESTED` theo phạm vi R6 |
| Tiêm lỗi C++ thực | `NOT_TESTED`; kill/SIGTERM chỉ là kết thúc có kiểm soát |
| GPU/VRAM, độ trễ hiển thị vật lý | `NOT_MEASURED`/thiếu đo |
| Symlink privilege Windows | Ba bài SKIP, không là chứng nhận bảo vệ symlink |

## 4. Quy tắc thêm sự cố

Dùng [quy tắc ghi nhật ký](../QUY_UOC_GHI_NHAT_KY.md). Một sự cố mới cần ID, ngày/nguồn, triệu chứng, phân loại, nguyên nhân và **mức xác nhận**, từng attempt thực tế, bản sửa, kiểm thử sau sửa, giới hạn còn mở và phòng ngừa. Nếu chỉ là kế hoạch phép thử, không cấp ID *incident đã xảy ra*.
