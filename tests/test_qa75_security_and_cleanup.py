from __future__ import annotations

import json
import sqlite3
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError


def test_password_policy_rejects_trivial_and_whitespace_values():
    from modules import accounts
    accounts.validate_password('Password123!')
    accounts.validate_password('abcdefgh1234')
    for weak in ('', ' ', '1', 'a', 'x'*129):
        with pytest.raises(ValueError):
            accounts.validate_password(weak)


def test_public_user_normalizes_enabled_to_boolean():
    from modules.accounts import public_user
    row = {'id': 1, 'username': 'u', 'role': 'Viewer', 'enabled': 1, 'created_at': '', 'updated_at': ''}
    assert public_user(row)['enabled'] is True
    row['enabled'] = 0
    assert public_user(row)['enabled'] is False


def test_login_model_rejects_unknown_fields_and_oversized_password():
    from webapi.main import LoginIn
    with pytest.raises(ValidationError):
        LoginIn(username='Admin', password='x', unexpected='bad')
    with pytest.raises(ValidationError):
        LoginIn(username='Admin', password='x' * 513)


def test_password_request_models_allow_short_nonempty_and_enforce_size_cap():
    from webapi.routes37 import PasswordIn
    PasswordIn(old_password='old', new_password='a', confirmation='a')
    with pytest.raises(ValidationError):
        PasswordIn(old_password='old', new_password='', confirmation='')
    with pytest.raises(ValidationError):
        PasswordIn(old_password='x' * 513, new_password='a', confirmation='a')


def test_server_and_credential_models_have_bounded_fields():
    from webapi.main import ServerTargetIn, CredentialIn, SNMPv3In, AutoIPProfileIn
    with pytest.raises(ValidationError):
        ServerTargetIn(name='n' * 121, host='127.0.0.1')
    with pytest.raises(ValidationError):
        CredentialIn(name='n', kind='SSH', username='u' * 161, secret='s')
    with pytest.raises(ValidationError):
        SNMPv3In(name='n', username='u' * 161)
    with pytest.raises(ValidationError):
        AutoIPProfileIn(name='n' * 121, mode='PING')


def test_asset_count_unions_unique_ips_across_sources():
    from webapi.cybersecurity51 import _asset_count
    c = sqlite3.connect(':memory:')
    c.execute('CREATE TABLE ip_mac_inventory(ip TEXT)')
    c.execute('CREATE TABLE security_assets(ip TEXT)')
    c.executemany('INSERT INTO ip_mac_inventory(ip) VALUES(?)', [('10.0.0.1',), ('10.0.0.2',)])
    c.executemany('INSERT INTO security_assets(ip) VALUES(?)', [('10.0.0.2',), ('10.0.0.3',)])
    assert _asset_count(c) == 3


def test_vulnerability_count_uses_latest_scan_per_asset_only():
    from webapi.cybersecurity51 import _current_vulnerability_findings_count
    c = sqlite3.connect(':memory:')
    c.execute('CREATE TABLE vulnerability_scans51(id INTEGER PRIMARY KEY,asset_ip TEXT)')
    c.execute('CREATE TABLE vulnerability_findings51(id INTEGER PRIMARY KEY,scan_id INTEGER,asset_ip TEXT)')
    c.executemany('INSERT INTO vulnerability_scans51(id,asset_ip) VALUES(?,?)', [(1,'10.0.0.1'),(2,'10.0.0.1'),(3,'10.0.0.2')])
    c.executemany('INSERT INTO vulnerability_findings51(scan_id,asset_ip) VALUES(?,?)', [(1,'10.0.0.1'),(1,'10.0.0.1'),(2,'10.0.0.1'),(3,'10.0.0.2')])
    assert _current_vulnerability_findings_count(c) == 2
    assert _current_vulnerability_findings_count(c, '10.0.0.1') == 1


def test_snapshot_decode_fails_closed_and_csv_formula_is_sanitized():
    from webapi.cybersecurity56 import _decode_snapshot, _csv_safe
    with pytest.raises(HTTPException) as exc:
        _decode_snapshot('{broken')
    assert exc.value.status_code == 409
    assert _csv_safe('=HYPERLINK("http://bad")').startswith("'=")
    assert _csv_safe('+1+1').startswith("'+")
    assert _csv_safe('normal') == 'normal'


def test_soc_asset_ip_validation():
    from webapi.cybersecurity55 import _optional_ip
    assert _optional_ip('192.168.1.5') == '192.168.1.5'
    assert _optional_ip('') == ''
    with pytest.raises(HTTPException) as exc:
        _optional_ip('not-an-ip')
    assert exc.value.status_code == 400


def test_windows_tool_input_and_profile_catalog_are_bounded():
    from webapi.windows_tools79 import WindowsToolRunIn, _profile_catalog
    from pydantic import ValidationError
    WindowsToolRunIn(mode='white', profile='ping', target='127.0.0.1', port=443, count=1)
    with pytest.raises(ValidationError):
        WindowsToolRunIn(mode='red', profile='red_light_load', target='http://127.0.0.1/', count=6)
    c=_profile_catalog()
    assert c['arbitrary_shell'] is False and c['limits']['red_light_load_requests_max']==5


def test_network_probe_is_backend_blocked_for_viewer(monkeypatch):
    import webapi.desktop70 as d70
    monkeypatch.setattr(d70.security37, 'require_role', lambda request: {'username':'v','role':'Viewer'})
    with pytest.raises(HTTPException) as exc:
        d70.network_overview(object(), probe=True, force=False)
    assert exc.value.status_code == 403


def test_detection_like_escapes_sql_wildcards_in_source():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / 'webapi/cybersecurity54.py').read_text(encoding='utf-8')
    assert ".replace('%','\\\\%').replace('_','\\\\_')" in src
    assert "LIKE ? ESCAPE '\\\\'" in src


def test_tls_check_uses_real_server_monitor_table_and_report_uses_real_ioc_table():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    c51 = (root / 'webapi/cybersecurity51.py').read_text(encoding='utf-8')
    c56 = (root / 'webapi/cybersecurity56.py').read_text(encoding='utf-8')
    assert 'FROM server_monitor_targets WHERE lower(host)=lower(?)' in c51
    assert 'FROM server_targets WHERE lower(host)=lower(?)' not in c51
    assert 'FROM ioc_watchlist54 WHERE enabled=1' in c56
    assert 'threat_iocs54' not in c56


def test_windows_tools_run_is_write_capable_role_only_and_tls_uses_default_validation_for_http():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / 'webapi/windows_tools79.py').read_text(encoding='utf-8')
    run = src.split("@router.post('/run')", 1)[1]
    assert "require_role(request, 'Admin', 'Analyst', 'Operator')" in run
    assert "'Viewer'" not in run.split('require_role',1)[1].split('mode =',1)[0]
    assert 'curl.exe' in src and '--resolve' in src and '-SkipCertificateCheck' not in src and ' -k' not in src
    assert 'PolicyErrors' in src


def test_security_settings_are_persisted_and_consulted():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    c51 = (root / 'webapi/cybersecurity51.py').read_text(encoding='utf-8')
    sec = (root / 'webapi/security37.py').read_text(encoding='utf-8')
    assert "@router.put('/settings')" in c51
    assert 'vt_enabled' in c51 and 'nvd_enabled' in c51 and 'remote_https_required' in c51
    assert '_remote_https_required' in sec


def test_mfa_is_removed_from_active_auth_and_ui_surface():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    sec=(root/'webapi/security37.py').read_text(encoding='utf-8')
    main=(root/'webapi/main.py').read_text(encoding='utf-8')
    js=(root/'webapi/static/app.js').read_text(encoding='utf-8')
    assert "PUBLIC = {'/api/health', '/api/auth/login'}" in sec
    assert "@app.post('/api/auth/mfa/verify')" not in main
    assert "mfa-login-form" not in js
    assert "UPDATE web_security_policy51 SET mfa_required=0" in sec


def test_missing_resource_delete_paths_return_404_contracts():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / 'webapi/main.py').read_text(encoding='utf-8')
    assert "server_monitor_targets WHERE id=?" in src and "raise HTTPException(404,'Không tìm thấy target')" in src
    assert "SELECT 1 FROM credentials WHERE id=?" in src and "raise HTTPException(404,'Credential không tồn tại.')" in src
    assert "SELECT 1 FROM snmpv3_credentials WHERE id=?" in src and "raise HTTPException(404,'Credential SNMPv3 không tồn tại.')" in src
    assert "if not cur.rowcount:" in src and "raise HTTPException(404,'Thiết bị chưa được gán credential SNMPv3.')" in src
    assert "SELECT 1 FROM autoip_profiles WHERE name=?" in src and "raise HTTPException(404,'Profile không tồn tại.')" in src


def test_db_read_failures_are_not_silently_reported_as_empty_or_zero():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    main = (root / 'webapi/main.py').read_text(encoding='utf-8')
    c56 = (root / 'webapi/cybersecurity56.py').read_text(encoding='utf-8')
    assert 'SSH_AUDIT_HISTORY_UNAVAILABLE' in main
    assert 'REPORT_DATA_UNAVAILABLE' in main
    assert 'NOTIFICATION_LOG_UNAVAILABLE' in c56
    assert 'invalid_case_due_dates' in c56


def test_case_status_reopen_clears_stale_resolution_timestamps():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / 'webapi/cybersecurity55.py').read_text(encoding='utf-8')
    assert "if status in {'OPEN','INVESTIGATING','CONTAINED'}" in src
    assert 'resolved_at = None' in src and 'closed_at = None' in src
    assert "elif status == 'RESOLVED'" in src and "elif status == 'CLOSED'" in src


def test_process_cleanup_is_scoped_to_current_app_descendants(monkeypatch):
    import desktop_launcher

    calls = []
    class Child:
        def __init__(self, pid): self.pid = pid
        def terminate(self): calls.append(('terminate', self.pid))
        def kill(self): calls.append(('kill', self.pid))
    children = [Child(101), Child(102)]
    class Parent:
        def children(self, recursive=False):
            assert recursive is True
            return children
    fake_psutil = SimpleNamespace(
        Process=lambda pid: Parent(),
        NoSuchProcess=RuntimeError,
        AccessDenied=PermissionError,
        wait_procs=lambda procs, timeout: (procs[:1], procs[1:]),
    )
    monkeypatch.setitem(sys.modules, 'psutil', fake_psutil)
    monkeypatch.setattr(desktop_launcher.os, 'name', 'nt')
    desktop_launcher._terminate_child_processes()
    assert ('terminate', 101) in calls and ('terminate', 102) in calls
    assert ('kill', 102) in calls


def test_process_cleanup_uses_windows_kill_on_job_close_and_never_global_taskkill():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / 'desktop_launcher.py').read_text(encoding='utf-8').lower()
    assert 'job_object_limit_kill_on_job_close' in src
    assert 'assignprocesstojobobject' in src
    assert 'children(recursive=true)' in src
    assert 'taskkill /im cmd.exe' not in src
    assert 'taskkill /im powershell.exe' not in src
