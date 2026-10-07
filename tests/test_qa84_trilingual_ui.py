from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(rel):
    return (ROOT / rel).read_text(encoding='utf-8')

def test_i18n_asset_loaded_before_app():
    index = text('webapi/static/index.html')
    assert '/static/i18n84.js?v=70405' in index
    assert '/static/app.js?v=70405' in index
    assert index.index('/static/i18n84.js?v=70405') < index.index('/static/app.js?v=70405')

def test_three_language_selectors_present_on_login_and_app():
    index = text('webapi/static/index.html')
    assert 'id="language-select-login"' in index
    assert 'id="language-select-header"' in index
    js = text('webapi/static/i18n84.js')
    assert "vi:{label:'🇻🇳 Tiếng Việt'" in js
    assert "zh:{label:'🇨🇳 中文（简体）'" in js
    assert "en:{label:'🇬🇧 English'" in js

def test_language_preference_is_persistent_and_local_only():
    js = text('webapi/static/i18n84.js')
    assert "localStorage?.getItem(key)" in js
    assert "localStorage?.setItem(key,value)" in js
    assert 'fetch(' not in js
    assert 'XMLHttpRequest' not in js

def test_dynamic_ui_translation_uses_mutation_observer_and_preserves_raw_outputs():
    js = text('webapi/static/i18n84.js')
    assert 'new MutationObserver' in js
    assert "pre,code,kbd,samp,textarea" in js
    assert '.terminal-output' in js
    assert "originalText=new WeakMap()" in js

def test_clock_uses_selected_locale():
    app = text('webapi/static/app.js')
    assert "window.naLocale?window.naLocale():'vi-VN'" in app
    assert "document.addEventListener('na:language-changed'" in app

def test_common_navigation_and_network_labels_have_chinese_and_english_translations():
    js = text('webapi/static/i18n84.js')
    for source in ['TỔNG QUAN','THIẾT BỊ & HẠ TẦNG','VẬN HÀNH & PHẢN ỨNG','QUẢN TRỊ','Tốc độ & Đường truyền','Kiểm tra mạng chi tiết','Đo tốc độ Internet','Windows Local Tools · Mũ trắng','Windows Local Lab · Mũ đỏ']:
        assert source in js
    assert '网速与线路质量' in js
    assert 'Speed & Connection Quality' in js

def test_language_selector_css_exists():
    css = text('webapi/static/style.css')
    assert '.language-select' in css
    assert '.login-card-controls' in css
