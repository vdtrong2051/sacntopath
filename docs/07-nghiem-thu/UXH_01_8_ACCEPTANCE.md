# UXH-01.8 — Biên bản nghiệm thu có điều kiện

> `source_head: 016f0cf06de65a432626bb58ec8868483b30eb04` · `creation_state: PENDING_WINDOWS_EVIDENCE`.

## Đối tượng

Closure **chỉ UXH-01.1–01.8** trên nhánh `feat/gd2-uxh-01-hardening`, không mặc định nghiệm thu GD2/GD3 hoặc robotic spray paths.

## Ma trận bằng chứng

| Evidence | Trạng thái khi tạo hồ sơ | Nguồn cần bổ sung |
|---|---|---|
| Git UXH-01.7 commit 15 files | `GIT_VERIFIED` | SHA `016f0cf...` |
| Source inventory & acceptance definition | `SOURCE_REVIEWED` | Các phụ lục UXH-01.8 |
| Windows targeted gates | `NOT_TESTED` | `SUMMARY.json`, JUnit, logs ngoài Git |
| R8.4 Full regression + CTest | `NOT_TESTED` | `R84_.../SUMMARY.json` ngoài Git |
| Gemini 2 real camera | `NOT_TESTED` | H01–H03 receipt |
| HMI DPI/Capture/Viewer/measurement | `NOT_TESTED` | M01–M09 operator manual receipt |
| Reviewer / scope/risk approval | `NOT_APPROVED` | Operator sign-off với evidence locator |

## Quy tắc quyết định

- `PASS` chỉ khi tất cả automated & required hardware/HMI đều PASS, 0 P0 mở; P1 xử lý/waiver rõ từng gate.
- `ACCEPTED_WITH_LIMITATIONS` chỉ khi có **quyết định ký duyệt** nêu rõ gate được waive, risk owner, lý do và phạm vi; không chuyển gate waive thành PASS.
- Nếu thiếu receipt → `PENDING_WINDOWS_EVIDENCE`, được commit **tài liệu kiểm kê** nhưng không được ghi `UXH_01_CLOSED`.

## Closure receipt

Receipt final **không được tạo sẵn**. Runner `FINALIZE_AND_COMMIT.ps1` chỉ tạo `docs/07-nghiem-thu/records/UXH_01_8_FINAL_RECEIPT.md` khi toàn bộ gate và manual receipt đạt, sau đó commit whitelist. File có HEAD gốc, thời điểm, trạng thái và SHA-256 evidence JSON. Full log và dữ liệu vật lý vẫn lưu ngoài Git.

## Chú ý dữ liệu

Không nộp file RAW/SQLite thật, ảnh người dùng, đường dẫn có secrets hoặc SDK binary vào repository. Acceptance summary không có kết quả đo metric/accuracy nếu protocol chưa được chạy.
