# QA78 - CSV/Excel export + destination picker

Asset revision: 70396

## Changes
- Every Workbench table now provides both **Xuất CSV...** and **Xuất Excel...** actions.
- Export actions open the native Windows folder picker through pywebview/WebView2.
- The selected folder is represented by a short-lived one-time token; the browser cannot submit an arbitrary filesystem path.
- CSV and XLSX files are written directly to the selected directory. Existing files are not overwritten; a timestamp suffix is added when necessary.
- Operations Report Excel and Security Snapshot CSV/Excel use the same destination-picker workflow.
- If the user cancels the folder picker, no file is created.

## Validation
- Regression suite includes native bridge wiring, one-time destination token, CSV write, XLSX write/read-back, endpoint authorization and UI action coverage.
