from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BACK=(ROOT/'webapi/windows_tools79.py').read_text(encoding='utf-8')
JS=(ROOT/'webapi/static/windows_tools79.js').read_text(encoding='utf-8')
NAV=(ROOT/'webapi/static/hotfix10_nav_core.js').read_text(encoding='utf-8')
LOADER=(ROOT/'webapi/static/app.js').read_text(encoding='utf-8')


def test_navigation_uses_windows_local_centers_and_no_kali_config_page():
    assert 'wintools79' in NAV and 'redlocal79' in NAV
    assert 'kaliconfig63' not in NAV and 'kali63' not in NAV
    assert 'HACKER MŨ ĐỎ · RED TEAM LAB' in NAV


def test_red_windows_profiles_are_bounded_safe_diagnostics():
    allowed=['red_recon','red_config_audit','red_connectivity','red_http_headers','red_tls_audit','red_cookie_audit','red_network_state','red_light_load']
    for profile in allowed:
        assert profile in BACK and profile in JS
    assert "le=5" in BACK
    assert "Start-Sleep -Milliseconds 250" in BACK
    forbidden=['exploit','metasploit','mimikatz','credential_dump','persistence_install','reverse_shell']
    low=BACK.lower()
    for item in forbidden:
        assert f"'{item}'" not in low


def test_windows_asset_loaded_after_security_catalog():
    assert LOADER.index("naLoadScript('security_catalog62.js')") < LOADER.index("naLoadScript('windows_tools79.js')")
    assert 'hotfix9_kali_red.js' not in LOADER
