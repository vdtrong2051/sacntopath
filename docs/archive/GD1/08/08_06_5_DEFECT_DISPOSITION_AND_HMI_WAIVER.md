# ScanToPath — GĐ1 / 08.06.5: Defect Disposition & HMI Waiver

**Ngày chốt sổ rủi ro:** 25/10/2026. **Baseline:** `feat/gd1-desktop-ui @ 5e3c176077008e77087a4db88140e75806c520a2` (08.06.3). **Quyết định:** không có defect runtime mới đã được chứng minh đòi hỏi sửa source. Ghi nhận khắc phục phép đo RAM, chấp nhận có điều kiện độ trễ tương tác và ngoại lệ HMI theo quyết định người vận hành.

## A. Quy tắc bằng chứng

- `08.06.2` trên Windows: 471 cases, 469 passed, 2 skipped (quyền symlink đã ghi nhận), 0 failed; Architecture, Quality, CTest, self-test đều exit 0. Đây là **bằng chứng hồi quy tự động**, không chứng minh native Windows HMI.
- `08.06.3` lần đầu: 21/21 tác vụ hoàn thành, nhưng Windows child RSS ~4.3 MiB là số đo sai đối tượng (khả năng theo dõi Python virtualenv redirector). Công cụ đo lại riêng đã kiểm tra và tái đo 21/21 thành công. Tại 1 triệu điểm: import ~244 MiB/1.605 s, orbit ~258 MiB/1.718 s, picking ~252 MiB/1.229 s. RAM là **đỉnh tiến trình VTK con**, không phải VRAM, không phải toàn bộ ứng dụng Qt.
- `08.06.4`: automated preflight 7/7 checks exit 0 và Qt focused 25 tests/0 failures/skips. Native **session A**: `result=PASS`, Windows Qt thật, 288.12 s, 1065 samples, `gui_exit_code=0`, Qt peak 245.4 MiB, sampled combined peak 439.03 MiB, 14 descendant PIDs được quan sát, không còn PID được quan sát sau đóng. Kết quả chứng minh **đóng bình thường sau thao tác trong phiên A**, không chứng minh đóng khi render đang chạy.
- Ảnh người vận hành gửi trong chat chứng minh một số trạng thái: TC02 ASCII RGB 4 điểm/bounds; TC03 binary 3 điểm/bounds; TC04 PLY invalid với thông báo đỏ và xóa preview; PLY 1 triệu điểm hiển thị sau khi import. Ảnh đã hiển thị **không** chứng minh picking, orbit, pan, toggles, 20 lần đổi workspace, 10 lần import liên tiếp hoặc close-while-busy; các phần này dựa vào xác nhận tổng quan của người vận hành, **không có bằng chứng độc lập từng ca**.
- Người vận hành tuyên bố **không cần chạy thêm phiên B/C vì ứng dụng đã thỏa mãn yêu cầu**. Không coi 2 ca chưa chạy là PASS. Không dùng hoặc sửa receipt `08_06_4_RECEIPT.json` vốn yêu cầu A/B/C và 12 PASS.

## B. Sổ khắc phục và ngoại lệ

| ID | Phân loại | Kết quả/nguồn | Quyết định |
|---|---|---|---|
| D-08063-RAM | Defect ở **benchmark harness**, không phải VTK renderer | Lần đầu RSS ~4.3 MiB cho mọi tải; Memory Recheck 190–258 MiB, 21/21 PASS | **RESOLVED_IN_COMPANION_HARNESS**. Không sửa source ScanToPath. |
| AR-01 | Nợ kiến trúc | `Viewer3DController` quản lý nhiều workflow | **DEFERRED_NON_BLOCKING**; chỉ refactor nếu có lỗi tái hiện. |
| AR-02 | Giới hạn thiết kế/UX | Tương tác render lại theo tác vụ có độ trễ ~1–3 s | **ACCEPTED_FOR_UI_MVP_A_INSPECTION_ONLY** theo người vận hành; **không có** chứng nhận viewport 60 FPS. |
| AR-03 | Rủi ro lifecycle chưa đủ bằng chứng | Session A đóng bình thường và thu hồi tiến trình; chưa có phiên B close-while-busy | **OPEN_WITH_OPERATOR_WAIVER**; phải giữ ở risk register, không tuyên bố an toàn hoàn toàn. |
| AR-04 | Giới hạn giao diện | VTK render PNG trong process con, không phải live embedded viewport | **ACCEPTED_LIMITATION**, đánh giá lại khi tính năng nâng cao cần liên tục. |
| AR-05/06/07/08/09 | Nợ kỹ thuật/kiểm chứng | Xem tài liệu 08.06.1; không có lỗi mới được cung cấp | **TRACKED/DEFERRED**, không đại refactor. |
| HMI-TC11 | Test case **chưa chạy** | Session B close while busy | **NOT_RUN_WAIVED_BY_OPERATOR**, residual risk AR-03. |
| HMI-TC12 | Test case **chưa chạy** | Session C relaunch after busy-close | **NOT_RUN_WAIVED_BY_OPERATOR**, residual risk AR-03. |

## C. Quyết định GĐ1

1. Giữ kiến trúc hiện tại: **offline-first Modular Monolith, MVC theo từng feature, SOLID**, VTK native cô lập qua `QProcess`. Không hoàn nguyên nhúng VTK trực tiếp vì sự cố Windows 08.02.
2. **Không sửa runtime** ở 08.06.5: không có defect runtime mới có đủ bằng chứng và reproduction. Không đụng SQLite/RAW/camera/firmware/C++.
3. `08.06.4` được công nhận **HMI_ACCEPTED_WITH_OPERATOR_WAIVER**, **không** phải `PASS_REVIEWED` theo cổng gốc; TC11–TC12 không thực hiện và chưa có chứng cứ bắt buộc để tự chứng nhận các trường hợp đó.
4. Cơ chế đóng gói 08.06.5 chỉ commit **hai tệp tài liệu** (`08_06_4_WINDOWS_HMI_ACCEPTANCE.md` đã được áp dụng, nhưng bị kẹt gate, và tài liệu này), sau khi xác minh session A, preflight hashes, trạng thái Git và người vận hành truyền switch chấp thuận ngoại lệ. Không tạo/sửa/gán giả mạo full HMI receipt.
5. 08.06.6 phải ghi chú quyết định miễn kiểm thử, độ trễ và bằng chứng còn thiếu; **final acceptance là quyết định độc lập**, không mặc định GĐ1 đã PASS không điều kiện.

## D. Điều kiện đóng 08.06.5

- [x] Đối chiếu HEAD, source và hồ sơ 08.06.1–08.06.4 từ GitHub và kết quả người vận hành cung cấp.
- [x] Phân loại defect vs giới hạn và lập sổ rủi ro; không tạo sửa mã không có cơ sở.
- [ ] Windows `verify.ps1` 08.06.5: HEAD, scope 2 docs, preflight hashes, session A native Qt, `resources.csv`, `qt_console.log` khớp; architecture/quality và focused regression PASS; sinh `08_06_5_SUMMARY.json`.
- [ ] Người vận hành ký xác nhận với `publish.ps1 -ManualWaiverAccepted`, tạo receipt `08_06_5_WAIVER_RECEIPT.json`, commit/push đúng hai tài liệu. **Không** dùng `publish.ps1` của 08.06.4.

**Trạng thái:** remediation/disposition đã hoàn thành trên source; nghiệm thu 08.06.5 chỉ khóa sau Windows verify và công bố hồ sơ. Bước tiếp theo 08.06.6 — final GĐ1 acceptance với residual-risk sign-off.
