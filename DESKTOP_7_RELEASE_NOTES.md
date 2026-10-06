# NetworkAutomation Desktop 7.0.3 - Fixed Release Candidate

- Windows Desktop only; backend binds `127.0.0.1`.
- Windows-native LAN identity, gateway, ARP/Neighbor and bounded ICMP probing.
- Runtime data stays under `%LOCALAPPDATA%\NetworkAutomation` in the packaged build.
- Installer output: `NetworkAutomation_Setup_7.0.3.exe`.

## QA / stability fixes

- Fixed critical UI 7.0.3 vs legacy 6.9.0 health-check mismatch that could disable all actions after login.
- Fixed WebView2/browser stale-JavaScript regression: hotfixes no longer reuse `?v=7002`; asset revision is now `70390`, is validated by `/api/health`, and local static assets use `Cache-Control: no-store`.
- Unknown `data-action` / form handlers now show an explicit UI error instead of silently doing nothing.
- Wired the previously missing `line-optimize59` action to `/api/v59/network/optimize`.
- Initial login now includes the MFA enroll/verify flow in the base bundle; it no longer depends on authenticated feature assets.
- Fixed multi-IP adapter selection to choose the subnet containing the default gateway.
- Fixed portable migration so failed copies are retried on next launch instead of being marked complete.
- Unified Desktop migration marker handling and made completion writes atomic.
- Fixed migration startup path missing `json` import.
- Live/Refresh OFF now stops periodic data refresh timers while keeping explicit user actions and terminal keepalive behavior intact.
- Removed CSP-incompatible inline event handler from Presence refresh.
- Stopped legacy overlays from replacing Desktop 7.0.3 branding with UI 6.9.0.
- Preserved Windows `<1 ms` ping semantics in Desktop network views.
- LAN-only Internet state is shown as not verified rather than definitively offline.
- Added WebView2 Runtime preflight with a clear remediation message.
- Removed unused duplicate auth/router implementation; one auth/session stack remains active.
- Added release dependency lock and explicit QA dependencies.
- Windows build/source bootstrap supports Python 3.13/3.12/3.11 and common direct installation paths.
- User-facing source startup is now `00_MO_APP_NETWORKAUTOMATION.vbs` / `MO_APP_NETWORKAUTOMATION.vbs`; source `.bat` bootstrap is internal-only and hidden.

## Regression status

- Python compile: PASS
- JavaScript syntax: PASS
- Pytest: **92/92 PASS**
- Desktop QA gate: **44/44 PASS**
## Bootstrap hotfix (2026-10-06)

- Fix error code 11 on Windows machines that have Python 3.13 but not 3.11/3.12.
- Source bootstrap now detects Python 3.13, 3.12, 3.11, common per-user/system install paths, and a compatible `python.exe` on PATH.
- Error code 11 is now explained in a friendly dialog; user can explicitly opt in to install Python 3.12 with `winget` and retry automatically.
- Error codes 12/13/14 now show actionable messages for venv/pip/dependency failures.
- Source bootstrap no longer touches the legacy `.venv` beside the source. It uses a versioned environment under `%LOCALAPPDATA%\NetworkAutomation\venvs`; an invalid/locked versioned environment is preserved and a separate repair environment is created.
- `00_MO_APP_NETWORKAUTOMATION.vbs` is the recommended no-console source launcher. The bootstrap no longer deletes an old `.venv`; it uses a versioned venv under LOCALAPPDATA and falls back to a repair environment if needed.


## Fast-start hotfix (QA93)

- Warm source launches now use a validated venv marker under `%LOCALAPPDATA%\NetworkAutomation\venvs` and skip Python discovery plus heavy dependency imports.
- Existing users are detected with a small read-only SQLite query; the legacy NMS schema stack is imported only for true first-run setup/repair.
- The native WebView window is painted immediately with a local splash; FastAPI starts in a background thread and the window navigates to the local UI as soon as `/api/health` is ready.
- A current `.desktop_migration_37.json` marker enables a warm schema path. Full backup/migration/table replay only runs for a new install, an upgrade, or a failed sanity check.
- Scheduler, jobs, endpoint monitor, daily automation and local network identity warm up after the HTTP/UI path is available.
- PyInstaller UPX compression is disabled to reduce cold EXE decompression/antivirus startup overhead.
- `/api/health` now reports `startup_mode` (`warm`/`cold`) and `background_ready` for diagnostics.

## QA93 verification

- Python compile: PASS
- JavaScript syntax: PASS
- Pytest: **97/97 PASS**
- Desktop QA gate: **48/48 PASS**
- Warm schema gate micro-test: approximately **0.2 ms** in the QA environment (excludes WebView/PyInstaller/Windows process startup).


## QA25 full-fix patch (2026-10-06)

- Startup health now stays HTTP 503 until critical background services and the jobs schema are ready; launcher validates the exact service/release/instance identity before opening the UI.
- Jobs/runtime/diagnostics paths tolerate early or optional-table states instead of returning startup 500 errors.
- First-run/recovery now detects the absence of an enabled Admin and can recover access without deleting application data.
- Login throttling counts failed attempts only, uses a correct retry window, and avoids localhost cross-account lockout in the Desktop-only runtime.
- Authenticated UI state is separated from feature-asset readiness. Feature load failures keep the valid session and expose an in-app retry instead of returning to Login.
- Feature assets load in dependency-safe parallel groups, both final Desktop hotfix bundles are verified, and login/health state can recover after a transient asset failure.
- Role switches reset inaccessible pages to Dashboard; Viewer mode no longer triggers active ICMP probes.
- Dashboard data loads with partial-failure tolerance; Windows-native network failure no longer takes down the main dashboard.
- Active neighbor probing is capped at 128 hosts per refresh and side-effecting GET probes are excluded from automatic retry.
- Health polling is single-flight to prevent overlapping requests.
- Localhost port allocation is reserved until Uvicorn takes ownership, closing the launcher port-selection race.

## QA25 verification

- Python compile: PASS
- JavaScript syntax: PASS
- Pytest: **111/111 PASS**
- Added regression coverage for the reported startup, login, session, asset, dashboard, role, probe and launcher-identity failures.
