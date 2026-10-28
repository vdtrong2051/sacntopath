# R7-B — Các vấn đề còn cần đối chiếu

Các mục sau **không được tự gán PASS** khi chỉ tổ chức lại tài liệu:

| Mã | Nội dung | Hướng xử lý |
|---|---|---|
| R7B-01 | Roadmap/tài liệu lịch sử có giả định camera cầm tay, một số ghi chú khác nói đến cơ cấu quét | Chốt phần cứng hiện hành bằng quyết định và tài liệu nguồn mới hơn; **R7-B không tự thay giả định nghiên cứu** |
| R7B-02 | Mốc trạng thái R7 trong `docs/INDEX.md` cũ không còn phù hợp với Git | Dùng `docs/README.md` làm cổng hiện hành, giữ trang cũ chỉ để tương thích |
| R7B-03 | Nhiều thế hệ tài liệu Viewer/Project giải thích cùng một phần mềm | Hồ sơ cũ chuyển `archive/`; một trang module hiện hành tiếng Việt |
| R7B-04 | Các liên kết trong báo cáo lịch sử có thể đã hỏng **trước** R7-B | Ghi rõ từng link lỗi còn lại trong receipt; không bịa file đích |
| R7B-05 | Đường dẫn cũ có thể nằm trong tài liệu/công cụ bên ngoài repository | Duy trì bản đồ chuyển đổi; không cam kết sửa những URL đã gửi ở nơi khác |
| R7B-06 | Quy ước ngôn ngữ trước đây lẫn tiếng Anh/Việt | Tài liệu hiện hành viết tiếng Việt; lịch sử bảo toàn nguyên bản |
| R7B-07 | Những ca native-busy, crash C++, DPI và GPU/VRAM chưa có bằng chứng | R6 tổng thể PENDING; không nâng trạng thái chỉ vì R7-B PASS |

Dữ liệu hiện hành kiểm chứng được bằng Git + mã nguồn/bằng chứng; các thông tin không đối chiếu đủ phải giữ trạng thái **CẦN XÁC MINH**.
