# Nguồn nghiên cứu và repository tham khảo GĐ2–GĐ3 (29/10/2026)

> `owner: RESEARCH_OWNER / ARCHITECTURE_OWNER` · `as_of: 2026-10-29`  
> `source-of-truth: phân loại nguồn tham chiếu, không phải trạng thái tích hợp thư viện` · `evidence_level: SOURCE_READ/RESEARCH_NOTE/USER_PROVIDED_LINKS`.

## 1. Thứ tự độ tin cậy của nguồn

1. **Source of truth phần mềm:** [`vdtrong2051/sacntopath@main`](https://github.com/vdtrong2051/sacntopath), baseline merge `9e32dafc747dab52fd5b58a54c42d37a9a7a8652`. Tài liệu chuẩn: `docs/01–07`; source: `src/scantopath/`, `cpp/`, tests.
2. **Lịch sử thuật toán V1:** [`vdtrong2051/scantopath_test`](https://github.com/vdtrong2051/scantopath_test). Chỉ là *algorithm reference*, không phải package để nhập nguyên hay gate PASS của bản mới.
3. **Nguồn nghiên cứu NCKH của chủ dự án:** [thư mục Drive NCKH](https://drive.google.com/drive/folders/1Otz7om-m-4I56CklchqkmDuJDy5-L-ed), đặc biệt `Tiền đề → Bản chuẩn/Bản thô → 01_PHAM_VI_VA_BAN_DO_NGHIEN_CUU.md`; trong thư mục nghiên cứu cũ có `Tech_note`, `Phân tích điểm yếu + 1 số giải pháp.docx`, `Kế hoạch nghiên cứu.docx`. Các tài liệu này chứa quyết định khoa học và mục tiêu đề xuất, **không** tự chứng minh code đã triển khai.
4. **Repository công khai bên thứ ba:** chỉ dùng để nghiên cứu API, thuật toán, benchmark và license; không được gọi là dependency đã dùng khi code chưa tích hợp.

## 2. V1 — ma trận ứng viên tái sử dụng

| Năng lực | Nguồn V1 | Điểm dùng mới | Hạn chế phải xử lý |
|---|---|---|---|
| RGB-D → point cloud | `modules/acquisition/rgbd_to_ply.py` | GĐ2 10 | V1 có heuristic suy đoán mm/m; phải bỏ, dùng depth scale metadata |
| Object extraction | `modules/segmentation/depth_object_extractor.py` | GĐ2 11 | RANSAC/depth/DBSCAN có thể nhầm cụm; cần manual fallback |
| Point-cloud filter | `modules/pointcloud/pointcloud_filter.py` | GĐ2 11 | Phải quản lý params, provenance, nguồn RAW bất biến |
| Normals | `modules/surface_map/normal_estimation.py` | GĐ2 12 | Cần quality/orientation gates |
| Multi-view yaw/ICP | `modules/registration/multiview_merger.py` | GĐ3 15–16 | V1 dựa trên yaw thủ công, tùy chọn ICP; không phải pose measured |
| Mesh Poisson/BPA | `modules/surface_map/surface_map_builder.py` | MVP-B/GĐ3+ | Không coi mesh Poisson kín là measured everywhere |
| Zigzag mesh slicing | `modules/path_generation/zigzag_generator.py` | Nhánh path sau MVP-B | Có code Zigzag; không phải robot trajectory |
| Contour | Mô tả V1/README | BACKLOG | Không có implementation contour tương đương đã xác nhận trong cây source đã rà soát |

Không tự chuyển kết quả thống kê V1 (các mẫu/độ phủ) thành benchmark Gemini 2 hiện hành. V1 README mô tả chức năng rộng hơn một số module thực tế.

## 3. Các repository chủ dự án mới cung cấp

| Nguồn | Vai trò xác minh qua README | Phù hợp với ScanToPath | Quyết định |
|---|---|---|---|
| [ARTenshi/robovision_ros2](https://github.com/ARTenshi/robovision_ros2) | Giáo trình image publisher/subscriber ROS2, OpenCV, services | Tham khảo giao tiếp khi về sau nối robot | **REFERENCE_ONLY**; không thêm ROS2 vào GĐ2 |
| [3dgeo-heidelberg/helios](https://github.com/3dgeo-heidelberg/helios) | HELIOS++ C++/Python mô phỏng khảo sát quét laser LiDAR | Học thiết kế survey/synthetic scans, coverage | **R&D_LATER**; LiDAR simulation không mô phỏng trực tiếp RGB-D Gemini 2 |
| [lukasmasuch/best-of-ml-python](https://github.com/lukasmasuch/best-of-ml-python) | Danh mục xếp hạng thư viện ML Python | Tra cứu lựa chọn AI nếu có task và benchmark | **CATALOG_ONLY**; không phải ML runtime |
| [OpenDriveLab/WorldEngine](https://github.com/OpenDriveLab/WorldEngine) | Simulation / 3DGS / post-training cho autonomous driving | Ý tưởng mô phỏng vòng kín và dữ liệu hiếm | **OUT_OF_GD2_SCOPE**; không tích hợp vào MVP-B |

## 4. Các công nghệ khác được nhắc trong NCKH

| Công cụ/nghiên cứu | Vai trò | Giai đoạn/nhãn |
|---|---|---|
| [Open3D](https://github.com/isl-org/Open3D) | Point cloud, filters, normals, registration/ICP, reconstruction | GĐ2/GĐ3 **CANDIDATE_TO_EVALUATE** |
| [OpenCV](https://github.com/opencv/opencv) | MJPEG/Depth image processing, distortion, ChArUco/ArUco | GĐ2/GĐ3 **CANDIDATE_TO_EVALUATE** |
| [FreeCAD](https://github.com/FreeCAD/FreeCAD) | CAD ground-truth/model đối chứng kích thước | Benchmark GĐ3/GĐ4, không thay ảnh quét RAW |
| Eigen | Transform/linear algebra native C++ | Nếu geometry native benchmark có lợi |
| PCL | Alternative geometry processing native | Không đồng thời chọn PCL+Open3D khi chưa có lý do và benchmark |
| GenCAD-3D, DeepCAD | AI/CAD parametric research | R&D GĐ4+, không dùng làm dữ liệu đo gốc |
| TRELLIS.2, Articraft | AI 3D asset / articulated model research | R&D dài hạn, không dùng để chứng nhận kích thước |

**License/dependency:** trước khi copy source, thêm package hoặc ship model/dataset phải kiểm tra license của đúng commit/release, Windows/Python/C++ ABI, bộ nhớ và giới hạn GPU. Bảng này **không** là phê duyệt license.

## 5. Sự khác biệt giữa bản đồ nghiên cứu NCKH và mã giai đoạn phần mềm

Bản đồ nghiên cứu NCKH dùng 'Giai đoạn 2 — dữ liệu hình học kiểm chứng' theo logic khoa học, rồi bản sao số/đầu ra kỹ thuật/active acquisition. Repo mới dùng **GĐ2=09–13 single-view**, **GĐ3=14–16 metric/registration/fusion**. Tên gọi tương tự nhưng không cùng cơ chế đánh số. Bảo toàn cả hai và dùng `docs/06-giai-doan/SESSION_CROSSWALK.md` để đối chiếu năng lực.

## 6. Giới hạn đã biết

Chưa rà soát/kiểm toán license chi tiết của từng third-party repository, chưa download dataset và chưa benchmark; không gán performance claims của HELIOS++/WorldEngine cho Gemini 2. Một số công trình trong note NCKH là hướng khảo sát, không có bằng chứng source code ScanToPath hiện thực hóa.
