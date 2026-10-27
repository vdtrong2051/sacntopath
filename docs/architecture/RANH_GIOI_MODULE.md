# Ranh giới trách nhiệm giữa các mô-đun

| Thành phần | Được sở hữu | Không được làm thay |
|---|---|---|
| `ui/shell` | Điều hướng, bố cục cửa sổ, kết nối controller | Đọc/ghi SQL, xử lý native 3D nặng |
| `project_workspace/presentation` | Lệnh người dùng, trạng thái trang, phản hồi Qt | Tự tạo RAW giả hoặc tự tính toán scan |
| Dịch vụ Project | Xác thực hành động và giao tiếp metadata/storage | Đưa widget Qt vào tầng lưu trữ |
| `metadata` | Bản ghi Project/Specimen/Session/Capture/Run, audit | Lưu dữ liệu MJPEG/Y16 trong SQLite |
| `storage` | Ghi/đọc RAW byte gốc, checksum, marker commit | Tự đổi hệ quy chiếu/align ảnh |
| `acquisition` | Giao tiếp Gemini 2, dữ liệu cảm biến và metadata | Tự chứng nhận sai số/pose quét |
| Viewer presentation | Công cụ, Inspector, yêu cầu camera/selection | Import VTK native, chặn Qt UI lâu |
| Viewer infrastructure | Đọc PLY/OBJ, actor VTK, camera, picking, frame | Ghi Capture/ProcessingRun hoặc RAW gốc |

## Bất biến xuyên mô-đun

- **Nguồn dữ liệu:** RAW sau commit không thay đổi byte; file nhập ngoài được nhận diện bằng SHA-256, không có đơn vị giả định.
- **Vòng đời:** Một `scene_revision` mới làm vô hiệu hóa frame/selection cũ. Child process mất không được kéo Qt chết theo.
- **Hình học:** Mesh có face không tự đổi thành point-only; giao điểm mặt không phải tọa độ một đỉnh CAD.
- **Độ tin cậy:** `measured` nghĩa là nguồn cảm biến thật, không có nghĩa `metric_validated`. Planned path không tương đương pose hoặc chuyển động đo thật.

Nguồn quyết định: [Chỉ mục ADR](../decisions/DECISION_INDEX.md); tài liệu chi tiết tại [Viewer](../modules/KIEM_TRA_3D.md) và [Project](../modules/QUAN_LY_DU_AN.md).
