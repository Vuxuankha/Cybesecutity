"""Desktop network speed and line-quality diagnostics.

All measurements execute on the local Windows machine. LAN reachability uses ICMP
to the active gateway, while Internet latency is measured with repeated TCP handshakes
to the same CDN host used by the bandwidth test. Bandwidth tests remain explicit
because they consume traffic and contact a third-party speed-test endpoint.
"""
from __future__ import annotations

import json
import os
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from webapi.model37 import StrictBaseModel

from modules.icmp_probe import icmp_ping
from webapi.platform50 import network_identity_status
from webapi.runtime37 import connection, utcnow
from webapi.security37 import require_role

router = APIRouter(prefix='/api/v59', tags=['Cybersecurity 5.9'])

DEFAULT_DOWNLOAD_URL = os.environ.get('NA_SPEEDTEST_DOWNLOAD_URL', 'https://speed.cloudflare.com/__down')
DEFAULT_UPLOAD_URL = os.environ.get('NA_SPEEDTEST_UPLOAD_URL', 'https://speed.cloudflare.com/__up')
DEFAULT_SPEED_HOST = urllib.parse.urlparse(DEFAULT_DOWNLOAD_URL).hostname or 'speed.cloudflare.com'
PUBLIC_PROBE = os.environ.get('NA_LINE_PUBLIC_PROBE', '1.1.1.1')
# QA87: domestic quality is the primary score for Vietnamese desktop users.
# These targets are TCP-only probes (no content download) and may be overridden
# for an enterprise/ISP deployment with NA_DOMESTIC_PROBE_HOSTS.
DEFAULT_DOMESTIC_PROBE_HOSTS = (
    'vnexpress.net', 'vietnamnet.vn', 'dantri.com.vn',
    'fpt.vn', 'viettel.com.vn', 'vnpt.com.vn',
)


def _domestic_probe_hosts() -> tuple[str, ...]:
    raw = str(os.environ.get('NA_DOMESTIC_PROBE_HOSTS') or '').strip()
    source = [x.strip() for x in raw.split(',')] if raw else list(DEFAULT_DOMESTIC_PROBE_HOSTS)
    out: list[str] = []
    for host in source:
        host = str(host or '').strip().lower().rstrip('.')
        if not host or any(ch.isspace() for ch in host) or host in out:
            continue
        out.append(host)
        if len(out) >= 8:
            break
    return tuple(out) or DEFAULT_DOMESTIC_PROBE_HOSTS


class LineTestIn(StrictBaseModel):
    scope: str = Field(default='domestic', pattern='^(domestic|international)$')


class SpeedTestIn(StrictBaseModel):
    # These are minimum traffic targets. The runner may adapt upward for fast links
    # so the timed interval is long enough to avoid TLS/setup overhead dominating.
    download_mb: int = Field(default=32, ge=1, le=128)
    upload_mb: int = Field(default=12, ge=1, le=64)
    run_upload: bool = True
    confirm_bandwidth_use: bool = False


class OptimizeLineIn(StrictBaseModel):
    confirm_system_change: bool = False


def ensure_tables59() -> None:
    with connection() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS network_quality59(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          test_type TEXT NOT NULL,
          target TEXT,
          gateway TEXT,
          local_ip TEXT,
          network_mode TEXT,
          latency_ms REAL,
          jitter_ms REAL,
          packet_loss REAL,
          download_mbps REAL,
          upload_mbps REAL,
          grade TEXT NOT NULL,
          detail TEXT,
          created_by TEXT,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_network_quality59_time ON network_quality59(created_at DESC);
        CREATE TABLE IF NOT EXISTS network_diagnostics59(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          overall TEXT NOT NULL,
          result_json TEXT NOT NULL,
          created_by TEXT,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_network_diagnostics59_time ON network_diagnostics59(created_at DESC);
        ''')
        # QA87 keeps domestic and international latency separate. ALTER is
        # intentionally idempotent so existing portable databases upgrade in place.
        existing = {str(r['name']) for r in c.execute('PRAGMA table_info(network_quality59)').fetchall()}
        additions = {
            'quality_scope': 'TEXT',
            'quality_target': 'TEXT',
            'international_latency_ms': 'REAL',
            'international_jitter_ms': 'REAL',
            'international_packet_loss': 'REAL',
        }
        for name, sql_type in additions.items():
            if name not in existing:
                c.execute(f'ALTER TABLE network_quality59 ADD COLUMN {name} {sql_type}')
        c.commit()


def _primary_network() -> dict[str, Any]:
    ident = network_identity_status(force=True)
    return {'local_ip': str(ident.get('ipv4') or ''), 'gateway': str(ident.get('gateway') or ''),
            'adapter': str(ident.get('adapter') or ''), 'mode': ident.get('mode') or 'OFFLINE',
            'source': str(ident.get('source') or 'WINDOWS_LOCAL'), 'hostname': str(ident.get('hostname') or ''),
            'endpoint_id': '', 'checked_at': ident.get('checked_at')}


def _icmp_series(target: str, samples: int = 4, timeout_ms: int = 1000) -> dict[str, Any]:
    values: list[float] = []
    replies = 0
    errors: list[str] = []
    for _ in range(samples):
        r = icmp_ping(target, timeout_ms=timeout_ms, count=1)
        if r.get('status') == 'Online':
            replies += 1
            if r.get('response') is not None:
                values.append(float(r['response']))
        elif r.get('error'):
            errors.append(str(r['error']))
        time.sleep(0.05)
    loss = round((samples - replies) * 100.0 / samples, 1)
    latency = round(sum(values) / len(values), 2) if values else None
    jitter = round(statistics.pstdev(values), 2) if len(values) > 1 else (0.0 if values else None)
    return {'target': target, 'samples': samples, 'replies': replies, 'packet_loss': loss, 'latency_ms': latency, 'jitter_ms': jitter, 'errors': errors[:4]}


def _grade(latency: float | None, jitter: float | None, loss: float | None) -> str:
    if latency is None or loss is None or loss >= 25:
        return 'POOR'
    j = 999.0 if jitter is None else jitter
    if loss == 0 and latency < 30 and j < 10:
        return 'EXCELLENT'
    if loss <= 1 and latency < 60 and j < 20:
        return 'GOOD'
    if loss <= 3 and latency < 120 and j < 40:
        return 'FAIR'
    return 'POOR'



def _run_windows_command(args: list[str], timeout: int = 15) -> dict[str, Any]:
    """Run one bounded Windows networking command and return auditable output.

    Commands are fixed by the application, never user supplied.  A failed command is
    reported instead of aborting the whole optimization so the after-test still runs.
    """
    try:
        cp = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        out = (cp.stdout or cp.stderr or '').strip().replace('\r', '')
        return {'command': ' '.join(args[:3]), 'ok': cp.returncode == 0,
                'returncode': int(cp.returncode), 'detail': out[-800:] or ('OK' if cp.returncode == 0 else 'FAILED')}
    except Exception as exc:
        return {'command': ' '.join(args[:3]), 'ok': False, 'returncode': None,
                'detail': f'{type(exc).__name__}: {str(exc)[:300]}'}


def _safe_windows_line_optimization() -> list[dict[str, Any]]:
    """Apply only conservative Windows network repairs that do not invent bandwidth.

    - DNS cache flush can clear stale resolution state.
    - TCP receive auto-tuning NORMAL restores Windows dynamic receive-window behavior
      if it had previously been disabled/restricted.
    These changes cannot exceed the ISP/router/link capacity and that limitation is
    intentionally surfaced to the UI.
    """
    if sys.platform != 'win32':
        return [{'command': 'windows-network-optimization', 'ok': False, 'returncode': None,
                 'detail': 'UNSUPPORTED_PLATFORM'}]
    return [
        _run_windows_command(['ipconfig', '/flushdns']),
        _run_windows_command(['netsh', 'interface', 'tcp', 'set', 'global', 'autotuninglevel=normal']),
    ]


def _improvement(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    def n(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    bl, al = n(before.get('latency_ms')), n(after.get('latency_ms'))
    bj, aj = n(before.get('jitter_ms')), n(after.get('jitter_ms'))
    bp, ap = n(before.get('packet_loss')), n(after.get('packet_loss'))
    latency_delta = round(bl - al, 2) if bl is not None and al is not None else None
    jitter_delta = round(bj - aj, 2) if bj is not None and aj is not None else None
    loss_delta = round(bp - ap, 2) if bp is not None and ap is not None else None
    improved = any(x is not None and x > 0 for x in (latency_delta, jitter_delta, loss_delta))
    return {'improved': improved, 'latency_reduction_ms': latency_delta,
            'jitter_reduction_ms': jitter_delta, 'packet_loss_reduction_pct': loss_delta}

def _tcp_latency_series(host: str = DEFAULT_SPEED_HOST, port: int = 443, samples: int = 6, timeout: float = 2.5) -> dict[str, Any]:
    """Measure TCP handshake RTT to the same host used by the speed test.

    DNS is resolved before timing so resolver latency does not contaminate the RTT.
    The first successful connection is a warm-up and the reported latency is the
    median of subsequent samples, which is much less sensitive to a single outlier
    than an arithmetic mean.
    """
    host = str(host or '').strip()
    samples = max(3, min(int(samples), 10))
    if not host:
        return {'target': host, 'samples': samples, 'replies': 0, 'packet_loss': 100.0,
                'latency_ms': None, 'jitter_ms': None, 'errors': ['EMPTY_HOST'], 'method': 'TCP'}
    try:
        infos = socket.getaddrinfo(host, int(port), type=socket.SOCK_STREAM)
    except Exception as exc:
        return {'target': host, 'samples': samples, 'replies': 0, 'packet_loss': 100.0,
                'latency_ms': None, 'jitter_ms': None, 'errors': [type(exc).__name__], 'method': 'TCP'}

    candidates = []
    seen = set()
    for family, socktype, proto, _canon, sockaddr in infos:
        key = (family, sockaddr)
        if key in seen:
            continue
        seen.add(key); candidates.append((family, socktype, proto, sockaddr))

    chosen = None
    warm_error = ''
    for family, socktype, proto, sockaddr in candidates:
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(timeout)
        try:
            sock.connect(sockaddr)
            chosen = (family, socktype, proto, sockaddr)
            break
        except Exception as exc:
            warm_error = type(exc).__name__
        finally:
            try:
                sock.close()
            except OSError:
                pass
    if chosen is None:
        return {'target': host, 'samples': samples, 'replies': 0, 'packet_loss': 100.0,
                'latency_ms': None, 'jitter_ms': None, 'errors': [warm_error or 'CONNECT_FAILED'], 'method': 'TCP'}

    values: list[float] = []
    errors: list[str] = []
    family, socktype, proto, sockaddr = chosen
    for _ in range(samples):
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(timeout)
        started = time.perf_counter()
        try:
            sock.connect(sockaddr)
            values.append((time.perf_counter() - started) * 1000.0)
        except Exception as exc:
            errors.append(type(exc).__name__)
        finally:
            try:
                sock.close()
            except OSError:
                pass
        time.sleep(0.04)
    replies = len(values)
    loss = round((samples - replies) * 100.0 / samples, 1)
    latency = round(statistics.median(values), 2) if values else None
    diffs = [abs(values[i] - values[i-1]) for i in range(1, len(values))]
    jitter = round(statistics.median(diffs), 2) if diffs else (0.0 if values else None)
    resolved = str(sockaddr[0]) if sockaddr else ''
    return {'target': host, 'resolved_ip': resolved, 'port': int(port), 'samples': samples,
            'replies': replies, 'packet_loss': loss, 'latency_ms': latency, 'jitter_ms': jitter,
            'errors': errors[:4], 'method': 'TCP_HANDSHAKE_MEDIAN'}


def _domestic_latency_probe(samples: int = 6, timeout: float = 1.8) -> dict[str, Any]:
    """Choose the lowest-latency reachable Vietnamese endpoint, then re-sample it.

    The first pass runs in parallel so one blocked website does not make the test slow.
    Only TCP 443 handshakes are performed; no page content is downloaded. Selecting
    the best responsive domestic target approximates a nearby in-country speed-test
    server and prevents an overseas CDN route from dominating the quality score.
    """
    hosts = _domestic_probe_hosts()
    if not hosts:
        return {'target': '', 'scope': 'domestic', 'samples': samples, 'replies': 0,
                'packet_loss': 100.0, 'latency_ms': None, 'jitter_ms': None,
                'errors': ['NO_DOMESTIC_TARGET'], 'method': 'TCP_HANDSHAKE_MEDIAN', 'candidates': []}

    def quick(host: str) -> dict[str, Any]:
        r = _tcp_latency_series(host, 443, 3, timeout)
        r['scope'] = 'domestic'
        return r

    workers = max(1, min(4, len(hosts)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        quick_results = list(pool.map(quick, hosts))
    responsive = [r for r in quick_results if int(r.get('replies') or 0) > 0 and r.get('latency_ms') is not None]
    candidate_summary = [
        {'target': r.get('target'), 'resolved_ip': r.get('resolved_ip'),
         'latency_ms': r.get('latency_ms'), 'jitter_ms': r.get('jitter_ms'),
         'packet_loss': r.get('packet_loss'), 'replies': r.get('replies')}
        for r in quick_results
    ]
    if not responsive:
        return {'target': '', 'scope': 'domestic', 'samples': samples, 'replies': 0,
                'packet_loss': 100.0, 'latency_ms': None, 'jitter_ms': None,
                'errors': ['DOMESTIC_TARGETS_UNREACHABLE'], 'method': 'TCP_HANDSHAKE_MEDIAN',
                'candidates': candidate_summary}
    best = min(responsive, key=lambda r: float(r.get('latency_ms') or 999999.0))
    refined = _tcp_latency_series(str(best.get('target') or ''), 443, samples, timeout)
    refined['scope'] = 'domestic'
    refined['candidates'] = candidate_summary
    return refined


def _https_probe(timeout: float = 3.0) -> dict[str, Any]:
    started = time.monotonic()
    try:
        url = DEFAULT_DOWNLOAD_URL + ('&' if '?' in DEFAULT_DOWNLOAD_URL else '?') + urllib.parse.urlencode({'bytes': 1, 'na_probe': int(time.time()*1000)})
        req = urllib.request.Request(url, headers={'User-Agent': 'NetworkAutomation/7.0.3', 'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(1)
            return {'ok': True, 'status': int(getattr(r, 'status', 200)), 'host': DEFAULT_SPEED_HOST,
                    'elapsed_ms': round((time.monotonic()-started)*1000, 1)}
    except Exception as exc:
        return {'ok': False, 'host': DEFAULT_SPEED_HOST, 'error': type(exc).__name__,
                'elapsed_ms': round((time.monotonic()-started)*1000, 1)}


def _dns_probe(host: str = DEFAULT_SPEED_HOST, timeout: float = 3.0) -> dict[str, Any]:
    # getaddrinfo uses the OS resolver timeout. Do not change socket.setdefaulttimeout
    # because that is process-global and could affect concurrent API requests.
    started = time.monotonic()
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = []
        for item in infos:
            addr = str(item[4][0])
            if addr not in addresses:
                addresses.append(addr)
        return {
            'ok': bool(addresses), 'host': host, 'addresses': addresses[:4],
            'elapsed_ms': round((time.monotonic() - started) * 1000, 1),
        }
    except Exception as exc:
        return {
            'ok': False, 'host': host, 'addresses': [], 'error': type(exc).__name__,
            'elapsed_ms': round((time.monotonic() - started) * 1000, 1),
        }


def _tcp_probe(host: str = DEFAULT_SPEED_HOST, port: int = 443, timeout: float = 3.0) -> dict[str, Any]:
    started = time.monotonic()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            pass
        return {'ok': True, 'host': host, 'port': int(port), 'elapsed_ms': round((time.monotonic()-started)*1000, 1)}
    except Exception as exc:
        return {'ok': False, 'host': host, 'port': int(port), 'error': type(exc).__name__, 'elapsed_ms': round((time.monotonic()-started)*1000, 1)}


def _diag_status(ok: bool, warn: bool = False) -> str:
    return 'WARN' if warn else ('OK' if ok else 'FAIL')


def _network_diagnostics(username: str) -> dict[str, Any]:
    ident = _primary_network()
    gateway = str(ident.get('gateway') or '')
    mode = str(ident.get('mode') or 'OFFLINE').upper()
    gateway_probe = _icmp_series(gateway, 4, 900) if gateway else None
    domestic_probe = _domestic_latency_probe(6, 1.8)
    international_probe = _tcp_latency_series(DEFAULT_SPEED_HOST, 443, 6, 2.5)
    public_probe = _icmp_series(PUBLIC_PROBE, 3, 1200)
    dns = _dns_probe(DEFAULT_SPEED_HOST)
    https = _https_probe()
    tcp443 = _tcp_probe(DEFAULT_SPEED_HOST)

    checks: list[dict[str, Any]] = []
    adapter_ok = bool(ident.get('adapter')) and mode != 'OFFLINE'
    checks.append({'key':'adapter','label':'Card mạng / IP','status':_diag_status(adapter_ok),
                   'detail': f"{ident.get('adapter') or 'Không nhận diện'} · {ident.get('local_ip') or 'Chưa có IPv4'} · {mode}"})
    checks.append({'key':'route','label':'Default gateway','status':_diag_status(bool(gateway)),
                   'detail': gateway or 'Không tìm thấy default gateway'})

    if gateway_probe:
        gw_replies = int(gateway_probe.get('replies') or 0)
        gw_loss = float(gateway_probe.get('packet_loss') or 0)
        gw_status = 'OK' if gw_replies == int(gateway_probe.get('samples') or 0) and gw_loss == 0 else ('WARN' if gw_replies else 'FAIL')
        checks.append({'key':'gateway_ping','label':'Kết nối tới Gateway','status':gw_status,
                       'detail': f"Latency {gateway_probe.get('latency_ms') if gateway_probe.get('latency_ms') is not None else '-'} ms · Loss {gateway_probe.get('packet_loss')}%"})
    else:
        checks.append({'key':'gateway_ping','label':'Kết nối tới Gateway','status':'FAIL','detail':'Không có gateway để kiểm tra'})

    domestic_ok = int(domestic_probe.get('replies') or 0) > 0 and domestic_probe.get('latency_ms') is not None
    dlat = domestic_probe.get('latency_ms')
    djit = domestic_probe.get('jitter_ms')
    dloss = domestic_probe.get('packet_loss')
    domestic_grade = _grade(dlat, djit, dloss) if domestic_ok else 'UNKNOWN'
    checks.append({'key':'domestic_latency','label':'Độ trễ trong nước','status':(
        'FAIL' if not domestic_ok else ('WARN' if float(dlat) >= 60 else 'OK')),
        'detail': ('Không đo được điểm trong nước' if not domestic_ok else
                   f"{dlat} ms · {domestic_probe.get('target')} · TCP 443 median")})

    ilat = international_probe.get('latency_ms')
    checks.append({'key':'international_latency','label':'Độ trễ quốc tế / CDN','status':'INFO',
                   'detail': ('Không đo được' if ilat is None else
                              f"{ilat} ms · {international_probe.get('target')} · chỉ tham khảo, không dùng để chấm mạng trong nước")})

    checks.append({'key':'dns','label':'DNS máy chủ đo tốc độ','status':_diag_status(bool(dns.get('ok'))),
                   'detail': (f"{dns.get('host')} → {', '.join(dns.get('addresses') or [])} · {dns.get('elapsed_ms')} ms" if dns.get('ok') else f"Không phân giải được DNS · {dns.get('error','ERROR')}")})
    checks.append({'key':'tcp443','label':'TCP tới máy chủ đo tốc độ','status':_diag_status(bool(tcp443.get('ok'))),
                   'detail': (f"{DEFAULT_SPEED_HOST}:443 · {tcp443.get('elapsed_ms')} ms" if tcp443.get('ok') else f"Không mở được TCP 443 · {tcp443.get('error','ERROR')}")})
    checks.append({'key':'https','label':'HTTPS máy chủ đo tốc độ','status':_diag_status(bool(https.get('ok'))),
                   'detail': (f"HTTP {https.get('status')} · {https.get('elapsed_ms')} ms" if https.get('ok') else f"HTTPS thất bại · {https.get('error','ERROR')}")})
    checks.append({'key':'jitter','label':'Jitter trong nước','status':'FAIL' if djit is None else ('WARN' if float(djit) >= 20 else 'OK'),
                   'detail':'Không đo được jitter trong nước' if djit is None else f'{djit} ms'})
    checks.append({'key':'packet_loss','label':'Mất kết nối mẫu trong nước','status':'FAIL' if dloss is None else ('WARN' if float(dloss) > 0 else 'OK'),
                   'detail':'Không đo được' if dloss is None else f'{dloss}% số lần TCP connect tới điểm trong nước thất bại'})
    ref_latency = public_probe.get('latency_ms')
    checks.append({'key':'reference_icmp','label':'ICMP tham chiếu 1.1.1.1','status':'INFO',
                   'detail': f"{ref_latency if ref_latency is not None else '-'} ms · chỉ tham khảo, không dùng để chấm điểm"})

    issues: list[str] = []
    recommendations: list[str] = []
    if not adapter_ok:
        issues.append('Không nhận diện được card mạng/IP đang hoạt động.')
        recommendations.append('Kiểm tra trạng thái Ethernet/Wi-Fi và DHCP trên Windows.')
    if not gateway:
        issues.append('Không có default gateway.')
        recommendations.append('Kiểm tra DHCP, cấu hình IPv4 và router nội bộ.')
    elif not gateway_probe or int(gateway_probe.get('replies') or 0) == 0:
        issues.append('Không liên lạc được default gateway.')
        recommendations.append('Kiểm tra cáp/Wi-Fi, switch và router trước khi kiểm tra Internet.')
    if not domestic_ok:
        issues.append('Không đo được điểm mạng trong nước; kết quả quốc tế không được dùng để kết luận mạng nội địa kém.')
        recommendations.append('Thử lại phép đo trong nước hoặc cấu hình NA_DOMESTIC_PROBE_HOSTS bằng máy chủ Việt Nam/ISP nội bộ phù hợp.')
    elif float(dlat) >= 80:
        issues.append(f'Độ trễ trong nước rất cao ({dlat} ms).')
        recommendations.append('Kiểm tra Wi-Fi/cáp, tải nền, VPN/proxy và tuyến ISP trong nước.')
    elif float(dlat) >= 40:
        issues.append(f'Độ trễ trong nước cao ({dlat} ms).')
    if djit is not None and float(djit) >= 20:
        issues.append(f'Jitter trong nước cao ({djit} ms), kết nối có thể không ổn định.')
    if dloss is not None and float(dloss) > 0:
        issues.append(f'{dloss}% mẫu TCP tới điểm trong nước thất bại.')
    if not dns.get('ok'):
        issues.append('DNS không phân giải được máy chủ đo tốc độ.')
        recommendations.append('Kiểm tra DNS server của adapter hoặc cấu hình DNS nội bộ.')
    if not tcp443.get('ok') or not https.get('ok'):
        issues.append('Kết nối HTTPS tới máy chủ đo tốc độ chưa thông suốt.')
        recommendations.append('Kiểm tra firewall/proxy/router và đường truyền WAN.')

    fail_count = sum(1 for c in checks if c['status'] == 'FAIL')
    warn_count = sum(1 for c in checks if c['status'] == 'WARN')
    critical_keys = {'adapter','route','gateway_ping','dns','https'}
    critical_fail = any(c['status'] == 'FAIL' and c['key'] in critical_keys for c in checks)
    if critical_fail:
        overall = 'POOR'
    elif not domestic_ok:
        overall = 'FAIR'
    elif domestic_grade == 'POOR':
        overall = 'POOR'
    elif fail_count or warn_count or domestic_grade == 'FAIR':
        overall = 'FAIR'
    else:
        overall = 'GOOD'
    result = {
        'overall': overall, 'line_grade': domestic_grade, 'quality_scope': 'domestic',
        'identity': ident, 'checks': checks,
        'issues': issues, 'recommendations': list(dict.fromkeys(recommendations)),
        'metrics': {'latency_ms': dlat, 'jitter_ms': djit, 'packet_loss': dloss,
                    'domestic_latency_ms': dlat, 'domestic_target': domestic_probe.get('target'),
                    'international_latency_ms': ilat,
                    'international_jitter_ms': international_probe.get('jitter_ms'),
                    'international_packet_loss': international_probe.get('packet_loss'),
                    'gateway_latency_ms': (gateway_probe or {}).get('latency_ms'),
                    'reference_icmp_latency_ms': ref_latency},
        'probes': {'gateway': gateway_probe, 'domestic': domestic_probe,
                   'speed_server': international_probe, 'public_reference': public_probe,
                   'dns': dns, 'tcp443': tcp443, 'https': https},
        'note': 'Điểm chất lượng chính dùng điểm đo trong nước nhanh nhất. Máy chủ CDN quốc tế và ICMP 1.1.1.1 chỉ hiển thị tham khảo.',
    }
    ensure_tables59()
    with connection() as c:
        cur = c.execute('INSERT INTO network_diagnostics59(overall,result_json,created_by,created_at) VALUES(?,?,?,?)',
                        (overall, json.dumps(result, ensure_ascii=False), username or 'system', utcnow()))
        c.commit()
        result['id'] = int(cur.lastrowid)
    return result


def _store(test_type: str, user: str, ident: dict[str, Any], result: dict[str, Any]) -> int:
    ensure_tables59()
    with connection() as c:
        cur = c.execute('''INSERT INTO network_quality59(
            test_type,target,gateway,local_ip,network_mode,latency_ms,jitter_ms,packet_loss,
            download_mbps,upload_mbps,grade,detail,created_by,created_at,quality_scope,quality_target,
            international_latency_ms,international_jitter_ms,international_packet_loss)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            test_type, str(result.get('target') or ''), ident.get('gateway') or '', ident.get('local_ip') or '', ident.get('mode') or '',
            result.get('latency_ms'), result.get('jitter_ms'), result.get('packet_loss'), result.get('download_mbps'), result.get('upload_mbps'),
            result.get('grade') or 'UNKNOWN', str(result.get('detail') or '')[:2000], user, utcnow(),
            str(result.get('quality_scope') or ''), str(result.get('quality_target') or result.get('target') or ''),
            result.get('international_latency_ms'), result.get('international_jitter_ms'), result.get('international_packet_loss')))
        c.commit()
        return int(cur.lastrowid)


def _speed_url(base: str, **params: Any) -> str:
    params = {**params, 'na_nonce': f"{time.time_ns()}-{os.getpid()}"}
    return base + ('&' if '?' in base else '?') + urllib.parse.urlencode(params)


def _download_once(byte_count: int, timeout: int = 35) -> int:
    byte_count = max(1, int(byte_count))
    req = urllib.request.Request(_speed_url(DEFAULT_DOWNLOAD_URL, bytes=byte_count), headers={
        'User-Agent': 'NetworkAutomation/7.0.3', 'Cache-Control': 'no-store', 'Pragma': 'no-cache'})
    received = 0
    with urllib.request.urlopen(req, timeout=timeout) as r:
        while received < byte_count:
            chunk = r.read(min(1024 * 1024, byte_count - received))
            if not chunk:
                break
            received += len(chunk)
    return received


def _upload_once(byte_count: int, timeout: int = 35) -> int:
    byte_count = max(1, int(byte_count))
    body = b'0' * byte_count
    req = urllib.request.Request(_speed_url(DEFAULT_UPLOAD_URL), data=body, method='POST', headers={
        'User-Agent': 'NetworkAutomation/7.0.3', 'Content-Type': 'application/octet-stream',
        'Cache-Control': 'no-store', 'Pragma': 'no-cache'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        r.read(1024)
    return byte_count


def _split_bytes(total: int, streams: int) -> list[int]:
    streams = max(1, int(streams)); total = max(streams, int(total))
    base, extra = divmod(total, streams)
    return [base + (1 if i < extra else 0) for i in range(streams)]


def _parallel_transfer(worker, total_bytes: int, streams: int, timeout: int) -> tuple[int, float]:
    sizes = _split_bytes(total_bytes, streams)
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=streams, thread_name_prefix='na-speed') as pool:
        futures = [pool.submit(worker, size, timeout) for size in sizes]
        completed = sum(int(f.result()) for f in futures)
    elapsed = max(time.perf_counter() - started, 0.001)
    return completed, elapsed


def _adaptive_bytes(warm_mbps: float, requested_mb: int, seconds: float, minimum_mb: int, maximum_mb: int) -> int:
    requested = max(int(requested_mb), minimum_mb) * 1024 * 1024
    estimated = int(max(0.0, float(warm_mbps)) * 1_000_000.0 / 8.0 * float(seconds))
    return max(minimum_mb * 1024 * 1024, min(maximum_mb * 1024 * 1024, max(requested, estimated)))


def _download_test(megabytes: int, detailed: bool = False):
    # Warm the resolver/TLS path, then size the real sample for roughly 2-3 s.
    warm_bytes = 2 * 1024 * 1024
    started = time.perf_counter(); warm_received = _download_once(warm_bytes, 20)
    warm_elapsed = max(time.perf_counter() - started, 0.001)
    warm_mbps = warm_received * 8.0 / 1_000_000.0 / warm_elapsed
    total_bytes = _adaptive_bytes(warm_mbps, megabytes, 2.5, 16, 128)
    streams = 4 if total_bytes >= 32 * 1024 * 1024 else 2
    received, elapsed = _parallel_transfer(_download_once, total_bytes, streams, 40)
    if received < total_bytes * 0.90:
        raise RuntimeError('SPEEDTEST_DOWNLOAD_INCOMPLETE')
    mbps = round((received * 8.0 / 1_000_000.0) / elapsed, 2)
    meta = {'mbps': mbps, 'bytes': received, 'megabytes': round(received / 1_000_000.0, 1),
            'seconds': round(elapsed, 3), 'streams': streams, 'warmup_mbps': round(warm_mbps, 2)}
    return meta if detailed else mbps


def _upload_test(megabytes: int, detailed: bool = False):
    warm_bytes = 512 * 1024
    started = time.perf_counter(); warm_sent = _upload_once(warm_bytes, 20)
    warm_elapsed = max(time.perf_counter() - started, 0.001)
    warm_mbps = warm_sent * 8.0 / 1_000_000.0 / warm_elapsed
    total_bytes = _adaptive_bytes(warm_mbps, megabytes, 2.0, 8, 64)
    streams = 4 if total_bytes >= 16 * 1024 * 1024 else 2
    sent, elapsed = _parallel_transfer(_upload_once, total_bytes, streams, 40)
    mbps = round((sent * 8.0 / 1_000_000.0) / elapsed, 2)
    meta = {'mbps': mbps, 'bytes': sent, 'megabytes': round(sent / 1_000_000.0, 1),
            'seconds': round(elapsed, 3), 'streams': streams, 'warmup_mbps': round(warm_mbps, 2)}
    return meta if detailed else mbps


@router.get('/network/summary')
def summary(request: Request):
    require_role(request)
    ensure_tables59()
    ident = _primary_network()
    with connection() as c:
        latest = c.execute("SELECT * FROM network_quality59 ORDER BY id DESC LIMIT 1").fetchone()
        speed = c.execute("SELECT * FROM network_quality59 WHERE test_type='SPEED' ORDER BY id DESC LIMIT 1").fetchone()
        line = c.execute("SELECT * FROM network_quality59 WHERE test_type='LINE' ORDER BY id DESC LIMIT 1").fetchone()
        intl = c.execute("SELECT * FROM network_quality59 WHERE test_type='LINE_INTL' ORDER BY id DESC LIMIT 1").fetchone()
        diag = c.execute("SELECT * FROM network_diagnostics59 ORDER BY id DESC LIMIT 1").fetchone()
    latest_diag = None
    legacy_diag = False
    if diag:
        try:
            parsed = json.loads(str(diag['result_json'] or '{}'))
            if isinstance((parsed.get('probes') or {}).get('domestic'), dict):
                latest_diag = parsed
                latest_diag['id'] = int(diag['id'])
                latest_diag['created_at'] = diag['created_at']
                latest_diag['created_by'] = diag['created_by']
            else:
                legacy_diag = True
        except (TypeError, ValueError, json.JSONDecodeError):
            latest_diag = {'overall':'UNKNOWN','checks':[],'issues':['Dữ liệu chẩn đoán gần nhất bị lỗi định dạng.']}
    raw_speed = dict(speed) if speed else None
    raw_line = dict(line) if line else None
    raw_intl = dict(intl) if intl else None
    speed_stats = raw_speed if raw_speed and 'Adaptive multi-stream WAN bandwidth test' in str(raw_speed.get('detail') or '') else None
    speed_quality = speed_stats if speed_stats and str(speed_stats.get('quality_scope') or '') == 'domestic' else None
    line_d = raw_line if raw_line and str(raw_line.get('quality_scope') or '') == 'domestic' else None
    intl_d = raw_intl if raw_intl and str(raw_intl.get('quality_scope') or '') == 'international' else None
    legacy_measurements = bool((raw_speed and not speed_quality) or (raw_line and not line_d) or legacy_diag)
    candidates = [x for x in (speed_quality, line_d) if x]
    display_quality = max(candidates, key=lambda x: str(x.get('created_at') or '')) if candidates else None
    return {'identity':ident,'latest':dict(latest) if latest else None,'latest_speed':speed_stats,
            'latest_line':line_d,'latest_international':intl_d,'display_quality':display_quality,
            'latest_diagnostics':latest_diag,'needs_retest':legacy_measurements,
            'quality_scope':'domestic','domestic_probe_hosts':list(_domestic_probe_hosts()),
            'speed_provider':f'{DEFAULT_SPEED_HOST} · international/CDN multi-stream',
            'note':'Chất lượng chính dùng điểm đo trong nước; tốc độ băng thông vẫn đo với CDN riêng.'}


def run_line_test_internal(username: str = 'system', scope: str = 'domestic'):
    ident = _primary_network(); gateway = str(ident.get('gateway') or '')
    gw = _icmp_series(gateway, 4, 1000) if gateway else None
    international = _tcp_latency_series(DEFAULT_SPEED_HOST, 443, 6, 2.5)
    public = _icmp_series(PUBLIC_PROBE, 3, 1200)
    scope = 'international' if str(scope).lower() == 'international' else 'domestic'
    if scope == 'international':
        chosen = international if int(international.get('replies') or 0) else public
        grade = _grade(chosen.get('latency_ms'), chosen.get('jitter_ms'), chosen.get('packet_loss'))
        result = {**chosen, 'grade': grade, 'quality_scope':'international',
                  'quality_target': chosen.get('target') or DEFAULT_SPEED_HOST,
                  'international_latency_ms': chosen.get('latency_ms'),
                  'international_jitter_ms': chosen.get('jitter_ms'),
                  'international_packet_loss': chosen.get('packet_loss'),
                  'gateway_probe':gw,'international_probe':international,'public_probe':public,
                  'detail':f"quality_scope=international; quality_target={chosen.get('target') or DEFAULT_SPEED_HOST}; method={chosen.get('method','ICMP')}; gateway={gateway or '-'}"}
        test_type = 'LINE_INTL'
    else:
        domestic = _domestic_latency_probe(6, 1.8)
        domestic_ok = int(domestic.get('replies') or 0) > 0 and domestic.get('latency_ms') is not None
        if domestic_ok:
            chosen = domestic
            grade = _grade(chosen.get('latency_ms'), chosen.get('jitter_ms'), chosen.get('packet_loss'))
            quality_scope = 'domestic'
        elif int(international.get('replies') or 0):
            chosen = international
            grade = 'FAIR'
            quality_scope = 'international_fallback'
        else:
            chosen = gw or international
            grade = 'POOR'
            quality_scope = 'unavailable'
        result = {**chosen, 'grade':grade, 'quality_scope':quality_scope,
                  'quality_target':chosen.get('target') or '', 'domestic_probe':domestic,
                  'gateway_probe':gw,'international_probe':international,'public_probe':public,
                  'international_latency_ms':international.get('latency_ms'),
                  'international_jitter_ms':international.get('jitter_ms'),
                  'international_packet_loss':international.get('packet_loss'),
                  'detail':f"quality_scope={quality_scope}; quality_target={chosen.get('target') or '-'}; international_target={DEFAULT_SPEED_HOST}; gateway={gateway or '-'}; reference_icmp={public.get('latency_ms')}"}
        test_type = 'LINE'
    result['id'] = _store(test_type, username or 'system', ident, result)
    result['identity'] = ident
    return result


@router.post('/network/line-test')
def line_test(payload: LineTestIn, request: Request):
    user = require_role(request, 'Admin', 'Analyst', 'Operator')
    return run_line_test_internal(user['username'], payload.scope)


@router.post('/network/diagnostics')
def network_diagnostics(request: Request):
    user = require_role(request, 'Admin', 'Analyst', 'Operator')
    return _network_diagnostics(user['username'])


@router.post('/network/speed-test')
def speed_test(payload: SpeedTestIn, request: Request):
    user = require_role(request, 'Admin', 'Analyst', 'Operator')
    if not payload.confirm_bandwidth_use:
        raise HTTPException(400, 'BANDWIDTH_CONFIRMATION_REQUIRED')
    ident = _primary_network()
    if ident.get('mode') not in {'LAN+WAN', 'WAN'}:
        raise HTTPException(409, 'WAN_NOT_AVAILABLE')
    domestic = _domestic_latency_probe(6, 1.8)
    before = _tcp_latency_series(DEFAULT_SPEED_HOST, 443, 6, 2.5)
    try:
        down_meta = _download_test(payload.download_mb, detailed=True)
        up_meta = _upload_test(payload.upload_mb, detailed=True) if payload.run_upload else None
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
        raise HTTPException(502, 'SPEEDTEST_FAILED: ' + str(exc)[:180])
    after = _tcp_latency_series(DEFAULT_SPEED_HOST, 443, 6, 2.5)
    intl_latency_values = [float(x['latency_ms']) for x in (before, after) if x.get('latency_ms') is not None]
    intl_jitter_values = [float(x['jitter_ms']) for x in (before, after) if x.get('jitter_ms') is not None]
    intl_latency = round(statistics.median(intl_latency_values), 2) if intl_latency_values else None
    intl_jitter = round(statistics.median(intl_jitter_values), 2) if intl_jitter_values else None
    intl_loss = max(float(before.get('packet_loss') or 0), float(after.get('packet_loss') or 0))
    domestic_ok = int(domestic.get('replies') or 0) > 0 and domestic.get('latency_ms') is not None
    if domestic_ok:
        latency = domestic.get('latency_ms'); jitter = domestic.get('jitter_ms'); loss = domestic.get('packet_loss')
        grade = _grade(latency, jitter, loss); quality_scope = 'domestic'
    else:
        latency = None; jitter = None; loss = None; grade = 'UNKNOWN'; quality_scope = 'international_fallback'
    result = {'target': DEFAULT_DOWNLOAD_URL, 'speed_host': DEFAULT_SPEED_HOST,
              'quality_scope':quality_scope,'quality_target':domestic.get('target') if domestic_ok else '',
              'domestic_target':domestic.get('target'),'domestic_probe':domestic,
              'download_mbps': down_meta['mbps'], 'upload_mbps': up_meta['mbps'] if up_meta else None,
              'latency_ms': latency, 'jitter_ms': jitter, 'packet_loss': loss, 'grade': grade,
              'international_latency_ms':intl_latency,'international_jitter_ms':intl_jitter,
              'international_packet_loss':intl_loss,
              'download_mb': down_meta['megabytes'], 'upload_mb': up_meta['megabytes'] if up_meta else 0,
              'download_streams': down_meta['streams'], 'upload_streams': up_meta['streams'] if up_meta else 0,
              'download_seconds': down_meta['seconds'], 'upload_seconds': up_meta['seconds'] if up_meta else None,
              'latency_method': 'Domestic TCP median for quality; international/CDN TCP median reported separately',
              'detail': f'Adaptive multi-stream WAN bandwidth test; quality_scope={quality_scope}; throughput_scope=international_cdn; domestic_target={domestic.get("target") or "-"}; international_target={DEFAULT_SPEED_HOST}'}
    result['id'] = _store('SPEED', user['username'], ident, result)
    result['identity'] = ident
    return result


@router.post('/network/optimize')
def optimize_line(payload: OptimizeLineIn, request: Request):
    user = require_role(request, 'Admin')
    if not payload.confirm_system_change:
        raise HTTPException(400, 'SYSTEM_CHANGE_CONFIRMATION_REQUIRED')
    ident=_primary_network()
    before = run_line_test_internal(user['username'])
    if str(before.get('grade') or '').upper() in {'EXCELLENT', 'GOOD'}:
        return {
            'status': 'NOT_NEEDED', 'before': before, 'after': before, 'actions': [],
            'improvement': _improvement(before, before),
            'message': 'Đường truyền hiện không ở mức lag cần tối ưu. Không thay đổi cấu hình Windows.',
            'capacity_note': 'Ứng dụng không thể tăng vượt giới hạn gói cước, Wi-Fi/router hoặc đường truyền ISP.'
        }

    actions = _safe_windows_line_optimization()
    time.sleep(0.6)
    after = run_line_test_internal(user['username'])
    ok_actions = sum(1 for a in actions if a.get('ok'))
    return {
        'status': 'APPLIED' if ok_actions else 'NO_CHANGE',
        'before': before, 'after': after, 'actions': actions,
        'improvement': _improvement(before, after),
        'message': f'Đã áp dụng {ok_actions}/{len(actions)} tối ưu an toàn và đo lại đường truyền.',
        'capacity_note': 'Tối ưu chỉ xử lý cấu hình cục bộ có thể gây trễ; không thể tự tăng băng thông vượt tốc độ do Wi-Fi/router/ISP cung cấp.'
    }


@router.get('/network/history')
def history(request: Request, limit: int = 100):
    require_role(request)
    ensure_tables59(); limit = max(1, min(int(limit), 500))
    with connection() as c:
        return [dict(r) for r in c.execute("SELECT * FROM network_quality59 ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
