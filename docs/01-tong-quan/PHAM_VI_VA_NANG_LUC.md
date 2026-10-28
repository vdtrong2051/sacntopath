# Phạm vi và năng lực ScanToPath — phân biệt nguồn, phần mềm và nghiệm thu

> `owner: PRODUCT_SCOPE_OWNER` · `as_of_commit: 7a0df7c5b596ff8750bf91f47310067c53a8b204` · `verified_at: 2026-10-28`  
> `scope: baseline phần mềm desktop GĐ0/GĐ1; chưa phải trạng thái hardware ngoài Git` · `evidence_level: SOURCE_REVIEW; HISTORICAL_OPERATOR_REPORT cho Windows/Gemini2`.

## 1. Cách đọc ma trận

Mỗi năng lực có **ba trục độc lập**:

1. **Triển khai:** `IMPLEMENTED`, `PARTIAL`, `NOT_IMPLEMENTED_IN_THIS_BUILD`, `PLANNED` — xác minh qua mã nguồn và API, không suy từ roadmap.
2. **Kiểm thử tự động:** có bài test/source và, khi có, log hoặc receipt tương ứng. Sự tồn tại của test **không bằng** test đã PASS trên máy của người đọc.
3. **Kiểm thử vật lý/thủ công:** chỉ PASS khi đo trên thiết bị, điều kiện, ngày và người duyệt có bằng chứng. Không có thì `NOT_TESTED` hoặc `PARTIAL_EVIDENCE`.

`measured=True` trong RAW metadata là provenance cảm biến, không phải một mục nghiệm thu thiết bị. Bảng dưới đây là **snapshot đọc Git**, không tạo trạng thái mới cho sổ DOC-04.

## 2. Ma trận năng lực hiện hành

| ID | Năng lực/đầu ra | Triển khai tại mốc Git | Nguồn kiểm chứng | Hạn chế cần biết |
|---|---|---|---|---|
| CAP-01 | Desktop Qt với bốn workspace và dock | IMPLEMENTED | `ui/main.py`, `ui/shell/main_window.py`, `tests/ui/` | HMI DPI 100/125/150 chưa được nghiệm thu tổng thể |
| CAP-02 | Tạo/đọc Project, Specimen, ScanSession, Capture, ProcessingRun | IMPLEMENTED | `metadata/store.py`, `modules/project_workspace/`, `tests/integration/project/` | ProcessingRun ghi metadata, không tự tính mesh/path |
| CAP-03 | RAW v2 MJPEG/Y16, manifest SHA-256, read-back, legacy v1 | IMPLEMENTED | `storage/session_store.py`, `tests/unit/raw/` | Không giao dịch nguyên tử gộp SQLite với filesystem |
| CAP-04 | Numbered Storage (P/S/T/C/R), migration có lệnh riêng | IMPLEMENTED trong các code path liên quan | `storage/numbered*.py`, `storage/legacy_migration.py`, `tests/integration/storage/` | Migration opt-in; không tự chạy khi mở UI |
| CAP-05 | Gemini 2 acquisition một lần qua C++/pybind11 | IMPLEMENTED dưới lệnh native/adapter | `acquisition/`, `cpp/`; PRE-06 operator report | Không có pose, motion-control, metric calibration validation |
| CAP-06 | Viewer mở PLY point/mesh và OBJ mesh | IMPLEMENTED | `viewer3d/infrastructure/scene_reader.py`, `tests/native/viewer/` | Tệp ngoài không chứng minh đơn vị/hệ tọa độ |
| CAP-07 | Render Host tách tiến trình, IPC/ACK, frame phiên bản | IMPLEMENTED | `viewer3d/infrastructure/resident_poc/`, tests R4 | Không chứng nhận mọi crash/busy C++ thật đã được kiểm soát |
| CAP-08 | Orbit/pan/zoom, point/cell picking, grid/layers, Inspector | IMPLEMENTED | `interactive_controller.py`, tests R5.3 | Giá trị XYZ không phải kết quả đo đã hiệu chuẩn |
| CAP-09 | RAW replay trên UI và back-project depth→cloud metric | NOT_IMPLEMENTED_IN_THIS_BUILD | GĐ2 roadmap | Không suy từ `read_raw()` rằng replay UI đã hoàn thành |
| CAP-10 | ROI/filter/normals/export pipeline, multi-view pose/fusion | NOT_IMPLEMENTED_IN_THIS_BUILD | GĐ2/GĐ3 roadmap | Không giả lập kết quả như dữ liệu đo thật |
| CAP-11 | Đánh giá sai số/coverage/trust, feature/digital replica | PLANNED | Roadmap GĐ3–GĐ4 | Chưa có phép đo mẫu chuẩn được tuyên bố cho pipeline |
| CAP-12 | Zigzag/Contour và robot actuation trên desktop này | NOT_IMPLEMENTED_IN_THIS_BUILD | Định hướng ứng dụng, không phải source GĐ1 | Path ≠ trajectory thực, không có controller robot trong build |
| CAP-13 | HMI/GPU/native-busy cuối GĐ1 | PENDING_ACCEPTANCE | `docs/acceptance/GD1_R6_ACCEPTANCE_STATUS.md` | Qt offscreen/CTest/benchmark không thay phép đo thực |

Cảnh báo: các số thứ tự R1–R8, 06–20, GĐ0–GĐ5 được dùng cho **mốc công việc khác nhau**, không phải những phiên bản của cùng một pipeline. Một tính năng hoàn thành trong bản thử nghiên cứu bên ngoài repository không được tự nhập vào CAP-09–12 mà không có source hoặc nghiệm thu được liên kết.

## 3. Những gì người dùng có thể thao tác hôm nay

**Kịch bản A — quản lý dữ liệu kỹ thuật.** Mở ứng dụng, chuyển vào Project Workspace, chọn một root SQLite đã có hoặc tạo qua thao tác tường minh được hỗ trợ; xem Project → Specimen → Session → Capture/Run và audit. UI không tự chạy thuật toán chỉ vì một `ProcessingRun` có trạng thái `succeeded` do metadata được cập nhật.

**Kịch bản B — kiểm tra một tệp 3D có sẵn.** Vào Kiểm tra 3D, chọn một PLY hoặc OBJ hợp lệ. Viewer dựng điểm hoặc mặt trong Render Host; orbit/pan/zoom và chọn phần tử gửi kết quả về Inspector. Nguồn tệp có SHA-256; đơn vị/hệ tọa độ vẫn `unknown` nếu chưa có hồ sơ đo.

**Kịch bản C — thu một RAW Gemini 2.** Chỉ dùng lệnh one-shot có chủ đích, SDK và native module phù hợp, thiết bị được kiểm tra. Lệnh sẽ **ghi dữ liệu mới ra đĩa**; không đưa vào Quick Start. Đọc/verify RAW có thể thực hiện ngoại tuyến, nhưng phải cung cấp đường dẫn thật của một Capture đã lưu.

## 4. Những cổng khoa học/nghiệm thu cần có trước khi mở rộng

| Cổng | Điều kiện tối thiểu trước khi khẳng định năng lực |
|---|---|
| Depth → 3D metric | Thang đo và intrinsics chính xác theo stream; reprojection và mẫu chuẩn; xử lý giá trị invalid và distortion |
| Ghép nhiều góc | Pose tương đối/chuỗi biến đổi có chứng cứ; đánh giá sai số/drift; từ chối ghép thiếu pose |
| Mesh/feature/trust | Phân biệt measured/observed, inferred/interpolated và missing; residual/uncertainty; giữ nguồn dữ liệu |
| Chuẩn bị đường robot | Hệ tọa độ robot/workpiece, tool/surface offset, ràng buộc hướng súng, khả thi cơ học và kiểm thử an toàn trước khi chạy |
| HMI/native thực địa | Test DPI, close-while-busy, native fault injection, resource/VRAM, input-to-present có phương pháp đo |

Đây là tiêu chí mục tiêu, **không** phải kết quả đã đạt tại mốc Git.

## 5. Quản lý rủi ro và tình trạng chưa xác minh

- **Cấu hình cơ khí:** nguồn Git hiện tại không cung cấp bản nghiệm thu xác nhận camera cố định hay cầm tay, bàn quay/trục nghiêng, động cơ/encoder và đồng bộ cơ khí. Phải có hồ sơ version/thiết kế được duyệt; trước đó ghi `OPEN_REQUIRED_SOURCE_DECISION`.
- **Đồng bộ RGB–Depth:** chênh timestamp chỉ là chẩn đoán (`sdk_reported_unverified`), không có quyền chứng nhận cùng clock domain/exposure.
- **Độ bền RAW:** `COMMITTED` và SHA-256 giúp phân biệt đầy đủ/hỏng; không phải chống mất điện tuyệt đối, và không có giao dịch nguyên tử đa hệ SQLite–filesystem.
- **SKIP trên Windows:** ba trường hợp tạo symlink có lý do được allowlist; **SKIP không phải PASS**.
- **HMI tổng thể:** R6 automated PASS theo log người vận hành nhưng R6/GĐ1 overall còn PENDING; mốc cuối 08.06.6 phải có kết quả thật hoặc waiver có phê duyệt.

## 6. Nguồn và cách cập nhật

Kiểm tra source theo đường dẫn ở bảng; xem [Kiến trúc](../02-kien-truc/KIEN_TRUC_HE_THONG.md), [Hợp đồng dữ liệu](../02-kien-truc/DU_LIEU_VA_HE_TOA_DO.md), [Lộ trình](LO_TRINH_PHAT_TRIEN.md) và [Biên bản nghiệm thu](../07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md). Khi DOC-04 tạo `TRANG_THAI_DU_AN`, bảng này chỉ được giữ như mô tả năng lực theo commit; trạng thái điều hành phải tra nguồn duy nhất mới. Không sửa hồi tố bằng chứng lịch sử.
