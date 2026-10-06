"""Verify the NetworkAutomation Desktop 7.0.3 source/build package offline."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT=Path(__file__).resolve().parent
MANIFEST=ROOT/'DESKTOP_RELEASE_MANIFEST.json'
FORBIDDEN={'runtime_data','.git','.venv','.buildvenv','build','dist','release','__pycache__','.pytest_cache'}
FORBIDDEN_FILES={
    'render.yaml','render_start.py','requirements-render.txt','requirements-web.txt',
    'START_WEB.bat','STOP_WEB.bat','RUN_WEB_HIDDEN.vbs','QA_PRODUCTION_GATE.py',
    'CONFIGURE_WEB.bat','INSTALL_WEB.bat','INSTALL_WEB_AUTOSTART.bat','OPEN_RENDER_WEB.bat',
    'VERIFY_WEB_DATA.bat','run_web.py','run_web_background.py','web_service50.py',
    'RENDER_DEPLOY.md','ROUTER_API_SETUP.md',
    'webapi/routerapi69.py','webapi/static/routerapi69.js','webapi/static/routerapi70.js',
}


def verify(root:Path=ROOT):
    root=root.resolve()
    manifest=root/'DESKTOP_RELEASE_MANIFEST.json'
    if not manifest.is_file():
        return {'ok':False,'checked':0,'errors':['MANIFEST_MISSING']}
    data=json.loads(manifest.read_text(encoding='utf-8'))
    if data.get('version')!='7.0.3' or not isinstance(data.get('files'),dict):
        return {'ok':False,'checked':0,'errors':['MANIFEST_INVALID']}
    errors=[]; checked=0
    for name,expected in data['files'].items():
        rel=PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or any(x in FORBIDDEN for x in rel.parts):
            errors.append('UNSAFE_PATH: '+name); continue
        p=root.joinpath(*rel.parts)
        if not p.is_file():
            errors.append('MISSING: '+name); continue
        checked+=1
        got=hashlib.sha256(p.read_bytes()).hexdigest()
        if got!=expected: errors.append('CHANGED: '+name)
    for forbidden in FORBIDDEN:
        p=root/forbidden
        if p.exists() and any(x.is_file() for x in p.rglob('*')):
            errors.append('FORBIDDEN_RUNTIME_CONTENT: '+forbidden)
    for name in FORBIDDEN_FILES:
        if (root/name).exists(): errors.append('OBSOLETE_HOSTED_FILE: '+name)
    dbroot=root/'database'
    if (dbroot/'db_backups').exists():
        errors.append('RUNTIME_BACKUP_SHIPPED: database/db_backups')
    for p in dbroot.rglob('*') if dbroot.exists() else []:
        if p.is_file() and (p.suffix in {'.db','.lock','.db-wal','.db-shm'} or p.name in {'.credential.key','known_hosts'}):
            errors.append('RUNTIME_DATABASE_SHIPPED: '+p.relative_to(root).as_posix())
    required=['desktop_launcher.py','webapi/desktop70.py','webapi/static/desktop70.js','NetworkAutomationDesktop.spec','installer/NetworkAutomation.iss','QA_DESKTOP_GATE.py','MO_APP_NETWORKAUTOMATION.vbs','00_MO_APP_NETWORKAUTOMATION.vbs','_internal/launcher/START_DESKTOP_CORE.bat','START_HERE.txt','requirements-lock.txt','requirements-dev.txt']
    for name in required:
        if name not in data['files']: errors.append('REQUIRED_NOT_MANIFESTED: '+name)
    return {'ok':not errors,'version':'7.0.3','checked':checked,'errors':errors}


def main():
    report=verify(); print(json.dumps(report,ensure_ascii=False,indent=2)); return 0 if report['ok'] else 1

if __name__=='__main__':
    raise SystemExit(main())
