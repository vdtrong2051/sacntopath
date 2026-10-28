# Giới thiệu ScanToPath — bài toán, sản phẩm và ranh giới nghiên cứu

> `owner: PRODUCT_SCOPE_OWNER` · `as_of_commit: 7a0df7c5b596ff8750bf91f47310067c53a8b204` · `verified_at: 2026-10-28`  
> `scope: GĐ0/GĐ1 đã có trong Git; hướng nghiên cứu GĐ2–GĐ5 được ghi riêng` · `evidence_level: SOURCE_REVIEW + HISTORICAL_OPERATOR_REPORT`  
> **Nguồn chuẩn về phạm vi sản phẩm:** tài liệu này và [ma trận năng lực](PHAM_VI_VA_NANG_LUC.md); trạng thái task/acceptance phát sinh sau ngày này phải đọc ở nguồn quản trị/biên bản mới hơn.

## 1. Vì sao có ScanToPath?

Đối tượng kỹ thuật có bề mặt cong thường khó mô tả chỉ bằng vài kích thước thủ công. Camera RGB-D ghi nhận một phần bề mặt, nhưng một lần thu ảnh **không tự mang đến** mô hình 3D đúng kích thước hay đường thao tác robot. Cần quản lý dữ liệu gốc, nguồn gốc của từng kết quả, hệ tọa độ, sai số, vùng chưa quan sát và khả năng tái sử dụng. ScanToPath đặt mục tiêu xây dựng chuỗi dữ liệu **có căn cứ kỹ thuật**, để từ một dữ liệu thu nhận có thể biết kết quả nào thực sự đo được, kết quả nào chỉ suy luận và khi nào cần đo bổ sung.

Những ứng dụng có thể hưởng lợi gồm kiểm tra/so sánh bề mặt, thiết kế ngược, tạo bản sao số kỹ thuật, chuẩn bị dữ liệu cho chế tạo và tham chiếu quỹ đạo phun phủ. Đây là **định hướng ứng dụng**, không phải khẳng định bản GĐ1 đã xuất G-code hoặc điều khiển robot.

Trong bản triển khai hiện hành, quan hệ Project/Specimen/Session/Capture được lưu trong **SQLite**, còn byte dữ liệu nguồn được giữ riêng dưới dạng tệp RAW. Người đọc có thể mở Viewer để kiểm tra PLY/OBJ độc lập với những bản ghi này.

## 2. Từ cảm biến tới hình học đáng tin: các tầng phải phân biệt

```text
DỮ LIỆU NGUỒN           DỮ LIỆU HÌNH HỌC               TÁC VỤ KỸ THUẬT
RGB-D + calibration → point cloud theo camera → hình học metric có đánh giá
                         │                           → feature/quan hệ kỹ thuật
                         │                           → bản sao số kỹ thuật
                         └──── chất lượng/chỗ thiếu → thu nhận bổ sung
                                                       → đường tham chiếu cho ứng dụng
```

Dòng sơ đồ này là **chuỗi mục tiêu nghiên cứu**, không phải luồng thực thi GĐ1. Trong bản hiện có, Qt Project quản lý metadata/RAW còn Viewer mở một PLY/OBJ **được cung cấp độc lập**; hai nhánh chưa được nối bằng một dịch vụ tái tạo từ RGB-D.

Có ba ranh giới cần hiểu:

- **RAW vs dữ liệu dẫn xuất:** MJPEG/Y16 là byte nguồn. Point cloud, mesh, feature và path là dữ liệu xử lý; để đáng tin, chúng phải mang mã nguồn, tham số thuật toán, frame và cấp độ kiểm chứng.
- **Có hình học vs đúng phép đo:** một mesh kín có thể đã nội suy qua vùng không nhìn thấy. Tọa độ có số thập phân không bảo đảm sai số thấp nếu chưa hiệu chuẩn/so với mẫu chuẩn.
- **Có đường tham chiếu vs robot di chuyển thật:** Zigzag/Contour là đường hình học theo mục tiêu về sau; robot trajectory/pose/điều khiển còn phụ thuộc hệ tọa độ máy, động học, giới hạn cơ cấu và xác nhận an toàn.

## 3. Sản phẩm phần mềm đang có trong repository

| Khối | Người dùng thấy gì hoặc gọi được gì? | Điểm triển khai |
|---|---|---|
| Desktop UI | Bốn workspace, dock quản lý, trạng thái tác vụ | `src/scantopath/ui/main.py`, `ui/shell/main_window.py` |
| Project & metadata | Project → Specimen → ScanSession → Capture/ProcessingRun, audit | `src/scantopath/modules/project_workspace/`, `src/scantopath/metadata/` |
| Lưu trữ nguồn | RAW v1/v2, manifest/checksum, `COMMITTED`, numbered registry | `src/scantopath/storage/` |
| Nguồn RGB-D | Adapter Gemini 2 qua C++/pybind11, one-shot theo lệnh | `src/scantopath/acquisition/`, `cpp/` |
| Kiểm tra 3D | Mở PLY/OBJ, điều hướng, picking, Inspector, grid/layer | `src/scantopath/modules/viewer3d/`, Render Host tách tiến trình |

Điều **chưa có trong build GĐ1**: chuyển tự động RAW RGB-D thành metric point cloud rồi ghép nhiều view, tái tạo mesh, sinh Zigzag/Contour, điều khiển robot, bản sao số được kiểm định. Có thể tồn tại dữ liệu thử hoặc prototype nghiên cứu ở nơi khác, nhưng tài liệu này chỉ đánh giá **repository desktop tại commit ghi đầu trang**.

## 4. Phần cứng và các giả định cần thận trọng

Hồ sơ GĐ0 ghi nhận **Orbbec Gemini 2**, OrbbecSDK v2.10.6, một lần thu RAW thật được người vận hành báo cáo thành công. Metadata có intrinsics/distortion, depth scale, D2C và timestamps. **Mốc Git không tự chứng minh cấu hình lắp đặt vật lý đang sử dụng**, vị trí camera cố định hay chuyển động theo hai trục, encoder, pose và đồng bộ với cơ cấu. Những mô tả camera cầm tay trong roadmap/metadata GĐ0 là giả định lịch sử của giai đoạn đó, không là quyết định hiện trạng cơ khí tháng 10 nếu chưa được đối chiếu.

Quyết định cấu hình vật lý cần ghi nhận độc lập trong DOC-04 bằng version cơ cấu, phương pháp đo/biên bản hoặc tài liệu nguồn. Cho tới lúc đó, kiến trúc phần mềm chỉ nói chắc được: acquisition có API thu nhận Gemini 2 theo lệnh; View 3D không điều khiển cơ cấu quét.

## 5. Kiến trúc thiết kế được chọn và lý do

ScanToPath phát triển theo **desktop modular monolith**, Qt/PySide6 xử lý tương tác; Python service và mô-đun hạ tầng xử lý chức năng; C++20/pybind11 cô lập phần gắn SDK camera; VTK chạy trong **Render Host riêng** để giảm tác động của vòng đời native lên Qt. Đó là lựa chọn đã được thử so sánh với VTK nhúng ở R4, nhưng không được hiểu là đã bảo đảm an toàn trước mọi lỗi native.

Nền tảng ưu tiên việc có luồng thao tác quan sát được (**UI-first theo lát cắt dọc**), không đồng nghĩa bỏ qua core hoặc chứng cứ dữ liệu. Xem giải thích chi tiết, kiến trúc process và ranh giới ở [Kiến trúc hệ thống](../02-kien-truc/KIEN_TRUC_HE_THONG.md).

## 6. Cách đánh giá một thành quả ScanToPath

Một năng lực mới chỉ nên gọi là hoàn thành trong phạm vi cụ thể khi trả lời được: đầu vào nào, có nguồn gốc không; biến đổi nào; đơn vị/hệ tọa độ nào; kiểm thử giả lập nào; phép thử thực nào; lỗi đã được xử lý thế nào; còn giới hạn gì. Ví dụ, `SceneDescriptor.source_sha256` bảo vệ sự đồng nhất tệp vào Viewer, **không** kiểm định độ chính xác hình học của tệp.

Ba tầng bằng chứng không thể thay thế nhau: `IMPLEMENTED_IN_GIT`, `AUTOMATED_VERIFICATION`, `PHYSICAL_MANUAL_ACCEPTANCE`. R8.5 đã được commit trong Git, nhưng kết quả nghiệm thu HMI/native cuối GĐ1 vẫn phải xử lý tại 08.06.6. Trường hợp chưa có phép đo ghi `NOT_TESTED`, không ghi PASS.

## 7. Bắt đầu tìm hiểu dự án

- Muốn biết chức năng nào dùng được: [Phạm vi và năng lực](PHAM_VI_VA_NANG_LUC.md).
- Muốn hiểu cách phần mềm chạy: [Kiến trúc hệ thống](../02-kien-truc/KIEN_TRUC_HE_THONG.md).
- Muốn hiểu mét, milimét, pose, frame và nguồn gốc dữ liệu: [Dữ liệu và hệ tọa độ](../02-kien-truc/DU_LIEU_VA_HE_TOA_DO.md).
- Muốn chạy desktop: [README gốc](../../README.md) (có lệnh Windows và điều kiện đầu vào).
- Muốn kiểm chứng một quyết định trước đây: [ADR](../05-quan-ly/QUYET_DINH_KY_THUAT.md) hoặc [nhật ký kỹ thuật](../99-lich-su/README.md).

**Giới hạn:** tài liệu này là bản giải nghĩa sản phẩm tại một commit. Các module GĐ1 sẽ có tài liệu tự chứa ở DOC-03B; không dùng phần này thay hồ sơ nghiệm thu có chữ ký và evidence thực địa.
