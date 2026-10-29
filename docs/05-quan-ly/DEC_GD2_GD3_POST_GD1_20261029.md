# DEC-GD2-GD3-20261029 — Quyết định sau khi đóng GĐ1

> `owner: PROJECT_OWNER / PRODUCT_SCOPE_OWNER` · `decision_date: 2026-10-29` · `source_baseline: main@9e32dafc747dab52fd5b58a54c42d37a9a7a8652`  
> `status: SCOPE_APPROVED_IN_CONVERSATION; IMPLEMENTATION_NOT_STARTED` · `evidence_level: USER_DECISION + GITHUB_SOURCE_REVIEW`  
> **Quan trọng:** Đây là hồ sơ quyết định phạm vi; không thay một ADR phần cứng đã đo thực, không phải kết quả kiểm thử, không cấp PASS cho GĐ2/GĐ3.

## 1. Bối cảnh và nguồn chuẩn

GĐ1 đã đóng theo quyết định `GD1_STAGE_CLOSED_ACCEPTED_WITH_EXPLICIT_WAIVERS`, merge trên `main` tại `9e32daf` (2026-10-29 giờ Việt Nam). Các phiên R là mở rộng để xử lý nợ kỹ thuật GĐ1; không khởi động R9 để dọn chung. Các điều khoản miễn nghiệm thu thuộc GĐ1 được giữ tại `docs/07-nghiem-thu/GD1_ACCEPTANCE.md`, không được đổi thành PASS.

Những buổi thảo luận từ khi chốt GĐ1 đến 29/10/2026 đã khóa mục tiêu và cách thực thi GĐ2/GĐ3. **Không có commit triển khai GĐ2 được xác nhận** tại baseline này.

## 2. Các quyết định đã chốt

| ID | Quyết định | Hệ quả cần bảo vệ |
|---|---|---|
| `DEC-21` | Giữ roadmap GĐ2 phiên 09–13; GĐ3 phiên 14–16 | Không đổi số phiên, không đẩy fusion thành điều kiện Done của GĐ2 |
| `DEC-22` | Desktop Qt/PySide6 + Python 3.12 + C++20/pybind11 + VTK Render Host; tận dụng Project/Processing/Viewer và panels hiện có | Không tạo workspace hoặc renderer thứ hai, không refactor GĐ1 nếu không có blocker |
| `DEC-23` | Pipeline bán tự động, từng bước có kết quả trung gian; có thể tự chạy những bước an toàn và hỗ trợ Run All về sau | Người vận hành xác nhận object/ROI, capture, tham số và kết quả; không giả định full-auto |
| `DEC-24` | **Phần cứng hiện có cho demo: Gemini 2 cầm tay**; chưa có cơ cấu hai trục | Không suy ra camera cố định, yaw/encoder/pose đo sẵn; cơ cấu hai trục chỉ là target design |
| `DEC-25` | Live RGB-D preview và khung bao động vật thể; fallback chọn ROI thủ công | Bounding box chỉ định vị trên ảnh; **không** đồng nghĩa mask chính xác hoặc camera pose |
| `DEC-26` | XYZRGB bắt buộc; object extraction/background removal bắt buộc | Không tô màu bằng cách ghép chỉ số pixel hai stream khác kích thước; xác minh D2C |
| `DEC-27` | ProcessingRun và artifact quản lý theo Project/Capture, với provenance và checksum | Không đánh dấu succeeded trước khi output ghi/verify thành công |
| `DEC-28` | Onboarding **04/11/2026: MVP-B gần V1**, gồm multi-view, ghép point cloud, mesh, vùng trên/quanh/dưới vật | Đây là mục tiêu bắt buộc của bản demo, **không phải lời cam kết chắc chắn PASS**; không hạ yêu cầu âm thầm |
| `DEC-29` | Vật mẫu đa dạng, pipeline không hardcode hộp/cốc/tượng/phôi/người | Chọn hộp có họa tiết và tượng nhỏ để đánh giá ưu tiên; người là kịch bản khó, ngoài gate bắt buộc demo |
| `DEC-30` | Độ đúng cơ bản mục tiêu sai lệch tuyệt đối **≤ 10 mm** trên các chiều được chọn khi đối chứng | Không tuyên bố 5%: 10 mm / 100 mm = 10%, 10 mm / 30 mm = 33,3%; phải ghi sai lệch từng chiều |
| `DEC-31` | GĐ3 dùng keyframe có overlap, ước lượng pose + registration, có thể dùng mốc tham chiếu; không cố định thuật toán cụ thể | Bắt buộc reject pose thiếu tin cậy, phân biệt frame gốc/camera/world và measured/inferred |
| `DEC-32` | V1 là kho tham chiếu thuật toán, không import nguyên pipeline | Port theo từng phiên, đo/test lại, không biến README V1 thành bằng chứng chức năng sẵn có |
| `DEC-33` | P0 phải fix ở phiên liên quan; P1 xử lý trong giai đoạn; P2/P3 backlog | Không mở vòng R diện rộng; không tự kéo scope AI, robot actuation, Digital Replica vào GĐ2 |

## 3. Hardware: hiện trạng, mục tiêu, điều chưa xác minh

| Loại thông tin | Kết luận |
|---|---|
| `CURRENT_PHYSICAL` | Người vận hành xác nhận **có Gemini 2 và đang cầm tay quét**; chưa có cơ cấu hai trục để vận hành. Xác nhận này là khai báo vận hành, **chưa phải kiểm chứng vật lý có ảnh/receipt tại ngày 29/10**. |
| `TARGET_DESIGN` | Camera/cơ cấu chuyển động theo hướng nghiên cứu cũ là định hướng tương lai, không cấp pose cho capture GĐ2. |
| `HISTORICAL_VARIANT` | V1 dùng Astra Mini Pro/OpenNI2, nhiều góc thủ công; không đồng nhất với Gemini 2 hiện tại. |
| `OPEN_EVIDENCE` | Model/firmware/serial của lần thu ngày demo, camera-to-object distance, độ ổn định keyframe, đặc điểm vật mẫu, hồ sơ đo cơ khí chưa có receipt mới. |

**Hành động với `HW-CURRENT-BASELINE` trong Task Register:** khi áp dụng gói, có thể thêm *ghi chú quyết định người vận hành* để gỡ giả định sai camera cố định; chưa tự nâng task thành `DONE` nếu gate nguồn vật lý yêu cầu ảnh/hồ sơ vẫn thiếu.

## 4. Phạm vi không đổi của các giai đoạn

- GĐ2 09–13: RAW replay, live capture có kiểm soát, single-view XYZRGB, ROI/segmentation cơ bản, filter, normals, export; test fixture + RAW thật.
- GĐ3 14–16: gauge/metric validation, pose estimation/registration, multi-view fusion, coverage/trust.
- **MVP-B** là *vertical slice demo liên giai đoạn* dùng năng lực GĐ2 + phần GĐ3 + surface reconstruction; không phải chứng nhận GĐ3 done hoặc GĐ4 done.
- Mesh phục vụ demo không phải lời khẳng định kín bề mặt hay chuẩn CAD. Zigzag chưa là gate bắt buộc của demo 04/11 theo quyết định cuối, dù hướng lâu dài là kế thừa V1.

## 5. Tình trạng và điều kiện khởi động

`GD1=CLOSED_ACCEPTED_WITH_EXPLICIT_WAIVERS`; `GD2=NOT_STARTED`; `GD3=NOT_STARTED`; `MVP_B_20261104=PLANNED_HIGH_RISK`. Gói tài liệu này chỉ khóa yêu cầu/đề án và dự kiến kiểm thử. Khi chủ dự án phê duyệt thực thi, lập task/branch riêng, không ghi trạng thái `IN_PROGRESS` từ việc soạn tài liệu.

## 6. Giới hạn đã biết

Độ chính xác 10 mm là **ngưỡng chấp nhận demo được người dùng đề xuất**, chưa có kết quả đo. Việc thu mặt dưới khi lật vật thể có thể làm mất hệ tham chiếu; không được giả định sẽ ghép được. Sự hiện diện của thuật toán V1/Open3D không chứng minh pipeline mới đã chạy. Lịch 04/11 là mục tiêu có rủi ro cao: không tự miễn test hoặc làm giả mesh để đạt lịch.
