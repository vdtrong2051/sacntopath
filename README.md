# ScanToPath — Ứng dụng desktop quản lý dữ liệu quét và kiểm tra hình học 3D

> **Bản mô tả phần mềm hiện hành:** `feat/gd1-desktop-ui@7a0df7c5b596ff8750bf91f47310067c53a8b204` (sau DOC-02), đối chiếu ngày **28/10/2026**.  
> **Phạm vi:** bản đã có trên Git ở GĐ0/GĐ1; không phải tuyên bố hoàn thành toàn bộ thuật toán Scan-to-Path.  
> **Chủ sở hữu tài liệu:** `DOCUMENTATION_OWNER`. **Bằng chứng:** source/pyproject/CTest và hồ sơ nghiệm thu GĐ0/GĐ1; các phép thử Windows mới của DOC-03A chỉ có hiệu lực sau khi người vận hành chạy xác minh.

## 1. ScanToPath là gì — và chưa phải là gì?

ScanToPath hướng tới chuyển dữ liệu cảm biến RGB-D của vật thể thật thành **hình học có thể truy vết, đánh giá độ tin cậy**, rồi phục vụ các tác vụ kỹ thuật: kiểm tra, thiết kế ngược, chế tạo và về sau là tham chiếu đường đi cho robot. Đích nghiên cứu lâu dài gồm tái tạo bề mặt và tạo đường tham chiếu; **bản desktop đang mô tả ở đây chưa có quy trình tự động nối từ camera tới mesh hay Zigzag/Contour**.

Bản phần mềm trên Git hiện cung cấp ba năng lực có source và test: (1) giao tiếp Gemini 2 theo lệnh, ghi/đọc RAW và metadata; (2) quản lý Project, vật mẫu, phiên quét, Capture, ProcessingRun qua SQLite; (3) mở **tệp PLY/OBJ từ bên ngoài** để xem, điều hướng và chọn điểm/mặt trên Viewer 3D. Ba năng lực này **chưa phải một pipeline end-to-end**. Việc Viewer đọc được một mesh không chứng minh phần mềm đã tái tạo mesh đó từ RAW.

Một giới hạn quan trọng: `measured=True` chỉ cho biết nguồn là dữ liệu cảm biến thật; **không** đồng nghĩa đã kiểm định sai số kích thước (`metric_validated`). Các tệp PLY/OBJ ngoài chưa xác minh có `units=unknown` và `coordinate_frame=unknown`; lưới tọa độ hiển thị không phải hệ tọa độ robot. Các bài kiểm thử tự động PASS không chứng minh HMI ở DPI thật, GPU/VRAM, lỗi native C++ khi bận hoặc độ trễ hình ảnh thực tế.

Đọc đầy đủ hơn tại [Giới thiệu dự án](docs/01-tong-quan/GIOI_THIEU_DU_AN.md) và [Phạm vi năng lực](docs/01-tong-quan/PHAM_VI_VA_NANG_LUC.md).

## 2. Năng lực tại mốc đối chiếu

| Năng lực | Triển khai trong Git | Bằng chứng phù hợp | Không được suy ra |
|---|---|---|---|
| Qt/PySide6 desktop, 4 workspace | `IMPLEMENTED` | Source UI và các Qt regression | Đã đạt HMI DPI thực tế |
| Project Workspace / SQLite / mã thư mục | `IMPLEMENTED` trong các đường thao tác được kiểm thử | Metadata, Project services, storage tests | Mọi tình huống mất điện đã được bảo đảm |
| Gemini 2 one-shot RAW MJPEG/Y16 | `IMPLEMENTED` theo lệnh riêng | Hồ sơ PRE-06, adapter/native, bài test RAW | Pose/world frame hoặc metric accuracy |
| PLY/OBJ Viewer, orbit/pan/zoom, point/face picking | `IMPLEMENTED` trong code | R5.3, R6 automated, test Viewer | Viewer tự sinh mesh hoặc xuất robot trajectory |
| RAW replay → point cloud metric → filtering → fusion | **Chưa có pipeline GĐ2/GĐ3 được tích hợp** | Roadmap/khả năng tương lai | Đã chạy end-to-end |
| Digital Replica, Active Acquisition, Zigzag/Contour thực thi trên bản desktop | **PLANNED / ngoài phạm vi build này** | Roadmap | Robot đang được điều khiển |
| GĐ1 HMI/native thực địa tổng thể | **PENDING** | [Biên bản R6](docs/07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md) | R8.5 commit = HMI PASS |

Bảng là **snapshot tại commit trên**, không phải sổ trạng thái luôn cập nhật. Khi DOC-04 hoàn thành, nguồn trạng thái vận hành sẽ chuyển sang `docs/05-quan-ly/TRANG_THAI_DU_AN.md`; không duy trì nhiều bảng trạng thái song song.

## 3. Cách các phần kết nối

```text
                      ỨNG DỤNG DESKTOP (Python 3.12 + Qt/PySide6)
        ┌──────────────────────────────────────────────────────────┐
        │ Qt Shell + Project Workspace + màn hình kiểm tra 3D      │
        │  ├─ lệnh người dùng → Project services → SQLite metadata│
        │  │                                 ↘ RAW files + manifest│
        │  └─ Viewer controller → IPC → Render Host VTK (process khác)
        │                                  ← RGB shared memory + ACK│
        └──────────────────────────────────────────────────────────┘

   Gemini 2 (mở theo lệnh) → OrbbecSDK/C++20 → pybind11 → RAW MJPEG/Y16
                        [không tự cấp point cloud/mesh cho Viewer]
   PLY/OBJ bên ngoài ────────────────────────────────→ Viewer controller
```

Giải thích ranh giới, vòng đời và xử lý lỗi ở [Kiến trúc hệ thống](docs/02-kien-truc/KIEN_TRUC_HE_THONG.md) và [Dữ liệu/hệ tọa độ](docs/02-kien-truc/DU_LIEU_VA_HE_TOA_DO.md).

## 4. Yêu cầu môi trường

- **Hệ điều hành phát triển/kiểm thử chính:** Windows; Python **3.12** khuyến nghị (package yêu cầu `>=3.12`).
- **Desktop:** Qt 6/PySide6; **Viewer 3D:** VTK. Đây là **optional dependencies** của `pyproject.toml`, phải cài khi cần chạy giao diện/Viewer.
- **C++:** CMake + MSVC có hỗ trợ C++20; `CTest` có hai smoke test không phụ thuộc camera khi build mặc định.
- **Camera thật:** Orbbec Gemini 2, OrbbecSDK và native extension là **bước cấu hình riêng**; không bắt buộc cho tài liệu, pytest cơ bản hoặc mở tệp PLY/OBJ.
- **Lưu trữ:** SQLite qua SQLAlchemy; RAW để trên filesystem, không đưa ảnh trực tiếp vào DB.

Danh sách trách nhiệm và phân biệt *đang dùng/định hướng* ở [Công nghệ và phụ thuộc](docs/02-kien-truc/CONG_NGHE_VA_PHU_THUOC.md).

## 5. Bắt đầu nhanh trên Windows (không mở camera)

Chạy **tại gốc repository** bằng PowerShell. Các lệnh sau tạo `.venv` và cài các phụ thuộc vào môi trường của dự án; **không tự thu ảnh** hoặc migrate SQLite. Cần Python 3.12 và kết nối tới package index khi cài lần đầu.

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[ui,viewer,test]"
& .\.venv\Scripts\python.exe -X utf8 -m scantopath.ui.main
```

Kết quả kỳ vọng: cửa sổ **ScanToPath** với bốn workspace (Dự án / Thu nhận RGB-D / Kiểm tra 3D / Xử lý). Chỉ khi người dùng chọn chức năng cần thiết mới mở nguồn dữ liệu hoặc khởi tạo Viewer; **không cần camera cắm sẵn**. Đóng cửa sổ để dừng Qt event loop. Khi chạy trên desktop thật, **không** đặt `QT_QPA_PLATFORM=offscreen`.

Nếu `.venv` đã được cấu hình, bỏ qua hai lệnh tạo/cài đặt. Nếu viewer báo thiếu VTK, đối chiếu `pip show vtk PySide6` trong chính `.venv` thay vì đổi mã nguồn. Xem [Sổ tay cài đặt hiện hành](docs/04-phat-trien/CAI_DAT_VA_CHAY.md) (DOC-03C sẽ viết lại đầy đủ).

## 6. Bản đồ repository

```text
src/scantopath/
  ui/                 Qt shell, dock, workspace, app entry
  modules/
    project_workspace/  presentation/application/infrastructure quản lý Project
    viewer3d/           controller, contracts và Render Host VTK tách tiến trình
  acquisition/       Gemini 2 adapter và lệnh thu nhận RAW
  storage/           RAW v1/v2, numbered layout và migration opt-in
  metadata/          SQLite schema/repository/audit
  domain/            hợp đồng dữ liệu và nguồn đo
  application/       DTO/command/task contract dùng chung
cpp/                 C++20, Orbbec source, native bindings, CTest
scripts/             unified regression, probes, quality gates
tests/               unit / integration / contracts / ui / native / performance
docs/                tài liệu chuẩn mới và hồ sơ tương thích/lịch sử
```

Điểm chạy UI là `src/scantopath/ui/main.py`; composition root là `src/scantopath/ui/shell/main_window.py`; điểm lắp Viewer là `src/scantopath/ui/shell/viewer_bootstrap.py`. **Không gọi `capture_once --once` như bước kiểm thử mặc định**: lệnh đó truy cập camera và ghi RAW mới.

## 7. Kiểm thử và cách hiểu kết quả

```powershell
.\scripts\verify.ps1 -Profile Quick
.\scripts\verify.ps1 -Profile Full
.\scripts\verify.ps1 -Profile Acceptance
```

- `Quick`: các kiểm tra tài liệu/kiến trúc/quality và pytest tập trung; dùng khi phát triển.
- `Full`: toàn bộ pytest, JUnit policy, CTest Release và các quality gates; dùng trước commit.
- `Acceptance`: ghi nhận các cổng tự động; **các cổng HMI/native thực địa chưa đo vẫn là `PENDING_MANUAL`**.

Dữ liệu kết quả chạy được lưu tại thư mục evidence **ngoài repository**. Ba test tạo symlink có thể SKIP trên Windows nếu thiếu quyền, và phải đúng ID/lý do trong chính sách. Xem [Quy trình kiểm thử](docs/04-phat-trien/KIEM_THU_VA_NGHIEM_THU.md), [Trạng thái R6](docs/07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md).

## 8. Cổng tài liệu và lịch sử

- [Bắt đầu đọc theo vai trò](docs/README.md): đường đọc từ người mới tới developer/nghiệm thu.
- [Lộ trình phát triển](docs/01-tong-quan/LO_TRINH_PHAT_TRIEN.md): điều gì có trước và phụ thuộc nào chưa làm.
- [Kiến trúc hệ thống](docs/02-kien-truc/KIEN_TRUC_HE_THONG.md), [hợp đồng dữ liệu](docs/02-kien-truc/DU_LIEU_VA_HE_TOA_DO.md) và [công nghệ](docs/02-kien-truc/CONG_NGHE_VA_PHU_THUOC.md).
- [Bằng chứng nghiệm thu GĐ1](docs/07-nghiem-thu/GD1_ACCEPTANCE.md): trạng thái và phần còn mở.

**Đường dẫn lịch sử tương thích, không phải cổng đọc chính:** [Tài liệu GĐ1 hiện hành](docs/README.md). Mục này được giữ vì gate R7 cũ đang kiểm tra liên kết chính xác; đến DOC-05 mới xem xét thay gate và redirect. Một số hồ sơ GĐ0/R4/R5 còn ở commit Git lịch sử, không nên xem các nhãn `PENDING` khi đó như trạng thái software tại commit hiện hành.
