# DOC-02 — Kiến trúc tài liệu ScanToPath v2 (đặc tả đã chốt cho triển khai)

> **Phạm vi hiệu lực:** thiết kế và quy tắc soạn tài liệu cho DOC-03A/B/C → DOC-04 → DOC-05.  
> **Baseline đối chiếu:** `feat/gd1-desktop-ui@493a24d2ab62cd34e5968cbcb60d5f9857c3c4b8` (R8.5).  
> **Trạng thái:** `DESIGN_LOCKED / CONTENT_MIGRATION_NOT_STARTED`. “Đã chốt thiết kế” **không** có nghĩa 65 tài liệu đã chuyển đổi, mọi mâu thuẫn đã giải quyết, cấu hình cơ khí đã nghiệm thu hay GĐ1 đã đóng băng.  
> **Phạm vi DOC-02:** bổ sung đặc tả, biểu mẫu và kiểm tra truy vết; không sửa runtime, test cũ, README/roadmap, dữ liệu đo, ADR lịch sử hoặc đường dẫn gate R7/R8.

## 1. Bài toán và kết quả cần đạt

Tài liệu ScanToPath tại R8.5 có 64 tệp trong `docs/` (62 Markdown, hai CSV) và `README.md` gốc: 65 đối tượng. Đọc từ README tới một module đang cần các đoạn kiến thức rải ở roadmap, archive, báo cáo từng phiên; một số trạng thái đã lỗi thời. DOC-01 kiểm kê **65 mục, 27 cụm nội dung, 16 hợp đồng kỹ thuật, 20 vấn đề, 7 trang chuyển hướng, 12 hồ sơ quan trọng trong archive** và xác nhận hai liên kết tương đối hỏng trong README.

**Định nghĩa đạt:** người chưa tham gia R4/R5 vẫn hiểu Viewer R5.3 khi chỉ đọc `VIEWER_3D.md`; người sửa RAW hiểu nguồn byte, schema, giới hạn FS/SQLite từ `RAW_STORAGE.md`; người nghiệm thu phân biệt rõ `IMPLEMENTED`, `AUTOMATED_PASS`, `MANUAL_PASS`, `NOT_TESTED`, `WAIVED`. Các chi tiết có thể kiểm chứng bằng source/test/receipt và có ngày. Liên kết tới ADR/evidence để tra cứu chứng cứ, **không** thay cho phần giải thích cần có ngay trong trang chuẩn.

### Không thuộc DOC-02

- Không cập nhật README thành mô tả hiện hành; việc đó thuộc DOC-03A.
- Không tuyên bố thuật toán RAW→point cloud→mesh→Zigzag đã triển khai trong GĐ1 Viewer; GĐ1 hiện có công cụ xem hình học PLY/OBJ, không đồng nghĩa pipeline.
- Không xác nhận bản cơ khí/camera đang lắp chỉ từ kế hoạch ghi trong repository.
- Không di chuyển hoặc xóa 65 file gốc; việc chuyển thư mục, cập nhật redirect và gate thuộc DOC-05.
- Không sửa nội dung ADR hoặc biên bản nghiệm thu theo hướng làm cho lịch sử có vẻ đã đạt từ trước.

## 2. Thứ tự đọc chuẩn và quyền sở hữu thông tin

```
README.md (người mới: hệ thống là gì, có gì, chạy sao)
  └── docs/README.md (bản đồ 4 luồng: hiểu / phát triển / quản trị / nghiệm thu)
      ├── 01-tong-quan + 02-kien-truc  (tầm nhìn, phạm vi, kiến trúc thật)
      ├── 03-modules + 04-phat-trien   (thực thi và bảo trì, mỗi module đủ thông tin)
      ├── 05-quan-ly + 06-giai-doan   (một nguồn task và trạng thái)
      ├── 07-nghiem-thu               (phương pháp và chứng cứ kiểm thử)
      └── 99-lich-su                  (ADR nguyên gốc, sự cố, bản đối chiếu cũ)
```

| Loại câu hỏi | Nguồn chuẩn khi hoàn tất DOC-04/05 | Không được biến thành nguồn chuẩn thứ hai |
|---|---|---|
| Đã triển khai/đang làm/chưa có | `docs/05-quan-ly/TRANG_THAI_DU_AN.md` theo commit/ngày | README chỉ dẫn snapshot rõ thời điểm; roadmap chỉ ghi định hướng |
| ID, owner, blocker, progress từng việc | `docs/05-quan-ly/TASK_REGISTER.md` | Hồ sơ giai đoạn chỉ tổng hợp outcome và danh sách ID |
| Kiến trúc hiện hành, process/thread, ranh giới | `docs/02-kien-truc/KIEN_TRUC_HE_THONG.md` | Hồ sơ R4/R5 là căn cứ lịch sử, không là mô tả runtime hiện tại |
| Hợp đồng dữ liệu RAW, units, frames, provenance | `DU_LIEU_VA_HE_TOA_DO.md` và module nguồn | Một hợp đồng có thể cần giải thích ở hai góc độ; phải có owner chính và không mâu thuẫn |
| Cách sử dụng/sửa một module | Một file trong `docs/03-modules/` | Tài liệu khác chỉ là tham khảo đào sâu và chứng cứ |
| Build, Git, test, code/document style | `docs/04-phat-trien/` | R7/R8 patch note là lịch sử, không hướng dẫn chính |
| Quyết định thiết kế cũ | ADR gốc bất biến tại `docs/99-lich-su/ADR/` | `QUYET_DINH_KY_THUAT.md` ghi trạng thái áp dụng hiện tại, không sửa ADR |
| Kết quả nghiệm thu | `docs/07-nghiem-thu/` và receipt nguồn | Status/README không suy ra HMI PASS từ pytest/CTest |
| Tiến trình từng giai đoạn | `docs/06-giai-doan/GD*.md` | Task detail và evidence raw để trong ledger/index |

**Chủ sở hữu theo vai trò (không tự gán tên người):** Bản đồ 65 dòng có `target_owner`, là vai trò chịu trách nhiệm cập nhật và phê duyệt khi tài liệu đổi: `DOCUMENTATION_OWNER` (cổng vào), `PRODUCT_SCOPE_OWNER` (tầm nhìn/roadmap), `ARCHITECTURE_OWNER`, `MODULE_OWNER:<tên module>`, `ENGINEERING_OWNER` (hướng dẫn và tiêu chuẩn), `PROJECT_COORDINATOR` (task/state), `STAGE_OWNER` (hồ sơ giai đoạn), `ACCEPTANCE_OWNER` (nghiệm thu) và `HISTORY_CUSTODIAN` (lưu trữ). DOC-04 mới xác nhận người cụ thể nếu tổ chức có phân quyền, DOC-02 không tự gán tên cá nhân. Trang đích nhiều nguồn chỉ có **một vai trò owner**; người viết, người kiểm kỹ thuật và người duyệt có thể khác nhau.

**Quy tắc thời gian:** mọi mệnh đề “hiện tại” cần ghi `as_of_commit` và `verified_at`; khi thay đổi source, chủ trang chuẩn phải xác minh lại. Snapshot lịch sử giữ ngày cũ và nhãn `HISTORICAL_SNAPSHOT`, không bị viết lại thành “đã xong”.

## 3. Cây tài liệu v2 chính thức cho các mốc tiếp theo

```text
scantopath-software/
├── README.md                               # Giới thiệu, giới hạn, quick start; 1 entrypoint
└── docs/
    ├── README.md                           # Mục lục theo vai trò, không lặp kỹ thuật
    ├── 01-tong-quan/
    │   ├── GIOI_THIEU_DU_AN.md
    │   ├── PHAM_VI_VA_NANG_LUC.md
    │   └── LO_TRINH_PHAT_TRIEN.md
    ├── 02-kien-truc/
    │   ├── KIEN_TRUC_HE_THONG.md
    │   ├── DU_LIEU_VA_HE_TOA_DO.md
    │   └── CONG_NGHE_VA_PHU_THUOC.md
    ├── 03-modules/
    │   ├── RGBD_ACQUISITION.md
    │   ├── RAW_STORAGE.md
    │   ├── PROJECT_WORKSPACE.md
    │   ├── DESKTOP_UI.md
    │   └── VIEWER_3D.md
    ├── 04-phat-trien/
    │   ├── CAI_DAT_VA_CHAY.md
    │   ├── HUONG_DAN_PHAT_TRIEN.md
    │   ├── TIEU_CHUAN_KY_THUAT.md
    │   └── KIEM_THU_VA_NGHIEM_THU.md
    ├── 05-quan-ly/
    │   ├── TASK_REGISTER.md
    │   ├── TRANG_THAI_DU_AN.md
    │   ├── QUYET_DINH_KY_THUAT.md
    │   └── INCIDENT_REGISTER.md
    ├── 06-giai-doan/
    │   ├── GD0_SOFTWARE_FOUNDATION.md
    │   ├── GD1_DESKTOP_VIEWER.md
    │   └── SESSION_CROSSWALK.md            # Snapshot đối chiếu 20 phiên, không là task
    ├── 07-nghiem-thu/
    │   ├── GD0_ACCEPTANCE.md
    │   ├── GD1_ACCEPTANCE.md
    │   ├── EVIDENCE_INDEX.md
    │   └── records/GD1_R6_ACCEPTANCE_STATUS.md
    └── 99-lich-su/
        ├── README.md
        ├── ADR/                             # ADR gốc bất biến
        ├── JOURNALS/                        # Nhật ký, lần FAIL/PASS, commit gốc
        ├── STANDARDIZATION/                  # R7/R8/DOC-01/DOC-02 snapshots
        ├── ARCHIVE/                          # Giữ đường dẫn con để tránh trùng tên
        └── HO_SO_CU_VA_TRUY_VET.md
```

Chỉ tạo hồ sơ GĐ2–GĐ5 khi bắt đầu giai đoạn tương ứng, **không tạo các trang placeholder giả**. Tên thư mục cố định dùng chữ thường ASCII, tiền tố số cho tuyến đọc; tên file .md uppercase ASCII và `_` như trên (API class/hàm giữ nguyên theo source). Các tệp .csv là phụ lục máy đọc, không phải tài liệu người dùng bắt buộc.

### Điều chỉnh có chủ đích so với DOC-01

- Không đưa `GD1_R6_ACCEPTANCE_STATUS.md` vào `evidence/` như một log thô: đây là **biên bản trạng thái lịch sử**, chuyển đích tới `07-nghiem-thu/records/`; evidence gốc vẫn ở `_setup` ngoài repo.
- Không cắt một đoạn đường dẫn `ARCHIVE/` chung cho 12 hồ sơ: bản đồ 65 dòng chỉ rõ **đường dẫn đích đầy đủ**, giữ cấu trúc con.
- Không đưa mọi vấn đề kỹ thuật thành task Markdown riêng. Task Register tập trung; bản sửa module và nguyên nhân nằm ở module/ADR/incident phù hợp.

## 4. Bốn quy tắc không được phá

**R-01 — Đọc độc lập:** mỗi module trả lời mục đích, trạng thái, input/output (có units/provenance), luồng đầu-cuối, lỗi/cancel/retry, API/source, ví dụ chạy với fixture an toàn, kiểm thử và giới hạn; không chấp nhận một mục chỉ ghi “Xem R4.3”.

**R-02 — Một chủ sở hữu mỗi sự thật có thể thay đổi:** trạng thái hiện hành chỉ nằm trong state ledger; task chỉ nằm trong task ledger; nghiệm thu chỉ nằm trong acceptance; roadmap không copy status mỗi task. Module có thể diễn giải API/invariant nhưng phải nêu ai sở hữu hợp đồng và nguồn kiểm chứng.

**R-03 — Bằng chứng phân tầng:** `implemented_in_git`, `automated_test_pass_operator_reported`, `hardware_measured`, `manual_hmi_pass`, `waived_with_approval` là các loại chứng cứ khác nhau. Không nâng `R6_OVERALL_PENDING` thành PASS khi chỉ có R8.5 commit hoặc `pytest` PASS.

**R-04 — Bảo toàn lịch sử:** giữ nguyên các ADR/receipt/attempt FAIL tại timestamp gốc; nếu cần sửa diễn giải, viết `CORRECTION` có ngày và nguồn. Di chuyển bằng manifest + kiểm tra SHA, không âm thầm “làm sạch” bằng cách xóa cảnh báo.

## 5. Tổ chức giai đoạn và task — không lẫn lộn

| Thành phần | Cấp độ thông tin | Ví dụ đúng | Ví dụ sai |
|---|---|---|---|
| Roadmap | Năng lực theo chặng và phụ thuộc | GĐ2: RAW replay → cloud một góc có provenance | Danh sách 35 bug với trạng thái mỗi ngày |
| Hồ sơ giai đoạn | Scope, deliverables, nghiệm thu, debt | GĐ1: Desktop/Project/Viewer và 08.06.6 chưa đóng | Copy 200 dòng log pytest vào từng chương |
| Task Register | ID, owner, acceptance, blocker, commit, trạng thái | `GD1-08-06-6`, `DOC-03B-VIEWER` | Cứ sửa 1 file thì tạo 1 hồ sơ task riêng |
| State ledger | Snapshot triển khai/kiểm thử theo commit | R8.5 merged/committed, HMI pending | Suy “R8.5 committed” = “GĐ1 overall PASS” |
| Acceptance | Cổng đo, môi trường, receipt và hạn chế | `HMI_DPI_125` = NOT_TESTED tới khi đo | “Qt offscreen PASS” = màn hình DPI 125% PASS |

Một task `DONE` chỉ khi `acceptance_gate` có bằng chứng phù hợp. `BLOCKED` có lý do và nguồn; `WAIVED` không là `PASS`, chỉ tồn tại với người duyệt, phạm vi, ngày và rủi ro còn lại. Task Register là danh sách **trạng thái điều hành**, không chứa raw evidence hay nguồn đo chưa xác minh.

## 6. Trạng thái phần cứng/camera — quyết định mở có kiểm soát

Dữ liệu Git chứng minh acquisition Gemini 2 một-shot và Viewer PLY/OBJ; **không chứng minh cấu hình cơ khí hiện tại**. Một số hồ sơ ghi camera cầm tay, còn thiết kế cơ khí khác có thể chốt sau đó. DOC-02 **không tự quyết định** camera cố định/cầm tay, cơ cấu quay hai trục hay host điều khiển. Trong `DOC02_QUYET_DINH_20.csv`, `DOC01-07` có nhãn `OPEN_REQUIRED_SOURCE_DECISION`.

Trước khi DOC-03A/03B khẳng định cấu hình: cần mốc quyết định kỹ thuật có ngày, phiên bản cơ khí, ảnh/sơ đồ có nguồn và phân biệt `CURRENT_PHYSICAL`, `TARGET_DESIGN`, `HISTORICAL_VARIANT`. Nếu chưa đủ nguồn, viết “chưa xác minh trong baseline Git” và chỉ mô tả chính xác chức năng phần mềm đã được kiểm thử. Không khóa bừa để tài liệu trông hoàn chỉnh.

## 7. Ma trận chuyển đổi 65 tài liệu — chính sách theo loại

Bảng nguồn chuẩn là [`DOC02_BAN_DO_65.csv`](DOC02_BAN_DO_65.csv). Mỗi dòng có ID từ DOC-01, đường dẫn nguồn, loại/ưu tiên, `primary_target` **đầy đủ**, `stage`, `doc02_role` và chính sách lưu giữ. Một số tài liệu cũ cùng hợp nhất thành một nguồn chuẩn mới; đó là nhiều-nguồn→một-đích có chủ ý, **không phải trùng đường dẫn file**. Trước khi DOC-05 xóa/di chuyển, kiểm tra incoming links, gate R7/R8 và bằng chứng đã kế thừa.

| Nhóm | Quyết định DOC-02 | Thời điểm |
|---|---|---|
| `README.md`, `docs/README.md` | Viết lại như hai cổng với trách nhiệm khác nhau | DOC-03A |
| `architecture/` và `modules/` | Chuyển nội dung và hợp đồng vào trang chuẩn tự chứa | DOC-03A/03B |
| `development/` | Hợp nhất quy trình còn đúng, cập nhật runner Quick/Full/Acceptance | DOC-03C |
| `decisions/` | ADR gốc giữ nguyên; chỉ mục quyết định hiện hành mới | DOC-04/DOC-05 |
| `acceptance/`, `history/` | State/task/evidence phân biệt; giữ attempt FAIL, waiver gốc | DOC-04/DOC-05 |
| `standardization/` | Chuyển hồ sơ R7/R8 vào lịch sử, giữ CSV snapshot + SHA | DOC-05 |
| 12 `archive/` hồ sơ | Đưa sang lịch sử tại đường dẫn đích có cấu trúc đầy đủ | DOC-05 |
| 7 trang chuyển hướng | GIỮ nguyên tới DOC-05, quyết định xóa dựa trên actual reference + gate | DOC-05 |

## 8. Truy vết tri thức — 27 cụm và 16 hợp đồng

[`DOC02_TRUY_VET_43.csv`](DOC02_TRUY_VET_43.csv) có 43 dòng (27 `CONTENT`, 16 `CONTRACT`), mỗi dòng định danh chủ đề, file gốc, tài liệu đích, nội dung bắt buộc, quy tắc không được phá, test/bằng chứng và mốc. Không đủ điều kiện đóng DOC-03 chỉ vì file đích tồn tại: **mỗi dòng phải có bằng chứng đã đưa nội dung vào đúng mục**, không chỉ một liên kết đi tới archive. Các hợp đồng `CT-01` tới `CT-16` giữ nguyên số hiệu.

Quy định xác nhận cho DOC-03/04: bổ sung `status=IMPLEMENTED_AND_REVIEWED`, `verified_source_commit`, `section_anchor`, `reviewer_or_operator` bằng commit/receipt thực, nếu không giữ `PENDING_CONTENT_MIGRATION`. Không tự dùng chữ `PASS` cho các mục chưa viết hoặc chưa kiểm thử.

## 9. Mâu thuẫn DOC-01 — xử lý theo chủ sở hữu, không ghi đã sửa

[`DOC02_QUYET_DINH_20.csv`](DOC02_QUYET_DINH_20.csv) có 20 vấn đề. Trong đó một vấn đề **cần quyết định nguồn riêng** (`DOC01-07` về cơ cấu/camera), hai vấn đề chốt nguyên tắc tổ chức tài liệu (`DOC01-19`, `DOC01-20`), phần còn lại **đã chốt hướng xử lý nhưng chưa sửa văn bản**. Các lỗi README, công nghệ Viewer, ADR-002, test path cũ, nghiệm thu `R8 NOT_STARTED`, v.v. thuộc DOC-03/04/05 theo `owner_stage`.

Mức ưu tiên P0 thể hiện độ ảnh hưởng, không đồng nghĩa đã kiểm chứng điều kiện vật lý. Các quyết định có thể đổi nếu xuất hiện nguồn mới, nhưng phải ghi thay đổi có căn cứ và cập nhật ma trận; không chỉnh âm thầm.

## 10. DOC-03A/B/C, DOC-04 và DOC-05 — quy tắc bàn giao

1. **DOC-03A** (README/tổng quan/kiến trúc): xác minh HEAD trước khi viết, diễn giải trạng thái thực, sửa 2 link README, phân biệt GĐ1 Viewer với pipeline mục tiêu; nếu cơ cấu còn mở thì không khẳng định cấu hình.
2. **DOC-03B** (5 modules): tối thiểu 13 mục theo template; 16 hợp đồng phải tới đúng trang module/architecture/test; đường dẫn source/test tra lại theo HEAD sau R8.2; các ví dụ không tự mở camera hoặc migrate DB người dùng.
3. **DOC-03C** (sổ tay): lệnh Windows có kiểm tra exit code, chuẩn Git/patch, code/document, unified test Quick/Full/Acceptance; mô tả fail của CTest/JUnit, HMI pending.
4. **DOC-04** (quản trị): tạo `TASK_REGISTER` và `TRANG_THAI_DU_AN` thành nguồn sống; cập nhật ADR-index, giai đoạn GD0/GD1 và Acceptance với bằng chứng; nối lịch sử R7/R8 bằng đính chính/append, không ghi đè.
5. **DOC-05** (chuyển cấu trúc): kiểm kê repo + link inbound; cập nhật/củng cố `scripts/r7_docs_gate.py` đang hardcode `docs/INDEX.md` và alias cũ, test R7/docs, script R8.5 trước khi đổi path; duy trì rollback theo SHA; chạy `scripts/verify.ps1 -Profile Full` trên Windows, không tự chứng nhận HMI.

### Điều kiện chặn chuyển giai đoạn

- Không bắt đầu DOC-05 khi nội dung P0 của DOC-03/04 chưa được kế thừa và duyệt.
- Không xóa alias trước khi gate/URL trong repo và ngoài repo được đánh giá; có thể quyết định giữ alias vĩnh viễn nếu chi phí phá tương thích lớn hơn lợi ích.
- Không nâng kết quả `R6_OVERALL_PENDING`, `08.06.6` hay `NOT_TESTED` thành PASS vì sửa tài liệu.
- Không tự tạo tài liệu module cho geometry/AI tương lai khi chưa có source và kiểm thử tương ứng.

## 11. Tiêu chuẩn nghiệm thu DOC-02 (chỉ kiến trúc)

- `65` dòng bản đồ unique ID/path; mỗi đích là đường dẫn tương đối an toàn trong repo; đủ 7 alias và đường dẫn đích của 12 hồ sơ; `43` dòng trace (27+16); `20` issue (đúng ID).
- Có template mô tả đầu vào/đầu ra, errors, lifecycle, API, test, limitation, source/evidence cho module; có template task, status, ADR, acceptance và giai đoạn.
- Kiểm tra cấu trúc bằng công cụ tĩnh `scripts/check_doc02_architecture.py` và test tương ứng; không đụng data/runtime/src/CPP hay README.
- R7/R8 docs gates và regression vẫn giữ nguyên khi áp patch. Kết quả Windows chưa chạy phải ghi `NOT_TESTED`, không tuyên bố đã PASS.
- **DOC-02 được coi là khóa kiến trúc tài liệu cho DOC-03 sau khi operator Windows xác minh/commit gói này.** Việc duyệt nội dung từng trang vẫn thuộc DOC-03/04.
