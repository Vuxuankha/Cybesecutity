from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]


def text(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def test_qa79_no_active_kali_router_assets_or_migration():
    assert not (ROOT/'webapi/kali63.py').exists()
    assert not (ROOT/'webapi/static/kali63.js').exists()
    assert not (ROOT/'webapi/static/hotfix9_kali_red.js').exists()
    joined='\n'.join(text(x) for x in ['webapi/main.py','webapi/security37.py','webapi/static/app.js','app_runtime.py'])
    assert '/api/v1/kali' not in joined
    assert 'kali_integration.json' not in text('app_runtime.py')


def test_qa79_request_model_forbids_arbitrary_command_fields_and_caps_load_count():
    from webapi.windows_tools79 import WindowsToolRunIn
    with pytest.raises(ValidationError):
        WindowsToolRunIn(mode='white', profile='ping', target='127.0.0.1', command='whoami')
    with pytest.raises(ValidationError):
        WindowsToolRunIn(mode='red', profile='red_light_load', target='http://127.0.0.1/', count=6)
    WindowsToolRunIn(mode='red', profile='red_light_load', target='http://127.0.0.1/', count=5)


def test_qa79_profile_mode_separation_is_enforced(monkeypatch):
    import webapi.windows_tools79 as w
    monkeypatch.setattr(w, 'require_role', lambda *a, **k: {'role':'Admin'})
    monkeypatch.setattr(w, '_run_ps', lambda script, timeout=25: {'ok':True,'exit_code':0,'stdout':'ok','stderr':'','elapsed_ms':1,'backend':'windows-local'})
    req=SimpleNamespace()
    with pytest.raises(HTTPException) as exc:
        w.run_profile(w.WindowsToolRunIn(mode='red', profile='ping', target='127.0.0.1'), req)
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException):
        w.run_profile(w.WindowsToolRunIn(mode='white', profile='red_recon', target='127.0.0.1'), req)


def test_qa79_private_target_validation_blocks_public_network_activity(monkeypatch):
    import webapi.windows_tools79 as w
    with pytest.raises(HTTPException):
        w._private_host('8.8.8.8')
    monkeypatch.setattr(w.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('8.8.8.8',0))])
    with pytest.raises(HTTPException):
        w._private_url('https://public.example/')
    assert w._private_host('127.0.0.1')[1]=='127.0.0.1'


def test_qa79_http_profiles_pin_private_resolution_and_do_not_disable_tls_validation(monkeypatch):
    import webapi.windows_tools79 as w
    monkeypatch.setattr(w, '_private_url', lambda x: ('https://srv.local/','srv.local',443,'192.168.1.10'))
    body=w.WindowsToolRunIn(mode='white',profile='http_head',target='https://srv.local/')
    script,timeout,engine=w._profile_script('http_head',body)
    assert '--resolve' in script and 'srv.local:443:192.168.1.10' in script
    assert ' -k' not in script and '--insecure' not in script
    assert timeout <= 15 and 'curl.exe' in script


def test_qa79_tls_profile_reports_certificate_policy_errors(monkeypatch):
    import webapi.windows_tools79 as w
    monkeypatch.setattr(w, '_private_host', lambda x: ('srv.local','192.168.1.10'))
    body=w.WindowsToolRunIn(mode='white',profile='tls_certificate',target='srv.local',port=443)
    script,timeout,_=w._profile_script('tls_certificate',body)
    assert 'PolicyErrors' in script
    assert "if($script:policyErrors -ne 'None'){exit 2}" in script
    assert 'AuthenticateAsClient' in script
    assert timeout <= 20


def test_qa79_red_configuration_and_load_profiles_are_readonly_or_tightly_bounded(monkeypatch):
    import webapi.windows_tools79 as w
    body=w.WindowsToolRunIn(mode='red',profile='red_config_audit')
    script,_,_=w._profile_script('red_config_audit',body)
    assert 'Get-NetFirewallProfile' in script and 'Get-ExecutionPolicy' in script
    assert 'Set-' not in script and 'Remove-' not in script and 'New-' not in script
    monkeypatch.setattr(w, '_private_url', lambda x: ('https://srv.local/','srv.local',443,'192.168.1.10'))
    body=w.WindowsToolRunIn(mode='red',profile='red_light_load',target='https://srv.local/',count=5)
    script,_,_=w._profile_script('red_light_load',body)
    assert '$n=5' in script and 'Start-Sleep -Milliseconds 250' in script
    assert '--head' in script and '--output NUL' in script


def test_qa79_runner_has_hidden_window_timeout_output_caps_and_process_cleanup():
    src=text('webapi/windows_tools79.py')
    assert 'CREATE_NO_WINDOW' in src and 'STARTF_USESHOWWINDOW' in src
    assert '_MAX_TIMEOUT = 60' in src and '_MAX_STDOUT = 256_000' in src and '_MAX_STDERR = 64_000' in src
    assert "env['NA_CHILD_KIND'] = 'windows-local-tool'" in src
    assert '_kill_tree(proc.pid)' in src
    assert 'shell=True' not in src


def test_qa79_ui_surfaces_windows_tools_in_both_hats_and_attaches_relevant_actions():
    js=text('webapi/static/windows_tools79.js')
    nav=text('webapi/static/hotfix10_nav_core.js')
    catalog=text('webapi/static/security_catalog62.js')
    assert 'wintools79' in nav and 'redlocal79' in nav
    assert 'Windows Local Tools / PowerShell Engine' in js
    assert 'Windows Red-Team Diagnostic Lab' in js
    for page in ('bluetls62','blueweb61','bluefirewall62','bluelog61','bluefim62','redpacket61','redsession62','redmitm62','redload61'):
        assert f"appendTool('{page}'" in js
    assert "['▣','Windows Local Tools'" in catalog and "['▤','Windows Local Lab'" in catalog
