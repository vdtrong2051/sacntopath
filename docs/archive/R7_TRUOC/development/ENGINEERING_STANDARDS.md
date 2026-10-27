# Quy chuẩn kỹ thuật & bảo trì ScanToPath (R7)

**Có hiệu lực từ mốc R7 khi nghiệm thu.** Tối ưu khả năng bảo trì với nhóm nhỏ; không tái cấu trúc toàn bộ dự án chỉ vì hình thức.

## 1. Kiến trúc nguồn

- Feature-oriented modular monolith; `domain → application → infrastructure / presentation` theo phụ thuộc được kiểm thử. Qt UI không phụ thuộc trực tiếp vào render engine, SQLite, OrbbecSDK.
- `ui/shell/main_window.py` là composition root; Presenter chịu điều phối, application service chịu use-case, infra chịu native/IO.
- Giữ một Inspector chung; không tạo cửa sổ thuộc tính thứ hai thiếu nguồn.
- Trước khi xóa/move facade: `git grep`, AST imports, dynamic calls và regression; không chuyển nợ kỹ thuật thành assertion test cứng vĩnh viễn.

## 2. Docstring và comment (R7.1)

- **Module docstring:** vai trò hiện hành + ranh giới an toàn, không ghi trạng thái lịch sử như sự thật vĩnh viễn.
- **Public function/method:** input, output, error contract, side effects, ownership/lifetime khi không hiển nhiên. **Native/IPC/transaction:** lý do timeout, owner-thread, ACK, rollback, SHA, scene revision.
- Tránh chú thích chỉ lặp lại lệnh; tránh comment-out dead code; không xóa comment safety khi chưa có test thay thế.
- Khi gặp lỗi cũ, ghi incident trong `docs/history/`, không kéo toàn bộ console log vào source.
- **Trong patch R7.1:** chỉ chỉnh docstring module ở `main_window.py` và `interactive_controller.py`; AST phần thực thi phải giữ nguyên 100%. Các file khác ghi danh sách ưu tiên cho sau R8; không tự động xóa hàng loạt chú thích.

## 3. Quy trình thay đổi

1. Git branch/ref sạch, source SHA đã kiểm và backup ngoài repo trong `_setup`.
2. Một patch định danh, phạm vi file tối thiểu. `apply.ps1` chỉ ghi vào danh sách cho phép; không commit.
3. `verify.ps1`: doc gate, focused tests, architecture/quality, `git diff --check`; khi cần full pytest + CTest (Release).
4. Lỗi → incident ID, root cause hoặc trạng thái chưa xác minh; sửa; chạy lại. **Không xóa nhật ký fail trước đó.**
5. HMI đúng Windows với 100/125/150% nếu có thay đổi UI; offscreen không tương đương HMI.
6. Publish chỉ sau operator duyệt và evidence; không merge `main` tự động.

## 4. Bảo toàn R6

Windows log operator: 618 PASS, 3 symlink SKIP, CTest 2/2, native R5.3/benchmark PASS, 14/14 automated gates. Đóng-native-đang-bận thật, crash C++, display present, GPU/VRAM và DPI vẫn **OPEN/NOT_TESTED**. Không gọi R6 overall PASS chỉ vì R7 test xanh.

**Nguồn:** [R6 ma trận](../../../acceptance/GD1_R6_ACCEPTANCE_STATUS.md) · [R7 chính sách tài liệu](R7_DOCUMENTATION_POLICY.md).
