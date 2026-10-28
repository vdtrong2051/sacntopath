# DOC-03C — Truy vết sổ tay phát triển và bàn giao

> `owner: ENGINEERING_OWNER` · `as_of_commit: a847faebe54050cd6f8bc42cc882b3927ddabfe2` · `verified_at: 2026-10-28`  
> **Trạng thái:** `CONTENT_PREPARED / WINDOWS_OPERATOR_VERIFICATION_PENDING`. Đây là biên bản xây dựng gói, **không** phải receipt PASS Windows. Không thay đổi `src/`, `cpp/`, các script R7/R8 hiện hành, tài liệu lịch sử, dữ liệu hoặc hồ sơ nghiệm thu.

## 1. Phạm vi đúng DOC-02

Bốn trang mới theo cây DOC-02, **chưa di chuyển** `docs/development/` cũ:

| Đích chuẩn | Nội dung có thể thao tác | Nguồn đối chiếu |
|---|---|---|
| [`CAI_DAT_VA_CHAY.md`](../04-phat-trien/CAI_DAT_VA_CHAY.md) | Windows mới, Python 3.12/Qt/VTK, CMake C++20, viewer và SDK opt-in, CLI side effects, troubleshooting | `pyproject.toml`, `cpp/CMakeLists.txt`, `src/scantopath/ui/main.py`, `docs/development/HUONG_DAN_CAI_DAT.md` |
| [`HUONG_DAN_PHAT_TRIEN.md`](../04-phat-trien/HUONG_DAN_PHAT_TRIEN.md) | Định vị module, walkthrough Viewer/RAW/Project, debug, Git/ZIP, scope + rollback | `src/scantopath/`, `docs/03-modules/`, `docs/development/QUY_TRINH_GIT.md` |
| [`TIEU_CHUAN_KY_THUAT.md`](../04-phat-trien/TIEU_CHUAN_KY_THUAT.md) | Naming, contracts, Qt thread/native, RAW/SQLite, chú thích, tài liệu provenance | `docs/development/QUY_CHUAN_CODE.md`, `QUY_TAC_TAI_LIEU.md`, `DOC02_KHUON_MAU_VA_TIEU_CHI.md` |
| [`KIEM_THU_VA_NGHIEM_THU.md`](../04-phat-trien/KIEM_THU_VA_NGHIEM_THU.md) | Quick/Full/Acceptance, step R8.4, JUnit/SKIP, CTest, HMI/manual và triage fail | `scripts/verify.ps1`, `scripts/r8_4_verify.py`, `scripts/check_qt_acceptance_xml.py`, `docs/development/QUY_TRINH_KIEM_THU.md` |

Có thêm một cập nhật **điều hướng giới hạn** trong `docs/README.md` (giữ nguyên mốc `as_of_commit` DOC-03A để không phá hợp đồng cũ); một checker `scripts/check_doc03c_content.py` và test `tests/contracts/tai_lieu/test_doc03c_content.py`. Không thay source app. Gói thực tế ở `_setup` ngoài repository có backup/manifest + `apply.ps1`, `verify.ps1`, `rollback.ps1`.

## 2. Truy vết bản đồ DOC-02

Các nguồn `DOC-031` đến `DOC-036` trong `DOC02_BAN_DO_65.csv` phân phối vào bốn đích chuẩn: cài đặt (031), phát triển (032), tiêu chuẩn code/docs (033–034), Git (035), kiểm thử (036). `DOC-038` (tài nguyên/phụ thuộc) có đích chủ tại `02-kien-truc/CONG_NGHE_VA_PHU_THUOC.md`; DOC-03C chỉ đọc và dẫn tới nguồn chuẩn này, **không tạo bảng nguồn chuẩn thứ hai**. Hai alias `DOC-030`/`DOC-037` giữ cho DOC-05. `DOC-044` (quy ước nhật ký) thuộc DOC-04, không tự sửa lịch sử ở mốc này.

| Bất biến | Trạng thái trong nội dung mới | Cách đối chiếu |
|---|---|---|
| Build thường không cần OrbbecSDK | Được giải thích | CMake flags mặc định OFF |
| Camera `--once` là opt-in | Được cảnh báo | `acquisition/capture_once.py` |
| Metadata CLI có thể tạo SQLite mới | Được cảnh báo | `metadata/cli.py`, `metadata/store.py` |
| Qt offscreen khác HMI present thực | Được phân tầng | `r8_4_verify.py`, hồ sơ R6 |
| Full cần pytest+JUnit+CTest | Được ghi lệnh và xử lý lỗi | `scripts/verify.ps1`, `r8_4_verify.py` |
| 3 symlink SKIP không thành PASS | Được giữ nguyên | `check_qt_acceptance_xml.py`, R8.3 |
| R8.5 audit không xóa file | Được giữ nguyên | `r8_5_audit.py` |
| R7 alias/ADR/acceptance chưa chuyển | Giữ nguyên, không đụng | `docs/development/`, `docs/acceptance/`, `docs/archive/` |
| `source code` ≠ `automated PASS` ≠ `MANUAL PASS` | Được giải thích | R6 pending và DOC-02 policy |

## 3. Cổng nghiệm thu và giới hạn

1. **Checker DOC-03C:** bốn trang có provenance/giới hạn/lệnh hữu ích, link nguồn/test tồn tại, mapping của DOC-02 có đủ các đích, portal dẫn tới v2. Báo cáo JSON tạo **ngoài repo**.
2. **Targeted pytest:** test mới của checker không yêu cầu Qt/camera/SQLite.
3. **Full Windows:** chạy `scripts/verify.ps1 -Profile Full` qua pack `verify.ps1 -FullRegression`, đọc `SUMMARY.json`; chưa chạy trong môi trường tác giả gói, không ghi PASS.
4. **Operator review:** đọc từ sổ tay và tự thực hiện một flow: cài `.venv`, mở desktop; định vị lỗi PLY; tìm đúng `JUNIT_POLICY`, `CTEST_RELEASE`, và cảnh báo CLI nguy hiểm. Nếu không hiểu độc lập, ghi FAIL nội dung và sửa trước commit.

**Giới hạn:** không thể xác thực MSVC/SDK/GPU/DPI/CTest từ môi trường biên soạn. `as_of_commit` là baseline source, không phải dấu đóng GĐ1. Việc di chuyển 7 alias, đổi gate R7/R8, xây task/state/evidence ledger và cấp quyết định cơ khí đang mở thuộc DOC-04/05 hoặc nhiệm vụ khác; không ghi là đã hoàn thành. Sau operator Windows PASS, commit/push là hành động riêng do operator quyết định.
