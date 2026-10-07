"""Central deny-by-default API authorization and revocable, expiring sessions."""
from __future__ import annotations
import hashlib
import logging
import os
import re
import secrets
import time
from urllib.parse import urlsplit
from fastapi import HTTPException, Request, Response
from starlette.responses import JSONResponse
from webapi.runtime37 import connection, utcnow

COOKIE = 'na_session'
ABSOLUTE_TTL = 8 * 3600
IDLE_TTL = 30 * 60
PUBLIC = {'/api/health', '/api/auth/login'}
ADMIN_PREFIXES = ('/api/v46', '/api/v43', '/api/v41', '/api/credentials', '/api/device-credentials', '/api/snmpv3/credentials', '/api/ssh/known-hosts', '/api/accounts', '/api/diagnostics', '/api/security-log', '/api/audit-log', '/api/connection-profiles', '/api/snmpv3/assignments')
OPERATOR_GET = ('/api/operations', '/api/autoip', '/api/ssh-audit', '/api/config-backups', '/api/ssh/hostkey', '/api/jobs')
# Read operations above still require login. Unrecognised writes are refused even for Admin.
WRITE_RULES = [
 ('POST',r'/api/devices/\d+/manage',('Admin',)),
 ('POST',r'/api/connection-profiles',('Admin',)),
 ('DELETE',r'/api/connection-profiles/[^/]+',('Admin',)),
 ('POST',r'/api/autoip/targets/[^/]+/profile',('Admin',)),
 ('POST', r'/api/auth/logout', ('Admin','Analyst','Operator','Viewer')),
 ('POST', r'/api/auth/password', ('Admin','Analyst','Operator','Viewer')),
 ('POST', r'/api/devices', ('Admin',)),
 ('PUT|DELETE', r'/api/devices/\d+', ('Admin',)),
 ('POST', r'/api/devices/(\d+/ping|refresh-status)', ('Admin','Operator')),
 ('POST', r'/api/scan', ('Admin',)),
 ('POST', r'/api/scan-results/\d+/import', ('Admin',)),
 ('PUT', r'/api/v69/router-api/config', ('Admin',)),
 ('POST', r'/api/v69/router-api/test', ('Admin','Operator')),
 ('POST', r'/api/v69/router-api/import', ('Admin',)),
 ('POST', r'/api/alerts/\d+/(close|reopen)', ('Admin','Operator')),
 ('POST', r'/api/server-targets', ('Admin',)),
 ('PUT|DELETE', r'/api/server-targets/\d+', ('Admin',)),
 ('POST', r'/api/server-monitor/run', ('Admin','Operator')),
 ('POST', r'/api/database/backup', ('Admin',)),
 ('POST', r'/api/autoip/(start|stop)', ('Admin',)),
 ('POST', r'/api/snmp/device/\d+/refresh', ('Admin','Operator')),
 ('POST', r'/api/ssh-audit/\d+', ('Admin',)),
 ('POST', r'/api/config-backup/\d+', ('Admin',)),
 ('POST', r'/api/desktop/export-directory', ('Admin','Analyst','Operator')),
 ('POST', r'/api/reports/export', ('Admin','Operator')),
 ('POST', r'/api/reports/csv', ('Admin','Analyst','Operator')),
 ('POST', r'/api/reports/xlsx', ('Admin','Analyst','Operator')),
 ('POST|PUT|DELETE', r'/api/credentials(/\d+)?', ('Admin',)),
 ('POST|DELETE', r'/api/devices/\d+/credential(/[A-Za-z]+)?', ('Admin',)),
 ('POST', r'/api/devices/\d+/ssh-test', ('Admin','Operator')),
 ('POST', r'/api/ssh/hostkey/\d+/trust', ('Admin',)),
 ('POST|PUT|DELETE', r'/api/snmpv3/credentials(/\d+)?', ('Admin',)),
 ('POST|DELETE', r'/api/devices/\d+/snmpv3', ('Admin',)),
 ('POST', r'/api/autoip/profiles', ('Admin',)),
 ('POST', r'/api/autoip/target-profile', ('Admin',)),
 ('POST', r'/api/operations/(ssh-test|snmp-test)', ('Admin','Operator')),
 ('POST', r'/api/operations/(audit|backup)', ('Admin',)),
 ('POST', r'/api/jobs', ('Admin','Operator')),
 ('POST', r'/api/jobs/\d+/cancel', ('Admin','Operator')),
 ('POST', r'/api/v45/ipmac/delete-many', ('Admin','Operator')),
 ('POST', r'/api/v45/ipmac/delete-all', ('Admin',)),
 ('POST|PUT|DELETE', r'/api/accounts(/\d+)?', ('Admin',)),
 ('POST', r'/api/accounts/\d+/reset-password', ('Admin',)),
 ('POST', r'/api/v4/topology/dependencies', ('Admin',)),
 ('DELETE', r'/api/v4/topology/dependencies/\d+', ('Admin',)),
 ('POST', r'/api/v4/sla', ('Admin',)),
 ('PUT|DELETE', r'/api/v4/sla/\d+', ('Admin',)),
 ('POST', r'/api/v4/maintenance', ('Admin',)),
 ('PUT|DELETE', r'/api/v4/maintenance/\d+', ('Admin',)),
 ('POST', r'/api/v4/organization/(sites|groups)', ('Admin',)),
 ('PUT|DELETE', r'/api/v4/organization/(sites|groups)/\d+', ('Admin',)),
 ('PUT', r'/api/v4/organization/devices/\d+', ('Admin',)),
 ('POST', r'/api/v4/incidents/sync', ('Admin','Operator')),
 ('PUT', r'/api/v4/incidents/\d+', ('Admin','Operator')),
 ('POST', r'/api/v4/cameras', ('Admin',)),
 ('PUT|DELETE', r'/api/v4/cameras/\d+', ('Admin',)),
 ('POST', r'/api/v4/restore/prepare', ('Admin',)),
 ('POST', r'/api/v4/schedules', ('Admin',)),
 ('PUT|DELETE', r'/api/v4/schedules/\d+', ('Admin',)),
 ('POST', r'/api/v4/schedules/\d+/run', ('Admin','Operator')),
 ('PUT', r'/api/v41/retention', ('Admin',)),
 ('POST', r'/api/v41/retention/apply', ('Admin',)),
 ('POST', r'/api/v41/disaster-recovery/export', ('Admin',)),
 ('POST', r'/api/v42/lan/probe', ('Admin','Operator')),
 ('POST|PUT|DELETE', r'/api/v42/snmpv2/credentials(/\d+)?', ('Admin',)),
 ('POST', r'/api/v42/snmpv2/assign', ('Admin',)),
 ('DELETE', r'/api/v42/snmpv2/assign/\d+', ('Admin',)),
 ('POST', r'/api/v42/ssh/assign', ('Admin',)),
 # v4.4 desktop operations. Keep central deny-by-default guard aligned with endpoint RBAC.
 ('POST', r'/api/v44/profiles', ('Admin',)),
 ('PUT|DELETE', r'/api/v44/profiles/\d+', ('Admin',)),
 ('POST', r'/api/v44/profiles/assign', ('Admin','Operator')),
 ('DELETE', r'/api/v44/profiles/assign/\d+', ('Admin','Operator')),
 ('POST', r'/api/v44/profiles/auto-detect/\d+', ('Admin','Operator')),
 ('POST', r'/api/v44/drivers', ('Admin',)),
 ('PUT|DELETE', r'/api/v44/drivers/\d+', ('Admin',)),
 ('POST', r'/api/v44/drivers/assign', ('Admin','Operator')),
 ('DELETE', r'/api/v44/drivers/assign/\d+', ('Admin','Operator')),
 ('POST', r'/api/v44/drivers/auto-detect/\d+', ('Admin','Operator')),
 ('POST', r'/api/v44/monitoring/(resource|interfaces)/\d+', ('Admin','Operator')),
 ('POST', r'/api/v44/alert-rules', ('Admin','Operator')),
 ('PUT|DELETE', r'/api/v44/alert-rules/\d+', ('Admin','Operator')),
 ('POST', r'/api/v44/alert-rules/evaluate', ('Admin','Operator')),
 ('PUT', r'/api/v44/notifications', ('Admin',)),
 ('POST', r'/api/v44/notifications/test', ('Admin',)),
 ('POST', r'/api/v44/services', ('Admin','Operator')),
 ('PUT|DELETE', r'/api/v44/services/\d+', ('Admin','Operator')),
 ('PUT', r'/api/v44/services/\d+/members', ('Admin','Operator')),
 ('POST', r'/api/v44/manual-backups', ('Admin',)),
 ('POST', r'/api/v44/config-compare', ('Admin','Operator')),
 ('POST', r'/api/v44/config-posture', ('Admin','Operator')),
 ('POST', r'/api/v44/baselines/from-backup', ('Admin',)),
 ('DELETE', r'/api/v44/baselines/[^/]+', ('Admin',)),
 ('PUT', r'/api/v44/settings', ('Admin',)),
 ('POST', r'/api/v44/remote/\d+/check', ('Admin','Operator')),
 ('POST', r'/api/v44/daily-audit/run', ('Admin','Operator')),
 # v5.1 Cybersecurity Center: analysts can investigate and run bounded defensive checks.
 ('POST', r'/api/v51/siem/events', ('Admin','Analyst','Operator')),
 ('POST', r'/api/v51/vulnerability/scan', ('Admin','Analyst','Operator')),
 ('POST', r'/api/v51/vulnerability/cve/lookup', ('Admin','Analyst')),
 ('POST', r'/api/v51/threat/hash-lookup', ('Admin','Analyst')),
 ('POST', r'/api/v51/crypto/(encrypt|decrypt)', ('Admin','Analyst','Operator','Viewer')),
 ('POST', r'/api/v51/password-strength', ('Admin','Analyst','Operator','Viewer')),
 ('POST', r'/api/v51/tls/check', ('Admin','Analyst','Operator')),
 ('PUT', r'/api/v51/settings', ('Admin',)),
 ('POST', r'/api/v51/alerts/\d+/ack', ('Admin','Analyst','Operator')),
 ('POST', r'/api/v51/alerts/\d+/(resolve|reopen)', ('Admin','Analyst')),
 ('POST', r'/api/v51/vault', ('Admin',)),
 ('POST', r'/api/v51/vault/\d+/reveal', ('Admin',)),
 ('DELETE', r'/api/v51/vault/\d+', ('Admin',)),
 # v5.3 Compliance / approval-only response workflow.
 ('PATCH', r'/api/v51/compliance/\d+', ('Admin','Analyst')),
 ('POST', r'/api/v51/playbooks', ('Admin','Analyst','Operator')),
 ('POST', r'/api/v51/playbooks/\d+/approve', ('Admin',)),
 ('POST', r'/api/v51/playbooks/\d+/cancel', ('Admin','Analyst')),
 # v5.4 defensive IOC watchlist and custom SIEM detection rules.
 ('POST', r'/api/v54/threat/iocs', ('Admin','Analyst')),
 ('POST', r'/api/v54/threat/iocs/\d+/toggle', ('Admin','Analyst')),
 ('DELETE', r'/api/v54/threat/iocs/\d+', ('Admin',)),
 ('POST', r'/api/v54/detection-rules', ('Admin','Analyst')),
 ('POST', r'/api/v54/detection-rules/\d+/toggle', ('Admin','Analyst')),
 ('DELETE', r'/api/v54/detection-rules/\d+', ('Admin',)),
 # v5.5 enterprise SOC case workflow.
 ('POST', r'/api/v55/cases', ('Admin','Analyst')),
 ('PATCH', r'/api/v55/cases/\d+', ('Admin','Analyst')),
 ('POST', r'/api/v55/cases/\d+/notes', ('Admin','Analyst','Operator')),
 ('POST', r'/api/v55/cases/\d+/alerts', ('Admin','Analyst','Operator')),
 # v5.6 enterprise notifications and report snapshots.
 ('POST', r'/api/v56/notifications/test', ('Admin',)),
 ('POST', r'/api/v56/alerts/\d+/notify', ('Admin','Analyst')),
 ('POST', r'/api/v56/reports/snapshots', ('Admin','Analyst')),
 # v5.7 daily security operations checklist.
 ('POST', r'/api/v57/daily/reviewed', ('Admin','Analyst','Operator')),
 # v5.9 network quality and explicit bandwidth diagnostics.
 ('POST', r'/api/v59/network/line-test', ('Admin','Analyst','Operator')),
 ('POST', r'/api/v59/network/diagnostics', ('Admin','Analyst','Operator')),
 ('POST', r'/api/v59/network/speed-test', ('Admin','Analyst','Operator')),
 ('POST', r'/api/v59/network/optimize', ('Admin',)),
 # QA79 Windows-local defensive and authorized diagnostic profiles.
 ('POST', r'/api/v1/windows-tools/run', ('Admin','Analyst','Operator')),
 ('POST', r'/api/v50/network/connectivity/probe', ('Admin','Operator')),
 ('POST', r'/api/v50/network/identity/refresh', ('Admin','Operator')),
 ('POST', r'/api/v46/diagnostics/export', ('Admin',)),
 ('POST', r'/api/v47/diagnostics/export', ('Admin',)),
 ('POST', r'/api/v45/remote/\d+/rdp-export', ('Admin','Operator')),
]

def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()

def ensure_tables():
    with connection() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS web_sessions37(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL,password_stamp TEXT NOT NULL,csrf TEXT NOT NULL,issued REAL NOT NULL,last_used REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS web_login_attempts37(id INTEGER PRIMARY KEY,username TEXT,peer TEXT,success INTEGER,at REAL);
        CREATE INDEX IF NOT EXISTS ix_web_login_attempts_time ON web_login_attempts37(at);
        CREATE INDEX IF NOT EXISTS ix_web_login_attempts_user_time ON web_login_attempts37(username COLLATE NOCASE,at);
        CREATE INDEX IF NOT EXISTS ix_web_login_attempts_peer_time ON web_login_attempts37(peer,at);
        CREATE TABLE IF NOT EXISTS web_security_log37(id INTEGER PRIMARY KEY,actor TEXT,method TEXT,path TEXT,status INTEGER,request_id TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS web_mfa_challenges51(
            token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL,purpose TEXT NOT NULL,issued REAL NOT NULL,expires REAL NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,last_attempt REAL DEFAULT NULL
        );
        CREATE TABLE IF NOT EXISTS web_security_policy51(
            id INTEGER PRIMARY KEY CHECK(id=1),mfa_required INTEGER NOT NULL DEFAULT 1,updated_at TEXT
        );
        ''')
        mfa_cols={r['name'] for r in c.execute('PRAGMA table_info(web_mfa_challenges51)').fetchall()}
        if 'attempts' not in mfa_cols: c.execute('ALTER TABLE web_mfa_challenges51 ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0')
        if 'last_attempt' not in mfa_cols: c.execute('ALTER TABLE web_mfa_challenges51 ADD COLUMN last_attempt REAL DEFAULT NULL')
        # Additive migration for MFA state; secrets are encrypted with the existing credential vault key.
        cols={r['name'] for r in c.execute('PRAGMA table_info(app_users)').fetchall()}
        if 'mfa_enabled' not in cols: c.execute('ALTER TABLE app_users ADD COLUMN mfa_enabled INTEGER DEFAULT 0')
        if 'mfa_secret_enc' not in cols: c.execute('ALTER TABLE app_users ADD COLUMN mfa_secret_enc TEXT DEFAULT NULL')
        if 'mfa_updated_at' not in cols: c.execute('ALTER TABLE app_users ADD COLUMN mfa_updated_at TEXT DEFAULT NULL')
        # MFA was removed from Desktop 7.0.3 at user request. Keep the legacy
        # columns/tables only so older databases migrate safely, but disable all
        # enrollment/challenges and clear legacy secrets.
        c.execute("INSERT OR IGNORE INTO web_security_policy51(id,mfa_required,updated_at) VALUES(1,0,datetime('now'))")
        c.execute("UPDATE web_security_policy51 SET mfa_required=0,updated_at=datetime('now') WHERE id=1")
        c.execute("DELETE FROM web_mfa_challenges51")
        c.execute("UPDATE app_users SET mfa_enabled=0,mfa_secret_enc=NULL WHERE COALESCE(mfa_enabled,0)<>0 OR mfa_secret_enc IS NOT NULL")

def public_user(row):
    return {k:row[k] for k in ('id','username','role','enabled')}

def _session_tokens(request: Request):
    """Return every candidate session cookie in wire order.

    Older local builds sometimes left more than one na_session cookie in the
    browser after update/recovery.  Starlette's parsed cookie dict keeps only
    one value, so a stale duplicate could make a freshly issued valid session
    look logged out immediately.  Desktop local sessions accept the first valid candidate
    and ignores malformed/stale duplicates.
    """
    values=[]
    raw=request.headers.get('cookie','') or ''
    for item in raw.split(';'):
        name,sep,value=item.strip().partition('=')
        if sep and name==COOKIE and value and len(value)<=256 and value not in values:
            values.append(value)
    parsed=request.cookies.get(COOKIE,'')
    if parsed and len(parsed)<=256 and parsed not in values:
        values.append(parsed)
    return values

def session(request: Request):
    tokens=_session_tokens(request)
    if not tokens: return None
    now = time.time()
    with connection() as c:
        for token in tokens:
            r = c.execute('''SELECT s.*,u.username,u.role,u.enabled,u.password_hash FROM web_sessions37 s
                             JOIN app_users u ON u.id=s.user_id WHERE s.token_hash=?''',(digest(token),)).fetchone()
            if not r:
                continue
            if not r['enabled'] or now-r['issued']>ABSOLUTE_TTL or now-r['last_used']>IDLE_TTL or not secrets.compare_digest(r['password_stamp'],digest(r['password_hash'])):
                c.execute('DELETE FROM web_sessions37 WHERE token_hash=?',(digest(token),))
                continue
            token_hash=digest(token)
            if now-r['last_used']>30: c.execute('UPDATE web_sessions37 SET last_used=? WHERE token_hash=?',(now,token_hash))
            # Keep the canonical authenticated session binding on request state; callers
            # must not re-parse a possibly duplicated Cookie header themselves.
            request.state.session_hash=token_hash
            return {'id':r['user_id'],'username':r['username'],'role':r['role'],'enabled':r['enabled'],'csrf_token':r['csrf']}
    return None

def session_binding(request: Request) -> str:
    binding=getattr(request.state,'session_hash','')
    if binding:
        return binding
    if not session(request):
        return ''
    return getattr(request.state,'session_hash','')

def require_role(request: Request, *roles):
    u=getattr(request.state,'user',None) or session(request)
    if not u: raise HTTPException(401,'LOGIN_REQUIRED')
    if roles and u['role'] not in roles: raise HTTPException(403,'PERMISSION_DENIED')
    return u

def _is_loopback_request(request: Request) -> bool:
    """True only for the local browser path explicitly supported without TLS."""
    peer=(request.client.host if request.client else '').strip().lower()
    host=(request.url.hostname or '').strip().lower()
    loop={'127.0.0.1','::1','localhost'}
    if peer=='testclient':
        return True
    return peer in loop and host in loop


def _remote_https_required(c=None) -> bool:
    """Read the persisted remote-session policy; fail secure on any schema/read error."""
    try:
        if c is not None:
            exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='security_settings51'").fetchone()
            if not exists:
                return True
            row=c.execute('SELECT remote_https_required FROM security_settings51 WHERE id=1').fetchone()
            return True if row is None else bool(row[0])
        with connection() as conn:
            return _remote_https_required(conn)
    except Exception:
        return True


def _finish_login(c,row,request,response):
    now=time.time()
    for old in _session_tokens(request):
        c.execute('DELETE FROM web_sessions37 WHERE token_hash=?',(digest(old),))
    token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
    c.execute('DELETE FROM web_sessions37 WHERE issued<? OR last_used<?',(now-ABSOLUTE_TTL,now-IDLE_TTL))
    c.execute('INSERT INTO web_sessions37 VALUES(?,?,?,?,?,?)',(digest(token),row['id'],digest(row['password_hash']),csrf,now,now))
    # Loopback HTTP is intentionally supported for the local desktop UI.  Any
    # non-loopback deployment must use HTTPS, so a remotely usable session is
    # never issued as a non-Secure cookie.
    scheme=str(request.url.scheme).lower()
    if scheme!='https' and not _is_loopback_request(request):
        required=_remote_https_required(c)
        allow_insecure=(not required and os.environ.get('NA_ALLOW_REMOTE_HTTP','0')=='1')
        if not allow_insecure:
            c.execute('DELETE FROM web_sessions37 WHERE token_hash=?',(digest(token),))
            raise HTTPException(403,'HTTPS_REQUIRED_FOR_REMOTE_SESSION')
    cookie_secure=(scheme=='https')
    response.set_cookie(COOKIE,token,httponly=True,secure=cookie_secure,samesite='strict',path='/',max_age=ABSOLUTE_TTL)
    return {'success':True,'user':public_user(row),'csrf_token':csrf}




def login(username: str,password: str,request: Request,response: Response):
    from modules.nms_v5 import _verify_password, _hash_password
    username=username.strip()
    if not 1<=len(username)<=64 or password=='': raise HTTPException(401,'INVALID_CREDENTIALS')
    ensure_tables(); now=time.time(); peer=request.client.host if request.client else 'unknown'
    with connection() as c:
        c.execute('DELETE FROM web_login_attempts37 WHERE at<?',(now-86400,))
        n=c.execute('SELECT COUNT(*) FROM web_login_attempts37 WHERE at>? AND success=0 AND username=? COLLATE NOCASE',(now-900,username)).fetchone()[0]
        # Keep a peer-wide spray budget even on localhost.  Desktop browsers share
        # 127.0.0.1, so the local threshold is intentionally a little higher, but a
        # local process still cannot try unlimited usernames.
        ipn=c.execute('SELECT COUNT(*) FROM web_login_attempts37 WHERE at>? AND success=0 AND peer=?',(now-60,peer)).fetchone()[0]
        peer_limit=60 if _is_loopback_request(request) else 30
        if n>=5:
            oldest=c.execute('SELECT MIN(at) FROM web_login_attempts37 WHERE at>? AND success=0 AND username=? COLLATE NOCASE',(now-900,username)).fetchone()[0] or now
            retry=max(1,int(900-(now-float(oldest))))
            raise HTTPException(429,'LOGIN_RATE_LIMITED; too many failed attempts',headers={'Retry-After':str(retry)})
        if ipn>=peer_limit:
            oldest=c.execute('SELECT MIN(at) FROM web_login_attempts37 WHERE at>? AND success=0 AND peer=?',(now-60,peer)).fetchone()[0] or now
            retry=max(1,int(60-(now-float(oldest))))
            raise HTTPException(429,'LOGIN_RATE_LIMITED; too many failed attempts',headers={'Retry-After':str(retry)})
        # New builds prevent case-insensitive duplicates.  For legacy databases
        # that already contain both e.g. Alice/alice, exact-case login remains
        # usable so an Admin can repair the duplicate instead of locking both out.
        exact=c.execute('SELECT * FROM app_users WHERE username=? ORDER BY id',(username,)).fetchall()
        if len(exact)==1:
            r=exact[0]
        else:
            rows=c.execute('SELECT * FROM app_users WHERE username=? COLLATE NOCASE ORDER BY id',(username,)).fetchall()
            r=rows[0] if len(rows)==1 else None
        stored=r['password_hash'] if r else _DUMMY_HASH
        good=_verify_password(password,stored) and bool(r and r['enabled'])
        c.execute('INSERT INTO web_login_attempts37(username,peer,success,at) VALUES(?,?,?,?)',(username,peer,int(good),now))
        if not good:
            c.commit(); raise HTTPException(401,'INVALID_CREDENTIALS')
        # Transparent PBKDF2 -> Argon2id migration after a successful password check.
        if not str(r['password_hash']).startswith('$argon2'):
            upgraded=_hash_password(password)
            c.execute('UPDATE app_users SET password_hash=?,updated_at=datetime(\'now\') WHERE id=?',(upgraded,r['id']))
            r=c.execute('SELECT * FROM app_users WHERE id=?',(r['id'],)).fetchone()
        result=_finish_login(c,r,request,response); c.commit(); return result


# Constant-format PBKDF2 hash only for equal-cost failed verification; not an account.
_DUMMY_HASH='pbkdf2_sha256$240000$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='

def logout(request:Request,response:Response):
    # Revoke every same-name cookie candidate.  Older builds could leave a stale
    # duplicate cookie beside the valid one; deleting only request.cookies[...] 
    # could revoke the wrong token while the real session stayed active.
    tokens=_session_tokens(request)
    with connection() as c:
        for token in tokens:
            c.execute('DELETE FROM web_sessions37 WHERE token_hash=?',(digest(token),))
    response.delete_cookie(COOKIE,path='/')
    return {'success':True}

def allowed_roles(method,path):
    if method in ('GET','HEAD'):
        if path.startswith(ADMIN_PREFIXES): return ('Admin',)
        if path.startswith(OPERATOR_GET): return ('Admin','Operator')
        return ('Admin','Analyst','Operator','Viewer')
    for methods,pattern,roles in WRITE_RULES:
        if re.fullmatch(methods,method) and re.fullmatch(pattern,path): return roles
    return ()

_RATE_LOCK = __import__('threading').Lock()
_RATE_BUCKETS = {}

def _env_rate_limit(name, default):
    raw=os.environ.get(name,str(default))
    try:
        value=int(raw)
    except (TypeError,ValueError):
        logging.getLogger('desktop.security').warning('Invalid %s=%r; using %s',name,raw,default)
        return default
    if not 1 <= value <= 100000:
        logging.getLogger('desktop.security').warning('Out-of-range %s=%r; using %s',name,raw,default)
        return default
    return value

def _rate_check(peer, method, path):
    # Lightweight in-process protection. Reverse-proxy/WAF rate limiting is still recommended for remote deployment.
    # Test/offline QA may explicitly disable this with NA_API_RATE_LIMIT=0.
    if os.environ.get('NA_API_RATE_LIMIT','1') == '0':
        return
    now=time.time(); window=60.0
    limit=_env_rate_limit('NA_API_READS_PER_MIN',600) if method in ('GET','HEAD','OPTIONS') else _env_rate_limit('NA_API_WRITES_PER_MIN',180)
    key=(peer, 'read' if method in ('GET','HEAD','OPTIONS') else 'write')
    with _RATE_LOCK:
        start,count=_RATE_BUCKETS.get(key,(now,0))
        if now-start>=window: start,count=now,0
        count+=1; _RATE_BUCKETS[key]=(start,count)
        if len(_RATE_BUCKETS)>4096:
            for k,(st,_) in list(_RATE_BUCKETS.items()):
                if now-st>120: _RATE_BUCKETS.pop(k,None)
    if count>limit: raise HTTPException(429,'API_RATE_LIMITED',headers={'Retry-After':'60'})

def install(app):
    @app.middleware('http')
    async def guard(request:Request,call_next):
        started=time.monotonic()
        request_id=secrets.token_hex(8); request.state.request_id=request_id
        path=request.url.path; user=None
        try:
            peer=request.client.host if request.client else 'unknown'
            _rate_check(peer,request.method,path)
            if '..' in path or '%2e%2e' in path.lower():
                raise HTTPException(404,'Static asset not found') if path.startswith('/static/') else HTTPException(400,'INVALID_PATH')
            if path.startswith('/api/') or path in ('/docs','/redoc','/openapi.json'):
                # Plain HTTP is supported only for the local desktop browser.
                # Remote sessions must use HTTPS; never downgrade a remote cookie
                # merely because the current request arrived over http://.
                if str(request.url.scheme).lower()!='https' and not _is_loopback_request(request):
                    required=_remote_https_required()
                    if required or os.environ.get('NA_ALLOW_REMOTE_HTTP','0')!='1':
                        raise HTTPException(403,'HTTPS_REQUIRED_FOR_REMOTE_SESSION')
                if request.method not in ('GET','HEAD','OPTIONS'):
                    origin=request.headers.get('origin')
                    if origin:
                        u=urlsplit(origin)
                        if u.scheme!=request.url.scheme or u.netloc!=request.url.netloc: raise HTTPException(403,'ORIGIN_REJECTED')
                    if request.headers.get('sec-fetch-site')=='cross-site': raise HTTPException(403,'ORIGIN_REJECTED')
                if path not in PUBLIC:
                    user=session(request)
                    if not user: raise HTTPException(401,'LOGIN_REQUIRED')
                    request.state.user=user
                    roles=allowed_roles(request.method,path)
                    if user['role'] not in roles: raise HTTPException(403,'PERMISSION_DENIED')
                    if request.method not in ('GET','HEAD','OPTIONS'):
                        if not secrets.compare_digest(request.headers.get('x-csrf-token',''),user['csrf_token']): raise HTTPException(403,'CSRF_REJECTED')
                if request.method in ('POST','PUT','PATCH'):
                    length=request.headers.get('content-length')
                    limit = 12*1024*1024 if path in ('/api/v45/autoip/import','/api/v45/inventory/import','/api/v45/ping/import') else 3*1024*1024 if path in ('/api/reports/csv','/api/reports/xlsx') else 1024*1024 if path in ('/api/v45/autoip/targets','/api/v45/ping/targets') else 65536
                    if length is not None and (not length.isdigit() or int(length)>limit): raise HTTPException(413,'REQUEST_TOO_LARGE')
                    body=await request.body()
                    if len(body)>limit: raise HTTPException(413,'REQUEST_TOO_LARGE')
                    # Validate the body actually received, not only Content-Length.
                    if body and request.headers.get('content-type','').split(';')[0].strip().lower()!='application/json': raise HTTPException(415,'JSON_REQUIRED')
            response=await call_next(request)
        except HTTPException as e:
            response=JSONResponse({'detail':e.detail,'request_id':request_id},status_code=e.status_code,headers=e.headers)
        except Exception as e:
            # Log only exception type / correlation id, not credentials or SQL values.
            logging.getLogger('desktop.security').error('request=%s type=%s',request_id,type(e).__name__)
            response=JSONResponse({'detail':'INTERNAL_ERROR; check local logs','request_id':request_id},status_code=500)
        connect_src="'self'"
        security_headers={
            'X-Request-ID':request_id,
            'X-Content-Type-Options':'nosniff',
            'X-Frame-Options':'DENY',
            'Referrer-Policy':'no-referrer',
            'Permissions-Policy':'camera=(), microphone=(), geolocation=()',
            'Content-Security-Policy':f"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src {connect_src}; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        }
        # HSTS is only relevant if a future local HTTPS wrapper is used.
        if str(request.url.scheme).lower()=='https':
            security_headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
        # Sensitive HTML/API responses are never cached. Versioned static assets
        # may be cached aggressively because the query-string version changes on release.
        if path.startswith('/static/') and 200 <= response.status_code < 400:
            # Desktop/WebView2 is local and tiny. Never keep year-long immutable assets:
            # hotfixes must take effect immediately even when the WebView2 profile persists.
            security_headers['Cache-Control']='no-store, max-age=0'
            security_headers['Pragma']='no-cache'
        else:
            security_headers['Cache-Control']='no-store'
        response.headers.update(security_headers)
        if path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS'):
            try:
                with connection() as c:
                    c.execute('INSERT INTO web_security_log37(actor,method,path,status,request_id,created_at) VALUES(?,?,?,?,?,?)',((user or {}).get('username') or getattr(request.state,'audit_actor',None) or 'anonymous',request.method,path[:200],response.status_code,request_id,utcnow()))
            except Exception as exc:
                logging.getLogger('desktop.security').error('security audit write failed request=%s type=%s', request_id, type(exc).__name__)
        try:
            from webapi.operations47 import record_request
            record_request(request,response,time.monotonic()-started)
        except Exception as exc:
            logging.getLogger('desktop.security').warning('request telemetry write failed request=%s type=%s', request_id, type(exc).__name__)
        return response
