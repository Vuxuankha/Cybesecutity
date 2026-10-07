from pathlib import Path
import os

import pytest

ROOT=Path(__file__).resolve().parents[1]

def text(rel):
    return (ROOT/rel).read_text(encoding='utf-8')


def test_portable_runtime_data_used_in_source_and_frozen_logic():
    runtime=text('app_runtime.py')
    launcher=text('desktop_launcher.py')
    assert "candidates.append(install_root() / 'runtime_data')" in runtime
    assert 'Path(sys.executable).resolve().parent / "runtime_data"' in launcher
    assert 'network_automation.db' in runtime and '.credential.key' in runtime and 'known_hosts' in runtime


def test_fresh_start_prepares_known_hosts_and_encryption_key_safely():
    launcher=text('desktop_launcher.py')
    assert 'def _ensure_local_security_files' in launcher
    assert "known.touch(exist_ok=True)" in launcher
    assert '_fernet(allow_create=True)' in launcher
    assert 'Mất khóa .credential.key nhưng database còn dữ liệu mã hóa' in text('modules/nms_v5.py')


def test_readiness_displays_text_status_for_known_hosts_and_key():
    back=text('webapi/terminal46.py')
    ui=text('webapi/static/terminal46.js')
    assert "'known_hosts_status':'Sẵn sàng'" in back
    assert "'credential_key_status':'Sẵn sàng'" in back
    assert 'r.known_hosts_status' in ui
    assert 'r.credential_key_status' in ui


def test_csv_export_is_server_persisted_and_excel_returns_saved_path(tmp_path, monkeypatch):
    import webapi.reports37 as reports
    monkeypatch.setattr('app_runtime.REPORT_DIR', tmp_path)
    monkeypatch.setattr(reports, 'register', lambda path,owner_id,kind:{'success':True,'name':path.name,'saved_path':str(path),'download_url':'/api/downloads/t'})
    r=reports.save_csv(1,'demo.csv','A,B\r\n1,2')
    path=Path(r['saved_path'])
    assert path.is_file()
    assert path.read_text(encoding='utf-8-sig').startswith('A,B')
    src=text('webapi/reports37.py')
    assert "'saved_relative_path': _relative_display(path)" in src


def test_ui_exports_use_backend_persistence_not_blob_only():
    wb=text('webapi/static/workbench45.js')
    app=text('webapi/static/app.js')
    cyber=text('webapi/static/cybersecurity51.js')
    assert "'/reports/xlsx':'/reports/csv'" in wb and "destination_token:picked.token" in wb
    assert "button('Xuất Excel...','export-excel37'" in app and 'chooseExportDirectory' in app
    assert "api('/reports/export',{method:'POST'" in app
    assert "security_snapshot_" in cyber and "'/reports/xlsx':'/reports/csv'" in cyber


def test_product_center_is_vietnamese_and_status_codes_are_translated():
    app=text('webapi/static/app.js')
    wb=text('webapi/static/workbench45.js')
    assert "production:'Trung tâm vận hành hệ thống'" in app
    assert "panel('Tự kiểm tra vận hành'" in app
    assert "x.detail_vi||x.detail" in app
    assert "'detail_vi': 'Cơ sở dữ liệu hoạt động bình thường'" in text('webapi/ops41.py')
    assert "PASS:'Đạt'" in wb and "WARN:'Cảnh báo'" in wb and "FAIL:'Lỗi'" in wb


def test_clock_updates_every_second_without_page_refresh():
    app=text('webapi/static/app.js')
    assert 'function renderLiveClock()' in app
    assert 'setInterval(renderLiveClock,1000)' in app
    assert "window.naLocale?window.naLocale():'vi-VN'" in app
    assert "new Intl.DateTimeFormat(loc" in app


def test_password_login_policy_is_nonempty_only():
    from modules.accounts import validate_password
    validate_password('1')
    validate_password('a')
    with pytest.raises(ValueError):
        validate_password('')


def test_mfa_removed_from_routes_login_and_vault_step_up():
    main=text('webapi/main.py')
    sec=text('webapi/security37.py')
    c51=text('webapi/cybersecurity51.py')
    ui=text('webapi/static/cybersecurity51.js')
    assert "@app.post('/api/auth/mfa/verify')" not in main
    assert "r'/api/auth/mfa/verify'" not in sec
    assert "@router.get('/auth/mfa/status')" not in c51
    assert '_vault_mfa_ok' not in c51
    assert "mfa-login-form" not in ui


def test_windows_local_tools_replace_kali_for_white_and_red_hat():
    js=text('webapi/static/windows_tools79.js')
    nav=text('webapi/static/hotfix10_nav_core.js')
    main=text('webapi/main.py')
    assert 'Windows Local Tools / PowerShell Engine' in js
    assert 'Windows Red-Team Diagnostic Lab' in js
    assert '/v1/windows-tools/run' in js
    assert 'wintools79' in nav and 'redlocal79' in nav
    assert 'kali63' not in nav and 'kaliconfig63' not in nav
    assert 'webapi.kali63' not in main
