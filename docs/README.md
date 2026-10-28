# Cổng tài liệu ScanToPath — đọc đúng nội dung, không phải ghép ghi chú

> `owner: DOCUMENTATION_OWNER` · `as_of_commit: 7a0df7c5b596ff8750bf91f47310067c53a8b204` · `verified_at: 2026-10-28`  
> **Trạng thái:** DOC-03A mới bổ sung lớp Tổng quan/Kiến trúc v2; các module và sổ tay phát triển cũ **chưa** được viết lại (DOC-03B/C). Tài liệu DOC-04 về task/state và DOC-05 về di chuyển thư mục cũng chưa triển khai tại mốc nguồn.

## Bạn cần hiểu gì trước tiên?

Đọc [README gốc](../README.md) để biết ứng dụng đang chạy được gì, sau đó chọn **một trong bốn tuyến** dưới đây. Khi vào tài liệu chuyên môn, các khái niệm cốt lõi và luồng xử lý sẽ được giải thích ngay trong trang, không bắt buộc tìm hồ sơ R4/R5 để ghép ý.

| Bạn là ai / bạn muốn gì? | Bắt đầu ở đâu? | Đọc tiếp nếu cần |
|---|---|---|
| Người mới: ScanToPath giải quyết việc gì? | [Giới thiệu dự án](01-tong-quan/GIOI_THIEU_DU_AN.md) | [Khả năng và giới hạn](01-tong-quan/PHAM_VI_VA_NANG_LUC.md) |
| Developer: phần mềm được chia lớp thế nào? | [Kiến trúc hệ thống](02-kien-truc/KIEN_TRUC_HE_THONG.md) | [Dữ liệu và tọa độ](02-kien-truc/DU_LIEU_VA_HE_TOA_DO.md), [công nghệ](02-kien-truc/CONG_NGHE_VA_PHU_THUOC.md) |
| Developer: sửa một module cụ thể? | [Project](modules/QUAN_LY_DU_AN.md), [Viewer](modules/KIEM_TRA_3D.md), [RAW](modules/LUU_TRU_RAW.md), [RGB-D](modules/THU_NHAN_RGBD.md), [Desktop](modules/GIAO_DIEN_DESKTOP.md) | **Lưu ý:** các trang module hiện tại là bản R7, sẽ được thay bằng bản đầy đủ ở DOC-03B |
| Phát triển/kiểm thử trên Windows? | [Cài đặt](development/HUONG_DAN_CAI_DAT.md), [Kiểm thử](development/QUY_TRINH_KIEM_THU.md) | Các sổ tay phát triển sẽ được biên tập đầy đủ ở DOC-03C |
| Điều phối/đánh giá dự án? | [Lộ trình](01-tong-quan/LO_TRINH_PHAT_TRIEN.md), [GĐ1](acceptance/GD1.md) | [R6](acceptance/GD1_R6_ACCEPTANCE_STATUS.md), [ADR](decisions/DECISION_INDEX.md), [nhật ký](history/README.md) |

## Ba tầng thông tin không được trộn

**Phần mềm đang chạy:** chỉ khẳng định những hành vi đã có source/kiểm thử ở baseline. Ví dụ Viewer có thể xem PLY/OBJ do nơi khác tạo, **chưa** biến RAW thành point cloud/mesh/đường robot.

**Định hướng:** lộ trình GĐ2–GĐ5 đề ra năng lực và điều kiện chứng minh. Dự định sử dụng Open3D/OpenCV hoặc có cơ cấu hai trục **không** mặc định là chức năng đã tích hợp.

**Bằng chứng và lịch sử:** commit xác nhận file đã được đưa vào Git; pytest/CTest xác nhận hợp đồng được thử trong môi trường cụ thể; HMI/native/GPU thực tế là phép thử khác. Trạng thái tổng thể GĐ1 vẫn cần cổng 08.06.6 và không tự được nâng thành PASS vì R8.5 đã commit.

## Ai sở hữu thông tin nào?

| Điều cần biết | Nguồn chuẩn theo thiết kế DOC-02 | Hiện tại ở DOC-03A |
|---|---|---|
| Kiến trúc và luồng kỹ thuật | `02-kien-truc/` | **Đã viết bản v2** theo commit đối chiếu |
| Phạm vi năng lực và roadmap | `01-tong-quan/` | **Đã viết bản v2**; snapshot, không phải task ledger |
| Hướng dẫn module chi tiết | `03-modules/` | **DOC-03B chưa thực hiện**; dùng `modules/` cũ có ghi phạm vi |
| Build/Git/kiểm thử đầy đủ | `04-phat-trien/` | **DOC-03C chưa thực hiện**; dùng `development/` hiện tại |
| Task và trạng thái sống | `05-quan-ly/` | **DOC-04 chưa thực hiện**; chưa tự tạo trạng thái giả |
| Hồ sơ giai đoạn và nghiệm thu | `06-giai-doan/`, `07-nghiem-thu/` | **DOC-04/05 chưa thực hiện**; dùng `acceptance/` hiện hành |
| Hồ sơ R7/R8, ADR và tài liệu gốc | `99-lich-su/` | **Chưa di chuyển**; dùng `archive/`, `history/`, `standardization/` |

## Cách duy trì khi có thay đổi mã nguồn

1. Xác định tài liệu chuẩn thuộc module/layer nào; mô tả lại đầu vào, đầu ra, lỗi và đường test thực.
2. Ghi `as_of_commit` và thời điểm đối chiếu; không sửa hồi tố tài liệu lịch sử thành “đã hoàn thành”.
3. Nếu thay đổi giao thức/đơn vị/nguồn dữ liệu, cập nhật tài liệu hợp đồng và kiểm thử cùng PR.
4. Nếu có kết quả HMI/native mới, ghi vào hồ sơ nghiệm thu có đường dẫn receipt thật; không sửa README thành “PASS tổng thể” trước khi duyệt.
5. DOC-05 mới cập nhật các gate R7/R8 đang trỏ vào đường cũ; không xóa redirect giữa chừng.

**Đặc tả thiết kế:** [Kiến trúc tài liệu DOC-02](standardization/DOC02_KIEN_TRUC_TAI_LIEU.md). Đây là tài liệu quy định cách viết và chuyển đổi, **không** phải nơi đọc kiến trúc runtime ScanToPath.
