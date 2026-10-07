# NetworkAutomation Desktop 7.0.3 - QA77 Full Audit Fixes

Asset revision: 70395

This build hardens the 50 issues identified in the QA76 source audit.

## Main corrections
- Red/Black Hat UI is Kali configuration-only. Active Kali execution is exposed only from bounded White Hat defensive pages.
- Kali tool discovery and active network/identity probes use POST and write-capable roles; passive GET routes do not create remote/network side effects.
- Frontend GET requests do not retry unless explicitly opted in.
- Navigation/feature overlays install idempotently and preserve user-open menu state.
- Diagnostics, RDP, DR, job/report export flows use server-side persistence instead of Blob/window navigation downloads.
- Download tokens expire after one hour, are one-time, and generated files have seven-day retention. CSV is capped at 2 MB and report sheets at 5000 rows.
- Export APIs expose relative data-folder paths rather than absolute machine paths; Viewer cannot create CSV files or active network probes.
- Portable data resolution falls back safely when data_location.json is malformed or unwritable. Migration is idempotent and also imports Kali config.
- Audited direct SQLite connections are explicitly closed.
- Windows process cleanup logs failures and can locate detached app-owned helpers by the per-launch NA_INSTANCE_TOKEN.
- Scheduler failures are logged, ticks are single-flight, failed submissions retry soon, and next run time advances only after job acceptance.
- Firewall and Microsoft Defender detection no longer report false ON for inactive/mixed/realtime-disabled states.
- Release packaging excludes runtime_data content, runtime database/locks/backups, caches and machine-specific release markers.
