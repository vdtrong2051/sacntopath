# UXH-01.8 — Kiểm toán vòng đời tài nguyên

> Mức hiện tại: `SOURCE_REVIEWED`; số liệu/process Windows thực tế ở UXH-01.8: `NOT_TESTED` cho đến khi có receipt.

| Tài nguyên | Owner / cơ chế | Test/evidence | Rủi ro còn lại |
|---|---|---|---|
| Native Gemini 2 | Camera subprocess (`ProcessIsolatedCameraAdapter`) | H01/H02/H03; worker stop/reopen | USB loss/hardware SDK crash khác import DLL fail; cần probe thật |
| Qt Live Worker | `LiveStreamWorker`, lifecycle controller | H03 / HMI | Đóng cửa sổ lúc SDK bận cần HMI |
| Viewer Render Host | `ResidentRenderClient`, `CoalescingRenderSession` | A06 + M07/M08 | Crash native/fault injection không được suy từ offscreen |
| Shared memory | `ResidentRenderClient.close()` | A06 | Kiểm tra child/SHM sau close trên Windows |
| Preview scratch PLY | `PreviewScratchLeases`, Scene retirement | A05/A07 + M06 | Synthetic stress không tương đương real VTK file lock |
| Measurement references | Geometry preview bridge / measurement UI | A05 + M05 | Chọn Capture/Scene mới không giữ số đo cũ |
| Qt timers / event loop | Controller/preview availability & poll | A02/A05 + M08 | Cần quan sát đóng lúc busy thật |
| Test RAW/SQLite | Capture store, replay read-only | A04 + M03/M04 | Dùng test store riêng, không đụng dữ liệu nghiên cứu |

## Ngưỡng và phương pháp

- 100 chu kỳ scratch stress phải trả `remaining=0`; đây là phép thử **quyền sở hữu tệp**, không phải phép đo FPS/RAM.
- Native cleanup test phải xác thực child đã thoát và `_shm is None`; khác với việc process không crash khi rút USB bất ngờ.
- Với real HMI, ghi nhận PID trước/giữa/sau, process mồ côi, dung lượng temp và tình huống close-while-busy. Không tuyên bố memory leak-free chỉ từ một snapshot.
- Đóng Qt không được cưỡng bức kết thúc thread; giữ cơ chế reaping hiện có. Không tự tăng timeout để giấu sự cố.

## Các rủi ro không đóng bởi UXH

Hiệu chuẩn metric, đồng bộ temporal được đo lường, GPU VRAM và native busy/fault toàn diện cần evidence riêng. `GD2_09_07_ACCEPTANCE_WITH_LIMITATIONS.md` có ghi native camera child failure khi rút USB; đây không phải bằng chứng bug đã được sửa. Mục tiêu UXH là an toàn GUI và quản lý lifecycle đã kiểm được, không tuyên bố firmware/SDK an toàn mọi trạng thái.
