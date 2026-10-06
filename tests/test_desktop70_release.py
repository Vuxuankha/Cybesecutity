from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_release_files_exist():
    required = [
        'desktop_launcher.py', 'NetworkAutomationDesktop.spec',
        'installer/NetworkAutomation.iss', 'requirements-desktop.txt',
        'webapi/desktop70.py', 'webapi/static/desktop70.js',
        '.github/workflows/windows-desktop-release.yml',
    ]
    for rel in required:
        assert (ROOT / rel).is_file(), rel


def test_desktop_static_asset_is_allowlisted_and_loaded_last():
    routes = (ROOT / 'webapi/routes37.py').read_text(encoding='utf-8')
    app = (ROOT / 'webapi/static/app.js').read_text(encoding='utf-8')
    assert "'desktop70.js': 'text/javascript'" in routes
    assert "'desktop70.js'" in app
    assert "'routerapi69.js'" not in app.split('const naFeatureScripts=', 1)[1].split(';', 1)[0]
    assert "'routerapi70.js'" not in app.split('const naFeatureScripts=', 1)[1].split(';', 1)[0]
    assert "NA_UI_VERSION='7.0.3'" in app


def test_launcher_forces_localhost_desktop_mode():
    text = (ROOT / 'desktop_launcher.py').read_text(encoding='utf-8')
    assert 'NA_DESKTOP_APP' in text
    assert 'NA_WEB_ONLY_BROWSER' not in text
    assert '127.0.0.1' in text
    assert 'NA_PUBLIC_REGISTRATION' not in text
    assert 'NA_MFA_REQUIRED' in text


def test_desktop_network_overview_uses_local_identity_and_arp(monkeypatch):
    import webapi.desktop70 as d70
    import webapi.platform50 as p50
    import webapi.autodiscovery5010 as ad

    monkeypatch.setattr(d70, '_desktop_only', lambda: None)
    monkeypatch.setattr(p50, 'network_connectivity', lambda force=True: {
        'wan': True, 'lan': True,
        'adapters': [{'name': 'Ethernet', 'description': 'NIC', 'ipv4': ['192.168.2.34'],
                      'networks': ['192.168.2.34/24'], 'metric': 10, 'gateway': '192.168.2.1'}]
    })
    monkeypatch.setattr(ad, '_arp_neighbors', lambda network: {
        '192.168.2.1': '64-05-E9-8B-48-23',
        '192.168.2.3': '90-09-D0-89-2F-8D',
    })
    monkeypatch.setattr(d70, '_probe_neighbors', lambda addresses, timeout_ms=450: {
        ip: {'status': 'Online', 'response': 2.0, 'packet_loss': 0.0, 'error': ''}
        for ip in addresses
    })
    d70._CACHE.update({'at': 0.0, 'probe': False, 'data': None})
    data = d70.network_overview_data(probe=True, force=True)
    assert data['source'] == 'WINDOWS_LOCAL_MACHINE'
    assert data['local_ip'] == '192.168.2.34'
    assert data['network'] == '192.168.2.0/24'
    assert data['gateway'] == '192.168.2.1'
    assert data['arp_count'] == 2
    assert data['online_count'] == 2
    assert data['devices'][0]['role'] == 'Gateway'


def test_release_identity_is_desktop_7():
    from webapi import runtime37
    assert runtime37.UI_VERSION == '7.0.3'
    assert runtime37.RELEASE == 'Desktop 7.0.3 Desktop Only'
    assert runtime37.SERVICE == 'networkautomation-desktop'
