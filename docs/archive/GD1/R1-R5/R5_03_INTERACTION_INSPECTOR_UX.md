# R5.3 - Chọn hình học và công cụ kiểm tra 3D (tiếng Việt)

**Baseline:** `feat/gd1-desktop-ui@2ec6e7dbd4c9ba6933cbee1b0d44081470ba84b3` (R5.2 committed). R5.3 là tích hợp UI/IPC có giới hạn; không tạo đường dẫn robot, không lọc/tái tạo hình học, không đọc camera, không ghi SQLite hay RAW.

## Phạm vi và hợp đồng

1. **Chọn điểm/mặt thực:** thao tác nhấp chuột trong chế độ **Chọn** tạo tọa độ màn hình chuẩn hóa; Render Host nhận đúng `scene_revision`/`frame_revision`, thực hiện `vtkPointPicker` cho point cloud và `vtkCellPicker` cho mesh, rồi trả về `source_sha256`, loại phần tử, ID và XYZ. Việc chọn chạy ở worker bất đồng bộ; Qt không import VTK.
2. **Inspector dùng chung:** `SceneInspectorBridge` chuyển kết quả đã kiểm chứng sang bảng Thuộc tính. Nguồn tệp PLY/OBJ **không** được biến thành dự án/phiên quét SQLite. Khi rời Viewer, đổi mô hình hoặc gặp lỗi, selection cũ được xóa; đơn vị/hệ tọa độ luôn ghi rõ "Chưa xác nhận".
3. **Thanh công cụ tiếng Việt:** Chọn / Xoay / Dời / Vừa / Trục / Lớp với tooltip giải nghĩa. Giữ nguyên các `objectName` Viewer cũ để bảo đảm khả năng tương thích. Không làm lớn thêm MainWindow. Trục XYZ chỉ mang tính tham khảo. Điều khiển "Vừa" dùng camera reset/fit hiện có.
4. **Hiện/ẩn thật:** lệnh IPC `set_visibility` đổi actor VTK thật; frame mới chỉ được công bố sau copy/ACK; không tự chế lớp hình học thứ hai. Chỉ có một actor hình học nguồn (và actor trục tham khảo).
5. **Fallback:** Chế độ Xem trước an toàn vẫn hoạt động độc lập với pipeline live; không mở hoặc sử dụng native renderer trong Qt chính.

## Bất biến an toàn

- Không sử dụng ảnh PNG hoặc vùng pixel làm bằng chứng tọa độ 3D.
- Không đánh đồng giao điểm mặt (XYZ nội suy) với đỉnh gốc; ID mặt là chỉ số cell trong VTK polydata (không phải ID CAD).
- Không trả lại lựa chọn từ scene/frame khác, không chấp nhận đơn vị đo/hệ tọa độ tự suy đoán.
- Không tải lại PLY/OBJ cho mỗi lần nhấp hoặc mỗi lần ẩn/hiện; nguồn giữ bất biến SHA.
- Phải giữ nguyên kiểm thử giới hạn `MainWindow` dưới 500 dòng, Architecture Guard, Quality Gate, full regression và CTest.
- Native probe chỉ chứng minh click/actor/Qt/IPC trên một fixture nhỏ; không là bằng chứng pointer-to-photon, crash C++ thật, GPU/VRAM, close genuinely-native-busy hoặc DPI 100/125/150%. Các gate này vẫn **OPEN cho R6**.

## Hướng dẫn thao tác nghiệm thu trên Windows

Mở ScanToPath → **Kiểm tra 3D** → **Mở mô hình** (PLY điểm/PLY mesh/OBJ) → chọn **Chọn**, nhấp lên điểm/mặt; quan sát bảng **Thuộc tính** bên phải. Thử **Xoay**, **Dời**, **Vừa**, **Trục**, **Lớp** và nhấp vào vùng trống để xác minh "không chọn". Đổi mô hình, đóng/mở Viewer, dùng **Xem trước an toàn** với PLY điểm. Kiểm tra không tồn tại Render Host thừa. Không bắt buộc cắm Gemini 2.

## Lỗi cần ghi

`_setup/ScanToPath_GD1_R5_3_Interaction_Inspector_UX/evidence/R5_03_OPERATOR_JOURNAL.md` ghi mỗi lần FAIL → nguyên nhân → sửa → chạy lại. R7 sẽ tổng hợp; không được sửa test cũ để vượt gate.

## R5.3 rework - Professional viewport / INC-R53-UX-001

The first R5.3 operator run failed 1/9 focused tests (`test_r53_live_click_emits_uv_only_in_select_mode`): test fixture did not have an acknowledged displayed frame, while `_ready_tools()` correctly rejected picking. The 8 passing tests and user-visible rendering are recorded; do not erase the failure. The reworked fixture sets a valid frame revision and adds a no-frame refusal assertion. No picking safety guard has been relaxed.

- SVG-only icon toolbar: selection, orbit, pan, fit, axes, zoom +/- , reference grid, geometry layer. All labels and tooltips are Vietnamese. Existing R5.2 legacy objectNames/buttons remain for compatibility; PNG fallback remains available.
- Native VTK orientation triad is drawn in a small top-right viewport; it follows camera direction and is informational. An independent XOY reference grid (`z=0`) can be toggled; right click Grid selects `XY` or a **display-only** plane at the model bounding-box minimum Z. Both modes are *uncalibrated*, not a measured machine datum.
- Grid is a separate nonpickable VTK actor and is temporarily hidden during `ResetCamera`; it cannot change source bounds, source hash, face IDs or fitting.
- Mouse: select+left click picks; select+left drag neither picks nor orbits; orbit+left drag rotates; pan+left drag pans; right/middle drag always pans; wheel zooms. S/R/P/F/G/L/Escape shortcuts apply while the viewer has focus.
- Inspector shows X/Y/Z separately at up to 12 significant figures, detailed bounds, original source SHA, and full Python float serialization copied by `Sao chép XYZ`. This is **not a claim of 12-digit measurement accuracy**. Units and coordinate frame remain unverified.
- Native tests, Qt behavior tests and manual Windows 100/125/150% HMI are required. Actual GPU VRAM, pointer-to-photon latency and genuinely busy native crash remain unverified until R6. No SQLite/RAW writes.
- This rework is a **repair to the existing uncommitted R5.3**, not a second commit or a new stage.
