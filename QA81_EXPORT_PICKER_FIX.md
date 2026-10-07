# QA81 - Export picker reliability fix

- Fixed CSV/Excel export failing with `Hộp chọn thư mục Windows chưa sẵn sàng`.
- New local endpoint: `POST /api/desktop/export-directory`.
- The endpoint opens the real Windows directory chooser without depending on `window.pywebview.api`.
- Primary picker: pywebview native window callback registered by the Desktop launcher.
- Fallback picker: hidden PowerShell + WinForms `FolderBrowserDialog`.
- Cancelling the dialog is not treated as an error.
- Destination authorization still uses a short-lived, one-time token.
- Asset revision: `70399`.
