# R5.1 - Hop dong du lieu Scene & Geometry

**Baseline:** `feat/gd1-desktop-ui@46427d7f37e1de287373a5eab1ed85b1cf9f64bb` (R4.5). Muc tieu: bo nap 3D trong Render Host, chua thay Viewer/PySide6.

## Nguyen tac

- `SceneSource`, `SceneDescriptor`, `SceneSelectionRef` o application: DTO bat bien, khong import Qt, VTK, SQLite.
- `infrastructure/scene_reader.py` chi duoc dung trong tien trinh Render Host, nhan PLY vertex, PLY co mat da giac va OBJ mesh.
- `ResidentRenderClient.open_source` su dung IPC moi `open_scene`. `open_ply` cu van chi chap nhan vertex-only PLY; khong pha kiem thu R4.1.
- `CoalescingRenderSession.open_source` dua tai tep vao worker, co ACK frame va revision nhu R4.3.
- Phan loai: `points` neu `face_count=0`; `mesh` neu co mat. PLY co faces giu actor surface, khong glyph hoa am tham. OBJ khong co mat bi tu choi.
- `point_count` la so dinh; `face_count` la so polygon goc, khong mac dinh la so tam giac. `bounds` XYZ, SHA-256, dung luong va ten tep duoc lay tu nguon.
- Du lieu ngoai khong du chung minh don vi mm/m, he toa do, CAD, pose hoac sai so. `units` va `coordinate_frame` bat buoc `unknown`.
- `SceneSelectionRef` chi la hop dong tham chieu diem/mat cho R5.3. R5.1 CHUA co native screen ray picker va Inspector.

## Bao ve nguon

- Chi duong dan tuyet doi, tep thuong, khong nhan symlink ngay tai path; PLY tuan thu gioi han `inspect_ply` (256 MiB, 1.5M dinh).
- OBJ: 256 MiB, 1.5M dinh, 3M mat, do dai moi dong duoc chan. Chi doc `v`, `vt`, `vn`, `f`, `o`, `g`, `s` va comment; chi so OBJ duong hop le, khong nhan index am, khong mo `mtllib`/texture ben ngoai. Thuoc tinh UV/normals chua duoc cam ket hien thi day du.
- Kiem tra fingerprint truoc va sau VTK reader; khong ghi PLY/OBJ nguon, RAW hoac SQLite.
- Khi nhan `expected_sha256`, file sai SHA phai bi tu choi. Khong tai/hash lai sau moi orbit/pan/zoom.

## Hop dong chuyen giao R5.2

- Controller/UI khong import VTK. R5.2 dung `open_source`/`FrameSnapshot`, hien thi khung hinh RGB sau copy va ACK; kiem tra scene/frame/input revision.
- Chua doi ten `viewer3dPreview`, `viewer3dOpenPlyButton` va cac objectName cu. Tat ca nut, thong bao, tooltip danh cho nguoi dung o R5.2/5.3 phai la tieng Viet; API, ma loi va file code giu tieng Anh.
- PLY/OBJ mat phai duoc hien thi dung geometry kind; khong tu tao metric provenance.

## Test va dieu kien PASS

1. Pytest R5.1: points RGB, polygon PLY, OBJ quad va normals/UV index, malformed OBJ, SHA, DTO, async ACK, legacy R4.
2. Architecture Guard 07.11 + Quality Gate 07.12, full Python/Qt regression, CTest 2/2 tren Windows.
3. CLI demo sinh 3 fixture trong thu muc tam, mot PID VTK xu ly ca 3, tra JSON PASS va khong sua tep nguon.
4. R5.1 khong chung minh native picking, texture/MTL, live Qt viewport, crash khi VTK dang ban, FPS. Cac hang muc nay la R5.2-R5.3/R6.

Loi co that khi phat trien R5.1: khoi tao VTK mapper truoc khi RenderWindow co the tao frame toan background, lam 3 bai R4.1/R4.3 FAIL. Fix: khoi tao RenderWindow truoc pipeline VTK mapper. Giu lai log trong `_setup/evidence/R5_01_OPERATOR_JOURNAL.md` de R7 tong hop.
