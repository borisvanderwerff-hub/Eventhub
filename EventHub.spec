# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('server')


a = Analysis(
    ['bezoekerslijst_app.py'],
    pathex=[],
    binaries=[],
    datas=[('templates', 'templates'), ('eventhub_logo.png', '.'), ('eventhub_icon.png', '.'), ('eventhub.ico', '.'), ('settings_gear.png', '.'), ('assets/sidebar', 'assets/sidebar'), ('assets/backgrounds', 'assets/backgrounds'), ('server/web/templates', 'server/web/templates'), ('server/web/static', 'server/web/static'), ('server/assets', 'server/assets'), ('browser_extension', 'browser_extension')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EventHub',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['eventhub.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EventHub',
)
