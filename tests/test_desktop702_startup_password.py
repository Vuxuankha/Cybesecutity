from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_uvicorn_does_not_use_default_logging_formatter():
    text=(ROOT/'desktop_launcher.py').read_text(encoding='utf-8')
    assert 'log_config=None' in text

def test_desktop_first_admin_has_no_length_rule():
    text=(ROOT/'desktop_launcher.py').read_text(encoding='utf-8')
    assert 'Mật khẩu (12+ ký tự)' not in text
    assert 'len(p) < 12' not in text
    assert 'Mật khẩu không được để trống.' in text

def test_account_password_has_no_arbitrary_maximum():
    acc=(ROOT/'modules/accounts.py').read_text(encoding='utf-8')
    routes=(ROOT/'webapi/routes37.py').read_text(encoding='utf-8')
    sec=(ROOT/'webapi/security37.py').read_text(encoding='utf-8')
    html=(ROOT/'webapi/static/index.html').read_text(encoding='utf-8')
    assert '8 <= len(password) <= 256' not in acc
    assert 'max_length=256' not in routes.split('class UserIn',1)[1].split('def account_call',1)[0]
    assert 'len(password)<=256' not in sec
    assert 'maxlength="256"' not in html
