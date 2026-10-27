# Cấu trúc mã nguồn và vị trí cần sửa

Tài liệu này là bản đồ điều hướng theo các đường dẫn đã đối chiếu ở GĐ1; không đề nghị đổi tên package/namespace trong R7.

```text
scantopath-software/
├── src/scantopath/
│   ├── ui/                         # Cửa sổ, điều hướng, tiện ích Qt chung
│   │   ├── shell/                  # Composition root, Viewer bootstrap/Inspector bridge
│   │   ├── components/             # Dock, Explorer, PropertyInspector
│   │   └── workspaces/             # Các trang workspace
│   ├── modules/
│   │   ├── project_workspace/      # Chức năng quản lý dự án
│   │   └── viewer3d/               # DTO, tương tác Qt, hạ tầng Render Host
│   ├── metadata/                   # SQLite metadata, trạng thái và audit
│   ├── storage/                    # RAW và registry lưu trữ
│   ├── acquisition/                # Nguồn thu nhận RGB-D/native bridge
│   ├── domain/                     # Hợp đồng miền dữ liệu dùng chung
│   └── application/                # Điều phối/hợp đồng ứng dụng dùng chung
├── cpp/                            # C++20/CMake/Orbbec
├── scripts/                        # Công cụ kiểm thử, kiểm tra kiến trúc
├── tests/                          # Bộ hồi quy Python/Qt/native ở mức hợp đồng
└── docs/                           # Bộ tài liệu tiếng Việt hiện hành + lịch sử
```

## Điểm vào của chức năng

| Muốn thay đổi | Bắt đầu từ | Ranh giới |
|---|---|---|
| Cửa sổ và dock | `src/scantopath/ui/shell/main_window.py` | Không nhét thuật toán VTK/SQL vào Qt shell |
| Viewer live/fallback | `src/scantopath/ui/shell/viewer_bootstrap.py` | Chỉ lắp ráp phụ thuộc |
| Chọn điểm/mặt, công cụ | `src/scantopath/modules/viewer3d/presentation/interactive_controller.py` | Không import VTK trong presentation |
| Render và IPC | `src/scantopath/modules/viewer3d/infrastructure/resident_poc/` | Không import Qt UI vào hạ tầng |
| Bảng thuộc tính | `src/scantopath/ui/shell/viewer_inspector_bridge.py` | Không biến PLY thành Project SQLite |
| Project logic | `src/scantopath/modules/project_workspace/` | Dịch vụ ứng dụng sở hữu truy cập metadata |
| RAW | `src/scantopath/storage/` | Không sửa dữ liệu nguồn khi chỉ đọc |

## Nguyên tắc bảo trì

Luôn đối chiếu đường dẫn với Git ở commit đang làm việc. Không xóa facade/compatibility chỉ vì có module mới: phải kiểm caller/import động và regression. Không thay đổi bộ kiểm thử trong R7-B; R8 mới xử lý kiến trúc test.
