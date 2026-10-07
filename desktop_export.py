"""Short-lived desktop-only export destination selections.

The browser never receives permission to write to an arbitrary path by itself.
A native folder picker registers a selected directory and returns a one-time token;
the local API consumes that token when it writes the requested export.
"""
from __future__ import annotations

from pathlib import Path
import os
import secrets
import subprocess
import threading
import time
from typing import Callable

_TTL_SECONDS = 10 * 60
_lock = threading.Lock()
_destinations: dict[str, tuple[str, float]] = {}
_native_picker: Callable[[], str | None] | None = None


def _cleanup(now: float | None = None) -> None:
    current = float(now or time.time())
    with _lock:
        expired = [token for token, (_, expiry) in _destinations.items() if expiry <= current]
        for token in expired:
            _destinations.pop(token, None)


def register_export_directory(path: str) -> str:
    _cleanup()
    target = Path(str(path or '')).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise ValueError('EXPORT_DIRECTORY_INVALID')
    if not os.access(target, os.W_OK):
        raise ValueError('EXPORT_DIRECTORY_NOT_WRITABLE')
    token = secrets.token_urlsafe(32)
    with _lock:
        _destinations[token] = (str(target), time.time() + _TTL_SECONDS)
    return token


def consume_export_directory(token: str | None) -> Path | None:
    if not token:
        return None
    _cleanup()
    with _lock:
        item = _destinations.pop(str(token), None)
    if not item:
        raise ValueError('EXPORT_DIRECTORY_SELECTION_EXPIRED')
    raw, expiry = item
    if expiry <= time.time():
        raise ValueError('EXPORT_DIRECTORY_SELECTION_EXPIRED')
    target = Path(raw).resolve()
    if not target.exists() or not target.is_dir():
        raise ValueError('EXPORT_DIRECTORY_INVALID')
    if not os.access(target, os.W_OK):
        raise ValueError('EXPORT_DIRECTORY_NOT_WRITABLE')
    return target


def set_native_export_picker(picker: Callable[[], str | None] | None) -> None:
    """Register the Desktop window's native picker.

    Export actions can call this through the local API, so they do not depend
    on ``window.pywebview`` being injected into the currently loaded page.
    """
    global _native_picker
    with _lock:
        _native_picker = picker


def _powershell_folder_picker() -> str | None:
    """Open a Windows folder dialog with a hidden PowerShell host."""
    if os.name != 'nt':
        return None
    script = """Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
$owner.StartPosition = 'CenterScreen'
$owner.Size = New-Object System.Drawing.Size(1,1)
$owner.Opacity = 0
$dlg = New-Object System.Windows.Forms.FolderBrowserDialog
$dlg.Description = 'Chọn thư mục lưu file xuất NetworkAutomation'
$dlg.ShowNewFolderButton = $true
try {
  $result = $dlg.ShowDialog($owner)
  if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dlg.SelectedPath
  }
} finally {
  $dlg.Dispose()
  $owner.Dispose()
}
"""
    kwargs = {}
    try:
        from app_runtime import hidden_subprocess_kwargs
        kwargs.update(hidden_subprocess_kwargs())
    except Exception:
        if hasattr(subprocess, 'CREATE_NO_WINDOW'):
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    cp = subprocess.run(
        ['powershell.exe', '-NoLogo', '-NoProfile', '-STA', '-ExecutionPolicy', 'Bypass', '-Command', script],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=120,
        **kwargs,
    )
    if cp.returncode != 0:
        raise RuntimeError((cp.stderr or cp.stdout or 'Windows folder picker failed').strip()[:500])
    selected = [line.strip() for line in (cp.stdout or '').splitlines() if line.strip()]
    return selected[-1] if selected else None


def choose_export_directory() -> dict:
    """Open the real Windows directory chooser and return a one-time token.

    The pywebview window callback is preferred.  A hidden PowerShell/WinForms
    chooser is used if that path is unavailable.  Cancellation is normal and
    does not surface as an error.
    """
    with _lock:
        picker = _native_picker
    errors: list[str] = []
    selected: str | None = None
    if picker is not None:
        try:
            selected = picker()
            if not selected:
                return {'cancelled': True}
        except Exception as exc:
            errors.append(f'pywebview: {exc}')
    if picker is None or errors:
        try:
            selected = _powershell_folder_picker()
        except Exception as exc:
            errors.append(f'PowerShell: {exc}')
    if not selected:
        if errors:
            return {
                'cancelled': True,
                'error': 'Không mở được hộp chọn thư mục Windows. ' + ' | '.join(errors)[:700],
            }
        return {'cancelled': True}
    token = register_export_directory(selected)
    return {'cancelled': False, 'token': token, 'display_path': str(Path(selected))}
