# Mô-đun lưu trữ RAW và bảo toàn nguồn gốc

## Dữ liệu RAW v2

```text
sessions/<session_id>/captures/<capture_id>/
    color.mjpg
    depth.y16
    metadata.json
    manifest.json
    COMMITTED
```

`color.mjpg` lưu byte MJPEG, `depth.y16` lưu little-endian `uint16` chưa căn chỉnh. `metadata.json` giữ nguồn, hiệu chuẩn SDK và thời gian từng stream. `manifest.json` chứa độ dài và SHA-256; `COMMITTED` chỉ đánh dấu khi Capture đã ghi xong. Capture v1 vẫn có đường đọc tương thích được kiểm thử.

## Điều kiện bất biến

- Không đổi byte RAW, không tự lọc, nâng cỡ ảnh, nén lại hay chuyển đơn vị ở tầng lưu trữ.
- File thiếu/thừa, sai manifest, hỏng checksum hoặc symlink không hợp lệ phải bị từ chối theo hợp đồng.
- Ghi vào thư mục tạm rồi đổi tên không chứng minh chống mất điện tuyệt đối. SHA-256 phát hiện thay đổi ngoài ý muốn, không thay chữ ký xác thực.
- SQLite chứa đường dẫn tương đối và metadata; filesystem/SQLite không có giao dịch nguyên tử xuyên hai hệ. Nếu đăng ký metadata thất bại, RAW đã commit vẫn giữ để khôi phục bằng thao tác riêng.

## Giao diện lập trình và kiểm thử

`src/scantopath/storage/session_store.py`: các hàm đã ghi nhận gồm `commit_raw`, `read_raw`, `read_capture`; `src/scantopath/metadata/` đăng ký và đọc metadata. Xem `tests/test_raw_storage.py`, `tests/test_pre06_gd0_acceptance.py` và các test registry.

Không suy ra pipeline xử lý 3D từ việc lưu trữ RAW. Tham khảo [Thu nhận](THU_NHAN_RGBD.md), [Quản lý dự án](QUAN_LY_DU_AN.md).
