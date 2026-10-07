import sqlite3
from pathlib import Path

from webapi import cybersecurity59 as net


def test_diagnostics_explains_poor_latency_and_persists(monkeypatch):
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    monkeypatch.setattr(net, 'connection', lambda: conn)
    monkeypatch.setattr(net, '_primary_network', lambda: {
        'local_ip': '192.168.2.34', 'gateway': '192.168.2.1', 'adapter': 'Ethernet',
        'mode': 'LAN+WAN', 'source': 'WINDOWS_LOCAL', 'hostname': 'QA-PC',
        'endpoint_id': '', 'checked_at': '2026-10-07T13:22:16+07:00',
    })

    def fake_icmp(target, samples=4, timeout_ms=1000):
        if target == '192.168.2.1':
            return {'target': target, 'samples': samples, 'replies': samples,
                    'packet_loss': 0.0, 'latency_ms': 1.4, 'jitter_ms': 0.3, 'errors': []}
        return {'target': target, 'samples': samples, 'replies': samples,
                'packet_loss': 0.0, 'latency_ms': 188.75, 'jitter_ms': 1.64, 'errors': []}

    monkeypatch.setattr(net, '_icmp_series', fake_icmp)
    monkeypatch.setattr(net, '_tcp_latency_series', lambda *a, **k: {
        'target': 'speed.cloudflare.com', 'samples': 6, 'replies': 6, 'packet_loss': 0.0,
        'latency_ms': 188.75, 'jitter_ms': 1.64, 'errors': [], 'method': 'TCP_HANDSHAKE_MEDIAN',
    })
    monkeypatch.setattr(net, '_domestic_latency_probe', lambda *a, **k: {
        'target': 'vnexpress.net', 'samples': 6, 'replies': 6, 'packet_loss': 0.0,
        'latency_ms': 188.75, 'jitter_ms': 1.64, 'errors': [], 'method': 'TCP_HANDSHAKE_MEDIAN', 'scope':'domestic',
    })
    monkeypatch.setattr(net, '_dns_probe', lambda *a, **k: {
        'ok': True, 'host': 'www.cloudflare.com', 'addresses': ['104.16.123.96'], 'elapsed_ms': 12.0,
    })
    monkeypatch.setattr(net, '_tcp_probe', lambda *a, **k: {
        'ok': True, 'host': '1.1.1.1', 'port': 443, 'elapsed_ms': 21.0,
    })
    monkeypatch.setattr(net, '_https_probe', lambda *a, **k: {'ok': True, 'status': 200, 'elapsed_ms': 30.0})

    r = net._network_diagnostics('qa-admin')
    assert r['overall'] == 'POOR'
    assert r['metrics']['latency_ms'] == 188.75
    assert any('Độ trễ trong nước rất cao' in x for x in r['issues'])
    checks = {x['key']: x for x in r['checks']}
    assert checks['gateway_ping']['status'] == 'OK'
    assert checks['dns']['status'] == 'OK'
    assert checks['https']['status'] == 'OK'
    assert checks['domestic_latency']['status'] == 'WARN'

    monkeypatch.setattr(net, 'require_role', lambda request, *roles: {'username': 'qa-admin'})
    summary = net.summary(None)
    assert summary['latest_diagnostics']['overall'] == 'POOR'
    assert summary['latest_diagnostics']['id'] == r['id']
    conn.close()


def test_diagnostics_route_is_permission_guarded():
    root = Path(__file__).resolve().parents[1]
    sec = (root / 'webapi/security37.py').read_text(encoding='utf-8')
    assert "('/api/v59/network/diagnostics'" not in sec  # regex tuple includes r prefix
    assert "r'/api/v59/network/diagnostics'" in sec
    assert "('Admin','Analyst','Operator')" in sec


def test_network_page_has_detailed_diagnostics_ui():
    root = Path(__file__).resolve().parents[1]
    js = (root / 'webapi/static/cybersecurity51.js').read_text(encoding='utf-8')
    assert "button('Kiểm tra mạng chi tiết','network-diagnostics59'" in js
    assert "api('/v59/network/diagnostics',{method:'POST'" in js
    assert "server đo tốc độ" in js and "latency/jitter/loss" in js
    assert "Nguyên nhân cần chú ý" in js
    assert "latest_diagnostics" in js
