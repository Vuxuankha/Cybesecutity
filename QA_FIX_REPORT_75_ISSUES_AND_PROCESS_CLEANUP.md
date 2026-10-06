# NetworkAutomation Desktop 7.0.3 - QA75 Fix Report + Process Cleanup

Date: 2026-10-06
Asset revision: 70391
Scope: 25 prior QA25 fixes retained + 50 additional defects fixed + Windows child-process cleanup enhancement.

## High-impact fixes

1. Strong password policy is consistently enforced for account creation, admin reset, and self-service password change.
2. MFA challenges have a five-failure attempt ceiling, per-challenge counters, invalidation, and account-attributed auditing.
3. Unknown request fields are rejected rather than ignored silently; externally supplied strings and ports are bounded.
4. Missing-resource deletes/unassign/history calls use explicit 404 contracts instead of false-success or misleading empty output.
5. DB/report failures no longer masquerade as valid zero/empty datasets in SSH audit, report summary, health/ping maps, notification logs, and security reporting.
6. Security report IOC table is corrected to `ioc_watchlist54`; TLS registration uses `server_monitor_targets`.
7. Asset counts are unique across inventory sources and vulnerability scoring/reporting uses the latest scan per asset.
8. Corrupt report snapshots fail closed and exported CSV neutralizes spreadsheet formulas beginning with `=`, `+`, `-`, or `@`.
9. SOC cases validate IP addresses and reset stale terminal timestamps when cases are reopened or transition between RESOLVED/CLOSED states.
10. Custom detection text matching escapes `%` and `_` before SQL LIKE correlation.
11. Persistent Cybersecurity settings now govern remote HTTPS enforcement and VT/NVD enablement.
12. Viewer cannot trigger active network probing or execute Kali tool checks through direct API calls.
13. Kali malformed ports fall back safely and HTTP checks no longer use `curl -k`.
14. Alert/case owner fallback no longer allows a whitespace-only owner to become an empty owner.
15. App shutdown now terminates the app's own descendant process tree. A Windows Job Object uses `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`; a scoped psutil fallback terminates/then kills remaining child processes. No global `taskkill` against cmd.exe or powershell.exe is used.

## Verification added

`tests/test_qa75_security_and_cleanup.py` adds targeted coverage for password policy, strict request validation, asset/vulnerability counting, report corruption and CSV safety, SOC IP validation, Kali port safety, Viewer probe denial, SQL LIKE escaping, correct IOC/TLS tables, Kali role/TLS behavior, persisted security settings, MFA attempt controls, 404 contracts, DB failure signaling, case timestamp transitions, and scoped child-process cleanup.

Targeted QA75 tests: 21/21 PASS.
Full regression suite after code changes: 132/132 PASS.
