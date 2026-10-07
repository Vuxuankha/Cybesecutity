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
- SQLite/runtime: lưu tại `runtime_data` cạnh ứng dụng để có thể chép nguyên thư mục sang máy Windows khác và giữ tài khoản/cấu hình.
- Không có public registration; Admin đầu tiên được tạo ở lần chạy đầu.

## Build Windows

Chạy `BUILD_WINDOWS.bat` trên Windows có Python 3.11, 3.12 hoặc 3.13 và Inno Setup 6, hoặc push lên GitHub để workflow Windows tự build. Build release dùng `requirements-lock.txt`; QA/build dùng `requirements-dev.txt`.

Đầu ra:

`release\NetworkAutomation_Setup_7.0.3.exe`

Người dùng cuối chỉ cần cài bộ cài. Python và các dependency được đóng gói cùng ứng dụng.

## Dữ liệu

Dữ liệu vận hành nằm trong thư mục `runtime_data` cạnh ứng dụng. Khi đổi máy, hãy chép **toàn bộ thư mục ứng dụng**, bao gồm `runtime_data`, để giữ tài khoản Admin, cấu hình, `known_hosts` và khóa mã hóa. Gói phát hành sạch không chứa dữ liệu người dùng có sẵn.


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


### Export CSV / Excel
Trong ứng dụng Desktop, các bảng hỗ trợ cả **Xuất CSV...** và **Xuất Excel...**. Khi xuất, Windows sẽ mở hộp chọn thư mục đích; file được ghi trực tiếp vào thư mục đã chọn và không tự ghi đè file cùng tên.

## Windows Local Tools - không cần Kali Linux

Từ QA79, khu vực Hacker Mũ Trắng và Hacker Mũ Đỏ không còn phụ thuộc Kali Linux/SSH/VM. Ứng dụng dùng **PowerShell/CMD và các công cụ Windows có sẵn** thông qua backend whitelist.

- **Mũ trắng:** ping, DNS, TCP port, route, ARP, TCP connections, HTTP/HTTPS headers, TLS/certificate, SHA-256 file, process, service, Firewall, Event Log, adapter/IP, traceroute và server/network status.
- **Mũ đỏ:** chỉ dành cho kiểm thử được phép: private-host reconnaissance/config/connectivity, HTTP headers, TLS, cookie/session audit, local network state và tải nhẹ tối đa 5 HEAD request tuần tự.
- Giao diện không có ô chạy command tùy ý. Backend chỉ chạy profile định nghĩa sẵn, ẩn console, có timeout/output cap và tự cleanup process khi đóng app.
- Các tác vụ mạng chủ động bị giới hạn vào private/loopback/link-local target; không có exploit, brute-force, persistence, reverse shell, sniffing hay flood/DDoS.


## QA81 - sửa lỗi chọn thư mục xuất CSV/Excel
- Nút **Xuất CSV...** và **Xuất Excel...** không còn phụ thuộc trực tiếp vào `window.pywebview.api`.
- Backend Desktop mở hộp chọn thư mục Windows qua API local; nếu native picker lỗi sẽ dùng PowerShell/WinForms chạy ẩn làm fallback.
- Bấm Hủy không tạo file và không hiện lỗi đỏ.
- Asset revision: `70400`.

## QA82 - đo mạng chính xác hơn
- Không còn dùng ping cố định tới `1.1.1.1` để quyết định `POOR/FAIR/GOOD`; số này chỉ còn là tham chiếu.
- Internet latency được đo bằng nhiều TCP handshake tới cùng máy chủ CDN dùng cho Speed Test và lấy median để giảm outlier.
- Download/upload dùng warm-up, nhiều luồng và dung lượng thích ứng (tối đa khoảng 128 MB tải xuống / 64 MB tải lên) để tránh kết quả thấp giả trên đường truyền nhanh.
- Trang Tốc độ mạng dùng phép đo gần nhất (line hoặc speed test) cho các card Latency/Jitter/Grade.
- Kết quả vẫn có thể khác Ookla/Fast.com vì máy chủ và thuật toán khác nhau; app hiển thị rõ máy chủ/phương pháp đo.
- Asset revision: `70400`.


## QA83 - sửa Speed Test không hiện Download/Upload
- Sửa timeout frontend 20 giây làm Speed Test bị hủy trước khi hoàn tất.
- API helper hỗ trợ timeout riêng cho tác vụ dài; Speed Test có thể chờ tối đa 180 giây, kiểm tra đường truyền 45 giây và chẩn đoán chi tiết 60 giây.
- Khi chưa có phép đo tốc độ mới, card Download/Upload hiển thị **Chưa đo** thay vì dấu `-`.
- Progress Speed Test thông báo rõ phép đo đa luồng có thể mất 30–120 giây tùy đường truyền.
- Asset revision: `70404`.

### QA84 language selector

The Desktop UI supports **Tiếng Việt**, **中文（简体）**, and **English**. Use the language selector on the login screen or in the main header. The selection is saved locally and restored on the next launch. Raw technical output (IP/MAC, host names, logs, code, PowerShell/CMD output) is deliberately not translated.

### QA85 language switching runtime fix
- Fixes the WebView2 MutationObserver feedback loop that could make the language dropdown visible but leave the UI unchanged.
- Vietnamese / Simplified Chinese / English now switch immediately on the login screen and inside the application.
- Language selector events are delegated, localStorage failures no longer abort i18n, and login placeholders/capability bullets are translated.
- Asset revision: `70404`.

## QA86 - Full Trilingual UI

Bản QA86 dùng asset revision `70404` và hoàn thiện giao diện ba ngôn ngữ Tiếng Việt / 中文（简体） / English trên toàn bộ UI, kể cả nội dung động và thông báo WebAPI. Dữ liệu kỹ thuật thô (IP/MAC/hostname/log/code/output PowerShell) được giữ nguyên để tránh làm sai dữ liệu.


### QA87 – đo tuyến trong nước và quốc tế riêng biệt

Bản QA87 dùng **tuyến trong nước làm chất lượng chính**. Ứng dụng tự thử nhiều điểm TCP 443 tại Việt Nam và chọn điểm phản hồi nhanh nhất để tính latency/jitter/loss. Tuyến quốc tế/CDN được hiển thị riêng và không kéo điểm trong nước xuống `POOR`. Nút **Kiểm tra trong nước** là phép đo mặc định; **Kiểm tra quốc tế** là phép đo tham khảo. Download/Upload vẫn là bài đo băng thông CDN riêng. Có thể thay danh sách điểm trong nước bằng biến môi trường `NA_DOMESTIC_PROBE_HOSTS`.

Asset revision: `70405`.
