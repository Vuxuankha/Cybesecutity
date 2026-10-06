"""Offline release gate for NetworkAutomation Desktop 7.0.3 Desktop Only."""
from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CHECKS=[]


def check(name, ok, detail=''):
    CHECKS.append((name,bool(ok),detail))


def main():
    launcher=(ROOT/'desktop_launcher.py').read_text(encoding='utf-8')
    appjs=(ROOT/'webapi/static/app.js').read_text(encoding='utf-8')
    idx=(ROOT/'webapi/static/index.html').read_text(encoding='utf-8')
    routes=(ROOT/'webapi/routes37.py').read_text(encoding='utf-8')
    native=(ROOT/'webapi/desktop70.py').read_text(encoding='utf-8')
    runtime=(ROOT/'webapi/runtime37.py').read_text(encoding='utf-8')
    main=(ROOT/'webapi/main.py').read_text(encoding='utf-8')
    sec=(ROOT/'webapi/security37.py').read_text(encoding='utf-8')
    cyberjs=(ROOT/'webapi/static/cybersecurity51.js').read_text(encoding='utf-8')
    spec=(ROOT/'NetworkAutomationDesktop.spec').read_text(encoding='utf-8')
    iss=(ROOT/'installer/NetworkAutomation.iss').read_text(encoding='utf-8')
    workflow=(ROOT/'.github/workflows/windows-desktop-release.yml').read_text(encoding='utf-8')

    check('Desktop mode forced', 'NA_DESKTOP_APP' in launcher and 'NA_RUN_MODE' in launcher)
    check('Backend localhost only', 'host="127.0.0.1"' in launcher and 'host="0.0.0.0"' not in launcher)
    check('No hard-coded admin password', 'Admin@' not in launcher and 'password.get()' in launcher)
    check('First-run Admin setup', 'Tạo tài khoản quản trị đầu tiên' in launcher)
    check('Uvicorn logging formatter bypass', 'log_config=None' in launcher)
    platform50=(ROOT/'webapi/platform50.py').read_text(encoding='utf-8')
    check('Background PowerShell hidden', 'WindowStyle' in platform50 and 'hidden_subprocess_kwargs' in platform50)
    check('Hidden desktop starter', 'sh.Run(cmd, 0, True)' in (ROOT/'MO_APP_NETWORKAUTOMATION.vbs').read_text(encoding='utf-8') and 'pythonw.exe' in (ROOT/'_internal/launcher/START_DESKTOP_CORE.bat').read_text(encoding='utf-8').lower() and not (ROOT/'START_DESKTOP_7.bat').exists())
    core=(ROOT/'_internal/launcher/START_DESKTOP_CORE.bat').read_text(encoding='utf-8')
    check('Locked venv cannot block startup', 'rmdir /s /q' not in core.lower() and '%LOCALAPPDATA%\\NetworkAutomation\\venvs' in core and '-repair-%RANDOM%-%RANDOM%' in core)
    check('Obvious no-console launcher', (ROOT/'00_MO_APP_NETWORKAUTOMATION.vbs').is_file() and (ROOT/'START_HERE.txt').is_file())
    check('PyInstaller windowed', 'console=False' in spec)
    check('Immediate WebView paint', 'html=_startup_splash_html()' in launcher and 'webview.start(_bootstrap, debug=False)' in launcher and '_fast_existing_user()' in launcher)
    check('Validated venv fast path', '.na_ready_70393' in core and 'current-7.0.3.txt' in core and 'goto RUNAPP_FAST' in core)
    check('Warm schema fast path', '_schema_marker_current()' in main and "return 'warm'" in main and 'NetworkAutomation-Warmup' in main)
    check('UPX disabled for faster startup', spec.count('upx=False') >= 2 and 'upx=True' not in spec)
    accounts=(ROOT/'modules/accounts.py').read_text(encoding='utf-8')
    check('Account password has no length cap', '8 <= len(password) <= 256' not in accounts and 'Mật khẩu phải có từ 8 đến 256 ký tự.' not in accounts and 'len(x.password)<12' not in routes and 'max_length=256' not in routes.split('class UserIn',1)[1].split('def account_call',1)[0])
    check('Local data isolation', 'LOCALAPPDATA' in (ROOT/'app_runtime.py').read_text(encoding='utf-8'))
    check('Windows native network endpoint', '/network-overview' in native and 'WINDOWS_LOCAL_MACHINE' in native)
    check('ARP source is local', '_arp_neighbors' in native and 'route","print","-4' in native)
    check('Bounded ICMP probe', 'ThreadPoolExecutor' in native and 'timeout_ms=450' in native)
    check('Desktop UI asset loaded', "'desktop70.js'" in appjs and "'desktop70.js': 'text/javascript'" in routes)
    check('Desktop release identity', "UI_VERSION='7.0.3'" in runtime and "RELEASE='Desktop 7.0.3 Desktop Only'" in runtime)
    check('Desktop login copy', 'Desktop 7.0.3' in idx and '127.0.0.1' in idx)
    check('Public registration removed', '/api/auth/register' not in main and '/auth/register' not in cyberjs)
    check('Router API removed', not (ROOT/'webapi/routerapi69.py').exists() and not (ROOT/'webapi/static/routerapi69.js').exists() and not (ROOT/'webapi/static/routerapi70.js').exists())
    check('Hosted deploy files removed', all(not (ROOT/x).exists() for x in ['render.yaml','render_start.py','requirements-render.txt','requirements-web.txt','RUN_WEB_HIDDEN.vbs','START_WEB.bat']))
    check('Browser-only network removed', all(x not in cyberjs for x in ['/v59/browser/','BROWSER_LINE','BROWSER_SPEED','WEB / BROWSER']))
    check('Legacy web flags removed', all(x not in launcher+main+sec for x in ['NA_WEB_ONLY_BROWSER','NA_PUBLIC_REGISTRATION']))
    check('Desktop/Web parity page removed', "parity:'Desktop" not in appjs and '/v44/parity' not in (ROOT/'webapi/parity44.py').read_text(encoding='utf-8'))
    check('PyInstaller builder', 'desktop_launcher.py' in spec and "name='NetworkAutomation'" in spec)
    check('Installer version', 'NetworkAutomation_Setup_7.0.3' in iss and 'PrivilegesRequired=lowest' in iss)
    check('GitHub Windows build', 'runs-on: windows-latest' in workflow and 'pyinstaller --noconfirm NetworkAutomationDesktop.spec' in workflow)
    check('UI health version aligned', 'r.ui_version!==NA_UI_VERSION' in (ROOT/'webapi/static/operations47.js').read_text(encoding='utf-8') and "ui_version!=='6.9.0'" not in (ROOT/'webapi/static/operations47.js').read_text(encoding='utf-8'))
    check('Static asset revision aligned', "NA_ASSET_VERSION='70390'" in appjs and '?v=70390' in idx and "ASSET_VERSION='70390'" in runtime and 'r.asset_version!==NA_ASSET_VERSION' in (ROOT/'webapi/static/operations47.js').read_text(encoding='utf-8'))
    check('Static assets cannot remain stale', 'max-age=31536000, immutable' not in sec and "no-store, max-age=0" in sec)
    check('Initial MFA login is self-contained', 'MFA_FLOW_HANDLER_NOT_READY' not in appjs and "'mfa-login-form':async" in appjs and "'/auth/mfa/verify'" in appjs)
    check('Line optimization action is wired', "actions['line-optimize59']" in cyberjs and "'/v59/network/optimize'" in cyberjs)
    check('Live toggle honored by desktop timers', all('state.live' in (ROOT/x).read_text(encoding='utf-8') for x in ['webapi/static/desktop70.js','webapi/static/operations50.js','webapi/static/enterprise592.js','webapi/static/workbench45.js']))
    check('CSP-safe presence action', 'onclick=' not in (ROOT/'webapi/static/enterprise592.js').read_text(encoding='utf-8') and 'e592-presence-refresh' in (ROOT/'webapi/static/enterprise592.js').read_text(encoding='utf-8'))
    check('Canonical migration marker', "MIGRATION_MARKER = '.desktop_migration_37.json'" in runtime and 'mark_migration_complete' in runtime and "'.desktop_migration.json').write_text" not in main)
    check('Gateway-aware adapter identity', 'gateway_rank' in platform50 and 'ipaddress.ip_address(gateway) in ipaddress.ip_network' in platform50)
    check('Release dependency lock', (ROOT/'requirements-lock.txt').is_file() and (ROOT/'requirements-dev.txt').is_file() and 'requirements-dev.txt' in workflow)
    check('WebView2 preflight', 'F3017226-FE2A-4295-8BDF-00C3A9A7E4C5' in launcher and '_ensure_webview2_runtime()' in launcher)
    check('Single active auth stack', not (ROOT/'webapi/core/security.py').exists() and not (ROOT/'webapi/routers/auth.py').exists())
    check('Runtime data ignored', 'runtime_data/' in (ROOT/'.gitignore').read_text(encoding='utf-8'))
    runtime_db_files = list((ROOT/'database').rglob('*.db')) + list((ROOT/'database').rglob('*.lock')) + list((ROOT/'database').rglob('*.db-wal')) + list((ROOT/'database').rglob('*.db-shm'))
    check('No runtime database shipped', not runtime_db_files and not (ROOT/'database'/'db_backups').exists())
    check('Obsolete hosted QA removed', not (ROOT/'QA_PRODUCTION_GATE.py').exists() and not (ROOT/'regression_test.py').exists())
    check('Hosted docs removed', not (ROOT/'RENDER_DEPLOY.md').exists() and not (ROOT/'ROUTER_API_SETUP.md').exists() and not (ROOT/'db_migration').exists())
    check('Legacy hosted scripts removed', all(not (ROOT/x).exists() for x in ['CONFIGURE_WEB.bat','INSTALL_WEB.bat','INSTALL_WEB_AUTOSTART.bat','OPEN_RENDER_WEB.bat','VERIFY_WEB_DATA.bat','run_web.py','web_service50.py']))

    passed=sum(1 for _,ok,_ in CHECKS if ok)
    failed=[name for name,ok,_ in CHECKS if not ok]
    report={'ok':not failed,'release':'NetworkAutomation Desktop 7.0.3 Desktop Only','passed':passed,'total':len(CHECKS),'failed':failed}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['ok'] else 1

if __name__=='__main__':
    raise SystemExit(main())
