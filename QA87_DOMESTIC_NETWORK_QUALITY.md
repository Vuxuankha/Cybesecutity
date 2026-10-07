# QA87 – Domestic Network Quality

## Vấn đề

Các bản QA82–QA86 đo latency tới cùng CDN dùng cho speed test. Với một số ISP Việt Nam, tuyến tới CDN này có thể khoảng 180–200 ms trong khi đường truyền trong nước chỉ 4–10 ms, làm màn hình báo `POOR` sai cho trải nghiệm nội địa.

## Thay đổi

- Tách hẳn **tuyến trong nước** và **tuyến quốc tế/CDN**.
- Chất lượng chính (`GOOD/FAIR/POOR`) dùng điểm đo trong nước nhanh nhất.
- Mặc định thử: `vnexpress.net`, `vietnamnet.vn`, `dantri.com.vn`, `fpt.vn`, `viettel.com.vn`, `vnpt.com.vn` bằng TCP 443; không tải nội dung trang.
- Chọn điểm có median latency thấp nhất rồi đo lại nhiều mẫu để lấy latency/jitter/loss ổn định.
- Có thể cấu hình danh sách khác bằng `NA_DOMESTIC_PROBE_HOSTS=host1,host2,...`.
- Tuyến quốc tế/CDN được đo riêng và chỉ mang tính tham khảo cho chất lượng trong nước.
- Speed Test băng thông vẫn chạy tới CDN đa luồng; kết quả modal hiển thị cả **Độ trễ trong nước** và **Độ trễ quốc tế/CDN**.
- Database được nâng cấp tại chỗ với các cột `quality_scope`, `quality_target`, `international_latency_ms`, `international_jitter_ms`, `international_packet_loss`.

## Hành vi kỳ vọng

Ví dụ: trong nước `5 ms`, quốc tế/CDN `189 ms`, packet loss nội địa `0%` → chất lượng chính có thể là `EXCELLENT/GOOD`; app không được báo `POOR` chỉ vì tuyến quốc tế cao.

## Kiểm thử

- Regression tổng thể: **208/208 PASS**.
- Có test riêng cho lựa chọn điểm trong nước nhanh nhất, tách route quốc tế, lưu DB riêng, diagnostics và giao diện/i18n ba ngôn ngữ.
- Release Gate: **65/65 PASS**.
- Manifest sạch: **195/195 file verified**.
- Python/JavaScript syntax: **PASS**.
- Asset revision: `70405`.
