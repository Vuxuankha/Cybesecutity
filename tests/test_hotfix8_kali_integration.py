from pathlib import Path
import pytest
from fastapi import HTTPException

ROOT=Path(__file__).resolve().parents[1]
BACK=(ROOT/'webapi/windows_tools79.py').read_text(encoding='utf-8')
JS=(ROOT/'webapi/static/windows_tools79.js').read_text(encoding='utf-8')
MAIN=(ROOT/'webapi/main.py').read_text(encoding='utf-8')
APP=(ROOT/'webapi/static/app.js').read_text(encoding='utf-8')


def test_windows_local_router_registered_and_kali_removed():
    assert 'windows_tools79_router' in MAIN
    assert "'windows_tools79.js'" in APP
    assert 'kali63_router' not in MAIN
    assert '/api/v1/kali' not in MAIN
    assert not (ROOT/'webapi/kali63.py').exists()
    assert not (ROOT/'webapi/static/kali63.js').exists()


def test_windows_runner_is_profile_whitelisted_and_has_no_arbitrary_shell_field():
    from webapi.windows_tools79 import WindowsToolRunIn, WHITE_PROFILES, RED_PROFILES
    assert 'ping' in WHITE_PROFILES and 'tls_certificate' in WHITE_PROFILES and 'file_hash' in WHITE_PROFILES
    assert 'red_recon' in RED_PROFILES and 'red_cookie_audit' in RED_PROFILES and 'red_light_load' in RED_PROFILES
    fields=set(WindowsToolRunIn.model_fields)
    assert 'command' not in fields and 'script' not in fields and 'args' not in fields
    assert 'UNSUPPORTED_WINDOWS_PROFILE' in BACK
    assert 'arbitrary_shell' in BACK


def test_active_windows_network_targets_are_private_limited(monkeypatch):
    import webapi.windows_tools79 as w
    monkeypatch.setattr(w.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('8.8.8.8',0))])
    with pytest.raises(HTTPException):
        w._private_host('public.example')
    assert w._private_host('127.0.0.1')[1] == '127.0.0.1'


def test_windows_processes_are_hidden_bounded_and_cleanup_tagged():
    assert 'CREATE_NO_WINDOW' in BACK
    assert 'STARTF_USESHOWWINDOW' in BACK
    assert '_MAX_TIMEOUT = 60' in BACK
    assert '_MAX_STDOUT = 256_000' in BACK
    assert "env['NA_CHILD_KIND'] = 'windows-local-tool'" in BACK
    assert '_kill_tree(proc.pid)' in BACK


def test_ui_has_white_and_red_windows_centers_without_kali_credentials():
    assert 'Windows Local Tools / PowerShell Engine' in JS
    assert 'Windows Red-Team Diagnostic Lab' in JS
    assert "pages.wintools79=async" in JS
    assert "pages.redlocal79=async" in JS
    assert '/v1/windows-tools/run' in JS
    for x in ('Kali Host','Kali Port','Kali Username','SSH host key','Nhập cấu hình JSON'):
        assert x not in JS
