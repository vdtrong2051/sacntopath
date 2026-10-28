# Viewer 3D — Kiểm tra hình học PLY/OBJ bằng Render Host cô lập

> **owner:** `modules/viewer3d` và `ui/shell/viewer_bootstrap` · **as_of_commit:** `0557c0d4fed9a3df3b180fc9872c6d3293b5f0d5` · **verified_at:** 2026-10-28  
> **scope:** Viewer live R5.3, đọc file PLY/OBJ, điều hướng, picking, Inspector, IPC/ACK · **implementation:** IMPLEMENTED; **manual HMI, GPU/VRAM, native fault injection:** NOT_TESTED mới ở DOC-03B; R6 overall PENDING.  
> **source-of-truth:** `src/scantopath/modules/viewer3d/`, `src/scantopath/ui/shell/` và các test UI/native. Không mô tả Viewer như pipeline scan-to-path.

## 1. Mục đích và trường hợp sử dụng

Viewer kiểm tra **một tệp hình học 3D đã tồn tại**: point cloud trong PLY, mesh PLY hoặc mesh OBJ. Người dùng có thể quay góc nhìn, pan/zoom/fit, bật/tắt lớp và lưới tham chiếu, chọn điểm hoặc mặt và đọc thuộc tính. Ví dụ: mở PLY đã xuất từ phần mềm khác để kiểm số đỉnh, bounding box, vị trí phần tử được chọn. Nó không kết nối Camera Gemini 2 để tự tạo point cloud, không chạy reconstruction hay xuất Zigzag/Contour.

Vấn đề khó nhất của Viewer là vòng đời native VTK/OpenGL: nếu đặt render nặng cùng tiến trình/luồng Qt dễ gây treo hoặc lỗi native kéo cả cửa sổ đi theo. Kiến trúc R4.5 chọn Render Host ở **tiến trình con riêng**, truyền lệnh qua IPC và ảnh RGB qua shared memory. Lựa chọn này được dùng trong R5.3 nhưng không tự chứng minh có thể sống sót mọi loại crash C++.

## 2. Phạm vi chạy được và chưa có

| Năng lực | Thực tế | Giới hạn |
|---|---|---|
| Mở PLY point-only | Có | không tạo face giả |
| Mở PLY có faces / OBJ | Có | không import material/texture phức tạp tùy ý |
| Orbit, pan, zoom, reset/fit | Có qua session/host | không reload source mỗi thao tác |
| Pick điểm/mặt | Có `vtkPointPicker`/`vtkCellPicker` trên host | face hit là điểm giao trên mặt, không phải đỉnh CAD |
| Grid XY, orientation marker, layer visibility | Có ở host và Qt tools | lưới/gizmo không chứng minh datum/world frame |
| Native live + lost-host recovery + PNG fallback | Có đường triển khai | offscreen fallback khác native live |
| RAW → point cloud/mesh/Zigzag | **Chưa có trong Viewer GĐ1** | nguồn mở chỉ là file ngoài đã tồn tại |
| Metrology/FPS màn hình/VRAM | **Chưa nghiệm thu đầy đủ** | benchmark renderer completion ≠ display-present |

## 3. Source map và luồng phụ thuộc

```text
QMainWindow._ensure_viewer3d()
    → viewer_bootstrap.create_viewer_controller()
         ├─ offscreen/minimal: Viewer3DController (PNG fixture fallback)
         └─ normal: InteractiveViewer3DController
                 └─ LiveViewer3DController (Qt presentation)
                       └─ CoalescingRenderSession (thread + bounded queues)
                             └─ ResidentRenderClient (IPC + shared memory)
                                  └─ host.py: PersistentScene (VTK/OpenGL child)
                                       └─ scene_reader.load_scene(PLY/OBJ)
```

| Đường dẫn `src/scantopath/...` | Vai trò |
|---|---|
| `ui/shell/viewer_bootstrap.py` | lắp ráp live/fallback và Inspector bridge |
| `modules/viewer3d/application/scene_contracts.py` | `SceneSource`, `SceneDescriptor`, `SceneSelectionRef`, validation nguồn |
| `modules/viewer3d/application/navigation.py`, `picking.py` | trạng thái camera/tương tác trung lập UI |
| `modules/viewer3d/presentation/live_controller.py` | lifecycle loading/ready/retry/dispose, frame nhận ở Qt |
| `modules/viewer3d/presentation/interactive_controller.py` | toolbar, mouse, pick point/face, grid/layer, Inspector event |
| `modules/viewer3d/presentation/live_tools.py` | bộ công cụ SVG/shortcut |
| `modules/viewer3d/infrastructure/scene_reader.py` | đọc file ngoài và tính SHA/bounds/point/face |
| `modules/viewer3d/infrastructure/resident_poc/protocol.py` | xác minh JSON lệnh và version/revision |
| `modules/viewer3d/infrastructure/resident_poc/async_session.py` | coalescing camera, Future, copy RGB/ACK |
| `modules/viewer3d/infrastructure/resident_poc/client.py` | quản lý child process/pipe/shared memory |
| `modules/viewer3d/infrastructure/resident_poc/host.py` | actor/renderer/grid/picking, hai slot frame |

**Ranh giới không được vượt:** Qt presentation không trực tiếp nạp VTK C++/Python native vào tiến trình UI; Render Host không truy cập SQLite hoặc viết RAW.

## 4. Hợp đồng dữ liệu và giới hạn an toàn

| Đối tượng/trường | Kiểu và ý nghĩa | Validation/bất biến |
|---|---|---|
| `SceneSource(path, expected_sha256)` | định danh file nguồn và hash kỳ vọng tùy chọn | string path hữu hạn, SHA hex đúng 64 ký tự |
| `SceneDescriptor` | tên, SHA, số byte, định dạng, geometry kind, counts, bounds, RGB | `units='unknown'`, `coordinate_frame='unknown'` |
| `SceneSelectionRef` | SHA, `scene_revision`, kind (`point`/`face`), element ID, XYZ | revision ≥1, ID ≥0, XYZ hữu hạn; không tự gán đơn vị |
| `MAX_SOURCE_BYTES` | 256 MiB (source validator) | vượt giới hạn → từ chối |
| `MAX_VERTICES` | 1.500.000 đỉnh | vượt giới hạn → từ chối |
| `MAX_FACES` | 3.000.000 mặt | vượt giới hạn → từ chối |
| frame shared RGB24 | width×height×3 byte/slot | Qt **copy** byte trước khi trả ACK |
| `scene_revision` / `frame_revision` | số phiên cảnh và frame | reply cũ không được áp vào cảnh/Inspector mới |
| `u, v` của pick | tỷ lệ normalized [0,1] | host kiểm tính hợp lệ trước khi pick |

**PLY point-only ≠ mesh:** không tạo faces để hợp thức hóa shape. OBJ yêu cầu có face; `scene_reader.py` không tự tải vật liệu/đường dẫn texture không kiểm soát. SHA nhận diện tệp ngoài, **không** biến dữ liệu thành capture measured. `SceneDescriptor` không nhận các đơn vị hoặc coordinate frame chưa xác minh từ file ngoài.

## 5. Luồng mở file và hiển thị từ đầu tới cuối

1. Người dùng vào workspace **Kiểm tra 3D**; shell tạo controller lazy. Trên Qt màn hình thật, controller live chưa nhất thiết khởi child cho tới khi được kích hoạt; `CoalescingRenderSession` sở hữu startup asynchronous.
2. Chọn PLY/OBJ: `LiveViewer3DController.load_ply(...)` / scene load path chuyển thành `SceneSource`, khóa context source, xóa lựa chọn/frame cũ; thread gọi `ResidentRenderClient.start()` nếu cần.
3. `scene_reader.load_scene()` preflight file, kiểm giới hạn, định dạng, hash và đọc hình học; VTK tạo actor/cache trong **host process**. SceneDescriptor quay về Qt qua JSON/async Future.
4. Host render vào RGB shared-memory slot; client sao chép thành owned `bytes`, xác nhận `ack_frame(scene_revision, frame_revision, slot)`, rồi Qt dựng QImage/preview từ bản sao. **Không giữ pointer sang slot shared memory sau ACK.**
5. `_poll_live()` / `_drain_newest_frame()` chỉ nhận frame hợp lệ, mới nhất, khớp scene và revision; frame cũ/mất nguồn không cập nhật UI. `frames_presented_to_qt` đếm frame tới Qt, **không** là FPS thật màn hình.
6. Thanh công cụ gửi thay đổi camera bằng `CoalescingRenderSession.camera()`; các lệnh cập nhật camera nhanh được gộp thành trạng thái đích, không tạo một lần reload PLY cho mỗi pixel chuột.

## 6. Luồng chọn điểm/mặt (picking) và Inspector

```text
click tại preview → mode='select' và frame ready?
    → (u,v) chuẩn hóa [0,1] + scene_revision + frame_revision
    → async_session.pick() → host.pick()
    → vtkPointPicker (point-cloud) / vtkCellPicker (mesh)
    → SceneSelectionRef(SHA, revision, point/face ID, XYZ)
    → interactive_controller._emit_scene() → SceneInspectorBridge
    → PropertyInspector, tùy chọn sao chép XYZ
```

Các chốt quan trọng: ở chế độ orbit/pan không emit pick; chưa có frame được ACK thì tool bị vô hiệu; khi đổi source/layer hoặc child mất thì `SceneSelectionRef` cũ bị hủy. Nếu nhấp vào mặt, XYZ là **tọa độ giao điểm trên mặt**, không phải vertex ID và không suy ra dung sai CAD. Nút sao chép XYZ giữ giá trị số nội bộ có độ chính xác hợp lý, nhưng hiển thị rõ `units=unknown`.

## 7. Vòng đời, hủy và quản lý tiến trình

```text
IDLE → STARTING → LOADING → READY
  \        \        \       ├─ camera/layer/grid/pick → READY
   \        \        \      ├─ change source → STOPPING → STARTING
    \        \        \     └─ error/lost host → FAILED → retry/fallback
     └─────────── close/request shutdown → CLOSING → DISPOSED
```

`LiveViewer3DController.begin_shutdown()` là chốt không chặn của `QMainWindow.closeEvent`; `dispose()` phải giải phóng session/child/shared memory khi đủ điều kiện. `CoalescingRenderSession.stop(timeout=...)` có timeout và đường abort, host có `close_scene`/`shutdown`. Một child process bị kill trong phép thử không chứng nhận kịch bản lỗi native C++ thật sự hoặc close khi native đang bận GPU.

Với frame: host chỉ tái sử dụng slot khi client đã copy/ACK; nếu ACK sai revision/slot phải từ chối. Với render: revision nguồn và frame ngăn kết quả cũ tranh ghi Inspector. Với Qt: signal/future từ worker không được cập nhật QWidget sau khi window bị hủy.

## 8. Lỗi, kết quả và phục hồi

| Lỗi/điều kiện | Rào chắn | Hành động người dùng/developer | Regression |
|---|---|---|---|
| File không đúng định dạng, quá lớn, đổi SHA | `scene_reader` + `SceneDescriptor` | hiển thị lỗi, không nạp actor; chọn file hợp lệ | `tests/native/viewer/test_gd1_r5_1_scene_geometry.py` |
| OBJ không có face, PLY malformed | kiểm source | từ chối; không chuyển dữ liệu giả thành mesh | `tests/integration/viewer/test_gd1_08_03_ply.py` |
| IPC JSON quá dài/sai field | `protocol.decode_request()` | từ chối request; không crash Qt | `tests/native/renderer/test_gd1_r4_3_transport_lifecycle.py` |
| Shared frame chưa copy/ACK, stale | revision/slot/frame guards | bỏ frame cũ, không hiển thị lẫn scene | renderer transport tests |
| Child process mất | `RenderHostError`, timeout, phase `FAILED` | clear selection, hiện Retry/fallback; không sửa dữ liệu gốc | `tests/ui/viewer/test_gd1_r5_2_live_viewer.py` |
| Pick khi chưa ready | `_ready_tools()` | disable pick, chờ frame hợp lệ | `tests/ui/viewer/test_gd1_r5_3_qt.py` |
| Native busy close, real GPU C++ fault | **Chưa có đủ nghiệm thu thực** | chạy gate HMI/native độc lập trước Final Freeze | 08.06.6: NOT_TESTED |

## 9. Ví dụ tái lập an toàn

Để chạy test hợp đồng dữ liệu và tương tác **không dùng tệp RAW thật/camera**:

```powershell
# Chạy tại gốc repo; .venv đã có pytest/PySide6, vtk theo optional extras.
$env:QT_QPA_PLATFORM = 'offscreen'
& .\.venv\Scripts\python.exe -X utf8 -m pytest -q `
  tests/native/viewer/test_gd1_r5_1_scene_geometry.py `
  tests/native/viewer/test_gd1_r5_3_geometry_interaction.py `
  tests/ui/viewer/test_gd1_r5_3_qt.py
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
```

Để kiểm live Viewer thực (không cần camera), cần Windows có VTK và màn hình/driver phù hợp; mở `python -m scantopath.ui.main`, chọn **Kiểm tra 3D**, chọn một PLY/OBJ *không chứa dữ liệu bí mật*. Kiểm chọn mặt/điểm, layer, grid và đóng lại. Đây là **thao tác HMI thủ công**, không có kết quả PASS nào được tạo trong tài liệu này. Lệnh `scripts/r5_3_native_probe.py --help` có thể kiểm option trước khi chạy probe; không tự bật benchmark trong quickstart.

## 10. Hiệu năng và phương pháp đo

R4.4 đã có benchmark A/B giữa embedded và resident renderer với dataset 1K/100K/1M. Chỉ số đo chủ yếu là **renderer workload hoàn thành**, không đo photon lên màn hình, nhịp quét vật lý hay VRAM đầy đủ. Không áp con số của một máy vào cấu hình GPU/driver khác. Performance có thể phụ thuộc có GPU thật, VTK backend, kích thước frame shared memory và logic coalescing. Để chứng minh HMI, phải có latency input→present, FPS thật, DPI và RAM+VRAM của *cả parent Qt lẫn child host*.

## 11. Mở rộng module an toàn

Thêm định dạng CAD/mesh: bắt đầu ở `scene_contracts` + `scene_reader` với hash, giới hạn nguồn và test dữ liệu hỏng; không sửa Qt shell để gọi VTK trực tiếp. Thêm công cụ pick: mở rộng protocol/`async_session`/host và DTO revision đồng thời, rồi mới nối toolbar. Thêm tương tác realtime: bảo toàn coalescing và ACK, kiểm host death/restart và đóng Qt. Nếu cần xử lý point-cloud từ RAW GĐ2, thiết kế một pipeline mới với provenance và units; Viewer chỉ nhận artifact đã được xác minh.

## 12. Kiểm thử tự động và thủ công

| Phạm vi | Test hoặc công cụ |
|---|---|
| Scene PLY/OBJ và bounds/SHA | `tests/native/viewer/test_gd1_r5_1_scene_geometry.py` |
| IPC/shared memory/transport | `tests/native/renderer/test_gd1_r4_3_transport_lifecycle.py` |
| Picking/geometry interaction | `tests/native/viewer/test_gd1_r5_3_geometry_interaction.py` |
| Qt viewer/live/retry | `tests/ui/viewer/test_gd1_r5_2_live_viewer.py`, `test_gd1_r5_3_qt.py` |
| Geometry navigation | `tests/integration/viewer/test_gd1_08_04_navigation.py` |
| A/B benchmark | `tests/performance/renderer/test_gd1_r4_4_benchmark.py` |
| Tổng hồi quy | `scripts/verify.ps1 -Profile Full` |

`Acceptance` của R8.4 có thể nhận `-RunNativeProbe -RunBenchmark` tường minh; ngay cả khi automated PASS, `overall=PENDING_MANUAL` cho đến khi có chứng cứ các ca HMI/native còn thiếu. Không sửa `docs/acceptance/GD1_R6_ACCEPTANCE_STATUS.md` chỉ vì viết lại tài liệu module.

## 13. Quyết định và giới hạn còn mở

R4.5 chọn giải pháp B (isolated resident VTK host) sau so sánh A/B, **có điều kiện**, không đồng nghĩa production certification. Thứ cần giữ bất biến khi mở rộng là source SHA, scene/frame revision, owned-frame-before-ACK, cleanup host, Qt main thread, phân biệt point/face và units chưa xác minh. **Chưa có** phép đo HMI DPI 100/125/150, input-to-present FPS thực, GPU/VRAM và fault-injection C++ được xác nhận đủ cho 08.06.6. Các quyết định cũ vẫn nằm ở archive để truy dấu nhưng hợp đồng vận hành hiện hành đã được giải thích trong trang này.
