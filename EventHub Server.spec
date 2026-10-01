# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
import os
import sys

# Voorkom dat hulpprogramma's op PATH verouderde runtime-DLL's meeleveren.
os.environ['PATH'] = os.pathsep.join([sys.base_prefix, os.path.join(os.environ['SystemRoot'], 'System32'), os.environ['SystemRoot']])

hiddenimports = []
hiddenimports += collect_submodules('server', filter=lambda name: name != 'server.tests' and not name.startswith('server.tests.'))


a = Analysis(
    ['server/manager/main.py'],
    pathex=[],
    binaries=[],
    datas=[('server/web/templates', 'server/web/templates'), ('server/web/static', 'server/web/static'), ('server/assets', 'server/assets')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['server.tests'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EventHub Server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=bool(os.environ.get('EVENTHUB_BUILD_CONSOLE')),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['server/assets/eventhub_server.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EventHub Server',
)
