# HS-01.3-R1 — Keyframe Quality Hardening

**Ngày:** 2026-11-01. **Phạm vi:** sửa logic chọn keyframe, KHÔNG sửa Native OrbbecSDK, RAW-v2, SQLite, Live Worker/Qt lifecycle, đăng ký hình học hay dữ liệu đã lưu.

## 1. Cơ sở thực nghiệm

Operator đã chứng minh `HS_01_3_RAW_AUDIT=PASS` với 46/46 Capture của 3 Scan Session: S01=1, S02=6, S03=39. RAW integrity & persistence PASS. Ảnh Replay S02 cho thấy nhiều góc nhìn gần như lặp khi camera ít di chuyển; S03 có nhiều góc quan sát khác nhau. Từ ảnh màn hình **không thể** biết `novelty_score` ban đầu hay khẳng định chính xác nguyên nhân từng lần `SELECT`.

**Không có dữ liệu RAW vật lý 46 Capture trong gói code này.** Các giá trị cấu hình R1 là baseline bảo thủ, chưa tối ưu/thẩm định bằng thí nghiệm lặp lại trên Gemini 2.

## 2. Quyết định kỹ thuật

- Chỉ đánh giá trên **Depth ROI** hiện hữu. Nếu thiếu ROI, không lấy toàn cảnh làm mặc định; không khẳng định ROI chính là mask vật thể.
- Lọc ưu tiên các bề mặt Depth gần trong ROI bằng 25th-percentile và dải sâu cấu hình, giới hạn số mẫu tối thiểu.
- Khử thay đổi độ sáng đồng đều trong ROI khi tính `color_score` và áp dụng noise floor.
- Khi so sánh chữ ký 16×16, thử bù dịch chuyển tối đa ±1 ô mẫu, chọn mức thay đổi nhỏ nhất để không đánh giá trượt ROI là góc nhìn mới.
- Tính thay đổi Depth với noise floor 12 mm (tham số kinh nghiệm), ưu tiên so sánh ở bề mặt gần trong ROI.
- Bỏ qua thay đổi nhỏ của near-surface silhouette dưới ngưỡng dung sai.
- Chỉ xác nhận keyframe tham chiếu khi `capture_completed(True)` được gọi từ receipt của RAW đã lưu và xác minh. Nếu capture thất bại, giữ mốc cũ. **Mốc lưu là preview kích hoạt RAW**, không giả định preview và RAW là cùng frame.
- Các trường `novelty_score`, `motion_proxy_m` không là xác suất nhận dạng, camera pose, overlap 3D hoặc chứng nhận kích thước.

## 3. File tác động

**Chỉnh sửa 2 file:**

- `src/scantopath/modules/capture/application/keyframe_selection_models.py`
- `src/scantopath/modules/capture/application/keyframe_selector.py`

**Thêm 3 file:**

- `tests/unit/capture/test_hs_01_3_r1_keyframe_hardening.py`
- `scripts/hs_01_3_r1_replay_quality_audit.py`
- `docs/06-giai-doan/HS_01_3_R1_REAL_DATA_KEYFRAME_HARDENING.md`

## 4. Nghiệm thu offline

Thử nghiệm offline không cần camera: 24 HS-01.2 + 15 HS-01.3 core + 11 R1 = **50 PASS** trong môi trường Python/NumPy có mô phỏng DTO nền. Bộ Qt tests trước đó được operator xác nhận **56/56 PASS** trên Windows; R1 giữ nguyên mã Qt, cần chạy lại toàn bộ nhóm focused trên Windows. Số dự kiến **67 passed** nếu đúng danh sách trước đó và không thay đổi fixture; kết quả thực tế từ Windows là nguồn xác nhận.

Unit regressions mới gồm: nhiễu Depth ±6 mm, thay đổi độ sáng toàn cảnh, nhiễu chỉ ngoài ROI, trượt ROI một ô mẫu, thay đổi Depth có ý nghĩa 40 mm, trạng thái chờ/commit lỗi, giới hạn config.

## 5. Kiểm toán REAL RAW chỉ đọc

Để xác minh lại tất cả 46 RAW sau khi áp dụng, chạy:

```powershell
$repo = "E:\1_BigProject\scantopath\scantopath-software"
$store = "E:\1_BigProject\scantopath\_setup\HS_01_3_REAL_20261101\scantopath-data"
Set-Location $repo
& .\.venv\Scripts\python.exe -X utf8 scripts\hs_01_3_r1_replay_quality_audit.py --root $store
```

Để **khảo sát** điểm chống trùng trên S02 với một ROI Depth *cố định thực sự bao quanh hộp trong các RAW*, có thể dùng thêm `--session S02_STATIC_AUTO --roi-depth x,y,width,height`. **Không lấy tọa độ RGB làm tọa độ Depth** (hai lưới chưa align). ROI hiện tại ở bản RAW lịch sử không được lưu lại như một trace và không thể tự phục hồi từ ảnh màn hình. Không tự dùng toàn khung hình làm ROI nếu muốn khảo sát riêng hộp.

Kết quả `DUPLICATE_PROXY/NOVEL_PROXY` chỉ là giả định đánh giá lại, **không tái hiện lựa chọn online** vì không lưu bộ số liệu preview/cooldown/ngữ cảnh trước đó. Không sử dụng kết quả này để kết luận geometric coverage hoặc độ chính xác.

## 6. Quyết định sau Windows tests

- Nếu Python/Qt/regression PASS: `R1_OFFLINE=PASS`, giữ nguyên 46 Capture lịch sử làm evidence.
- Nếu Windows FAIL: không chạy lại installer, gửi stdout/stderr và bản ghi so khớp SHA; installer có backup trong `_setup`.
- R1 phần cứng `NOT_TESTED` cho đến khi có bài test tĩnh mới (S02-R1) và quỹ đạo tối thiểu (S03-R1) trên Gemini 2.
- **Chưa tuyên bố** khắc phục 6 Capture gần trùng trong S02 thực tế cho đến khi đo lại; chưa bắt đầu HS-02.
