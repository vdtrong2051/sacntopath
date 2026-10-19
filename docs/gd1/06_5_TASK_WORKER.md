# GĐ1 — 06.5: Worker & Task Management

**Source:** nhánh `feat/gd1-desktop-ui`, commit `32b9306583b9ff801b1d416a4d77c95efd031e94` (06.4 đã được push).

**Scope:** thực thi hệ thống tác vụ nền cho UI qua một hàng đợi giới hạn, báo tiến độ, hủy hợp tác, báo lỗi, đóng ứng dụng an toàn. Mọi văn bản hiển thị cho người dùng bằng tiếng Việt. **Không** mở SQLite, camera, RAW, VTK hoặc AI, không thay QSS toàn cục.

## Thay đổi

- `application/tasks/manager.py`: một worker Python **non-daemon** được khởi tạo khi có job đầu tiên; `max_pending=2`, lịch sử tối đa 64 mặc định; task status từ `TaskSnapshot` 06.2. Không có thư viện Qt trong tầng này.
- `ui/tasks/controller.py`: bridge bằng `QTimer` đọc trạng thái mỗi 80 ms ở GUI thread. Worker tuyệt đối không thao tác QWidget, không tự phát Qt signals. `snapshots_changed`, `notice`, `stopped` phát từ GUI thread.
- `ui/components/task_event_panel.py`: nút **Chạy tác vụ KIỂM THỬ** và **Yêu cầu hủy tác vụ**; bảng có trạng thái/tiến độ/ID, lưu lựa chọn khi cập nhật; dữ liệu hiển thị là snapshot UI **không phải** `ProcessingRun` bền vững của SQLite.
- `ui/shell/main_window.py`: nối nút, bảng, status và thông báo; sử dụng `closeEvent` không chặn event loop. Không thay thiết kế QSS ở 06.3/06.4.
- `tests/test_gd1_06_5_core.py`, `tests/test_gd1_06_5_qt.py`: headless + Qt test.

## Hợp đồng chạy và hủy

1. `TaskManager.submit(title, func)` trả task ID; một worker chạy lần lượt, hàng đợi giới hạn 2 tác vụ chờ; nếu đầy báo `TaskQueueFull`, không âm thầm thả task.
2. `TaskContext.report_progress(p)` chỉ nhận số hữu hạn `[0, 100]` hoặc `None` để biểu diễn không biết tiến độ. `None` không thành phần trăm giả.
3. `TaskManager.cancel(task_id)` trên `QUEUED` hoàn thành ngay là `CANCELLED`. Với `RUNNING`, trả thành công cho **yêu cầu**, nhưng state vẫn là `RUNNING` và chỉ thành `CANCELLED` sau khi worker trả về/nhận `TaskCancelled`.
4. `shutdown(timeout=0)` dừng nhận job, yêu cầu hủy mọi job đang chờ/chạy và trả ngay; nếu thread chưa thoát trả `False`.
5. Khi đóng cửa sổ mà worker còn chạy, `closeEvent` được trì hoãn thay vì chặn GUI. Qt polling tiếp tục cho tối đa 3 giây; khi worker dừng sẽ tự đóng. Nếu chưa dừng, cửa sổ vẫn mở và ghi cảnh báo; **không kill thread**.
6. Lỗi trong job chuyển sang trạng thái `FAILED`; UI chỉ hiển thị tên kiểu lỗi đã giới hạn, không phát tán nguyên văn exception chứa path/secret.
7. Job demo cố ý kéo dài khoảng 1,8 giây và không đọc/sửa dữ liệu thực. Các chức năng Project/RAW/ProcessingRun và pose/metric/AI vẫn chưa được kết nối.

## Nghiệm thu

- Headless mới: 17 test (success/failure, full queue, cancellation queued/running, shutdown, invalid/unknown progress, bounded history, no thread on import).
- Qt mới: 10 test (phím/nút, timer, cancel, full queue, GUI responsiveness, GUI-thread signals, closure and exception surface).
- Chạy full Python regression; CTest 2/2; native self-test import/buffer ownership, không cần camera.
- **Các kiểm thử trên Windows phải do operator chạy**, không đánh dấu pass ở đây. Qt offscreen không thay thế smoke cửa sổ thực.
- Bảo toàn các kiểm thử 06.2–06.4 và PRE-01–06; kiểm tra `git diff --check`, chỉ 9 tệp (2 sửa, 7 mới).
- Giữ nguyên nhánh hiện hành. Không merge trước nghiệm thu GĐ1. QSS theo yêu cầu người dùng sẽ bàn **sau 06.5**, tách khỏi bước nghiệp vụ.

## Dừng triển khai khi thiếu chứng cứ

Các job C++ native hoặc camera có thể không hỗ trợ hủy ngay; không gắn chúng vào executor 06.5 khi chưa có hợp đồng cancellation/lifetime thích hợp. Worker chung này không chứng minh an toàn của OrbbecSDK hay VTK lifecycle.
