# GD2-09 — EXECUTION PLAN / ROADMAP (Approved scope, implementation pending)

- Ngày chốt: **29/10/2026**.
- Baseline source: `main@c890b0bee1a43546e0aa0e76484efeb050c86334`.
- Thiết kế UI reuse: `GD2_09_00_UI_AUDIT_LOCK.md` (SOURCE_AUDIT_COMPLETE; Windows visual NOT_RUN).
- Canonical scope: `GD2_RAW_REPLAY_SINGLE_VIEW_GEOMETRY.md`, `HOP_DONG_GD2_LIVE_OBJECT_V1.md` và ma trận nghiệm thu GĐ2–GĐ3–MVP-B.
- **GĐ2-09 là phiên 09**, còn 09.00 là design gate được hoàn thành trước khi thực thi. 09.01–09.09 phát triển theo thứ tự; không áp dụng payload theo từng bước.

## Outcome và ranh giới

**Outcome:** Desktop phát lại RAW v2 (đúng byte/hash), decode JPEG/Y16 độc lập, live preview Gemini 2 có kiểm soát, bbox depth gợi ý + manual ROI, capture keyframe RAW vào Project/ScanSession đã tồn tại, SQLite/numbered registry và replay lại, shutdown/retry an toàn.

**Ngoài phạm vi:** XYZRGB/metric 3D (09 không làm; phiên 10), segmentation point cloud (11), normals (12), ProcessingRun hình học/export (13), pose/fusion/mesh (GĐ3/MVP-B). BBox 2D != mask object != 6DoF pose. Không sửa GĐ1 Viewer hoặc mở UI thứ năm. Không AI bắt buộc.

## Roadmap / đầu ra / nghiệm thu từng bước

| Bước | Phụ thuộc | Tác vụ phát triển trong VS Code | Đầu ra mã nguồn / kiểm thử nhỏ | Step PASS khi |
|---|---|---|---|---|
| 09.00 | GĐ1 CLOSED | Source UI inventory, ownership/reuse/gap map | `GD2_09_00_UI_AUDIT_LOCK.md` | SOURCE_AUDIT_COMPLETE / UI_REUSE_MAP_LOCKED; Windows actual UI còn pending |
| **09.01** | 09.00 | Architecture, capture context, typed DTO/ports, module boundary | `modules/capture/*` skeleton + `tests/unit/capture/test_gd2_09_01_contracts.py` | Import/DTO validation/AST architecture PASS, không giả camera/DB được bật |
| **09.02** | 09.01 | Replay theo immutable capture ID từ metadata, phân biệt layout thường và numbered, verify RAW `COMMITTED`/SHA | `application/replay.py`, `infrastructure/raw_reader.py`, tests RAW corruption/ID | Đọc đúng, detect corruption, không sửa RAW, không đọc arbitrary path ngoài root |
| **09.03** | 09.02 | Decode MJPEG RGB (đúng RGB order) và Y16 LE theo per-stream dimensions; preview depth diagnostic | decoder adapter/service, synthetic JPEG/Y16 tests | Shape/dtype/encoding đúng, không resize/align RAW, unsupported input reject |
| **09.04** | 09.03 | Gắn **child panel** vào `workspace_capture`, hiển thị RGB/Depth & source metadata; giữ UI objectName | Capture view, preview widget, Qt offscreen tests | Không tạo workspace/dock, startup không đọc SDK/SQLite, resize/nav OK |
| **09.05** | 09.04 | Worker/adapter nhận RGB-D liên tục qua `OrbbecCameraSource` lazy native, owned copies | native camera adapter + fake camera worker tests | Không block Qt, buffers owned, queue bounded; device manual pending |
| **09.06** | 09.05 | Lifecycle `IDLE/OPENING/STREAMING/CAPTURING/STOPPING/CLOSED/FAILED` + timeout, stop/reopen | lifecycle service/worker tests | transitions hợp lệ, không double-open/worker leak; hardware pending |
| **09.07** | 09.06 | Depth-based bbox candidate, jitter/hysteresis/low-confidence, manual ROI | bbox/ROI application + overlay, unit/UI tests | BBox trong ảnh, thay đổi hợp lý mẫu thử, fallback hoạt động; không suy pose |
| **09.08** | 09.07 | Capture keyframe riêng preview (không lấy nhầm stale), persist immutable RAW + SQLite qua registry, recovery | `capture_service` / storage adapter, temp+hash+DB tests | ID đúng, numbered reservation đúng, recovery khi DB fail, RAW không ghi đè |
| **09.09** | 09.08 | HMI actions + Project context handoff, shutdown, errors, integration/physical acceptance | controller wiring, integration + manual receipts | G2-09-A/B/C và ARCH/DATA/LIFE/REG gates PASS |

Từng bước: code review → test nhỏ → stage chính xác → commit SHA → ledger update. **Không commit code/expected test của bước sau**. Không push/PR `main` trước hoàn tất MVP-B.

## UI ownership / mức sửa GĐ1

| Trách nhiệm | Repo path | Quyết định |
|---|---|---|
| Capture module mới | `src/scantopath/modules/capture/` | **NEW**: 4 layers `domain/application/infrastructure/presentation`; skeleton chỉ được sinh đầu phiên |
| Qt shell + 4-workspace host | `src/scantopath/ui/shell/main_window.py`, `src/scantopath/ui/workspaces/pages.py` | **EXTEND_MINIMAL vào 09.04/09.09**; không thay MainWindow/page objectName hay navigation semantics |
| Project Explorer/selection | `ui/components/project_explorer.py`, Project controller/reading | **KEEP**, context verified explicit; không làm lại cây Project; `main_window._navigate` đang clear selection nên handoff snapshot phải đúng |
| Property Inspector | `ui/components/property_inspector.py` | **EXTEND_ONLY_IF_NEEDED**; metadata verified, không camera console |
| Task events/progress | `ui/tasks/controller.py`, `ui/components/task_event_panel.py` | **REUSE_EXISTING**; không nhân đôi Task Manager/UI log |
| Project dashboard/Processing workspace | `modules/project_workspace/presentation/dashboard.py`, `processing_workspace.py` | **KEEP**, no duplicate Capture list / ProcessingRun history |
| Viewer 3D & Render Host | `modules/viewer3d/`, `ui/shell/viewer_bootstrap.py` | **UNTOUCHED** |
| Native SDK/GĐ0 RAW/metadata | `acquisition`, `storage/session_store.py`, `storage/numbered_ops`, `metadata`, `cpp` | **REUSE_API_FIRST**; mọi thay đổi contract/hệ thống cần blocker & review độc lập |
| GĐ1 HMI QSS | `ui/theme/hmi_panel.qss` | KEEP/theme extension only if needed; không redesign |

**Cấm:** `CaptureInspectionController` nhận live SDK, UI gọi SQL/file trực tiếp, `SessionStore.commit_raw` thay cho numbered reservation, đọc native SDK khi import UI, giả pose/metric hoặc `ProcessingRun` thành công.

## Gate nghiệm thu cuối phiên

| Gate | Bằng chứng PASS bắt buộc |
|---|---|
| **G2-09-A** | RAW v2 manifest/SHA/size + replay RGB/Depth correctly; corrupt rejected; source bytes before/after unchanged; fixture + at least one real RAW |
| **G2-09-B** | Windows + Gemini2 thật open/preview/capture/stop/reopen/close, active worker lifecycle, app responsive; log/video, firmware/profile |
| **G2-09-C** | Bbox theo vật mẫu trong điều kiện thử có khai báo, manual ROI fallback & metadata, không tự khẳng định segmentation/pose |
| **ARCH-09** | `scripts/check_architecture_boundaries.py` + import graph + SRP/ISP/DIP review; không nới gate GĐ1 |
| **DATA-09** | Immutable RAW/metadata + proper numbered reservation & registered identity; failure recoverable |
| **LIFE-09** | Timeout, cancel, reconnect/disconnect/shutdown & failed states; no abandoned active capture worker |
| **REG-09** | Related GĐ1 UI tests, Project/Storage tests, Qt widget state regression; physical device test riêng |

Các gate trên mặc định **NOT_TESTED**; không tự nhận PASS chỉ vì skeleton test đạt. Gate 09.00 là source/design gate riêng (Windows visual verification chờ 09.04/09.09).

## Runtime failure/security constraints

- C++ binding `read_next()` có timeout bounded; Worker cannot block Qt event loop. Khi stop: không đóng camera ở thread khác đồng thời với blocking SDK read nếu lifetime không bảo đảm.
- MJPEG 1920x1080 và Y16 1280x800 là profile đã có ở native; không suy chung grid.
- Source RAW v2 uses `depth_scale_m_per_unit` and `coordinate_frame=depth_optical`, pose unknown; 09 không tạo point cloud.
- V1 RAW đường tương thích riêng, không giả v2/provenance.
- Numbered Storage: `reserve_capture` → `write_reserved_capture` → `register_reserved_capture`; lỗi DB sau ghi giữ recoverable RAW, không xóa.
- Capture chỉ khi operator chọn Session hợp lệ; khi đổi Project store hoặc close session phải invalidate context.
- UI không tự mở device/SQLite, không tạo card/tác vụ giả; smoke test Qt trên Windows với `QT_QPA_PLATFORM=offscreen`, physical HMI riêng.

## Workflow đã khóa

1. Chạy pack bootstrap **một lần**, chỉ sinh skeleton 09.01 và tài liệu cho cả phiên.
2. Mở VS Code sửa/hoàn thiện **09.01** (không chạy scripts apply từng bước).
3. Test nhỏ + AST gate; commit/đẩy checkpoint nếu muốn.
4. Tới 09.02–09.09: code mới theo roadmap, test nhỏ, commit, ledger; không chạy Full Regression liên tục.
5. Cuối 09.09: acceptance/regression liên quan + manual Windows/Gemini 2; chỉ khi gate đạt mới chốt 09 DONE.
6. Vẫn giữ một branch dài hạn tới MVP-B; **PR main chỉ khi hoàn tất MVP-B**, không phải khi xong 09.
