"""NetworkAutomation Desktop 7.0.3 launcher.

Runs the internal local UI engine on Windows and embeds it in a desktop window.
The backend binds only to 127.0.0.1, so network operations execute on this PC.

Fast-start design:
- Existing local users are detected with one read-only SQLite query; expensive schema
  imports are only used for true first-run setup.
- The WebView window is created immediately with a tiny local splash while the local
  FastAPI service starts in a background thread.
- On a current database schema the backend performs only a minimal auth/table sanity
  check before serving; background workers warm up after the UI is available.
"""
from __future__ import annotations

import html
import os
import socket
import sqlite3
import sys
import threading
import time
import urllib.request
import json
import secrets
from pathlib import Path

APP_TITLE = "NetworkAutomation Desktop 7.0.3"

WEBVIEW2_CLIENT_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def _webview2_runtime_version() -> str:
    """Return installed Evergreen WebView2 Runtime version on Windows, if present."""
    if os.name != "nt":
        return "non-windows"
    try:
        import winreg
    except Exception:
        return ""
    paths = [
        rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_GUID}",
        rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{WEBVIEW2_CLIENT_GUID}",
    ]
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for key_path in paths:
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    version = str(winreg.QueryValueEx(key, "pv")[0] or "").strip()
                if version and version != "0.0.0.0":
                    return version
            except OSError:
                continue
    return ""


def _ensure_webview2_runtime() -> str:
    version = _webview2_runtime_version()
    if os.name == "nt" and not version:
        raise RuntimeError(
            "Thiếu Microsoft Edge WebView2 Runtime. Hãy cài WebView2 Runtime (Evergreen), "
            "sau đó mở lại NetworkAutomation Desktop."
        )
    return version


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _resource_root() -> Path:
    if _is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def _configure_environment() -> None:
    # Source runs keep runtime data outside tracked source. Frozen builds let
    # app_runtime choose %LOCALAPPDATA%\NetworkAutomation automatically.
    if not _is_frozen():
        os.environ.setdefault("NETWORK_AUTOMATION_DATA_DIR", str(_resource_root() / "runtime_data"))
    os.environ["NA_DESKTOP_APP"] = "1"
    # Unique per process so a stale/unrelated localhost service can never satisfy health.
    os.environ["NA_INSTANCE_TOKEN"] = "desktop-" + secrets.token_hex(12)
    os.environ["NA_RUN_MODE"] = "desktop"
    os.environ["NA_ALLOWED_HOSTS"] = "127.0.0.1,localhost"
    os.environ["NA_ALLOW_EMPTY_DB"] = "1"
    os.environ["NA_MFA_REQUIRED"] = "0"
    os.environ["NA_DISABLE_MFA"] = "1"
    os.environ["NA_ENABLE_AUTOIP"] = "1"
    os.environ.setdefault("NA_TIMEZONE", "Asia/Ho_Chi_Minh")


def _single_instance() -> object | None:
    if os.name != "nt":
        return object()
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, "Local\\NetworkAutomationDesktop7")
    if not handle:
        return None
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return None
    return handle


def _show_error(title: str, message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror(title, message, parent=root)
        root.destroy()
    except Exception:
        pass


def _fast_existing_user() -> bool:
    """Cheap warm-start check that avoids importing the legacy NMS schema stack.

    This function is intentionally read-only. If anything looks unusual we fall back
    to the full first-run path, which performs all normal migrations/validation.
    """
    try:
        from app_runtime import DATABASE_DIR
        db_path = Path(DATABASE_DIR) / "network_automation.db"
        if not db_path.is_file() or db_path.stat().st_size <= 0:
            return False
        uri = db_path.resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=0.5) as conn:
            table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='app_users'"
            ).fetchone()
            if not table:
                return False
            # A usable installation must have an enabled Admin. Enabled viewers or
            # disabled historical accounts cannot repair account access themselves.
            return conn.execute("SELECT 1 FROM app_users WHERE role='Admin' AND enabled=1 LIMIT 1").fetchone() is not None
    except Exception:
        return False


def _first_run_admin() -> bool:
    """Create the first local Admin without any hard-coded password."""
    if _fast_existing_user():
        return True

    # Heavy imports are deliberately delayed until a real first-run/repair case.
    from database.db import init_database, get_connection
    from modules.nms_v5 import ensure_v5_tables, _hash_password
    from modules import accounts
    from webapi.runtime37 import utcnow

    init_database(); ensure_v5_tables()
    with get_connection() as c:
        count = int(c.execute("SELECT COUNT(*) FROM app_users").fetchone()[0])
        active_admin = c.execute("SELECT 1 FROM app_users WHERE role='Admin' AND enabled=1 LIMIT 1").fetchone()
    if active_admin:
        return True

    import tkinter as tk
    from tkinter import ttk, messagebox

    result = {"ok": False}
    root = tk.Tk()
    root.title("Thiết lập NetworkAutomation Desktop 7.0.3")
    root.resizable(False, False)
    try:
        root.iconname("NetworkAutomation")
    except Exception:
        pass

    frame = ttk.Frame(root, padding=22)
    frame.grid(row=0, column=0, sticky="nsew")
    heading = "Tạo tài khoản quản trị đầu tiên" if count == 0 else "Khôi phục quyền quản trị cục bộ"
    detail = "Tài khoản này chỉ được lưu trong dữ liệu cục bộ của máy." if count == 0 else "Không còn Admin đang hoạt động. Có thể kích hoạt lại Admin cũ hoặc tạo Admin mới; dữ liệu khác được giữ nguyên."
    ttk.Label(frame, text=heading, font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
    ttk.Label(frame, text=detail, wraplength=470).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 14))

    username = tk.StringVar(value="Admin")
    password = tk.StringVar()
    confirm = tk.StringVar()
    fields = [("Tài khoản", username, False), ("Mật khẩu", password, True), ("Nhập lại mật khẩu", confirm, True)]
    entries=[]
    for idx,(label,var,secret) in enumerate(fields, start=2):
        ttk.Label(frame, text=label).grid(row=idx, column=0, sticky="w", padx=(0, 12), pady=6)
        e=ttk.Entry(frame, textvariable=var, width=34, show="*" if secret else "")
        e.grid(row=idx, column=1, sticky="ew", pady=6); entries.append(e)

    def create_admin():
        u=username.get().strip(); p=password.get(); q=confirm.get()
        if p != q:
            messagebox.showwarning("Thiết lập", "Mật khẩu xác nhận không khớp.", parent=root); return
        if p == "":
            messagebox.showwarning("Thiết lập", "Mật khẩu không được để trống.", parent=root); return
        try:
            accounts._validate(u, "Admin", p)
        except ValueError as exc:
            messagebox.showwarning("Thiết lập", str(exc), parent=root); return
        stamp=utcnow()
        with get_connection() as c:
            existing=c.execute("SELECT id,role,enabled FROM app_users WHERE username=? COLLATE NOCASE ORDER BY id",(u,)).fetchall()
            if len(existing)>1:
                messagebox.showwarning("Thiết lập", "Tên đăng nhập đang bị trùng trong dữ liệu cũ. Hãy chọn tên Admin mới.", parent=root); return
            if existing:
                row=existing[0]
                if row['role']!='Admin':
                    messagebox.showwarning("Thiết lập", "Tên này đang thuộc tài khoản không phải Admin. Hãy chọn tên khác.", parent=root); return
                c.execute("UPDATE app_users SET password_hash=?,enabled=1,updated_at=? WHERE id=?",(_hash_password(p),stamp,row['id']))
            else:
                c.execute("INSERT INTO app_users(username,password_hash,role,enabled,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                          (u,_hash_password(p),"Admin",1,stamp,stamp))
            c.commit()
        result["ok"]=True
        root.destroy()

    buttons=ttk.Frame(frame); buttons.grid(row=5,column=0,columnspan=2,sticky="e",pady=(16,0))
    ttk.Button(buttons,text="Thoát",command=root.destroy).pack(side="right",padx=(8,0))
    ttk.Button(buttons,text="Tạo Admin",command=create_admin).pack(side="right")
    root.bind("<Return>", lambda _e:create_admin())
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.update_idletasks()
    x=(root.winfo_screenwidth()-root.winfo_reqwidth())//2; y=(root.winfo_screenheight()-root.winfo_reqheight())//2
    root.geometry(f"+{max(0,x)}+{max(0,y)}")
    entries[1].focus_set()
    root.mainloop()
    return bool(result["ok"])


def _reserve_port() -> tuple[int, socket.socket]:
    """Reserve the localhost port until Uvicorn takes ownership of the socket."""
    for port in range(8765, 8796):
        s=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            s.bind(("127.0.0.1", port))
            s.setblocking(False)
            return port, s
        except OSError:
            s.close()
    raise RuntimeError("Không tìm được cổng local trống từ 8765 đến 8795.")


def _wait_health(url: str, timeout: float = 35.0) -> None:
    deadline = time.monotonic() + timeout
    last = ""
    expected_instance=os.environ.get("NA_INSTANCE_TOKEN","")
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=0.9) as r:
                payload=json.loads(r.read().decode("utf-8"))
                valid=(r.status==200 and payload.get("ok") is True and payload.get("background_ready") is True
                       and payload.get("service")=="networkautomation-desktop"
                       and payload.get("ui_version")=="7.0.3"
                       and payload.get("release")=="Desktop 7.0.3 Desktop Only"
                       and payload.get("instance")==expected_instance)
                if valid:
                    return
                last="Backend health không khớp phiên Desktop hiện tại."
        except Exception as exc:
            last = str(exc)
        time.sleep(0.08)
    raise RuntimeError("Backend local không khởi động kịp." + (" " + last if last else ""))


def _start_server(port: int, reserved_socket: socket.socket):
    import uvicorn
    config = uvicorn.Config("webapi.main:app", host="127.0.0.1", port=port, workers=1,
                            log_level="warning", access_log=False, proxy_headers=False,
                            log_config=None)
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    def run_server():
        try:
            server.run(sockets=[reserved_socket])
        finally:
            try: reserved_socket.close()
            except OSError: pass
    thread = threading.Thread(target=run_server, name="NetworkAutomationLocalAPI", daemon=True)
    thread.start()
    return server, thread


def _startup_splash_html() -> str:
    # Keep this self-contained so it paints before FastAPI/static files are ready.
    return """<!doctype html><html><head><meta charset='utf-8'><style>
    html,body{height:100%;margin:0;background:#061522;color:#eef8ff;font-family:Segoe UI,Arial,sans-serif}
    body{display:flex;align-items:center;justify-content:center}.box{text-align:center}
    .logo{width:54px;height:54px;border-radius:16px;background:#168ff2;display:inline-flex;align-items:center;justify-content:center;font-size:28px;font-weight:800;box-shadow:0 0 34px #168ff255}
    h1{font-size:20px;margin:16px 0 6px}.sub{font-size:13px;color:#8fb8d1}.bar{width:240px;height:3px;background:#123247;border-radius:8px;overflow:hidden;margin:18px auto 0}.bar:before{content:'';display:block;height:100%;width:42%;background:#1ca6ff;animation:m .75s ease-in-out infinite alternate}@keyframes m{to{transform:translateX(140%)}}
    </style></head><body><div class='box'><div class='logo'>N</div><h1>NetworkAutomation Desktop 7.0.3</h1><div class='sub'>Đang mở giao diện cục bộ...</div><div class='bar'></div></div></body></html>"""


def _startup_error_html(message: str) -> str:
    safe = html.escape(str(message))
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>
    html,body{{height:100%;margin:0;background:#071621;color:#eff8ff;font-family:Segoe UI,Arial,sans-serif}}
    body{{display:flex;align-items:center;justify-content:center}}.box{{max-width:760px;padding:30px;border:1px solid #713d47;border-radius:16px;background:#101b26}}
    h2{{color:#ff7485}}pre{{white-space:pre-wrap;color:#cfe3ef}}
    </style></head><body><div class='box'><h2>Không thể khởi động backend local</h2><pre>{safe}</pre><p>Đóng cửa sổ này và xem log để kiểm tra chi tiết.</p></div></body></html>"""


def _run_desktop_window(port: int, url: str, reserved_socket: socket.socket) -> None:
    """Paint a window immediately, then start/navigate to the local backend."""
    import webview

    state: dict[str, object] = {"server": None, "thread": None, "error": None}
    window = webview.create_window(
        APP_TITLE,
        html=_startup_splash_html(),
        width=1480,
        height=920,
        min_size=(1024, 700),
        text_select=True,
    )

    def _bootstrap() -> None:
        try:
            server, thread = _start_server(port, reserved_socket)
            state["server"], state["thread"] = server, thread
            _wait_health(url)
            window.load_url(url)
        except Exception as exc:
            state["error"] = exc
            try:
                window.load_html(_startup_error_html(str(exc)))
            except Exception:
                pass

    # pywebview invokes this callback after the native window is already visible.
    webview.start(_bootstrap, debug=False)

    server = state.get("server")
    thread = state.get("thread")
    if server is not None:
        server.should_exit = True
    if thread is not None and getattr(thread, "is_alive", lambda: False)():
        thread.join(timeout=8)
    if state.get("error") is not None:
        raise RuntimeError(str(state["error"]))


def main() -> int:
    _configure_environment()
    mutex = _single_instance()
    if mutex is None:
        _show_error(APP_TITLE, "NetworkAutomation Desktop đang chạy. Chỉ mở một phiên trên mỗi máy.")
        return 2

    from app_runtime import setup_logging, migrate_portable_data_once
    setup_logging(); migrate_portable_data_once()
    try:
        _ensure_webview2_runtime()
    except Exception as exc:
        _show_error(APP_TITLE, str(exc))
        return 3
    if not _first_run_admin():
        return 0

    port, reserved_socket = _reserve_port(); url=f"http://127.0.0.1:{port}"
    try:
        _run_desktop_window(port, url, reserved_socket)
        return 0
    except Exception as exc:
        try: reserved_socket.close()
        except OSError: pass
        _show_error(APP_TITLE, f"Không thể mở giao diện Desktop.\n\n{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
