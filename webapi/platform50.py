"""NetworkAutomation Desktop platform endpoints.

Local Windows connectivity, Wi-Fi/camera diagnostics and readiness checks.
Desktop-only local execution path.
"""
from __future__ import annotations
import json, os, platform, shutil, socket, subprocess, sys, time, ipaddress, threading
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from webapi.runtime37 import connection, utcnow
from webapi.security37 import require_role
from webapi import security37
from app_runtime import hidden_subprocess_kwargs

router=APIRouter(prefix='/api/v50')

security37.WRITE_RULES.extend([
    ('POST', r'/api/v50/cameras/\d+/diagnose', ('Admin','Operator')),
    ('POST', r'/api/v50/wifi/diagnose', ('Admin','Operator')),
    ('POST', r'/api/v50/startup-discovery/ensure', ('Admin','Operator')),
])

class CameraDiagIn(BaseModel):
    timeout_seconds: float = Field(default=5.0, ge=0.5, le=15.0)

class WifiDiagIn(BaseModel):
    gateway: str = Field(default='', max_length=255)
    internet: str = Field(default='1.1.1.1', max_length=255)


def normalize_discovery_sources(raw):
    """Normalize DB comma strings and preliminary in-memory source lists."""
    if isinstance(raw,(list,tuple,set)):
        src=[str(x).strip().upper() for x in raw if str(x).strip()]
    else:
        src=[x.strip().upper() for x in str(raw or '').split(',') if x.strip()]
    return list(dict.fromkeys(src))


def normalize_discovery_rows(rows):
    counts={'ICMP':0,'ARP':0,'DHCP':0,'MDNS':0,'SSDP':0,'DNS':0,'NETBIOS':0}
    for row in rows:
        src=normalize_discovery_sources(row.get('sources'))
        row['sources']=src
        for source in src:
            if source in counts:
                counts[source]+=1
    return counts



_NETWORK_CACHE_LOCK=threading.Lock()
_NETWORK_CACHE={'checked_at':0.0,'result':None}


def _powershell_adapters():
    """Return active Windows IPv4 adapters. Read-only and best-effort."""
    if os.name!='nt':
        return []
    script=(
        "$ErrorActionPreference='Stop';"
        "Get-NetIPConfiguration | Where-Object { $_.IPv4Address -and $_.NetAdapter.Status -eq 'Up' } | "
        "ForEach-Object { [PSCustomObject]@{ alias=$_.InterfaceAlias; description=$_.InterfaceDescription; "
        "ipv4=@($_.IPv4Address | ForEach-Object {$_.IPAddress}); "
        "networks=@($_.IPv4Address | ForEach-Object {\"$($_.IPAddress)/$($_.PrefixLength)\"}); "
        "metric=if($_.NetIPInterface){$_.NetIPInterface.InterfaceMetric}else{999999}; "
        "gateway=if($_.IPv4DefaultGateway){$_.IPv4DefaultGateway.NextHop}else{$null} } } | ConvertTo-Json -Compress"
    )
    try:
        r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',script],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,errors='replace',timeout=6,**hidden_subprocess_kwargs())
        if r.returncode or not (r.stdout or '').strip():
            return []
        data=json.loads(r.stdout)
        rows=data if isinstance(data,list) else [data]
        out=[]
        for row in rows:
            ips=row.get('ipv4') or []
            if isinstance(ips,str): ips=[ips]
            clean=[]
            for value in ips:
                try:
                    addr=ipaddress.ip_address(str(value))
                    if addr.version==4 and not addr.is_loopback: clean.append(str(addr))
                except ValueError: pass
            if clean:
                nets=[]
                for value in row.get('networks') or []:
                    try:
                        iface=ipaddress.ip_interface(str(value))
                        if iface.version==4 and not iface.ip.is_loopback: nets.append(str(iface))
                    except ValueError: pass
                try: metric=int(row.get('metric') or 999999)
                except Exception: metric=999999
                out.append({'name':str(row.get('alias') or ''),'description':str(row.get('description') or ''),'ipv4':clean,
                            'networks':nets,'metric':metric,'gateway':str(row.get('gateway') or '')})
        return out
    except Exception:
        return []


def _fallback_ipv4():
    ips=set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET,socket.SOCK_DGRAM):
            ip=info[4][0]
            if ip and not ip.startswith('127.'): ips.add(ip)
    except Exception:
        pass
    for target in ('1.1.1.1','8.8.8.8','192.168.1.1'):
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try:
            s.connect((target,53));ip=s.getsockname()[0]
            if ip and not ip.startswith('127.'): ips.add(ip)
        except OSError:
            pass
        finally:
            s.close()
    return [{'name':'system','description':'fallback route detection','ipv4':sorted(ips),'gateway':''}] if ips else []


def _wan_probe(timeout=1.5):
    targets=[('1.1.1.1',443),('8.8.8.8',53),('9.9.9.9',443)]
    attempts=[]
    for host,port in targets:
        started=time.monotonic()
        try:
            with socket.create_connection((host,port),timeout=timeout):
                elapsed=round((time.monotonic()-started)*1000,1)
                attempts.append({'target':f'{host}:{port}','ok':True,'elapsed_ms':elapsed})
                return True,attempts
        except OSError as exc:
            attempts.append({'target':f'{host}:{port}','ok':False,'error':type(exc).__name__,
                             'elapsed_ms':round((time.monotonic()-started)*1000,1)})
    return False,attempts


def network_connectivity(force=False):
    now=time.time()
    with _NETWORK_CACHE_LOCK:
        cached=_NETWORK_CACHE.get('result')
        if cached and not force and now-float(_NETWORK_CACHE.get('checked_at') or 0)<30:
            return {**cached,'cached':True}
    adapters=_powershell_adapters() or _fallback_ipv4()
    addresses=[];private=[];link_local=[];gateways=[]
    for row in adapters:
        if row.get('gateway'): gateways.append(row['gateway'])
        for value in row.get('ipv4',[]):
            if value in addresses: continue
            addresses.append(value)
            try:
                addr=ipaddress.ip_address(value)
                if addr.is_link_local: link_local.append(value)
                elif addr.is_private: private.append(value)
            except ValueError: pass
    lan=bool(private)
    wan,attempts=_wan_probe()
    if wan and lan: mode='LAN+WAN'
    elif wan: mode='WAN'
    elif lan: mode='LAN_ONLY'
    elif link_local: mode='LINK_LOCAL'
    else: mode='OFFLINE'
    result={'mode':mode,'lan':lan,'wan':wan,'connected':bool(lan or wan),'checked_at':utcnow(),
            'adapters':adapters,'ipv4':addresses,'private_ipv4':private,'gateways':gateways,
            'wan_checks':attempts,'meaning':{
                'LAN+WAN':'Đã kết nối mạng nội bộ và có đường ra Internet.',
                'WAN':'Có đường ra Internet; không phát hiện IPv4 LAN riêng trên adapter đang hoạt động.',
                'LAN_ONLY':'Đã kết nối LAN nhưng chưa xác minh được đường ra Internet.',
                'LINK_LOCAL':'Chỉ phát hiện địa chỉ link-local; có thể chưa nhận được IP/gateway hợp lệ.',
                'OFFLINE':'Chưa phát hiện LAN hoạt động và chưa xác minh được kết nối Internet.'
            }[mode], 'cached':False}
    with _NETWORK_CACHE_LOCK:
        _NETWORK_CACHE['checked_at']=now;_NETWORK_CACHE['result']=result
    return result


@router.get('/network/connectivity')
def network_status(request:Request, force:bool=False):
    require_role(request)
    return network_connectivity(force=force)


def _primary_identity_from_connectivity(result: dict) -> dict:
    candidates=[]
    for row in result.get('adapters') or []:
        try: metric=int(row.get('metric') or 999999)
        except Exception: metric=999999
        gateway=str(row.get('gateway') or '')
        net_by_ip={}
        for raw in row.get('networks') or []:
            try:
                iface=ipaddress.ip_interface(str(raw))
                if iface.version==4: net_by_ip[str(iface.ip)]=str(iface.network)
            except ValueError: pass
        for raw_ip in row.get('ipv4') or []:
            try: addr=ipaddress.ip_address(str(raw_ip))
            except ValueError: continue
            if addr.version!=4 or addr.is_loopback or addr.is_link_local: continue
            network=net_by_ip.get(str(addr),'')
            gateway_rank=2
            if gateway:
                gateway_rank=1
                try:
                    if network and ipaddress.ip_address(gateway) in ipaddress.ip_network(network,strict=False):
                        gateway_rank=0
                except ValueError:
                    pass
            candidates.append((gateway_rank, metric, 0 if addr.is_private else 1, int(addr), str(addr), row, network))
    if not candidates:
        return {'ipv4':'','network':'','adapter':'','gateway':'','description':''}
    candidates.sort(key=lambda x:(x[0],x[1],x[2],x[3]))
    _,_,_,_,ip,row,network=candidates[0]
    return {'ipv4':ip,'network':network,'adapter':str(row.get('name') or ''),
            'gateway':str(row.get('gateway') or ''),'description':str(row.get('description') or '')}


def ensure_network_identity_table():
    sql="""CREATE TABLE IF NOT EXISTS web_network_identity_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ipv4 TEXT NOT NULL DEFAULT '', network TEXT NOT NULL DEFAULT '',
        adapter TEXT NOT NULL DEFAULT '', gateway TEXT NOT NULL DEFAULT '',
        mode TEXT NOT NULL DEFAULT '', reason TEXT NOT NULL DEFAULT '', observed_at TEXT NOT NULL
    )"""
    with connection() as c:
        c.execute(sql)
        c.execute('CREATE INDEX IF NOT EXISTS idx_web_network_identity_history_id ON web_network_identity_history(id DESC)')
        c.commit()


def record_network_identity(reason='runtime', force=False) -> dict:
    ensure_network_identity_table()
    current=network_connectivity(force=force)
    ident=_primary_identity_from_connectivity(current)
    with connection() as c:
        prev=c.execute('SELECT * FROM web_network_identity_history ORDER BY id DESC LIMIT 1').fetchone()
        previous=dict(prev) if prev else {}
        changed=bool(previous and (previous.get('ipv4')!=ident['ipv4'] or previous.get('network')!=ident['network'] or previous.get('adapter')!=ident['adapter']))
        c.execute('INSERT INTO web_network_identity_history(ipv4,network,adapter,gateway,mode,reason,observed_at) VALUES(?,?,?,?,?,?,?)',
                  (ident['ipv4'],ident['network'],ident['adapter'],ident['gateway'],current.get('mode') or '',reason,utcnow()))
        c.commit()
    return {**ident,'mode':current.get('mode') or 'OFFLINE','checked_at':current.get('checked_at'),
            'reason':reason,'changed':changed,'previous_ipv4':previous.get('ipv4',''),
            'previous_network':previous.get('network',''),'previous_adapter':previous.get('adapter','')}



def network_identity_status(force=False) -> dict:
    current=network_connectivity(force=force)
    ident=_primary_identity_from_connectivity(current)
    ensure_network_identity_table()
    with connection() as c:
        row=c.execute('SELECT * FROM web_network_identity_history ORDER BY id DESC LIMIT 1').fetchone()
    last=dict(row) if row else {}
    changed=bool(last and (last.get('ipv4')!=ident['ipv4'] or last.get('network')!=ident['network'] or last.get('adapter')!=ident['adapter']))
    return {**ident,'mode':current.get('mode') or 'OFFLINE','checked_at':current.get('checked_at'),
            'changed_since_start':changed,'startup_ipv4':last.get('ipv4',''),'startup_network':last.get('network',''),
            'startup_adapter':last.get('adapter',''),'startup_observed_at':last.get('observed_at',''),'source':'WINDOWS_LOCAL'}

@router.get('/network/identity')
def network_identity(request:Request, force:bool=False):
    require_role(request)
    return network_identity_status(force=force)

@router.get('/about')
def about(request:Request):
    require_role(request)
    return {'version':'7.0.3','api':'5.9.2-cybersecurity','edition':'Desktop Only',
            'principle':'local Windows execution only',
            'run_mode':'desktop','python':platform.python_version(),'platform':platform.platform()}

@router.post('/cameras/{camera_id}/diagnose')
def camera_diagnose(camera_id:int,x:CameraDiagIn,request:Request):
    u=require_role(request,'Admin','Operator')
    from modules.monitor_extensions import diagnose_camera, history
    with connection() as c:
        row=c.execute('SELECT id,name,host,port,stream_enc,snapshot_enc FROM camera_registry WHERE id=?',(camera_id,)).fetchone()
    if not row: raise HTTPException(404,'Không tìm thấy camera/NVR.')
    camera=dict(row)
    result=diagnose_camera(camera,x.timeout_seconds)
    result.update({'camera_id':camera_id,'name':camera['name'],'has_stream':bool(camera.get('stream_enc')),'has_snapshot':bool(camera.get('snapshot_enc')),
                   'checked_at':utcnow(),'actor':u['username']})
    safe={'code':result.get('code'),'elapsed_ms':result.get('elapsed_ms'),'steps':result.get('steps',[]),'meaning':result.get('meaning')}
    history('Camera',camera['host'],result['status'],json.dumps(safe,ensure_ascii=False))
    return result

@router.post('/wifi/diagnose')
def wifi_diagnose(x:WifiDiagIn,request:Request):
    u=require_role(request,'Admin','Operator')
    from modules.monitor_extensions import wifi_diagnostics, history, redact
    result=wifi_diagnostics(x.gateway,x.internet)
    safe={k:v for k,v in result.items() if k not in ('interfaces','nearby_networks')}
    history('WiFi','Windows',result.get('status','Unknown'),redact(json.dumps(safe,ensure_ascii=False)))
    result['checked_at']=utcnow();result['actor']=u['username']
    return result


@router.get('/startup-discovery')
def startup_discovery_status(request:Request):
    require_role(request)
    from webapi.autodiscovery5010 import status
    return status()


@router.get('/connected-devices')
def connected_devices(request:Request):
    """Return devices observed by local Windows LAN discovery sources."""
    require_role(request,'Admin','Operator','Viewer')
    from webapi.autodiscovery5010 import status as discovery_status, ensure_tables
    ensure_tables()
    st=discovery_status()
    scan_key=st.get('scan_key') or ''
    result=[]
    if not scan_key and st.get('state') in ('RUNNING','QUEUED'):
        # 6.7.1: expose passive preliminary LAN evidence immediately instead of
        # returning an empty list for the entire active sweep duration.
        result=[dict(x) for x in (st.get('preliminary_devices') or [])]
    if scan_key:
        with connection() as c:
            try:
                rows=c.execute("""SELECT r.ip,r.mac,r.hostname,r.status,r.latency_ms,r.created_at,
                               COALESCE(e.sources,CASE WHEN lower(r.status)='online' THEN 'ICMP' ELSE 'ARP' END) sources
                        FROM web_scan_results r LEFT JOIN web_connected_device_evidence e
                          ON e.scan_key=r.scan_key AND e.ip=r.ip
                        WHERE r.scan_key=? AND lower(r.status) IN ('online','activearp','activelan')
                        ORDER BY r.ip""",(scan_key,)).fetchall()
            except Exception:
                rows=c.execute("SELECT ip,mac,hostname,status,latency_ms,created_at FROM web_scan_results WHERE scan_key=? AND lower(status) IN ('online','activearp','activelan') ORDER BY ip",(scan_key,)).fetchall()
            result=[dict(r) for r in rows]
    counts=normalize_discovery_rows(result)
    return {'state':st.get('state'),'network':st.get('network'),'scan_key':scan_key,
            'count':len(result),'devices':result,'source_counts':counts,'detail':st.get('detail'),'completed_at':st.get('completed_at')}

@router.post('/startup-discovery/ensure')
def startup_discovery_ensure(request:Request, force:bool=False):
    require_role(request,'Admin','Operator')
    from webapi.autodiscovery5010 import ensure
    return ensure(source='desktop-open', force=force)

@router.get('/readiness')
def readiness(request:Request):
    require_role(request,'Admin')
    root=Path(__file__).resolve().parent.parent
    deps={name:bool(shutil.which(name)) for name in ('ping','ssh','telnet')}
    pydeps={}
    for name in ('paramiko','pysnmp','uvicorn','fastapi','cryptography'):
        try: __import__(name);pydeps[name]=True
        except Exception: pydeps[name]=False
    return {'version':'7.0.3','executables':deps,'python_dependencies':pydeps,'network':network_connectivity(),
            'release_verify':(root/'VERIFY_DESKTOP_RELEASE.py').is_file(),'data_policy':'Local app data is preserved across upgrades',
            'warnings':[m for m,ok in [('Paramiko chưa sẵn sàng',pydeps['paramiko']),('PySNMP chưa sẵn sàng',pydeps['pysnmp'])] if not ok]}
