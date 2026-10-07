from pathlib import Path
import ast
import re

ROOT=Path(__file__).resolve().parents[1]
I18N=(ROOT/'webapi/static/i18n84.js').read_text(encoding='utf-8')
VI_CHARS=re.compile(r'[ăâđêôơưĂÂĐÊÔƠƯàáảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựỳýỷỹỵÀÁẢÃẠẤẦẨẪẬẮẰẲẴẶÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰỲÝỶỸỴ]')


def test_qa86_asset_revision_and_complete_dom_translation():
    assert "NA_ASSET_VERSION='70405'" in (ROOT/'webapi/static/app.js').read_text(encoding='utf-8')
    assert "ASSET_VERSION='70405'" in (ROOT/'webapi/runtime37.py').read_text(encoding='utf-8')
    assert '/static/i18n84.js?v=70405' in (ROOT/'webapi/static/index.html').read_text(encoding='utf-8')
    assert "return !!p.closest('#login-view,#app,#dialog,#toast');" in I18N
    assert 'const QA86_API_EN=' in I18N and 'const QA86_API_ZH=' in I18N


def test_qa86_screenshot_phrases_are_fully_localized():
    expected=[
        '优先处理今天需要关注的事项','每日安全运维 / 6.9','需处理组','总项目','自动完成','周期',
        '每 5 分钟：在线状态 · 局域网发现 · 告警规则 · 事件/根因分析 · 线路质量 · 数据库备份',
        '优先检查清单','IP、名称、状态…','Priority checklist','Items requiring attention',
        'Danh sách kiểm tra có chế độ tự động hoàn thiện an toàn',
        'Mỗi 5 phút: Trạng thái hiện diện · Khám phá LAN · Quy tắc cảnh báo · Sự cố/RCA · Chất lượng đường truyền · Sao lưu CSDL',
    ]
    for phrase in expected:
        assert phrase in I18N, phrase


def test_qa86_all_webapi_vietnamese_user_messages_are_catalogued():
    missing=[]
    for p in (ROOT/'webapi').rglob('*.py'):
        try:
            tree=ast.parse(p.read_text(encoding='utf-8'))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node,ast.Constant) and isinstance(node.value,str):
                s=node.value.strip()
                if 1 < len(s) <= 500 and VI_CHARS.search(s) and s not in I18N:
                    missing.append((p.relative_to(ROOT).as_posix(),s))
    assert not missing, f'Uncatalogued Vietnamese API/UI messages: {missing[:20]}'


def test_qa86_legacy_english_labels_have_vi_and_zh_canonical_forms():
    for token in [
        "'SOC Dashboard':'Bảng điều khiển SOC'",
        "'Presence':'Trạng thái hiện diện'",
        "'LAN Discovery':'Khám phá LAN'",
        "'Alert Rules':'Quy tắc cảnh báo'",
        "'Incident/RCA':'Sự cố/RCA'",
        "'Line Quality':'Chất lượng đường truyền'",
        "'DB Backup':'Sao lưu CSDL'",
        "'Indicator':'指标'",
        "'Requested by':'申请人'",
        "'Approved by':'审批人'",
    ]:
        assert token in I18N, token


def test_qa86_api_catalog_covers_error_and_status_examples():
    pairs=[
        ('Không tìm thấy thiết bị.','Device not found.','未找到设备。'),
        ('Không đo được latency','Unable to measure latency','无法测量延迟'),
        ('Thiếu thư viện openpyxl. Hãy cài lại ứng dụng rồi thử lại.','The openpyxl library is missing. Reinstall the application and try again.','缺少 openpyxl 库。请重新安装应用后再试。'),
        ('Đã kết nối mạng nội bộ và có đường ra Internet.','The local network is connected and Internet access is available.','本地网络已连接，并且可以访问互联网。'),
    ]
    for vi,en,zh in pairs:
        assert vi in I18N and en in I18N and zh in I18N
