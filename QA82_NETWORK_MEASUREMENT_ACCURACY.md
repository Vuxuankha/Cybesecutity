# QA82 - Network Measurement Accuracy

## Nguyên nhân lỗi
Bản trước dùng ICMP cố định tới `1.1.1.1` để chấm chất lượng đường truyền và dùng phép tải 5 MB / tải lên 2 MB một luồng. Route tới `1.1.1.1` có thể khác hoàn toàn máy chủ Speedtest gần người dùng; với đường truyền hàng trăm Mbps, mẫu 5 MB quá ngắn nên TLS/connection overhead có thể làm kết quả thấp giả.

## Thay đổi
- Chất lượng Internet dùng median TCP handshake tới `speed.cloudflare.com:443` (hoặc host được cấu hình cho speed test). DNS được resolve trước thời gian đo.
- ICMP `1.1.1.1` vẫn hiển thị để tham khảo nhưng không kéo điểm tổng xuống `POOR`.
- Gateway vẫn được ping riêng để phân biệt lỗi LAN và lỗi WAN.
- Download: warm-up 2 MiB, sau đó tự chọn 16-128 MiB và 2-4 luồng song song.
- Upload: warm-up 512 KiB, sau đó tự chọn 8-64 MiB và 2-4 luồng song song.
- Speed Test lưu stream count, duration, actual traffic và latency method.
- UI dùng measurement mới nhất giữa LINE/SPEED cho Grade, Latency, Jitter và Sample loss.

## Lưu ý
Kết quả không thể bắt buộc trùng 100% Ookla/Fast.com vì nhà cung cấp server, protocol và thuật toán khác nhau. Mục tiêu của QA82 là loại sai số hệ thống rõ ràng như trường hợp 470/484 Mbps bên ngoài nhưng app báo 20/8 Mbps và 188 ms chỉ do route ICMP khác.

## QA
- Regression kiểm tra trường hợp `1.1.1.1 = 188.75 ms` nhưng speed host = `6.1 ms`: app phải `GOOD`, không `POOR`.
- Regression kiểm tra line test chọn speed host thay vì fixed public ICMP.
- Regression kiểm tra adaptive sample sizing và multi-stream.
- Local HTTP smoke test xác nhận download/upload parallel runner truyền đúng byte count.
- Asset revision: `70400`.
