# QA85 - Language switching runtime fix

Asset revision: **70403**

## Fixed

- Fixed a MutationObserver feedback loop in the trilingual UI runtime. Attribute translations now call `setAttribute()` only when the value actually changes.
- Added a delegated `change` handler for both language selectors, so switching continues to work after UI refresh/re-render.
- Wrapped localStorage access in safe guards. If WebView2 storage is unavailable, language switching still works for the current session instead of aborting the i18n script.
- Added missing login-screen translations for English and Simplified Chinese, including username/password placeholders and the Windows/LAN capability bullets.
- Language selection remains synchronized between the login selector and the in-app selector.

## Validation

- Runtime browser smoke test verifies Vietnamese -> English -> Simplified Chinese -> Vietnamese switching.
- Dynamic DOM content added after switching language is translated by the MutationObserver without entering an attribute loop.
