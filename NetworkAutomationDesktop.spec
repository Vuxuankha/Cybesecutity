# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
for package in ('webapi', 'modules', 'database', 'webview', 'uvicorn', 'pysnmp'):
    hiddenimports += collect_submodules(package)

# Some optional backends should not be pulled into the release when unused.
excludes = ['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'cefpython3', 'matplotlib', 'notebook']

datas = [
    ('webapi/static', 'webapi/static'),
    ('tools/daily_audit', 'tools/daily_audit'),
    ('templates', 'templates'),
]

a = Analysis(
    ['desktop_launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NetworkAutomation',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='windows_version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='NetworkAutomation',
)
