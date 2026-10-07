from __future__ import annotations

import logging
import json
from logging.handlers import RotatingFileHandler
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "NetworkAutomation"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Read-only application resources (source tree or PyInstaller bundle)."""
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def install_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _writable_data_dir(path: Path) -> Path | None:
    """Return a writable directory or ``None`` without aborting application import."""
    try:
        resolved = path.expanduser().resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        probe = resolved / '.na_write_probe'
        probe.write_text('ok', encoding='ascii')
        probe.unlink(missing_ok=True)
        return resolved
    except Exception:
        return None


def data_root() -> Path:
    """Resolve a writable data directory, preferring portable application data.

    A malformed/unwritable optional override must never make the desktop fail
    before its error UI can be shown.  The last fallback is the per-user app
    data directory on Windows.
    """
    candidates: list[Path] = []
    override = str(os.environ.get('NETWORK_AUTOMATION_DATA_DIR') or '').strip()
    if override:
        candidates.append(Path(override))

    config = install_root() / 'data_location.json'
    if config.is_file():
        try:
            payload = json.loads(config.read_text(encoding='utf-8'))
            value = str(payload.get('data_dir') or '').strip()
            if value and Path(value).is_absolute():
                candidates.append(Path(value))
        except Exception as exc:
            # Logging may not yet be configured during module import.  Preserve
            # a diagnostic hint for the launcher instead of crashing import.
            os.environ['NA_DATA_LOCATION_WARNING'] = type(exc).__name__

    candidates.append(install_root() / 'runtime_data')
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA')
    if base:
        candidates.append(Path(base) / APP_NAME)

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        usable = _writable_data_dir(candidate)
        if usable is not None:
            return usable
    raise RuntimeError('Không tìm thấy thư mục dữ liệu có quyền ghi cho NetworkAutomation.')


RESOURCE_DIR = resource_root()
DATA_DIR = data_root()
DATABASE_DIR = DATA_DIR / "database"
REPORT_DIR = DATA_DIR / "reports"
BACKUP_DIR = DATA_DIR / "backups"
LOG_DIR = DATA_DIR / "logs"

for _p in (DATA_DIR, DATABASE_DIR, REPORT_DIR, BACKUP_DIR, LOG_DIR):
    _p.mkdir(parents=True, exist_ok=True)


def resource_path(*parts: str) -> Path:
    return RESOURCE_DIR.joinpath(*parts)


def data_path(*parts: str) -> Path:
    p = DATA_DIR.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def migrate_portable_data_once() -> None:
    """Idempotently import missing legacy state into the active data folder.

    The marker is informational only.  Every start may safely check for files
    that are still missing, so a marker accidentally present in a release ZIP
    cannot suppress migration on a different PC.
    """
    marker = DATA_DIR / '.portable_migration_checked'
    roots: list[Path] = [install_root()]
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA')
    if base:
        roots.append(Path(base) / APP_NAME)

    mappings = (
        ('database/network_automation.db', DATABASE_DIR / 'network_automation.db'),
        ('database/.credential.key', DATABASE_DIR / '.credential.key'),
        ('database/known_hosts', DATABASE_DIR / 'known_hosts'),
    )
    copied: list[str] = []
    failures: list[Exception] = []
    for legacy_root in roots:
        try:
            if legacy_root.resolve() == DATA_DIR.resolve():
                continue
        except Exception:
            pass
        for rel, dst in mappings:
            src = legacy_root / rel
            try:
                if src.is_file() and not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    copied.append(rel)
            except Exception as exc:
                logging.getLogger(__name__).error('Portable migration failed for %s: %s', rel, exc)
                failures.append(exc)

    if failures:
        # Do not write the completion marker when a legacy source existed but
        # could not be copied; the launcher can show the failure and retry next start.
        raise failures[0]

    try:
        payload = {'checked': True, 'copied': copied}
        tmp = marker.with_name(marker.name + '.tmp')
        tmp.write_text(json.dumps(payload, ensure_ascii=False) + '\n', encoding='utf-8')
        os.replace(tmp, marker)
    except Exception as exc:
        logging.getLogger(__name__).warning('Cannot write portable migration marker: %s', exc)


def hidden_subprocess_kwargs() -> dict:
    """Prevent helper console windows from flashing on Windows."""
    if os.name != "nt":
        return {}
    kwargs = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    startup_cls = getattr(subprocess, "STARTUPINFO", None)
    if startup_cls is not None:
        si = startup_cls()
        si.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        si.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = si
    return kwargs


def setup_logging() -> Path:
    log_file = LOG_DIR / "network_automation.log"
    # PyInstaller windowed mode may set stdout/stderr to None. Keep third-party
    # print() calls harmless and preserve their output for troubleshooting.
    if is_frozen() and (sys.stdout is None or sys.stderr is None):
        stream = open(LOG_DIR / "console_capture.log", "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = stream
        if sys.stderr is None:
            sys.stderr = stream
    logging.basicConfig(
        handlers=[RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")],
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger(__name__).info(
        "Application start frozen=%s data_dir=%s", is_frozen(), DATA_DIR
    )
    return log_file
