# UXH-01.8 — Quy tắc khóa baseline

**CANDIDATE**, không phải dấu đóng sẵn:

- Branch: `feat/gd2-uxh-01-hardening`
- Parent baseline UXH-01.7: `016f0cf06de65a432626bb58ec8868483b30eb04`
- Trạng thái hiện hành khi soạn: `LOCK_PENDING_WINDOWS_ACCEPTANCE`.

## Gate khóa

1. Tất cả A01–A08, H01–H03 có receipt PASS hợp lệ, source SHA trùng baseline và log ngoài Git.
2. M01–M09 được operator kiểm tra trên Windows và xác nhận PASS theo evidence locator thực tế.
3. `git diff --check`, whitelist + đường dẫn docs, không data/SDK/generated logs bị stage.
4. Tất cả P0 đóng; P1 có quyết định chấp nhận giới hạn rõ ràng.
5. Final receipt được tạo và commit riêng, HEAD sau commit được lấy từ Git thật. Không bịa trước SHA.

Khóa UXH không chứng nhận GĐ2/GĐ3. Khi commit, dùng Git `git log -1`, `git status --short` và ghi SHA thật vào hồ sơ bàn giao bên ngoài hoặc commit sau nếu cần. Không push/merge trong script.
