# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 6.x 单文件无控制台打包配置

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('resources/app.ico', 'resources')],
    hiddenimports=[
        'core', 'core.portal', 'core.network', 'core.config', 'core.credential',
        'core.daemon', 'core.autostart',
        'app', 'app.main_window', 'app.tray', 'app.settings_dialog',
        'app.log_dialog', 'app.theme', 'app.widgets', 'app.icons',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='校园网自动登录',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/app.ico',
)
