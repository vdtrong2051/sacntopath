# ScanToPath — Phạm vi công nghệ và chính sách lựa chọn (18/10/2026)

**Áp dụng cho roadmap UI-first từ phiên 06.** Không phải danh sách yêu cầu cài đặt tất cả thư viện. Mỗi công nghệ có một **trạng thái**: (1) Đang dùng và đã kiểm thử, (2) Được chọn để triển khai kế tiếp, (3) Benchmark tùy chọn, (4) Tham khảo/ngoài lõi.

## A. Nguồn tư duy nghiên cứu

Tài liệu [`01_PHAM_VI_VA_BAN_DO_NGHIEN_CUU`](https://drive.google.com/drive/folders/1Otz7om-m-4I56CklchqkmDuJDy5-L-ed) xác định **Scan → Trusted Geometry → Engineering Digital Replica → Technical Use**, bổ sung vòng thông tin kỹ thuật còn thiếu → đo thêm. Không đồng nhất đo, nội suy, dự đoán AI. Phân biệt rõ:

- **A — Nghiên cứu:** độ tin cậy phép đo, truyền sai số, feature confidence, độ đủ dữ liệu theo nhiệm vụ, mô hình hóa bản sao số, phản hồi yêu cầu thu nhận bổ sung.
- **B — Công nghệ kế thừa:** ICP, RANSAC, KD-tree, Open3D/PCL, calibration, VTK, OpenCV, chuẩn tệp.
- **C — Ứng dụng kiểm chứng:** thiết kế ngược, cụm lỗ/cơ khí, kiểm tra, sửa chữa, phục hồi, xử lý bề mặt, chuẩn bị gia công.

Không chấp nhận «thuật toán / mô hình mới hơn trên benchmark» là đóng góp khoa học của dự án nếu không có đánh giá phục vụ mục tiêu metric/feature/trust.

## B. Stack và ranh giới tích hợp

| Miền | Công nghệ | Trạng thái | Quyết định | Phiên |
|---|---|---|---|---|
| Desktop UI | **Qt 6 / PySide6 Widgets** | Đang dùng ở mức shell | Dùng tiếp; giao diện chính + 4 workspace; tránh framework UI thứ hai | 06–09 |
| Application | **Python 3.12, Pydantic, services, workers** | Đang dùng một phần | Điều phối/DTO/UI adapter; không đặt heavy processing trên Qt main thread | 06+ |
| Capture | **OrbbecSDK v2.10.6 / C++20 / pybind11** | Đã nghiệm thu real one-shot | Giữ version đã kiểm thử, nâng SDK theo ticket compatibility riêng | 09+ |
| RAW+Metadata | **SessionStore v1/v2 + SQLite/SQLAlchemy** | Đã nghiệm thu | Nguồn dữ liệu hiện hữu; schema migration chỉ khi có lý do | 07+ |
| Viewer | **VTK + Qt** | Chưa tích hợp | Được chọn cho viewer; kiểm thử VTK widget/event-loop/point picking | 08 |
| Geometry | **Open3D**, NumPy, Eigen, C++20 | Được chọn, chưa coi là đã tích hợp | Prototype bằng Python; hot path native C++ sau profiling; contract không ràng buộc UI vào Open3D | 10–18 |
| Image/Depth | **OpenCV** | Được chọn, chưa coi là đã tích hợp | MJPEG decode, depth render, projection/preprocessing có kiểm tra biến dạng | 09–10 |
| Build | **CMake, MSVC, pybind11**; vcpkg khi cần dependency native | CMake/native hiện hữu, vcpkg theo nhu cầu | Không nâng build toàn bộ nếu không có dependency mới | 08+ |
| Point-cloud alternative | [PCL](https://github.com/pointcloudlibrary/pcl) | Benchmark tùy chọn | Chỉ thêm nếu so A/B tốt hơn Open3D ở bài toán cụ thể; tránh 2 core song song | 13+ |
| Export | **PLY, CSV, JSON** trước; PCD, OBJ/STEP/E57 sau đánh giá | Planned | Đúng units/frame/provenance và roundtrip; không giả định tự viết STEP B-rep | 13, 18+ |

**Không có `T_world_camera(t)` chính xác sẵn có trong dữ liệu GĐ0.** Gemini 2 cầm tay, Color MJPEG 1920×1080 và Depth Y16 1280×800 là lưới độc lập; intrinsics/distortion theo stream, D2C translation mm, scale depth m/unit. Không gắn nhãn object pose/metric-trusted cho bất kỳ nguồn đo chưa được validation.

## C. Candidate AI/perception — không là dependency của UI/3D Core

| Nhóm và nguồn | Nhiệm vụ đề xuất | Gate / giới hạn | Trạng thái |
|---|---|---|---|
| [RF-DETR](https://github.com/roboflow/rf-detr) | Object detection, một số biến thể segmentation | A/B với YOLO trên dữ liệu cơ khí; kiểm tra license phần code/model | Candidate 19 |
| [YOLO26](https://github.com/ultralytics/ultralytics) | Detection/segmentation/tracking tùy cấu hình | Xem license AGPL/commercial, performance thực | Candidate 19 |
| [SAM family](https://github.com/facebookresearch/sam3) | Promptable segmentation/masks | Benchmark GPU/latency/VRAM/weights; không biến mask thành phép đo | R&D 19+ |
| [DINOv3](https://github.com/facebookresearch/dinov3) | Visual embeddings, retrieval/representation | Không thay RANSAC/cylinder/hole fitting | R&D 19+ |
| [Depth Anything 3](https://github.com/ByteDance-Seed/depth-anything-3) | AI-estimated depth/pose hypothesis benchmark | Đối chứng Gemini 2 metric; giữ inferred label | R&D 16+/20+ |
| [LocateAnything3D](https://nvlabs.github.io/LocateAnything3D/) | Spatial/3D language grounding | Kiểm tra code, weights và điều kiện chạy; không đồng nhất với 3B | R&D 19+ |
| [LocateAnything-3B](https://huggingface.co/nvidia/LocateAnything-3B) | Text-guided 2D localization/boxes | Không phải point cloud/3D metric; kiểm tra phạm vi phi thương mại của weights | R&D 19+ |
| [locate-anything.cpp](https://github.com/mudler/locate-anything.cpp) | C++ runner cho 3B | Kiểm tra quyền weights và chất lượng Windows x64/offline | R&D 19+ |
| [LingBot-Map](https://github.com/robbyant/lingbot-map) | Benchmark streaming/multi-view pose, geometry | Có thể đòi CUDA/runtime riêng; không nhập luôn vào `.venv` chính | R&D 16+/20+ |
| [best-of-ml-python](https://github.com/lukasmasuch/best-of-ml-python) | Danh bạ thư viện tìm hiểu | Không phải runtime hay công nghệ lõi | Tham khảo |

**Giấy phép là cổng bắt buộc:** xác minh riêng **code, checkpoint/weights, pretrained data và model wrapper** theo phiên bản cụ thể trước khi phân phối, thương mại hóa hoặc nhúng vào ứng dụng; nội dung bảng chỉ là cảnh báo lập kế hoạch, **không phải thẩm định pháp lý**.

**Chọn detector:** đưa RF-DETR và YOLO vào cùng một benchmark; ở cuối phiên 19 **chỉ chọn một** mặc định (hoặc fallback manual) theo số liệu. Không cài cùng lúc RF-DETR + YOLO + SAM + DINO + DA3 vào runtime chính.

## D. Tài nguyên khác — tham khảo không đồng nhất với metric geometry

| Nguồn | Vai trò phù hợp | Không được tuyên bố |
|---|---|---|
| [text-to-cad](https://github.com/earthtojake/text-to-cad) | Học workflow CAD và handoff | Mô hình AI sinh ra từ prompt là hình học đo thực |
| [image-blaster](https://github.com/neilsonnn/image-blaster) | Workflow thế giới/asset 3D | Dùng trực tiếp làm kiểm tra kích thước cơ khí |
| [3dviz-pro-max](https://github.com/viettranx/3dviz-pro-max) | Thiết kế giao diện/visualization patterns | Thư viện VTK/Qt production |
| [OrbbecSDK v2 releases](https://github.com/orbbec/OrbbecSDK_v2/releases) | Nguồn cập nhật driver/SDK | Bắt buộc nâng ngay khỏi SDK đã kiểm thử |

### Ba bài báo gương/ToF người dùng cung cấp

- *Matching-Based Depth Camera and Mirrors for 3D Reconstruction* (Nguyen et al., SPIE 2018, arXiv:1908.06342).
- *3D Reconstruction With Time-of-Flight Depth Camera and Multiple Mirrors* (Nguyen et al., IEEE Access 2018, DOI:10.1109/ACCESS.2018.2854262).
- *Using ToF camera and two mirrors for 3D reconstruction of dynamic objects* (Technical Report 1380, 2018).

Các kết quả này cung cấp hướng nghiên cứu **multi-view bằng gương, đo/calibration mặt gương, phát hiện point nhiễu do phản xạ**. **Không** mặc định camera Gemini 2 đang dùng gương hay cảm biến ToF. Không rút ra kết luận sai số trực tiếp cho cấu hình handheld hiện tại; muốn tích hợp thì cần thiết kế/đánh giá thực nghiệm riêng.

## E. Quy trình benchmark và quyết định đưa vào core

1. **Giả thuyết:** công nghệ X cải thiện tác vụ Y; baseline hiện có Z; loại sai số cần giảm.
2. **I/O & provenance:** format, units, coordinate frame, timestamps, expected artifact, `source_id`, model/version, checksum.
3. **Environment:** Windows x64, Python/C++ compatibility, GPU VRAM/CPU/RAM, khả năng offline và dependency isolation.
4. **Dữ liệu:** fixture hình học chuẩn + Gemini 2 RGB-D đã lưu + trường hợp khó (lỗ, trụ, bề mặt trơn/bóng, occlusions, ánh sáng).
5. **Số liệu:** P50/P95 latency, FPS, peak memory, repeatability, geometry RMSE vs reference, pose error, registration fitness, mIoU/mAP khi phù hợp, trust/feature correctness.
6. **Rủi ro:** license code+weights, footprint, install/remove, thất bại có kiểm soát, fallback không AI.
7. **Decision record:** Accept/Reject/Defer kèm bằng chứng; benchmark vẫn nằm trong `experiments/` hoặc thư mục sandbox đến khi chấp nhận.

**Nguồn còn thiếu:** liên kết ghi chú ChatGPT chia sẻ `https://chatgpt.com/s/t_6ad4426520748191960a62b05772b311` chưa xác minh được nội dung; không được dùng để tự phát minh thêm yêu cầu kỹ thuật.
