# ScanToPath — GĐ1 / 08.06.1: Integrated Architecture Audit

**Ngày kiểm toán:** 25/10/2026.  **Loại công việc:** kiểm toán mã nguồn tĩnh + sổ rủi ro. **Không refactor, không sửa runtime.**

**Nguồn chính:** GitHub `vdtrong2051/sacntopath`, nhánh `feat/gd1-desktop-ui`, commit [`32caa4b93d16a4dc64686b6871b3d597ee8e9b5b`](https://github.com/vdtrong2051/sacntopath/commit/32caa4b93d16a4dc64686b6871b3d597ee8e9b5b), đã xác minh sau khi hoàn thành 08.05. Tại thời điểm kiểm toán nhánh đi trước `main` 26 commit, không tụt commit. Báo cáo này phản ánh source tại commit; không tự chứng nhận kết quả chạy Windows.

## I. Phạm vi, phương pháp, mức bằng chứng

- Đọc trực tiếp source ở commit nêu trên; đối chiếu kiến trúc trong `docs/architecture/07_10_MODULAR_MONOLITH_TARGET.md`, `07_11_ARCHITECTURE_HARDENING.md`, `07_12_CONSOLIDATION_RISK_REGISTER.md` và roadmap `docs/ROADMAP.md`.
- Đối chiếu source lớp Qt shell; Project Workspace application/presentation; compatibility layers; scripts static guard; Viewer domain/application/presentation/infrastructure; render pipeline/picking; lưu trữ SQLite/RAW và C++ bridge.
- Kiểm chứng chữ ký/hash Git blob cho các tệp Viewer 08.05 trong bản snapshot nội bộ so với HEAD GitHub: Controller/View, navigation/picking contracts, render PLY, render navigation, pick-point đều khớp.
- **Chưa** chạy fresh full checkout regression, native Windows GUI, đo latency/RAM hoặc xem profiler trên máy phát triển. Kiểm chứng lại bằng `verify.ps1` đính kèm (chỉ chạy static audit, không cài dependency, không mở camera).
- AST guard và giới hạn số dòng chỉ chứng minh các thuộc tính kiểm thử được; **không** chứng minh SOLID tuyệt đối, an toàn native hay hiệu năng.

## II. Ma trận tuân thủ nguyên tắc cứng

| Tiêu chí | Trạng thái tại HEAD | Bằng chứng & giới hạn |
|---|---|---|
| Modular Monolith | **Đạt cấu trúc** | Một desktop app; `modules/project_workspace` và `modules/viewer3d` có ownership; shared `metadata`, `storage`, `acquisition` đúng vai trò, không nhân đôi. |
| MVC theo feature | **Đạt có nợ kỹ thuật** | Viewer: Qt View + Controller, `application` contracts, `infrastructure` VTK subprocess. Project Workspace: controller/workflows/use cases; worker Qt còn ở `ui/projects`. |
| SOLID / SRP | **Đạt một phần** | Service/Repo đã được tách. `Viewer3DController` 408 dòng, 17 method, chứa nhiều workflow và trạng thái; không kết luận vi phạm chỉ từ LOC. |
| SOLID / ISP + DIP | **Khá, chưa tuyệt đối** | Ports/DTO tách Qt-VTK, nhưng `ProjectWorkspaceService` còn default adapter bootstrap; View Controller cầm process job và trạng thái. |
| SOLID / OCP + LSP | **Chưa đủ bằng chứng** | Cần contract substitution/adapters và kiểm thử thay thế; không tuyên bố bảo đảm bởi AST. |
| Architecture guards | **Có nền tảng, còn giới hạn** | `check_architecture_boundaries.py` bao gồm cross-feature imports; chỉ phân tích import tĩnh, chưa chứng minh dynamic imports/call graph/thread-safety. |
| RAW/SQLite isolation | **Không thấy thay đổi bởi Viewer** | Viewer child làm việc với PLY local, image/JSON temp; không import SQLite/OrbbecSDK trong runtime Viewer. Cần regression GĐ0 ở 08.06.2. |
| Native failure isolation | **Đúng hướng** | `QProcess` tạo native VTK subprocess, Qt chỉ đọc PNG/JSON, timeout và cleanup. Đã có lịch sử crash in-process ở 08.02: không hoàn nguyên nhúng trực tiếp. |
| Provenance/metric honesty | **Đạt hợp đồng cơ bản** | `PlySummary`, `PickResult` yêu cầu units/frame `unknown`, không gán metric validated; point-count/bounds chỉ là dữ liệu nguồn. |

## III. Những điểm đã kiểm tra và giữ nguyên

- `src/scantopath/ui/shell/main_window.py`: shell tạo Viewer *lazy*, giữ đúng 4 workspace; Qt app không trực tiếp render PLY. Có khoảng 482 dòng gồm menu/docks/navigation/compatibility delegates (không phải mặc nhiên là God Class).
- `src/scantopath/modules/project_workspace/application/`: query/command/inspection/records và ports riêng, default SQLite adapter bootstrap là ngoại lệ tương thích đã được ghi lại từ 07.11.
- `src/scantopath/modules/viewer3d/application/navigation.py`, `picking.py`, `ply_contracts.py`: camera/point DTO thuần Python, không import Qt/VTK và không suy đoán hệ đơn vị/pose.
- `src/scantopath/modules/viewer3d/infrastructure/render_ply.py`, `render_navigation.py`, `pick_point.py`: VTK chạy ở tiến trình con riêng; PLY được kiểm tra preflight/giới hạn kích thước và fingerprint; xem điểm chọn qua VTK.
- `src/scantopath/modules/viewer3d/presentation/view.py`: hiển thị ảnh và tín hiệu chuột; không import VTK. Native-rendered image chỉ cập nhật sau khi nhận kết quả hợp lệ.
- SQLite v1 read-only, v2 explicit writes, numbered alias sau commit, RAW immutable và recovery vẫn là *contract bắt buộc*: bước audit này không thay đổi implementation cũng không xem việc chỉ đọc source là regression pass.

## IV. Sổ rủi ro đã xác định

| ID | Mức | Nhận định có bằng chứng | Quyết định/điều kiện theo dõi |
|---|---|---|---|
| **AR-01** | **P1 / tập trung SRP** | `viewer3d/presentation/controller.py` khoảng 408 dòng và 17 methods; cùng điều phối fixture/PLY/navigation/picking, QProcess, timeout, result validation, source state. | **Không tách ngay.** Tại 08.06.2/08.06.4 kiểm thử chuyển trạng thái liên tiếp, lỗi từng job, close while busy; nếu có defect/coupling rõ, tách theo job-coordinator trong bước 08.06.5 riêng. |
| **AR-02** | **P0 / nghiệm thu hiệu năng** | Mỗi orbit/pan/zoom/pick chạy `sys.executable -m ...`, khởi tạo VTK mới; PLY có thể được kiểm tra/hash nhiều lần trong một thao tác; ảnh tĩnh 1000×620 được tái tạo. | **Bắt buộc benchmark 08.06.3**: tải 1K/10K/100K/300K/1M điểm; đo cold/warm latency, peak RSS tổng main+child, timeout, độ trễ picking, thao tác chuỗi. Không tuyên bố 60 FPS. |
| **AR-03** | **P0 / nghiệm thu lifecycle** | `Viewer3DController` điều phối `QProcess`, `QTimer`, `TemporaryDirectory`; `_cleanup` có `kill()` và `waitForFinished(200)` khi cần. | **Bắt buộc 08.06.2–08.06.4**: đóng khi render/pick đang chạy, timeout/child crash, 20+ lần đổi workspace/PLY, subprocess/temp không còn sót; đo nguồn lực Windows. |
| **AR-04** | **P1 / ngữ nghĩa viewport** | Qt hiện hiển thị PNG do VTK render thay vì một `QVTKRenderWindowInteractor` tương tác liên tục. Tính năng camera nhận event rời rạc. | Ghi rõ tiêu chí UI MVP-A; chỉ chấp nhận nếu độ trễ thao tác đạt ngưỡng đã được đo/chấp thuận. Cơ chế an toàn hơn không đồng nghĩa trải nghiệm tương tác real-time. |
| **AR-05** | **P1 / coupling Project Workspace** | `project_workspace/presentation/workflows/base.py` dùng `__getattr__/__setattr__` proxy trạng thái giữa read/write/capture workflows; các worker implementation vẫn có tại `ui/projects`. | Nợ tương thích có từ 07.11–07.12; theo dõi, **không sửa trong 08.06.1**; chỉ refactor độc lập có tests nếu phát sinh lỗi. |
| **AR-06** | **P1 / DIP một phần** | `project_workspace/application/service.py` vẫn load adapter mặc định qua bootstrap tương thích; `WorkspaceContext` dùng `Callable`/`object` ở một vài chỗ. | Khi có provider thứ hai, đưa wiring sang composition root và bổ sung contract-test trước khi bỏ ngoại lệ. Không bắt buộc trước 08.06.2. |
| **AR-07** | **P2 / shell maintenance** | `ui/shell/main_window.py` khoảng 482 dòng và nhiều delegates từ 07.x; lõi tác vụ Project đã được chuyển đi. | Theo dõi trách nhiệm/nút chuyển tiếp khi thêm phiên 09, không phá public hooks hiện có chỉ để giảm dòng. |
| **AR-08** | **P1 / static blind spots** | Bộ AST gate kiểm soát import, không kiểm soát dynamic imports, runtime Qt threading, native driver crashes, reflection, chất lượng substitutability hay độ trễ. | Ghép static gate với integration tests, runtime HMI và benchmark trong 08.06.2–08.06.4. |
| **AR-09** | **P1 / mô hình dữ liệu nguồn** | PLY preflight có giới hạn 256 MiB/1.5M điểm; RGB phụ thuộc point scalars VTK; unit/frame luôn `unknown`; checksum không chứng minh giá trị đo. | Thử PLY thật, rỗng/lỗi, big-endian, RGB/sans RGB và provenance, không suy diễn thành metric validation. |

**Lưu ý P0:** Ở đây P0 là *bằng chứng bắt buộc phải có trước khi khóa GĐ1*, **không phải khẳng định đã phát hiện bug runtime ở source**. Không có bằng chứng hợp lý để viết lại renderer hoặc refactor toàn dự án ngay tại 08.06.1.

## V. Quyết định kiến trúc / Không thực hiện trong bước này

1. Giữ **Modular Monolith + MVC trong feature + SOLID** và native isolation bằng `QProcess`.
2. Giữ `main_window.py` là composition/UI shell; không đưa VTK/SQLite/RAW I/O vào đây.
3. Ghi rõ ownership: `viewer3d/application` DTO/logic thuần; `presentation` Qt+input/UI state; `infrastructure` VTK/PLY process; `domain` mô hình nguồn thuần; `project_workspace` chỉ quản lý metadata.
4. Không tạo module/controller trừ khi có use case thực tế; không dùng kiến trúc mới hoặc duplicate TaskManager.
5. Không cài lại VTK/PySide6; không chạm camera, firmware hoặc metadata DB.
6. Không âm thầm chuyển sang 08.06.2; mỗi gate cần bằng chứng và nghiệm thu.

## VI. Tiêu chí đạt của 08.06.1 / chuyển sang 08.06.2

- [x] Đã đối chiếu HEAD/nhánh và roadmap chính thức từ GitHub.
- [x] Đã review ranh giới runtime Viewer, cách ly native, contracts, shell và Project Workspace trên source HEAD.
- [x] Đã lập danh sách rủi ro có mức độ, source và gate kiểm chứng tiếp theo.
- [ ] Chạy `verify.ps1` trên checkout Windows thực: architecture scanner `0 violations`, quality scanner `0 errors`, inventory JSON/Markdown tạo mới và hash receipt hợp lệ; verify script không chạy camera, không cài VTK.
- [ ] Review kết quả inventory, xác nhận không có vấn đề kiến trúc mới nghiêm trọng làm cản trở bước 08.06.2.
- [ ] Commit/push **duy nhất tài liệu audit** sau khi máy Windows PASS và người vận hành phê duyệt; không merge `main`.

> Đây là **kết quả kiểm toán từ xa** kèm kế hoạch xác nhận bằng máy Windows, chưa phải giấy chứng nhận GĐ1 PASS. Full Python/Qt regression, native CTest/self-test thuộc 08.06.2; benchmark thuộc 08.06.3, Windows HMI thuộc 08.06.4.

## VII. Nguồn mã đã đối chiếu

- [ROADMAP](https://github.com/vdtrong2051/sacntopath/blob/32caa4b93d16a4dc64686b6871b3d597ee8e9b5b/docs/ROADMAP.md)
- [Viewer3DController](https://github.com/vdtrong2051/sacntopath/blob/32caa4b93d16a4dc64686b6871b3d597ee8e9b5b/src/scantopath/modules/viewer3d/presentation/controller.py)
- [Viewer3DPage](https://github.com/vdtrong2051/sacntopath/blob/32caa4b93d16a4dc64686b6871b3d597ee8e9b5b/src/scantopath/modules/viewer3d/presentation/view.py)
- [PLY renderer](https://github.com/vdtrong2051/sacntopath/blob/32caa4b93d16a4dc64686b6871b3d597ee8e9b5b/src/scantopath/modules/viewer3d/infrastructure/render_ply.py)
- [Camera renderer](https://github.com/vdtrong2051/sacntopath/blob/32caa4b93d16a4dc64686b6871b3d597ee8e9b5b/src/scantopath/modules/viewer3d/infrastructure/render_navigation.py)
- [VTK point picker](https://github.com/vdtrong2051/sacntopath/blob/32caa4b93d16a4dc64686b6871b3d597ee8e9b5b/src/scantopath/modules/viewer3d/infrastructure/pick_point.py)
- [Project workflow proxy](https://github.com/vdtrong2051/sacntopath/blob/32caa4b93d16a4dc64686b6871b3d597ee8e9b5b/src/scantopath/modules/project_workspace/presentation/workflows/base.py)
- [Architecture boundary checker](https://github.com/vdtrong2051/sacntopath/blob/32caa4b93d16a4dc64686b6871b3d597ee8e9b5b/scripts/check_architecture_boundaries.py)
- [07.12 quality checker](https://github.com/vdtrong2051/sacntopath/blob/32caa4b93d16a4dc64686b6871b3d597ee8e9b5b/scripts/check_07_12_quality.py)
