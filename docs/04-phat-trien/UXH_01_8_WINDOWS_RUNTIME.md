# UXH-01.8 — Orbbec Gemini 2 runtime trên Windows

> Bổ sung cho [hướng dẫn cài đặt](CAI_DAT_VA_CHAY.md), không thay build/SDK. Bằng chứng: operator đã gặp và khắc phục lỗi DLL load thiếu env tại UXH-01.6; lần chạy Windows mới phải có receipt.

1. Nạp native extension qua `scantopath.acquisition.native.load_native()`; Windows Python 3.8+ không thể chỉ dựa vào `PATH` khi tải DLL phụ thuộc của `.pyd`.
2. Đặt `SCANTOPATH_ORBBEC_SDK_BIN` thành **thư mục chứa `OrbbecSDK.dll`**, không trỏ trực tiếp tệp DLL. Giá trị trên máy operator tại 01/11/2026: `E:\1_BigProject\scantopath\_sdk\OrbbecSDK_v2.10.6\bin`; máy khác phải kiểm tra thực tế.
3. Kiểm tra `Test-Path (Join-Path $env:SCANTOPATH_ORBBEC_SDK_BIN 'OrbbecSDK.dll')` và chạy:

```powershell
& .\.venv\Scripts\python.exe -X utf8 -c "from scantopath.acquisition.native import load_native; load_native(); print('NATIVE_LOAD=PASS')"
```

4. Biến `$env:` chỉ sống trong process PowerShell hiện hành. Sau khi đã xác nhận chính xác SDK bin, để giữ giữa các phiên:

```powershell
[Environment]::SetEnvironmentVariable('SCANTOPATH_ORBBEC_SDK_BIN', $env:SCANTOPATH_ORBBEC_SDK_BIN, 'User')
```

Đóng VS Code/terminal cũ, mở terminal mới và thử `NATIVE_LOAD` **không gán lại biến**. Cần đăng xuất/đăng nhập nếu GUI launcher vẫn dùng môi trường cũ.

5. Đóng Orbbec Viewer/ứng dụng khác trước khi mở ScanToPath; kết nối camera bằng nút **Kết nối**, ứng dụng không auto-open khi khởi động. Sau khi đóng app, có thể rút camera; khi làm việc lại, cắm USB3.0 trực tiếp trước rồi mở ứng dụng.
6. `Windows PnP Status OK` chỉ xác nhận enumeration; `NATIVE_LOAD=PASS` chỉ xác nhận DLL; `--once` + live probe mới là kiểm chứng mở thiết bị/frameset.
7. Không lưu đường SDK tuyệt đối vào source, không copy DLL vào Git, không thay firmware/SDK hoặc recompile để sửa một lỗi env. Nếu native child bị lỗi khi rút camera lúc streaming, ghi incident riêng; không được hứa reconnect tự động.

Bộ UXH-01.8 cung cấp gate H01–H03 **chỉ chạy khi operator bật `-WithCamera`**; log/receipt lưu ngoài repository.
