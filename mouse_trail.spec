# -*- mode: python ; coding: utf-8 -*-
import os
import shutil

_src_icon = os.path.join(SPECPATH, '1.ico')
_build_dir = os.path.join(SPECPATH, 'build')
os.makedirs(_build_dir, exist_ok=True)
# 复制到 ASCII 路径，避免 PyInstaller 在中文路径下偶发读取失败
icon_file = os.path.join(_build_dir, 'app_icon.ico')
shutil.copy2(_src_icon, icon_file)

a = Analysis(
    ['mouse_trail.pyw'],
    pathex=[],
    binaries=[],
    datas=[('1.ico', '.')],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='mouse_trail',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)
