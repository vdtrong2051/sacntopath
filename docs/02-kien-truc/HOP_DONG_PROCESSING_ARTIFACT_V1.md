# CT-CROSS-01 — Hợp đồng ProcessingRun, artifact và Viewer provenance

> `owner: STORAGE + APPLICATION + VIEWER` · `specified_at: 2026-10-29` · `implementation: PROPOSED_EXTENSION`  
> Không tuyên bố `MetadataStore` đã có schema artifact SHA riêng. Phải ưu tiên tương thích các API và layout đang tồn tại.

## 1. Nguồn hiện hành

`SessionStore` giữ RAW v2 bất biến (`color.mjpg`, `depth.y16`, `metadata.json`, `manifest.json`, `COMMITTED`). `MetadataStore` quản lý Project → Specimen → ScanSession → Capture → ProcessingRun. `finish_processing_run()` hiện nhận `output_files` (chuỗi), chưa tự chứng minh output tồn tại, SHA khớp hoặc units hợp lệ. Viewer hiện gắn `units/frame=unknown` cho PLY/OBJ ngoài; **không** nới quy tắc này cho mọi tệp tùy ý.

## 2. Pipeline ghi artifact (thiết kế)

1. Đọc/verify Capture nguồn, lưu ID và SHA.
2. Tạo ProcessingRun `pending`, lưu params/version/source IDs; chuyển `running` khi worker thực sự bắt đầu.
3. Chạy thuật toán trong worker; ghi file **dẫn xuất** vào staging path riêng dưới run, không ghi đè RAW hoặc output run cũ.
4. Flush/đóng writer; verify file type, checksum, dimension/unit/frame/bounds/point count và ownership, tạo manifest JSON.
5. Công bố artifact vào vị trí đích theo chính sách filesystem; sau đó `finish_processing_run(..., state='succeeded', output_files=...)` khi output đã xác minh.
6. Khi SQLite update thất bại sau file commit: output có thể orphaned; dùng reconciliation có kiểm soát để gắn lại hoặc đánh dấu recoverable, **không tự xóa** dữ liệu thật.
7. Khi tính toán lỗi, lưu failed status + error class/retry info, không công bố file tạm là artifact hợp lệ.

**Atomicity:** không có transaction toàn hệ filesystem + SQLite; ghi thủ tục khôi phục và test crash points (trước/during/after rename, trước/during/after DB commit). Không sửa RAW migration tự động.

## 3. Artifact manifest đề xuất

```json
{
  "schema": "scantopath-derived-artifact-v1",
  "run_id": "<run-id>",
  "artifact_id": "<artifact-id>",
  "kind": "pointcloud_xyzrgb",
  "uri": "<relative-path-within-root>",
  "sha256": "<64 lowercase hex>",
  "size_bytes": 0,
  "source_capture_ids": ["<capture-id>"],
  "source_raw_hashes": ["<manifest-or-payload-hash>"],
  "algorithm": {"id": "<name>", "version": "<version>", "params": {}},
  "geometry": {"units": "m", "coordinate_frame": "depth_optical", "point_count": 0},
  "provenance": {"measured": true, "metric_validated": false, "inferred_regions": "unknown"}
}
```

**Chú ý:** giá trị `0` và `<>` trong ví dụ là placeholder schema, **không** phải một manifest hợp lệ để PASS. Tạo Pydantic/JSON schema thực khi đến phiên 13. Các provenance flags phải được dẫn từ dữ liệu/gate, không gán `true` từ giả định.

## 4. Viewer: external vs internal artifact

- External PLY/OBJ: không có proof, mặc định `unknown/unknown` như GĐ1.
- Internal artifact: chỉ cho phép `m/depth_optical` hoặc frame đã chứng minh khi có ID/manifest/hash từ ProcessingRun; không chỉ dựa vào extension hoặc người dùng điền text `units=m`.
- Scene selection phải giữ `source_sha256` và revision; khi đo khoảng cách, chỉ cộng/trừ các điểm cùng frame và unit.
- Tránh tăng giới hạn PLY 1.5M vertices/256 MiB khi chưa benchmark; nếu lớn, giảm mẫu ở VIEW layer, giữ artifact đầy đủ.

## 5. Chỉ tiêu nghiệm thu

`AR-01` RAW không đổi; `AR-02` output tồn tại và hash đúng trước succeeded; `AR-03` reopen bằng Project/Viewer khớp metadata; `AR-04` thiếu/mất/corrupt artifact bị từ chối; `AR-05` crash/retry không overwrite; `AR-06` external PLY không tự biến thành metric. Giai đoạn ghi nghiệm thu tại ma trận, **không** ghi pass ở tài liệu này.

## 6. Giới hạn

Chưa chọn artifact ID/format API triển khai. Không bắt đầu database migration chỉ để thêm metadata nếu sidecar manifest + `output_files` đáp ứng đủ gate; đổi schema cần ADR và rollback riêng.
