from __future__ import annotations

from contextlib import contextmanager
import os
import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException, Request, Response

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _request(host="127.0.0.1", scheme="http"):
    scope = {
        "type": "http", "http_version": "1.1", "method": "POST", "scheme": scheme,
        "path": "/api/auth/login", "raw_path": b"/api/auth/login", "query_string": b"",
        "headers": [(b"host", b"127.0.0.1")], "client": (host, 12345),
        "server": ("127.0.0.1", 80),
    }
    return Request(scope)


def test_health_is_not_ok_until_critical_background_ready(monkeypatch):
    import webapi.main as main
    main._STARTUP_STATE.update({"mode": "warm", "background_ready": False, "background_error": ""})
    r = main.health()
    assert getattr(r, "status_code", None) == 503
    main._STARTUP_STATE["background_ready"] = True
    r = main.health()
    assert r["ok"] is True and r["background_ready"] is True


def test_jobs_schema_is_part_of_warm_start_and_route_defense():
    main = text("webapi/main.py")
    routes = text("webapi/routes37.py")
    assert "ensure_job_tables()" in main
    assert routes.count("ensure_job_tables()") >= 3


def test_runtime_diagnostics_degrade_when_optional_tables_are_missing():
    ops = text("webapi/operations47.py")
    assert "def table_exists(name)" in ops
    assert "if table_exists('web_schedules40') else 0" in ops
    assert "if table_exists('web_ping_runs47') else None" in ops


def test_successful_logins_do_not_consume_bruteforce_budget(tmp_path, monkeypatch):
    import webapi.security37 as security
    from modules.nms_v5 import _hash_password

    db = tmp_path / "auth.db"
    with sqlite3.connect(db) as c:
        c.row_factory = sqlite3.Row
        c.execute("""CREATE TABLE app_users(
            id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT,
            enabled INTEGER, created_at TEXT, updated_at TEXT,
            mfa_enabled INTEGER DEFAULT 0, mfa_secret_enc TEXT, mfa_updated_at TEXT)""")
        c.execute("INSERT INTO app_users VALUES(1,'Admin',?,'Admin',1,'','',0,NULL,NULL)", (_hash_password("pw"),))

    @contextmanager
    def conn():
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback(); raise
        finally:
            c.close()

    monkeypatch.setattr(security, "connection", conn)
    monkeypatch.setenv("NA_MFA_REQUIRED", "0")
    for _ in range(35):
        result = security.login("Admin", "pw", _request(), Response())
        assert result["success"] is True
    with conn() as c:
        assert c.execute("SELECT COUNT(*) FROM web_login_attempts37 WHERE success=0").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM web_login_attempts37 WHERE success=1").fetchone()[0] == 35


def test_loopback_failed_logins_do_not_cross_lock_other_user(tmp_path, monkeypatch):
    import webapi.security37 as security
    from modules.nms_v5 import _hash_password

    db = tmp_path / "auth2.db"
    with sqlite3.connect(db) as c:
        c.row_factory = sqlite3.Row
        c.execute("""CREATE TABLE app_users(
            id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT,
            enabled INTEGER, created_at TEXT, updated_at TEXT,
            mfa_enabled INTEGER DEFAULT 0, mfa_secret_enc TEXT, mfa_updated_at TEXT)""")
        c.execute("INSERT INTO app_users VALUES(1,'Admin',?,'Admin',1,'','',0,NULL,NULL)", (_hash_password("pw"),))
        c.execute("INSERT INTO app_users VALUES(2,'Viewer',?,'Viewer',1,'','',0,NULL,NULL)", (_hash_password("pw2"),))

    @contextmanager
    def conn():
        c = sqlite3.connect(db); c.row_factory = sqlite3.Row
        try: yield c; c.commit()
        except Exception: c.rollback(); raise
        finally: c.close()

    monkeypatch.setattr(security, "connection", conn)
    monkeypatch.setenv("NA_MFA_REQUIRED", "0")
    for _ in range(5):
        with pytest.raises(HTTPException) as exc:
            security.login("Admin", "wrong", _request(), Response())
        assert exc.value.status_code == 401
    # A different local account is still allowed; loopback is not a shared IP lock bucket.
    assert security.login("Viewer", "pw2", _request(), Response())["success"] is True
    with pytest.raises(HTTPException) as exc:
        security.login("Admin", "wrong", _request(), Response())
    assert exc.value.status_code == 429
    assert 1 <= int(exc.value.headers["Retry-After"]) <= 900


def test_disabled_only_install_enters_admin_repair(tmp_path, monkeypatch):
    import desktop_launcher
    import app_runtime

    dbdir = tmp_path / "database"; dbdir.mkdir()
    db = dbdir / "network_automation.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE app_users(id INTEGER PRIMARY KEY,username TEXT,role TEXT,enabled INTEGER)")
        c.execute("INSERT INTO app_users VALUES(1,'OldAdmin','Admin',0)")
    monkeypatch.setattr(app_runtime, "DATABASE_DIR", dbdir)
    assert desktop_launcher._fast_existing_user() is False
    with sqlite3.connect(db) as c:
        c.execute("UPDATE app_users SET enabled=1 WHERE id=1")
    assert desktop_launcher._fast_existing_user() is True


def test_launcher_reserves_socket_and_verifies_exact_backend_identity():
    src = text("desktop_launcher.py")
    assert "def _reserve_port()" in src
    assert "server.run(sockets=[reserved_socket])" in src
    assert 'payload.get("service")=="networkautomation-desktop"' in src
    assert 'payload.get("ui_version")=="7.0.3"' in src
    assert 'payload.get("instance")==expected_instance' in src
    assert "background_ready" in src


def test_frontend_keeps_authenticated_session_when_feature_asset_fails():
    app = text("webapi/static/app.js")
    assert "state.assetsReady" in app
    assert "Phiên đăng nhập vẫn còn hiệu lực" in app
    assert "'assets-retry'" in app
    logged = app.split("async function loggedIn()", 1)[1].split("\npages.dashboard", 1)[0]
    assert "showLogin()" not in logged
    assert "Đang tải các chức năng" in logged


def test_asset_retry_can_recover_failed_elements_and_checks_final_overlays():
    app = text("webapi/static/app.js")
    assert "if(old)old.remove()" in app
    assert "['hotfix10_nav_core.js',()=>typeof window.naHotfix10==='object']" in app
    assert "['desktop70.js',()=>window.__NA_DESKTOP70_LOADED__===true]" in app
    assert "state.assetsReady=missing.length===0" in app


def test_role_change_resets_inaccessible_page_and_logout_resets_dashboard():
    app = text("webapi/static/app.js")
    assert "pageVisibleForRole(state.page)" in app
    assert "state.page='dashboard'" in app
    assert "adminOnlyPages" in app and "opsOnlyPages" in app


def test_dashboard_is_partial_failure_tolerant():
    app = text("webapi/static/app.js")
    d70 = text("webapi/static/desktop70.js")
    dashboard = app.split("pages.dashboard=async()=>", 1)[1].split("const deviceCols", 1)[0]
    assert "Promise.allSettled" in dashboard
    assert "Dữ liệu một phần" in dashboard
    assert "Dashboard chính vẫn hoạt động" in d70


def test_viewer_does_not_trigger_native_ping_and_probe_is_bounded(monkeypatch):
    import webapi.desktop70 as d70
    import webapi.platform50 as p50
    import webapi.autodiscovery5010 as ad

    monkeypatch.setattr(d70, "_desktop_only", lambda: None)
    monkeypatch.setattr(p50, "network_connectivity", lambda force=True: {
        "wan": True, "lan": True,
        "adapters": [{"name":"Ethernet","description":"NIC","ipv4":["192.168.1.10"],
                      "networks":["192.168.1.10/24"],"metric":1,"gateway":"192.168.1.1"}],
    })
    neighbors = {f"192.168.1.{i}": f"00-00-00-00-00-{i%100:02d}" for i in range(1, 201)}
    monkeypatch.setattr(ad, "_arp_neighbors", lambda network: neighbors)
    seen = {}
    def fake_probe(addresses, timeout_ms=450):
        seen["count"] = len(addresses)
        return {}
    monkeypatch.setattr(d70, "_probe_neighbors", fake_probe)
    monkeypatch.setattr(d70, "icmp_ping", lambda *a, **k: {})
    d70._CACHE.update({"at":0.0,"probe":False,"data":None})
    result = d70.network_overview_data(probe=True, force=True)
    assert seen["count"] == 128
    assert result["probe_truncated"] is True and result["probe_limit"] == 128
    js = text("webapi/static/desktop70.js")
    assert "native70(canWrite(),false)" in js
    assert "native70(canWrite(),true)" in js


def test_probe_gets_disable_automatic_retry_and_health_is_single_flight():
    app = text("webapi/static/app.js")
    d70 = text("webapi/static/desktop70.js")
    kali = text("webapi/static/kali63.js")
    assert "options.retry!==false" in app
    assert "network-overview" in d70 and "{retry:false}" in d70
    assert "hostkey/'+v.device_id" in app and "{retry:false}" in app
    assert "probe-hostkey" in kali and "{retry:false}" in kali
    assert "let naHealthPromise=null" in app
    assert "if(naHealthPromise)return naHealthPromise" in app


def test_operational_asset_loader_parallelizes_only_independent_modules():
    app = text("webapi/static/app.js")
    assert "Promise.all(['workbench45.js','vendor/xterm.js'].map(naLoadScript))" in app
    assert "Promise.all(['operations47.js','operations50.js','cybersecurity51.js','enterprise592.js'].map(naLoadScript))" in app
    # Dependent security overlays remain ordered.
    assert app.index("naLoadScript('security_modes61.js')") < app.index("naLoadScript('security_catalog62.js')") < app.index("naLoadScript('hotfix9_kali_red.js')")
