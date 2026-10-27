# Luồng dữ liệu trong ScanToPath hiện hành

## Luồng A — Thu nhận và ghi RAW (GĐ0)

```text
Gemini 2 → OrbbecSDK C++ → bản sao MJPEG/Y16
        → Python/pybind11 → metadata RAW v2
        → SessionStore.commit_raw()
        → thư mục Capture + manifest SHA-256 + COMMITTED
        → đăng ký MetadataStore/SQLite bằng hành động tường minh
```

Ảnh màu và độ sâu giữ **độ phân giải, thời gian, nội suy và thang đo độc lập** theo bản tin cảm biến; không căn chỉnh RGB–depth ngầm. Có bằng chứng một lần thu nhận thực, chưa chứng nhận độ chính xác 3D hay đồng bộ exposure.

## Luồng B — Quản lý dự án

```text
Người dùng → Project Workspace → Application service
                            → SQLite Project/Specimen/Session/Run
                            ↘ RAW registry (đọc/kiểm SHA khi yêu cầu)
```

SQLite chỉ chứa metadata và đường dẫn tương đối. Thao tác ghi tường minh, có trạng thái xử lý và audit trong phạm vi được hỗ trợ. `ProcessingRun` là bản ghi, không tự động chạy thuật toán.

## Luồng C — Xem dữ liệu PLY/OBJ

```text
Tệp ngoài PLY/OBJ → DTO nguồn/SHA-256 → phiên render bất đồng bộ
                    → Render Host cô lập: đọc point/mesh, dựng actor
                    → RGB shared memory → copy ở Qt → ACK
                    → Viewer và PropertyInspector

Click trong Viewer → scene/frame/source revision → picker trên host
                   → ID điểm/mặt + XYZ → Inspector
```

Mở tệp để xem **không** tự nạp RAW camera, lọc điểm, tạo mesh hay Zigzag. Hình học và lưới tham chiếu trong Viewer chỉ dùng quan sát cho đến khi được hiệu chuẩn riêng.

## Luồng chưa có trong bản này

RAW → giải mã → tính point cloud metric → ROI/filter → tái tạo mặt → đường dẫn robot là roadmap về sau. Không viết sơ đồ này như thể đã chạy end-to-end.
