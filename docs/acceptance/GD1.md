# Nghiệm thu GĐ1 — Mốc hiện hành và điều kiện còn mở

**Baseline kiểm tra tài liệu:** R7-A `8e37eba`. Không gộp nghiệm thu riêng phần R6 vào nghiệm thu cuối GĐ1.

| Nhóm | Kết quả/giới hạn |
|---|---|
| R5.3 Viewer | Qt live 3D, icon, chọn điểm/mặt, Inspector, lưới; đã commit theo lịch sử Git |
| R6 Python/Qt | 618 PASS / 3 SKIP (symlink privilege) |
| R6 CTest | 2/2 PASS |
| R6 geometry/native/transport/benchmark | 14/14 automated PASS theo log operator |
| R6 tổng thể | **PENDING**, chưa có bằng chứng đầy đủ cho HMI/DPI, native busy/crash, GPU/VRAM, display-present |
| R7-B | Tài liệu/đường dẫn; không sửa runtime |
| R8 | Chưa nghiệm thu, là giai đoạn chuẩn hóa hệ thống test |

Nguồn: [Ma trận R6 chi tiết](GD1_R6_ACCEPTANCE_STATUS.md), [hồ sơ tổng hợp](TONG_HOP_NGHIEM_THU.md), [nhật ký GĐ1](../history/GD1/GD1_EXECUTION_JOURNAL.md).

Cổng cuối GĐ1 **08.06.6** chỉ xét sau R7, R8 và khi các khoản nghiệm thu thiếu đã được xử lý hoặc duyệt ngoại lệ rõ ràng. **Không tự động miễn** những phép thử chưa thực hiện.
