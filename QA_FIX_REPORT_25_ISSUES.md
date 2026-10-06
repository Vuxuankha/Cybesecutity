# NetworkAutomation Desktop 7.0.3 - QA25 Fix Report

Date: 2026-10-06
Asset revision: 70390

This patch addresses all 25 issues found in the post-QA93 runtime audit.

| # | Status | Fix |
|---|---|---|
| 1 | FIXED | `/api/health` does not return ready/200 before critical background startup completes. |
| 2 | FIXED | Frontend health requires `background_ready=true`. |
| 3 | FIXED | Jobs schema is ensured before Dashboard jobs reads. |
| 4 | FIXED | Runtime reporting tolerates early/optional table state. |
| 5 | FIXED | Diagnostics export tolerates early/optional table state. |
| 6 | FIXED | Missing enabled Admin is detected and can be recovered during first-run setup. |
| 7 | FIXED | Successful logins no longer consume the failure-rate budget. |
| 8 | FIXED | Repeated successful logins no longer produce the old 31st-login 429. |
| 9 | FIXED | Desktop localhost peer no longer cross-locks unrelated accounts. |
| 10 | FIXED | Login `Retry-After` now matches the remaining failure window. |
| 11 | FIXED | Feature asset failure no longer invalidates a successful login. |
| 12 | FIXED | Failed assets can be retried; Login remains recoverable. |
| 13 | FIXED | UI no longer shows a false unauthenticated state while the backend session is valid. |
| 14 | FIXED | Independent feature assets load in parallel while dependency order is preserved. |
| 15 | FIXED | Authenticated shell shows explicit feature-loading/error/retry state. |
| 16 | FIXED | Role/login transitions reset an inaccessible saved page to Dashboard. |
| 17 | FIXED | Dashboard uses partial-failure tolerant loading instead of all-or-nothing `Promise.all`. |
| 18 | FIXED | Windows-native network failure is isolated from the base Dashboard. |
| 19 | FIXED | Viewer Dashboard does not run active ICMP probing. |
| 20 | FIXED | Active ARP-neighbor probing is capped at 128 hosts per refresh. |
| 21 | FIXED | Side-effecting GET probes opt out of automatic retry. |
| 22 | FIXED | Health polling is single-flight and cannot overlap itself. |
| 23 | FIXED | Asset validation explicitly verifies `desktop70.js`. |
| 24 | FIXED | Asset validation explicitly verifies `hotfix10_nav_core.js`. |
| 25 | FIXED | Launcher reserves its localhost port and validates exact backend identity/readiness. |

## Automated regression result

`111 passed`

The package is also checked by the Desktop release gate and manifest verifier before distribution.
