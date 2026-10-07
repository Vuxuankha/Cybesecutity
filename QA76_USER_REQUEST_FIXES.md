# QA76 - User-requested fixes

Release: NetworkAutomation Desktop 7.0.3 Desktop Only
Asset revision: 70394
Date: 2026-10-07

## Implemented

1. **CSV export fixed**
   - Grid/Security CSV exports POST content to `/api/reports/csv`.
   - Files are saved under `runtime_data/reports` and also receive a protected download URL.
   - CSV output is UTF-8 BOM compatible with Excel and protects leading formula characters.

2. **Excel export fixed**
   - Report and Auto-IP Excel files are persisted server-side.
   - Export responses include `saved_path` so WebView2 download handling is not a single point of failure.

3. **MFA removed**
   - Login is username/password only.
   - MFA verify/reset/enrollment routes and UI flow are removed.
   - Legacy MFA schema is disabled/cleared only for migration compatibility.

4. **Password length rule relaxed**
   - Any non-empty account password is accepted.
   - A 512-character maximum remains only to bound local request/database input.

5. **Product Center localized**
   - Operational check names and detailed results have Vietnamese presentation fields.
   - Raw queue/scheduler/LAN validation codes are converted to readable Vietnamese summaries.

6. **SSH known_hosts / encryption key readiness fixed**
   - Launcher creates an empty local `known_hosts` when missing.
   - Credential key is created only when safe; if encrypted data exists without its key, startup refuses silent key replacement.
   - Readiness UI shows `Sẵn sàng` / recovery guidance instead of raw booleans.

7. **Portable account data for moving PCs**
   - Writable state is under `runtime_data` beside the application in source and packaged modes.
   - Copying the whole folder including `runtime_data` preserves Admin accounts/password hashes, settings, known_hosts and `.credential.key`.
   - Existing old LocalAppData/database files can be imported once when present; destination files are never overwritten.
   - A truly empty new install still requires creating the first Admin because no credentials exist to recover.

8. **Live date/time**
   - Header system time is rendered with `vi-VN` formatting and refreshes every second independently of page data refresh.

9. **Kali split by security mode**
   - White Hat: Admin can import JSON Kali connection configuration; authorized write roles can run only the bounded defensive profiles already permitted by the backend.
   - Red/Black Hat: configuration-only page; no JSON import, test, tool enumeration or run controls.

10. **Shutdown cleanup retained**
    - App-owned hidden CMD/PowerShell/backend/WebView child processes are cleaned on close via scoped process-tree handling.
    - No global `taskkill /IM cmd.exe` or `powershell.exe` behavior is used.

## Verification performed

- Full pytest regression suite: 142/142 PASS.
- JavaScript `node --check`: PASS on all modified bundles.
- Python `py_compile`: PASS on all modified Python modules.
- Runtime API smoke test in isolated data directory:
  - `/api/health`: ready.
  - Password-only `/api/auth/login` with a 1-character password: 200.
  - No MFA field returned by `/api/auth/me`.
  - `/api/reports/csv`: file created on disk.
  - `/api/reports/export`: `.xlsx` file created on disk.
- Desktop QA gate: 52/52 PASS.
- Release manifest: 173/173 files verified.
