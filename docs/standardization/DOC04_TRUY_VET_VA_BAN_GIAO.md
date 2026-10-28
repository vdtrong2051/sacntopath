# DOC-04 — Truy vết quản trị, giai đoạn, quyết định và nghiệm thu

> `owner: PROJECT_COORDINATOR` · `as_of_commit: 81da5d2050324b1dc4a65ffbca9a38ed1ebba10a` · `verified_at: 2026-10-28`  
> `scope: DOC-04, nội dung docs-only, không di chuyển lịch sử` · `source-of-truth: DOC-02 mapping/trace + source Git + hồ sơ PRE-06/R6/R8` · `evidence_level: SOURCE_REVIEWED; WINDOWS_VERIFY_PENDING`

## 1. Phạm vi và sản phẩm

DOC-04 tạo đúng 4 trang `docs/05-quan-ly/` (Task Register, State Ledger, Technical Decision Index, Incident Register), 3 trang `docs/06-giai-doan/` (GĐ0/GĐ1, Session Crosswalk) và 4 trang `docs/07-nghiem-thu/` (GĐ0/GĐ1 acceptance, Evidence Index, R6 snapshot trong `records/`). Cập nhật điều hướng `docs/README.md`, bổ sung quy tắc ghi nhật ký vào `04-phat-trien/TIEU_CHUAN_KY_THUAT.md`, tạo `scripts/check_doc04_content.py` và test `tests/contracts/tai_lieu/test_doc04_content.py`.

**Giữ nguyên:** `src/`, `cpp/`, CMake, `pyproject.toml`, SQLite/RAW, cả `docs/acceptance/`, `docs/history/`, `docs/decisions/` và `docs/archive/`; toàn bộ test/runner R7/R8 cũ. Bảy alias, source historical, rename `99-lich-su` và thay đổi R7 gate là DOC-05. Không tự commit/push.

## 2. Truy vết theo DOC-02

| DOC-02 nguồn / content contract | Nơi kế thừa | Quy tắc bảo vệ |
|---|---|---|
| `DOC-004`, `CW-02` — roadmap tách task | `05-quan-ly/TASK_REGISTER.md`, `06-giai-doan/SESSION_CROSSWALK.md`; roadmap chuẩn vẫn `01-tong-quan/LO_TRINH_PHAT_TRIEN.md` | Không chép task status vào roadmap |
| `DOC-005`, `DOC-006`, `DOC-008`, `CW-23/26`, `CT-15` | `07-nghiem-thu/GD0_ACCEPTANCE.md`, `GD1_ACCEPTANCE.md`; `05-quan-ly/TRANG_THAI_DU_AN.md` | 14/14 R6 automated reported ≠ manual/overall PASS |
| `DOC-027..029`, `CW-21` | `05-quan-ly/QUYET_DINH_KY_THUAT.md` | ADR-001/002 không sửa; hardware `OPEN_REQUIRED_SOURCE_DECISION` |
| `DOC-039..043`, `CW-25` | `05-quan-ly/INCIDENT_REGISTER.md`, `07-nghiem-thu/EVIDENCE_INDEX.md`, links tới journal gốc | Không xoá lần FAIL, runner defect khác runtime defect |
| `DOC-044` | Appendix quy tắc journal tại `04-phat-trien/TIEU_CHUAN_KY_THUAT.md` | Quy tắc đính chính, phân biệt Git/operator/waiver |
| `DOC-045`, `DOC-054`, `CW-24` | `06-giai-doan/*`, crosswalk + dẫn tới history (chưa di chuyển) | Mapping phiên cũ→mới không là completion |
| `DOC01-03/04/10/13/14/16` | ledger, ADR index, gates, crosswalk và handover | Sửa cách trình bày tại nguồn mới, không hồi tố file cũ |

Riêng `DOC-055` (technology scope) thuộc owner `ARCHITECTURE_OWNER`, canonical `02-kien-truc/CONG_NGHE_VA_PHU_THUOC.md` đã biên soạn DOC-03A; DOC-04 không tạo bảng công nghệ thứ hai. `DOC-027/028` có đích vật lý DOC-05 `99-lich-su/ADR/`, tại DOC-04 chỉ nối về file ADR gốc.

## 3. Giải quyết mâu thuẫn quan trọng

- **PRE-06:** summary GĐ0 ghi 80 PASS/1 SKIP, còn PRE-06 gốc ghi 74/1 là log đã chạy trước patch và 80/1 là kết quả kỳ vọng; chưa có receipt cuối được truy xuất, nên ghi rõ khác biệt thay vì biến kỳ vọng thành PASS.
- **R8:** các hồ sơ R7-A cũ ghi “R8 chưa làm” là **snapshot lịch sử**, nhưng Git đã có code R8.5 `493a24d` và commit DOC-03C `81da5d2`. Trạng thái hiện hành tách implementation Git khỏi Full Windows receipt và final HMI.
- **ADR-002:** dòng ngày 19/10 ghi pending là tình trạng tại ngày soạn; current index nêu registry/migration code có rồi, nhưng bảo toàn nguyên văn ADR.
- **08.06.5:** waiver cho TC11/TC12 và giới hạn render không miễn cổng 08.06.6; final manual remains `NOT_TESTED` hoặc `PARTIAL_EVIDENCE`.
- **Hạ tầng thử nghiệm:** `scripts/verify.ps1 -Profile Full` cùng JUnit/CTest là bắt buộc; không sửa các test R7/R8 để hợp thức hóa tài liệu.
- **Nguồn phần cứng:** các phiên bản handheld/rig trong tài liệu khác nhau theo thời gian; DOC-04 không tự xác nhận cơ cấu vật lý mới khi chưa có ADR ký.

## 4. Các mức nghiệm thu DOC-04

1. **Content/structural:** `python -X utf8 scripts/check_doc04_content.py --project-root <repo> --out-dir <outside>` phải PASS; kiểm 11 docs, các mã task/state/ADR/incident/evidence, Markdown link/path, DOC-02 mapping và nguồn test chính.
2. **Focused tests:** `python -m pytest -q tests/contracts/tai_lieu/test_doc04_content.py` PASS. Test gate không mở camera/SQLite, không đọc dữ liệu người dùng.
3. **Full:** `scripts/verify.ps1 -Profile Full` trên Windows, dùng evidence ở `_setup` ngoài repo. R7/R8 gate + pytest + JUnit policy + CTest Release cần PASS; không skip cổng chỉ do docs thay đổi.
4. **Operator usability:** người mới tìm task mở GĐ2, trạng thái R8/GĐ1, quyết định ADR-002, incident runner R6 và danh sách HMI 08.06.6 từ cổng docs/README trong tối đa hai bước. Đánh dấu FAIL nội dung nếu thiếu giải thích thay vì sửa test.

**Trạng thái lúc tạo pack:** `PACK_PREPARED / WINDOWS_OPERATOR_VERIFICATION_PENDING`. Thực tế apply và verify cần máy Windows do user vận hành; chưa có receipt mới, chưa có commit DOC-04. Không dùng kết quả thử checker ở fixture môi trường đóng gói làm Windows Full PASS.

## 5. Bảo toàn và bàn giao DOC-05

Sau khi nghiệm thu DOC-04, DOC-05 mới có quyền di chuyển bản cũ sang `99-lich-su/`, rà soát incoming link/gate hardcoded và xoá redirect nếu được chứng minh an toàn. Hãy giữ `docs/INDEX.md`, `docs/architecture/CURRENT_GD1_ARCHITECTURE.md`, `docs/modules/VIEWER3D.md`, `docs/modules/PROJECT_WORKSPACE.md`, các hồ sơ acceptance/R6 và các văn bản ADR nguyên trạng tới lúc đó. Chuyển đổi đường dẫn không cho phép thay assertion cũ chỉ để gate xanh.
