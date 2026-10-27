# Tài liệu kỹ thuật ScanToPath — Điểm bắt đầu

**Mốc nguồn:** `feat/gd1-desktop-ui` tại R7-A `8e37eba2d270974b0dc61dde52c62ebc92d24a98`. **Ngôn ngữ tài liệu hiện hành:** tiếng Việt. **Vai trò:** cổng tra cứu, không phải báo cáo nghiệm thu.

## Tôi cần đọc tài liệu nào?

| Nhu cầu | Đọc trước | Đọc tiếp |
|---|---|---|
| Hiểu kiến trúc | [Tổng quan kiến trúc](architecture/TONG_QUAN_KIEN_TRUC.md) | [Cấu trúc nguồn](architecture/CAU_TRUC_SOURCE.md), [Ranh giới mô-đun](architecture/RANH_GIOI_MODULE.md) |
| Hiểu các luồng dữ liệu | [Luồng dữ liệu](architecture/LUONG_DU_LIEU.md) | [Thu nhận RGB-D](modules/THU_NHAN_RGBD.md), [Lưu trữ RAW](modules/LUU_TRU_RAW.md) |
| Sửa giao diện | [Giao diện desktop](modules/GIAO_DIEN_DESKTOP.md) | [Viewer 3D](modules/KIEM_TRA_3D.md) |
| Quản lý dự án và tệp quét | [Quản lý dự án](modules/QUAN_LY_DU_AN.md) | [Lưu trữ RAW](modules/LUU_TRU_RAW.md) |
| Cài đặt, phát triển | [Cài đặt](development/HUONG_DAN_CAI_DAT.md) | [Phát triển](development/HUONG_DAN_PHAT_TRIEN.md) và [Git](development/QUY_TRINH_GIT.md) |
| Viết mã và tài liệu | [Quy chuẩn mã](development/QUY_CHUAN_CODE.md) | [Quy tắc tài liệu](development/QUY_TAC_TAI_LIEU.md) |
| Kiểm thử và nghiệm thu | [Quy trình kiểm thử](development/QUY_TRINH_KIEM_THU.md) | [Tổng hợp nghiệm thu](acceptance/TONG_HOP_NGHIEM_THU.md) |
| Tìm quyết định thiết kế | [Chỉ mục quyết định](decisions/DECISION_INDEX.md) | [Nhật ký phát triển](history/DEVELOPMENT_MASTER_LOG.md) |
| Tìm tài liệu từng phiên cũ | [Kho lưu trữ](archive/README.md) | [Bảng đối chiếu đường dẫn R7-B](history/NGUON_HO_SO_CU.md) |
| Xem lộ trình nghiên cứu | [Lộ trình hiện hành](ROADMAP.md) | [Ánh xạ phiên](roadmap/SESSION_CROSSWALK.md) |

## Phân biệt đúng phạm vi

- **Đã có:** Ứng dụng desktop Qt/PySide6, quản lý Project/SQLite/RAW, mở PLY/OBJ trong Viewer VTK thường trú ở tiến trình riêng; chọn điểm/mặt, bảng thuộc tính và công cụ tương tác 3D.
- **Chưa có trong Viewer hiện hành:** Quy trình tự động quét → tái tạo point cloud → lọc → tạo mesh → sinh Zigzag/Contour. Mở PLY/OBJ là đọc và kiểm tra hình học, **không phải chạy pipeline scan-to-path**.
- **R6:** 14/14 cổng *tự động* PASS theo log người vận hành (618 Python PASS, ba trường hợp SKIP có giải thích, CTest 2/2); **R6 tổng thể vẫn PENDING** vì các cổng HMI/native chưa đủ bằng chứng. Xem [trạng thái GĐ1](acceptance/GD1.md).
- **Giả định cơ cấu quét:** Các hồ sơ trước đây có những giả định phần cứng theo thời điểm. Không dùng một ghi chú cũ để tự xác định tư thế máy, đơn vị đo hay chuyển động cơ cấu. Xem [điểm cần xác minh](standardization/R7B_CAN_XAC_MINH.md).

## Quy tắc đọc

Tài liệu trong `architecture/`, `modules/`, `development/`, `acceptance/` là lớp tra cứu hiện hành; `decisions/` lưu quyết định, `history/` ghi diễn tiến, `archive/` giữ hồ sơ theo thời điểm. Tên hàm, class, API, đường dẫn mã nguồn được giữ nguyên để có thể tra cứu trong repository. Kết luận chưa có chứng cứ phải ghi rõ **CHƯA XÁC MINH**.
