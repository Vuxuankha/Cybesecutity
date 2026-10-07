# QA83 - Speed Test Visibility Fix

Asset revision: **70401**

## Lỗi xác nhận
Global frontend API helper tự abort request sau 20 giây. QA82 Speed Test dùng warm-up, latency pre/post, adaptive multi-stream download và upload nên trên Windows thực tế có thể vượt 20 giây. Khi browser abort trước lúc backend trả kết quả, trang vẫn có latency từ line test nhưng Download/Upload không có sample mới và hiển thị `-`.

## Bản vá
- `api()` hỗ trợ `timeoutMs` theo từng request, giới hạn tối đa 180 giây.
- Line test: 45 giây.
- Detailed network diagnostics: 60 giây.
- Speed Test: 180 giây.
- Card Download/Upload hiển thị `Chưa đo` khi chưa có kết quả mới.
- Speed Test hiển thị tiến trình và nhắc có thể cần 30-120 giây.

## Regression
- Test custom timeout API helper.
- Test Speed Test sử dụng timeout 180 giây.
- Test trạng thái `Chưa đo` rõ ràng.
