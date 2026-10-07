import sqlite3
from pathlib import Path

from webapi import cybersecurity59 as net


def _identity():
    return {
        'local_ip': '192.168.2.34', 'gateway': '192.168.2.1', 'adapter': 'Ethernet',
        'mode': 'LAN+WAN', 'source': 'WINDOWS_LOCAL', 'hostname': 'QA-PC',
        'endpoint_id': '', 'checked_at': '2026-10-07T13:22:16+07:00',
    }


def test_reference_icmp_no_longer_drives_quality(monkeypatch):
    conn = sqlite3.connect(':memory:'); conn.row_factory = sqlite3.Row
    monkeypatch.setattr(net, 'connection', lambda: conn)
    monkeypatch.setattr(net, '_primary_network', _identity)

    def fake_icmp(target, samples=4, timeout_ms=1000):
        if target == '192.168.2.1':
            return {'target': target, 'samples': samples, 'replies': samples,
                    'packet_loss': 0.0, 'latency_ms': 1.0, 'jitter_ms': 0.1, 'errors': []}
        return {'target': target, 'samples': samples, 'replies': samples,
                'packet_loss': 0.0, 'latency_ms': 188.75, 'jitter_ms': 2.0, 'errors': []}

    monkeypatch.setattr(net, '_icmp_series', fake_icmp)
    monkeypatch.setattr(net, '_tcp_latency_series', lambda *a, **k: {
        'target': net.DEFAULT_SPEED_HOST, 'samples': 6, 'replies': 6,
        'packet_loss': 0.0, 'latency_ms': 6.1, 'jitter_ms': 0.4,
        'errors': [], 'method': 'TCP_HANDSHAKE_MEDIAN',
    })
    monkeypatch.setattr(net, '_dns_probe', lambda *a, **k: {
        'ok': True, 'host': net.DEFAULT_SPEED_HOST, 'addresses': ['104.16.0.1'], 'elapsed_ms': 4.0,
    })
    monkeypatch.setattr(net, '_tcp_probe', lambda *a, **k: {
        'ok': True, 'host': net.DEFAULT_SPEED_HOST, 'port': 443, 'elapsed_ms': 6.0,
    })
    monkeypatch.setattr(net, '_https_probe', lambda *a, **k: {
        'ok': True, 'host': net.DEFAULT_SPEED_HOST, 'status': 200, 'elapsed_ms': 12.0,
    })

    result = net._network_diagnostics('qa-admin')
    assert result['overall'] == 'GOOD'
    assert result['metrics']['latency_ms'] == 6.1
    assert result['metrics']['reference_icmp_latency_ms'] == 188.75
    assert not any('188.75' in x for x in result['issues'])
    ref = {x['key']: x for x in result['checks']}['reference_icmp']
    assert ref['status'] == 'INFO'
    assert 'không dùng để chấm điểm' in ref['detail']
    conn.close()


def test_line_test_uses_speed_host_tcp_not_fixed_public_icmp(monkeypatch):
    conn = sqlite3.connect(':memory:'); conn.row_factory = sqlite3.Row
    monkeypatch.setattr(net, 'connection', lambda: conn)
    monkeypatch.setattr(net, '_primary_network', _identity)
    monkeypatch.setattr(net, '_tcp_latency_series', lambda *a, **k: {
        'target': net.DEFAULT_SPEED_HOST, 'samples': 6, 'replies': 6,
        'packet_loss': 0.0, 'latency_ms': 5.6, 'jitter_ms': 0.2,
        'errors': [], 'method': 'TCP_HANDSHAKE_MEDIAN',
    })
    monkeypatch.setattr(net, '_icmp_series', lambda target, samples=4, timeout_ms=1000: {
        'target': target, 'samples': samples, 'replies': samples, 'packet_loss': 0.0,
        'latency_ms': 187.75 if target == net.PUBLIC_PROBE else 1.0,
        'jitter_ms': 1.5 if target == net.PUBLIC_PROBE else 0.1, 'errors': [],
    })
    monkeypatch.setattr(net, '_https_probe', lambda: {'ok': True, 'status': 200, 'elapsed_ms': 10})
    result = net.run_line_test_internal('qa')
    assert result['latency_ms'] == 5.6
    assert result['grade'] == 'EXCELLENT'
    assert result['public_probe']['latency_ms'] == 187.75
    assert result['target'] == net.DEFAULT_SPEED_HOST
    conn.close()


def test_adaptive_transfer_scales_for_fast_links_but_is_bounded():
    fast = net._adaptive_bytes(500.0, 32, 2.5, 16, 128)
    slow = net._adaptive_bytes(20.0, 1, 2.5, 16, 128)
    assert 100 * 1024 * 1024 <= fast <= 128 * 1024 * 1024
    assert slow == 16 * 1024 * 1024


def test_download_test_uses_warmup_and_multiple_streams(monkeypatch):
    calls = []
    monkeypatch.setattr(net, '_download_once', lambda size, timeout=35: calls.append(size) or size)
    monkeypatch.setattr(net, '_adaptive_bytes', lambda *a, **k: 40 * 1024 * 1024)
    monkeypatch.setattr(net, '_parallel_transfer', lambda worker, total, streams, timeout: (total, 1.0))
    ticks = iter([0.0, 0.2])
    monkeypatch.setattr(net.time, 'perf_counter', lambda: next(ticks))
    r = net._download_test(32, detailed=True)
    assert calls == [2 * 1024 * 1024]
    assert r['streams'] == 4
    assert r['megabytes'] > 40.0  # decimal MB display for 40 MiB
    assert r['mbps'] > 300


def test_network_page_uses_latest_measurement_and_adaptive_multistream_copy():
    root = Path(__file__).resolve().parents[1]
    js = (root / 'webapi/static/cybersecurity51.js').read_text(encoding='utf-8')
    assert 'q=s.display_quality||l||{}' in js
    assert 'download_mb:32,upload_mb:12' in js
    assert "button('Kiểm tra trong nước','line-test59'" in js
    assert "button('Kiểm tra quốc tế','intl-line-test59'" in js
    assert 'Download CDN' in js and 'Độ trễ quốc tế / CDN' in js


def test_local_http_speed_runner_transfers_real_bytes(monkeypatch):
    import threading
    import urllib.parse
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            remaining = int(q.get('bytes', ['1'])[0])
            self.send_response(200)
            self.send_header('Content-Length', str(remaining))
            self.end_headers()
            chunk = b'x' * (64 * 1024)
            while remaining:
                part = chunk[:min(len(chunk), remaining)]
                self.wfile.write(part)
                remaining -= len(part)
        def do_POST(self):
            remaining = int(self.headers.get('Content-Length', '0'))
            while remaining:
                part = self.rfile.read(min(64 * 1024, remaining))
                if not part:
                    break
                remaining -= len(part)
            self.send_response(200)
            self.send_header('Content-Length', '2')
            self.end_headers()
            self.wfile.write(b'OK')
        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        monkeypatch.setattr(net, 'DEFAULT_DOWNLOAD_URL', f'http://127.0.0.1:{port}/__down')
        monkeypatch.setattr(net, 'DEFAULT_UPLOAD_URL', f'http://127.0.0.1:{port}/__up')
        monkeypatch.setattr(net, '_adaptive_bytes', lambda *a, **k: 2 * 1024 * 1024)
        down = net._download_test(1, detailed=True)
        up = net._upload_test(1, detailed=True)
        assert down['bytes'] == 2 * 1024 * 1024
        assert up['bytes'] == 2 * 1024 * 1024
        assert down['mbps'] > 0 and up['mbps'] > 0
    finally:
        server.shutdown()
        server.server_close()


def test_summary_hides_legacy_measurements_until_retest(monkeypatch):
    conn = sqlite3.connect(':memory:'); conn.row_factory = sqlite3.Row
    monkeypatch.setattr(net, 'connection', lambda: conn)
    monkeypatch.setattr(net, '_primary_network', _identity)
    net.ensure_tables59()
    conn.execute("INSERT INTO network_quality59(test_type,target,gateway,local_ip,network_mode,latency_ms,jitter_ms,packet_loss,download_mbps,upload_mbps,grade,detail,created_by,created_at) VALUES('LINE','1.1.1.1','192.168.2.1','192.168.2.34','LAN+WAN',188.75,1.64,0,NULL,NULL,'POOR','gateway=192.168.2.1; https=OK','qa','2026-10-07T06:00:00Z')")
    conn.execute("INSERT INTO network_quality59(test_type,target,gateway,local_ip,network_mode,latency_ms,jitter_ms,packet_loss,download_mbps,upload_mbps,grade,detail,created_by,created_at) VALUES('SPEED','https://speed.cloudflare.com/__down','192.168.2.1','192.168.2.34','LAN+WAN',187.75,2.49,0,20.68,8.69,'POOR','Manual WAN bandwidth test; third-party endpoint contacted explicitly by user.','qa','2026-10-07T06:01:00Z')")
    conn.commit()
    monkeypatch.setattr(net, 'require_role', lambda request, *roles: {'username': 'qa'})
    result = net.summary(None)
    assert result['needs_retest'] is True
    assert result['latest_line'] is None
    assert result['latest_speed'] is None
    assert result['display_quality'] is None
    conn.close()


def test_summary_uses_new_measurement_after_retest(monkeypatch):
    conn = sqlite3.connect(':memory:'); conn.row_factory = sqlite3.Row
    monkeypatch.setattr(net, 'connection', lambda: conn)
    monkeypatch.setattr(net, '_primary_network', _identity)
    net.ensure_tables59()
    conn.execute("INSERT INTO network_quality59(test_type,target,gateway,local_ip,network_mode,latency_ms,jitter_ms,packet_loss,download_mbps,upload_mbps,grade,detail,created_by,created_at,quality_scope,quality_target,international_latency_ms) VALUES('LINE','vnexpress.net','192.168.2.1','192.168.2.34','LAN+WAN',6.1,0.4,0,NULL,NULL,'EXCELLENT','quality_scope=domestic; quality_target=vnexpress.net','qa','2026-10-07T06:10:00Z','domestic','vnexpress.net',188.0)")
    conn.execute("INSERT INTO network_quality59(test_type,target,gateway,local_ip,network_mode,latency_ms,jitter_ms,packet_loss,download_mbps,upload_mbps,grade,detail,created_by,created_at,quality_scope,quality_target,international_latency_ms) VALUES('SPEED','https://speed.cloudflare.com/__down','192.168.2.1','192.168.2.34','LAN+WAN',5.8,0.3,0,470.2,484.1,'EXCELLENT','Adaptive multi-stream WAN bandwidth test; quality_scope=domestic; throughput_scope=international_cdn','qa','2026-10-07T06:11:00Z','domestic','vnexpress.net',189.0)")
    conn.commit()
    monkeypatch.setattr(net, 'require_role', lambda request, *roles: {'username': 'qa'})
    result = net.summary(None)
    assert result['needs_retest'] is False
    assert result['latest_speed']['download_mbps'] == 470.2
    assert result['display_quality']['test_type'] == 'SPEED'
    assert result['display_quality']['latency_ms'] == 5.8
    conn.close()
