# Viewer 3D — tài liệu mô-đun hiện hành

**Baseline kiểm tra:** R5.3 `ff45ccf` · **Trạng thái:** có viewer 3D thực; các phép xử lý dữ liệu quét là chức năng tương lai.

## Các luồng chính

1. `viewer_bootstrap.py` tạo `InteractiveViewer3DController` khi người dùng vào Kiểm tra 3D; khi Qt chạy offscreen/minimal dùng fallback controller theo hợp đồng kiểm thử.
2. `live_controller.py` thực hiện `load_ply` (tên API tương thích, hỗ trợ PLY/OBJ ở live), quản lý phiên, quy tắc chọn frame mới nhất, mất host, retry và teardown. Việc tải dữ liệu thực do resident child đảm nhiệm.
3. `interactive_controller.py` điều phối chọn điểm/mặt, hiển thị/ẩn actor, lưới, công cụ SVG và phím tắt, tương tác dựa trên frame hợp lệ.
4. `viewer_inspector_bridge.py` nối kết quả hình học vào PropertyInspector chung. Thay scene/rời Viewer/xảy ra lỗi phải vô hiệu hóa lựa chọn cũ.
5. `resident_poc/{protocol,host,async_session}.py` xử lý renderer resident, IPC, RGB24 shared frame + ACK, scene/frame/source identity.

## Hợp đồng kiểm tra

| Thao tác | Hợp đồng |
|---|---|
| Mở PLY points | Chỉ đỉnh, `face_count=0`; hiển thị points, không bịa mặt |
| Mở PLY mesh / OBJ | Nhận diện faces thật, hiển thị mesh; không đổi sang points ngầm |
| Orbit/pan/zoom | Không mở lại source mỗi cử chỉ; frame mới nhất, nonblocking Qt |
| Chọn điểm | Point ID và tọa độ gắn với file/scene còn hiệu lực |
| Chọn mặt | Cell ID VTK và **điểm giao trên mặt**, không phải vertex ID CAD |
| Grid Oxy | Mặt phẳng hiển thị Z=0, không đảm bảo quy chiếu metric/world |
| Inspector | XYZ, SHA-256, bounds và units/frame ghi unknown khi chưa xác nhận |
| Source switch | Xóa selection/frame cũ; tiến trình cũ được thu hồi an toàn |
| Host loss/retry | Không freeze GUI; no orphan child theo bài thử vòng đời |
| PNG fallback | Phương án xem trước tương thích, không thay kiến trúc native chính |

## Phạm vi KHÔNG được khẳng định

Không có tự động lọc point cloud, reconstruct từ RAW, pháp tuyến/sinh Zigzag/Contour, calibration, pose đo thật hoặc motion control ở Viewer hiện tại. R6 benchmark 1k/100k/1m là **completed render / resident workload**, không phải pointer-to-photon FPS thực. R5.3 native probe dùng fixture nhỏ, không thay HMI ngoài thực tế.

**Kiểm thử:** `tests/test_gd1_r5_1_scene_geometry.py`, `tests/test_gd1_r5_2_live_viewer.py`, `tests/test_gd1_r5_3_geometry_interaction.py`, `tests/test_gd1_r5_3_qt.py`, `scripts/r5_3_native_probe.py`.

**Hồ sơ:** [R4.5](../gd1/ux_rebaseline/R4_05_R5_HANDOVER_GATES.md) · [R5.2](../gd1/ux_rebaseline/R5_02_LIVE_QT_VIEWPORT_INTEGRATION.md) · [R5.3](../gd1/ux_rebaseline/R5_03_INTERACTION_INSPECTOR_UX.md).
