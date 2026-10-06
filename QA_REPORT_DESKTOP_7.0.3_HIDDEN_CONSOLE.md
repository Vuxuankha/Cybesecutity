# QA Report - NetworkAutomation Desktop 7.0.3 Fixed Build

Date: 2026-10-06

## Result

Status: **PASS for source/release verification**. Windows-native visual smoke testing is still required on an actual Windows machine after building the EXE/installer.

## Defects fixed

1. UI/API release mismatch no longer hard-codes UI 6.9.0; runtime health is validated against `NA_UI_VERSION` / `NA_RELEASE` for Desktop 7.0.3.
2. Successful health validation restores `state.uiReady=true` instead of leaving the UI disabled.
3. Multi-IP adapters now prefer the IPv4/subnet that actually contains the default gateway.
4. Portable-data migration no longer writes its completion marker after a failed copy.
5. Desktop migration uses one canonical marker (`.desktop_migration_37.json`), accepts legacy markers for compatibility, and upgrades them atomically after successful migrations.
6. `main.py` imports `json` for the migration path and records migration completion only after schema/data migration steps succeed.
7. Live/Refresh OFF is honored by Desktop, platform, enterprise presence/automation status, and IP/MAC periodic refresh timers.
8. IP/MAC periodic refresh now uses a singleton timer instead of adding another interval after every navigation.
9. The Presence refresh button no longer uses inline `onclick`, so it is compatible with the application's CSP.
10. User-visible release branding no longer gets overwritten by legacy 6.9.0 overlays.
11. Ping results that Windows reports as `<1 ms` preserve the upper-bound flag through the Desktop API and UI.
12. Internet status on LAN-only connectivity is presented as "Chưa xác minh" instead of a definite offline result.
13. Build QA dependencies are explicit in `requirements-dev.txt`; release dependencies are pinned in `requirements-lock.txt`.
14. Windows build/source bootstrap supports verified Python 3.13/3.12/3.11 and common direct install paths; error 11 now offers an explicit winget Python 3.12 install/retry flow.
15. Desktop launcher checks the documented WebView2 Evergreen Runtime registration before creating the embedded UI and returns a clear error if missing.
16. The unused alternative `webapi/core` + `webapi/routers` auth stack was removed; the application ships one active auth/session implementation (`webapi/security37.py`).
17. User-facing source startup is VBS-only; the `.bat` bootstrap is internal so users cannot accidentally open a visible CMD launcher from the root folder.
18. Bootstrap no longer deletes a stale/locked `.venv`; it uses a versioned environment under `%LOCALAPPDATA%\NetworkAutomation\venvs` and creates a separate repair environment when needed.
19. Static asset cache invalidation is now release-safe: `NA_ASSET_VERSION=70389`, `/api/health` reports `asset_version`, the UI validates it, and static responses use `no-store` instead of one-year immutable caching. This fixes the observed symptom where navigation still worked but all actions were globally blocked by a cached legacy `operations47.js`.
20. Missing UI handlers no longer fail silently; unknown button actions/forms surface a visible diagnostic.
21. The previously unbound `line-optimize59` button is now connected to the bounded Admin-only `/api/v59/network/optimize` endpoint.
22. MFA enrollment/verification is available in the initial `app.js` login bundle, removing the pre-authentication dependency cycle.

## Verification

- Python `compileall`: PASS
- JavaScript `node --check`: PASS
- Existing regression suite before new tests: **73/73 PASS**
- Expanded regression suite after fixes: **92/92 PASS**
- Desktop release gate: **44/44 PASS**
- Runtime DB/cache/lock artifacts removed before packaging: PASS
- Release manifest regenerated after all code/doc changes: PASS
- Functional browser-harness smoke test: local form submit, action dispatch, stale-asset guard and missing-handler diagnostic PASS
- Offline release verifier: PASS

## Windows validation note

This environment is not Windows, so actual WebView2 rendering, native PowerShell adapter enumeration, hidden-console visual behavior, Inno Setup build, and the final EXE launch cannot be visually exercised here. The corresponding launch paths, process flags, adapter-selection logic, WebView2 registry check, and release build workflow are covered by static/unit regression tests and must still receive one final smoke test on Windows.

## QA93 fast-start optimization

23. Warm source launches now use a validated venv pointer/ready marker, avoiding repeated Python discovery and the heavy dependency import probe.
24. Existing-account detection is read-only and lightweight; full schema imports are delayed until real first-run/repair.
25. WebView is created with an immediate local splash before backend readiness, then navigates to the local FastAPI UI when health is available.
26. Current-schema databases use a warm startup path; full migration/table replay is reserved for new/upgrade/fallback cases.
27. Scheduler/jobs/automation/endpoint monitor/network identity are moved off the critical UI path and warm in a daemon thread.
28. UPX is disabled in the PyInstaller spec to reduce cold-start decompression and antivirus overhead.

Verification after QA93:
- Pytest: **97/97 PASS**
- Desktop release gate: **48/48 PASS**
- Warm schema gate micro-test: ~0.2 ms in QA environment (not a full Windows GUI benchmark).
