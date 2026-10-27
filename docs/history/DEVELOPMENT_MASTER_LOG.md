# ScanToPath — Nhật ký phát triển tổng (canonical index)

**Tạo tại R7 (27/10/2026), hồi cứu trên GitHub và log người vận hành.** Đây là nhật ký tổng hợp, không thay thế log terminal hay tạo số attempt chưa biết. Trạng thái phân tách module, automated và HMI.

| Mốc | Git/baseline đã nêu | Kết quả / nguồn | Nhãn |
|---|---|---|---|
| GĐ0 PRE-01–06 | PR #3, merge `8bf33591389dcdff82f0fbd5bf5932a22547c984` | RAW Gemini 2 real-shot, SQLite, 80 passed/1 skipped, CTest 2/2 trong hồ sơ | VERIFIED (Git/docs), OPERATOR_REPORTED (hardware) |
| GĐ1 06–08 (bản đầu) | Phiên 06/07/08 theo hồ sơ `docs/gd1/` | Shell/Project/legacy preview, lỗi crash Qt–VTK / latency/UX dẫn tới rebaseline | PARTIAL_EVIDENCE |
| R1–R3.5 | R3.5 commit `8c295e0` | Nâng UX shell, Project, Inspector, workflows; R3.5 test/HMI theo hồ sơ | VERIFIED/PARTIAL_EVIDENCE |
| R4.1–R4.5 | R4.5 `46427d7f37e1de287373a5eab1ed85b1cf9f64bb` | So sánh A/B, lựa chọn B isolated resident **có điều kiện** | VERIFIED (Git/docs), PARTIAL_EVIDENCE (HMI/native) |
| R5.1 | `1019127803d6eac391ed2f5ea567c254feecaf2c` | Geometry contracts PLY/OBJ, provenance | VERIFIED (Git) |
| R5.2 | `2ec6e7dbd4c9ba6933cbee1b0d44081470ba84b3` | Qt live viewer, sửa lỗi shell 511 dòng và deprecation Qt | VERIFIED (Git), OPERATOR_REPORTED (tests/HMI) |
| R5.3 | `ff45ccf87ce770e25eedf6e12df6bb5aaa958734` | Picking/Inspector, rework công cụ/icon/lưới, sửa fixture và R5.2 compatibility | VERIFIED (Git), OPERATOR_REPORTED (tests/UI) |
| R6 automated | `ff45ccf` (không đổi source) | **14/14 PASS**; 618 passed, 3 skipped, CTest 2/2, native probe, benchmark | OPERATOR_REPORTED |
| R6 overall | Cùng baseline | **PENDING** HMI/DPI, native-busy, real C++ fault, GPU/VRAM, present latency | NOT_TESTED/PARTIAL_EVIDENCE |
| R7 tài liệu | Baseline `ff45ccf` | Gói R7: chuẩn hóa docstring, docs theo chức năng, journal, doc gate; **chưa xác nhận trên Windows trước verify** | PENDING |
| R8 / 08.06.6 | Sau R7 | Test mapping, consolidation, permanent gates, freeze | NOT_STARTED |

**Nguồn chi tiết:** [GĐ0 journal](GD0/GD0_EXECUTION_JOURNAL.md) · [GĐ1 journal](GD1/GD1_EXECUTION_JOURNAL.md) · [incident register](GD1/INCIDENT_REGISTER.md) · [R6 status](../acceptance/GD1_R6_ACCEPTANCE_STATUS.md).

**Không được gộp:** một lượt pytest PASS không xóa attempt FAIL trước đó; comment lỗi runner của R6 không chứng minh source ScanToPath lỗi; bộ render benchmark không chứng minh FPS màn hình thật. Thay đổi kết luận phải thêm bản ghi correction kèm căn cứ.
