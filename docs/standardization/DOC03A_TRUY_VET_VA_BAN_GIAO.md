# DOC-03A — Biên bản truy vết nội dung và bàn giao sang DOC-03B/C

> `as_of_commit: 7a0df7c5b596ff8750bf91f47310067c53a8b204` · `verified_at: 2026-10-28` · `owner: DOCUMENTATION_OWNER`  
> `status: CONTENT_DRAFTED / WINDOWS_REGRESSION_PENDING / REVIEWER_APPROVAL_PENDING`. DOC-03A không thay đổi runtime, test cũ, trạng thái HMI hoặc cơ cấu quét.

## 1. Phạm vi đã viết lại

| Đích | Nguồn đã đối chiếu | Nội dung bắt buộc được kế thừa |
|---|---|---|
| `README.md` | README R7, `pyproject.toml`, Qt entrypoint, DOC-02 | Tám mục; quick start thực; giới hạn pipeline và HMI |
| `docs/README.md` | DOC-02 architecture lock | Tuyến đọc theo vai trò và trạng thái từng bộ đang chuyển |
| `docs/01-tong-quan/GIOI_THIEU_DU_AN.md` | README/roadmap, source Qt/Viewer/RAW | Bài toán, đối tượng, sản phẩm hiện tại, giới hạn nghiên cứu |
| `docs/01-tong-quan/PHAM_VI_VA_NANG_LUC.md` | Source modules, acceptance R6 | Ma trận năng lực theo implementation/auto/manual |
| `docs/01-tong-quan/LO_TRINH_PHAT_TRIEN.md` | Roadmap UI-first và crosswalk | GĐ0–GĐ5, phụ thuộc và tiêu chí khác biệt |
| `docs/02-kien-truc/KIEN_TRUC_HE_THONG.md` | Qt shell, Project service, Render Host, storage | Ba luồng thực thi, ownership, shutdown, các lỗi điển hình |
| `docs/02-kien-truc/DU_LIEU_VA_HE_TOA_DO.md` | RAW v2 metadata, SessionStore, SceneDescriptor | CT-02, CT-12; nguồn, unit/frame/provenance và ví dụ đổi đơn vị |
| `docs/02-kien-truc/CONG_NGHE_VA_PHU_THUOC.md` | `pyproject.toml`, `cpp/CMakeLists.txt` | Đang khai báo/đang dùng/planned; lệnh Windows an toàn |

## 2. Đối chiếu DOC-02 (không sửa ma trận khóa)

| ID | Đích đã có nội dung | Mức đánh giá |
|---|---|---|
| CW-01 | `README.md`, `GIOI_THIEU_DU_AN.md` | `DRAFT_COMPLETE`, chưa phê duyệt Windows |
| CW-03 | `PHAM_VI_VA_NANG_LUC.md` | `DRAFT_COMPLETE`, chưa có state ledger DOC-04 |
| CW-04 | `KIEN_TRUC_HE_THONG.md` | `DRAFT_COMPLETE`, source code đã đối chiếu |
| CW-05 | `DU_LIEU_VA_HE_TOA_DO.md` | `DRAFT_COMPLETE`, chưa có GĐ2 metric validation |
| CW-06 | `CONG_NGHE_VA_PHU_THUOC.md` | `DRAFT_COMPLETE`, không coi planned là installed |
| CT-02 | `DU_LIEU_VA_HE_TOA_DO.md` | `DRAFT_COMPLETE`, đồng bộ bổ sung ở DOC-03B/RGBD |
| CT-12 | `DU_LIEU_VA_HE_TOA_DO.md` | `DRAFT_COMPLETE`, giữ measured ≠ metric_validated |
| CT-01, CT-03–CT-11 | Các module `docs/03-modules/` | `PENDING_DOC03B`, không tự đánh dấu hoàn thành |
| CT-13–CT-16 | Quy định thuộc DOC-03B/C/04 | `PENDING_LATER_STAGE`; đối chiếu DOC-02 chính thức |

Không chuyển trạng thái `PENDING_CONTENT_MIGRATION` của tài liệu DOC-02 khóa chỉ bằng sự tồn tại của trang đích. Quyết định duyệt nội dung cuối và xác nhận người kiểm chứng cần bằng chứng riêng ở DOC-03/04.

## 3. Các ràng buộc có chủ ý

- **Giữ nguyên** 7 alias R7 và các hồ sơ PRE/R4/R5; DOC-05 mới quyết định đổi đường dẫn sau khi rà soát inbound links/gates.
- README giữ nguyên **chuỗi liên kết tương thích** `[Tài liệu GĐ1 hiện hành](docs/INDEX.md)` để không làm sai R7 docs gate ở giai đoạn chuyển đổi.
- Không sửa `docs/ROADMAP.md`, `docs/acceptance/` hoặc ADR; việc cập nhật status nguồn sống/hồ sơ giai đoạn thuộc DOC-04.
- Cấu hình cơ khí/camera hiện hành vẫn có nhãn `OPEN_REQUIRED_SOURCE_DECISION` vì Git không chứng minh bản lắp vật lý; không lấy phương án cầm tay lịch sử để phủ nhận phương án cố định mới.
- Lệnh camera thật/migrate database không được chạy trong DOC-03A; ví dụ quick-start chỉ cài package/mở desktop.

## 4. Điều kiện chốt DOC-03A

1. Đúng 2 tài liệu sửa (`README.md`, `docs/README.md`) và 6 trang kỹ thuật thêm; không di chuyển file cũ.
2. Kiểm tra relative links trong 8 trang, đường dẫn source/test có thật trong Git baseline; R7 compatibility link giữ nguyên.
3. Nội dung không tự nhận pipeline RAW→mesh→Zigzag hoặc nghiệm thu HMI; có `as_of_commit`, `verified_at`, hạn chế và nguồn.
4. `scripts/check_doc03a_content.py` PASS; focused pytest PASS; unified Full (R7/R8/DOC02 và CTest) PASS trên Windows trước commit.
5. Người vận hành đọc để kiểm tra tính hiểu được, đặc biệt giải nghĩa 3 luồng: Camera→RAW, Project→SQLite, PLY→Render Host. Chỉ sau khi người vận hành chấp nhận mới ghi `REVIEWED`.

## 5. Bàn giao tới bước sau

- **DOC-03B:** 5 module với 13 mục/đủ trường hợp lỗi, source/API và test mới; bảo vệ CT-01 tới CT-11.
- **DOC-03C:** sổ tay kỹ thuật Windows, dev Git, cổng regression, các quy chuẩn test/docs.
- **DOC-04:** state/task/ADR ledger, cập nhật tình trạng và nguồn cơ khí, báo cáo nghiệm thu theo giai đoạn.
- **DOC-05:** di chuyển/alias, kiểm tra inbound links, nâng gate cũ đúng hợp đồng; không phá lịch sử.

**Giới hạn:** một bài kiểm tra Markdown/link/static source không chứng minh tài liệu giải thích dễ hiểu với mọi nhóm người đọc. Kết quả Windows phải được operator thực hiện; không có receipt thì giữ `WINDOWS_REGRESSION_PENDING`.
