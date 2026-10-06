"""Windows-native network overview for NetworkAutomation Desktop 7.0.3.

This module reads only the local Windows machine's active adapter, default gateway and ARP/neighbor table, then performs
bounded ICMP probes against the already-observed private neighbors.
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, HTTPException, Request

from modules.icmp_probe import icmp_ping
from app_runtime import hidden_subprocess_kwargs
from webapi import security37
from webapi.runtime37 import utcnow

router = APIRouter(prefix="/api/desktop", tags=["desktop-7.0.3"])

_CACHE = {"at": 0.0, "probe": False, "data": None}
_CACHE_TTL = 15.0
_MAX_NEIGHBOR_PROBES = 128


def _desktop_only() -> None:
    if os.environ.get("NA_DESKTOP_APP", "0").strip().lower() not in ("1", "true", "yes", "on"):
        raise HTTPException(409, "DESKTOP_NATIVE_NETWORK_ONLY")
    if os.name != "nt":
        raise HTTPException(409, "WINDOWS_NATIVE_NETWORK_ONLY")


def _sort_ip(value: str):
    try:
        return int(ipaddress.ip_address(value))
    except ValueError:
        return 2**128




def _fallback_windows_identity() -> dict:
    """PowerShell-independent default-route fallback for locked-down Windows PCs."""
    if os.name != "nt":
        return {"ipv4":"","network":"","adapter":"","gateway":"","description":""}
    gateway=""; interface_ip=""
    try:
        cp=subprocess.run(["route","print","-4"],capture_output=True,text=True,errors="ignore",timeout=5,**hidden_subprocess_kwargs())
        choices=[]
        for line in (cp.stdout or "").splitlines():
            m=re.match(r"^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+(?:\.\d+){3})\s+(\d+(?:\.\d+){3})\s+(\d+)\s*$",line)
            if m:
                choices.append((int(m.group(3)),m.group(1),m.group(2)))
        if choices:
            _,gateway,interface_ip=sorted(choices,key=lambda x:x[0])[0]
    except Exception:
        pass
    try:
        import psutil
        stats=psutil.net_if_stats()
        candidates=[]
        for name,addrs in psutil.net_if_addrs().items():
            if name in stats and not stats[name].isup:
                continue
            for a in addrs:
                if a.family != socket.AF_INET:
                    continue
                try:
                    addr=ipaddress.ip_address(a.address)
                except ValueError:
                    continue
                if addr.is_loopback or addr.is_link_local:
                    continue
                net=""
                if a.netmask:
                    try: net=str(ipaddress.ip_network(f"{a.address}/{a.netmask}",strict=False))
                    except ValueError: pass
                row={"ipv4":str(addr),"network":net,"adapter":name,"gateway":gateway if str(addr)==interface_ip else "","description":name}
                if str(addr)==interface_ip:
                    return row
                candidates.append(row)
        private=[x for x in candidates if ipaddress.ip_address(x["ipv4"]).is_private]
        if private:
            row=private[0]
            if gateway: row["gateway"]=gateway
            return row
        if candidates:
            return candidates[0]
    except Exception:
        pass
    return {"ipv4":interface_ip,"network":"","adapter":"Windows","gateway":gateway,"description":"route print fallback"}

def _probe_neighbors(addresses: list[str], timeout_ms: int = 450) -> dict[str, dict]:
    if not addresses:
        return {}
    workers = min(48, max(1, len(addresses)))
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="na-desktop-ping") as pool:
        futures = {pool.submit(icmp_ping, ip, timeout_ms, 1): ip for ip in addresses}
        for future in as_completed(futures):
            ip = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # defensive: one host must never abort the page
                result = {"ip": ip, "status": "Error", "response": None, "packet_loss": None,
                          "error": f"{type(exc).__name__}: {exc}"[:180]}
            out[ip] = result
    return out


def network_overview_data(*, probe: bool = True, force: bool = False) -> dict:
    _desktop_only()
    now = time.monotonic()
    cached = _CACHE.get("data")
    if cached and not force and bool(_CACHE.get("probe")) == bool(probe) and now - float(_CACHE.get("at") or 0) < _CACHE_TTL:
        return {**cached, "cached": True}

    # Reuse the already-tested 5.0 Windows adapter selection and the 5.0.10
    # neighbor parser instead of introducing a second network stack.
    from webapi.platform50 import network_connectivity, _primary_identity_from_connectivity
    from webapi.autodiscovery5010 import _arp_neighbors

    connectivity = network_connectivity(force=True)
    identity = _primary_identity_from_connectivity(connectivity)
    if not identity.get("ipv4") or not identity.get("network") or not identity.get("gateway"):
        fallback = _fallback_windows_identity()
        for key in ("ipv4","network","adapter","gateway","description"):
            if not identity.get(key) and fallback.get(key):
                identity[key]=fallback[key]
    local_ip = str(identity.get("ipv4") or "")
    gateway = str(identity.get("gateway") or "")
    network = str(identity.get("network") or "")
    adapter_name = str(identity.get("adapter") or "")
    description = str(identity.get("description") or "")

    neighbors: dict[str, str] = {}
    if network:
        try:
            net = ipaddress.ip_network(network, strict=False)
            if net.version == 4 and net.is_private:
                neighbors = _arp_neighbors(network)
        except ValueError:
            neighbors = {}

    addresses = sorted(neighbors, key=_sort_ip)
    probe_addresses = addresses[:_MAX_NEIGHBOR_PROBES]
    probes = _probe_neighbors(probe_addresses, timeout_ms=450) if probe else {}

    devices = []
    online = 0
    for ip in addresses:
        p = probes.get(ip) or {}
        status = str(p.get("status") or "ARP") if probe else "ARP"
        if status == "Online":
            online += 1
        role = "Gateway" if gateway and ip == gateway else "Neighbor"
        devices.append({
            "ip": ip,
            "mac": neighbors.get(ip, ""),
            "role": role,
            "status": status,
            "latency_ms": p.get("response") if probe else None,
            "latency_is_upper_bound": bool(p.get("response_is_upper_bound")) if probe else False,
            "packet_loss": p.get("packet_loss") if probe else None,
            "error": p.get("error", "") if probe else "",
        })

    gateway_probe = None
    if gateway:
        gateway_probe = probes.get(gateway) if gateway in probes else (icmp_ping(gateway, 700, 2) if probe else None)

    result = {
        "mode": "WINDOWS_NATIVE",
        "source": "WINDOWS_LOCAL_MACHINE",
        "adapter": adapter_name,
        "description": description,
        "local_ip": local_ip,
        "network": network,
        "gateway": gateway,
        "internet": bool(connectivity.get("wan")),
        "lan": bool(connectivity.get("lan")),
        "gateway_ping": gateway_probe,
        "arp_count": len(devices),
        "online_count": online if probe else None,
        "probe_count": len(probe_addresses) if probe else 0,
        "probe_truncated": bool(probe and len(addresses) > len(probe_addresses)),
        "probe_limit": _MAX_NEIGHBOR_PROBES,
        "devices": devices,
        "observed_at": utcnow(),
        "cached": False,
        "note": "ARP/neighbor table is a local observation. Ping marks current ICMP replies; ARP presence alone does not prove a device is currently online.",
    }
    _CACHE.update({"at": now, "probe": bool(probe), "data": result})
    return result


@router.get("/network-overview")
def network_overview(request: Request, probe: bool = True, force: bool = False):
    user=security37.require_role(request)
    if probe and user['role']=='Viewer':
        raise HTTPException(403,'PERMISSION_DENIED: Viewer cannot initiate network probes')
    return network_overview_data(probe=probe, force=force)
