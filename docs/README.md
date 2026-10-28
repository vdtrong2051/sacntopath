# Cổng tài liệu ScanToPath — đọc đúng nội dung, không phải ghép ghi chú

> `owner: DOCUMENTATION_OWNER` · `as_of_commit: 7a0df7c5b596ff8750bf91f47310067c53a8b204` · `verified_at: 2026-10-28`  
> **Trạng thái cập nhật DOC-03B (source baseline `0557c0d4fed9a3df3b180fc9872c6d3293b5f0d5`, 2026-10-28):** bộ 5 module v2 đã được bổ sung. Metadata `as_of_commit` phía trên là mốc nội dung DOC-03A và vẫn giữ để bảo toàn hợp đồng kiểm tra DOC-03A; đây **không** phải tuyên bố DOC-03B đã được nghiệm thu Windows. Sổ tay phát triển DOC-03C đã commit trên Git; DOC-04 đã soạn bộ quản trị/giai đoạn/nghiệm thu (chỉ có hiệu lực khi operator áp gói và nghiệm thu Windows). DOC-05 đã commit tại `1a79e1e`; DOC-06 hợp nhất đường dẫn cũ, giữ các bản lịch sử có truy vết Git và vẫn chờ HMI 08.06.6.

## Bạn cần hiểu gì trước tiên?

Đọc [README gốc](../README.md) để biết ứng dụng đang chạy được gì, sau đó chọn **một trong bốn tuyến** dưới đây. Khi vào tài liệu chuyên môn, các khái niệm cốt lõi và luồng xử lý sẽ được giải thích ngay trong trang, không bắt buộc tìm hồ sơ R4/R5 để ghép ý.

| Bạn là ai / bạn muốn gì? | Bắt đầu ở đâu? | Đọc tiếp nếu cần |
|---|---|---|
| Người mới: ScanToPath giải quyết việc gì? | [Giới thiệu dự án](01-tong-quan/GIOI_THIEU_DU_AN.md) | [Khả năng và giới hạn](01-tong-quan/PHAM_VI_VA_NANG_LUC.md) |
| Developer: phần mềm được chia lớp thế nào? | [Kiến trúc hệ thống](02-kien-truc/KIEN_TRUC_HE_THONG.md) | [Dữ liệu và tọa độ](02-kien-truc/DU_LIEU_VA_HE_TOA_DO.md), [công nghệ](02-kien-truc/CONG_NGHE_VA_PHU_THUOC.md) |
| Developer: sửa một module cụ thể? | [Project Workspace](03-modules/PROJECT_WORKSPACE.md), [Viewer 3D](03-modules/VIEWER_3D.md), [RAW Storage](03-modules/RAW_STORAGE.md), [RGB-D Acquisition](03-modules/RGBD_ACQUISITION.md), [Desktop UI](03-modules/DESKTOP_UI.md) | Bộ DOC-03B trình bày trực tiếp API, flow, lỗi và test; chỉ còn một bộ tài liệu chuẩn v2 |
| Phát triển/kiểm thử trên Windows? | [Cài đặt, build, chạy](04-phat-trien/CAI_DAT_VA_CHAY.md), [Phát triển, debug, Git](04-phat-trien/HUONG_DAN_PHAT_TRIEN.md), [Tiêu chuẩn kỹ thuật](04-phat-trien/TIEU_CHUAN_KY_THUAT.md), [Kiểm thử, nghiệm thu](04-phat-trien/KIEM_THU_VA_NGHIEM_THU.md) | DOC-03C đã viết nội dung; kết quả Windows cần receipt operator. Các trang cũ đã được hợp nhất vào `04-phat-trien/` |
| Điều phối/đánh giá dự án? | [Task Register](05-quan-ly/TASK_REGISTER.md), [Trạng thái dự án](05-quan-ly/TRANG_THAI_DU_AN.md), [Hồ sơ GĐ1](06-giai-doan/GD1_DESKTOP_VIEWER.md), [Nghiệm thu GĐ1](07-nghiem-thu/GD1_ACCEPTANCE.md) | [ADR hiện hành](05-quan-ly/QUYET_DINH_KY_THUAT.md), [Incident Register](05-quan-ly/INCIDENT_REGISTER.md), [Evidence Index](07-nghiem-thu/EVIDENCE_INDEX.md), [GĐ0](06-giai-doan/GD0_SOFTWARE_FOUNDATION.md), [Crosswalk](06-giai-doan/SESSION_CROSSWALK.md) |

**Kho lịch sử:** [Chỉ mục ADR, nhật ký, R7/R8 và archive](99-lich-su/README.md) — bản lưu lịch sử, không dùng thay ledger trạng thái hoặc nghiệm thu hiện hành.

## Ba tầng thông tin không được trộn

**Phần mềm đang chạy:** chỉ khẳng định những hành vi đã có source/kiểm thử ở baseline. Ví dụ Viewer có thể xem PLY/OBJ do nơi khác tạo, **chưa** biến RAW thành point cloud/mesh/đường robot.

**Định hướng:** lộ trình GĐ2–GĐ5 đề ra năng lực và điều kiện chứng minh. Dự định sử dụng Open3D/OpenCV hoặc có cơ cấu hai trục **không** mặc định là chức năng đã tích hợp.

**Bằng chứng và lịch sử:** commit xác nhận file đã được đưa vào Git; pytest/CTest xác nhận hợp đồng được thử trong môi trường cụ thể; HMI/native/GPU thực tế là phép thử khác. Trạng thái tổng thể GĐ1 vẫn cần cổng 08.06.6 và không tự được nâng thành PASS vì R8.5 đã commit.

## Ai sở hữu thông tin nào?

| Điều cần biết | Nguồn chuẩn theo thiết kế DOC-02 | Hiện trạng sau biên soạn DOC-04 (chờ Windows verify) |
|---|---|---|
| Kiến trúc và luồng kỹ thuật | `02-kien-truc/` | **Đã viết bản v2** theo commit đối chiếu |
| Phạm vi năng lực và roadmap | `01-tong-quan/` | **Đã viết bản v2**; snapshot, không phải task ledger |
| Hướng dẫn module chi tiết | `03-modules/` | **DOC-03B: đã soạn 5 tài liệu**; chưa xác nhận Windows đến khi chạy full regression và operator review |
| Build/Git/kiểm thử đầy đủ | `04-phat-trien/` | **DOC-03C đã biên soạn**; chưa tuyên bố Full Windows PASS; sử dụng duy nhất `04-phat-trien/` |
| Task và trạng thái sống | `05-quan-ly/` | **DOC-04 đã biên soạn** Task Register/State Ledger với nguồn và `NOT_TESTED` rõ ràng; Windows operator chưa duyệt pack |
| Hồ sơ giai đoạn và nghiệm thu | `06-giai-doan/`, `07-nghiem-thu/` | **DOC-04 đã biên soạn** GĐ0/GĐ1, Evidence Index và HMI gate; chỉ sử dụng `07-nghiem-thu/` |
| Hồ sơ R7/R8, ADR và tài liệu gốc | `99-lich-su/` | **DOC-05:** kho lịch sử bản sao có đối chiếu Git; đường dẫn cũ được hợp nhất; bản gốc có thể truy xuất bằng commit Git; HMI 08.06.6 vẫn pending |

## Cách duy trì khi có thay đổi mã nguồn

1. Xác định tài liệu chuẩn thuộc module/layer nào; mô tả lại đầu vào, đầu ra, lỗi và đường test thực.
2. Ghi `as_of_commit` và thời điểm đối chiếu; không sửa hồi tố tài liệu lịch sử thành “đã hoàn thành”.
3. Nếu thay đổi giao thức/đơn vị/nguồn dữ liệu, cập nhật tài liệu hợp đồng và kiểm thử cùng PR.
4. Nếu có kết quả HMI/native mới, ghi vào hồ sơ nghiệm thu có đường dẫn receipt thật; không sửa README thành “PASS tổng thể” trước khi duyệt.
5. Khi đổi đường dẫn tài liệu, cập nhật Markdown, gate và test cùng một thay đổi; giữ bản gốc trong Git.

**Đặc tả thiết kế:** [Kiến trúc tài liệu DOC-02](standardization/DOC02_KIEN_TRUC_TAI_LIEU.md). Đây là tài liệu quy định cách viết và chuyển đổi, **không** phải nơi đọc kiến trúc runtime ScanToPath.

## Cập nhật cuối 28/10/2026: GĐ1 đã đóng

`GD1_08_06_6_FINAL_CLOSURE_20261028`: các dòng trạng thái “GĐ1 pending” phía trên phản ánh snapshot DOC-04/DOC-06 trước buổi nghiệm thu. Chủ dự án chốt **GĐ1 CLOSED_ACCEPTED_WITH_EXPLICIT_WAIVERS**; NT-01, GPU/VRAM measured và input-to-physical-present latency không có PASS đo thực. Chi tiết tại [GD1 acceptance](07-nghiem-thu/GD1_ACCEPTANCE.md#7-quyết-định-đóng-gđ1-ngày-28102026). Không khởi động GĐ2 hoặc công bố tính năng mới chỉ vì merge.
