from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


def test_rfc1918_scan_scope_only():
    from webapi.main import _validate_scan_scope
    for value in ('10.2.0.0/24','172.16.5.0/24','192.168.50.0/24'):
        assert str(_validate_scan_scope(value)) == value
    for value in ('127.0.0.0/24','0.0.0.0/24','192.0.2.0/24','198.51.100.0/24','203.0.113.0/24','8.8.8.0/24'):
        with pytest.raises(HTTPException):
            _validate_scan_scope(value)


def test_rate_limit_bad_environment_uses_safe_default(monkeypatch):
    from webapi import security37
    monkeypatch.setenv('NA_API_READS_PER_MIN','oops')
    security37._RATE_BUCKETS.clear()
    security37._rate_check('test-peer','GET','/api/test')
    assert security37._env_rate_limit('NA_API_READS_PER_MIN',600) == 600


def test_session_binding_prefers_canonical_authenticated_state():
    from webapi import security37
    request=SimpleNamespace(state=SimpleNamespace(session_hash='canonical-hash'))
    assert security37.session_binding(request) == 'canonical-hash'


def test_local_websocket_allowed_without_cookie_secure_env(monkeypatch):
    from webapi.terminal46 import websocket_origin_ok
    monkeypatch.delenv('NA_COOKIE_SECURE',raising=False)
    ws=SimpleNamespace(
        headers={'origin':'http://127.0.0.1:8765','sec-fetch-site':'same-origin'},
        url=SimpleNamespace(scheme='ws',netloc='127.0.0.1:8765',hostname='127.0.0.1'),
        client=SimpleNamespace(host='127.0.0.1'),
    )
    assert websocket_origin_ok(ws) is True
    ws.client.host='10.0.0.2'
    assert websocket_origin_ok(ws) is False


def test_export_filename_blocks_windows_reserved_names():
    from webapi.reports37 import _safe_export_name
    assert _safe_export_name('CON.csv','.csv').startswith('_CON')
    assert _safe_export_name('LPT1.xlsx','.xlsx').startswith('_LPT1')


def test_csv_export_neutralizes_formula_and_is_atomic(tmp_path, monkeypatch):
    from webapi import reports37
    monkeypatch.setattr(reports37,'_export_root',lambda token=None:tmp_path)
    monkeypatch.setattr(reports37,'register',lambda path,owner_id,kind:{'path':str(path),'kind':kind})
    result=reports37.save_csv(1,'data.csv','name,value\nrouter,=HYPERLINK("http://bad")\n')
    raw=Path(result['path']).read_text(encoding='utf-8-sig')
    assert "'=HYPERLINK" in raw
    assert not list(tmp_path.glob('.export_*'))


def test_csv_and_xlsx_column_limits():
    from webapi.reports37 import _read_bounded_csv
    with pytest.raises(ValueError,match='CSV_TOO_MANY_COLUMNS'):
        _read_bounded_csv(','.join(['x']*257))


def test_external_export_kind_is_explicit(tmp_path):
    from webapi.reports37 import _download_kind
    assert _download_kind(tmp_path/'x.csv','csv') == 'external_csv'


def test_config_backup_encryption_roundtrip(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    from modules import nms_v5
    cipher=Fernet(Fernet.generate_key())
    monkeypatch.setattr(nms_v5,'_fernet',lambda allow_create=True:cipher)
    path=tmp_path/'router.cfg.enc'
    nms_v5.write_config_backup(path,'username admin secret 123\n')
    raw=path.read_text(encoding='ascii')
    assert 'username admin secret 123' not in raw
    assert raw.startswith(nms_v5.CONFIG_BACKUP_MAGIC)
    assert nms_v5.read_config_backup(path) == 'username admin secret 123\n'


def test_server_monitor_blocks_metadata_and_public_by_default(monkeypatch):
    from modules.server_monitor import validate_target
    monkeypatch.delenv('NA_ALLOW_PUBLIC_MONITOR_TARGETS',raising=False)
    assert validate_target('127.0.0.1',80,'HTTP')[0] == '127.0.0.1'
    with pytest.raises(ValueError): validate_target('169.254.169.254',80,'HTTP')
    with pytest.raises(ValueError): validate_target('8.8.8.8',443,'HTTPS')


def test_database_module_has_no_migration_import_side_effect():
    source=Path('database/db.py').read_text(encoding='utf-8')
    assert 'migrate_portable_data_once()' not in source


def test_logging_forces_file_handler_configuration():
    source=Path('app_runtime.py').read_text(encoding='utf-8')
    block=source.split('def setup_logging()',1)[1]
    assert 'force=True' in block


def test_login_attempt_indexes_cover_user_and_peer():
    source=Path('webapi/security37.py').read_text(encoding='utf-8')
    assert 'ix_web_login_attempts_user_time' in source
    assert 'ix_web_login_attempts_peer_time' in source


def test_content_type_check_uses_actual_body_not_content_length_only():
    source=Path('webapi/security37.py').read_text(encoding='utf-8')
    assert 'body=await request.body()' in source
    assert "if body and request.headers.get('content-type'" in source


def test_public_health_remote_shape_is_minimal():
    from webapi import main
    request=SimpleNamespace(client=SimpleNamespace(host='10.10.10.10'),url=SimpleNamespace(hostname='10.10.10.20'))
    result=main.health(request)
    if hasattr(result,'body'):
        import json
        result=json.loads(result.body)
    assert 'boot_id' not in result and 'instance' not in result and 'background_error' not in result


def test_diagnostics_names_include_microseconds_and_randomness():
    ops=Path('webapi/operations47.py').read_text(encoding='utf-8')
    term=Path('webapi/terminal46.py').read_text(encoding='utf-8')
    assert '%Y%m%d_%H%M%S_%f' in ops and 'secrets.token_hex(4)' in ops
    assert '%Y%m%d_%H%M%S_%f' in term and 'secrets.token_hex(4)' in term


def test_scan_results_have_indexes_and_retention():
    main=Path('webapi/main.py').read_text(encoding='utf-8')
    ops=Path('webapi/ops41.py').read_text(encoding='utf-8')
    assert 'ix_web_scan_results_scan_key' in main
    assert "'web_scan_results': 90" in ops


def test_retention_skips_snapshot_when_nothing_to_delete():
    source=Path('webapi/ops41.py').read_text(encoding='utf-8')
    assert "if not actionable:" in source
    assert "'safety_backup': None" in source


def test_tcp_security_check_no_longer_unconditionally_passes():
    source=Path('modules/enterprise_security.py').read_text(encoding='utf-8')
    block=source.split('def tcp_probe',1)[1].split('def tls_certificate_check',1)[0]
    assert 'result = "REVIEW" if risky else "PASS"' in block


def test_tls_check_verifies_certificate_before_diagnostic_fallback():
    source=Path('modules/enterprise_security.py').read_text(encoding='utf-8')
    block=source.split('def tls_certificate_check',1)[1].split('class EnterpriseSecurityPage',1)[0]
    assert 'ssl.create_default_context()' in block
    assert 'except ssl.SSLCertVerificationError' in block
    assert 'certificate_verified' in block


def test_release_backup_marker_is_validated_not_blindly_trusted():
    source=Path('upgrade_backup.py').read_text(encoding='utf-8')
    assert 'def _valid_existing_marker' in source
    assert "PRAGMA quick_check" in source
    assert "marker.unlink(missing_ok=True)" in source


def test_portable_migration_captures_wal_and_same_root_key(tmp_path, monkeypatch):
    import app_runtime
    legacy=tmp_path/'legacy'
    legacy_db_dir=legacy/'database'
    legacy_db_dir.mkdir(parents=True)
    db_path=legacy_db_dir/'network_automation.db'
    conn=sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT)')
    conn.execute("INSERT INTO sample(value) VALUES('from-wal')")
    conn.commit()
    # Keep the WAL-capable source connection alive while migration uses SQLite backup().
    (legacy_db_dir/'.credential.key').write_bytes(b'same-root-key')

    data=tmp_path/'active-data'
    database_dir=data/'database'
    database_dir.mkdir(parents=True)
    monkeypatch.setattr(app_runtime,'DATA_DIR',data)
    monkeypatch.setattr(app_runtime,'DATABASE_DIR',database_dir)
    monkeypatch.setattr(app_runtime,'install_root',lambda:legacy)
    monkeypatch.delenv('LOCALAPPDATA',raising=False)
    monkeypatch.delenv('APPDATA',raising=False)
    try:
        app_runtime.migrate_portable_data_once()
    finally:
        conn.close()

    migrated=sqlite3.connect(database_dir/'network_automation.db')
    try:
        assert migrated.execute('SELECT value FROM sample').fetchone()[0] == 'from-wal'
    finally:
        migrated.close()
    assert (database_dir/'.credential.key').read_bytes() == b'same-root-key'
    assert not (database_dir/'network_automation.db-wal').exists()


def test_release_backup_recreates_when_marker_target_disappears(tmp_path):
    from upgrade_backup import backup_before_release
    db=tmp_path/'network_automation.db'
    conn=sqlite3.connect(db)
    conn.execute('CREATE TABLE t(v TEXT)')
    conn.execute("INSERT INTO t VALUES('ok')")
    conn.commit(); conn.close()
    resource=tmp_path/'resource'; resource.mkdir()
    (resource/'VERSION.txt').write_text('7.0.3',encoding='utf-8')

    first=backup_before_release(db,resource)
    assert first and first.exists()
    import shutil
    shutil.rmtree(first)
    second=backup_before_release(db,resource)
    assert second and second.exists() and second != first


def test_export_same_name_reservation_is_collision_safe(tmp_path, monkeypatch):
    from webapi import reports37
    monkeypatch.setattr(reports37,'_export_root',lambda token=None:tmp_path)
    monkeypatch.setattr(reports37,'register',lambda path,owner_id,kind:{'path':str(path),'kind':kind})
    one=reports37.save_csv(1,'same.csv','a,b\n1,2\n')
    two=reports37.save_csv(1,'same.csv','a,b\n3,4\n')
    assert Path(one['path']).name != Path(two['path']).name
    assert Path(one['path']).read_text(encoding='utf-8-sig') != Path(two['path']).read_text(encoding='utf-8-sig')


def test_server_monitor_allows_ipv6_loopback():
    from modules.server_monitor import _monitor_ip_allowed
    assert _monitor_ip_allowed('::1') is True
