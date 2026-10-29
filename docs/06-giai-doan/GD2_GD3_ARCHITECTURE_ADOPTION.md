# Phương án tích hợp GĐ2/GĐ3 vào kiến trúc GĐ1 hiện hành

> `owner: ARCHITECTURE_OWNER` · `specified_at: 2026-10-29` · `implementation: PLANNED`  
> `as_of_commit: main@9e32daf` · Hợp đồng bổ sung, **không** thay sơ đồ runtime có thật trong `02-kien-truc/KIEN_TRUC_HE_THONG.md`.

## 1. Không tạo framework thứ hai

Giữ modular monolith theo `domain/application/infrastructure/presentation` và 4 nhóm workspace Qt hiện có. Viewer VTK tiếp tục ở Render Host child process, không đưa computation nặng vào Qt event loop.

```text
Qt Desktop (Project + Processing + Viewer)
               |
         Python app services
               |
   +-----------+------------+
   |           |            |
RAW storage  Geometry    Artifact/ProcessingRun
   |           |            |
Gemini2    NumPy/Open3D     SQLite + manifest
C++ SDK    (native batch C++   |
           when benchmarked)  +----> VTK Render Host
               |
        Keyframes / Registration / Fusion (GĐ3)
```

Sơ đồ trên là **target topology**, chưa phải trạng thái runtime tại commit nguồn. Không viết import code giả để giống sơ đồ.

## 2. Module boundaries đề xuất

- `acquisition` giữ SDK/live/capture, trả RAW và owned preview frames; không tính ICP trong camera adapter.
- `scan_pipeline` / `geometry` (tên module cần chốt khi triển khai 09): domain DTO cho cloud/ROI/transform, app services quyết định thứ tự, infrastructure adapter gọi Open3D/NumPy/C++.
- `metadata` là chủ SQLite, `storage` chủ RAW/derived files, `ProcessingRun` chủ trace trạng thái.
- `viewer3d` chỉ render và picking; không sinh cloud, không tự đo metric-accuracy.
- `ui/shell` composition root; không viết Open3D trực tiếp trong signal handler.

## 3. C++ khi nào bắt buộc

- Native Orbbec SDK camera/capture và buffer lifetime: bắt buộc đúng contract.
- `geometry.cpp` hiện hỗ trợ `unproject` đơn điểm; batch C++ chỉ thêm khi cần dựa trên benchmark NumPy/Open3D, tránh gọi Python↔C++ từng pixel.
- OpenCV/Open3D Python API có lõi C/C++ sẵn: không tự viết lại ROI/ICP/fusion để tăng tỷ lệ C++.
- Tách worker/process cho tính toán lớn; xem cancellation, buffer ownership, GIL, timeout, Windows DLL/ABI. Native camera crash không được phép làm hỏng RAW/SQLite.

## 4. Những điểm UI phải review trước code

- Wireframe/ảnh gắn panel cụ thể của GĐ1 cho Replay, Live Preview, Steps, Before/After, ROI, Measurement, Export. Không đổi theme/sidebar theo cảm tính.
- State matrix `no_project / no_capture / replay_ready / live_streaming / processing / error / partial_success / done`.
- Khi open external PLY khác artifact nội bộ: Inspector thể hiện `unknown` về unit/frame nếu thiếu provenance.
- Không để thêm toolbar trùng, số liệu giả, dữ liệu fixture không dán nhãn.

## 5. Các quyết định phải được khóa khi code

Phiên 09: worker camera SDK API, UI placement, `Capture` permission; phiên 10: datatype XYZRGB/occlusion/pixel center; phiên 11: segmentation mask semantics; phiên 12: normal orientation; phiên 13: artifact storage/recovery + internal scene provenance; phiên 15: `T_A_B` convention, quality thresholds; phiên 16: fusion/coverage definitions. Mỗi quyết định cần test/receipt và rollback.

## 6. Giới hạn

Chưa có tên module/code mới được thực thi; đây là proposed architecture. Không coi Open3D/OpenCV dependencies đã cài trong GĐ1 chỉ vì xuất hiện trong roadmap.
