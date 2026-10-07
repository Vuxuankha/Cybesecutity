from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def test_i18n_avoids_mutation_observer_attribute_feedback_loop():
    js = text('webapi/static/i18n84.js')
    assert "if(el.getAttribute(a)!==next)el.setAttribute(a,next);" in js
    assert "observer.observe(document.body,{subtree:true,childList:true,attributes:true" in js


def test_language_change_handler_is_delegated_and_storage_is_guarded():
    js = text('webapi/static/i18n84.js')
    assert "document.addEventListener('change',e=>" in js
    assert "storageGet('na_language')" in js
    assert "storageSet('na_language',lang)" in js
    assert "try{return window.localStorage?.getItem(key)" in js
    assert "try{window.localStorage?.setItem(key,value)" in js


def test_login_strings_have_english_and_chinese_translations():
    js = text('webapi/static/i18n84.js')
    for source in [
        'Đăng nhập hệ thống',
        'Tài khoản',
        'Mật khẩu',
        'Ví dụ: Admin',
        'Nhập mật khẩu',
        'Đọc trực tiếp IP LAN, gateway, subnet và bảng ARP của Windows',
        'Ping thiết bị trong LAN và hiển thị IP/MAC đã quan sát',
        'Backend chạy cục bộ trên 127.0.0.1',
    ]:
        assert js.count(source) >= 2
    assert 'System sign in' in js
    assert '系统登录' in js


def test_qa85_asset_revision_is_aligned():
    assert "NA_ASSET_VERSION='70405'" in text('webapi/static/app.js')
    assert '/static/i18n84.js?v=70405' in text('webapi/static/index.html')
    assert "ASSET_VERSION='70405'" in text('webapi/runtime37.py')
