# UXH-01.8 — Giới hạn và backlog sau closure

> Không được tự nhận các hạng mục dưới là đã triển khai hoặc đo lường.

| ID | Mức | Giới hạn | Cách xử lý / trách nhiệm |
|---|---|---|---|
| UXH-L01 | P1 | SDK DLL phụ thuộc biến môi trường trong process Windows (`SCANTOPATH_ORBBEC_SDK_BIN`), chưa có app installer tự tìm/đóng gói SDK | Ghi hướng dẫn thiết lập persistent trong [runtime](../04-phat-trien/UXH_01_8_WINDOWS_RUNTIME.md); đưa vào backlog đóng gói |
| UXH-L02 | P1 | Camera child native có thể crash nếu mất USB trong lúc streaming; GUI được cô lập nhưng retry/hardware fault recovery chưa được chứng minh đầy đủ | Không làm hot-unplug stress trong UXH-01.8 nếu chưa có protocol an toàn; dự án camera hardening riêng |
| UXH-L03 | P1 | DPI/hardware native HMI chưa có receipt UXH-01.8 cho tới khi operator thực thi | Manual receipt bắt buộc |
| UXH-L04 | P2 | Viewer Canvas/toolbar là UI working baseline, chưa đo hiệu suất GPU/VRAM/display-present latency | Không tuyên bố performance certification |
| UXH-L05 | P2 | Geometry Preview là single-view XYZRGB tham chiếu, Depth A–B không tự chứng minh sai số metrology | GD2 metric trust thuộc kế hoạch riêng |
| UXH-L06 | P2 | Raw-to-multiview fusion, mesh đáng tin, normals, segmentation và robot path không phải năng lực UXH | Quay về roadmap GD2/GD3, không mở UXH-01.9 |
| UXH-L07 | P2 | Các trang module cũ có metadata snapshot trước UXH; phụ lục UXH-01.8 cung cấp delta, chưa đồng bộ từng dòng của toàn bộ docs | DOC future maintenance, không ghi đè snapshot lịch sử |

Mọi phát hiện P0 trong regression/hardware/HMI thực tế chặn khóa baseline. P1 phải có quyết định chấp nhận rủi ro cụ thể, không được đánh đồng với PASS.
