# NetworkAutomation Desktop 7.0.3 - Fixed Release Candidate

- Windows Desktop only; backend binds `127.0.0.1`.
- Windows-native LAN identity, gateway, ARP/Neighbor and bounded ICMP probing.
- Runtime data is portable under `runtime_data` beside the application; copying the complete folder preserves local accounts and trust/config state.
- Installer output: `NetworkAutomation_Setup_7.0.3.exe`.

## QA / stability fixes

- Fixed critical UI 7.0.3 vs legacy 6.9.0 health-check mismatch that could disable all actions after login.
- Fixed WebView2/browser stale-JavaScript regression: hotfixes no longer reuse `?v=7002`; asset revision is now `70390`, is validated by `/api/health`, and local static assets use `Cache-Control: no-store`.
- Unknown `data-action` / form handlers now show an explicit UI error instead of silently doing nothing.
- Wired the previously missing `line-optimize59` action to `/api/v59/network/optimize`.
- Historical note: the MFA flow added in an earlier hotfix is superseded by QA76; MFA is no longer an active login feature.
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
- User-facing source startup is now `app.vbs` / `MO_APP_NETWORKAUTOMATION.vbs`; source `.bat` bootstrap is internal-only and hidden.

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
- `app.vbs` is the recommended no-console source launcher. The bootstrap no longer deletes an old `.venv`; it uses a versioned venv under LOCALAPPDATA and falls back to a repair environment if needed.


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

## QA75 security/data-integrity + process-cleanup patch (2026-10-06)

- Fixed 50 additional issues found by negative/fuzz/static/runtime retesting after QA25.
- Historical QA75 note superseded by QA76: the requested current policy accepts any non-empty account password (bounded only by a 512-character safety maximum).
- Request models now reject unknown JSON fields and apply practical length/range bounds to authentication, credentials, SNMPv3, server-target and Auto-IP inputs.
- Historical QA75 note superseded by QA76: MFA login/enrollment/reset functionality has now been removed; legacy schema is kept only for safe database migration.
- Security reporting uses the correct IOC/server-target tables, unique asset counts, current/latest vulnerability scans, explicit data-unavailable errors, corrupt-snapshot handling and CSV formula-injection protection.
- SOC case IP validation and reopen/resolve/close timestamps are consistent; custom detection LIKE rules escape SQL wildcard characters.
- Persisted Cybersecurity settings now control remote HTTPS requirements and VT/NVD integration enablement.
- Viewer cannot initiate network probes or Kali command/tool checks; Kali HTTP probes no longer disable TLS certificate verification.
- Nonexistent delete/unassign/history operations now return explicit 404s instead of false-success/empty results.
- On Windows close, the launcher uses a Job Object with `KILL_ON_JOB_CLOSE` plus a scoped psutil fallback so app-owned child processes (including hidden cmd/PowerShell/WebView helpers) are terminated without touching unrelated user processes.
- Asset revision bumped to `70391`.

## QA75 verification

- Python compile: PASS
- Regression suite: **132/132 PASS** before release-gate packaging.
- New targeted QA75 suite: **21/21 PASS**.

## QA76 user-requested functional patch (2026-10-07)

- CSV exports now persist through the authenticated backend into `runtime_data/reports`; Excel exports also return the exact saved file path, avoiding WebView2 download-manager failures.
- MFA login/enrollment/reset functionality was removed. Legacy MFA database columns/tables are retained only as a disabled migration compatibility layer.
- Account passwords now accept any non-empty value (maximum 512 characters only as an input-safety bound).
- Product/Production Center labels and operational check details are rendered in Vietnamese instead of raw status/code payloads.
- Operational readiness initializes `known_hosts` and the local credential encryption key safely and displays human-readable status text instead of boolean error-like values.
- Runtime state is portable in `runtime_data` beside the app. Copying the complete application folder to another PC preserves Admin accounts, settings, SSH trust and the matching credential key.
- Header system time now updates once per second without requiring page refresh.
- White Hat Kali integration supports importing a JSON connection profile and bounded defensive execution. Red/Black Hat exposes only a Kali connection configuration form—no JSON import, test, tools or execution controls.
- Existing QA75 shutdown cleanup remains active: closing the app terminates only app-owned child processes/hidden consoles, not unrelated CMD/PowerShell windows.
- Asset revision bumped to `70395` so WebView2 cannot reuse older JavaScript/CSS.

## QA76 verification

- Python compile: PASS
- JavaScript syntax: PASS
- Regression suite: **142/142 PASS** before clean packaging.
- Auth/export runtime smoke test: PASS (password-only login, CSV saved, Excel saved, no MFA field in session).
- Desktop QA gate: **52/52 PASS**.
- Release manifest: **173/173 files verified**.

## QA77 full code-audit hardening
- Red/Black Hat is Kali configuration-only; removed all Red-side Kali execution hooks and unsupported profiles.
- Active network checks and Kali tools are POST-only and role-gated; passive GETs no longer initiate WAN probes.
- Generated downloads use server persistence, one-hour one-time tokens, seven-day cleanup, relative display paths and bounded CSV/Excel exports.
- Portable data startup tolerates malformed/unwritable optional locations, rechecks migration idempotently, and migrates Kali configuration.
- Closed audited SQLite handles; strengthened Windows child-process cleanup diagnostics and detached-helper cleanup by launch token.
- Scheduler now logs failures, prevents overlapping ticks/duplicate threads, and only advances schedule time after a durable job submission.
- Firewall/Defender posture avoids false-safe states for inactive/mixed profiles and disabled realtime protection.
- Asset revision bumped to `70395`.

## QA78 - Export destination + Excel parity
- Added native Windows folder selection before CSV/XLSX export.
- Added Excel (.xlsx) next to CSV on data grids and Security Snapshot export.
- Report Center Excel now asks where to save instead of silently using the internal reports directory.
- Added one-time export-directory capability tokens so the local Web UI cannot write to arbitrary paths.
- Asset revision bumped to `70396`.

## QA79 - Windows Local Tools / PowerShell-CMD Engine

- Removed active Kali Linux integration and all `/api/v1/kali/*` routes, Kali SSH configuration UI, host-key import/test controls and Kali runtime migration.
- Added a centralized Windows-local command runner with server-owned profile whitelists. The browser cannot submit arbitrary PowerShell/CMD commands.
- White Hat now exposes Windows-native diagnostics for ping, DNS, TCP ports, HTTP/HTTPS headers, TLS/certificates, routes, ARP, TCP state, file hashes, processes, services, Firewall, Windows Event Log, adapters/IP, traceroute and server/network status.
- Red Hat now exposes bounded authorized diagnostics only: private-host recon/config/connectivity, HTTP headers, TLS, cookie/session audit, local network state and at most 1-5 sequential HEAD requests to a private URL.
- PowerShell runs hidden/non-interactive with timeout/output caps and app-owned process cleanup. Active targets are private-only; HTTP hostname resolution is pinned with `curl.exe --resolve`, and TLS validation is not bypassed.
- Added Windows Local Tools centers to both security navigation groups and relevant White/Red pages.
- Asset revision bumped to `70397`.

### QA79 verification

- Regression suite: **166/166 PASS**.
- Desktop QA gate: **61/61 PASS**.
- Python compile: PASS.
- JavaScript syntax: PASS.


## QA80 - Detailed Network Diagnostics
- Added a dedicated **Kiểm tra mạng chi tiết** action on Tốc độ & Đường truyền.
- Diagnostics separate Adapter/IP, default gateway, gateway reachability, DNS, TCP 443, HTTPS, latency, jitter and packet loss.
- The result now explains the specific cause behind FAIR/POOR instead of showing only the aggregate grade.
- The latest detailed diagnostic is persisted and remains visible after page refresh.
- Detailed diagnostics are lightweight and do not run bandwidth speed tests or modify Windows network settings.
- Asset revision bumped to `70398`.

## QA81 export picker reliability
- Fixed the CSV/Excel error `Hộp chọn thư mục Windows chưa sẵn sàng`.
- Export actions now invoke the native folder chooser through the local Desktop API first, so they do not depend on JavaScript bridge readiness.
- The Desktop launcher registers its pywebview folder chooser with the backend; a hidden PowerShell/WinForms dialog is used as a Windows fallback.
- Cancel is treated as a normal user action and creates no file.
- Asset revision: 70400.

## QA82 - Network measurement accuracy
- Reworked Internet quality measurement so fixed ICMP latency to `1.1.1.1` is reference-only and no longer determines the overall grade.
- Line quality now uses median TCP handshake latency to the same CDN host used by the bandwidth test, with DNS resolved before timing.
- Replaced the 5 MB / 2 MB single-stream bandwidth estimate with warm-up + adaptive multi-stream transfers, bounded to 128 MB download and 64 MB upload.
- Speed-test results now expose actual bytes, duration, stream count and the latency method used.
- The network page uses the newest line/speed measurement for quality cards instead of always showing an older line-test grade.
- LAN gateway latency remains separate from Internet latency; reference ICMP is visible only for troubleshooting.
- Asset revision bumped to `70400`.


## QA83 - Speed Test result visibility
- Fixed the global 20-second browser API timeout aborting adaptive multi-stream bandwidth tests before they could persist/render Download and Upload values.
- Added per-request bounded timeouts: 45s line test, 60s detailed diagnostics and 180s speed test.
- Network cards now show `Chưa đo` instead of a bare dash when no fresh QA82+ speed sample exists.
- Speed-test progress text now explains that the multi-stream test can take 30-120 seconds on some connections.
- Asset revision bumped to `70401`.

## QA84 - Trilingual UI

- Added Vietnamese, Simplified Chinese and English language selector to login and main header.
- Language choice persists locally and can be changed without logging out.
- Added dynamic translation for navigation, common controls, dialogs, table headers, network diagnostics and Windows Local Tools.
- Raw device data, code/logs and PowerShell/terminal output remain untranslated.
- Live system clock now follows the selected locale.
- Added `i18n84.js` to the explicit static-asset allowlist and release manifest requirements.
- Asset revision bumped to `70402`.

## QA85 - Trilingual language switch runtime fix
- Fixed the WebView2 MutationObserver attribute feedback loop that could leave the selector visible while preventing language changes from applying.
- Added delegated selector events, guarded localStorage access, and complete login translations.
- Asset revision bumped to `70403`.

## QA86 - Full Trilingual UI

- Asset revision bumped to `70404`.
- Expanded i18n from selected chrome labels to the complete app DOM (`#login-view`, `#app`, dialogs and toasts).
- Added complete English and Simplified Chinese catalog coverage for user-visible Vietnamese messages emitted by WebAPI.
- Added canonical Vietnamese replacements for legacy English/mixed UI labels to prevent mixed-language Vietnamese pages.
- Added dynamic-content and legacy-English compatibility mappings.
- Added QA86 static coverage tests and browser runtime smoke verification.


## QA87 – Domestic vs International Network Quality

- Primary network quality now uses the fastest reachable Vietnam/domestic TCP 443 probe instead of the international speed-test CDN.
- Domestic latency/jitter/sample-loss and international/CDN latency are stored and displayed separately.
- `Kiểm tra trong nước` is the default quality test; `Kiểm tra quốc tế` is a separate reference test.
- A slow international/CDN route can no longer force the domestic quality card to `POOR` when the domestic route is healthy.
- Bandwidth Download/Upload continues to use the explicit multi-stream CDN test and is labeled separately from domestic latency.
- Domestic probe targets are configurable through `NA_DOMESTIC_PROBE_HOSTS` for ISP/enterprise deployments.
- Asset revision bumped to `70405`.
