# UXH-01.8 — Phụ lục triển khai Qt UI, Capture và Viewer

> Source HEAD: `016f0cf06de65a432626bb58ec8868483b30eb04`; bổ sung cho [Desktop UI](DESKTOP_UI.md) và [Viewer 3D](VIEWER_3D.md). Đây là bản cập nhật năng lực của các checkpoint UXH, không phải tuyên bố mọi nghiệm thu hardware/human đã PASS.

## UXH-01.1–01.6

- Qt shell duy trì bốn workspace, Project selection và Scene selection được phân định.
- Capture click từ Explorer/Dashboard dẫn đến RAW đã lưu và Replay; không suy ra mọi selected Capture là active camera stream.
- Viewer VTK Render Host ở child process; toolbar/picking được kiểm bằng typed source/scene revision, stale reply không viết đè Inspector.
- Geometry Preview tạo PLY XYZRGB một góc nhìn từ RAW, `PreviewScratchLeases` quản lý thư mục tạm theo vòng đời source; Depth A–B sử dụng ảnh Depth, không coi tọa độ PLY ngoài là metric verified.

## UXH-01.7 — giao diện

- `Viewer3DPage` công khai các named layout slots; `InteractiveViewer3DController` không còn dùng index `itemAt(1)` để ẩn fallback navigation; Geometry Preview và Measurement dùng slot có tên.
- Toolbar chính: Select, Orbit, Pan, Fit; Advanced menu: Zoom, Axes, Grid/planes XY-XZ-YZ-Base, Layer. Các nút Qt gốc, `objectName`, phím S/R/P/F/G/L vẫn được giữ. B-R01 đồng bộ Grid/Layer menu actions hai chiều; visual hotfix chỉ thay kiểu hiển thị.
- Canvas giảm khoảng đệm, không thay camera algorithm; Capture workflow hint co gọn theo viewport, tab không mất widget khi resize; Property Inspector hiển thị title/note co giãn.
- UXH-01.7 commit `016f0cf...` gồm 8 source files và 7 tests.

## Phân biệt fallback và live native

`QT_QPA_PLATFORM=offscreen` kiểm thử contract/layout, không chứng nhận GPU/VTK native HMI, pixel-present latency hay USB reconnect. Dùng bản Windows giao diện thật khi chạy manual M01–M09.

## Liên quan roadmap

Những thay đổi trên **không** bổ sung segmentation, normals, multi-view registration, mesh, digital replica hoặc robot trajectory. Các năng lực này phải tiếp tục qua GD2/GD3 và kế hoạch hiện hành.
