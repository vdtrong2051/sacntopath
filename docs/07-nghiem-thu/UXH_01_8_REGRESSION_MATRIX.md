# UXH-01.8 — Ma trận regression và trạng thái gate

> `as_of_source: 016f0cf06de65a432626bb58ec8868483b30eb04` · `new_windows_receipt: NOT_TESTED` lúc tạo hồ sơ.  
> Runner tạo receipt thật ngoài repository; kết quả gate bên dưới là **định nghĩa/tiêu chí**, không phải khai báo PASS.

| Gate | Phạm vi | Công cụ/bằng chứng | PASS khi |
|---|---|---|---|
| U18-S00 | Branch, HEAD, working tree, runtime | `install.py --verify`, Git status | Baseline đúng, không thay đổi ngoài whitelist |
| U18-A01 | Kiến trúc 01.1/01.7 | Pytest `tests/contracts/kien_truc/test_uxh_*` | Thực thi >0, 0 fail, 0 skip |
| U18-A02 | Toolbar, Viewer UI, responsive | Qt offscreen tests UXH 01.2, 01.7 | Thực thi >0, 0 fail, 0 skip |
| U18-A03 | Picking & stale results | Tests UXH 01.5 | Thực thi >0, 0 fail, 0 skip |
| U18-A04 | Capture → RAW / workflow | Tests UXH 01.3/01.4, Capture layout | Thực thi >0, 0 fail, 0 skip |
| U18-A05 | Geometry/Depth/leases | Tests 01.1/01.6 và measurement | Thực thi >0, 0 fail, 0 skip |
| U18-A06 | Native Render Host & shared memory | `tests/native/viewer/test_uxh_01_6_native_cleanup.py` | Chạy trên Windows, exit 0, no skip |
| U18-A07 | Scratch lease stress 100 vòng | `scripts/uxh_01_6_preview_stress.py --cycles 100` | Exit 0 và `remaining=0` |
| U18-A08 | Full regression + CTest | `scripts/verify.ps1 -Profile Full` / `R8.4 SUMMARY.json` | Full PASS, receipt có JUnit/CTest thực |
| U18-H01 | SDK runtime | `load_native()`, `--once` | DLL import, Gemini 2 real RGB-D capture thành công |
| U18-H02 | Live 60 giây | `gd2_09_05_live_probe.py --seconds 60` | Có khung hình, không có error |
| U18-H03 | GUI camera lifecycle | `gd2_09_07_3_hardware_probe.py --cycles 2 --seconds 8` | 2/2 vòng và child cleanup thành công |
| U18-M01…M09 | HMI/DPI/nguồn/cleanup và operator review | `MANUAL_RECEIPT.json` + ảnh/log lưu ngoài Git | Mỗi case có PASS và locator thực, reviewer xác nhận |

`--with-camera` là opt-in; nếu không chạy, ba gate H01–H03 phải là `NOT_TESTED` và **không được khóa final**. Automated Qt offscreen không chứng minh performance native, USB unplug stress, GPU/VRAM hoặc latency vật lý. Skip, waiver, `NOT_TESTED` không được tự biến thành PASS.

**Lệnh:** `powershell -ExecutionPolicy Bypass -File RUN_UXH_01_8.ps1 -Repo <repo> [-WithCamera]`. Kết quả trong `_setup/UXH_01_8/evidence/RUN_<UTC>_<pid>/SUMMARY.json` và log theo gate.
