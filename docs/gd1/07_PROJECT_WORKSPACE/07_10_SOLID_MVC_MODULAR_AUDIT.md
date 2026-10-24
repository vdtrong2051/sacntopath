# GĐ1 — 07.10: Kiểm toán SOLID / MVC / Modular Monolith (evidence-based)

**Mốc khảo sát:** `feat/gd1-desktop-ui` @ `19e950c9a3bcd5ed08decb59f8d1fd1b203536ba`. Audit dựa trên source Python đã đối chiếu Git blob và công cụ AST `scripts/gd1_architecture_audit.py`; không có quyền xác nhận độ ổn định runtime ngoài kết quả kiểm thử của người vận hành. **Không tự refactor mã nghiệp vụ trong phiên này.**

## 1. Kết luận kỹ thuật

**Chưa thể chứng nhận đạt đầy đủ SOLID.** Repo có cấu trúc modular/layered tốt hơn monolith một tệp, và có View / ViewModel / Controller / Application Service / persistence tách tương đối rõ. Tuy nhiên **chưa phải modular monolith lai MVC rõ ràng theo feature boundary**: module project workspace bị chia theo technical folders; MainWindow và service đảm nhiệm nhiều use-case. Không đủ bằng chứng để gọi toàn bộ repo “spaghetti”, nhưng có **nguy cơ module-by-technical-layer phát triển thành tightly-coupled monolith** nếu tiếp tục cộng tính năng ở cùng controller/service.

## 2. Bằng chứng theo component (baseline trước HMI)

| Thành phần / nguồn | Quan sát có thể kiểm tra | Kết luận |
|---|---|---|
| `src/scantopath/ui/shell/main_window.py:ScanToPathMainWindow` | ~660 dòng / 41 method trước 07.9; `_install_project_loader`, `_install_project_writer`, `_install_capture_checker`, `_on_project_loaded`, `_on_project_written`, `_on_explorer_selection`, `closeEvent` cùng tồn tại | **SRP risk — High**: composition root đồng thời ôm orchestration, project and capture coordination |
| `src/scantopath/application/projects/service.py:ProjectWorkspaceService` | ~333 dòng / 26 method; `list_projects`, `get_project_tree`, `get_capture`, `list_events`, create/update/close, assign codes | **SRP/ISP risk — High**: một service có API read, write, codes, audit, integrity |
| `src/scantopath/metadata/store.py:MetadataStore` | ~535 dòng; ORM entities + CRUD + audit + capture/run logic | **SRP risk — Medium/High**; tập trung quan hệ SQLite ở một lớp |
| `src/scantopath/storage/numbered.py:NumberedStorageRegistry` | ~534 dòng; mã P/S/T/C/R, folder reservation, resolver và protect layout | **SRP risk — Medium**; có lý do transactional coupling nhưng cần ổn định interface |
| `src/scantopath/ui/projects/controller.py`, `write_controller.py`, `inspection_controller.py` | QThread worker riêng, GUI chỉ nhận signal/DTO; service được import sau khi chọn kho | **Separation — Good**, bảo toàn GUI responsive và start-up isolation |
| `src/scantopath/ui/projects/presentation.py` | ProjectLoadBundle/ProjectRow DTO-to-view; không chạy trực tiếp SQL | **MVC/ViewModel — Good** |
| `src/scantopath/application/projects/models.py` | DTO immutable được trả về service | **Boundary — Good** |
| `src/scantopath/application/projects/service.py` | `from scantopath.metadata.store import MetadataStore` và `from scantopath.storage.numbered import NumberedStorageRegistry` | **DIP — Partial**: cấp ứng dụng phụ thuộc concrete persistence, thiếu port/interface |
| `src/scantopath/ui/projects/write_controller.py` | factory service khởi tạo trong worker, không injection qua port thống nhất | **DIP/testability — Partial** |
| `src/scantopath/domain/` | Model dữ liệu và RAW contract không import Qt | **Dependency inward — Good** (AST phải kiểm lại trên checkout đầy đủ) |

## 3. SOLID: đánh giá không đánh đồng test-pass với architectural-pass

| Nguyên tắc | Trạng thái | Minh chứng và khoảng trống |
|---|---|---|
| **S** — Single Responsibility | ⚠️ Chưa đạt triệt để | MainWindow, WorkspaceService, MetadataStore có quá nhiều lý do thay đổi khác nhau. Tách GUI behavior ra coordinator chuyên trách theo feature khi cần. |
| **O** — Open/Closed | ⚠️ Một phần | Bổ sung một loại entity/hành động thường phải sửa `main_window.py`, `presentation.py`, `forms_contract.py`, service; thiếu dispatch/registry trên feature boundary. Không cần “plugin hóa” tràn lan ngay. |
| **L** — Liskov Substitution | ◻️ Chưa đủ điều kiện đánh giá | Ít abstraction/subtype nghiệp vụ công khai; không thể nói LSP pass hoặc fail nếu không có contract thay thế được. |
| **I** — Interface Segregation | ⚠️ Một phần | Một `ProjectWorkspaceService` nhiều nhiệm vụ; đề xuất read/write/audit/RAW verification ports nhỏ theo use case. |
| **D** — Dependency Inversion | ⚠️ Chưa đầy đủ | Application service phụ thuộc concrete `MetadataStore`/`NumberedStorageRegistry`; UI controllers dùng service factory; cần ports ở application boundary để adapter SQLite triển khai. |

## 4. MVC lai theo từng module: phần nào đã có, phần nào chưa

| MVC / Layers | Hiện hành | Đề xuất trách nhiệm |
|---|---|---|
| **Model** | `domain/models.py`, `domain/raw_rgbd.py`, immutable `application/projects/models.py` | Không import UI/Qt, không chứa DB session |
| **View** | `ui/components/*`, `ui/workspaces/pages.py`, dialogs | Chỉ render/signal/validation hình thức, không quản lý transaction |
| **Controller / ViewModel** | `ui/shell/main_window.py`, `ui/viewmodels/navigation.py`, `ui/projects/controller.py`, `write_controller.py` | Shell chỉ composition + cross-workspace, module controller tự orchestrate workflow UI |
| **Application use cases** | `application/projects/service.py`, `application/tasks/manager.py` | Nhận DTO/command, business validation, transaction coordination; phụ thuộc ports |
| **Infrastructure** | `metadata/store.py`, `storage/numbered.py`, `session_store.py`, acquisition native | SQLite/FS/device adapter; không phụ thuộc widget |

Hiện tại đã có **MVC responsibilities**, nhưng **chưa nhóm trọn một bounded context** theo module feature. Vấn đề không phải `MVC` vs `modular monolith` (hai khái niệm độc lập); có thể kết hợp mà không chồng lớp.

## 5. Kiến trúc đích (định hướng, KHÔNG đổi đường dẫn ngay)

```text
scantopath/
  modules/
    project_workspace/
      domain/             # business rules / typed state
      application/        # project CRUD, list/tree, commands, ports
      presentation/       # controller, presenter, dialog/view models
      infrastructure/     # SQLite project repo, numbered alias adapter
    capture/
      domain/
      application/
      presentation/
      infrastructure/     # Gemini2, RAW reader/writer adapters
    processing/
      domain/
      application/
      presentation/
      infrastructure/
  shared/
    contracts/            # stable typed messages, IDs, errors
    qt/                   # QSS, reusable HMI widgets
    core/                 # logging, clocks, guarded IO helpers
  shell/                  # composition root, workspace router only
```

**Modular monolith** nghĩa là một desktop process/deployment với **feature modules có API rõ**, không cần microservices. Bên trong mỗi feature có các vai trò Model–View–Controller và Application/Infrastructure; không bắt buộc lập đủ 4 thư mục cho một feature chưa có chức năng. UI desktop PySide6 là View layer, không đồng nghĩa mỗi widget phải có MVC phức tạp.

## 6. Backlog thay đổi — không chèn refactor vào patch theme

| Ưu tiên | Ticket | Tiêu chí nghiệm thu |
|---|---|---|
| P0 | ARC-01: `ProjectWorkspaceController` module-level orchestration, shell delegate | MainWindow không trực tiếp điều phối form/load/capture; 07.8/07.9 tests vẫn pass; không nạp SQLite lúc start |
| P0 | ARC-02: tách `ProjectReadService`, `ProjectWriteService`, `ProjectAuditQuery`, `CaptureIntegrityQuery` interfaces | Giữ API tương thích từ service façade, ID/storage immutability, coverage no regression |
| P1 | ARC-03: ports `ProjectMetadataPort`, `StorageRegistryPort`, adapters SQLite/numbered | UI/app test bằng fake port; không cần migrate DB, không làm tăng import ngược |
| P1 | ARC-04: architecture guard/graph trong CI | `scripts/gd1_architecture_audit.py` kết quả có report; fail nếu import inward→UI bất hợp lệ phát sinh; không fail chỉ vì file dài |
| P1 | ARC-05: feature module packaging theo migration map | mỗi bước nhỏ, giữ import compatibility, test + native self-test; không mass-move |
| P2 | ARC-06: tối ưu load all-trees, cache/pagination ở data lớn | benchmark với representative data (chưa có nghiệm thu hàng nghìn captures) |

## 7. Phương pháp audit + phạm vi khẳng định

`python scripts/gd1_architecture_audit.py --project-root . --out-dir <output>` quét Python AST, đếm files/dòng/method và đồ thị import trực tiếp. `ARCH_AUDIT.json`/`.md` được tạo **ngoài repo** khi verify. Không import app, không mở SQLite, không tính điểm SOLID máy móc, không kiểm tra C++ dependencies, Qt runtime graphs, dispatch động, hoặc decorator injection. Ở bản snapshot tái dựng tại môi trường phát triển: **43 file Python / 5.570 dòng / 6 structural hotspots / 0 inward-to-UI imports**, nhưng source tái dựng không phải full checkout; kết quả chuẩn trên Windows sẽ được tạo lại từ chính repository sau `apply.ps1`.

**Verdict:** Giữ baseline được nghiệm thu 07.8 và UI chỉnh nhẹ; cần refactor có kiểm soát ARC-01/02 **trước khi tích hợp nhiều module mới**, không coi việc đổi folder hoặc tạo giao diện mới là giải pháp SOLID.
