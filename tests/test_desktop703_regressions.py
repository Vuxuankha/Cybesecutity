from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_ui_health_check_uses_current_release_constants():
    js = text("webapi/static/operations47.js")
    assert "r.ui_version!==NA_UI_VERSION" in js
    assert "r.release!==NA_RELEASE" in js
    assert "ui_version!=='6.9.0'" not in js
    assert "state.uiReady=true" in js


def test_live_off_is_honored_by_all_periodic_desktop_refreshers():
    d70 = text("webapi/static/desktop70.js")
    ops50 = text("webapi/static/operations50.js")
    ent = text("webapi/static/enterprise592.js")
    assert "state.user&&state.live&&document.visibilityState==='visible'" in d70
    assert "state.user&&state.live&&document.visibilityState==='visible'" in ops50
    assert ent.count("state.user&&state.live&&document.visibilityState==='visible'") >= 2
    workbench = text("webapi/static/workbench45.js")
    assert "__naIpMac624Timer" in workbench and "state.user&&state.live&&state.page==='ipmac'" in workbench


def test_presence_refresh_is_csp_safe():
    ent = text("webapi/static/enterprise592.js")
    assert 'onclick="void e592refreshPresence()"' not in ent
    assert 'data-action="e592-presence-refresh"' in ent
    assert "actions['e592-presence-refresh']" in ent


def test_legacy_overlays_do_not_overwrite_visible_ui_with_690():
    for rel in ["webapi/static/enterprise592.js", "webapi/static/enterprise600.js", "webapi/static/hotfix10_nav_core.js"]:
        js = text(rel)
        assert "brand.textContent='Cybersecurity Platform / UI 6.9.0'" not in js
        assert "sub.textContent='Cybersecurity Platform / UI 6.9.0" not in js


def test_multi_ip_adapter_prefers_subnet_containing_default_gateway():
    from webapi.platform50 import _primary_identity_from_connectivity

    result = {
        "adapters": [{
            "name": "Ethernet",
            "description": "NIC",
            "ipv4": ["10.10.0.5", "192.168.1.100"],
            "networks": ["10.10.0.5/24", "192.168.1.100/24"],
            "metric": 5,
            "gateway": "192.168.1.1",
        }]
    }
    ident = _primary_identity_from_connectivity(result)
    assert ident["ipv4"] == "192.168.1.100"
    assert ident["network"] == "192.168.1.0/24"
    assert ident["gateway"] == "192.168.1.1"


def test_portable_migration_does_not_mark_complete_after_copy_failure(tmp_path, monkeypatch):
    import app_runtime

    install = tmp_path / "install"
    legacy = install / "database"
    legacy.mkdir(parents=True)
    (legacy / "network_automation.db").write_bytes(b"legacy")
    data = tmp_path / "data"
    database = data / "database"
    database.mkdir(parents=True)

    monkeypatch.setattr(app_runtime, "is_frozen", lambda: True)
    monkeypatch.setattr(app_runtime, "install_root", lambda: install)
    monkeypatch.setattr(app_runtime, "DATA_DIR", data)
    monkeypatch.setattr(app_runtime, "DATABASE_DIR", database)

    def fail_copy(*_args, **_kwargs):
        raise OSError("locked")

    monkeypatch.setattr(app_runtime.shutil, "copy2", fail_copy)
    try:
        app_runtime.migrate_portable_data_once()
    except OSError:
        pass
    else:
        raise AssertionError("copy failure must propagate")
    assert not (data / ".portable_migration_checked").exists()


def test_migration_legacy_marker_is_upgraded_to_canonical_marker(tmp_path, monkeypatch):
    import app_runtime
    import database.db as dbmod
    from webapi import runtime37

    dbdir = tmp_path / "database"
    dbdir.mkdir()
    db = dbdir / "network_automation.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE devices(id INTEGER PRIMARY KEY)")
    legacy = dbdir / ".desktop_migration.json"
    legacy.write_text(json.dumps({"backup": "legacy-backup.db", "version": "old"}), encoding="utf-8")

    monkeypatch.setattr(app_runtime, "DATABASE_DIR", dbdir)
    monkeypatch.setattr(dbmod, "DB_PATH", db)
    assert runtime37.preflight() is None
    marker = runtime37.mark_migration_complete(None)
    assert marker.name == ".desktop_migration_37.json"
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload["ui_version"] == "7.0.3"
    assert payload["backup"] == "legacy-backup.db"


def test_ping_upper_bound_is_preserved_in_desktop_api(monkeypatch):
    import webapi.desktop70 as d70
    import webapi.platform50 as p50
    import webapi.autodiscovery5010 as ad

    monkeypatch.setattr(d70, "_desktop_only", lambda: None)
    monkeypatch.setattr(p50, "network_connectivity", lambda force=True: {
        "wan": True, "lan": True,
        "adapters": [{"name": "Ethernet", "description": "NIC", "ipv4": ["192.168.1.10"],
                      "networks": ["192.168.1.10/24"], "metric": 10, "gateway": "192.168.1.1"}],
    })
    monkeypatch.setattr(ad, "_arp_neighbors", lambda network: {"192.168.1.2": "AA-BB-CC-DD-EE-FF"})
    monkeypatch.setattr(d70, "_probe_neighbors", lambda addresses, timeout_ms=450: {
        "192.168.1.2": {"status": "Online", "response": 1.0, "response_is_upper_bound": True,
                         "packet_loss": 0.0, "error": ""}
    })
    monkeypatch.setattr(d70, "icmp_ping", lambda *a, **k: {"status": "Online", "response": 1.0,
                                                            "response_is_upper_bound": True, "packet_loss": 0.0})
    d70._CACHE.update({"at": 0.0, "probe": False, "data": None})
    data = d70.network_overview_data(probe=True, force=True)
    assert data["devices"][0]["latency_is_upper_bound"] is True
    assert data["gateway_ping"]["response_is_upper_bound"] is True


def test_build_uses_dev_requirements_and_supported_python_only():
    build = text("BUILD_WINDOWS.bat")
    workflow = text(".github/workflows/windows-desktop-release.yml")
    source = text("_internal/launcher/START_DESKTOP_CORE.bat")
    assert "requirements-dev.txt" in build and "requirements-dev.txt" in workflow
    assert "py -3.13" in build and "py -3.12" in build and "py -3.11" in build
    assert "py -3.13" in source and "py -3.12" in source and "py -3.11" in source
    assert "Python313\\python.exe" in source and "Python312\\python.exe" in source
    assert "py -3 -m venv" not in build and "py -3 -c" not in source
    assert (ROOT / "requirements-lock.txt").is_file()
    assert (ROOT / "requirements-dev.txt").is_file()


def test_webview2_preflight_is_present():
    launcher = text("desktop_launcher.py")
    assert "F3017226-FE2A-4295-8BDF-00C3A9A7E4C5" in launcher
    assert "_ensure_webview2_runtime()" in launcher
    assert "Thiếu Microsoft Edge WebView2 Runtime" in launcher


def test_only_one_auth_stack_is_shipped():
    assert (ROOT / "webapi/security37.py").is_file()
    assert not (ROOT / "webapi/core/security.py").exists()
    assert not (ROOT / "webapi/routers/auth.py").exists()

def test_hidden_launcher_explains_error_11_and_can_offer_python_install():
    vbs = text("MO_APP_NETWORKAUTOMATION.vbs")
    assert "If rc = 11 Then" in vbs
    assert "Python.Python.3.12" in vbs
    assert "vbYesNo + vbQuestion" in vbs
    assert "winget install" in vbs
    assert "_internal\\launcher\\START_DESKTOP_CORE.bat" in vbs


def test_source_bootstrap_logs_selected_python_and_has_actionable_exit_codes():
    source = text("_internal/launcher/START_DESKTOP_CORE.bat")
    assert "Using Python:" in source
    assert "exit /b 11" in source
    assert "exit /b 12" in source
    assert "exit /b 13" in source
    assert "exit /b 14" in source
    assert "exit /b 15" in source
    assert "exit /b 16" in source

def test_source_bootstrap_never_deletes_locked_virtualenv():
    source = text("_internal/launcher/START_DESKTOP_CORE.bat")
    assert 'import fastapi,uvicorn,webview,pandas,openpyxl' in source
    assert 'Existing versioned environment is incomplete; keeping it untouched' in source
    assert 'rmdir /s /q' not in source.lower()
    assert '%LOCALAPPDATA%\\NetworkAutomation\\venvs' in source
    assert '-repair-%RANDOM%-%RANDOM%' in source

def test_user_facing_source_launcher_is_vbs_only():
    assert (ROOT / "00_MO_APP_NETWORKAUTOMATION.vbs").is_file()
    assert (ROOT / "MO_APP_NETWORKAUTOMATION.vbs").is_file()
    assert not (ROOT / "START_DESKTOP_7.bat").exists()
    assert not (ROOT / "START_DESKTOP_CORE.bat").exists()
    assert (ROOT / "_internal/launcher/START_DESKTOP_CORE.bat").is_file()



def test_static_assets_use_new_revision_and_no_immutable_cache():
    app = text("webapi/static/app.js")
    index = text("webapi/static/index.html")
    security = text("webapi/security37.py")
    runtime = text("webapi/runtime37.py")
    assert "NA_ASSET_VERSION='70405'" in app
    assert "/static/app.js?v=70405" in index
    assert "/static/style.css?v=70405" in index
    assert "ASSET_VERSION='70405'" in runtime
    assert "max-age=31536000, immutable" not in security
    assert "no-store, max-age=0" in security


def test_health_contract_detects_stale_asset_bundle():
    main = text("webapi/main.py")
    ops = text("webapi/static/operations47.js")
    assert "'asset_version':ASSET_VERSION" in main
    assert "r.asset_version!==NA_ASSET_VERSION" in ops


def test_unknown_ui_actions_are_not_silent_and_line_optimize_is_wired():
    app = text("webapi/static/app.js")
    cyber = text("webapi/static/cybersecurity51.js")
    assert "NA_UNKNOWN_ACTION" in app
    assert "NA_UNKNOWN_FORM" in app
    assert "actions['line-optimize59']" in cyber
    assert "'/v59/network/optimize'" in cyber
    assert "confirm_system_change:true" in cyber


def test_initial_login_bundle_is_password_only_without_mfa_flow():
    app = text("webapi/static/app.js")
    main = text("webapi/main.py")
    assert "'mfa-login-form':async" not in app
    assert "r.mfa_enroll_required" not in app
    assert "r.mfa_required" not in app
    assert "'/auth/mfa/verify'" not in app
    assert "@app.post('/api/auth/mfa/verify')" not in main
