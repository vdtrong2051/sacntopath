# GĐ0 — Ma trận nghiệm thu Software Foundation

> `owner: ACCEPTANCE_OWNER` · `as_of_commit: 81da5d2050324b1dc4a65ffbca9a38ed1ebba10a` · `verified_at: 2026-10-28`  
> `scope: tái trình bày bằng chứng PRE-06 đã có, không tiến hành camera/test mới` · `source-of-truth: PRE-06 và chứng cứ merge; status sống tại 05-quan-ly` · `evidence_level: HISTORICAL_OPERATOR_REPORTED + GIT_COMMIT_VERIFIED`

## 1. Phạm vi cần chứng minh

GĐ0 nghiệm thu **thu RAW và truy vết dữ liệu**, không phải nghiệm thu Scan-to-Path end-to-end: SDK opt-in, Python/C++ import/buffer, RAW v2 MJPEG/Y16, SHA/checksum/`COMMITTED`, SQLite và một capture Gemini 2 thật. Các lệnh destructive trong PRE-06 chỉ chạy trên **bản sao**. Sau DOC-04 không tự thu ảnh, migrate dữ liệu hoặc xóa SQLite để kiểm tra tài liệu.

## 2. Gate và dữ liệu gốc

| gate_id | expected / method | result trong hồ sơ nguồn | environment / evidence / giới hạn |
|---|---|---|---|
| `GD0-PYTEST` | pytest RAW, metadata, negative fixtures | `PASS` theo operator ở baseline 74/1; **80 PASS / 1 SKIP** là *kỳ vọng* sau thêm 6 tests trong PRE-06, chưa có receipt cuối được DOC-04 kiểm độc lập | [PRE-06](../archive/GD0/PRE/PRE_06_GD0_ACCEPTANCE.md); 1 SKIP privilege symlink, không phải symlink guard PASS; [GD0 summary](../acceptance/GD0.md) nêu mốc 80/1 nhưng gốc PRE-06 chưa kèm log cuối |
| `GD0-CTEST` | `ctest --test-dir build-orbbec -C Release --output-on-failure` | `PASS` 2/2 (core+RGBD contract) theo operator | Không mở camera, không có độ chính xác 3D |
| `GD0-NATIVE` | Python extension import, memory ownership self-test | `PASS` reported, no hardware access in self-test | OrbbecSDK native environment tại Windows operator |
| `GD0-CAPTURE` | `capture_once --once`, lưu và đọc lại byte/hash | `PASS` reported 1 lần Gemini 2, exit 0; color 1920×1080 MJPEG, depth 1280×800 Y16 | `camera_pose_known=false`, `alignment_mode=disabled`, delta timestamp chẩn đoán, không chứng minh exposure sync |
| `GD0-RAW-FAULTS` | corrupt color byte/missing depth trên bản sao phải bị reject | `PASS` expected rejection reported | byte gốc được kiểm lại; không thử bất biến khi đột ngột mất điện |
| `GD0-SQLITE` | CRUD Project/Specimen/Session/Capture/ProcessingRun, audit, FK/integrity | `PASS` reported khi SQLite `integrity_check=ok`, `foreign_key_check=[]` | Run record không tự chạy geometry; DB và RAW không có distributed transaction |
| `GD0-RELEASE` | PR/commit merge mã nguồn + review | `GIT_VERIFIED` PR #3 merge `8bf33591389dcdff82f0fbd5bf5932a22547c984` | Bằng chứng release Git, không là lần test phần cứng mới |

**Ngày/operator:** hồ sơ PRE-06 ghi Windows user evidence 18/10/2026. DOC-04 không có danh tính người ký/receipt path độc lập ngoài liên kết lịch sử; `reviewer_or_operator=OPERATOR_REPORTED_IN_SOURCE`, **không** tự cấp chữ ký GĐ0 mới. Test hiện tại thuộc [sổ tay](../04-phat-trien/KIEM_THU_VA_NGHIEM_THU.md), code nằm trong `tests/integration/metadata/`, `tests/unit/raw/`, `tests/contracts/camera/` theo R8.2.

## 3. Quyết định lịch sử và giới hạn nghiệm thu

PR #3 cho phép dự án chuyển sang GĐ1 theo lịch sử phát triển. Không được suy từ kết quả trên rằng hiệu chuẩn metric, world pose, actual rig trajectory, camera 2-stream exposure sync, crash recovery điện hoặc symlink Windows đã được chứng nhận. Một lần ghi `measured=true` chỉ là **nguồn cảm biến thật**. Tình trạng dự án tại ngày DOC-04 đặt trong [State Ledger](../05-quan-ly/TRANG_THAI_DU_AN.md), task điều phối `GD0-PRE06` ở [Task Register](../05-quan-ly/TASK_REGISTER.md).

## 4. Cách bổ sung evidence

Gắn `gate_id`, `executed_at`, môi trường, cấu hình phiên bản SDK/firmware, command/exit code, JUnit/report/sha và reviewer vào [Evidence Index](EVIDENCE_INDEX.md). Nếu phát hiện hồ sơ gốc có điều kiện bỏ sót, ghi **đính chính có ngày** trong bản mới; không sửa PRE-06 để trông như lúc nào cũng PASS. `NOT_TESTED` là kết quả phải giữ nếu chưa có phép thử đúng loại.

## 5. Giới hạn đã biết

Không có phép thử Windows hoặc camera mới trong DOC-04. Phép đo 3D, độ lặp, drift, camera pose và kiểm chứng ngoài lab vẫn không thuộc GĐ0.
