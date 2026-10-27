# Mô-đun Kiểm tra mô hình 3D — Viewer R5.3

## Vai trò

Đọc và tương tác với tệp hình học 3D **PLY point-only, PLY có mặt và OBJ**. Viewer không tự tái tạo hình học từ dữ liệu camera hay tạo quỹ đạo robot.

## Thành phần triển khai

- `src/scantopath/ui/shell/viewer_bootstrap.py`: lắp ráp live controller/fallback.
- `modules/viewer3d/presentation/live_controller.py`: nạp nguồn bất đồng bộ, nhận frame, mất host/thử lại và đóng.
- `modules/viewer3d/presentation/interactive_controller.py`: chọn điểm/mặt, toolbar SVG, lưới, lớp, phím tắt.
- `ui/shell/viewer_inspector_bridge.py`: chuyển thông tin hình học sang PropertyInspector dùng chung.
- `modules/viewer3d/infrastructure/resident_poc/`: VTK Render Host, IPC, shared memory, revision và quản lý actor.

## Hợp đồng tương tác

| Dữ liệu/thao tác | Kết quả |
|---|---|
| PLY chỉ chứa vertex | Hiển thị point cloud; không bịa polygon |
| PLY/OBJ có face | Hiển thị mesh; không âm thầm chuyển thành đỉnh rời |
| Click điểm | Trả Point ID/XYZ theo file và frame hợp lệ |
| Click mặt | Trả Cell ID và giao điểm trên mặt (không phải vertex ID CAD) |
| Orbit/pan/zoom/fit | Không đọc lại file mỗi cử chỉ; Qt tiếp tục phản hồi |
| Lưới Oxy / gizmo XYZ | Tham chiếu hiển thị, **không** chứng minh datum hoặc tọa độ robot |
| Hiện/ẩn lớp | Thao tác actor nguồn thật, không tạo lớp hình học giả |
| Đổi source hoặc mất child | Xóa lựa chọn/frame cũ; không sử dụng lại dữ liệu stale |
| Sao chép XYZ | Giá trị số đầy đủ theo dữ liệu nội bộ; không suy ra độ chính xác phép đo |

## Không được ghi sai trạng thái

Đơn vị và hệ tọa độ tệp ngoài chưa xác minh phải hiển thị `unknown`. Benchmark renderer 1K/100K/1M và native probe R5.3 không phải bằng chứng FPS màn hình, latency thực, VRAM hay close-while-native-busy. R6 tổng thể vẫn PENDING.

## Kiểm thử và hướng dẫn

`tests/test_gd1_r5_1_scene_geometry.py`, `tests/test_gd1_r5_2_live_viewer.py`, `tests/test_gd1_r5_3_geometry_interaction.py`, `tests/test_gd1_r5_3_qt.py`; `scripts/r5_3_native_probe.py`.

Xem [Luồng dữ liệu](../architecture/LUONG_DU_LIEU.md), [Giao diện desktop](GIAO_DIEN_DESKTOP.md), [Trạng thái nghiệm thu](../acceptance/GD1.md).
