from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_launcher_paints_native_window_before_backend_is_ready():
    source = text("desktop_launcher.py")
    body = source.split("def _run_desktop_window", 1)[1].split("def main", 1)[0]
    assert "html=_startup_splash_html()" in body
    assert "webview.start(_bootstrap, debug=False)" in body
    # Server startup lives inside the callback that is run after the WebView is visible.
    callback = body.split("def _bootstrap()", 1)[1]
    assert "_start_server(port, reserved_socket)" in callback
    assert "window.load_url(url)" in callback


def test_existing_user_check_is_read_only_and_avoids_full_schema_imports():
    source = text("desktop_launcher.py")
    fast = source.split("def _fast_existing_user", 1)[1].split("def _first_run_admin", 1)[0]
    assert "?mode=ro" in fast
    assert "SELECT 1 FROM app_users" in fast
    first = source.split("def _first_run_admin", 1)[1].split("def _pick_port", 1)[0]
    assert first.index("if _fast_existing_user():") < first.index("from modules.nms_v5 import")


def test_source_bootstrap_has_validated_venv_fast_path():
    core = text("_internal/launcher/START_DESKTOP_CORE.bat")
    assert ".na_ready_70393" in core
    assert "current-7.0.3.txt" in core
    assert "goto RUNAPP_FAST" in core
    fast = core.split(":RUNAPP_FAST", 1)[1].split(":RUNAPP", 1)[0]
    assert "py -3.13" not in fast
    assert "import fastapi,uvicorn,webview,pandas" not in fast


def test_pyinstaller_disables_upx_for_faster_cold_start():
    spec = text("NetworkAutomationDesktop.spec")
    assert spec.count("upx=False") >= 2
    assert "upx=True" not in spec


def test_current_schema_marker_uses_warm_path_without_full_migration(tmp_path, monkeypatch):
    import webapi.main as main

    db = tmp_path / "network_automation.db"
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE app_users(id INTEGER PRIMARY KEY, mfa_enabled INTEGER, mfa_secret_enc TEXT, mfa_updated_at TEXT)")

    marker = tmp_path / ".desktop_migration_37.json"
    marker.write_text(json.dumps({
        "ui_version": main.UI_VERSION,
        "release": main.RELEASE,
        "asset_version": main.ASSET_VERSION,
    }), encoding="utf-8")

    monkeypatch.setattr(main, "DATABASE_DIR", tmp_path)
    monkeypatch.setattr(main, "DB_PATH", db)
    monkeypatch.setattr(main.security37, "ensure_tables", lambda: None)
    monkeypatch.setattr(main, "_full_schema_startup", lambda: (_ for _ in ()).throw(AssertionError("cold migration called")))

    assert main._prepare_schema_fast() == "warm"
