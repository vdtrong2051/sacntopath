# GĐ0 — Software Foundation, RGB-D RAW và metadata

> `owner: STAGE_OWNER` · `as_of_commit: 81da5d2050324b1dc4a65ffbca9a38ed1ebba10a` · `verified_at: 2026-10-28`  
> `scope: hồ sơ giai đoạn, không sửa hồ sơ PRE-06` · `source-of-truth: nguồn stage outcome và handover; gate ở 07-nghiem-thu` · `evidence_level: GIT_MERGE_VERIFIED + PRE06_OPERATOR_REPORTED`

## 1. Mục tiêu và tiêu chí đã đặt

GĐ0 tạo phần mềm nền **offline-first** để thu nhận RAW RGB-D và lưu truy xuất có nguồn, không phải thuật toán đo hình học. Đầu ra đúng: thu Gemini 2 theo lệnh, hai stream color MJPEG/depth Y16, metadata schema v2, checksum/manifest/`COMMITTED`, SQLite Project→Specimen→ScanSession→Capture→ProcessingRun và audit. Bên ngoài GĐ0: align/metric calibration/pose đo thật, point-cloud/multiview, đường robot, actuator tự động.

## 2. Các lát cắt PRE-01→06 và deliverables

| Lát cắt | Deliverable tồn tại | Vị trí bảo trì / dấu hiệu kiểm chứng |
|---|---|---|
| PRE-01 | C++20 + OrbbecSDK Gemini 2, pybind11 opt-in | `cpp/CMakeLists.txt`, `src/scantopath/acquisition/native.py` |
| PRE-02 | `RawRgbdCaptureMetadataV2`, MJPEG/Y16 và intrinsics | `src/scantopath/domain/raw_rgbd.py`, [contract](../archive/GD0/PRE/PRE_02_RAW_RGBD_CONTRACT.md) |
| PRE-03 | Byte-preserving RAW, SHA-256 + `COMMITTED` | `src/scantopath/storage/session_store.py`, [RAW module](../03-modules/RAW_STORAGE.md) |
| PRE-04 | `capture_once --once` opt-in, đọc lại RAW và kiểm byte | `src/scantopath/acquisition/capture_once.py` |
| PRE-05 | MetadataStore, SQLite/audit, ProcessingRun lifecycle | `src/scantopath/metadata/store.py`, [Project module](../03-modules/PROJECT_WORKSPACE.md) |
| PRE-06 | Hồ sơ nghiệm thu trên Windows theo operator, merge PR #3 | [PRE-06](../archive/GD0/PRE/PRE_06_GD0_ACCEPTANCE.md), [GD0 acceptance](../07-nghiem-thu/GD0_ACCEPTANCE.md) |

Commit merge GĐ0 đã ghi trong nhật ký: `8bf33591389dcdff82f0fbd5bf5932a22547c984` (PR #3). Việc `PRE-06` chứa checkbox cũ chưa đóng tại ngày soạn không được sửa hồi tố; merge sau đó là một bằng chứng Git khác có mốc thời gian riêng.

## 3. Luồng thật và giới hạn dữ liệu

`Gemini 2 → OrbbecSDK C++ → pybind11/adapter → RawRgbdCapture → SessionStore → manifest+COMMITTED → read_raw` là luồng thu và lưu. SQLite liên kết Project/Specimen/Session/Capture/Run theo ID; database **không** chứa nguyên byte ảnh. Color/depth có kích thước và timestamp riêng; `depth_scale_m_per_unit` là thông số chuyển đơn vị, **không xác nhận sai số đo**. `measured=true` chỉ xác nhận nguồn cảm biến thật; `camera_pose` có thể `None`; không được suy pose của camera/vật từ một capture.

Một trường hợp lỗi: đổi một byte trong bản sao `color.mjpg` bị checksum reject; thiếu `depth.y16` bị từ chối; bản gốc không bị sửa. Khôi phục không có transaction xuyên FS/SQLite; làm việc với migration/backup phải thao tác riêng trên môi trường được phê duyệt. Test từng vùng nằm tại `tests/unit/raw/`, `tests/integration/metadata/`, `tests/contracts/camera/` sau R8.2.

## 4. Nghiệm thu, điều kiện chấp nhận, các điều không được nâng cấp

Hồ sơ [GD0 snapshot](../acceptance/GD0.md) tổng hợp mốc **80 PASS / 1 SKIP**, nhưng PRE-06 gốc chỉ ghi log đã quan sát **74 PASS / 1 SKIP** trước khi thêm 6 ca và xem **80 PASS / 1 SKIP** là *kỳ vọng* cho lượt Windows tiếp theo. DOC-04 chưa có receipt độc lập của lượt 80/1; không đánh dấu đó là kết quả vừa kiểm chứng. CTest **2/2**, native self-test, một capture thật + replay cùng các lỗi giả lập trên bản sao là bằng chứng operator-reported theo hồ sơ PRE-06. PR #3 merge là một mốc phát hành nguồn. [Ma trận GĐ0](../07-nghiem-thu/GD0_ACCEPTANCE.md) phân biệt cụ thể test đã báo cáo, skip privilege, vật lý và việc chưa thể kết luận. Không xem hiện diện code sau merge là bằng chứng hiệu chuẩn hình học hoặc cơ cấu chuyển động.

## 5. Bàn giao cho GĐ1/GĐ2

GĐ1 dùng RAW/SQLite và typed contracts để xây shell/Project/Viewer. Viewer R5.3 nhận **PLY/OBJ từ bên ngoài**, không nối RAW thành mesh. GĐ2 dự kiến xử lý replay/unprojection và metric single-view, phải kiểm intrinsics, unit/frame, pose, provenance trước khi có số đo.

`task_id`: [GD0-PRE06](../05-quan-ly/TASK_REGISTER.md). [State hiện hành](../05-quan-ly/TRANG_THAI_DU_AN.md) nêu scope/giới hạn; không sao chép status mỗi phiên vào hồ sơ này. Lịch sử chi tiết ở [nhật ký GĐ0](../history/GD0/GD0_EXECUTION_JOURNAL.md).

## 6. Giới hạn đã biết

DOC-04 không mở lại thiết bị hoặc evidence PRE-06 ở máy Windows; người biên tập chỉ đối chiếu hồ sơ Git + nguồn operator. Với thiếu receipt gốc trong phiên này, mọi tuyên bố `PASS` chỉ ở phạm vi operator-reported PRE-06, không chứng nhận phép đo mới; các phép kiểm định metric và rig là `NOT_TESTED` theo phạm vi GĐ0.
