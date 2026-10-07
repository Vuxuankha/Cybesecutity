from __future__ import annotations

import base64
import ipaddress
import logging
import os
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

from webapi.model37 import StrictBaseModel
from webapi.security37 import require_role

router = APIRouter(prefix='/api/v1/windows-tools', tags=['Windows Local Tools'])

_MAX_STDOUT = 256_000
_MAX_STDERR = 64_000
_DEFAULT_TIMEOUT = 25
_MAX_TIMEOUT = 60

WHITE_PROFILES = {
    'system_overview', 'ping', 'dns_lookup', 'tcp_port', 'route_table', 'arp_table',
    'tcp_connections', 'http_head', 'tls_certificate', 'file_hash', 'processes',
    'services', 'firewall', 'windows_events', 'adapters', 'traceroute', 'server_status',
    'network_state',
}
RED_PROFILES = {
    'red_recon', 'red_config_audit', 'red_connectivity', 'red_http_headers', 'red_tls_audit',
    'red_cookie_audit', 'red_network_state', 'red_light_load',
}
ALL_PROFILES = WHITE_PROFILES | RED_PROFILES


class WindowsToolRunIn(StrictBaseModel):
    mode: str = Field(default='white', max_length=16)
    profile: str = Field(min_length=1, max_length=64)
    target: str | None = Field(default=None, max_length=2048)
    port: int | None = Field(default=None, ge=1, le=65535)
    text: str | None = Field(default=None, max_length=16_384)
    count: int | None = Field(default=None, ge=1, le=5)


def _is_windows() -> bool:
    return os.name == 'nt'


def _ps_exe() -> str:
    exe = shutil.which('powershell.exe') or shutil.which('powershell')
    if not exe:
        raise HTTPException(503, 'WINDOWS_POWERSHELL_NOT_FOUND')
    return exe


def _hidden_kwargs() -> dict:
    if not _is_windows():
        return {}
    kwargs: dict = {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    kwargs['startupinfo'] = startupinfo
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    if flags:
        kwargs['creationflags'] = flags
    return kwargs


def _kill_tree(pid: int) -> None:
    if not _is_windows() or pid <= 0:
        return
    try:
        taskkill = shutil.which('taskkill.exe') or 'taskkill.exe'
        result = subprocess.run(
            [taskkill, '/PID', str(int(pid)), '/T', '/F'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
            **_hidden_kwargs(),
        )
        if result.returncode not in (0, 128):
            logging.getLogger(__name__).warning('taskkill returned %s for pid=%s', result.returncode, pid)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        logging.getLogger(__name__).warning('Unable to terminate process tree pid=%s: %s', pid, exc)


def _run_process(argv: list[str], timeout: int = _DEFAULT_TIMEOUT) -> dict:
    if not _is_windows():
        raise HTTPException(503, 'WINDOWS_LOCAL_TOOLS_ONLY')
    timeout = max(1, min(int(timeout), _MAX_TIMEOUT))
    started = time.perf_counter()
    env = os.environ.copy()
    env['NA_CHILD_KIND'] = 'windows-local-tool'
    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env,
            **_hidden_kwargs(),
        )
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            _kill_tree(proc.pid)
            try:
                proc.kill()
            except (OSError, ProcessLookupError) as kill_exc:
                logging.getLogger(__name__).warning('Direct kill failed pid=%s: %s', proc.pid, kill_exc)
            try:
                out, err = proc.communicate(timeout=3)
            except (OSError, subprocess.SubprocessError) as comm_exc:
                logging.getLogger(__name__).warning('Timed-out process output collection failed pid=%s: %s', proc.pid, comm_exc)
                out, err = '', ''
            raise HTTPException(504, 'WINDOWS_TOOL_TIMEOUT') from exc
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(503, 'WINDOWS_TOOL_EXECUTABLE_NOT_FOUND') from exc
    except Exception as exc:
        raise HTTPException(500, f'WINDOWS_TOOL_START_FAILED:{type(exc).__name__}') from exc
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    out = (out or '')[:_MAX_STDOUT]
    err = (err or '')[:_MAX_STDERR]
    return {
        'ok': proc.returncode == 0,
        'exit_code': int(proc.returncode or 0),
        'stdout': out,
        'stderr': err,
        'elapsed_ms': elapsed_ms,
        'backend': 'windows-local',
    }


def _run_ps(script: str, timeout: int = _DEFAULT_TIMEOUT) -> dict:
    prefix = "$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.UTF8Encoding]::new();"
    encoded = base64.b64encode((prefix + script).encode('utf-16le')).decode('ascii')
    return _run_process([
        _ps_exe(), '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
        '-EncodedCommand', encoded,
    ], timeout=timeout)


def _ps_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _hostname(value: str) -> str:
    value = (value or '').strip()
    if not value or len(value) > 253 or not re.fullmatch(r'[A-Za-z0-9._:-]+', value):
        raise HTTPException(400, 'INVALID_HOST_OR_IP')
    return value


def _private_host(value: str) -> tuple[str, str]:
    value = _hostname(value)
    try:
        ip = ipaddress.ip_address(value)
        if not (ip.is_private or ip.is_loopback or ip.is_link_local):
            raise ValueError
        return value, str(ip)
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(value, None, type=socket.SOCK_STREAM)
        addrs = {ipaddress.ip_address(x[4][0]) for x in infos}
        if not addrs or any(not (ip.is_private or ip.is_loopback or ip.is_link_local) for ip in addrs):
            raise ValueError
        approved = sorted(addrs, key=lambda ip: (ip.version, int(ip)))[0]
        return value, str(approved)
    except Exception as exc:
        raise HTTPException(400, 'TARGET_MUST_RESOLVE_PRIVATE') from exc


def _private_url(value: str) -> tuple[str, str, int, str]:
    try:
        p = urlsplit((value or '').strip())
        if p.scheme not in {'http', 'https'} or not p.hostname or p.username or p.password:
            raise ValueError
        original_host, approved_ip = _private_host(p.hostname)
        port = p.port or (443 if p.scheme == 'https' else 80)
        return p.geturl(), original_host, int(port), approved_ip
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, 'URL_MUST_BE_HTTP_S_AND_PRIVATE') from exc


def _existing_file(value: str) -> str:
    raw = (value or '').strip().strip('"')
    if not raw or len(raw) > 1024:
        raise HTTPException(400, 'FILE_PATH_REQUIRED')
    p = Path(raw).expanduser()
    if not p.is_file():
        raise HTTPException(404, 'FILE_NOT_FOUND')
    return str(p.resolve())


def _profile_script(profile: str, body: WindowsToolRunIn) -> tuple[str, int, str]:
    target = (body.target or '').strip()
    port = int(body.port or 443)

    if profile == 'system_overview':
        script = r"""
$os=Get-CimInstance Win32_OperatingSystem
$cs=Get-CimInstance Win32_ComputerSystem
[pscustomobject]@{ComputerName=$env:COMPUTERNAME;User=$env:USERNAME;OS=$os.Caption;Version=$os.Version;Build=$os.BuildNumber;LastBoot=$os.LastBootUpTime;RAM_GB=[math]::Round($cs.TotalPhysicalMemory/1GB,2)} | Format-List | Out-String -Width 240
"""
        return script, 20, 'PowerShell'

    if profile == 'ping':
        original, approved = _private_host(target)
        script = f"Test-Connection -ComputerName {_ps_literal(approved)} -Count 2 -ErrorAction Stop | Select-Object Address,IPv4Address,ResponseTime,Status | Format-Table -AutoSize | Out-String -Width 240"
        return script, 15, 'PowerShell'

    if profile == 'dns_lookup':
        host = _hostname(target)
        script = f"Resolve-DnsName -Name {_ps_literal(host)} -ErrorAction Stop | Select-Object -First 40 Name,Type,IPAddress,NameHost | Format-Table -AutoSize | Out-String -Width 240"
        return script, 15, 'PowerShell'

    if profile in {'tcp_port', 'server_status', 'red_connectivity', 'red_recon'}:
        original, approved = _private_host(target)
        p = int(body.port or 443)
        script = f"$r=Test-NetConnection -ComputerName {_ps_literal(approved)} -Port {p} -InformationLevel Detailed -WarningAction SilentlyContinue; $r | Select-Object ComputerName,RemoteAddress,RemotePort,NameResolutionSucceeded,PingSucceeded,TcpTestSucceeded,SourceAddress,InterfaceAlias | Format-List | Out-String -Width 240"
        if profile == 'red_recon':
            script = f"Resolve-DnsName -Name {_ps_literal(original)} -ErrorAction SilentlyContinue | Select-Object -First 10 Name,Type,IPAddress | Format-Table -AutoSize | Out-String -Width 240; " + script
        return script, 20, 'PowerShell'

    if profile == 'route_table':
        return "Get-NetRoute -AddressFamily IPv4 -ErrorAction Stop | Sort-Object RouteMetric | Select-Object -First 120 DestinationPrefix,NextHop,RouteMetric,InterfaceAlias | Format-Table -AutoSize | Out-String -Width 260", 20, 'PowerShell'

    if profile == 'arp_table':
        return "Get-NetNeighbor -AddressFamily IPv4 -ErrorAction Stop | Select-Object -First 200 IPAddress,LinkLayerAddress,State,InterfaceAlias | Format-Table -AutoSize | Out-String -Width 260", 20, 'PowerShell'

    if profile in {'tcp_connections', 'red_network_state'}:
        script = "Get-NetTCPConnection -ErrorAction SilentlyContinue | Sort-Object State,RemoteAddress | Select-Object -First 200 LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess | Format-Table -AutoSize | Out-String -Width 300"
        if profile == 'red_network_state':
            script = "Get-NetRoute -AddressFamily IPv4 -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 60 DestinationPrefix,NextHop,RouteMetric,InterfaceAlias | Format-Table -AutoSize | Out-String -Width 260; " + script
        return script, 20, 'PowerShell'

    if profile in {'http_head', 'red_http_headers'}:
        url, host, p, approved = _private_url(target)
        curl_ip = f'[{approved}]' if ':' in approved else approved
        resolve_value = f'{host}:{p}:{curl_ip}'
        script = f"""
$curl=(Get-Command curl.exe -ErrorAction Stop).Source
& $curl --silent --show-error --head --max-time 10 --max-redirs 0 --resolve {_ps_literal(resolve_value)} {_ps_literal(url)}
if($LASTEXITCODE -ne 0){{exit $LASTEXITCODE}}
"""
        return script, 15, 'PowerShell + curl.exe (Windows)'

    if profile in {'tls_certificate', 'red_tls_audit'}:
        host, approved = _private_host(target)
        p = int(body.port or 443)
        script = f"""
$script:policyErrors='Unknown'
$tcp=[Net.Sockets.TcpClient]::new()
try {{
  $tcp.Connect({_ps_literal(approved)},{p})
  $ssl=[Net.Security.SslStream]::new($tcp.GetStream(),$false,{{param($s,$c,$ch,$e) $script:policyErrors=[string]$e; return $true}})
  try {{
    $ssl.AuthenticateAsClient({_ps_literal(host)})
    $cert=[Security.Cryptography.X509Certificates.X509Certificate2]::new($ssl.RemoteCertificate)
    [pscustomobject]@{{Host={_ps_literal(host)};IP={_ps_literal(approved)};Port={p};Protocol=[string]$ssl.SslProtocol;Cipher=[string]$ssl.CipherAlgorithm;CipherStrength=$ssl.CipherStrength;PolicyErrors=$script:policyErrors;Subject=$cert.Subject;Issuer=$cert.Issuer;NotBefore=$cert.NotBefore;NotAfter=$cert.NotAfter;Thumbprint=$cert.Thumbprint}} | Format-List | Out-String -Width 260
    if($script:policyErrors -ne 'None'){{exit 2}}
  }} finally {{ if($ssl){{$ssl.Dispose()}} }}
}} finally {{ $tcp.Dispose() }}
"""
        return script, 20, 'PowerShell'

    if profile == 'file_hash':
        path = _existing_file(target)
        return f"Get-FileHash -Algorithm SHA256 -LiteralPath {_ps_literal(path)} -ErrorAction Stop | Format-List Algorithm,Hash,Path | Out-String -Width 260", 20, 'PowerShell'

    if profile == 'processes':
        return "Get-Process -ErrorAction SilentlyContinue | Sort-Object CPU -Descending | Select-Object -First 120 Id,ProcessName,CPU,WorkingSet,Path | Format-Table -AutoSize | Out-String -Width 300", 20, 'PowerShell'

    if profile == 'services':
        return "Get-Service | Sort-Object Status,DisplayName | Select-Object -First 220 Status,Name,DisplayName | Format-Table -AutoSize | Out-String -Width 280", 20, 'PowerShell'

    if profile == 'firewall':
        return "Get-NetFirewallProfile -ErrorAction Stop | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction,NotifyOnListen,LogFileName | Format-Table -AutoSize | Out-String -Width 300", 20, 'PowerShell'

    if profile == 'windows_events':
        return "Get-WinEvent -FilterHashtable @{LogName='System';StartTime=(Get-Date).AddHours(-24)} -MaxEvents 100 -ErrorAction Stop | Select-Object TimeCreated,Id,LevelDisplayName,ProviderName,@{N='Message';E={($_.Message -replace '[\\r\\n]+',' ')}} | Format-Table -Wrap | Out-String -Width 320", 30, 'PowerShell'

    if profile == 'adapters':
        return "Get-NetAdapter -ErrorAction Stop | Select-Object Name,InterfaceDescription,Status,LinkSpeed,MacAddress | Format-Table -AutoSize | Out-String -Width 280; Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object InterfaceAlias,IPAddress,PrefixLength | Format-Table -AutoSize | Out-String -Width 220", 20, 'PowerShell'

    if profile == 'traceroute':
        original, approved = _private_host(target)
        # Direct executable invocation via PowerShell keeps the window hidden and avoids arbitrary cmd input.
        return f"& tracert.exe -d -h 15 -w 1000 {_ps_literal(approved)} | Out-String -Width 240", 35, 'PowerShell/CMD tool'

    if profile == 'network_state':
        return "Get-NetAdapter -ErrorAction SilentlyContinue | Select-Object Name,Status,LinkSpeed,MacAddress | Format-Table -AutoSize | Out-String -Width 240; Get-NetRoute -AddressFamily IPv4 -ErrorAction SilentlyContinue | Sort-Object RouteMetric | Select-Object -First 80 DestinationPrefix,NextHop,RouteMetric,InterfaceAlias | Format-Table -AutoSize | Out-String -Width 260; Get-NetTCPConnection -ErrorAction SilentlyContinue | Select-Object -First 120 LocalAddress,LocalPort,RemoteAddress,RemotePort,State | Format-Table -AutoSize | Out-String -Width 280", 25, 'PowerShell'

    if profile == 'red_config_audit':
        script = "Get-NetFirewallProfile -ErrorAction SilentlyContinue | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction | Format-Table -AutoSize | Out-String -Width 240; Get-ExecutionPolicy -List | Format-Table -AutoSize | Out-String -Width 200; if(Get-Command Get-SmbServerConfiguration -ErrorAction SilentlyContinue){Get-SmbServerConfiguration | Select-Object EnableSMB1Protocol,EnableSMB2Protocol,RequireSecuritySignature,EncryptData | Format-List | Out-String -Width 220}; if(Get-Command Get-SmbClientConfiguration -ErrorAction SilentlyContinue){Get-SmbClientConfiguration | Select-Object EnableInsecureGuestLogons,RequireSecuritySignature | Format-List | Out-String -Width 220}"
        return script, 20, 'PowerShell'

    if profile == 'red_cookie_audit':
        cookie = (body.text or '').strip()
        if not cookie:
            raise HTTPException(400, 'COOKIE_TEXT_REQUIRED')
        script = f"""
$s={_ps_literal(cookie)}
[pscustomobject]@{{Secure=[bool]($s -match '(?i);\\s*Secure\\b');HttpOnly=[bool]($s -match '(?i);\\s*HttpOnly\\b');SameSite=[bool]($s -match '(?i);\\s*SameSite=(Lax|Strict|None)\\b');SameSiteStrictOrLax=[bool]($s -match '(?i);\\s*SameSite=(Lax|Strict)\\b')}} | Format-List | Out-String -Width 200
"""
        return script, 10, 'PowerShell'

    if profile == 'red_light_load':
        url, host, p, approved = _private_url(target)
        count = int(body.count or 3)
        curl_ip = f'[{approved}]' if ':' in approved else approved
        resolve_value = f'{host}:{p}:{curl_ip}'
        script = f"""
$curl=(Get-Command curl.exe -ErrorAction Stop).Source;$u={_ps_literal(url)};$resolve={_ps_literal(resolve_value)};$n={count};$times=@();$failed=0
for($i=1;$i -le $n;$i++){{
  $sw=[Diagnostics.Stopwatch]::StartNew()
  & $curl --silent --show-error --head --output NUL --max-time 5 --max-redirs 0 --resolve $resolve $u
  $code=$LASTEXITCODE;if($code -ne 0){{$failed++}}
  $sw.Stop();$times+=$sw.ElapsedMilliseconds
  [pscustomobject]@{{Attempt=$i;CurlExit=$code;LatencyMs=$sw.ElapsedMilliseconds}}
  Start-Sleep -Milliseconds 250
}}
'AverageMs='+[math]::Round((($times|Measure-Object -Average).Average),1)
if($failed -gt 0){{exit 2}}
"""
        return script, 35, 'PowerShell + curl.exe (Windows)'

    raise HTTPException(400, 'UNSUPPORTED_WINDOWS_PROFILE')


def _profile_catalog() -> dict:
    return {
        'backend': 'windows-local',
        'shells': ['PowerShell', 'CMD/native Windows executables'],
        'arbitrary_shell': False,
        'white': sorted(WHITE_PROFILES),
        'red': sorted(RED_PROFILES),
        'limits': {'timeout_seconds_max': _MAX_TIMEOUT, 'stdout_bytes_max': _MAX_STDOUT, 'stderr_bytes_max': _MAX_STDERR, 'red_light_load_requests_max': 5},
    }


@router.get('/profiles')
def profiles(request: Request):
    require_role(request, 'Admin', 'Analyst', 'Operator', 'Viewer')
    return _profile_catalog()


@router.get('/status')
def status(request: Request):
    require_role(request, 'Admin', 'Analyst', 'Operator', 'Viewer')
    return {
        'windows': _is_windows(),
        'powershell': bool(shutil.which('powershell.exe') or shutil.which('powershell')),
        'cmd': bool(shutil.which('cmd.exe') or shutil.which('cmd')),
        'curl': bool(shutil.which('curl.exe') or shutil.which('curl')),
        'backend': 'windows-local',
        'arbitrary_shell': False,
    }


@router.post('/run')
def run_profile(body: WindowsToolRunIn, request: Request):
    require_role(request, 'Admin', 'Analyst', 'Operator')
    mode = body.mode.strip().lower()
    profile = body.profile.strip().lower()
    if mode not in {'white', 'red'}:
        raise HTTPException(400, 'MODE_MUST_BE_WHITE_OR_RED')
    allowed = WHITE_PROFILES if mode == 'white' else RED_PROFILES
    if profile not in allowed:
        raise HTTPException(400, 'PROFILE_NOT_ALLOWED_FOR_MODE')
    script, timeout, engine = _profile_script(profile, body)
    result = _run_ps(script, timeout=timeout)
    return {
        'mode': mode,
        'profile': profile,
        'engine': engine,
        'target': (body.target or '').strip(),
        **result,
    }
