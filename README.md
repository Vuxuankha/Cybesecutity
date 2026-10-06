# NetworkAutomation Desktop 7.0.3 — Desktop Only

## Startup fix 7.0.3

- Fixed Uvicorn `formatter 'default'` startup error on Windows/Python 3.13.
- Account password length is unrestricted; only an empty password is rejected.
- Source startup now uses a versioned environment under `%LOCALAPPDATA%\NetworkAutomation\venvs`; an old or locked `.venv` beside the source can no longer block startup.

Bản phát hành này chỉ dành cho **Windows Desktop**. Ứng dụng chạy cục bộ, lưu dữ liệu cục bộ và đọc mạng trực tiếp từ Windows.


## Fast Start / mở ứng dụng nhanh

Bản QA93 tối ưu riêng đường khởi động Desktop:

- Cửa sổ WebView được tạo ngay trước khi backend hoàn tất warm-up, vì vậy người dùng nhận phản hồi trực quan ngay khi mở app.
- Những lần mở sau dùng môi trường Python đã xác thực và bỏ qua dò Python/import dependency nặng.
- Nếu database đã ở đúng schema 7.0.3, app không replay toàn bộ migration/backup/table setup ở mỗi lần mở.
- Worker nền (scheduler, jobs, endpoint monitor, automation, network identity) khởi động sau khi HTTP/UI đã sẵn sàng.
- Bản EXE build bằng PyInstaller tắt UPX để giảm thời gian giải nén DLL và giảm overhead quét antivirus lúc cold start.

Lần chạy đầu hoặc sau khi nâng cấp vẫn có thể lâu hơn vì app phải tạo môi trường, migrate schema hoặc cài dependency. Các lần mở sau là đường fast-start.

## Mạng Windows Native

Ứng dụng tự đọc adapter đang hoạt động, IPv4 LAN, subnet, default gateway, bảng ARP/Neighbor, ping gateway và ping các địa chỉ đã quan sát. Dashboard cập nhật dữ liệu LAN từ chính máy đang chạy ứng dụng.

## Kiến trúc

- `desktop_launcher.py`: khởi động ứng dụng và cửa sổ Desktop.
- FastAPI/Uvicorn: engine nội bộ chỉ bind `127.0.0.1` để phục vụ giao diện ứng dụng.
- HTML/CSS/JS: giao diện nội bộ hiển thị trong WebView2; không phải dịch vụ public.
- SQLite/runtime: lưu tại `%LOCALAPPDATA%\NetworkAutomation`.
- Không có public registration; Admin đầu tiên được tạo ở lần chạy đầu.

## Build Windows

Chạy `BUILD_WINDOWS.bat` trên Windows có Python 3.11, 3.12 hoặc 3.13 và Inno Setup 6, hoặc push lên GitHub để workflow Windows tự build. Build release dùng `requirements-lock.txt`; QA/build dùng `requirements-dev.txt`.

Đầu ra:

`release\NetworkAutomation_Setup_7.0.3.exe`

Người dùng cuối chỉ cần cài bộ cài. Python và các dependency được đóng gói cùng ứng dụng.

## Dữ liệu

Dữ liệu vận hành không nằm trong thư mục cài đặt và không được đóng vào source release. Upgrade/uninstall không được dùng để xóa dữ liệu người dùng ngoài quy trình xác nhận riêng.


## Khởi động không hiện CMD/PowerShell

Để bảo đảm không hiện cửa sổ CMD, hãy mở `00_MO_APP_NETWORKAUTOMATION.vbs` (khuyên dùng) hoặc `MO_APP_NETWORKAUTOMATION.vbs`. Các launcher `.bat` khởi động source đã được chuyển vào `_internal\launcher` để tránh người dùng nhấp nhầm. Môi trường Python được đặt trong `%LOCALAPPDATA%\NetworkAutomation\venvs`, không xóa `.venv` cũ cạnh source. Log bootstrap nằm tại `runtime_data\logs\desktop_bootstrap.log`.


## WebView2 prerequisite

Ứng dụng kiểm tra Microsoft Edge WebView2 Runtime trước khi mở giao diện. Nếu thiếu, app dừng với thông báo rõ ràng thay vì lỗi cửa sổ chung.
## Khởi động bản source trên Windows

- **Nên mở `00_MO_APP_NETWORKAUTOMATION.vbs`** để khởi động không hiện cửa sổ CMD.
- Bản source hỗ trợ Python **3.11, 3.12 và 3.13**; khuyến nghị Python 3.12 x64.
- Nếu máy chưa có Python tương thích, launcher sẽ hỏi có muốn tự động cài Python 3.12 bằng `winget` hay không.
- Lần chạy đầu có thể mất vài phút vì ứng dụng tạo môi trường Python theo phiên bản trong `%LOCALAPPDATA%\NetworkAutomation\venvs` và cài dependency; tiến trình được ghi tại `runtime_data\logs\desktop_bootstrap.log`.
- `.venv` cũ cạnh source không còn được dùng hoặc xóa. Nếu môi trường theo phiên bản bị lỗi/đang bị khóa, launcher giữ nguyên nó và tạo một repair environment mới.
- Không chạy trực tiếp các file `.bat` trong `_internal\launcher`; chúng chỉ là bootstrap nội bộ được VBS gọi ở chế độ ẩn.

