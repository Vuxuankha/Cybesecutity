from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def test_kali_is_removed_and_red_hat_uses_bounded_windows_profiles():
    win = text('webapi/windows_tools79.py')
    js = text('webapi/static/windows_tools79.js')
    assert not (ROOT/'webapi/kali63.py').exists()
    assert not (ROOT/'webapi/static/kali63.js').exists()
    assert '/api/v1/kali' not in text('webapi/main.py')
    for profile in ('red_recon','red_config_audit','red_connectivity','red_http_headers','red_tls_audit','red_cookie_audit','red_network_state','red_light_load'):
        assert profile in win and profile in js
    assert 'arbitrary_shell' in win


def test_side_effect_network_checks_are_post_and_no_default_get_retry():
    api = text('webapi/static/app.js')
    p50 = text('webapi/platform50.py')
    ui50 = text('webapi/static/operations50.js')
    assert "const retrySafe=options.retry===true" in api
    assert "@router.post('/network/connectivity/probe')" in p50
    assert "@router.post('/network/identity/refresh')" in p50
    assert "api('/v50/network/connectivity/probe',{method:'POST'" in ui50
    assert "api('/v50/network/identity/refresh',{method:'POST'" in ui50
    assert "void checkNetwork50(false);void checkIp5011(false)" in ui50


def test_navigation_and_feature_installation_is_idempotent():
    h10=text('webapi/static/hotfix10_nav_core.js')
    assert '__naHotfix10Installed' in h10
    assert "addEventListener('load'" not in h10
    assert 'setTimeout(apply' not in h10
    for rel, token in [
        ('webapi/static/security_modes61.js','__naSecurityModes61Installed'),
        ('webapi/static/security_catalog62.js','__naSecurityCatalog62Installed'),
        ('webapi/static/enterprise600.js','__naEnterprise600Installed'),
        ('webapi/static/windows_tools79.js','__naWindowsTools79Installed'),
    ]:
        assert token in text(rel)
    for rel in ('webapi/static/security_modes61.js','webapi/static/security_catalog62.js','webapi/static/enterprise600.js','webapi/static/windows_tools79.js'):
        assert 'window.go=' not in text(rel).replace(' ', '')


def test_generated_downloads_use_server_registry_and_short_lived_one_time_tokens():
    reports=text('webapi/reports37.py')
    routes=text('webapi/routes37.py')
    assert 'TOKEN_TTL_SECONDS = 3600' in reports
    assert 'FILE_RETENTION_SECONDS = 7 * 86400' in reports
    assert "'saved_relative_path': _relative_display(path)" in reports
    assert "'saved_path'" not in reports
    assert "DELETE FROM web_downloads37 WHERE token=?" in routes
    assert "raise HTTPException(410,'Download expired')" in routes
    assert 'merged_devices()[:5000]' in reports
    assert '2 * 1024 * 1024' in reports


def test_all_runtime_generated_download_actions_are_server_side():
    static='\n'.join(text(x) for x in [
        'webapi/static/app.js','webapi/static/operations47.js','webapi/static/terminal46.js','webapi/static/workbench45.js'
    ])
    assert 'URL.createObjectURL' not in static
    assert 'new Blob(' not in static
    assert "window.location=r.download_url" not in static
    assert "@router.post('/diagnostics/export')" in text('webapi/operations47.py')
    assert "@router.post('/diagnostics/export')" in text('webapi/terminal46.py')
    assert "@router.post('/remote/{device_id}/rdp-export')" in text('webapi/workbench45.py')


def test_viewer_cannot_create_csv_or_active_network_probe():
    sec=text('webapi/security37.py')
    assert "r'/api/reports/csv', ('Admin','Analyst','Operator')" in sec
    assert "r'/api/v50/network/connectivity/probe', ('Admin','Operator')" in sec
    assert "r'/api/v50/network/identity/refresh', ('Admin','Operator')" in sec


def test_portable_data_resolution_survives_bad_or_unwritable_optional_config():
    runtime=text('app_runtime.py')
    assert 'def _writable_data_dir' in runtime
    assert "NA_DATA_LOCATION_WARNING" in runtime
    assert "candidates.append(install_root() / 'runtime_data')" in runtime
    assert "Path(base) / APP_NAME" in runtime
    # Migration marker is informational and no longer an early-return gate.
    fn=runtime.split('def migrate_portable_data_once()',1)[1].split('def hidden_subprocess_kwargs',1)[0]
    assert 'if marker.exists()' not in fn
    assert 'kali_integration.json' not in fn
    assert 'raise failures[0]' in fn


def test_sqlite_manual_connections_are_closed_in_audited_paths():
    launcher=text('desktop_launcher.py')
    main=text('webapi/main.py')
    runtime=text('webapi/runtime37.py')
    ops=text('webapi/ops41.py')
    assert 'conn.close()' in launcher.split('def _fast_existing_user()',1)[1].split('def _first_run_admin',1)[0]
    assert 'c.close()' in main.split('def _prepare_schema_fast()',1)[1].split('def _start_background_services',1)[0]
    assert 'src.close()' in runtime and 'dst.close()' in runtime
    assert 'c.close()' in runtime.split('def preflight()',1)[1].split('def _columns',1)[0]
    assert 'c.close()' in ops.split('def _quick_check',1)[1].split('def _latest_file_age',1)[0]


def test_process_cleanup_logs_failures_and_tracks_detached_helpers_by_instance_token():
    launcher=text('desktop_launcher.py')
    cleanup=launcher.split('def _terminate_child_processes()',1)[1].split('def _webview2_runtime_version',1)[0]
    job=launcher.split('def _install_process_cleanup_job()',1)[1].split('def _terminate_child_processes',1)[0]
    assert "proc.environ().get('NA_INSTANCE_TOKEN') == token" in cleanup
    assert 'logger.warning' in cleanup
    assert 'logger.warning' in job
    assert "taskkill" not in cleanup.lower()


def test_scheduler_does_not_advance_before_success_and_prevents_duplicate_threads():
    sched=text('webapi/scheduler40.py')
    before=sched.split('def submit_schedule',1)[0]
    submit=sched.split('def submit_schedule',1)[1]
    assert 'logger.exception' in before
    assert 'self._tick_lock.acquire(blocking=False)' in before
    assert 'time.time() + 60' in before
    assert 'engine.submit(operation, payload, user)' in submit
    assert submit.index('engine.submit(operation, payload, user)') < submit.index('next_epoch = time.time()')
    assert "if thread.is_alive():" in before and "return False" in before


def test_firewall_and_defender_detection_avoid_false_safe_states():
    cyber=text('webapi/cybersecurity58.py')
    fw=cyber.split('def _firewall_state()',1)[1].split('def _antivirus_state',1)[0]
    av=cyber.split('def _antivirus_state()',1)[1].split('def _software_sample',1)[0]
    assert fw.index("'inactive' in t") < fw.index("t == 'running'")
    assert "return 'ON' if all(v == 'ON' for v in states) else 'OFF'" in fw
    assert "AntivirusEnabled -and $x.RealTimeProtectionEnabled" in av
    assert "elseif($x.AntivirusEnabled){'ON'}" not in av


def test_release_backup_marker_does_not_store_absolute_build_path():
    src=text('upgrade_backup.py')
    assert "str(final.relative_to(base))" in src
    assert "json.dumps({'backup': str(final)})" not in src
