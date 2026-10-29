# CT-GD3-01 — Hợp đồng keyframe pose, registration, fusion và mesh

> `owner: GEOMETRY_MODULE_OWNER` · `specified_at: 2026-10-29` · `implementation: NOT_STARTED`  
> `scope: GĐ3 14–16 + MVP-B surface reconstruction`, không phải source đã có.

## 1. Frame và transform

Quy ước: `T_A_B` là transform **B → A**, `p_A = T_A_B * p_B` theo homogeneous column vector. Rigid transform phải có `R ∈ SO(3)` trong tolerance, `det(R)≈+1`, `T[3,:]=[0,0,0,1]`, translation theo `m`. Không để orientation/degree/radian/row-major ngầm định.

| Trường pose | Kiểu | Ý nghĩa |
|---|---|---|
| `capture_id`, `keyframe_id`, `group_id` | IDs | Nguồn RAW và nhóm A/B/C |
| `source_frame`, `target_frame` | typed identifiers | Đầu/cuối phép biến đổi |
| `T_target_source` | float64[4,4], m | Pose ước lượng/đã kiểm chứng |
| `method`, `initialization`, `version` | strings | Odometry, feature+RANSAC, ICP, marker... |
| `overlap`, `rmse_m`, `fitness`, `degeneracy_flags` | metrics | Chứng cứ registration, định nghĩa phương pháp tính |
| `status` | candidate/accepted/rejected/unknown | Không đưa rejected view vào fusion |
| `covariance_or_uncertainty` | optional typed | Nếu chưa có, ghi UNKNOWN, không điền confidence giả |

**Mốc ChArUco/ArUco:** chỉ cấp pose nếu kích thước mốc, frame mốc và phép hiệu chuẩn đã được xác nhận. Việc nhìn thấy marker trên ảnh **không đủ** tự xác nhận metric scale của depth.

## 2. Keyframe/coverage

Ưu tiên camera cầm tay di chuyển quanh **vật đứng yên**, các frame kề nhau đủ overlap. Lưu cả point cloud `scene` và `object`; scene feature có thể hỗ trợ camera odometry khi background cố định. Hệ thống phải phân biệt:

- `group_A`: vòng quanh vật ở trạng thái đặt ban đầu.
- `group_B`: góc trên, vẫn cùng trạng thái vật ban đầu nếu không di chuyển vật.
- `group_C`: vật đã lật/đặt lại; pose camera theo nền **không** chứng minh object pose tới A/B.

Bắt buộc có transform **object-centric** giữa `group_C` và nhóm chuẩn trước khi gắn nhãn underside registered. Nếu thiếu overlap/landmark, gate underside `MB-06` FAIL/BLOCKED. Không dùng tên nhóm/sequence number làm pose.

## 3. Registration và fail-closed

Pipeline tham khảo (không khóa thuật toán): preprocessing → initialization (image/depth/marker/features) → pairwise registration → pose graph/global consistency → validation → accepted transforms. Ngưỡng fitness/RMSE/overlap phải được thiết lập trên fixture rồi kiểm tra dữ liệu thật; không định nghĩa một giá trị tuyệt đối vô căn cứ trước khi đo.

Reject nếu thiếu overlap, transform đảo chiều, scale drift phi vật lý (đối với rigid pose), ICP local minimum, đối xứng nhiều nghiệm, rank deficiency hoặc báo chất lượng không nhất quán giữa edges. Không ghép tất cả view nếu biết một transform fail.

## 4. Fusion/output

- Thực hiện fusion từ **accepted views**; có `source_capture_ids`, transform versions và `confidence/coverage/missing` theo vùng.
- Không làm mất scale/đơn vị trong voxel downsample, re-center hay mesh reconstruction.
- Mesh output là bản dựng bề mặt từ cloud, có thể Poisson/BPA/TSDF khi phép thử phù hợp; file phải phân biệt `measured_surface`, `inferred/interpolated`, `unknown/missing` nếu có khả năng xác định, và ghi hạn chế khi không thể.
- Không đánh giá mesh kín = đã thấy toàn bộ vật. Mesh không được dùng thay point cloud thô để chứng nhận sai số nếu có vùng nội suy.
- Gắn kết quả đo các trục/hướng đã định, từng phép đo so với reference object, không dùng bounding box sau re-center để lẫn với camera frame.

## 5. Input/output contract chuẩn

**Input:** danh sách verified `Capture/SingleViewCloud` + `mask` + `intrinsics/depth_scale` + pose candidates + params. **Output:** `RegistrationGraph`, `AcceptedPoseSet`, `MergedObjectCloud`, `CoverageReport`, `SurfaceMesh` (khi có) + manifest liên kết tất cả nguồn và `ProcessingRun`.

Data lifecycle: `RAW_COMMITTED → SINGLE_VIEW_READY → POSE_CANDIDATE → REGISTRATION_ACCEPTED/REJECTED → FUSION_READY → MESH_READY/INSUFFICIENT_DATA`. Không đưa `INSUFFICIENT_DATA` về `SUCCEEDED` bằng cách xuất file rỗng.

## 6. Testing

Synthetic: 3D object với known transforms, Gaussian noise/outliers/overlap loss, đảo chiều transform, missing underside, symmetry. Real: hộp họa tiết + tượng; ít nhất một mẫu đạt MB gates mới đánh dấu MVP-B PASS. Đo lặp để phân biệt sai số do calibration, pose và mesh. Native Open3D ICP có sẵn không được xem là chất lượng PASS nếu thiếu dữ liệu thực.

## 7. Giới hạn đã biết

Người/vật động, mặt phản xạ, vật không đủ texture và đáy không có overlap là ngoài điều kiện thành công chắc chắn. GĐ3 phải giữ `unknown/rejected` minh bạch thay vì cố ghép cho đẹp.
