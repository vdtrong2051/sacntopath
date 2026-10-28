# Kiến trúc hệ thống ScanToPath — phiên bản đang triển khai

> `owner: ARCHITECTURE_OWNER` · `as_of_commit: 7a0df7c5b596ff8750bf91f47310067c53a8b204` · `verified_at: 2026-10-28`  
> `scope: Desktop GĐ0/GĐ1; kiến trúc code thực, không phải dự báo GĐ2–GĐ5` · `evidence_level: SOURCE_REVIEW`  
> **Nguồn chuẩn:** tài liệu này sở hữu sơ đồ và ranh giới kiến trúc; các trang module DOC-03B sẽ làm rõ chi tiết tính năng. Bằng chứng lịch sử R4/R5 giải thích lý do lựa chọn, không thay mô tả vận hành hiện tại.

## 1. Vấn đề kiến trúc cần giải quyết

ScanToPath phải phục vụ tương tác Qt, lưu dữ liệu RAW bền vững, giao tiếp cảm biến qua SDK native và hiển thị hình học 3D tốn tài nguyên. Các hoạt động có đặc tính vòng đời khác nhau: Qt xử lý event loop; SQLite có giao dịch; RAW trên filesystem; native C++ có thể lỗi độc lập; renderer VTK có state scene/actor và frame liên tiếp. Nếu gộp mọi việc vào một QWidget hoặc để VTK/SDK chặn main thread, hệ thống khó kiểm soát đóng cửa sổ, lỗi process, dữ liệu không còn hợp lệ và khả năng bảo trì.

Thiết kế hiện hành là **modular monolith ở mức source**, tổ chức theo ranh giới chức năng và bốn tầng `domain`–`application`–`infrastructure`–`presentation` tại nơi có triển khai. *Monolith* ở đây không đồng nghĩa một tiến trình: Render Host VTK được tách process để bảo vệ UI. Định hướng là các module có trách nhiệm rõ; tài liệu không tuyên bố toàn code đã đạt mọi nguyên tắc SOLID.

### Mục tiêu phi chức năng

| Mục tiêu | Cách đạt trong code | Giới hạn |
|---|---|---|
| Qt không đơ khi IO/render | Qt shell, async services, Render Host riêng | Chưa có benchmark input-to-physical-present toàn diện |
| RAW không bị biến đổi khi chỉ xem | `SessionStore`, manifest và read verification | Không atomic transaction xuyên SQLite/filesystem |
| Truy vết hình học ngoài | SHA-256 source, scene/input/frame revisions | Không xác nhận unit/metric của file ngoài |
| Thay đổi module ít ảnh hưởng | Ports/DTO, service layer, boundary tests | Cần regression mỗi lần đổi contract |
| Giữ an toàn khi process render mất | IPC, deadline, retry, lifecycle | Lỗi C++ fault-injection thực vẫn chưa nghiệm thu tổng thể |

## 2. Sơ đồ ngữ cảnh — những tiến trình thực sự có

```text
Người dùng Windows
    │ click / keyboard
    ▼
┌────────────────────── QT/PYTHON PROCESS ───────────────────────┐
│ ScanToPathMainWindow (Qt shell)                                │
│  ├── ProjectWorkspaceController → application services        │
│  │                                 └── metadata/SQLite        │
│  │                                       └── RAW filesystem    │
│  └── Viewer presentation / InteractiveViewer3DController      │
│        └── CoalescingRenderSession (futures, timeout, queue)   │
└──────────────────────────┬────────────────────────────────────┘
                     IPC / source SHA / scene revision
                           │
                           ▼
          ┌────── VTK RENDER HOST — tiến trình con ─────┐
          │ PLY/OBJ reader → VTK scene/actor/camera/pick │
          │ RGB24 frame slots + explicit frame ACK       │
          └──────────────────────┬───────────────────────┘
                         RGB shared memory → Qt copy/ACK

Gemini 2 ── OrbbecSDK/C++20 ── pybind11 ── acquisition adapter
                                                └─ SessionStore RAW + metadata
```

**Hai nhánh lưu RAW và Viewer nhập PLY/OBJ độc lập ở GĐ1.** Chưa có tác vụ trong ứng dụng kết nối RAW→point cloud→mesh. Mọi sơ đồ nối hai nhánh thông qua Open3D hiện chỉ là kiến trúc tương lai, không được vẽ vào sơ đồ thực thi ở trên.

## 3. Sở hữu layer và phụ thuộc

| Layer / module | Trách nhiệm và điểm vào | Không được làm |
|---|---|---|
| `ui/shell` | Composition root, dock, navigation, lắp controller | Không tự query SQLite hoặc tính toán VTK nặng |
| `project_workspace/presentation` | Qt state, form, workflows, command dispatch | Không viết SQL trong event handlers |
| `project_workspace/application` | `ProjectWorkspaceService`, command/query/inspection contracts | Không sở hữu QWidget; không tạo dữ liệu giả khi load |
| `project_workspace/infrastructure` | `sqlite_backend`, xác minh root và adapter metadata | Không ngầm migrate kho thật |
| `metadata` | SQLite schema, repositories, transaction & audit | Không ghi MJPEG/Y16 trực tiếp vào DB |
| `storage` | RAW v1/v2, manifest, numbered registry, migration opt-in | Không tự resize/align/transform ảnh |
| `acquisition` + `cpp` | Gemini 2 SDK, RAW capture packet và binding | Không biến timestamp thành pose hoặc metric accuracy |
| `viewer3d/application` | `SceneSource`, `SceneDescriptor`, navigation/picking DTO | Không import Qt/native VTK |
| `viewer3d/presentation` | UI Viewer, Inspector event, lệnh async | Không tự tạo actor VTK trong Qt process |
| `viewer3d/infrastructure` | Reader, native render, IPC/shared memory host | Không tạo `Capture`/`ProcessingRun` trong SQLite |

Ví dụ về phụ thuộc đúng: Qt chuyển một thao tác mở Project cho `ProjectWorkspaceService`, service quyết định truy vấn qua backend; khi mở file 3D, Qt chuyển `SceneSource` tới Render Host, chỉ nhận kết quả mô tả và frame. *Data Transfer Object (DTO)* giúp tầng giao diện không cần thao tác trực tiếp actor VTK.

## 4. Bản đồ file — bắt đầu sửa ở đâu?

```text
src/scantopath/
├── ui/main.py                         # QApplication và mở main window
├── ui/shell/main_window.py            # composition root, 4 workspaces
├── ui/shell/viewer_bootstrap.py       # real Viewer hoặc fallback
├── ui/shell/viewer_inspector_bridge.py# Inspector nguồn hình học
├── modules/project_workspace/
│   ├── presentation/controller.py     # Qt façade
│   ├── application/service.py         # API Project ổn định
│   └── infrastructure/sqlite_backend.py
├── modules/viewer3d/
│   ├── application/scene_contracts.py # SceneSource / Descriptor / SelectionRef
│   ├── presentation/live_controller.py
│   ├── presentation/interactive_controller.py
│   └── infrastructure/
│       ├── scene_reader.py            # PLY/OBJ
│       └── resident_poc/              # host/client/protocol/async_session
├── metadata/store.py + metadata/repos/
├── storage/session_store.py + numbered_ops/
└── acquisition/native.py + orbbec_adapter.py
cpp/CMakeLists.txt                     # C++20, 2 CTest smoke
```

R8.2 đã phân nhóm test ở `tests/unit`, `integration`, `contracts`, `ui`, `native`, `performance`. Tìm bài liên quan theo tên module; tránh dùng đường dẫn test phẳng `tests/test_*.py` trong tài liệu mới.

## 5. Luồng A — nhận và lưu RAW (có code, kích hoạt theo lệnh)

1. Người vận hành gọi one-shot Gemini 2 với session/specimen ID hợp lệ. Không có bước camera tự chạy khi mở Qt.
2. `acquisition.orbbec_adapter.capture_one_raw` sử dụng binding C++/SDK để lấy dữ liệu và metadata nguồn; payload MJPEG/Y16 có buffer riêng.
3. `RawRgbdCaptureMetadataV2` xác thực encoding, kích thước, byte length, intrinsic per stream, timestamp và depth scale.
4. `SessionStore.commit_raw()` ghi `color.mjpg`, `depth.y16`, `metadata.json`, `manifest.json`, `COMMITTED` qua `.partial` rồi rename trong filesystem.
5. `SessionStore.read_raw()` xác minh schema/hash và khôi phục payload; đăng ký Capture vào SQLite là hành động tường minh khác.

**Lỗi quan trọng:** thiếu file, sửa byte, sai checksum hoặc giá trị schema bất hợp lệ phải bị từ chối. Đổi tên thư mục trong cùng filesystem **không** tạo một transaction chung với SQLite và không chứng minh bền vững trước mọi sự cố mất nguồn. Quy trình bảo toàn chi tiết sẽ nằm ở DOC-03B `RAW_STORAGE.md`.

## 6. Luồng B — quản lý Project/SQLite (có code)

```text
Người dùng chọn kho dữ liệu
    → Qt Project controller
    → ProjectWorkspaceService (root được probe xác thực)
    → metadata/repositories + numbered registry khi phù hợp
    → Project / Specimen / Session / Capture / ProcessingRun / Audit
```

`MetadataStore` có schema v1/v2; khi mở một database có bảng nhưng không có version, nó từ chối việc “nhận quản lý” và migrate ngầm. Numbered Storage v2 là một layout/registry khác với **schema version** của RAW packet. `ProcessingRun` chứa stage/algorithm/input ids và trạng thái nhưng không tự thực thi một thuật toán hình học. Khi mở UI, không tự tạo Project hay đọc camera.

**Lỗi và phục hồi:** root không hợp lệ, thiếu bảng, version không hỗ trợ hoặc RAW metadata sai phải trả lỗi có ngữ nghĩa; không chữa bằng `create_all`/rename thủ công vào dữ liệu thật. Các thao tác migration phải được gọi tường minh, sao lưu và kiểm thử riêng.

## 7. Luồng C — mở tệp PLY/OBJ, render và picking (có code)

1. Người dùng vào **Kiểm tra 3D**. `main_window._ensure_viewer3d` tạo controller theo nhu cầu. `viewer_bootstrap.create_viewer_controller` chọn fallback Qt `offscreen/minimal` hoặc `InteractiveViewer3DController` + `CoalescingRenderSession` cho màn hình thật.
2. Người dùng chọn PLY/OBJ. Controller gửi nguồn tới Render Host; `scene_reader` đọc và validate scene, trả `SceneDescriptor` có format/kind/count/bounds/`source_sha256`.
3. Host dựng actor, trả RGB frame qua shared memory; Qt **copy RGB trước ACK** để host không ghi đè buffer còn được giao diện đọc. Event/revision giúp từ chối frame cũ khi chuyển scene hoặc camera.
4. Orbit/pan/zoom được chuyển thành các yêu cầu có revision. Picker nhận tọa độ 2D và version scene/frame; trả `SceneSelectionRef` cho điểm/mặt và Inspector. Kết quả mặt là **giao điểm trên mặt**, không đồng nghĩa tọa độ một vertex CAD.
5. Khi đổi source, mất host hoặc đóng app, controller hủy/clear selection cũ, yêu cầu host shutdown/dispose có giới hạn; Qt không dùng actor đã giải phóng.

**Lỗi và phục hồi:** input quá lớn/bị sửa/hỏng, timeout, child crash, stale frame hoặc stale selection phải bị từ chối/hồi phục có kiểm soát. Không suy từ test host termination rằng đã thử native C++ fault injection khi thật sự bận.

## 8. Concurrency, tài nguyên và vòng đời

- **Qt event loop:** chỉ quản lý widget, trạng thái và sự kiện; không gọi VTK native bên trong Qt shell.
- **Python application/worker:** IO, thao tác Project hoặc điều phối được tách theo contract; có trạng thái busy/error/cancel và shutdown.
- **Render Host:** process con sở hữu VTK scene và shared RGB frame; `CoalescingRenderSession` gộp camera request để tránh queue tăng vô hạn. `scene_revision`, `frame_revision`, `input_revision` bảo vệ thứ tự dữ liệu.
- **IPC/ACK:** frame chỉ được giải phóng/tái sử dụng sau ACK, vì copy data chưa xong sẽ có nguy cơ ảnh rách hoặc dữ liệu sai vòng đời.
- **SQLite & RAW:** mỗi hệ có atomicity riêng; cần phục hồi bằng kiểm tra tương ứng, không giả định một transaction toàn hệ thống.

**Trạng thái kiểm thử thực địa: `NOT_TESTED` hoặc `PENDING_MANUAL` đối với các cổng chưa có bằng chứng phù hợp.**

**Các phép đo còn mở:** DPI 100/125/150, reopen/close Qt thực, native C++ busy/fault, GPU/VRAM và input-to-display-present latency. Benchmark 1K/100K/1M là completed renderer workload, không phải FPS màn hình.

## 9. Ranh giới dự kiến — chưa là code GĐ1

GĐ2 sẽ cần replay RAW→depth unprojection và ROI/filter/export có provenance; GĐ3 thêm metric validation/pose registration/fusion/coverage; GĐ4 feature và digital replica; GĐ5 hướng dẫn thu nhận/AI tùy chọn. **Không** đưa module planned này vào dependency graph hiện tại. Việc chọn camera cố định hay cầm tay và chuyển động bàn quay cần một quyết định cấu hình vật lý có version ngoài lời mô tả lịch sử.

## 10. Quyết định, kiểm thử và giới hạn

Render Host tách process được chọn **có điều kiện** tại R4.5 sau đối chiếu nhúng/tách; nguyên tắc UI-first có ADR-001. Thử tự động: `scripts/verify.ps1 -Profile Quick|Full|Acceptance`; source contract/test nằm trong `tests/contracts/`, Qt trong `tests/ui/`, renderer/native trong `tests/native/`. Evidence theo lần chạy lưu **ngoài repository**.

**Không dùng `Acceptance` auto PASS làm HMI overall PASS**; nguồn lịch sử [R6](../acceptance/GD1_R6_ACCEPTANCE_STATUS.md) vẫn giữ các cổng cần đo. Sơ đồ và luồng trên được đối chiếu với source tại commit đầu tài liệu; các hành vi runtime Windows cần người vận hành xác minh mới có thể ghi `MANUAL_PASS`.

Đọc sâu [Hợp đồng dữ liệu và hệ tọa độ](DU_LIEU_VA_HE_TOA_DO.md) và [Công nghệ và phụ thuộc](CONG_NGHE_VA_PHU_THUOC.md). Hồ sơ nguyên thủy [R4.5](../archive/GD1/R1-R5/R4_05_RENDERER_ARCHITECTURE_DECISION.md) được giữ làm quyết định lịch sử, không phải trang kiến trúc runtime thứ hai.
