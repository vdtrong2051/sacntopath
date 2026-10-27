# R7-A — Sổ vấn đề về tài liệu và nguy cơ trùng lặp

Danh sách này là **ứng viên đối chiếu** cho R7-B, không kết luận nội dung trùng nhau khi chưa so sánh toàn văn. Không có file nào bị xóa.

| ID | Ưu tiên | Vấn đề | Trạng thái bằng chứng |
|---|---|---|---|
| R7A-01 | CAO | Nhiều tài liệu kiến trúc cùng xuất hiện như hiện hành | CHƯA XÁC NHẬN NỘI DUNG MÂU THUẪN |
| R7A-02 | CAO | Roadmap có giả định phần cứng cầm tay; cần đối chiếu baseline hiện hành | CẦN NGƯỜI DUYỆT |
| R7A-03 | CAO | Chỉ mục hiện hành chứa câu R7 chưa commit dù HEAD đã là commit R7 | CÓ BẰNG CHỨNG TRỰC TIẾP |
| R7A-04 | CAO | Hồ sơ Viewer nhiều thế hệ bị lẫn trong mục tra cứu | NGHI VẤN GIAO THOA |
| R7A-05 | CAO | Project Workspace có nhiều hồ sơ phiên và tài liệu module | NGHI VẤN GIAO THOA |
| R7A-06 | VỪA | Quy ước ngôn ngữ chưa thống nhất | CÓ BẰNG CHỨNG TRỰC TIẾP |
| R7A-07 | VỪA | Dữ liệu GPU/FPS/native busy có thể bị hiểu lầm là nghiệm thu | CẦN GIỮ BẤT BIẾN |
| R7A-08 | VỪA | Các tài liệu GĐ0 kỹ thuật chưa có tài liệu module tiếng Việt hoàn chỉnh | THIẾU TÀI LIỆU CHUẨN |
| R7A-09 | VỪA | Một số báo cáo 08.06/UX HMI có nội dung chồng phạm vi | NGHI VẤN GIAO THOA |
| R7A-10 | VỪA | Các quyết định renderer phân bố ở ADR và hồ sơ từng phiên | CẦN TỔNG HỢP |

## Bằng chứng và hướng xử lý

### R7A-01 — Nhiều tài liệu kiến trúc cùng xuất hiện như hiện hành

- **Tài liệu cần đối chiếu:** `docs/ARCHITECTURE.md; docs/architecture/CURRENT_GD1_ARCHITECTURE.md; docs/architecture/07_10_MODULAR_MONOLITH_TARGET.md`.
- **Việc R7-B:** Đối chiếu các phát biểu về trạng thái GĐ0/GĐ1; ARCHITECTURE cũ là lịch sử, kiến trúc hiện hành cần một nguồn chuẩn.
- **Độ chắc chắn:** CHƯA XÁC NHẬN NỘI DUNG MÂU THUẪN.

### R7A-02 — Roadmap có giả định phần cứng cầm tay; cần đối chiếu baseline hiện hành

- **Tài liệu cần đối chiếu:** `docs/ROADMAP.md; docs/PRE_01_BASELINE.md; docs/GEMINI2_VALIDATION.md`.
- **Việc R7-B:** Không đổi giả định camera và cơ cấu quét nếu chưa có quyết định nguồn mới hơn; ghi khác biệt theo thời điểm.
- **Độ chắc chắn:** CẦN NGƯỜI DUYỆT.

### R7A-03 — Chỉ mục hiện hành chứa câu R7 chưa commit dù HEAD đã là commit R7

- **Tài liệu cần đối chiếu:** `docs/INDEX.md; docs/history/DEVELOPMENT_MASTER_LOG.md`.
- **Việc R7-B:** Sửa trạng thái/commit trong R7-B, không làm mất nhật ký lịch sử.
- **Độ chắc chắn:** CÓ BẰNG CHỨNG TRỰC TIẾP.

### R7A-04 — Hồ sơ Viewer nhiều thế hệ bị lẫn trong mục tra cứu

- **Tài liệu cần đối chiếu:** `docs/gd1/08_02_VTK_VIEWER_FOUNDATION.md; docs/gd1/ux_rebaseline/R4_05_RENDERER_ARCHITECTURE_DECISION.md; docs/gd1/ux_rebaseline/R5_03_INTERACTION_INSPECTOR_UX.md; docs/modules/VIEWER3D.md`.
- **Việc R7-B:** Tài liệu chuẩn mô-đun phải phản ánh bản R5.3; các hồ sơ từng phiên đi archive; R6 gate chưa hoàn tất.
- **Độ chắc chắn:** NGHI VẤN GIAO THOA.

### R7A-05 — Project Workspace có nhiều hồ sơ phiên và tài liệu module

- **Tài liệu cần đối chiếu:** `docs/gd1/07_PROJECT_WORKSPACE/07_04_PROJECT_EXPLORER_SQLITE.md; docs/gd1/ux_rebaseline/R3_02_PROJECT_WORKSPACE.md; docs/modules/PROJECT_WORKSPACE.md`.
- **Việc R7-B:** Bảo đảm chỉ một tài liệu module hiện hành, giữ nguyên ADR/storage versions.
- **Độ chắc chắn:** NGHI VẤN GIAO THOA.

### R7A-06 — Quy ước ngôn ngữ chưa thống nhất

- **Tài liệu cần đối chiếu:** `docs/INDEX.md; docs/modules/PROJECT_WORKSPACE.md; docs/decisions/DECISION_INDEX.md; docs/development/R7_DOCUMENTATION_POLICY.md`.
- **Việc R7-B:** Biên soạn tiêu đề và prose tiếng Việt; giữ tên định danh API và nội dung chứng cứ gốc.
- **Độ chắc chắn:** CÓ BẰNG CHỨNG TRỰC TIẾP.

### R7A-07 — Dữ liệu GPU/FPS/native busy có thể bị hiểu lầm là nghiệm thu

- **Tài liệu cần đối chiếu:** `docs/acceptance/GD1_R6_ACCEPTANCE_STATUS.md; docs/gd1/ux_rebaseline/R4_04_AB_PERFORMANCE_AND_STABILITY.md`.
- **Việc R7-B:** Giữ R6_AUTOMATED_PASS nhưng R6_OVERALL_PENDING; phân biệt completed render với present.
- **Độ chắc chắn:** CẦN GIỮ BẤT BIẾN.

### R7A-08 — Các tài liệu GĐ0 kỹ thuật chưa có tài liệu module tiếng Việt hoàn chỉnh

- **Tài liệu cần đối chiếu:** `docs/PRE_02_RAW_RGBD_CONTRACT.md; docs/PRE_03_RAW_STORAGE.md; docs/GD1_2_3_2_1_CAMERA_SOURCE.md`.
- **Việc R7-B:** R7-B lập mô-đun THU_NHAN_RGBD và LUU_TRU_RAW bằng tiếng Việt từ source + hồ sơ gốc.
- **Độ chắc chắn:** THIẾU TÀI LIỆU CHUẨN.

### R7A-09 — Một số báo cáo 08.06/UX HMI có nội dung chồng phạm vi

- **Tài liệu cần đối chiếu:** `docs/gd1/08_06_4_WINDOWS_HMI_ACCEPTANCE.md; docs/gd1/ux_rebaseline/R3_05_INTEGRATED_UX_ACCEPTANCE.md`.
- **Việc R7-B:** Lưu hồ sơ theo thời điểm, một bảng nghiệm thu hiện hành ở acceptance; không gộp PASS cũ với mới.
- **Độ chắc chắn:** NGHI VẤN GIAO THOA.

### R7A-10 — Các quyết định renderer phân bố ở ADR và hồ sơ từng phiên

- **Tài liệu cần đối chiếu:** `docs/gd1/ux_rebaseline/R1_03_RENDERER_ARCHITECTURE_ADR.md; docs/gd1/ux_rebaseline/R4_05_RENDERER_ARCHITECTURE_DECISION.md; docs/decisions/DECISION_INDEX.md`.
- **Việc R7-B:** Giữ ADR theo thời điểm, chỉ mục quyết định nên có đường dẫn đến quyết định hiện hành và trạng thái có điều kiện.
- **Độ chắc chắn:** CẦN TỔNG HỢP.
