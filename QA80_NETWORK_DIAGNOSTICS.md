# QA80 - Detailed Network Diagnostics

## Change
The **Tốc độ & Đường truyền** page now includes a dedicated **Kiểm tra mạng chi tiết** workflow.

It checks and reports separately:
- Active adapter and local IPv4
- Default gateway and gateway reachability
- DNS resolution
- TCP 443 Internet connectivity
- HTTPS connectivity
- Internet latency
- Jitter
- Packet loss

The UI shows the latest persisted diagnostic, identifies the concrete reasons for a FAIR/POOR result, and provides targeted suggestions. For example, high latency can be flagged while packet loss remains healthy.

The check is lightweight: ICMP, DNS, one TCP connect, and an HTTPS HEAD request. It does not run a bandwidth speed test and does not change Windows configuration.

Asset revision: **70398**.
