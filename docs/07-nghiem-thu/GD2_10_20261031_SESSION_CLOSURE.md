# Biên bản chốt phiên GD2-10 — Single-view Geometry / Measurement UI

> **Ngày quyết định:** 2026-10-31 (UTC+07).
> **Đối tượng:** riêng phiên GD2-10; **không** phải nghiệm thu toàn GĐ2/GĐ3/MVP-B.
> **Repository/branch:** `vdtrong2051/sacntopath` / `feat/gd2-10-metric-geometry`.
> **Source baseline:** `292c9d81404a75caccae21f3a3e08ec4fa8e2267`.
> **Quyết định operator:** `SESSION_CLOSED_ACCEPTED_WITH_LIMITATIONS`.
> **Điểm 10.08.3:** `NOT_RUN_BY_OWNER_DECISION` (không lặp lại kiểm thử UI cuối khi các kịch bản đã được chạy theo từng checkpoint). Không ghi 10.08.3 = PASS.

## 1. Phạm vi được chấp nhận

- Single-view Depth → XYZ từ calibration của đúng RAW Capture, bảo vệ validity, frame `depth_optical`, đơn vị `m`.
- Depth-to-Color mapping, K6 thực tế của Gemini 2, RGB hợp lệ theo subset có visibility/occlusion policy, không tạo màu giả.
- Replay → Decode → Geometry bằng service có boundary rõ và kiểm thử dữ liệu tổng hợp / RAW thực.
- Desktop Qt + Viewer VTK subprocess: chọn Capture, hiển thị XYZRGB thật, camera orientation, auto-fit, grid mặc định tắt khi Preview; PLY chỉ là bản tạm.
- Đo hai điểm A/B: kiểm tra scene SHA/revision/Capture, ánh xạ PLY ID sang `ValidGeometry` index, đo `float64`, hiển thị neo/đường nối và m/mm, cảnh báo chưa certified.

## 2. Gate và mức bằng chứng

| Gate / Checkpoint | Trạng thái đóng | Bằng chứng / giới hạn |
|---|---|---|
| 10.01–10.03 (`G2-10-A`) | `PASS` tính toán | Synthetic ground truth, validity/scale/frame; committed checkpoints |
| 10.04–10.05 (`G2-10-B`) | `PASS` tích hợp | K6 corrective, 94/94 regression; RAW Gemini 2 C0001/C0002 H6 PASS |
| 10.06 | `PASS` | 18/18 tests, m/mm/lineage và provisional status; commit `e527ba3` |
| 10.07.1 | `PASS` | 13/13 unit + 35/35 related regression; commit `6374a2d` |
| 10.07.2 | `PASS` | 26/26 offline end-to-end + 16/16 related regression; commit `d900d2e` |
| 10.07.3 | `PASS` real RAW | H6 2 Capture trên snapshot byte-identical; checksum RAW + SQLite nguồn không đổi |
| 10.07.4 | `PASS` full regression | 1,199 passed, 3 skipped; architecture 0 violations; CTest Release 2/2 |
| 10.08.1 | `PASS` manual visual | C0001 và C0002 XYZRGB hiển thị, sensor-camera auto-fit, grid off, thao tác Viewer; commit `7df9d5a` |
| 10.08.2 (`G2-10-C` phần mềm) | `ACCEPTED_WITH_LIMITATIONS` | Operator thử UI A/B trên hai Capture; screenshot C0002 cho `0.405693 m = 405.693 mm`; full regression cuối operator xác nhận PASS nhưng không đính kèm tổng kết terminal cuối; commit `292c9d8` |
| 10.08.3 kiểm thử cuối bổ sung | `NOT_RUN_BY_OWNER_DECISION` | Owner không yêu cầu chạy lại kịch bản đã thực hiện nhiều lần; quyết định đóng phiên không tạo thêm chứng chỉ test |
| Độ chính xác đo vật chuẩn / sai số mm | `NOT_TESTED` | Chưa có reference physical measurements / repeatability / uncertainty; không cấp METRIC_VALIDATED |

### Bằng chứng thực tế H6 — operator log

| Chỉ tiêu | C0001 | C0002 |
|---|---:|---:|
| Capture ID | `0d23c9da9059488fa5fe34a3e9af8c07` | `7369033a75c445749579cc9e4f2f4bf8` |
| XYZ | 624,520 | 626,748 |
| Có màu | 469,997 (75.26%) | 473,228 (75.51%) |
| RAW manifest + SHA on snapshot | PASS | PASS |
| `SOURCE_RAW_AND_SQLITE_SHA256_UNCHANGED` | PASS | PASS |
| `PIPELINE` | PASS | PASS |
| Observed end-to-end time | 938.71 ms | 232.93 ms |

Mô hình Color K6/Depth K6-zero 4 với hai Capture thực tế đã được kiểm thử; không dùng hai Capture này làm bằng chứng pose/multi-view. Dữ liệu vật lý H6 nằm ngoài Git và không cần copy vào repository để công bố kết quả này.

## 3. Dấu mốc Git (theo lịch sử commit)

| Mốc | SHA ngắn | Thay đổi |
|---|---|---|
| K6 correction | `3d9e2a4` | Support Orbbec K6 calibration; H6 fix |
| 10.06 | `e527ba3` | Measurement backend |
| 10.07.1 | `6374a2d` | ReplayGeometryService orchestration |
| 10.07.2 | `d900d2e` | Offline integration tests |
| 10.08.1 | `7df9d5a` | RGB-D point cloud Preview, sensor camera auto-fit |
| UTF-8 quality gate | `db5586f` | Read architecture files with UTF-8 on Windows |
| 10.08.2 | `292c9d8` | Interactive two-point measurement UI |

Các commit 10.01–10.05 được giữ trong lịch sử branch; bảng này chỉ ghi các mốc chốt chính và bản sửa phát sinh. **Commit không thay thế log chạy test.**

## 4. Giới hạn được chấp thuận, không nâng thành PASS

1. `PROVISIONAL_NOT_METRIC_VALIDATED`: đo Euclid 3D ở frame camera, chưa đo đối chứng độ chính xác bằng vật chuẩn; không tuyên bố ≤10 mm, không tự nhận kích thước toàn vật.
2. RAW chứa cả nền và môi trường; vùng Depth không hợp lệ, sai lệch màu và phần khuyết hình học có thể tồn tại; làm sạch/tách vật thể thuộc GD2-11.
3. Chỉ M điểm có RGB được chuyển thành PLY Preview tạm (M ≤ N XYZ). Khả năng xem Preview không thay thế `ProcessingRun`, artifact manifest, export/reopen chính thức (GD2-13).
4. Overlay A/B là nhãn màn hình; sau khi thay góc camera phải chọn lại để tránh nhãn sai vị trí; chưa có khả năng giữ điểm 3D cố định qua mọi camera move.
5. C0001/C0002 là H6 single-view samples, không đánh giá registration/fusion, mesh hoặc robot spray path.
6. Thời gian/bộ nhớ H6 chỉ là quan sát riêng lẻ, không phải benchmark được chuẩn hóa; timestamp SDK không phải chứng minh hardware synchronization.
7. Mốc 10.08.3 **bỏ theo quyết định owner do trùng kiểm thử**, không chuyển tự động thành PASS; full regression cuối 10.08.2 được owner báo PASS nhưng chưa có bản transcript chi tiết trong hồ sơ này. Ba skipped ở mốc 10.07.4 không bị coi là passed.

## 5. Quyết định đóng và handoff

- **Phiên GD2-10: `CLOSED_ACCEPTED_WITH_LIMITATIONS`**, áp dụng cho phạm vi phần mềm single-view geometry, RGB Preview và phép đo sơ bộ.
- **Không** phát biểu `METRIC_ACCURACY_CERTIFIED`, `GD2_OVERALL_PASS`, `MVP_B_PASS` hoặc `G3_CALIBRATION_PASS`.
- **Tiếp theo:** GD2-11 — tách vật thể và lọc point cloud, giữ scene/raw provenance; chỉ mở phạm vi mới khi owner cho phép.
- **Tham chiếu kỹ thuật:** [GD2-10 implementation](../06-giai-doan/GD2_10_SINGLE_VIEW_GEOMETRY_IMPLEMENTATION.md); [ma trận nghiệm thu GĐ2](GD2_GD3_MVPB_ACCEPTANCE_MATRIX.md); [hợp đồng RAW/XYZRGB](../02-kien-truc/HOP_DONG_GD2_RAW_XYZRGB_V1.md).

**Quy tắc lưu hồ sơ:** Bằng chứng test ghi từ kết quả terminal/operator và commit đã có; những mục chưa có vật chuẩn, JUnit, video hoặc receipt cuối không được tự bổ sung như đã đo. Không ghi RAW/capture dữ liệu cá nhân vào Git.
