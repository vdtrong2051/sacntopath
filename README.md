# ScanToPath 2026 — Engineering 3D Reconstruction Desktop

**GĐ1 hiện hành (R7, 27/10/2026):** [Tài liệu GĐ1 hiện hành](docs/INDEX.md) ghi kiến trúc Viewer/Project sau R5.3, lịch sử sửa lỗi, và ma trận R6. R6 tự động 14/14 PASS theo log người vận hành; R6 tổng thể vẫn PENDING. Các mục GĐ0 và kế hoạch bên dưới là mốc lịch sử theo thời điểm soạn README.

**Trạng thái:** GĐ0 (Software Skeleton + Gemini 2 RAW/metadata) đã merge vào `main` qua [PR #3](https://github.com/vdtrong2051/sacntopath/pull/3), commit `8bf33591389dcdff82f0fbd5bf5932a22547c984`. Sau GĐ0 phát triển theo **UI-first + vertical slices**, roadmap mới có đối chiếu và kho lưu bản cũ.

**Tài liệu bắt đầu:** [ROADMAP](docs/ROADMAP.md) · [ARCHITECTURE](docs/ARCHITECTURE.md) · [Công nghệ](docs/roadmap/TECHNOLOGY_SCOPE.md) · [Ánh xạ phiên cũ/mới](docs/roadmap/SESSION_CROSSWALK.md) · [ADR-001 UI-first](docs/decisions/ADR_001_UI_FIRST.md) · [Bản cũ](docs/roadmap/ROADMAP_V1_ARCHIVED.md).

## Mục tiêu

**Vật thể thật → RAW có nguồn gốc → hình học theo kích thước thật → chất lượng/độ tin cậy → đặc trưng và quan hệ → bản sao số kỹ thuật → dữ liệu phục vụ thiết kế ngược, kiểm tra hoặc chế tạo.** Về sau cho phép yêu cầu đo bổ sung theo nhiệm vụ. Không đồng nhất mesh đẹp với phép đo chuẩn, AI prediction với dữ liệu measured hoặc planned trajectory với pose thực.

## Đã hoàn thành (GĐ0)

- Gemini 2 **cầm tay** qua OrbbecSDK v2.10.6, C++20 và pybind11; raw color MJPEG và depth Y16 lưu độc lập, chưa align; timestamp, calibration và scale được giữ theo nguồn.
- `RawRgbdCaptureMetadataV2`, `SessionStore.commit_raw`/`read_raw`, manifest SHA-256, marker `COMMITTED`, hỗ trợ đọc dữ liệu v1 synthetic.
- Project/Specimen/ScanSession/Capture Registry/ProcessingRun và audit events trong SQLite/SQLAlchemy.
- Một shot thu nhận/ghi/đọc lại với Gemini 2 thật đã nghiệm thu trên Windows, lỗi checksum/thiếu tệp bị từ chối.
- Hồi quy PRE-06 Windows: **80 passed / 1 skipped** (symlink test bị giới hạn quyền), CTest **2/2**, native self-test exit **0**. Đây là bằng chứng GĐ0; **không** suy ra metric accuracy/pose/sync được kiểm chứng.
- PySide6 mới ở mức giao diện shell đơn giản, **chưa** có VTK viewer/3D import/workflow UI.

## Sắp triển khai

**GĐ1 (06–08):** Desktop UI Foundation → Project Workspace trên SQLite → VTK 3D Viewer. GĐ2 (09–13): RAW Replay → single-view cloud → tương tác/filter/export. Các giai đoạn sau mới metric validation, pose/multi-view registration, trust, feature/replica và AI-assisted handheld scanning.

**Không có** bàn quay, motor, encoder, Pi/ESP32, fixed world pose hay camera motion-control trong build đã nghiệm thu. Plan dẫn hướng bằng tay và object detection/tracking là mục tiêu tương lai.

## Windows developer checks

Tại thư mục gốc repo, dùng `.venv` Python 3.12 đã cài project:

```powershell
$pyExe = (Resolve-Path '.\.venv\Scripts\python.exe').Path
& $pyExe -m pytest -q -rs .\tests
ctest --test-dir .\build-orbbec -C Release --output-on-failure
$env:SCANTOPATH_ORBBEC_SDK_BIN = 'E:\1_BigProject\scantopath\_sdk\OrbbecSDK_v2.10.6\bin'
& $pyExe -u -X faulthandler -m scantopath.acquisition.native --self-test
```

CLI hiện có (không tự mở camera trừ `--once`):

```powershell
& $pyExe -m scantopath.metadata.cli list-projects
& $pyExe -m scantopath.metadata.cli tree --project project-001
& $pyExe -m scantopath.metadata.cli events --limit 20
# Khi có một Capture v2 đã lưu thật, đường dẫn phải trỏ vào đúng root:
# & $pyExe -m scantopath.acquisition.capture_once --verify '<CAPTURE_DIR>' --output '.\scantopath-data'
```

**Không commit** `.venv`, dữ liệu `scantopath-data`, log runtime, camera identifiers hoặc RAW thật lên repository công khai. Đường dẫn SDK ví dụ là của máy Windows đã thử, không portable.

## Hồ sơ và lịch sử

- [`docs/PRE_06_GD0_ACCEPTANCE.md`](docs/PRE_06_GD0_ACCEPTANCE.md) là hồ sơ được viết **trước lúc merge** (trạng thái pending/checkbox trong file giữ nguyên làm lịch sử); PR #3/commit nói trên xác nhận đã merge sau đó.
- [`docs/PRE_01_BASELINE.md`](docs/PRE_01_BASELINE.md) … [`docs/PRE_05_GD0_METADATA_PERSISTENCE.md`](docs/PRE_05_GD0_METADATA_PERSISTENCE.md) là hồ sơ các bước nền tảng.
- [`docs/roadmap/ROADMAP_V1_ARCHIVED.md`](docs/roadmap/ROADMAP_V1_ARCHIVED.md) giữ nguyên phiên bản roadmap lịch sử, không viết lại Git history.
