# Lộ trình năng lực ScanToPath — từ nền desktop đến hình học tin cậy

> `owner: PRODUCT_SCOPE_OWNER` · `as_of_commit: 7a0df7c5b596ff8750bf91f47310067c53a8b204` · `verified_at: 2026-10-28`  
> `scope: roadmap định hướng và phụ thuộc năng lực, không phải task ledger hay trạng thái nghiệm thu thời gian thực`  
> **Nguồn lịch sử:** `docs/ROADMAP.md` (lộ trình UI-first) và `docs/roadmap/SESSION_CROSSWALK.md` (đối chiếu với 20 phiên trước); tài liệu hiện tại diễn giải dễ đọc, không thay quyết định lịch sử.

## 1. Roadmap giải quyết điều gì?

Mục tiêu nghiên cứu cuối không đơn giản là “xem mô hình 3D”: hệ thống phải bảo toàn nguồn dữ liệu, dựng hình học có đơn vị và sai số, đánh giá độ tin cậy theo mục đích kỹ thuật, rồi mới cho phép dùng kết quả trong thiết kế/chế tạo. Để tránh phát triển thuật toán sâu rồi mới phát hiện khó vận hành, thứ tự sau GĐ0 được chọn là **UI-first + vertical slices**: đưa một phần chức năng qua đủ UI, service, data và test rồi mới mở rộng.

Roadmap chỉ nói **thứ tự phụ thuộc và tiêu chí cần đạt**. Task chi tiết, chủ sở hữu và trạng thái tiến độ sau này thuộc `docs/05-quan-ly/TASK_REGISTER.md` (DOC-04), không tạo một task riêng cho mỗi đoạn roadmap.

## 2. Các chặng và điều kiện nối tiếp

| Chặng | Năng lực phải có | Chốt chất lượng trước khi đi tiếp | Tình trạng ở commit nguồn |
|---|---|---|---|
| **GĐ0 — Software & RAW foundation** | C++/Python bridge, Gemini 2 one-shot, RAW v1/v2, SQLite/audit | Đọc lại đúng byte, xác thực schema/checksum và một lần kiểm tra thiết bị | Có code và hồ sơ PRE-06; không chứng minh metric accuracy |
| **GĐ1 — Desktop Experience & 3D Viewer** | Qt shell/Project Workspace, Viewer PLY/OBJ cô lập tiến trình, picking/Inspector | Full regression, HMI/native thực địa và xử lý ngoại lệ hợp lệ | Code Viewer/Project có trong Git; **overall pending 08.06.6** |
| **GĐ2 — RAW Replay & Single-view Geometry** | Xem lại color/depth, unprojection một góc, ROI/filter/export, provenance | Synthetic ground truth + replay thực, đơn vị/frame và round-trip | **PLANNED**, chưa có pipeline GĐ2 trong build GĐ1 |
| **GĐ3 — Metric Reconstruction & Trust** | Kiểm định metric, pose registration, fusion, coverage/trust | Mẫu chuẩn, RMSE/drift, chính sách từ chối pose không chắc | **PLANNED** |
| **GĐ4 — Feature & Engineering Replica** | Feature fitting/uncertainty, feature graph, as-is/nominal | Residual và xác nhận đo đối với đối tượng kỹ thuật | **PLANNED** |
| **GĐ5 — Intelligent/Active Acquisition** | Nhận biết vật thể tùy chọn, hướng dẫn thu nhận theo vùng thiếu | Benchmark AI, latency/VRAM, giá trị bổ sung thực, planned ≠ actual | **PLANNED** |

Không suy rằng tên GĐ3 hay GĐ4 đã tồn tại thì code xử lý đó có sẵn. Các yêu cầu dành cho giai đoạn sau là mục tiêu thiết kế, không phải check box được duyệt.

## 3. Vì sao thứ tự này quan trọng?

**Không dựng metric cloud trước khi hiểu RAW.** Dữ liệu màu và độ sâu được giữ hai lưới, intrinsics theo stream, depth scale theo `m/unit`, D2C translation theo mm. Nếu tùy tiện align hoặc coi camera pose có sẵn thì mọi phép đo sau sẽ không có nguồn đáng tin.

**Không fusion khi chưa có pose.** Một camera quay quanh vật hoặc vật quay trước camera tạo ra các quan hệ chuyển động khác nhau; nếu thiếu biến đổi hợp lệ, ghép điểm có thể tạo mesh trông đúng nhưng sai kích thước. Vì vậy metric gate (phiên 14) và đăng ký pose (15) phải đi trước fusion/trust (16).

**Không gọi kết quả AI là phép đo.** Phân đoạn vật thể/mask chỉ là giả thuyết vùng ảnh. Từng điểm 3D hoặc feature vẫn phải có bằng chứng hình học, hiệu chuẩn và độ tin cậy.

**Không phát robot command từ path hình học chưa xác minh.** ScanToPath có thể cung cấp đường tham chiếu trong tương lai, nhưng đường điều khiển thực cần hệ tọa độ, an toàn, chuyển động và các thiết bị không thuộc baseline hiện hành.

## 4. Mốc chức năng tương ứng phiên 06–20+

| Phiên mới | Nội dung cốt lõi | Điều kiện khác biệt |
|---|---|---|
| 06–08 | Desktop, Project, Viewer | Hành vi dùng được trên Qt, không chặn UI |
| 09–10 | RAW replay và depth→cloud | Không làm mất metadata/units; kiểm projection |
| 11–13 | ROI, filter, normals và export | Kết quả có provenance, lưu/đọc được |
| 14 | Metric calibration & mẫu chuẩn | Chưa qua gate thì không tuyên bố độ chính xác |
| 15–16 | Pose/registration, fusion và trust | Phải có đánh giá pose và nguồn mỗi view |
| 17–18 | Feature và bản sao số | Residual, uncertainty, as-is/nominal có căn cứ |
| 19–20+ | AI tùy chọn và hướng dẫn đo bổ sung | Không blocking UI, không thay actual pose bằng planned |

**Lưu ý về lịch sử:** roadmap cũ xếp 3D Core sớm và dùng số phiên khác. Bảng đối chiếu chính xác theo khả năng ở [SESSION_CROSSWALK](../06-giai-doan/SESSION_CROSSWALK.md), không đổi tên lịch sử rồi coi là đã nghiệm thu.

## 5. Các quyết định công nghệ gắn với cổng

- Qt 6/PySide6 là UI desktop hiện có; VTK là renderer trong Render Host. Không mở thêm framework desktop chỉ vì có ví dụ mới.
- Python là orchestration; C++20/pybind11 xử lý bridge camera và phần native cần profile; SQLite là metadata.
- Open3D, OpenCV và Eigen có trong định hướng xử lý hình học/ảnh; **chưa đồng nghĩa đã có pipeline metric**. PCL/AI là candidate theo benchmark và license.
- Thiết kế chuyển động camera/cơ cấu quay phải có quyết định vật lý riêng, không suy từ GĐ0 cầm tay hay gợi ý cơ khí ở các note khác.

Xem [Công nghệ và phụ thuộc](../02-kien-truc/CONG_NGHE_VA_PHU_THUOC.md) để phân biệt package được khai báo, module đang dùng và candidate R&D.

## 6. Thế nào là đóng một giai đoạn?

Cần: chức năng đúng scope; mã nguồn/commit và test; bản đo môi trường thật nếu phạm vi có HMI/camera; chốt hạn chế còn mở và waiver có trách nhiệm. Đặc biệt, **GĐ1 không được đóng chỉ vì R8.5 đã commit**. Những phép thử DPI/native busy/GPU/render-present phải được xử lý trong 08.06.6 theo cách đo tương ứng.

Lịch sử thử và lỗi được bảo toàn ở [Nhật ký GĐ1](../99-lich-su/JOURNALS/GD1_EXECUTION_JOURNAL.md); nguồn lịch sử R6 ở [Trạng thái nghiệm thu R6](../07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md). Đây là hồ sơ chứng cứ, không phải hướng dẫn tạo task mới.


<!-- SCANTOPATH_GD2_GD3_PLANNING_20261029_BEGIN -->
## Phụ lục quyết định 29/10/2026 — Không đổi roadmap, bổ sung mục tiêu demo

Roadmap giữ nguyên **GĐ2=09–13 single-view**, **GĐ3=14–16 metric/registration/fusion**, GĐ4 feature/digital replica và GĐ5 active acquisition. Chủ dự án bổ sung **MVP-B trước 04/11/2026**, kết hợp GĐ2 + phần GĐ3 cần thiết + mesh để demo. Đây là một **vertical slice liên giai đoạn**, không được dùng làm chứng cứ GĐ3 Done.

Điều kiện vận hành hiện tại: Gemini 2 **cầm tay**, chưa có rig hai trục; camera cố định là ý tưởng tương lai, không suy pose đo thực. [Hồ sơ quyết định](../05-quan-ly/DEC_GD2_GD3_POST_GD1_20261029.md), [MVP-B](../06-giai-doan/MVP_B_ONBOARDING_20261104.md), [Kế hoạch](../06-giai-doan/GD2_GD3_KE_HOACH_THUC_THI_20261029.md).
<!-- SCANTOPATH_GD2_GD3_PLANNING_20261029_END -->
