from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_api_supports_custom_timeout_for_long_network_tasks():
    app = (ROOT / 'webapi/static/app.js').read_text(encoding='utf-8')
    assert 'options.timeoutMs' in app
    assert 'Math.min(requestedTimeout,180000)' in app
    assert 'delete options.timeoutMs' in app


def test_speed_test_uses_extended_timeout_and_explicit_empty_state():
    js = (ROOT / 'webapi/static/cybersecurity51.js').read_text(encoding='utf-8')
    assert "timeoutMs:180000" in js
    assert "sp.download_mbps==null?'Chưa đo'" in js
    assert "sp.upload_mbps==null?'Chưa đo'" in js
    assert 'có thể mất 30–120 giây' in js


def test_line_and_diagnostics_have_longer_timeouts_than_default():
    js = (ROOT / 'webapi/static/cybersecurity51.js').read_text(encoding='utf-8')
    assert "timeoutMs:45000" in js
    assert "timeoutMs:60000" in js
