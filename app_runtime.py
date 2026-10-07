from __future__ import annotations

import logging
import json
from logging.handlers import RotatingFileHandler
import os
import shutil
import subprocess
import sys
import sqlite3
import tempfile
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
        fd, probe_name = tempfile.mkstemp(prefix='.na_write_probe_', dir=resolved)
        os.close(fd)
        Path(probe_name).unlink(missing_ok=True)
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
        override_path=Path(override).expanduser()
        if override_path.is_absolute():
            candidates.append(override_path)
        else:
            os.environ['NA_DATA_LOCATION_WARNING']='NETWORK_AUTOMATION_DATA_DIR_MUST_BE_ABSOLUTE'

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
    """Import one coherent legacy database bundle exactly once.

    The database is copied with SQLite's backup API (so WAL state is included) and
    credential/trust files are taken only from that same legacy root.  We never mix
    a database from one installation with a key from another.
    """
    marker = DATA_DIR / '.portable_migration_checked'
    active_db = DATABASE_DIR / 'network_automation.db'
    roots: list[Path] = [install_root()]
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA')
    if base:
        roots.append(Path(base) / APP_NAME)

    # If an active database already exists, never guess which legacy key belongs to it.
    if active_db.is_file() and active_db.stat().st_size > 0:
        if not marker.exists():
            tmp=marker.with_name(marker.name+'.tmp')
            tmp.write_text(json.dumps({'checked': True, 'copied': [], 'reason': 'active_database_exists'}, ensure_ascii=False)+'\n', encoding='utf-8')
            os.replace(tmp, marker)
        return

    source_root = None
    for legacy_root in roots:
        try:
            if legacy_root.resolve() == DATA_DIR.resolve():
                continue
        except (OSError, RuntimeError):
            if os.path.abspath(os.fspath(legacy_root)) == os.path.abspath(os.fspath(DATA_DIR)):
                continue
        candidate = legacy_root / 'database' / 'network_automation.db'
        if candidate.is_file() and candidate.stat().st_size > 0:
            source_root = legacy_root
            break

    if source_root is None:
        if not marker.exists():
            tmp=marker.with_name(marker.name+'.tmp')
            tmp.write_text(json.dumps({'checked': True, 'copied': []}, ensure_ascii=False)+'\n', encoding='utf-8')
            os.replace(tmp, marker)
        return

    # Do not merge a coherent bundle into a partially populated destination directory.
    existing=[p for p in DATABASE_DIR.iterdir() if p.is_file()]
    if existing:
        raise RuntimeError('Thư mục database đích đã có dữ liệu rời; không tự ghép với dữ liệu legacy khác nguồn.')

    stage_root=Path(tempfile.mkdtemp(prefix='.portable_migration_', dir=DATA_DIR))
    stage_db=stage_root/'database'
    stage_db.mkdir(parents=True, exist_ok=True)
    copied=[]
    try:
        src_db=source_root/'database'/'network_automation.db'
        src=sqlite3.connect(src_db.resolve().as_uri()+'?mode=ro', uri=True, timeout=15)
        dst=sqlite3.connect(stage_db/'network_automation.db')
        try:
            src.backup(dst)
            if dst.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise RuntimeError('Portable database integrity check failed')
        finally:
            dst.close(); src.close()
        copied.append('database/network_automation.db')
        for name in ('.credential.key','known_hosts'):
            src_file=source_root/'database'/name
            if src_file.is_file():
                shutil.copy2(src_file,stage_db/name); copied.append('database/'+name)
        # DATABASE_DIR was created during startup; replace it as a directory to make
        # the bundle switch atomic instead of replacing DB/key/trust files separately.
        DATABASE_DIR.rmdir()
        os.replace(stage_db, DATABASE_DIR)
        stage_root.rmdir()
        payload={'checked':True,'copied':copied,'source':str(source_root)}
        tmp=marker.with_name(marker.name+'.tmp')
        tmp.write_text(json.dumps(payload,ensure_ascii=False)+'\n',encoding='utf-8')
        os.replace(tmp,marker)
    except Exception:
        shutil.rmtree(stage_root,ignore_errors=True)
        DATABASE_DIR.mkdir(parents=True,exist_ok=True)
        raise


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
        force=True,
    )
    logging.getLogger(__name__).info(
        "Application start frozen=%s data_dir=%s", is_frozen(), DATA_DIR
    )
    return log_file
