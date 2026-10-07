import sqlite3
from pathlib import Path

from webapi import cybersecurity59 as net


def ident():
    return {'local_ip':'192.168.2.34','gateway':'192.168.2.1','adapter':'Ethernet',
            'mode':'LAN+WAN','source':'WINDOWS_LOCAL','hostname':'QA','endpoint_id':'','checked_at':'now'}


def probe(target, latency, jitter=0.3, loss=0.0):
    return {'target':target,'resolved_ip':'203.0.113.10','samples':6,'replies':6,
            'packet_loss':loss,'latency_ms':latency,'jitter_ms':jitter,
            'errors':[],'method':'TCP_HANDSHAKE_MEDIAN'}


def test_domestic_probe_selects_fastest_reachable(monkeypatch):
    monkeypatch.setattr(net, '_domestic_probe_hosts', lambda: ('slow.vn','fast.vn','dead.vn'))
    values={'slow.vn':30.0,'fast.vn':5.2,'dead.vn':None}
    def fake(host, port=443, samples=6, timeout=2.5):
        v=values[host]
        if v is None:
            return {'target':host,'samples':samples,'replies':0,'packet_loss':100.0,'latency_ms':None,'jitter_ms':None,'errors':['TIMEOUT'],'method':'TCP_HANDSHAKE_MEDIAN'}
        return probe(host,v)
    monkeypatch.setattr(net, '_tcp_latency_series', fake)
    r=net._domestic_latency_probe()
    assert r['target']=='fast.vn'
    assert r['latency_ms']==5.2
    assert r['scope']=='domestic'
    assert len(r['candidates'])==3


def test_domestic_quality_not_pulled_down_by_international_latency(monkeypatch):
    conn=sqlite3.connect(':memory:'); conn.row_factory=sqlite3.Row
    monkeypatch.setattr(net,'connection',lambda:conn)
    monkeypatch.setattr(net,'_primary_network',ident)
    monkeypatch.setattr(net,'_domestic_latency_probe',lambda *a,**k: probe('vnexpress.net',5.4,0.2,0.0))
    monkeypatch.setattr(net,'_tcp_latency_series',lambda *a,**k: probe(net.DEFAULT_SPEED_HOST,189.0,3.0,0.0))
    monkeypatch.setattr(net,'_icmp_series',lambda target,*a,**k: probe(target,1.0 if target=='192.168.2.1' else 188.0,1.0,0.0))
    r=net.run_line_test_internal('qa','domestic')
    assert r['quality_scope']=='domestic'
    assert r['latency_ms']==5.4
    assert r['international_latency_ms']==189.0
    assert r['grade']=='EXCELLENT'
    conn.close()


def test_international_measurement_is_stored_separately(monkeypatch):
    conn=sqlite3.connect(':memory:'); conn.row_factory=sqlite3.Row
    monkeypatch.setattr(net,'connection',lambda:conn)
    monkeypatch.setattr(net,'_primary_network',ident)
    monkeypatch.setattr(net,'_tcp_latency_series',lambda *a,**k: probe(net.DEFAULT_SPEED_HOST,189.0,3.0,0.0))
    monkeypatch.setattr(net,'_icmp_series',lambda target,*a,**k: probe(target,188.0,2.0,0.0))
    r=net.run_line_test_internal('qa','international')
    assert r['quality_scope']=='international'
    assert r['latency_ms']==189.0
    net.ensure_tables59()
    row=conn.execute("SELECT * FROM network_quality59 WHERE test_type='LINE_INTL'").fetchone()
    assert row['international_latency_ms']==189.0
    conn.close()


def test_diagnostics_grade_uses_domestic_even_when_cdn_is_slow(monkeypatch):
    conn=sqlite3.connect(':memory:'); conn.row_factory=sqlite3.Row
    monkeypatch.setattr(net,'connection',lambda:conn)
    monkeypatch.setattr(net,'_primary_network',ident)
    monkeypatch.setattr(net,'_domestic_latency_probe',lambda *a,**k: probe('fpt.vn',5.0,0.2,0.0))
    monkeypatch.setattr(net,'_tcp_latency_series',lambda *a,**k: probe(net.DEFAULT_SPEED_HOST,190.0,4.0,0.0))
    monkeypatch.setattr(net,'_icmp_series',lambda target,*a,**k: probe(target,1.0 if target=='192.168.2.1' else 190.0,1.0,0.0))
    monkeypatch.setattr(net,'_dns_probe',lambda *a,**k:{'ok':True,'host':net.DEFAULT_SPEED_HOST,'addresses':['1.1.1.1'],'elapsed_ms':5})
    monkeypatch.setattr(net,'_tcp_probe',lambda *a,**k:{'ok':True,'host':net.DEFAULT_SPEED_HOST,'port':443,'elapsed_ms':190})
    monkeypatch.setattr(net,'_https_probe',lambda *a,**k:{'ok':True,'status':200,'elapsed_ms':210})
    r=net._network_diagnostics('qa')
    assert r['overall']=='GOOD'
    assert r['metrics']['domestic_latency_ms']==5.0
    assert r['metrics']['international_latency_ms']==190.0
    checks={x['key']:x for x in r['checks']}
    assert checks['domestic_latency']['status']=='OK'
    assert checks['international_latency']['status']=='INFO'
    conn.close()


def test_speed_test_reports_domestic_and_international_separately(monkeypatch):
    conn=sqlite3.connect(':memory:'); conn.row_factory=sqlite3.Row
    monkeypatch.setattr(net,'connection',lambda:conn)
    monkeypatch.setattr(net,'_primary_network',ident)
    monkeypatch.setattr(net,'require_role',lambda request,*roles:{'username':'qa'})
    monkeypatch.setattr(net,'_domestic_latency_probe',lambda *a,**k: probe('vnexpress.net',5.6,0.2,0.0))
    monkeypatch.setattr(net,'_tcp_latency_series',lambda *a,**k: probe(net.DEFAULT_SPEED_HOST,188.5,2.5,0.0))
    monkeypatch.setattr(net,'_download_test',lambda *a,**k:{'mbps':470.2,'megabytes':64.0,'streams':4,'seconds':2.0})
    monkeypatch.setattr(net,'_upload_test',lambda *a,**k:{'mbps':484.1,'megabytes':32.0,'streams':4,'seconds':1.0})
    payload=net.SpeedTestIn(download_mb=32,upload_mb=12,run_upload=True,confirm_bandwidth_use=True)
    r=net.speed_test(payload,None)
    assert r['latency_ms']==5.6
    assert r['international_latency_ms']==188.5
    assert r['grade']=='EXCELLENT'
    assert r['download_mbps']==470.2 and r['upload_mbps']==484.1
    conn.close()


def test_summary_prefers_domestic_quality_and_keeps_international_reference(monkeypatch):
    conn=sqlite3.connect(':memory:'); conn.row_factory=sqlite3.Row
    monkeypatch.setattr(net,'connection',lambda:conn)
    monkeypatch.setattr(net,'_primary_network',ident)
    monkeypatch.setattr(net,'require_role',lambda request,*roles:{'username':'qa'})
    net.ensure_tables59()
    net._store('LINE','qa',ident(),{**probe('vnexpress.net',5.0),'grade':'EXCELLENT','quality_scope':'domestic','quality_target':'vnexpress.net','detail':'quality_scope=domestic'})
    net._store('LINE_INTL','qa',ident(),{**probe(net.DEFAULT_SPEED_HOST,190.0),'grade':'POOR','quality_scope':'international','quality_target':net.DEFAULT_SPEED_HOST,'international_latency_ms':190.0,'detail':'quality_scope=international'})
    r=net.summary(None)
    assert r['display_quality']['quality_scope']=='domestic'
    assert r['display_quality']['latency_ms']==5.0
    assert r['latest_international']['latency_ms']==190.0
    conn.close()


def test_ui_makes_domestic_default_and_international_explicit():
    root=Path(__file__).resolve().parents[1]
    js=(root/'webapi/static/cybersecurity51.js').read_text(encoding='utf-8')
    assert "button('Kiểm tra trong nước','line-test59'" in js
    assert "button('Kiểm tra quốc tế','intl-line-test59'" in js
    assert "scope:'domestic'" in js and "scope:'international'" in js
    assert 'Độ trễ trong nước' in js and 'Độ trễ quốc tế / CDN' in js
    assert 'Chất lượng tuyến trong nước' in js


def test_i18n_covers_new_domestic_route_labels():
    root=Path(__file__).resolve().parents[1]
    text=(root/'webapi/static/i18n84.js').read_text(encoding='utf-8')
    for term in ['Kiểm tra trong nước','Kiểm tra quốc tế','Độ trễ trong nước','Độ trễ quốc tế / CDN','Chất lượng tuyến trong nước']:
        assert text.count("'"+term+"'") >= 2
