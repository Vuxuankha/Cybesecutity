"""Consistent local snapshots before each application release's first migration."""
import json
import os
import hashlib
import shutil
import sqlite3
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

_LOCK = threading.Lock()


@contextmanager
def _release_lock(base):
    from runtime_lock import RuntimeLock
    lock = RuntimeLock(base / '.release_backup.lock')
    deadline = time.monotonic() + 30
    while True:
        try:
            lock.__enter__()
            break
        except RuntimeError:
            if time.monotonic() >= deadline:
                raise RuntimeError('Đang sao lưu trước nâng cấp; hãy đợi rồi mở lại ứng dụng.') from None
            time.sleep(.02)
    try:
        yield
    finally:
        lock.__exit__(None, None, None)


def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _valid_existing_marker(marker: Path, base: Path, database_name: str) -> bool:
    """Return True only when the marker still references a healthy local backup."""
    try:
        payload=json.loads(marker.read_text(encoding='utf-8'))
        rel=Path(str(payload.get('backup') or ''))
        if not rel.parts or rel.is_absolute() or '..' in rel.parts:
            return False
        backup=(base/rel).resolve(); root=(base/'db_backups').resolve()
        if not backup.is_dir() or not backup.is_relative_to(root):
            return False
        db=backup/database_name
        if not db.is_file() or db.stat().st_size <= 0:
            return False
        conn=sqlite3.connect(f'file:{db.as_posix()}?mode=ro',uri=True,timeout=5)
        try:
            if conn.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                return False
        finally:
            conn.close()
        manifest=backup/'manifest.json'
        if manifest.is_file():
            meta=json.loads(manifest.read_text(encoding='utf-8'))
            hashes=meta.get('sha256') or {}
            for name, expected in hashes.items():
                f=backup/name
                if not f.is_file() or _sha256(f) != expected:
                    return False
        return True
    except Exception:
        return False


def backup_before_release(database_path, resource_dir, version=None):
    database_path = Path(database_path)
    base = database_path.parent
    version = version or (Path(resource_dir) / 'VERSION.txt').read_text(encoding='utf-8').strip()
    if not version or any(c not in '0123456789.' for c in version):
        raise ValueError('Invalid application version')
    marker = base / f'.release_backup_{version}.json'
    base.mkdir(parents=True, exist_ok=True)
    with _LOCK, _release_lock(base):
        if not database_path.exists() or database_path.stat().st_size == 0:
            return None
        if marker.exists():
            if _valid_existing_marker(marker, base, database_path.name):
                return None
            marker.unlink(missing_ok=True)
        backups = base / 'db_backups'
        backups.mkdir(parents=True, exist_ok=True)
        pending = Path(tempfile.mkdtemp(prefix='.pending_', dir=backups))
        try:
            source = sqlite3.connect(database_path, timeout=15)
            destination = sqlite3.connect(pending / database_path.name)
            try:
                # Capture ancillary trust/key material under the same release lock and
                # a stable database read transaction, then snapshot SQLite via backup().
                source.execute('BEGIN')
                for name in ('.credential.key', 'known_hosts'):
                    if (base / name).is_file():
                        shutil.copy2(base / name, pending / name)
                source.backup(destination)
                if destination.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Backup database integrity check failed')
                source.rollback()
            finally:
                destination.close()
                source.close()
            files=sorted(p.name for p in pending.iterdir())
            metadata = {'version': version, 'created_at': datetime.now().isoformat(),
                        'database': database_path.name,
                        'files': files,
                        'sha256': {name:_sha256(pending/name) for name in files}}
            (pending / 'manifest.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
            final = backups / f"pre_app_v{version}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            pending.rename(final)
            temporary_marker = base / f'.release_backup_{version}.tmp'
            temporary_marker.write_text(json.dumps({'backup': str(final.relative_to(base))}), encoding='utf-8')
            os.replace(temporary_marker, marker)
            return final
        except Exception:
            shutil.rmtree(pending, ignore_errors=True)
            raise
