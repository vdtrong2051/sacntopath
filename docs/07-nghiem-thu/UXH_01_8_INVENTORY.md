# UXH-01.8 — Kiểm kê cấu trúc và capability

> Baseline source đối chiếu: `feat/gd2-uxh-01-hardening@016f0cf06de65a432626bb58ec8868483b30eb04` (2026-11-01).  
> Mức bằng chứng: `SOURCE_REVIEWED / GIT_VERIFIED`; kết quả kiểm thử Windows tại mốc UXH-01.8: `NOT_TESTED` cho đến khi có receipt mới.  
> Báo cáo này **không** chứng nhận GĐ2/GĐ3 đã hoàn thành và **không** ghi đè các acceptance ledger cũ.

## 1. Phạm vi các checkpoint UXH

| Checkpoint | Đối tượng kiểm kê | Nguồn kiểm chứng trong repo | Trạng thái tại snapshot |
|---|---|---|---|
| 01.1 | Ranh giới ứng dụng, Depth two-point UX | `tests/contracts/kien_truc/test_uxh_01_1_boundary.py`, `tests/unit/geometry/test_uxh_depth_*` | Code + tests present; mới chưa chạy |
| 01.2 | Viewer spatial visual, toolbar và grid | `live_tools.py`, `tests/ui/viewer/test_uxh_01_2_*`, `tests/native/viewer/test_uxh_01_2_*` | Code + tests present |
| 01.3 | Workflow context, chọn dữ liệu | `tests/ui/workflow/test_uxh_01_3_navigation.py` và `tests/unit/workflow/test_uxh_01_3_context.py` | Code + tests present |
| 01.4-R02 | Click Capture → RAW Replay | `tests/ui/workflow/test_uxh_01_4_r02_click_to_raw.py` | Code + tests present |
| 01.5 | Typed Point/Face picking và stale-future | `tests/unit/viewer/test_uxh_01_5_typed_pick.py`, `tests/ui/viewer/test_uxh_01_5_selection.py` | Code + tests present |
| 01.6 | PLY temp leases, Qt/native cleanup | `preview_scratch_leases.py`, `tests/*/test_uxh_01_6_*`, `scripts/uxh_01_6_preview_stress.py` | Code + tests present |
| 01.7 | Named layout slots, Advanced toolbar, Canvas, Capture/Inspector responsive | Commit `016f0cf...`, 8 production files + 7 tests (15 files) | `GIT_VERIFIED`; Windows reported previous targeted PASS; UXH-01.8 full retest pending |

## 2. Thành phần kiến trúc cần giữ

1. Python 3.12 điều phối application; C++20 + pybind11 xử lý native nơi có hợp đồng.
2. PySide6/Qt UI không nạp VTK Render Host vào GUI thread.
3. Render Host là tiến trình con; IPC/SHM có vòng đời đóng an toàn.
4. Gemini 2 đi qua camera subprocess cô lập; Camera UI không trực tiếp giữ native SDK pointers.
5. SQLite/RAW giữ nguyên phân tách, Replay không cần camera đã mở.
6. Geometry Preview XYZRGB là dữ liệu xem tạm; không suy đoán pose, độ chính xác, đa góc hoặc mesh đã tin cậy.
7. Điểm chọn Viewer có source/scene revision và giới hạn đơn vị; Depth A–B không tự chứng nhận hiệu chuẩn đo lường.

## 3. Bảng truy vết source chính

| Mảng | Source chính | Tình trạng xem xét |
|---|---|---|
| Entry / Shell | `src/scantopath/ui/main.py`, `ui/shell/main_window.py` | Tìm thấy trong cây Git |
| Capture / Replay | `modules/capture/presentation/`, `modules/capture/infrastructure/` | Tìm thấy |
| Camera native | `acquisition/native.py`, `modules/capture/infrastructure/process_camera.py`, `cpp/src/acquisition/orbbec_camera_source.cpp` | Tìm thấy |
| Viewer | `modules/viewer3d/presentation/`, `modules/viewer3d/infrastructure/resident_poc/` | Tìm thấy |
| Geometry & measurement | `ui/shell/geometry_preview.py`, `ui/shell/geometry_measurement.py`, `application/preview_scratch_leases.py` | Tìm thấy |
| UI responsive / inspector | `modules/capture/presentation/workspace_layout.py`, `ui/components/property_inspector.py` | Tìm thấy |
| Existing full verification | `scripts/verify.ps1`, `scripts/r8_4_verify.py` | Tìm thấy |

## 4. Phát hiện kiểm kê cần được xử lý qua tài liệu

- Trang `docs/README.md`, `docs/03-modules/VIEWER_3D.md`, `docs/03-modules/DESKTOP_UI.md`, `docs/04-phat-trien/CAI_DAT_VA_CHAY.md`, `docs/05-quan-ly/TRANG_THAI_DU_AN.md` có metadata snapshot cũ hơn UXH-01.7. **Không** được đọc các snapshot cũ đó như trạng thái UXH mới nhất; dùng phụ lục UXH-01.8 để nối truy vết. Đề nghị tái đồng bộ metadata toàn hệ thống trong một checkpoint tài liệu riêng nếu cần, không sửa hàng loạt ở closure này.
- USB PnP `OK` **không** đồng nghĩa DLL load/camera stream PASS. Trước đó SDK DLL load FAIL khi `SCANTOPATH_ORBBEC_SDK_BIN` chưa được gán trong process.
- Native Orbbec child đã từng báo lỗi khi ngắt thiết bị đột ngột; process isolation bảo vệ GUI nhưng không khẳng định SDK child không crash. Xem ledger GD2-09 lịch sử.
- Tác vụ kiểm toán đọc source/GitHub **không** tạo được Windows/HMI receipt. Các kết quả thực phải ghi bởi bộ runner trên Windows trong `_setup`, ngoài Git.

## 5. Điều kiện đóng

Không P0 tồn đọng; targeted + R8.4 Full có `PASS` thực; hardware và HMI bắt buộc có receipt riêng, xác nhận giới hạn P1/P2; file closure phải gắn SHA và thời gian đúng. Chi tiết: [ma trận regression](UXH_01_8_REGRESSION_MATRIX.md) và [acceptance](UXH_01_8_ACCEPTANCE.md).
