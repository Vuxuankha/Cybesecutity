# QA84 - Trilingual UI

Asset revision: **70402**

## New language selector

NetworkAutomation Desktop now includes a persistent language selector in both the login screen and the main application header:

- 🇻🇳 **Tiếng Việt** (`vi-VN`) - default
- 🇨🇳 **中文（简体）** (`zh-CN`)
- 🇬🇧 **English** (`en-GB`)

The selected language is stored locally in `localStorage` under `na_language` and is restored on the next launch.

## Translation behavior

- Main navigation groups and feature names are translated.
- Login controls, common buttons, dialogs, notices, table headers, network diagnostics labels and Windows Local Tools labels are translated dynamically.
- Content rendered after login is translated through a DOM mutation observer, so a page reload is not required when switching language.
- The system clock follows the selected locale.
- Raw operational data is intentionally excluded from translation: IP/MAC addresses, host names, terminal/PowerShell output, code blocks, preformatted logs and textarea contents remain unchanged.

## Safety / architecture

The implementation is entirely local and does not call any external translation service. It therefore does not send operational data, logs or credentials to a translation API.

## QA

QA84 adds regression coverage for:

- load order of `i18n84.js` before `app.js`;
- all three language choices;
- persistent local language selection;
- dynamic DOM translation;
- raw-output exclusion;
- locale-aware live clock;
- presence of translated navigation/network labels.
