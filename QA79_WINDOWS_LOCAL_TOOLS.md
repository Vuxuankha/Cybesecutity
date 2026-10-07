# QA79 - Windows Local Tools / PowerShell-CMD Engine

## Mục tiêu

QA79 loại bỏ hoàn toàn Kali Linux khỏi runtime của NetworkAutomation Desktop. Không còn Kali Host, Kali Port, Kali Username, Kali Password/Key, Import/Test Kali hay `/api/v1/kali/*`.

## Backend mới

- API: `/api/v1/windows-tools/status`, `/profiles`, `/run`.
- Chỉ `/run` gây thực thi và chỉ cho Admin/Analyst/Operator.
- Frontend không thể gửi command/script/args tùy ý; request chỉ chứa `mode`, `profile`, `target`, `port`, `text`, `count`.
- PowerShell chạy `-NoProfile -NonInteractive` bằng `-EncodedCommand` do backend tự tạo.
- Tiến trình chạy ẩn (`CREATE_NO_WINDOW`), có timeout tối đa 60 giây, giới hạn stdout/stderr và gắn `NA_CHILD_KIND=windows-local-tool` để cleanup khi đóng app.
- Tác vụ mạng chủ động chỉ chấp nhận private/loopback/link-local target. HTTP private hostname được pin bằng `curl.exe --resolve` để tránh DNS đổi đích sau validation; không dùng `-k/--insecure`.
- TLS auditor kết nối tới IP đã validate, giữ SNI hostname và báo `PolicyErrors`; certificate không hợp lệ làm tác vụ trả trạng thái lỗi sau khi vẫn thu thập được metadata chứng chỉ.

## Mũ trắng

Các profile Windows-native:

- Tổng quan Windows
- Ping
- DNS lookup
- TCP port / server status
- Route table
- ARP / Neighbor
- TCP connections
- HTTP/HTTPS headers
- TLS / certificate
- SHA-256 file
- Processes
- Services
- Windows Firewall
- Windows Event Log
- Adapter / IPv4
- Traceroute
- Network state

Các panel Windows Local Tools được gắn trực tiếp vào TLS, Web Header, Firewall, Log và File Integrity pages.

## Mũ đỏ

Chỉ giữ kiểm thử được ủy quyền và chẩn đoán có giới hạn:

- Recon một private host
- Kiểm tra cấu hình Windows cục bộ
- Connectivity private host/port
- HTTP headers của private URL
- TLS/certificate audit private host
- Cookie/session attribute audit
- Local packet/network state
- Light load: tối đa 1-5 HTTP HEAD request tuần tự tới private URL, có delay 250 ms giữa request

Không có exploit, brute force, credential dump, reverse shell, persistence, pivot, sniffing promiscuous hay flood/DDoS.

## QA

- Regression suite: 166/166 PASS.
- Desktop Release Gate: 61/61 PASS.
- Python compile: PASS.
- JavaScript syntax: PASS.
- Asset revision: 70397.
