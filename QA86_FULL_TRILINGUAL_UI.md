# QA86 - Full Trilingual UI

NetworkAutomation Desktop 7.0.3 - asset revision **70404**.

## Mục tiêu

QA86 hoàn thiện cơ chế đa ngôn ngữ cho toàn bộ giao diện người dùng với ba lựa chọn:

- Tiếng Việt
- 中文（简体）
- English

## Phạm vi đã hoàn thiện

- Màn hình đăng nhập, menu, header, tìm kiếm và đồng hồ.
- Tất cả trang được render động sau đăng nhập.
- Tiêu đề, mô tả, card, trạng thái, badge, nút, bảng, placeholder, tooltip và aria-label.
- Dialog, toast, confirm, prompt và alert của trình duyệt.
- Nội dung động từ checklist, SOC, cảnh báo, thiết bị, mạng, Windows Local Tools và báo cáo.
- Thông báo lỗi/trạng thái từ WebAPI: toàn bộ chuỗi tiếng Việt tĩnh mà WebAPI có thể trả về giao diện đều được đưa vào catalog English/Chinese.
- Chuỗi tiếng Anh legacy trong các module cũ được ánh xạ về tiếng Việt hoặc tiếng Trung để tránh giao diện trộn ngôn ngữ.
- Lựa chọn ngôn ngữ được lưu cục bộ và áp dụng ngay không cần đăng nhập lại.

## Dữ liệu không dịch có chủ đích

Các giá trị kỹ thuật không được biến đổi: IP, MAC, hostname, URL, OID, CVE, JSON, code, tên file, raw log, output CMD/PowerShell, fingerprint/hash và các acronym chuẩn như API, SOC, SSH, SNMP, TLS khi cần giữ nguyên nghĩa kỹ thuật. Nhãn và mô tả xung quanh các giá trị này vẫn được dịch.

## Kiểm thử

- Static catalog audit: tất cả chuỗi tiếng Việt tĩnh từ `webapi/*.py` đều có catalog dịch.
- Browser smoke: Việt -> English -> 中文 -> Việt và nội dung DOM được thêm động sau khi đổi ngôn ngữ.
- Regression suite đầy đủ.
- Desktop release gate.
